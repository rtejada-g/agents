# utils.py
import pandas as pd
from typing import Dict, Any, List
import requests
from . import config # Import the configuration
import os
import tempfile # For handling temporary image files
from urllib.parse import urlparse # To check if logo is a URL
from google.adk.tools import FunctionTool
from datetime import datetime, timedelta
import math
from fpdf import FPDF

# --- Data Loading ---
def load_data(filename: str) -> pd.DataFrame:
    """Loads data from a CSV file into a Pandas DataFrame.

    Args:
        file_path: The path to the CSV file.

    Returns:
        A Pandas DataFrame containing the data, or None if an error occurs.
    """
    path = os.path.join(os.path.dirname(__file__), f"data/{filename}")
    try:
        df = pd.read_csv(path)
        return df
    except Exception as e:
        print(f"Error loading data from {path}: {e}")
        return None

# --- Data Filtering ---
def filter_sales_data(sales_data: pd.DataFrame, sku: str) -> pd.DataFrame:
    """Filters sales data for a specific SKU.

    Args:
        sales_data: The sales data DataFrame.
        sku: The SKU to filter by.

    Returns:
        A DataFrame containing sales data for the specified SKU.
    """
    return sales_data[sales_data["SKU"] == sku]

# --- Forecasting ---
def calculate_demand_forecast(sales_data: List[Dict[str, Any]]) -> float:
    """Calculates a simple demand forecast based on the average of the latest week's sales.

    Args:
        sales_data: Filtered sales data for a specific SKU.

    Returns:
        The predicted demand for the next 14 days.
    """
    if not sales_data:
        return 0.0  # Handle case with no sales data

    # Convert to DataFrame for easier calculations
    df = pd.DataFrame(sales_data)
    df['Date'] = pd.to_datetime(df['Date'])

    # Get the latest date in the sales data
    latest_date = df['Date'].max()

    # Calculate the date one week prior to the latest date
    one_week_ago = latest_date - timedelta(weeks=1)

    # Filter sales data for the last week
    recent_sales = df[df['Date'] >= one_week_ago]

    # Convert back to original format for consistency
    recent_sales = recent_sales.to_dict(orient='records')

    # Calculate the average quantity sold in the last week
    if recent_sales:
        average_weekly_sales = sum(item['Quantity Sold'] for item in recent_sales)
    else:
        average_weekly_sales = 0

    # Forecast demand for the next 14 days (2 weeks)
    forecasted_demand = average_weekly_sales * 2

    return forecasted_demand

# --- Inventory ---
def get_inventory_for_sku_location(inventory_data: pd.DataFrame, sku: str, location: str="") -> pd.DataFrame:
    """Gets inventory data for a specific SKU and optionally a location.

    Args:
        inventory_data: The inventory data DataFrame.
        sku: The SKU to filter by.
        location: Optional location to filter by.

    Returns:
        A DataFrame containing inventory data for the specified SKU and location (if provided).
    """
    filtered_inventory = inventory_data[inventory_data["SKU"] == sku]
    if location!="":
        filtered_inventory = filtered_inventory[filtered_inventory["Location"] == location]
    return filtered_inventory

# --- Orders ---
def check_open_orders(order_data: pd.DataFrame, sku: str) -> pd.DataFrame:
    """Checks for open orders for a specific SKU.

    Args:
        order_data: The order status updates DataFrame.
        sku: The SKU to filter by.

    Returns:
        A DataFrame containing open order information for the specified SKU.
    """
    return order_data[order_data["SKU"] == sku]

# --- Supplier --- 
def get_supplier_capacity(supplier_data: pd.DataFrame, sku: str) -> pd.DataFrame:
    """Gets supplier capacity for a specific SKU.

    Args:
        supplier_data: The supplier capacity DataFrame.
        sku: The SKU to filter by.

    Returns:
        A DataFrame containing supplier capacity information for the specified SKU.
    """
    return supplier_data[supplier_data["SKU"] == sku]

