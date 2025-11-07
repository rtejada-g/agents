import logging
import re
from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps import App
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field, ConfigDict
from typing import AsyncGenerator, Dict, List, Any
from typing_extensions import override
import pandas as pd
from datetime import datetime, timedelta
import math
import os # Ensure os is imported

# Import tools and utility functions
from .utils import (
    get_weather_forecast_tool,
    get_weather_forecast,
    get_base_sales_data_tool,
    get_sku_promotions_tool,
    get_inventory_for_sku_tool,
    check_open_orders_tool,
    get_supplier_capacity_tool,
    place_po_tool,
    pause_promo_tool,
    calculate_replenishment_need_tool,
    calculate_final_forecast_tool,
)

# --- Configure Logging ---
logging.getLogger("google.adk.cli.fast_api").setLevel(logging.WARNING)
logging.getLogger("google.adk.models.google_llm").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.WARNING)  # Mute the root logger

logger = logging.getLogger(__name__)

# Import configuration
from . import config

# --- Constants ---
APP_NAME = "supply_chain_team"
USER_ID = "user1"
MODEL_NAME = "gemini-2.0-flash"


class ForecastingAgent(LlmAgent):
    def __init__(self, name: str):
        super().__init__(
            name=name,
            model=MODEL_NAME,
            instruction=f"""You are a forecasting agent that predicts demand for a given SKU.
            **IMPORTANT: You MUST use the 'get_base_sales_data_tool', 'get_sku_promotions_tool', 'get_weather_forecast_tool', and 'calculate_final_forecast_tool', TOOLS. DO NOT attempt to generate code or call any other functions. You MUST ONLY use the tools provided, and use EACH ONE ONLY ONCE**
            1. Parse the user's request to extract the SKU
            2. The forecast start date is always 2025-05-01, and the end date is 2025-05-14
            3. Use the `get_base_sales_data_tool` tool to retrieve a base forecast based on historical sales data for the SKU.
            4. Use the `get_sku_promotions_tool` tool to get any active promotions for the SKU during the forecast period. 
            5. Use the `get_weather_forecast_tool` tool to get the weather forecast for the next 14 days. (default to Los Angeles)
            6. You will then use the outputs of the first three to call the `calculate_final_forecast_tool` tool to get the final forecast.  This result is deterministic. Do NOT attempt do do your own calculations. 
            8. Only produce an output when done with all function/tool calls and have a final result.
            9. The output should be a concise bullet-point summary:
            Example:
            User: "Forecast demand for SKU NOVA-P1 for the next 14 days"
            Output:
            * SKU: (from sku)
            * Forecast Start Date: 2025-05-01 
            * Forecast End Date: 2025-05-14 
            * Promotions:(from promotions_summary)
            * Weather: (Short sentence describing weather_string including if it's favorable)
            * Forecasted Demand: (A single number, strictly from final_forecasted_result)
            * Critical Spike: (STRICTLY from final_critical_spike, either True or False)
            """,
            tools=[
                get_base_sales_data_tool,
                get_sku_promotions_tool,
                get_weather_forecast_tool,
                calculate_final_forecast_tool,
            ],
            output_key="demand_forecast_output",
        )

class InventoryAgent(LlmAgent):
    def __init__(self, name: str):
        super().__init__(
            name=name,
            model=MODEL_NAME,
            instruction="""You are an inventory management agent.
            **IMPORTANT: You MUST use your existing TOOLS to retrieve data. DO NOT attempt to generate code or call any other functions. You MUST ONLY use the tools provided, and use EACH ONE ONLY ONCE**
            1. Use `get_inventory_for_sku_tool` to check the on_hand for the SKU across all locations.
            2. Use `check_open_orders_tool` to check for any existing purchase orders for the SKU.
            4. Use `calculate_replenishment_need_tool` to check for replenishment need
            5. Use `get_supplier_capacity_tool` to check the supplier capacity for the SKU, which will help decide if the PO action needs to be flagged as partial
            7. A PO would be placed with `place_po_tool`
            8. Only after all of these processes are completed, return a concise summary of the actions taken and whether systemic strain was detected.
            The summary MUST follow this format:
            * SKU: <SKU>
            * Action Taken: <action_taken> (exclusively formated as one of the four options: NEW_PO_PLACED, PARTIAL_REPLENISHMENT, NO_SUPPLIER_FOUND, or NO_REPLENISHMENT_NEEDED)
            * On Hand: <on_hand>
            * Open Orders: <open_orders_quantity>
            * Replenishment Needed: <replenishment_needed>
            * Supplier Capacity: <max_units_per_day>
            * PO Result: <po_message>
            * Generated PO PDF Path: <pdf_path_from_place_po_tool_response_or_None_if_no_PO>
            """,
            tools=[
                get_inventory_for_sku_tool,
                check_open_orders_tool,
                get_supplier_capacity_tool,
                calculate_replenishment_need_tool,
                place_po_tool,
            ],
            output_key="inventory_action_output",
        )

