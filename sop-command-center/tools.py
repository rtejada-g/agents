"""
Tools for S&OP Command Center Agent

Simulation and analysis tools for promotional impact assessment,
inventory optimization, and recommendation generation.
"""

import os
import csv
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from google.adk.tools import ToolContext
from google.genai import types
from google import genai

from . import config


# ============================================================================
# Shared GenAI Client (from aesthetic-to-routine pattern)
# ============================================================================

http_options = types.HttpOptions(
    async_client_args={'read_bufsize': 16 * 1024 * 1024}
)
shared_client = genai.Client(vertexai=True, http_options=http_options)


# ============================================================================
# DATA LOADING UTILITIES
# ============================================================================

def load_csv_data(filename: str) -> List[Dict[str, Any]]:
    """Load CSV data from the data directory."""
    file_path = os.path.join(
        os.path.dirname(__file__),
        f"data/{config.CUSTOMER_DATA_SET}/{filename}"
    )
    
    if not os.path.exists(file_path):
        print(f"[TOOLS] Warning: {filename} not found at {file_path}")
        return []
    
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    
    print(f"[TOOLS] Loaded {len(data)} rows from {filename}")
    return data


def clean_numeric_value(value: str) -> float:
    """
    Clean numeric values from CSV (remove $, %, commas).
    
    Examples:
        "18%" -> 18.0
        "$55.00" -> 55.0
        "1,234.56" -> 1234.56
    """
    if not value or value == '':
        return 0.0
    
    # Remove $, %, and commas
    cleaned = str(value).replace('$', '').replace('%', '').replace(',', '').strip()
    
    try:
        return float(cleaned)
    except ValueError:
        print(f"[TOOLS] Warning: Could not convert '{value}' to float, returning 0.0")
        return 0.0


def load_products() -> List[Dict[str, Any]]:
    """Load product catalog (from symlinked products.json)."""
    file_path = os.path.join(
        os.path.dirname(__file__),
        f"data/{config.CUSTOMER_DATA_SET}/products.json"
    )
    
    if not os.path.exists(file_path):
        print(f"[TOOLS] Warning: products.json not found at {file_path}")
        return []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # Handle both array format (new) and object format (legacy)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'products' in data:
            return data.get('products', [])
        else:
            print(f"[TOOLS] Warning: Unexpected products.json format: {type(data)}")
            return []


# ============================================================================
# TOOL 1: Search Promotions
# ============================================================================