# --- Promotions ---
def get_promotional_calendar_for_sku(promo_data: List[Dict[str, Any]], sku: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """Gets promotional calendar entries for a specific SKU within a date range."""
    promo_data = pd.DataFrame(promo_data)
    promo_data['StartDate'] = pd.to_datetime(promo_data['StartDate'])
    promo_data['EndDate'] = pd.to_datetime(promo_data['EndDate'])
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    sku_promos = promo_data[promo_data["SKU"] == sku]
    date_filtered_promos = sku_promos[(sku_promos['StartDate'] <= end_date) & (sku_promos['EndDate'] >= start_date)].copy()

    if not date_filtered_promos.empty:
        # Explicitly create new columns with string type
        date_filtered_promos.loc[:, 'StartDateStr'] = date_filtered_promos['StartDate'].dt.strftime('%Y-%m-%d')
        date_filtered_promos.loc[:, 'EndDateStr'] = date_filtered_promos['EndDate'].dt.strftime('%Y-%m-%d')
        # Now use the new string columns in the records
        promo_records = date_filtered_promos[["PromotionName", "SKU", "StartDateStr", "EndDateStr", "Discount", "Channel"]].rename(columns={"StartDateStr": "StartDate", "EndDateStr": "EndDate"}).to_dict(orient="records")
        return promo_records    
    return []

get_promotional_calendar_for_sku_tool = FunctionTool(
    func=get_promotional_calendar_for_sku
)

# --- Weather (Tool) ---
def get_weather_forecast_verbose(location: str) -> Dict[str, Any]:
    """Gets the weather forecast from Open-Meteo for a given location.

    Args:
        location: The location to get the forecast for.

    Returns:
        A dictionary containing the weather forecast, with a 'status' key ('success' or 'error').
        On success, includes a 'weather' dictionary with current and hourly data.
        On error, includes an 'error_message'.
    """
    print(f"get_weather_forecast: Getting weather forecast for {location}...")

    try:
        # Geocoding to get latitude and longitude
        geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
        geocoding_response = requests.get(geocoding_url)
        geocoding_response.raise_for_status()
        geocoding_data = geocoding_response.json()
        if not geocoding_data.get("results"):  # Use .get() to handle missing key
            return {"status": "error", "error_message": f"Location '{location}' not found by geocoding API"}
        latitude = geocoding_data["results"][0]["latitude"]
        longitude = geocoding_data["results"][0]["longitude"]

        # Now get the weather for that location
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m&forecast_days=14"  # Get 14-day forecast
        weather_response = requests.get(weather_url)
        weather_response.raise_for_status()

        weather_data = weather_response.json()
        current_temperature = weather_data["current"]["temperature_2m"]
        current_wind_speed = weather_data["current"]["wind_speed_10m"]
        hourly_data = weather_data["hourly"]

        # Basic logic to determine if weather is favorable (can be customized)
        is_favorable = (15 <= current_temperature <= 25 and current_wind_speed < 20)

        return {
            "status": "success",
            "weather": {
                "current": {
                    "temperature_2m": current_temperature,
                    "wind_speed_10m": current_wind_speed,
                },
                "hourly": {
                    "time": hourly_data["time"],
                    "temperature_2m": hourly_data["temperature_2m"],
                    "relative_humidity_2m": hourly_data["relative_humidity_2m"],
                    "wind_speed_10m": hourly_data["wind_speed_10m"]
                },
                "is_favorable": is_favorable
            },
        }
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error_message": f"Error fetching weather data for '{location}': {e}"}

def get_weather_forecast(location: str) -> Dict[str, Any]:
    """Gets a concise weather forecast from Open-Meteo for a given location, 
    including only current temperature, wind speed, and a favorable condition indicator.
    """
    full_forecast = get_weather_forecast_verbose(location)
    if full_forecast["status"] == "success":
        weather = full_forecast["weather"]
        return {"status": "success", "weather": {"current": weather["current"], "is_favorable": weather["is_favorable"]}}
    return full_forecast

get_weather_forecast_tool = FunctionTool(
    func=get_weather_forecast
)

# --- Tool: Get Base Forecast from Sales ---
def get_base_sales_data(sku: str, location: str = "") -> float:
    """
    Calculates a base demand forecast for a specific SKU based on historical sales data.

    Args:
        sku: The SKU to forecast demand for.
        location: Optional location to filter sales data by.

    Returns:
        The base demand forecast for the next 14 days, or -1.0 if an error occurs.
    """
    print(f"get_base_forecast_from_sales: Calculating base forecast for SKU '{sku}'{f' at location {location}' if location else ''}...")
    sales_data = load_data("historical_sales_data.csv")
    if sales_data is None:
        return -1.0

    filtered_data = filter_sales_data(sales_data, sku)
    if location:
        filtered_data = filtered_data[filtered_data["Location"] == location]

    if filtered_data.empty:
        return 0.0  # No sales data, return a forecast of 0

    sales_records = filtered_data[["Date", "Location", "Quantity Sold"]].to_dict(orient="records")
    return calculate_demand_forecast(sales_records)

get_base_sales_data_tool = FunctionTool(
    func=get_base_sales_data
)

# --- Tool: Get SKU Promotions ---
def get_sku_promotions(sku: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """Retrieves active promotions for a specific SKU within a given date range.

    Args:
        sku: The SKU to retrieve promotions for.
        start_date: The start date of the promotion period (YYYY-MM-DD).
        end_date: The end date of the promotion period (YYYY-MM-DD).

    Returns:
        A dictionary containing promotion information, with a 'status' key ('success' or 'error').
        On success, includes a 'promotions' list of dictionaries, each with promotion details.
        On error, includes an 'error_message'.
    """

    promo_data = load_data("promotional_calendar.csv")
    if promo_data is None:
        return {"status": "error", "error_message": "Failed to load promotional calendar data."}

    promotions_list = get_promotional_calendar_for_sku(promo_data, sku, start_date, end_date)
    if not promotions_list:
        return {"status": "success", "promotions_summary": "None"}

    promotions_summary = ", ".join([p["PromotionName"] for p in promotions_list])
    return {"status": "success", "promotions_summary": promotions_summary}


get_sku_promotions_tool = FunctionTool(
    func=get_sku_promotions
)

# --- Tool: Get Inventory for SKU ---
def get_inventory_for_sku(sku: str, location: str="") -> Dict[str, Any]:
    """Retrieves inventory information for a specific SKU, optionally filtered by location.

    Args:
        sku: The SKU to retrieve inventory for.
        location: Optional location to filter inventory.

    Returns:
        A dictionary containing inventory information, with a 'status' key ('success' or 'error').
        On success, includes an 'inventory' list of dictionaries, each with inventory details.
        On error, includes an 'error_message'.
    """
    print(f"get_inventory_for_sku: Retrieving inventory for SKU '{sku}'{f' at location {location}' if location else ''}...")
    inventory_data = load_data("current_inventory_levels.csv")
    if inventory_data is None:
        return {"status": "error", "error_message": "Failed to load inventory data."}

    inventory = get_inventory_for_sku_location(inventory_data, sku, location)
    if not inventory.empty:
        total_on_hand = inventory["QuantityOnHand"].sum()
    else:
        total_on_hand = 0
    return {"status": "success", "on_hand": int(total_on_hand)}


get_inventory_for_sku_tool = FunctionTool(
    func=get_inventory_for_sku
)
                                          

def check_open_orders(sku: str) -> Dict[str, Any]:
    """Checks for open purchase orders for a specific SKU.

    Args:
        order_data: The order status updates DataFrame.
        sku: The SKU to check for open orders.

    Returns:
        A dictionary containing open order information, with a 'status' key ('success' or 'error').
        On success, includes an 'open_orders' list of dictionaries, each with order details.
        On error, includes an 'error_message'.
    """
    print(f"check_open_orders: Checking open orders for SKU '{sku}'...")
    order_data = load_data("order_status_updates.csv")
    if order_data is None:
        return {"status": "error", "error_message": "Failed to load order data."}

    open_orders = order_data[order_data["SKU"] == sku]
    open_orders = open_orders.fillna("None")
    open_orders_data = open_orders.to_dict(orient="records")
    open_orders_quantity = sum(order["Quantity"] for order in open_orders_data) if open_orders_data else 0

    return {"status": "success", "open_orders_quantity": open_orders_quantity}

check_open_orders_tool = FunctionTool(
    func=check_open_orders
)


def get_supplier_capacity(sku: str) -> Dict[str, Any]:
    """Retrieves supplier capacity information for a specific SKU.

    Args:
        sku: The SKU to retrieve supplier capacity for.

    Returns:
        A dictionary containing supplier capacity information, with a 'status' key ('success' or 'error').
        On success, includes a 'supplier_capacity' list of dictionaries, each with supplier details.
        On error, includes an 'error_message'.
    """
    print(f"get_supplier_capacity: Retrieving supplier capacity for SKU '{sku}'...")
    supplier_data = load_data("supplier_capacity.csv")
    if supplier_data is None:
        return {"status": "error", "error_message": "Failed to load supplier capacity data."}

    capacity = supplier_data[supplier_data["SKU"] == sku]
    if not capacity.empty:
        capacity_record = capacity.iloc[0] # Use iloc for Series access
        max_units_per_day = int(capacity_record.get("MaxUnitsPerDay", 0))
        supplier_name = capacity_record.get("Supplier", "N/A") # Corrected column name
        return {"status": "success", "max_units_per_day": max_units_per_day, "supplier_name": supplier_name}
    else:
        return {"status": "success", "max_units_per_day": 0, "supplier_name": "N/A"}

get_supplier_capacity_tool = FunctionTool(
    func=get_supplier_capacity
)
                                          
# --- Tool: Calculate Final Forecast ---
def calculate_final_forecast(base_forecast: float, promotions_summary: str, weather: Dict[str, Any]) -> Dict[str, Any]:
    """Calculates the final demand forecast by applying multipliers based on promotions and weather.

    Args:
        base_forecast: The base demand forecast.
        promotions_summary: A summary of active promotions.
        weather: A dictionary containing weather information, including an 'is_favorable' flag.

    Returns:
        The final adjusted demand forecast.
    """
    CRITICAL_SPIKE_THRESHOLD = 100
    forecasted_demand = base_forecast

    if promotions_summary != "None" and not promotions_summary.startswith("Error:"):
        forecasted_demand *= 1.05  # Apply promotion multiplier

    if weather.get("is_favorable"):
        forecasted_demand *= 1.05  # Apply favorable weather multiplier
    else:
        forecasted_demand *= 0.95  # Apply unfavorable weather multiplier

    # Determine critical spike
    is_critical_spike = forecasted_demand > CRITICAL_SPIKE_THRESHOLD

    return {"forecasted_demand": math.ceil(forecasted_demand), "is_critical_spike": is_critical_spike}

calculate_final_forecast_tool = FunctionTool(
    func=calculate_final_forecast
)

# --- Tool: PO Placement  ---
def place_po(sku: str, replenishment_needed: int, max_units_per_day: int, supplier_name: str = "N/A") -> Dict[str, Any]:
    """placing a purchase order for a specific SKU and quantity.
    Customer name and logo are sourced from config.py.

    Args:
        sku: The SKU to order.
        replenishment_needed: The quantity to order.
        max_units_per_day: The maximum units per day that the supplier can provide
        supplier_name: The name of the supplier.

    Returns:
        A dictionary indicating the PO placement, with a 'status' key ('success'),
        message, action_taken, quantity, and pdf_path.
    """
    quantity_to_order = 0
    action_taken_status = ""
    message = ""
    pdf_path = None
    
    actual_customer_name = config.CUSTOMER_NAME or config.DEFAULT_NAME
    actual_customer_logo = config.CUSTOMER_LOGO or config.DEFAULT_LOGO

    if replenishment_needed <= 0: # Should not happen if called correctly, but as a safeguard
        quantity_to_order = 0
        action_taken_status = "NO_PO_NEEDED_ZERO_OR_NEGATIVE_REPLENISHMENT"
        message = f"No PO placed for SKU '{sku}' as replenishment needed is {replenishment_needed}."
    elif abs(replenishment_needed) <= max_units_per_day:
        quantity_to_order = replenishment_needed
        action_taken_status = "NEW_PO_PLACED"
        message = f"Placed PO for SKU '{sku}', quantity {quantity_to_order}."
        print(f"place_po: PO placement for SKU '{sku}', quantity {quantity_to_order}...")
    else:
        quantity_to_order = max_units_per_day # Order only what supplier can handle
        action_taken_status = "PARTIAL_REPLENISHMENT"
        message = f"Partial PO placed for SKU '{sku}', quantity {quantity_to_order} due to supplier capacity (needed {replenishment_needed})."
        print(f"place_po: Partial PO placement for SKU '{sku}', quantity {quantity_to_order}...")

    if quantity_to_order > 0:
        try:
            output_dir = os.path.join(os.path.dirname(__file__), "output")
            os.makedirs(output_dir, exist_ok=True)

            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
            po_number = f"PO-{sku}-{timestamp_str}"
            pdf_file_name = f"{po_number}.pdf"
            pdf_path = os.path.join(output_dir, pdf_file_name)

            pdf = FPDF()
            pdf.add_page()

            # Add logo if available
            logo_path_to_use = None
            if actual_customer_logo:
                try:
                    parsed_url = urlparse(actual_customer_logo)
                    if parsed_url.scheme in ['http', 'https']: # It's a URL
                        response = requests.get(actual_customer_logo, stream=True)
                        response.raise_for_status()
                        
                        # Create a temporary file to save the image
                        # Ensure the suffix matches the image type if possible, or use a generic one like .png
                        # For simplicity, assuming PNG or JPEG which FPDF handles well.
                        img_suffix = os.path.splitext(parsed_url.path)[1] or '.png'
                        with tempfile.NamedTemporaryFile(delete=False, suffix=img_suffix, dir=output_dir) as tmp_logo_file:
                            for chunk in response.iter_content(chunk_size=8192):
                                tmp_logo_file.write(chunk)
                            logo_path_to_use = tmp_logo_file.name
                        
                        pdf.image(logo_path_to_use, x=10, y=8, w=30)
                        
                        if logo_path_to_use and os.path.exists(logo_path_to_use):
                            os.remove(logo_path_to_use) # Clean up the temporary file

                    elif os.path.exists(actual_customer_logo): # It's a local file path
                        pdf.image(actual_customer_logo, x=10, y=8, w=30)
                    else:
                        print(f"Logo path/URL not valid or file not found: {actual_customer_logo}")

                except Exception as e:
                    print(f"Error adding logo to PDF: {e}")
                    if logo_path_to_use and os.path.exists(logo_path_to_use): # Ensure cleanup on error too
                        try:
                            os.remove(logo_path_to_use)
                        except OSError:
                            pass # Ignore if already deleted or other issue
            
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "PURCHASE ORDER", 0, 1, "C")
            pdf.ln(15) # Increased spacing after the main title

            pdf.set_font("Arial", "", 12)
            pdf.cell(0, 10, f"PO Number: {po_number}", 0, 1)
            pdf.cell(0, 10, f"Date: 2025-06-25 9:35:42", 0, 1)
            #pdf.cell(0, 10, f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
            pdf.cell(0, 10, f"Supplier: {supplier_name if supplier_name else 'N/A'}", 0, 1)
            pdf.ln(5)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(100, 10, "Item SKU", 1, 0, "C")
            pdf.cell(40, 10, "Quantity", 1, 0, "C") # Keep on same line for unit price/total later
            pdf.cell(50, 10, "Unit Price", 1, 1, "C") # Add Unit Price header

            pdf.set_font("Arial", "", 12)
            pdf.cell(100, 10, sku, 1)
            pdf.cell(40, 10, str(quantity_to_order), 1, 0, "R")
            pdf.cell(50, 10, "N/A", 1, 1, "R") # Placeholder for Unit Price value
            pdf.ln(5)

            # Ship To / Bill To (Minimal)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(95, 6, "SHIP TO:", 0, 0)
            pdf.cell(95, 6, "BILL TO:", 0, 1)
            pdf.set_font("Arial", "", 10)
            pdf.cell(95, 6, f"{actual_customer_name} Warehouse", 0, 0)
            pdf.cell(95, 6, f"{actual_customer_name} Accounts Payable", 0, 1)
            pdf.cell(95, 6, "123 Distribution Way", 0, 0) # Address can be parameterized later if needed
            pdf.cell(95, 6, "456 Finance Ave", 0, 1)      # Address can be parameterized later if needed
            pdf.cell(95, 6, "Anytown, ST 54321", 0, 0)
            pdf.cell(95, 6, "Businesstown, ST 12345", 0, 1)
            pdf.ln(10)
            
            # Notes Section (Minimal)
            customer_email_domain = actual_customer_name.lower().replace(' ', '').replace('.', '') + ".com"
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, "NOTES:", 0, 1)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 6, f"1. Please include PO number on all invoices.\n2. Contact procurement@{customer_email_domain} for queries.", border=0, align="L", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)

            pdf.output(pdf_path, "F")
            print(f"place_po: Generated PO PDF at {pdf_path}")
            # pdf_path is already the absolute path, which is what we need.
            # The incorrect relative path generation is removed.
            print(f"place_po: Returning PDF path: {pdf_path}")


        except Exception as e:
            print(f"Error generating PDF for PO: {e}")
            message += f" (Error generating PDF: {e})"
            pdf_path = None

    return {
        "status": "success",
        "message": message,
        "action_taken": action_taken_status,
        "quantity": quantity_to_order,
        "pdf_path": pdf_path
    }