class MarketingAgent(LlmAgent):
    def __init__(self, name: str):
        super().__init__(
            name=name,
            model=MODEL_NAME,
            instruction=f"""
            You are a marketing agent responsible for managing promotions.
            Your goal is to determine if a promotion for a given SKU should be paused due to system strain.
            System strain is indicated if the 'inventory_action_output' (from session state, provided by the InventoryAgent) shows 'Action Taken: PARTIAL_REPLENISHMENT'.

            **Workflow:**
            1. Retrieve the 'inventory_action_output' from the session state. This contains the SKU and action taken by the InventoryAgent.
            2. Parse 'inventory_action_output' to find the SKU and the 'Action Taken' field.
            - If 'inventory_action_output' is not found or cannot be parsed for SKU, state that the inventory summary is missing or invalid and stop.
            3. Determine if there is system strain: Check if 'Action Taken' is 'PARTIAL_REPLENISHMENT'.
            4. If there IS system strain ('Action Taken: PARTIAL_REPLENISHMENT'):
                a. Use the `get_sku_promotions_tool` to check for any active promotions for the extracted SKU. Use a wide date range (e.g., today +/- 30 days like 2025-05-01 to 2025-07-01 if today is around 2025-06-01) to ensure all relevant promotions are caught.
                b. If active promotions are found for the SKU:
                    i. **First, you MUST explicitly call the `pause_promo_tool`** for the first active promotion found. Ensure this tool call is yielded so it can be executed.
                    ii. **After the `pause_promo_tool` has been executed and you have received its response (which will include `simulated_email_path` and `simulated_email_content`), then, as a separate step, you MUST formulate your final comprehensive message.** This message must include:
                        - Confirmation that the promotion was paused (e.g., "Due to system strain, paused active promotion '[Promotion Name]' for SKU [SKU].")
                        - A recommendation to send communication, mentioning the saved email path (e.g., "Recommend sending the following communication to relevant stakeholders (email saved to [simulated_email_path]):")
                        - The FULL content of the simulated email (from the `simulated_email_content` field that was in the `pause_promo_tool`'s response).
                        The customer's name is {config.CUSTOMER_NAME or config.DEFAULT_NAME}
                        Example final response format:
                        "Due to system strain, paused active promotion [Promotion Name] for SKU [SKU Name].
                        Recommend sending the following communication to relevant stakeholders:

                        To: supply_chain_manager@customer_domain.com
                        From: automated_system@customer_domain.com
                        Subject: Promotion Paused: [Promotion Name] for SKU [SKU Name]
                        Date: [Current Date and time]

                        Dear [Customer Name] Team,

                        This is an automated notification to inform you that the following promotion has been paused due to system strain and potential stock shortages for [Customer Name]:

                        Promotion Name: [Promotion Name]
                        SKU: [SKU Name]

                        Please review inventory levels and supplier capacity.

                        Regards,
                        [Customer Name] Automated Supply Chain Agent"
                c. If no active promotions are found for the SKU experiencing strain, state that "No active promotions found for SKU [SKU Name], although system strain was detected."
            5. If there is NO system strain (i.e., 'Action Taken' is not 'PARTIAL_REPLENISHMENT'), state that "No system strain detected from inventory actions. No marketing intervention required for promotions."

            **IMPORTANT: You MUST use your existing TOOLS. DO NOT attempt to generate code or call any other functions. You MUST ONLY use the tools provided.**
            Only produce an output when all steps are complete and you have a final message to deliver.
            """,
            tools=[get_sku_promotions_tool, pause_promo_tool],
        )

