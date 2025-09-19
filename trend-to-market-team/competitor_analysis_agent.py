import os
import requests
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

def search_competitors(product_name: str) -> dict:
    """Searches for competitor products using the Google Custom Search JSON API."""
    api_key = os.getenv("GOOGLE_API_KEY")
    search_engine_id = os.getenv("SEARCH_ENGINE_ID")
    
    if not api_key or not search_engine_id:
        return {"error": "Google API Key or Search Engine ID not found. Please set them in your .env file."}

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": f'"{product_name}" competitors',
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"An error occurred during the search: {e}"}

search_competitors_tool = FunctionTool(func=search_competitors)

CompetitorAnalysisAgent = Agent(
    name="CompetitorAnalysisAgent",
    model="gemini-2.5-flash",
    description="Analyzes competitor products and marketing strategies.",
    instruction="""You are a competitor intelligence analyst. Your goal is to analyze the competitive landscape for a given product.

    1.  Use the `search_competitors` tool with the product name to find similar products from competitors.
    2.  Analyze the search results to identify key competitors and their marketing strategies.
    3.  Produce a concise "Competitive Landscape" summary.
    4.  Your final output MUST be a single string containing the summary.
    """,
    tools=[search_competitors_tool],
)