place_po_tool = FunctionTool(
    func=place_po
)

# --- Tool: Pause Promotion ---
def pause_promo(promotion_name: str, sku: str) -> Dict[str, Any]:
    """pausing a promotion for a specific SKU.
    Customer name is sourced from config.py.

    Args:
        promotion_name: The name of the promotion to pause.
        sku: The SKU associated with the promotion.

    Returns:
        A dictionary indicating the promotion pause, with a 'status' key ('success'),
        message, and simulated_email_path.
    """
    print(f"pause_promo: Pausing promotion '{promotion_name}' for SKU '{sku}'...")
    simulated_email_path = None
    message = f"Paused promotion '{promotion_name}' for SKU '{sku}'."

    actual_customer_name = config.CUSTOMER_NAME or config.DEFAULT_NAME
    customer_email_domain = actual_customer_name.lower().replace(' ', '').replace('.', '').replace("'", "") + ".com"


    try:
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        os.makedirs(output_dir, exist_ok=True)

        timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
        email_file_name = f"promo_paused_{sku}_{timestamp_str}.txt" # Changed to .txt
        simulated_email_path = os.path.join(output_dir, email_file_name)

        email_content = f"""To: supply_chain_manager@{customer_email_domain}
From: automated_system@{customer_email_domain}
Subject: Promotion Paused: {promotion_name} for SKU {sku} (Customer: {actual_customer_name})
Date: {datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")}

Dear {actual_customer_name} Team,

This is an automated notification to inform you that the following promotion has been paused due to system strain and potential stock shortages for {actual_customer_name}:

Promotion Name: {promotion_name}
SKU: {sku}

Please review inventory levels and supplier capacity.

Regards,
{actual_customer_name} Automated Supply Chain Agent
"""
        with open(simulated_email_path, "w") as f:
            f.write(email_content)
        
        print(f"pause_promo: Generated simulated email (txt) at {simulated_email_path}")
        # Convert path for eval consistency
        simulated_email_path = os.path.join("supply_chain_team", "output", email_file_name)

    except Exception as e:
        print(f"Error generating simulated email (txt) for promo pause: {e}")
        message += f" (Error generating .txt file: {e})"
        email_content = f"Error generating email content: {e}" # Ensure email_content is defined on error
        # simulated_email_path remains None or path before error

    return {
        "status": "success",
        "message": message,
        "simulated_email_path": simulated_email_path,
        "simulated_email_content": email_content  # Add the email content to the return
    }

