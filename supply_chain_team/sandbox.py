from utils import (
    calculate_demand_forecast,
    get_weather_forecast,
    get_sku_sales_data,
    get_sku_promotions,
    get_weather_forecast_tool,
    get_sku_sales_data_tool,
    get_sku_promotions_tool,
    get_inventory_for_sku_tool,
    get_promotional_calendar_for_sku_tool,
    check_open_orders_tool,
    get_supplier_capacity_tool,
    simulate_place_po_tool,
    simulate_pause_promo_tool,
)

from datetime import datetime, timedelta

def main():
    #test = get_sku_promotions("NOVA-P1","2025-01-31","2025-07-15")
    #print(test)
    #test_result = test.get("promotions", [])
    #print("-----------------------------")
    #print(test_result)
    #test_summary = ", ".join([p["PromotionName"] for p in test_result]) if test_result else "None"
    #print("-----------------------------")
    #print(test_summary)

    print("-----------------------------")
    start_date = (datetime(2025, 5, 1) - timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"START: {start_date}")
    end_date = (datetime(2025, 5, 1) + timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"END: {end_date}")
    print("-----------------------------")
    print("-----------------------------")
    print("-----------------------------")
    start_date = (datetime(2025, 5, 1) + timedelta(days=-30)).strftime("%Y-%m-%d")
    print(f"START: {start_date}")
    end_date = (datetime(2025, 5, 1) + timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"END: {end_date}")
    print("-----------------------------")
    print("-----------------------------")

    #test = get_sku_promotions("NOVA-P1",start_date,end_date)
    #print(test)
    #test_result = test.get("promotions", [])
    #print("-----------------------------")
    #print(test_result)
    #test_summary = ", ".join([p["PromotionName"] for p in test_result]) if test_result else "None"
    #print("-----------------------------")
    #print(test_summary)

if __name__ == "__main__":
    main()