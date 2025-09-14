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
from google.adk.agents import Agent, SequentialAgent
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
        "cherry red cardigan": "7890"
    }
    return VISUAL_MATCH_DATA.get(trend_description, "SKU not found")

def get_product_data(sku_id: str) -> dict:
    """Gets the inventory, margin, and other data for a given product SKU."""
    PRODUCT_CATALOG = {
        "7890": {
            "displayName": "The Autumn Cardigan",
            "description": "A stylish and comfortable cardigan, perfect for the autumn season.",
            "price": 68.00,
            "inventory": 2500,
            "margin": 0.60
        }
    }
    return PRODUCT_CATALOG.get(sku_id, {"error": "Product not found"})

find_visual_match_tool = FunctionTool(func=find_visual_match)
get_product_data_tool = FunctionTool(func=get_product_data)

async def generate_campaign_images(tool_context: ToolContext, sku_id: str) -> dict:
    """Generates a set of marketing images for a given product SKU."""

    client = genai.Client(vertexai=True)
    prompts = {
        "website_hero": "A wide, cinematic shot of a model walking through a beautiful, sun-drenched park with golden autumn leaves, wearing this cardigan.",
        "instagram_post": "A 'flat lay' of this cardigan on a cozy blanket with a book and a cup of coffee.",
        "email_header": "This cardigan draped over a chic chair next to a window showing an autumn scene."
    }

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
    generated_image_uris = {}
    for key, prompt in prompts.items():
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
                        artifact_name = f"generated_{key}_{sku_id}.png"
                        artifact_uri = await tool_context.save_artifact(artifact_name, generated_part)
                        generated_image_uris[key] = artifact_uri
                        break  # Assuming one image per prompt
                else:
                    continue
                break
                if part.inline_data is not None:
                    generated_part = Part(inline_data=Blob(
                        mime_type=part.inline_data.mime_type,
                        data=part.inline_data.data
                    ))
                    artifact_name = f"generated_{key}_{sku_id}.png"
                    artifact_uri = await tool_context.save_artifact(artifact_name, generated_part)
                    generated_image_uris[key] = artifact_uri
                    break  # Assuming one image per prompt

        except Exception as e:
            print(f"API call failed for prompt '{key}':")
            traceback.print_exc()
            return {"error": f"API call failed for prompt '{key}': {e}"}

    return generated_image_uris

generate_campaign_images_tool = FunctionTool(func=generate_campaign_images)

def launch_marketing_campaign(tool_context: ToolContext, campaign_brief: str) -> str:
    """Launches the marketing campaign after receiving final approval."""
    
    if not tool_context.tool_confirmation:
        # First call: Request confirmation from the user
        tool_context.request_confirmation(
            hint="The campaign is projected to generate an additional $250,000 in revenue. Are you ready to launch?"
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
opportunity_agent = Agent(
    name="opportunity_agent",
    model="gemini-2.5-flash",
    description="Analyzes market trends to identify product opportunities.",
    instruction="""You are the first agent in a sequence. Your input is a user prompt about a social media trend.
1.  Extract the trend description from the user prompt.
2.  Call the `find_visual_match` tool with the trend description to get the product SKU.
3.  Call the `get_product_data` tool with the SKU to get its business data.
4.  Your final output MUST be a single string containing a summary of your findings for the next agent. Example:
    'SKU: 7890, Name: The Autumn Cardigan, Inventory: 2500, Margin: 0.60'""",
    tools=[find_visual_match_tool, get_product_data_tool],
)

# Agent 2: Creative Agent
creative_agent = Agent(
    name="creative_agent",
    model="gemini-2.5-flash",
    description="Develops marketing campaign assets.",
    instruction="""You are the second agent in a sequence. Your input is a string with product data from the previous agent.
1.  Parse the input to identify the SKU.
2.  Call the `generate_campaign_images` tool with the SKU.
3.  Your final output MUST be a single string containing a campaign brief for the next agent, including the image URIs. Example:
    'Campaign Brief for SKU 7890: Generated images are ready. website_hero: [URI], instagram_post: [URI], email_header: [URI]'""",
    tools=[generate_campaign_images_tool],
)

# Agent 3: Activation Agent
activation_agent = Agent(
    name="activation_agent",
    model="gemini-2.5-flash",
    description="Launches marketing campaigns after receiving final approval.",
    instruction="""You are the final agent in a sequence. Your input is a campaign brief from the previous agent.
1.  Summarize the campaign brief for the user.
2.  Call the `launch_marketing_campaign` tool, passing the campaign brief as the `campaign_brief` argument.
3.  Your final output will be the result of the tool call.""",
    tools=[launch_marketing_campaign_tool],
)


# Orchestrator Agent
root_agent = SequentialAgent(
    name="trend_to_market_team",
    sub_agents=[opportunity_agent, creative_agent, activation_agent],
)