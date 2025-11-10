# Data Validation Guide

## Quick Validation

Run this command from the `agents/sop-command-center/data/default/` directory:

```bash
python3 validate_all_data.py
```

## Expected Output

The script will validate all datasets and provide a comprehensive report:

```
============================================================
S&OP COMMAND CENTER DATA VALIDATION
============================================================

📋 Validating promo_plan.csv...
  ✅ 32 rows, all required columns present and filled

📋 Validating stores.csv...
  ✅ 23 rows, all required columns present and filled

📋 Validating inventory.csv...
  ✅ 616 rows, all required columns present and filled

📋 Validating demand.csv...
  ✅ [count] rows, all required columns present and filled

📋 Validating dc_inventory.csv...
  ✅ 46 rows, all required columns present and filled

📋 Validating promo_alternatives.csv...
  ✅ 43 rows, all required columns present and filled

📋 Validating products.json...
  ✅ 42 items in array

============================================================
✅ ALL DATASETS VALID - Ready for demo!
============================================================
```

## What Each Dataset Provides

### 1. promo_plan.csv (32 promotional scenarios)
- **Supports**: Flow A, B, C, D
- **Key Fields**: Week Date, Campaign Theme, SKU, Pricing, Demand Uplift
- **Demo Usage**: Initial scenario selection in Panel 1

### 2. stores.csv (23 NYC retail locations)
- **Supports**: Flow A, B (capacity constraints)
- **Key Fields**: Store ID, Location, Lat/Lng, Capacity, Throughput Score
- **Demo Usage**: Map visualization, capacity analysis

### 3. inventory.csv (616 store/SKU combinations)
- **Supports**: All Flows
- **Key Fields**: Current Inventory, Reorder Point, Safety Stock, Last Restocked
- **Demo Usage**: Stockout risk calculation, baseline inventory state

### 4. demand.csv (5000+ demand records)
- **Supports**: All Flows
- **Key Fields**: Store ID, SKU, Week, Demand
- **Demo Usage**: Baseline demand forecasting, uplift calculation

### 5. dc_inventory.csv (46 DC/SKU records)
- **Supports**: Flow A (supply-side solutions)
- **Key Fields**: DC ID, SKU, Available Units, Lead Time, Transfer Cost
- **Demo Usage**: Inventory transfer recommendations

### 6. promo_alternatives.csv (43 substitute scenarios)
- **Supports**: Flow B (demand-shaping solutions)
- **Key Fields**: Original SKU, Alternate SKU, Reason, Price Adjustment, Uplift
- **Demo Usage**: Product substitute recommendations

### 7. products.json (42 products)
- **Supports**: All Flows
- **Key Fields**: SKU, Name, Brand, Category, Price
- **Demo Usage**: Product metadata enrichment

## Data Quality Checklist

- [x] All CSVs have headers with correct column names
- [x] No empty/null values in critical columns
- [x] inventory.csv has Last_Restocked for all 616 rows
- [x] stores.csv has capacity metrics (Weekly_Capacity_Units, Throughput_Score)
- [x] dc_inventory.csv has sufficient SKU coverage
- [x] promo_alternatives.csv maps to real SKUs in products.json
- [x] Lat/Lng coordinates are valid for NYC metro area
- [x] JSON files are valid and parseable

## Manual Spot Checks

If validation passes, do a quick visual inspection:

```bash
# Check inventory dates are filled
head -20 inventory.csv | cut -d',' -f7

# Check DC inventory has variety
cut -d',' -f4 dc_inventory.csv | sort -u | wc -l

# Check promo alternatives coverage
cut -d',' -f1 promo_alternatives.csv | sort -u | wc -l

# Check stores have capacity data
tail -5 stores.csv
```

## Troubleshooting

If validation fails:

1. **Missing columns**: Check CSV headers match exactly (case-sensitive)
2. **Empty cells**: Run the fix scripts for that dataset
3. **File not found**: Ensure you're in the correct directory
4. **JSON parse error**: Validate JSON syntax with `python3 -m json.tool < products.json`