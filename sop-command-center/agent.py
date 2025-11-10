"""
S&OP Command Center Agent

Main orchestrator for S&OP simulation and strategic decision-making.
Combines promotional impact analysis, inventory optimization, and
AI-driven recommendations.
"""

from google.adk.agents import BaseAgent
from google.adk.apps import App
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import Field, ConfigDict
from typing import AsyncGenerator, Any
from typing_extensions import override
import json
import asyncio

from . import config
from .tools import (
    search_promos,
    run_sop_simulation,
    generate_recommendations
)
from .prompts import system_prompts


class SOpCommandCenterAgent(BaseAgent):
    """
    Orchestrator for S&OP Command Center.
    
    Handles:
    - Promotional scenario selection and simulation
    - Inventory sufficiency analysis
    - Strategic recommendation generation
    - Conversational UI control via command tags
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, name: str = "SOpCommandCenter"):
        super().__init__(
            name=name,
            description=f"S&OP Command Center for {config.COMPANY_NAME}"
        )
    
    @override
    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
        """
        Main orchestration logic.
        
        Handles:
        1. Greeting messages
        2. JSON requests from UI (button clicks)
        3. Natural language queries (from assistant panel)
        """
        # Extract user message
        user_text = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                if part.text:
                    user_text = part.text
                    break
        
        user_text_lower = user_text.lower()
        
        # STEP 1: Handle greeting
        if "hello" in user_text_lower or "hi" in user_text_lower:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"""Welcome to the {config.COMPANY_NAME} S&OP Command Center! 🎯

I'm your AI assistant for strategic S&OP simulation and decision-making. I can help you:

• Analyze promotional impact on inventory
• Identify supply chain constraints
• Generate strategic recommendations
• Simulate "what-if" scenarios

**To get started:**
1. Select a promotional campaign from the left panel
2. Click "Run S&OP Simulation" to see the impact
3. Ask me questions about the results!

