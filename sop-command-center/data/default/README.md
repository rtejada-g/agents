# S&OP Command Center - Data Files

This directory contains the data files needed for the S&OP Command Center demo.

## Required Data Files

### 1. `promo_plan.csv`
Promotional campaign schedule with demand uplift predictions.

**Columns**:
- Month
- Week
- Week Date (format: YYYY-MM-DD)
- Product Focus
- SKU
- Brand
- Campaign Theme
- Target Audience
- Marketing Channel
- Current Price
- Decreased Promo Price
- Demand Uplift (%)
- Current GrossMargin
- New Gross New Margin

### 2. `stores.csv`
Store locations in NYC metro area.

**Required Columns**:
- Brand
- Synthetic ID (e.g., SEPH-NYC-001)
- Store Name
- Address
- Neighborhood
- Borough
- Latitude (must be added for map rendering)
- Longitude (must be added for map rendering)

**Note**: You must add lat/lng coordinates for each store. Use geocoding for the provided addresses.

### 3. `demand_forecast.csv`
Weekly demand projections per store/SKU combination.

**Columns**:
- Store ID
- SKU
- Week Ending (format: YYYY-MM-DD)
- Demand (units)

### 4. `inventory.csv`
Current inventory levels and replenishment parameters.

**Suggested Schema**:
```csv
Store ID,SKU,Current Inventory,Reorder Point,Lead Time Days,Safety Stock
SEPH-NYC-001,EL-ANR-001,25,15,3,10
```

### 5. `products.json`
Product catalog (SYMLINK to aesthetic-to-routine's products.json).

**To create symlink** (macOS/Linux):
```bash
cd agents/sop-command-center/data/default
ln -s ../../../../aesthetic-to-routine/data/default/products.json products.json
```

**For Windows**: Copy the file instead or use mklink

## Data Preparation Notes

- All date fields should use ISO format (YYYY-MM-DD)
- Store IDs must match across all files
- SKUs must match those in products.json
- Ensure lat/lng coordinates are accurate for NYC metro area
- Demand values should be realistic (e.g., 10-100 units per week)