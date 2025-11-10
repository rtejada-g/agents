#!/usr/bin/env python3
"""Generate realistic weekly demand data for stores and SKUs"""

import csv
import random
from datetime import datetime, timedelta
from collections import defaultdict

# Read stores
with open('stores.csv', 'r') as f:
    reader = csv.DictReader(f)
    stores = [row['Synthetic ID'] for row in reader]

# Read promo plan to get SKUs
with open('promo_plan.csv', 'r') as f:
    reader = csv.DictReader(f)
    skus = list(set(row['SKU'] for row in reader))

print(f"Generating demand for {len(stores)} stores and {len(skus)} SKUs")

# Generate demand for promo weeks (November 2025 - January 2026)
# Read promo plan to get exact weeks
promo_weeks = set()
with open('promo_plan.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        promo_weeks.add(row['Week Date'])

weeks = sorted(list(promo_weeks))
print(f"Found {len(weeks)} unique promo weeks: {weeks[0]} to {weeks[-1]}")

# Generate demand data
demand_records = []

# Define base demand ranges by store tier (based on capacity)
store_tiers = {
    'high': ['SEPH-NYC-001', 'SEPH-NYC-002', 'SEPH-NYC-011', 'SEPH-NYC-006'],  # High traffic
    'medium': ['SEPH-NYC-003', 'SEPH-NYC-004', 'SEPH-NYC-005', 'SEPH-NYC-007', 
               'SEPH-NYC-008', 'SEPH-NYC-009', 'SEPH-NYC-014'],  # Medium traffic
    'low': [s for s in stores if s not in ['SEPH-NYC-001', 'SEPH-NYC-002', 'SEPH-NYC-011', 
                                             'SEPH-NYC-006', 'SEPH-NYC-003', 'SEPH-NYC-004', 
                                             'SEPH-NYC-005', 'SEPH-NYC-007', 'SEPH-NYC-008', 
                                             'SEPH-NYC-009', 'SEPH-NYC-014']]
}

# Define base demand by SKU category (premium vs mass)
premium_skus = ['LM-CDLM-004', 'LM-TL-013', 'LM-LRM-024', 'LM-SPF50-031', 
                'TF-ECQ-009', 'TF-BO-017', 'TF-SL-025', 'JML-EPC-016']
high_volume_skus = ['EL-ANR-001', 'EL-DW-002', 'CL-MS-003', 'MAC-SFF-008', 
                     'CL-HM-018', 'BB-CB-022']

for store_id in stores:
    # Determine store tier
    if store_id in store_tiers['high']:
        store_multiplier = 1.5
    elif store_id in store_tiers['medium']:
        store_multiplier = 1.0
    else:
        store_multiplier = 0.6
    
    for sku in skus:
        # Determine SKU base demand
        if sku in premium_skus:
            base_demand = random.randint(5, 15)
        elif sku in high_volume_skus:
            base_demand = random.randint(25, 50)
        else:
            base_demand = random.randint(10, 30)
        
        # Apply store multiplier
        base_demand = int(base_demand * store_multiplier)
        
        # Generate weekly demand with seasonality and randomness
        for week_idx, week_end in enumerate(weeks):
            # Add trend (slight increase over time)
            trend = 1 + (week_idx * 0.02)
            
            # Add seasonality (November spike for holidays)
            month = datetime.strptime(week_end, '%Y-%m-%d').month
            if month == 11:
                seasonal = 1.3
            elif month == 12:
                seasonal = 1.5
            else:
                seasonal = 1.0
            
            # Add random variation (-20% to +30%)
            variation = random.uniform(0.8, 1.3)
            
            # Calculate final demand
            demand = int(base_demand * trend * seasonal * variation)
            demand = max(1, demand)  # Ensure at least 1
            
            demand_records.append({
                'Store ID': store_id,
                'SKU': sku,
                'Week Ending': week_end,
                'Demand': demand
            })

# Write to CSV
with open('demand.csv', 'w', newline='') as f:
    fieldnames = ['Store ID', 'SKU', 'Week Ending', 'Demand']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(demand_records)

print(f"✅ Generated {len(demand_records)} demand records")
print(f"   Stores: {len(stores)}")
print(f"   SKUs: {len(skus)}")
print(f"   Weeks: {len(weeks)}")
print(f"   Total combinations: {len(stores)} × {len(skus)} × {len(weeks)} = {len(demand_records)}")