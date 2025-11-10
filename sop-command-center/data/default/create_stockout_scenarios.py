#!/usr/bin/env python3
"""Create realistic stockout scenarios for demo impact"""

import csv
import random
import shutil
from datetime import datetime

# Target promos that should show supply chain issues (for demo drama)
HIGH_RISK_PROMOS = [
    '2025-11-02_EL-ANR-001',  # Holiday Glow-Up - 18% uplift
    '2025-11-16_MAC-SFF-008',  # Black Friday - 50% uplift!
    '2025-12-14_MAC-RW-005',   # Holiday Party - 50% uplift
    '2025-12-28_MAC-PFP-014',  # NYE - 50% uplift
]

# Extract SKUs from high-risk promos
HIGH_RISK_SKUS = [p.split('_')[1] for p in HIGH_RISK_PROMOS]

print(f"Creating stockout scenarios for: {HIGH_RISK_SKUS}")

# Read current inventory
with open('inventory.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Check if already modified (idempotency check)
# If Safety_Stock_Level exists and some high-risk SKUs have inventory < 50% of safety stock,
# assume we already ran this
already_modified = False
check_count = 0
low_inventory_count = 0

for row in rows:
    if row['SKU'] in HIGH_RISK_SKUS:
        check_count += 1
        current_inv = int(float(row['Current Inventory']))
        safety_stock = int(float(row['Safety_Stock_Level']))
        if current_inv < safety_stock * 0.8:  # Less than 80% of safety stock
            low_inventory_count += 1

if check_count > 0 and low_inventory_count > check_count * 0.5:
    print(f"⚠️  ALREADY MODIFIED: {low_inventory_count}/{check_count} high-risk SKUs have low inventory")
    print("Skipping modification to prevent double-reduction (idempotent)")
    print("If you want to re-run, restore from backup: inventory.csv.backup")
    exit(0)

# Create backup before destructive operation
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_name = f'inventory.csv.backup'
shutil.copy2('inventory.csv', backup_name)
print(f"✅ Created backup: {backup_name}")

# Adjust inventory for high-risk SKUs
# We want ~30% of stores to be at risk or stockout for these promos
modified_count = 0
random.seed(42)  # Consistent results for repeatability

for row in rows:
    sku = row['SKU']
    store_id = row['Store ID']
    
    if sku in HIGH_RISK_SKUS:
        # Reduce inventory to create risk
        # Use a random factor to create variety
        risk_factor = random.choice([0.3, 0.4, 0.5, 0.6, 0.7])  # 30-70% of safe level
        
        # Current inventory should be LOWER than projected demand
        # For a 50% uplift promo, if baseline demand is 30, projected = 45
        # We want inventory around 15-30 to create stockout risk
        current_inv = int(float(row['Current Inventory']))
        new_inventory = max(5, int(current_inv * risk_factor))
        
        row['Current Inventory'] = str(new_inventory)
        modified_count += 1

print(f"Modified {modified_count} inventory records to create supply risk")

# Write back
with open('inventory.csv', 'w', newline='') as f:
    fieldnames = ['Store ID', 'SKU', 'Current Inventory', 'Reorder_Point',
                  'Lead_Time_Days', 'Safety_Stock_Level', 'Last_Restocked']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("✅ Inventory adjusted - high-uplift promos will now show supply chain constraints!")
print(f"\nAffected promos:")
for promo in HIGH_RISK_PROMOS:
    week, sku = promo.split('_')
    print(f"  - {week} {sku}")
print(f"\n💾 Backup saved as: {backup_name}")
print(f"   To restore: cp {backup_name} inventory.csv")