Or simply tell me what you'd like to explore.""")])
            )
            return
        
        # STEP 2: Try to parse as JSON (UI button click)
        try:
            request_data = json.loads(user_text)
            action = request_data.get("action")
            
            if action == "run_simulation":
                # Run S&OP simulation flow
                async for event in self._handle_simulation(ctx, request_data):
                    yield event
                return
            
            elif action == "get_promos":
                # Search for promotions
                result = search_promos(
                    week_date=request_data.get("week_date"),
                    sku=request_data.get("sku"),
                    campaign_theme=request_data.get("campaign_theme")
                )
                
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text=f"Found {result.get('count', 0)} promotions.")]),
                    actions=EventActions(
                        agent_state={
                            "custom_experience_data": {
                                "type": "promo_list",
                                "promos": result.get("promos", [])
                            }
                        }
                    )
                )
                return
            
            elif action == "approve_recommendation":
                # Handle recommendation approval
                recommendation_id = request_data.get("recommendation_id")
                promo_id = request_data.get("promo_id")
                
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text=f"✓ Recommendation approved! Re-running simulation with this solution...")]),
                    actions=EventActions(
                        agent_state={
                            "custom_experience_data": {
                                "type": "recommendation_approved",
                                "recommendation_id": recommendation_id,
                                "promo_id": promo_id
                            }
                        }
                    )
                )
                # TODO: Implement re-simulation logic in Task 7
                return
            
            elif action == "explore_alternative":
                # Handle alternative exploration request
                recommendation_id = request_data.get("recommendation_id")
                promo_id = request_data.get("promo_id")
                
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text="💡 To explore alternatives, please use the S&OP Assistant (coming in Phase 2) to ask specific questions about other options or constraints.")])
                )
                return
            
            elif action == "show_store_details":
                # Show detailed store information
                store_id = request_data.get("store_id")
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text=f"Showing details for store {store_id}. [SHOW_STORE] {store_id}")])
                )
                return
        
        except json.JSONDecodeError:
            # Not JSON, treat as natural language query
            pass
        
        # STEP 3: Handle natural language queries
        # Use LLM to interpret and respond with command tags
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text=f"""I can help you analyze promotions and inventory. Try:

• "Show me the Holiday Glow-Up campaign"
• "What's the impact of the November promotions?"
• "Which stores have inventory issues?"

Or click a promotion in the left panel to begin!""")])
        )
    
    async def _handle_simulation(self, ctx: Any, request_data: dict) -> AsyncGenerator[Event, None]:
        """
        Handle S&OP simulation workflow.
        
        Steps:
        1. Acknowledge request
        2. Run simulation tool
        3. Stream progress updates
        4. Generate recommendations if needed
        5. Return final results
        """
        promo_id = request_data.get("promo_id")
        stores = request_data.get("stores")  # Optional store filter
        
        print(f"[AGENT] _handle_simulation called for promo_id: {promo_id}")
        
        # Step 1: Acknowledge
        print(f"[AGENT] Yielding acknowledgment event...")
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="✨ Running S&OP simulation...")])
        )
        print(f"[AGENT] Acknowledgment event yielded")
        
        # Small delay for UI responsiveness
        await asyncio.sleep(0.2)
        
        # Step 2: Run simulation
        print(f"[AGENT] Calling run_sop_simulation for promo: {promo_id}")
        simulation_result = run_sop_simulation(promo_id=promo_id, stores=stores)
        print(f"[AGENT] run_sop_simulation returned: status={simulation_result.get('status')}")
        
        if simulation_result.get("status") != "success":
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"❌ Simulation error: {simulation_result.get('error')}")])
            )
            return
        
        # Step 3: Stream progress update with initial results
        kpis = simulation_result.get("kpis", {})
        stores_data = simulation_result.get("stores", [])
        
        print(f"[AGENT] Yielding progress event... (stores: {len(stores_data)})")
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="📊 Analyzing promotional impact...")]),
            actions=EventActions(
                agent_state={
                    "custom_experience_data": {
                        "type": "simulation_progress",
                        "promo_id": promo_id,
                        "percent": 50
                    }
                }
            )
        )
        print(f"[AGENT] Progress event yielded")
        
        await asyncio.sleep(0.3)
        
        # Step 4: Generate recommendations if stockouts detected
        recommendations = []
        stockouts = kpis.get("projected_stockouts", 0)
        at_risk = kpis.get("stores_at_risk", 0)
        
        print(f"[AGENT] Stockouts: {stockouts}, At risk: {at_risk}")
        
        if stockouts > 0 or at_risk > 0:
            print(f"[AGENT] Calling generate_recommendations...")
            try:
                rec_result = await generate_recommendations(simulation_result)
                print(f"[AGENT] generate_recommendations returned: status={rec_result.get('status')}")
                if rec_result.get("status") == "success":
                    recommendations = rec_result.get("recommendations", [])
                    print(f"[AGENT] Generated {len(recommendations)} recommendations")
                else:
                    print(f"[AGENT] Recommendation generation failed: {rec_result.get('error')}")
            except Exception as e:
                print(f"[AGENT] Error generating recommendations: {e}")
                import traceback
                traceback.print_exc()
                # Continue without recommendations
                recommendations = []
        else:
            print(f"[AGENT] Skipping recommendations (no stockouts or at-risk stores)")
        
        # Step 5: Final result with complete data
        stockout_count = kpis.get("projected_stockouts", 0)
        at_risk_count = kpis.get("stores_at_risk", 0)
        
        # Build executive summary
        summary_parts = [
            f"**{simulation_result.get('promo_name')}** simulation complete! 🎯\n"
        ]
        
        summary_parts.append(
            f"\n📈 **Impact:** ${kpis.get('incremental_sales', 0):,.0f} incremental sales "
            f"({kpis.get('promo_lift_percent', 0)}% lift)"
        )
        
        summary_parts.append(
            f"\n🏪 **Coverage:** {kpis.get('affected_stores', 0)} stores analyzed"
        )
        
        if stockout_count > 0:
            summary_parts.append(
                f"\n⚠️ **Alert:** {stockout_count} stores face stockout risk"
            )
        
        if at_risk_count > 0:
            summary_parts.append(
                f"\n⚡ **Watch:** {at_risk_count} additional stores at risk"
            )
        
        if not stockout_count and not at_risk_count:
            summary_parts.append(
                "\n✅ **Status:** All stores have sufficient inventory"
            )
        
        if recommendations:
            summary_parts.append(
                f"\n\n💡 **Recommendations:** {len(recommendations)} strategic options available in Panel 3"
            )
        
        summary_text = "".join(summary_parts)
        
        print(f"[AGENT] Preparing final event...")
        print(f"[AGENT] - Stores: {len(stores_data)}")
        print(f"[AGENT] - Recommendations: {len(recommendations)}")
        print(f"[AGENT] - Summary: {summary_text[:100]}...")
        
        print(f"[AGENT] Yielding final event...")
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text=summary_text)]),
            actions=EventActions(
                agent_state={
                    "custom_experience_data": {
                        "type": "simulation_result",
                        "promo_id": promo_id,
                        "promo_name": simulation_result.get("promo_name"),
                        "week_date": simulation_result.get("week_date"),
                        "sku": simulation_result.get("sku"),
                        "kpis": kpis,
                        "stores": stores_data,
                        "recommendations": recommendations
                    }
                }
            )
        )
        print(f"[AGENT] Final event yielded - simulation complete!")


# Initialize agent
root_agent = SOpCommandCenterAgent(name="SOpCommandCenter")

# Create app
app = App(
    name="sop-command-center",
    root_agent=root_agent,
)