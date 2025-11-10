#!/usr/bin/env python3
"""Convert products.json from object to array format"""

import json

# Read the current file
with open('products.json', 'r') as f:
    data = json.load(f)

# Extract the products array
if isinstance(data, dict) and 'products' in data:
    products_array = data['products']
    print(f"✅ Extracted {len(products_array)} products from wrapper object")
elif isinstance(data, list):
    products_array = data
    print(f"✅ Already an array with {len(products_array)} products")
else:
    print(f"❌ Unexpected format: {type(data)}")
    exit(1)

# Write back as pure array
with open('products.json', 'w') as f:
    json.dump(products_array, f, indent=2)

print(f"✅ Successfully converted products.json to array format")