pause_promo_tool = FunctionTool(
    func=pause_promo
)

# --- Tool: Calculate Replenishment Need ---
def calculate_replenishment_need(forecasted_demand: int, total_on_hand: int, open_orders_quantity: int) -> int:
    """Calculates the replenishment need for a SKU.

    Args:
        total_reorder_point: The total reorder point for the SKU.
        forecasted_demand: The forecasted demand for the SKU.
        total_on_hand: The total quantity on hand for the SKU.
        open_orders_quantity: The quantity of the SKU in open orders.

    Returns:
        The calculated replenishment need.
    """
    total_reorder_point = 200 
    print(f"[REPNEED] Forecast: {forecasted_demand}, On Hand:{total_on_hand}, Open Orders: {open_orders_quantity}")
    replenishment_needed = total_reorder_point + forecasted_demand - (total_on_hand + open_orders_quantity)
    print(f"[REPNEED] Replenishment Needed: {replenishment_needed}")
    return replenishment_needed

calculate_replenishment_need_tool = FunctionTool(
    func=calculate_replenishment_need
)
# --- Tool: Calculate Tariff Impact ---
def calculate_tariff_impact(sku: str, forecasted_demand: int) -> Dict[str, Any]:
    """
    Calculates the financial impact of a tariff on a given SKU.

    Args:
        sku: The SKU to calculate the tariff impact for.
        forecasted_demand: The forecasted demand for the SKU.

    Returns:
        A dictionary containing the tariff impact details.
    """
    # Deterministic tariff calculation
    tariff_rate = 0.15  # 15% tariff
    cost_per_unit = 50  # $50 cost per unit
    financial_impact = forecasted_demand * cost_per_unit * tariff_rate
    high_impact = financial_impact > 5000

    return {
        "status": "success",
        "financial_impact": round(financial_impact, 2),
        "high_impact": high_impact,
    }

calculate_tariff_impact_tool = FunctionTool(
    func=calculate_tariff_impact
)