class SupplyChainAgent(BaseAgent):
    """
    Custom agent to conditionally execute replenishment and marketing agents.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    forecasting_agent: LlmAgent = Field(description="Forecasting agent")
    inventory_agent: LlmAgent = Field(description="Inventory replenishment agent")
    marketing_agent: LlmAgent = Field(description="Marketing agent")
    tools: List[Any] = Field(default_factory=list)  # Add a tools attribute

    def __init__(self, name: str, forecasting_agent: LlmAgent, inventory_agent: LlmAgent, marketing_agent: LlmAgent, tools: List[Any] = None): # noqa: E501
        super().__init__(
            name=name,
            forecasting_agent=forecasting_agent,
            inventory_agent=inventory_agent,
            marketing_agent=marketing_agent,
            description="Conditionally executes replenishment and marketing agents based on demand forecast. Can also provide weather information.",
            sub_agents=[forecasting_agent, inventory_agent, marketing_agent],
        )
        self.tools = tools or []  # Initialize the tools attribute

    @override
    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
        """
        Executes sub-agents conditionally based on the demand forecast.
        """
        # Clear relevant keys from session state at the beginning of each run
        ctx.session.state["demand_forecast_output"] = None
        ctx.session.state["inventory_action_output"] = None
        ctx.session.state["marketing_decision_output"] = None

        # Get the user query from ctx.user_content
        user_query = ctx.user_content.parts[0].text if ctx.user_content and ctx.user_content.parts else ""
        user_query_lower = user_query.lower()

        # Handle simple greetings
        # Use regex word boundaries to ensure "hello" or "hi" are matched as whole words
        if re.search(r"\bhello\b", user_query_lower) or re.search(r"\bhi\b", user_query_lower):
            # Use constants from config module
            resolved_customer_name = config.CUSTOMER_NAME or config.DEFAULT_NAME
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"Hello! I'm a {resolved_customer_name} Supply Chain Agent. How can I assist you today?")])
            )
            return

        # Route the request based on the user input
        if "weather in" in user_query_lower:
            # Weather query: Use the get_weather_forecast_tool directly
            location = user_query_lower.split("weather in ")[1].strip()
            # Yield an event BEFORE calling the tool
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"Getting weather forecast for {location}")])
            )
            weather_forecast_result = get_weather_forecast(location)
            if weather_forecast_result["status"] == "success":
                weather_forecast = weather_forecast_result["weather"]
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text=f"The weather in {location} is: {weather_forecast['current']['temperature_2m']}°C, wind speed {weather_forecast['current']['wind_speed_10m']} m/s.")])
                )
            else:
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text=f"Could not retrieve weather for {location}. Error: {weather_forecast_result.get('error_message', 'Unknown error')}")])
                )
            print("End of WEATHER QUERY")
            return  # exit after handling the weather query

        # 1. Forecasting
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="Running Forecasting Agent... ")]))

        # Call the forecasting agent's run method
        async for event in self.forecasting_agent.run_async(ctx):\
            yield event

        # 2. Inventory (if critical spike)
        forecast_summary = ctx.session.state.get("demand_forecast_output")
        is_critical_spike = False  # Default value

        if forecast_summary:
            # Parse the summary to extract the is_critical_spike value
            try:
                # Use a regular expression to find the "Critical Spike: True/False" part
                match = re.search(r"Critical Spike: (True|False)", forecast_summary)
                if match:
                    is_critical_spike = match.group(1) == "True"
            except Exception as e:
                print(f"Error parsing forecast summary: {e}")

        trigger_marketing = False 

        if is_critical_spike:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="Critical spike detected. Running Inventory Agent...")])
            )

            # --- FIX: Create a new, specific context for the InventoryAgent ---
            # Extract SKU from the forecast summary to pass a clear instruction
            sku_match = re.search(r"\* SKU: ([\w-]+)", forecast_summary)
            sku = sku_match.group(1) if sku_match else "UNKNOWN"
            
            inventory_context = ctx.copy(
                update={
                    "user_content": types.Content(
                        parts=[
                            types.Part(
                                text=f"Handle inventory for SKU {sku}"
                            )
                        ]
                    )
                }
            )
            # --- END FIX ---

            # Call the inventory agent's run method and capture its summary from events
            inventory_agent_final_summary = ""
            async for event in self.inventory_agent.run_async(inventory_context):
                yield event # Forward to UI
                if event.author == self.inventory_agent.name and event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.function_response and part.function_response.name == "place_po":
                            print(f"Found functionResponse from place_po_tool: {part.function_response}")
                            if part.function_response.response and part.function_response.response.get("pdf_path"):
                                pdf_path = part.function_response.response["pdf_path"]
                                print(f"Extracted pdf_path: {pdf_path}")
                                ctx.session.state["generated_po_pdf_path"] = pdf_path
                        if part.text:
                            inventory_agent_final_summary += part.text + "\n"
            
            if inventory_agent_final_summary:
                logger.info(f"Captured InventoryAgent summary: {inventory_agent_final_summary}")
            
            # After InventoryAgent has finished, use the captured summary for parsing.
            # Fallback to session state only if event capture yielded nothing at all.
            inventory_summary_text_to_parse = inventory_agent_final_summary
            if not inventory_summary_text_to_parse:
                inventory_summary_text_to_parse = ctx.session.state.get("inventory_action_output")
                if inventory_summary_text_to_parse:
                    logger.warning("Falling back to session state for inventory_action_output as event capture was empty.")
                else:
                    logger.warning("InventoryAgent summary not found in events or session state.")

            if inventory_summary_text_to_parse:
                logger.info(f"Inventory Agent Output for parsing: {inventory_summary_text_to_parse}")

                # Get the PDF path from the session state
                pdf_path = ctx.session.state.get("generated_po_pdf_path")
                print(f"Retrieved PDF path from session state: {pdf_path}")
                if pdf_path and pdf_path.lower() != "none":
                    try:
                        logger.info(f"Attempting to read PDF artifact from: {pdf_path}")
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        
                        # Correctly save artifact using artifact_service from InvocationContext
                        # and prepare EventActions
                        if ctx.artifact_service:
                            version = await ctx.artifact_service.save_artifact(
                                app_name=ctx.app_name,
                                user_id=ctx.user_id,
                                session_id=ctx.session.id,
                                filename=os.path.basename(pdf_path),
                                artifact=types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
                            )
                            event_actions = EventActions()
                            event_actions.artifact_delta[os.path.basename(pdf_path)] = version
                            # Yield an event with only actions, no text content,
                            # so the UI creates a dedicated message for the artifact.
                            print(f"Event actions before yielding: {event_actions.model_dump_json()}")
                            yield Event(
                                author=self.name,
                                invocation_id=ctx.invocation_id,
                                actions=event_actions,
                                content=types.Content(parts=[types.Part()])
                            )
                            logger.info(f"Successfully saved PDF artifact: {os.path.basename(pdf_path)}, version {version}. Event yielded with artifactDelta.")
                        else:
                            logger.error("Artifact service not available in InvocationContext.")
                            yield Event(
                                author=self.name,
                                invocation_id=ctx.invocation_id,
                                content=types.Content(parts=[types.Part(text="Error: Artifact service not available.")])
                            )
                    except FileNotFoundError:
                        logger.error(f"PDF file not found at path: {pdf_path}")
                        yield Event(
                            author=self.name,
                            invocation_id=ctx.invocation_id,
                            content=types.Content(parts=[types.Part(text=f"Error: PDF file not found at {pdf_path}.")]) # noqa: E501
                        )
                    except Exception as e:
                        logger.error(f"Error saving PDF artifact from path {pdf_path}: {e}")
                        yield Event(
                            author=self.name,
                            invocation_id=ctx.invocation_id,
                            content=types.Content(parts=[types.Part(text=f"Error saving PDF artifact: {e}.")])
                        )
                else:
                    logger.info("No PDF path found or path was 'None' in session state.")

                # Determine marketing trigger
                action_taken_match = re.search(r"\* Action Taken:\s*(PARTIAL_REPLENISHMENT)", inventory_summary_text_to_parse) # Added \s*
                if action_taken_match:
                    trigger_marketing = True
                else:
                    action_taken_value_match = re.search(r"\* Action Taken:\s*([^\n]+)", inventory_summary_text_to_parse) # Added \s*
                    action_taken_value = action_taken_value_match.group(1).strip() if action_taken_value_match else "Not Found" # Added strip()
                    logger.info(f"Marketing trigger not met. Action Taken: {action_taken_value}")
            else:
                logger.warning("Inventory_action_output (from event capture or state) was empty or None.")

        # 3. Marketing (if replenishment and system strain)
        if trigger_marketing:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="System strain detected. Running Marketing Agent... ")])
            )
            
            async for event in self.marketing_agent.run_async(ctx):
                yield event
        else:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="No system strain detected. No further action required.")])
            )

# --- Agent Initialization ---
forecasting_agent = ForecastingAgent(name="ForecastingAgent")
inventory_agent = InventoryAgent(name="InventoryAgent")
marketing_agent = MarketingAgent(name="MarketingAgent")

# Define the root agent for the demo pipeline
supplychain_agent = SupplyChainAgent(
    name="SupplyChainAgent",
    forecasting_agent=forecasting_agent,
    inventory_agent=inventory_agent,
    marketing_agent=marketing_agent,
)

# Export root_agent (required by agent loader)
root_agent = supplychain_agent

# Wrap in App with context caching enabled
# This applies caching to ALL agents in the app (Forecasting, Inventory, Marketing)
app = App(
    name="supply_chain_team",
    root_agent=supplychain_agent,
    context_cache_config=ContextCacheConfig(
        cache_intervals=10,      # Reuse cache for up to 10 conversation turns
        ttl_seconds=1800,        # 30-minute TTL (cache expires after inactivity)
        min_tokens=500           # Only cache if instruction + tools > 500 tokens
    )
)

# Note: Evaluation metrics are configured through the UI when running evaluations,
# not hardcoded in the agent. This allows flexibility to test different metrics
# and thresholds without modifying agent code.