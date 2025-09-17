# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Trend-to-Market Agent Team"""

import os
import base64
import traceback
from dotenv import load_dotenv
import re
from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.adk.tools import FunctionTool, ToolContext
from google import genai
from google.genai import types
from google.genai.types import Content, Part, Blob
from PIL import Image
from io import BytesIO

load_dotenv()


# --- Tools ---

def find_visual_match(trend_description: str) -> str:
    """Finds a product SKU that visually matches the described trend."""
    VISUAL_MATCH_DATA = {
        "cherry red cardigan": "7890",
        "red cardigan": "7890",
        "autumn cardigan": "7890",
        "cozy cardigan": "7890",
        "black louis vuitton bag": "5670",
        "black handbag": "5670",
        "city handbag": "5670",
        "crossover handbag": "5670",
        "crossover bag": "5670",
        "designer bag": "5670",
        "hydrating moisturizer": "1234",
        "hydrating cream": "1234",
        "hydrating face cream": "1234",
        "face cream": "1234",
        "luxury serum": "9876",
        "glow serum": "9876",
        "anti-aging serum": "9876"
    }
    return VISUAL_MATCH_DATA.get(trend_description, "SKU not found")

def get_product_data(sku_id: str) -> dict:
    """Gets the inventory, margin, and other data for a given product SKU."""
    PRODUCT_CATALOG = {
        "7890": {
            "displayName": "The Autumn Cardigan",
            "description": "A stylish and comfortable cardigan, perfect for the autumn season.",
            "price": 120.00,
            "inventory": 12500,
            "margin": 0.65,
            "category": "apparel"
        },
        "5670": {
            "displayName": "The City Handbag",
            "description": "An elegant and versatile handbag, ideal for any urban adventure.",
            "price": 3000.00,
            "inventory": 3300,
            "margin": 0.80,
            "category": "apparel"
        },
        "1234": {
            "displayName": "HydraBoost Moisturizer",
            "description": "A deeply hydrating moisturizer for all skin types.",
            "price": 27.00,
            "inventory": 10000,
            "margin": 0.85,
            "category": "beauty"
        },
        "9876": {
            "displayName": "Multi-Active Glow Serum",
            "description": "A luxurious serum that refines skin",
            "price": 70.00,
            "inventory": 1500,
            "margin": 0.8,
            "category": "beauty"
        }
    }
    return PRODUCT_CATALOG.get(sku_id, {"error": "Product not found"})

find_visual_match_tool = FunctionTool(func=find_visual_match)
get_product_data_tool = FunctionTool(func=get_product_data)

async def get_product_image(tool_context: ToolContext, sku_id: str) -> dict:
    """Gets the product image for a given product SKU and saves it as an artifact."""

    image_path = os.path.join(os.path.dirname(__file__), f"data/{sku_id}.png")
    if not os.path.exists(image_path):
        return {"error": f"Image for SKU {sku_id} not found at {image_path}"}

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    image_part = Part.from_bytes(data=image_bytes, mime_type="image/png")

    artifact_name = f"product_{sku_id}.png"
    await tool_context.save_artifact(artifact_name, image_part)
    return {"status": f"Image for SKU {sku_id} saved as artifact {artifact_name}"}

get_product_image_tool = FunctionTool(func=get_product_image)

