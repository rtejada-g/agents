#!/usr/bin/env python3
"""Validate all S&OP Command Center datasets"""

import csv
import json
import sys
from pathlib import Path

def validate_csv(filename, required_columns, min_rows=1):
    """Validate a CSV file has all required columns and minimum rows"""
    print(f"\n📋 Validating {filename}...")
    
    try:
        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            # Check columns
            missing_cols = set(required_columns) - set(reader.fieldnames)
            if missing_cols:
                print(f"  ❌ Missing columns: {missing_cols}")
                return False
            
            # Check row count
            if len(rows) < min_rows:
                print(f"  ❌ Expected at least {min_rows} rows, found {len(rows)}")
                return False
            
            # Check for empty cells in critical columns
            empty_cells = 0
            for idx, row in enumerate(rows, 1):
                for col in required_columns:
                    if not row.get(col) or row[col].strip() == '':
                        empty_cells += 1
                        if empty_cells <= 3:  # Show first 3 examples
                            print(f"  ⚠️  Row {idx}, column '{col}' is empty")
            
            if empty_cells > 0:
                print(f"  ❌ Found {empty_cells} empty cells in required columns")
                return False
            
            print(f"  ✅ {len(rows)} rows, all required columns present and filled")
            return True
            
    except FileNotFoundError:
        print(f"  ❌ File not found: {filename}")
        return False
    except Exception as e:
        print(f"  ❌ Error reading file: {e}")
        return False

def validate_json(filename, required_keys=None, is_array=True):
    """Validate a JSON file"""
    print(f"\n📋 Validating {filename}...")
    
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        if is_array:
            if not isinstance(data, list):
                print(f"  ❌ Expected array, got {type(data)}")
                return False
            
            count = len(data)
            if count == 0:
                print(f"  ❌ Array is empty")
                return False
            
            # Check first item has required keys
            if required_keys and count > 0:
                missing_keys = set(required_keys) - set(data[0].keys())
                if missing_keys:
                    print(f"  ❌ Missing keys in first item: {missing_keys}")
                    return False
            
            print(f"  ✅ {count} items in array")
            return True
        else:
            print(f"  ✅ Valid JSON object")
            return True
            
    except FileNotFoundError:
        print(f"  ❌ File not found: {filename}")
        return False
    except json.JSONDecodeError as e:
        print(f"  ❌ Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error reading file: {e}")
        return False

def main():
    print("=" * 60)
    print("S&OP COMMAND CENTER DATA VALIDATION")
    print("=" * 60)
    
    all_valid = True
    
    # Validate promo_plan.csv
    all_valid &= validate_csv(
        'promo_plan.csv',
        ['Month', 'Week', 'Week Date', 'Product Focus', 'SKU', 'Brand', 
         'Campaign Theme', 'Target Audience', 'Marketing Channel', 
         'Current Price', 'Decreased Promo Price', 'Demand Uplift (%)', 
         'Current GrossMargin', 'New Gross New Margin'],
        min_rows=30
    )
    
    # Validate stores.csv
    all_valid &= validate_csv(
        'stores.csv',
        ['Brand', 'Synthetic ID', 'Store Name', 'Address', 'Neighborhood', 
         'Borough', 'Latitude', 'Longitude', 'Weekly_Capacity_Units', 'Throughput_Score'],
        min_rows=23
    )
    
    # Validate inventory.csv
    all_valid &= validate_csv(
        'inventory.csv',
        ['Store ID', 'SKU', 'Current Inventory', 'Reorder_Point', 
         'Lead_Time_Days', 'Safety_Stock_Level', 'Last_Restocked'],
        min_rows=600
    )
    
    # Validate demand.csv
    all_valid &= validate_csv(
        'demand.csv',
        ['Store ID', 'SKU', 'Week Ending', 'Demand'],
        min_rows=100
    )
    
    # Validate dc_inventory.csv
    all_valid &= validate_csv(
        'dc_inventory.csv',
        ['DC_ID', 'DC_Name', 'Location', 'SKU', 'Available_Units', 
         'Lead_Time_Hours', 'Cost_Per_Unit_Transfer'],
        min_rows=40
    )
    
    # Validate promo_alternatives.csv
    all_valid &= validate_csv(
        'promo_alternatives.csv',
        ['Original_Promo_ID', 'Alternate_SKU', 'Alternate_Product_Name', 
         'Reason', 'Price_Adjustment_Percent', 'Expected_Uplift_Percent', 
         'Inventory_Availability'],
        min_rows=40
    )
    
    # Validate products.json
    all_valid &= validate_json(
        'products.json',
        required_keys=['sku', 'name', 'brand', 'category'],
        is_array=True
    )
    
    # Summary
    print("\n" + "=" * 60)
    if all_valid:
        print("✅ ALL DATASETS VALID - Ready for demo!")
    else:
        print("❌ VALIDATION FAILED - Please fix issues above")
        sys.exit(1)
    print("=" * 60)

if __name__ == '__main__':
    main()