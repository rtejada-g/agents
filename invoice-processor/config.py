"""
Configuration for Invoice Processor Agent
"""

# Company Configuration
COMPANY_NAME = "Publix"
DEFAULT_COMPANY_NAME = "Global Retail Corp"

# Company logo (URL or local path)
COMPANY_LOGO = "https://upload.wikimedia.org/wikipedia/commons/1/1e/Publix_Retail_Logo.png"  # Set to path/URL if available
DEFAULT_LOGO = None

# ERP System Configuration
ERP_SYSTEM_NAME = "SAP"
ERP_API_ENDPOINT = "https://api.sap.example.com"  # Mock endpoint

# Validation Rules
PRICE_TOLERANCE_PERCENT = 5.0  # Allow 5% price variance
QUANTITY_TOLERANCE_PERCENT = 2.0  # Allow 2% quantity variance

# File Paths
# Customer-specific data directory (e.g., "default", "customerA", "customerB")
# Pre-generated data files should exist in data/{CUSTOMER_DATA_SET}/
CUSTOMER_DATA_SET = "default"
OUTPUT_DIR = "output"