def search_promos(
    week_date: Optional[str] = None,
    sku: Optional[str] = None,
    campaign_theme: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search promotional campaigns from PROMO_PLAN.
    
    Args:
        week_date: Filter by week date (YYYY-MM-DD format)
        sku: Filter by specific product SKU
        campaign_theme: Filter by campaign theme (partial match)
    
    Returns:
        Dictionary with status and list of matching promos
    """
    try:
        promo_data = load_csv_data("promo_plan.csv")
        
        if not promo_data:
            return {
                "status": "error",
                "error": "Promo plan data not loaded. Please ensure promo_plan.csv exists."
            }
        
        # Filter promos
        results = promo_data
        
        if week_date:
            results = [p for p in results if p.get('Week Date') == week_date]
        
        if sku:
            results = [p for p in results if p.get('SKU') == sku]
        
        if campaign_theme:
            theme_lower = campaign_theme.lower()
            results = [p for p in results if theme_lower in p.get('Campaign Theme', '').lower()]
        
        # Format results
        formatted_promos = []
        for promo in results:
            formatted_promos.append({
                "promo_id": f"{promo.get('Week Date')}_{promo.get('SKU')}",
                "week_date": promo.get('Week Date'),
                "product_focus": promo.get('Product Focus'),
                "sku": promo.get('SKU'),
                "brand": promo.get('Brand'),
                "campaign_theme": promo.get('Campaign Theme'),
                "target_audience": promo.get('Target Audience'),
                "current_price": clean_numeric_value(promo.get('Current Price', '0')),
                "promo_price": clean_numeric_value(promo.get('Decreased Promo Price', '0')),
                "demand_uplift_percent": clean_numeric_value(promo.get('Demand Uplift (%)', '0')),
                "current_margin": clean_numeric_value(promo.get('Current GrossMargin', '0')),
                "new_margin": clean_numeric_value(promo.get('New Gross New Margin', '0'))
            })
        
        return {
            "status": "success",
            "count": len(formatted_promos),
            "promos": formatted_promos
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": f"Error searching promos: {str(e)}"
        }


# ============================================================================
# TOOL 2: Run S&OP Simulation
# ============================================================================

def run_sop_simulation(
    promo_id: str,
    stores: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Core S&OP simulation logic.
    
    Analyzes promotional impact on inventory sufficiency across stores.
    
    Args:
        promo_id: Promotion identifier (format: YYYY-MM-DD_SKU)
        stores: Optional list of store IDs to analyze (default: all stores)
    
    Returns:
        Simulation results with KPIs and store-level inventory status
    """
    try:
        print(f"[SIMULATION] Starting simulation for {promo_id}")
        
        # Parse promo_id
        week_date, sku = promo_id.split('_', 1)
        print(f"[SIMULATION] Parsed: week_date={week_date}, sku={sku}")
        
        # Load data
        promo_data = load_csv_data("promo_plan.csv")
        store_data = load_csv_data("stores.csv")
        demand_data = load_csv_data("demand.csv")
        inventory_data = load_csv_data("inventory.csv")
        
        print(f"[SIMULATION] Data loaded: {len(promo_data)} promos, {len(store_data)} stores, {len(demand_data)} demand records, {len(inventory_data)} inventory records")
        
        # Find the specific promo
        promo = next((p for p in promo_data
                     if p.get('Week Date') == week_date and p.get('SKU') == sku), None)
        
        if not promo:
            print(f"[SIMULATION] ERROR: Promotion not found for {week_date}/{sku}")
            return {
                "status": "error",
                "error": f"Promotion not found: {promo_id}"
            }
        
        print(f"[SIMULATION] Found promo: {promo.get('Campaign Theme')}")
        
        # Clean numeric values from CSV (they have $ and % symbols)
        demand_uplift = clean_numeric_value(promo.get('Demand Uplift (%)', '0')) / 100
        promo_price = clean_numeric_value(promo.get('Decreased Promo Price', '0'))
        
        print(f"[SIMULATION] Uplift: {demand_uplift*100}%, Price: ${promo_price}")
        
        # Filter stores if specified
        if stores:
            store_data = [s for s in store_data if s.get('Synthetic ID') in stores]
            print(f"[SIMULATION] Filtered to {len(store_data)} stores")
        
        # Simulation results
        store_results = []
        total_incremental_sales = 0
        stockout_count = 0
        at_risk_count = 0
        
        print(f"[SIMULATION] Processing {len(store_data)} stores...")
        
        # Debug: Show sample demand data to verify format
        if demand_data:
            print(f"[SIMULATION] Sample demand record: {demand_data[0]}")
            print(f"[SIMULATION] Looking for week_date: '{week_date}', sku: '{sku}'")
        
        for idx, store in enumerate(store_data):
            if idx % 5 == 0:
                print(f"[SIMULATION] Processing store {idx+1}/{len(store_data)}")
            store_id = store.get('Synthetic ID')
            
            # Get baseline demand for this store/SKU
            baseline_demand = next(
                (clean_numeric_value(d.get('Demand', '0')) for d in demand_data
                 if d.get('Store ID') == store_id and d.get('SKU') == sku and d.get('Week Ending') == week_date),
                0.0
            )
            
            # Debug first store only
            if idx == 0:
                print(f"[SIMULATION] Store {store_id}, SKU {sku}:")
                print(f"[SIMULATION]   Baseline demand: {baseline_demand}")
                # Show matching demand records
                matching = [d for d in demand_data
                           if d.get('Store ID') == store_id and d.get('SKU') == sku]
                if matching:
                    print(f"[SIMULATION]   Found {len(matching)} demand records for this store/SKU")
                    print(f"[SIMULATION]   Sample weeks: {[d.get('Week Ending') for d in matching[:3]]}")
                else:
                    print(f"[SIMULATION]   ❌ NO demand records found for store {store_id}, SKU {sku}")
            
            # Calculate projected demand with uplift
            projected_demand = baseline_demand * (1 + demand_uplift)
            
            # Get current inventory
            current_inventory = next(
                (clean_numeric_value(inv.get('Current Inventory', '0')) for inv in inventory_data
                 if inv.get('Store ID') == store_id and inv.get('SKU') == sku),
                0.0
            )
            
            # Determine inventory status
            inventory_ratio = current_inventory / projected_demand if projected_demand > 0 else 1.0
            
            if inventory_ratio < config.STOCKOUT_THRESHOLD:
                inventory_status = "stockout"
                stockout_count += 1
            elif inventory_ratio < config.AT_RISK_THRESHOLD:
                inventory_status = "at_risk"
                at_risk_count += 1
            else:
                inventory_status = "sufficient"
            
            # Calculate incremental sales for this store
            store_incremental_sales = (projected_demand - baseline_demand) * promo_price
            total_incremental_sales += store_incremental_sales
            
            # Add store result (include lat/lng for map)
            store_results.append({
                "store_id": store_id,
                "store_name": store.get('Store Name'),
                "lat": float(store.get('Latitude', 40.7589)),  # Default to NYC center if missing
                "lng": float(store.get('Longitude', -73.9851)),
                "sku": sku,
                "baseline_demand": round(baseline_demand, 1),
                "projected_demand": round(projected_demand, 1),
                "current_inventory": round(current_inventory, 1),
                "inventory_status": inventory_status,
                "stockout_probability": round(max(0, 1 - inventory_ratio), 2),
                "incremental_sales": round(store_incremental_sales, 2)
            })
        
        print(f"[SIMULATION] Processed all {len(store_results)} stores")
        print(f"[SIMULATION] Stockouts: {stockout_count}, At risk: {at_risk_count}, Total sales: ${total_incremental_sales:,.2f}")
        
        # Calculate KPIs
        kpis = {
            "incremental_sales": round(total_incremental_sales, 2),
            "promo_lift_percent": round(demand_uplift * 100, 1),
            "affected_stores": len(store_results),
            "projected_stockouts": stockout_count,
            "stores_at_risk": at_risk_count
        }
        
        print(f"[SIMULATION] Simulation complete! Returning {len(store_results)} store results")
        
        return {
            "status": "success",
            "promo_id": promo_id,
            "promo_name": promo.get('Campaign Theme'),
            "week_date": week_date,
            "sku": sku,
            "kpis": kpis,
            "stores": store_results
        }
        
    except Exception as e:
        print(f"[SIMULATION] EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": f"Simulation error: {str(e)}"
        }


# ============================================================================
# TOOL 3: Generate Recommendations
# ============================================================================

async def generate_recommendations(
    simulation_result: Dict[str, Any],
    llm_model: str = "gemini-2.0-flash"
) -> Dict[str, Any]:
    """
    Generate strategic S&OP recommendations using LLM.
    
    Args:
        simulation_result: Output from run_sop_simulation
        llm_model: LLM model to use for generation
    
    Returns:
        List of recommendation objects
    """
    try:
        # Only generate recommendations if there are issues
        kpis = simulation_result.get('kpis', {})
        stockouts = kpis.get('projected_stockouts', 0)
        at_risk = kpis.get('stores_at_risk', 0)
        
        if stockouts == 0 and at_risk == 0:
            print("[TOOLS] No stockouts detected, skipping recommendations")
            return {
                "status": "success",
                "recommendations": []
            }
        
        # Build context for recommendations
        stores_at_risk = [s for s in simulation_result.get('stores', [])
                         if s['inventory_status'] in ['at_risk', 'stockout']]
        
        print(f"[TOOLS] Generating AI recommendations for {len(stores_at_risk)} at-risk stores")
        
        # Build prompt for LLM
        promo_name = simulation_result.get('promo_name', 'promotion')
        sku = simulation_result.get('sku', '')
        
        critical_stores_text = "\n".join([
            f"- {s['store_name']}: {s['current_inventory']:.0f} units vs {s['projected_demand']:.0f} demand (stockout risk: {s['stockout_probability']*100:.0f}%)"
            for s in sorted(stores_at_risk, key=lambda x: x['stockout_probability'], reverse=True)[:5]
        ])
        
        prompt = f"""You are an S&OP strategy advisor for Estée Lauder Companies.

SIMULATION RESULTS:
- Campaign: {promo_name}
- SKU: {sku}
- Total stores analyzed: {kpis.get('affected_stores', 0)}
- Stores with stockout risk: {stockouts}
- Stores at risk: {at_risk}
- Incremental sales opportunity: ${kpis.get('incremental_sales', 0):,.0f}

CRITICAL STORES:
{critical_stores_text}

YOUR TASK:
Generate 2-3 strategic recommendations to address these supply chain constraints.

RECOMMENDATION TYPES TO CONSIDER:
1. Supply-side solutions (expedited shipments, inventory transfers)
2. Demand-shaping solutions (product substitutes, alternative SKUs)
3. Promotional adjustments (timing changes, store selection)

OUTPUT FORMAT (JSON):
{{
  "recommendations": [
    {{
      "type": "supply|demand|promotion",
      "priority": "high|medium|low",
      "title": "Brief action title",
      "description": "1-2 sentence explanation",
      "estimated_impact": "Quantified benefit"
    }}
  ]
}}

Be specific, actionable, and data-driven. Focus on solutions that balance cost, speed, and customer impact."""

        # Call LLM using shared_client pattern
        response = await shared_client.aio.models.generate_content(
            model=llm_model,
            contents=prompt
        )
        
        response_text = response.text.strip()
        print(f"[TOOLS] LLM response: {response_text[:200]}...")
        
        # Parse LLM response
        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text
            
            llm_data = json.loads(json_text)
            llm_recommendations = llm_data.get("recommendations", [])
            
            # Enhance LLM recommendations with structured data
            recommendations = []
            for i, rec in enumerate(llm_recommendations[:3], 1):  # Max 3 recommendations
                structured_rec = {
                    "id": f"rec_{i:03d}",
                    "type": rec.get("type", "supply"),
                    "priority": rec.get("priority", "medium"),
                    "title": rec.get("title", "Strategic Recommendation"),
                    "description": rec.get("description", ""),
                    "impact": [
                        {"metric": "Estimated Impact", "value": rec.get("estimated_impact", "TBD")}
                    ],
                    "confidence": "high" if rec.get("priority") == "high" else "medium"
                }
                
                # Add store-specific data if available
                if stores_at_risk and rec.get("type") == "supply":
                    top_store = stores_at_risk[0]
                    structured_rec["store_id"] = top_store['store_id']
                
                recommendations.append(structured_rec)
            
            print(f"[TOOLS] ✓ Generated {len(recommendations)} AI recommendations")
            return {
                "status": "success",
                "recommendations": recommendations
            }
            
        except json.JSONDecodeError as e:
            print(f"[TOOLS] Failed to parse LLM JSON, falling back to rule-based: {e}")
            # Fall through to rule-based recommendations
        
    except Exception as e:
        print(f"[TOOLS] LLM recommendation error: {e}, falling back to rule-based")
    
    # Fallback: Generate rule-based recommendations
    print("[TOOLS] Using rule-based recommendations as fallback")
    recommendations = []
    
    # Supply-side recommendation
    if stores_at_risk:
        top_store = max(stores_at_risk, key=lambda s: s['stockout_probability'])
        shortfall = top_store['projected_demand'] - top_store['current_inventory']
        
        recommendations.append({
            "id": "rec_001",
            "type": "supply",
            "priority": "high",
            "title": f"Expedite Shipment to {top_store['store_name']}",
            "description": f"Rush {int(shortfall)} units of {simulation_result.get('sku')} to prevent stockout during promotion",
            "impact": [
                {"metric": "Cost", "value": "+$500"},
                {"metric": "Delivery Time", "value": "24 hours"},
                {"metric": "Stockout Risk", "value": f"-{int(top_store['stockout_probability']*100)}%"}
            ],
            "confidence": "high",
            "store_id": top_store['store_id']
        })
    
    # Demand-side recommendation (product substitute)
    if len(stores_at_risk) > 1:
        products = load_products()
        current_product = next((p for p in products if p.get('sku') == simulation_result.get('sku')), None)
        
        if current_product:
            # Find similar product
            similar_products = [p for p in products
                              if p.get('category') == current_product.get('category')
                              and p.get('sku') != current_product.get('sku')]
            
            if similar_products:
                substitute = similar_products[0]
                recommendations.append({
                    "id": "rec_002",
                    "type": "demand",
                    "priority": "medium",
                    "title": "Suggest Product Substitute",
                    "description": f"Recommend {substitute.get('name')} as alternative for stores at risk",
                    "impact": [
                        {"metric": "Customer Satisfaction", "value": "~90%"},
                        {"metric": "Revenue Impact", "value": "-5%"}
                    ],
                    "confidence": "medium",
                    "substitute_sku": substitute.get('sku')
                })
    
    print(f"[TOOLS] ✓ Generated {len(recommendations)} rule-based recommendations")
    return {
        "status": "success",
        "recommendations": recommendations
    }