async def generate_campaign_images(tool_context: ToolContext, sku_id: str, prompt: str, image_type: str) -> dict:
    """Generates a marketing image for a given product SKU and prompt."""

    client = genai.Client(vertexai=True)

    # --- 2. Get SKU Image ---
    image_path = os.path.join(os.path.dirname(__file__), f"data/{sku_id}.png")
    if not os.path.exists(image_path):
        return {"error": f"Image for SKU {sku_id} not found at {image_path}"}

    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    # Mimic the console's base64 handling
    image_data = base64.b64decode(base64.b64encode(image_bytes))
    image_part = Part.from_bytes(data=image_data, mime_type="image/png")

    # --- 3. Call Generative AI API and Save Artifacts ---
    try:
        text_part = Part.from_text(text=prompt)
        contents = Content(role="user", parts=[image_part, text_part])
        
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            safety_settings = [types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE"
            ),types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE"
            ),types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE"
            ),types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE"
            )],
        )

        response_chunks = client.models.generate_content_stream(
            model="gemini-2.5-flash-image-preview",
            contents=[contents],
            config=generate_content_config
        )

        for chunk in response_chunks:
            for part in chunk.candidates[0].content.parts:
                if part.inline_data is not None:
                    generated_part = Part(inline_data=Blob(
                        mime_type=part.inline_data.mime_type,
                        data=part.inline_data.data
                    ))
                    artifact_name = f"generated_{image_type}_{sku_id}.png"
                    artifact_uri = await tool_context.save_artifact(artifact_name, generated_part)
                    return {image_type: artifact_uri}
            else:
                continue
            break

    except Exception as e:
        print(f"API call failed for prompt '{prompt}':")
        traceback.print_exc()
        return {"error": f"API call failed for prompt '{prompt}': {e}"}

    return {"error": "Image generation failed"}

generate_campaign_images_tool = FunctionTool(func=generate_campaign_images)

def launch_marketing_campaign(tool_context: ToolContext, campaign_brief: str) -> str:
    """Launches the marketing campaign after receiving final approval."""
    
    if not tool_context.tool_confirmation:
        # First call: Request confirmation from the user
        
        # Extract projected revenue from the campaign brief
        projected_revenue_text = "an additional $250,000" # Default value
        # Regex to find dollar amounts related to revenue increase
        match = re.search(r"projected revenue increase.*?(\$[\d,]+\.?\d*)", campaign_brief, re.IGNORECASE | re.DOTALL)
        
        if match:
            projected_revenue_text = f"an additional {match.group(1)}"

        tool_context.request_confirmation(
            hint=f"The campaign is projected to generate {projected_revenue_text} in revenue. Are you ready to launch?"
        )
        return "" # Important: Return nothing to wait for the user's response
    
    # Second call: Process the user's decision
    if tool_context.tool_confirmation.confirmed:
        return "Campaign was approved by the user and has been launched."
    else:
        return "Campaign was rejected by the user."

launch_marketing_campaign_tool = FunctionTool(func=launch_marketing_campaign)


# --- Agents ---

# Agent 1: Opportunity Agent
OpportunityAgent = Agent(
    name="OpportunityAgent",
    model="gemini-2.5-flash",
    description="Analyzes market trends to identify product opportunities.",
    instruction="""You are the first agent in the trend-to-market team. Your input is a user prompt about a social media trend.
1.  Extract the trend description from the user prompt.
2.  Call the `find_visual_match` tool with the trend description to get the product SKU.
3.  Call the `get_product_data` tool with the SKU to get its business data.
4.  Call the `get_product_image` tool with the SKU. This will save the product image as an artifact, which will be automatically displayed to the user. Absolutely avoid placeholders in the text.
5.  Your final output MUST be a single string containing a summary of your findings for the orchestrator. Example:
    'Product Summary: SKU: 7890, Name: The Autumn Cardigan, Inventory: 2500, Margin: 0.60, Category: apparel'""",
    tools=[find_visual_match_tool, get_product_data_tool, get_product_image_tool],
)

# Agent 2: Ideation Agent
IdeationAgent = Agent(
    name="IdeationAgent",
    model="gemini-2.5-flash",
    description="Generates creative prompts for marketing images.",
    instruction="""You are a creative assistant. Your task is to generate a detailed, evocative prompt for an image generation model.
    - Your input will be a high-level style description, the product name, and the desired image type (e.g., website_hero, instagram_post).
    - Your output MUST be a single string containing the generated prompt.
    - Example Input: style_description='a cozy fall afternoon', product_name='The Autumn Cardigan', image_type='website_hero'
    - Example Output: 'A wide, cinematic shot of a model wearing The Autumn Cardigan, walking through a beautiful, sun-drenched park with golden autumn leaves.'""",
)

