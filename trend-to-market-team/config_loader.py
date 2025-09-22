import os
import json

COMPANY_NAME = os.getenv("COMPANY_NAME", "Google")
IMAGE_DATA_PATH = os.getenv("IMAGE_DATA_PATH", "images")
PRODUCT_CATALOG_FILE = os.getenv("PRODUCT_CATALOG_FILE", "catalogs/default.json")

def load_product_catalog():
    """Loads the product catalog from the JSON file specified in the .env file."""
    dir_path = os.path.dirname(os.path.realpath(__file__))
    catalog_path = os.path.join(dir_path, PRODUCT_CATALOG_FILE)
    
    try:
        with open(catalog_path, "r") as f:
            print(f"Successfully loaded product catalog from '{PRODUCT_CATALOG_FILE}'.")
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading product catalog from '{catalog_path}': {e}. Attempting to load default catalog.")
        try:
            default_catalog_path = os.path.join(dir_path, "catalogs", "default.json")
            with open(default_catalog_path, "r") as f:
                print("Successfully loaded default product catalog.")
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading default product catalog: {e}. Using an empty catalog as a fallback.")
            return {}

# Load the catalog once and make it available for import
PRODUCT_CATALOG = load_product_catalog()