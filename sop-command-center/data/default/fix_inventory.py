#!/usr/bin/env python3
"""Fix inventory.csv by adding Last_Restocked dates to all rows"""

import csv
import random
from datetime import datetime, timedelta

# Read the inventory file
with open('inventory.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Generate random restock dates within the last 2-4 weeks
def random_restock_date():
    days_ago = random.randint(3, 14)  # 3-14 days ago
    date = datetime.now() - timedelta(days=days_ago)
    return date.strftime('%Y-%m-%d')

# Update rows that don't have Last_Restocked
updated_count = 0
for row in rows:
    if not row.get('Last_Restocked') or row['Last_Restocked'] == '':
        row['Last_Restocked'] = random_restock_date()
        updated_count += 1

# Write back to file
with open('inventory.csv', 'w', newline='') as f:
    fieldnames = ['Store ID', 'SKU', 'Current Inventory', 'Reorder_Point', 
                  'Lead_Time_Days', 'Safety_Stock_Level', 'Last_Restocked']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Updated {updated_count} rows with Last_Restocked dates")
print(f"Total rows processed: {len(rows)}")