import logging
from google.adk.agents import LlmAgent, BaseAgent
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

async def run(self, ctx: Any, **kwargs) -> AsyncGenerator[Event, None]:
    """
    Main entry point for the ForecastingAgent.
    Parses the user request, forecasts demand, and returns a summary.
    """
    # Get user input from ctx.user_content
    user_input = ctx.user_content.parts[0].text if ctx.user_content and ctx.user_content.parts else ""

    # Extract SKU from user input
    try:
        user_request = {}
        parts = user_input.split()
        sku_index = parts.index("SKU") + 1
        user_request["sku"] = parts[sku_index]
        sku = user_request["sku"].replace("'","")
    except IndexError:
        error_message = "Invalid user input. Please specify the SKU."
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=error_message)])
        )
        return

    # Set static start date for promotions
    promo_start_date = (datetime(2025, 5, 1) - timedelta(days=30)).strftime("%Y-%m-%d")
    promo_end_date = (datetime(2025, 5, 1) + timedelta(days=30)).strftime("%Y-%m-%d")

    # Get data using tools - Corrected to use ctx.tool_call
    base_forecast = await get_base_sales_data_tool(sku=sku, location="", context=ctx)
    promotions_result = await get_sku_promotions_tool(
        sku=sku, start_date=promo_start_date, end_date=promo_end_date, context=ctx
    )
    weather_result = get_weather_forecast_tool.func(location="Los Angeles")

    # Process tool results
    if promotions_result["status"] == "success":
        promotions_summary = promotions_result.get("promotions_summary", "None")
    else:
        promotions_summary = "Error: " + promotions_result.get("error_message", "Unknown error")

    weather_string = weather_result.get("weather", {})

    final_results = calculate_final_forecast_tool.func(base_forecast=base_forecast, promotions_summary=promotions_summary, weather=weather_string)
    final_forecasted_result = final_results.get("forecasted_demand", "Forecast Error")
    final_critical_spike = final_results.get("is_critical_spike", "Critical Spike Error")

    yield Event(
        author=self.name,
        content=types.Content(parts=[types.Part(text=f"Forecasted demand: {final_forecasted_result}")]),
    )
    # Create and yield an event with the forecast summary and state updates
    yield Event(
        author=self.name,
        content=types.Content(parts=[types.Part(text=f"Critical Spike: {final_critical_spike}")]),
    )


async def run(self, ctx: Any) -> AsyncGenerator[Event, None]:
    """
    Main entry point for the InventoryAgent.
    Checks inventory, open orders, supplier capacity, and PO placement.
    Returns the message and the inventory_action_output.
    """
    # Access the demand_forecast_output from the session state
    forecast_output = ctx.session.state.get("demand_forecast_output")

    if not forecast_output:
        output = {"status": "error", "message": "Demand forecast output not found in session state."}
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text="Error: Demand forecast not available.")]),
            actions=EventActions(state_delta={"inventory_action_output": output})
        )
        return

    # Parse the forecast summary to extract the SKU, forecasted demand, and forecast period start date
    try:
        import re
        sku_match = re.search(r"SKU: (\S+)", forecast_output)
        forecast_start_match = re.search(r"Forecast Start Date: (\d{4}-\d{2}-\d{2})", forecast_output)
        forecasted_demand_match = re.search(r"Forecasted Demand: (\d+)", forecast_output)

        if sku_match and forecast_start_match and forecasted_demand_match:
            sku = sku_match.group(1)
            forecast_period_start = forecast_start_match.group(1)
            forecasted_demand = int(forecasted_demand_match.group(1))
        else:
            output = {
                "status": "error",
                "message": "Could not parse forecast summary.",
            }
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="Error: Could not parse forecast summary.")]),
                actions=EventActions(state_delta={"inventory_action_output": output})
            )
            return
    except Exception as e:
        print(f"Error parsing forecast summary: {e}")

    
    # 1. Check current inventory
    inventory_result = get_inventory_for_sku_tool.func(sku=sku)
    if inventory_result["status"] == "error":
        output = {"status": "error", "message": inventory_result["error_message"]}
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=f"Error: {inventory_result['error_message']}")]),
            actions=EventActions(state_delta={"inventory_action_output": output})
        )
        return
    on_hand = inventory_result.get("on_hand", 0)
    
    # 2. Check for open orders
    open_orders_result = check_open_orders_tool.func(sku=sku)

    if open_orders_result["status"] == "error":
        output = {"status": "error", "message": open_orders_result["error_message"]}
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=f"Error: {open_orders_result['error_message']}")]),
            actions=EventActions(state_delta={"inventory_action_output": output})
        )
        return
    open_orders_quantity = open_orders_result.get("open_orders_quantity", 0)
    
    # 3. Calculate total replenishment need
    total_on_hand = on_hand
    replenishment_needed = calculate_replenishment_need_tool.func(forecasted_demand=forecasted_demand, total_on_hand=total_on_hand, open_orders_quantity=open_orders_quantity)
    if replenishment_needed <= 0:
        output = {"sku": sku, "Action Taken": "NO_REPLENISHMENT_NEEDED", "reason": "Forecasted demand is covered by current inventory and open orders."}
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text="Forecasted demand is covered by current inventory and open orders. No replenishment needed.")]),
            actions=EventActions(state_delta={"inventory_action_output": output})
        )
        return

    # 4. Verify supplier capacity
    supplier_capacity_result = get_supplier_capacity_tool.func(sku=sku)
    if supplier_capacity_result["status"] == "error":
        output = {"status": "error", "message": supplier_capacity_result["error_message"]}
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=f"Error: {supplier_capacity_result['error_message']}")]),
            actions=EventActions(state_delta={"inventory_action_output": output})
        )
        return

    max_units_per_day = math.ceil(supplier_capacity_result.get("max_units_per_day", 0))
    supplier_name = supplier_capacity_result.get("supplier_name", "N/A") # Extract supplier name

    if not max_units_per_day: # This check might be redundant if supplier_name is N/A and max_units is 0 from tool
        output = {"sku": sku, "Action Taken": "NO_SUPPLIER_FOUND", "reason": f"Supplier capacity not found for {sku}"}
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=f"Supplier capacity not found for {sku}. No replenishment possible.")]),
            actions=EventActions(state_delta={"inventory_action_output": output})
        )
        return
    
    # 5. Place order, the tool handles the comparison
    po_result = place_po_tool.func(
        sku=sku,
        replenishment_needed=replenishment_needed,
        max_units_per_day=max_units_per_day,
        supplier_name=supplier_name
    )
    po_message = po_result.get("message", "UNKNOWN"),
    action_taken = po_result.get("action_taken", "UNKNOWN"),
    output = {
        "SKU": sku,
        "Action Taken": po_result.get("action_taken", "UNKNOWN"),
        "On Hand": on_hand,
        "Open Orders": open_orders_quantity,
        "Replenishment Needed": replenishment_needed,
        "Supplier Capacity": max_units_per_day,
        "PO Result": po_message,
    }
    yield Event(
        author=self.name,
        content=types.Content(parts=[types.Part(text=po_result.get("message", "Order processing complete."))]),
        actions=EventActions(state_delta={"inventory_action_output": action_taken})
    )



