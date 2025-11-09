"""
Configuration for Aesthetic to Routine Agent

Supports data pivoting between different brand datasets (default, elc, etc.)
Similar pattern to invoice-processor/config.py
"""

import os

# Data set configuration - allows switching between different brand catalogs
BRAND_DATA_SET = os.getenv("BRAND_DATA_SET", "default")

# Company/Brand name for UI display
COMPANY_NAME = os.getenv("COMPANY_NAME", "Beauty Co")

# Routine configuration - Smart bounds
MAX_ROUTINE_STEPS = int(os.getenv("MAX_ROUTINE_STEPS", "10"))  # Raised to allow longer routines
MIN_ROUTINE_STEPS = int(os.getenv("MIN_ROUTINE_STEPS", "4"))   # Minimum for a complete routine

# Display configuration
SHOW_TRENDING_TERMS = os.getenv("SHOW_TRENDING_TERMS", "true").lower() == "true"
CAROUSEL_AUTO_SCROLL = os.getenv("CAROUSEL_AUTO_SCROLL", "true").lower() == "true"

# Default values (for when env vars aren't set)
DEFAULT_NAME = "Beauty Co"
DEFAULT_DATA_SET = "default"

print(f"[CONFIG] Loaded configuration:")
print(f"  - BRAND_DATA_SET: {BRAND_DATA_SET}")
print(f"  - COMPANY_NAME: {COMPANY_NAME}")
print(f"  - MAX_ROUTINE_STEPS: {MAX_ROUTINE_STEPS}")