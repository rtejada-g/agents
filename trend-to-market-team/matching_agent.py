from google.adk.agents import Agent
from .config_loader import PRODUCT_CATALOG

MatchingAgent = Agent(
    name="MatchingAgent",
    model="gemini-2.5-flash",
    description="Finds and ranks products based on a trend.",
    instruction=f"""You are a product matching expert. Your goal is to find up to three relevant products from the catalog that match the given trend.

    1.  Analyze the user's trend description.
    2.  Compare the trend to the product information in the catalog.
    3.  Return a ranked list of up to three product SKUs that are the best match.
    4.  Your final output MUST be a single string of comma-separated SKUs. Example: '7890,5670,1234'

    Product Catalog:
    {PRODUCT_CATALOG}
    """,
)