async def run(self, ctx: Any) -> AsyncGenerator[Event, None]:
    """
    Main entry point for the MarketingAgent.
    Checks for active promotions and recommends pausing them if urgent replenishment is needed and the system is under strain.
    """
    inventory_summary = ctx.session.state.get("inventory_action_output")
    if not inventory_summary:
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text="Error: Inventory action output not found in session state.")])
        )
        return

    try:
        import re
        sku_match = re.search(r"SKU: (\S+)", inventory_summary)

        if sku_match:
            sku = sku_match.group(1)
        else:
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="Error: Could not parse inventory summary.")]),
            )
            return
    except Exception as e:
        print(f"Error parsing inventory summary: {e}")

    # 1. Check for active promotions

    # Set static start date for promotions
    promo_start_date = (datetime(2025, 5, 1) - timedelta(days=30)).strftime("%Y-%m-%d")
    promo_end_date = (datetime(2025, 6, 1) + timedelta(days=30)).strftime("%Y-%m-%d")

    # Get data using tools
    promotions_result = get_sku_promotions_tool.func(sku=sku, start_date=promo_start_date, end_date=promo_end_date)

    if promotions_result["status"] == "error":
        message = f"Error retrieving promotions: {promotions_result['error_message']}"
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=message)]),
            actions=EventActions(state_delta={"marketing_decision_output": {"action_taken": "ERROR", "reason": message}})
        )
        return

    promotions = promotions_result["promotions"]
    if not promotions:
        message = "No active promotions found."
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=message)]),
            actions=EventActions(state_delta={"marketing_decision_output": {"action_taken": "NO_ACTIVE_PROMOTION", "reason": message}})
        )
        return

    # 2. Pausing the promotion (pausing the first promotion found)
    promotion_name = promotions[0]["PromotionName"]
    # customer_name_param is no longer passed;
    # pause_promo_tool will get it from config directly.
    pause_result = pause_promo_tool.func(
        promotion_name=promotion_name,
        sku=sku
    )
    simulated_email_content = "Could not retrieve simulated email content."
    email_file_path_for_message = pause_result.get('simulated_email_path', 'N/A')

    if pause_result.get("simulated_email_path"):
        try:
            # The path from pause_promo_tool is "multi_tool_agent/output/..." which is relative to CWD.
            full_email_path = pause_result["simulated_email_path"]
            if os.path.exists(full_email_path): 
                with open(full_email_path, "r") as f:
                    simulated_email_content = f.read()
            else:
                simulated_email_content = f"Simulated email file not found at: {full_email_path}"
        except Exception as e:
            simulated_email_content = f"Error reading simulated email: {e}"

    if pause_result["status"] == "success":
        main_message = f"Due to system strain, paused active promotion '{promotion_name}' for {sku}."
        full_event_message = (
            f"{main_message}\nRecommend sending the following communication to relevant stakeholders "
            f"(simulated email saved to {email_file_path_for_message}):\n\n"
            f"{simulated_email_content}"
        )
        output = {
            "action_taken": "PROMOTION_PAUSE",
            "promotion_name": promotion_name,
            "reason": main_message, # Original concise reason
            "simulated_email_path": email_file_path_for_message,
            "email_content_preview": simulated_email_content[:200] + "..." if len(simulated_email_content) > 200 else simulated_email_content,
            "sku": sku
        }
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=full_event_message)]), # Yield the full message
            actions=EventActions(state_delta={"marketing_decision_output": output})
        )
    else:
        message = f"Failed to pause promotion '{promotion_name}' for {sku}. Error: {pause_result.get('message')}"
        output = {
            "action_taken": "PROMOTION_PAUSE_FAILED",
            "promotion_name": promotion_name,
            "reason": message,
            "pause_result": pause_result,
            "sku": sku
        }
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=message)]),
            actions=EventActions(state_delta={"marketing_decision_output": output})
        )
    return