"""
Configuration for S&OP Command Center Agent

Supports data pivoting between different customer datasets (default, elc, etc.)
"""

import os

# Data set configuration - allows switching between different customer catalogs
CUSTOMER_DATA_SET = os.getenv("CUSTOMER_DATA_SET", "default")

# Company name for UI display
COMPANY_NAME = os.getenv("COMPANY_NAME", "Estée Lauder Companies")

# Simulation parameters
SAFETY_STOCK_MULTIPLIER = float(os.getenv("SAFETY_STOCK_MULTIPLIER", "1.5"))
STOCKOUT_THRESHOLD = float(os.getenv("STOCKOUT_THRESHOLD", "0.15"))  # <15% inventory = at-risk
AT_RISK_THRESHOLD = float(os.getenv("AT_RISK_THRESHOLD", "0.30"))  # <30% inventory = at-risk

# Map configuration
DEFAULT_MAP_CENTER = [40.7589, -73.9851]  # NYC metro center
DEFAULT_MAP_ZOOM = 11

# Display configuration
SHOW_DSD_ROUTES = os.getenv("SHOW_DSD_ROUTES", "false").lower() == "true"

# Default values
DEFAULT_NAME = "CPG Company"
DEFAULT_DATA_SET = "default"

print(f"[CONFIG] Loaded S&OP Command Center configuration:")
print(f"  - CUSTOMER_DATA_SET: {CUSTOMER_DATA_SET}")
print(f"  - COMPANY_NAME: {COMPANY_NAME}")
print(f"  - SAFETY_STOCK_MULTIPLIER: {SAFETY_STOCK_MULTIPLIER}")
print(f"  - STOCKOUT_THRESHOLD: {STOCKOUT_THRESHOLD}")