# Agent 3: Creative Agent
CreativeAgent = Agent(
    name="CreativeAgent",
    model="gemini-2.5-flash",
    description="Develops marketing campaign assets.",
    instruction="""You are the second agent in a sequence. Your input is a product summary, a desired style description, and a list of image types.
    1.  Parse the input to identify the SKU and product name.
    2.  For each image type in the list, call the `IdeationAgent` to generate a prompt. You MUST pass the `style_description`, `product_name`, and `image_type`.
    3.  For each generated prompt, call the `generate_campaign_images` tool. You MUST pass the `sku_id`, `prompt`, and `image_type`.
    4.  Your final output MUST be a single string confirming that the images have been generated. Example:
        'Campaign Brief for SKU 7890: The requested images have been generated and saved as artifacts.'""",
    tools=[AgentTool(agent=IdeationAgent), generate_campaign_images_tool],
)

# Agent 3: Proposal Agent
ProposalAgent = Agent(
    name="ProposalAgent",
    model="gemini-2.5-flash",
    description="Develops a campaign proposal for user review.",
    instruction="""You are the third agent in a sequence. Your input is a campaign brief and the original product summary.
1.  Analyze the campaign brief and the product's business data (margin, inventory) from the summary.
2.  Create a compelling proposal for the user that includes:
    - A catchy campaign slogan.
    - A brief summary of the target audience.
    - A final figure of projected revenue increase (assuming a 10% lift in sales), using the product's price and margin.
    - The final figure must be strictly formatted concisely as "Projected Revenue Increase: $X". This should be the first and only mention of "Projected Revenue Increase" in the text.
    - A summary of the potential risks (e.g., inventory shortages, low engagement), considering the product's inventory.
3.  Your final output MUST be a single string containing the full proposal for the orchestrator.""",
)

# Orchestrator Agent
root_agent = Agent(
    name="MarketingAgent",
    model="gemini-2.5-flash",
    description="An orchestrator agent that manages the trend-to-market team.",
    instruction="""You are the orchestrator of a multi-agent team. Your goal is to guide the user through a step-by-step process of identifying a market trend, creating a campaign, and launching it. You MUST manage the context between steps.

**Workflow & State Management:**

1.  **Opportunity Analysis:**
    a. Call the `OpportunityAgent` with the user's initial request about a trend.
    b. **Capture the full `Product Summary` from the result.**
    c. Present the findings and ask if they want to proceed.

2.  **Creative Development:**
    a. If the user agrees, ask for a freeform description of the desired campaign style (e.g., "a cozy fall afternoon"). Also ask for image types (Website Hero, Instagram Post, Email Header).
    b. **Capture the user's selected `style_description` and `image_types`.**
    c. **Interpret the user's response flexibly.** You MUST map natural language requests to the correct tool parameters. For example:
        - "a cozy fall afternoon, and only for social media" should be mapped to style_description='a cozy fall afternoon' and image_types=['instagram_post'].
        - "website and social media" should be mapped to image_types=['website_hero', 'instagram_post'].
        - "all of them" should be mapped to image_types=['website_hero', 'instagram_post', 'email_header'].
    d. Call the `CreativeAgent` tool. You MUST pass a `request` that includes the captured `Product Summary`, the user's selected `style_description`, and `image_types`.
    e. **Capture the full `Campaign Brief` from the result.**
    f. Ask if they are ready for a proposal.

3.  **Proposal:**
    a. If the user agrees, call the `ProposalAgent` tool. You MUST pass a `request` that includes the captured `Product Summary`, the `Campaign Brief`, and the selected `style`.
    b. **Capture the full `Campaign Proposal` from the result.**
    c. Present the full proposal to the user.

4.  **Activation:**
    a. Ask the user for final approval to launch the campaign.
    b. **You MUST wait for an explicit "yes" or "approve" from the user.**
    c. Once approval is given, call the `launch_marketing_campaign` tool, passing the captured `Campaign Proposal` as the `campaign_brief`. This will trigger the final HITL confirmation.

5.  **Error Handling:** If any agent or tool returns an error, stop the entire process and inform the user about the error.
""",
    tools=[
        AgentTool(agent=OpportunityAgent),
        AgentTool(agent=CreativeAgent),
        AgentTool(agent=ProposalAgent),
        launch_marketing_campaign_tool,
    ],
)