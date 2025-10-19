import os
import base64
import time
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
from .config_loader import PRODUCT_CATALOG, COMPANY_NAME, IMAGE_DATA_PATH
from .matching_agent import MatchingAgent
from .competitor_analysis_agent import CompetitorAnalysisAgent

load_dotenv()


# --- Client Initialization ---
http_options = types.HttpOptions(
    async_client_args={'read_bufsize': 16 * 1024 * 1024}
)
shared_client = genai.Client(vertexai=True, http_options=http_options)


# --- Tools ---

def get_product_data(sku_id: str) -> dict:
    """Gets the inventory, margin, and other data for a given product SKU."""
    return PRODUCT_CATALOG.get(sku_id, {"error": "Product not found"})

get_product_data_tool = FunctionTool(func=get_product_data)

async def get_product_image(tool_context: ToolContext, sku_id: str) -> dict:
    """Gets the product image for a given product SKU and saves it as an artifact."""

    image_path = os.path.join(os.path.dirname(__file__), f"{IMAGE_DATA_PATH}/{sku_id}.jpeg")
    if not os.path.exists(image_path):
        return {"error": f"Image for SKU {sku_id} not found at {image_path}"}

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    image_part = Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    artifact_name = f"product_{sku_id}.jpeg"
    await tool_context.save_artifact(artifact_name, image_part)
    return {"status": f"Image for SKU {sku_id} saved as artifact {artifact_name}"}

get_product_image_tool = FunctionTool(func=get_product_image)

async def generate_campaign_images(tool_context: ToolContext, sku_id: str, prompt: str, image_type: str) -> dict:
    """Generates a marketing image for a given product SKU and prompt."""
    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        print(f"[{time.time()}] Generating image for {image_type} (Attempt {attempt + 1}/{max_retries})...")
        start_time = time.time()

        # --- 2. Get SKU Image ---
        image_path = os.path.join(os.path.dirname(__file__), f"{IMAGE_DATA_PATH}/{sku_id}.jpeg")
        if not os.path.exists(image_path):
            return {"error": f"Image for SKU {sku_id} not found at {image_path}"}

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        # Mimic the console's base64 handling
        image_data = base64.b64decode(base64.b64encode(image_bytes))
        image_part = Part.from_bytes(data=image_data, mime_type="image/jpeg")

        # --- 3. Call Generative AI API and Save Artifacts ---
        try:
            text_part = Part.from_text(text=prompt)
            contents = Content(role="user", parts=[image_part, text_part])
            
            print(f"[{time.time()}] [{image_type}] Sending request to GenAI API...")
            
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

            response_chunks = await shared_client.aio.models.generate_content_stream(
                model="gemini-2.5-flash-image-preview",
                contents=[contents],
                config=generate_content_config
            )
            
            print(f"[{time.time()}] [{image_type}] GenAI API stream opened.")
            
            image_found = False
            async for chunk in response_chunks:
                print(f"[{time.time()}] [{image_type}] Received chunk: {chunk}")
                for part in chunk.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image_found = True
                        generated_part = Part(inline_data=Blob(
                            mime_type=part.inline_data.mime_type,
                            data=part.inline_data.data
                        ))
                        artifact_name = f"generated_{image_type}_{sku_id}.jpeg"
                        artifact_uri = await tool_context.save_artifact(artifact_name, generated_part)
                        end_time = time.time()
                        print(f"[{time.time()}] Finished generating image for {image_type} in {end_time - start_time:.2f}s")
                        return {image_type: artifact_uri}
                else:
                    continue
            
            if not image_found:
                print(f"[{time.time()}] [{image_type}] Stream finished but no image data was found.")

        except ValueError as e:
            if "Chunk too big" in str(e):
                print(f"[{time.time()}] [{image_type}] 'Chunk too big' error on attempt {attempt + 1}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue  # Go to the next attempt
            else:
                # Handle other ValueErrors
                print(f"API call failed for prompt '{prompt}' with a non-retryable ValueError:")
                traceback.print_exc()
                return {"error": f"API call failed for prompt '{prompt}': {e}"}
        except Exception as e:
            print(f"API call failed for prompt '{prompt}':")
            traceback.print_exc()
            return {"error": f"API call failed for prompt '{prompt}': {e}"}

    return {"error": f"Image generation failed for {image_type} after {max_retries} attempts."}

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


async def generate_prompt(style_description: str, product_name: str, image_type: str) -> str:
    """Generates a creative prompt for a marketing image."""
    print(f"[{time.time()}] Generating prompt for {image_type}...")
    start_time = time.time()
    try:
        response = await shared_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""You are a creative assistant. Your task is to generate a detailed, evocative prompt for an image generation model, based on the style_description provided.
            - Your input will be a high-level style description, the product name, and the desired image type (e.g., website_hero, instagram_post).
            - The prompt must always include the product being featured in the image (see examples)
            - The prompt must always be photorealistic, professional-quality
            - The image_type also influences the type of prompt (e.g. website_hero are usually wide, and feature a real life model, cinematic. instagram_post are usually lifestyle, cozy scene. email_header are very product-centric, clean background)
            - Your output MUST be a single string containing the generated prompt. No preamble or explanations, just a prompt under 250 characters. Here are a few examples:
            Example 1 Input: style_description='a chic city night', product_name='The City Handbag', image_type='website_hero'
            Example 1 Output: 'A photorealistic, professional-quality, wide, and cinematic shot of a model holding the product at a rooftop bar, with the sparkling city skyline blurred in the background.'

            Example 2 Input: style_description='cozy fall couch', product_name='The Autumn Cardigan', image_type='instagram_post'
            Example 2 Output: 'A photorealistic, professional-quality, lifestyle shot of the product draped over a plush couch, with soft, warm light and autumnal decor in the background.'

            Example 3 Input: style_description='minimalist morning vanity', product_name='Multi-Active Glow Serum', image_type='email_header'
            Example 3 Output: 'A photorealistic, professional-quality, product-centric shot of the product on a clean, white marble vanity table surface'
            
            Input: style_description='{style_description}', product_name='{product_name}', image_type='{image_type}'"""
        )
        end_time = time.time()
        print(f"[{time.time()}] Finished generating prompt for {image_type} in {end_time - start_time:.2f}s")
        return response.text
    except Exception as e:
        print(f"API call failed for prompt generation for {image_type}:")
        traceback.print_exc()
        return f"Error generating prompt for {image_type}: {e}"

generate_prompt_tool = FunctionTool(func=generate_prompt)


# --- Agents ---

# Agent 1: Opportunity Agent
OpportunityAgent = Agent(
    name="OpportunityAgent",
    model="gemini-2.5-flash",
    description="Analyzes market trends to identify product opportunities.",
    instruction="""You are the first agent in the trend-to-market team. Your input is a user prompt about a social media trend.
1.  Extract the trend description from the user prompt.
2.  Use the `MatchingAgent` with the trend description to get a list of matching product SKUs.
3.  For each SKU, use the `get_product_data` tool to get its business data.
4.  For each SKU, use the `get_product_image` tool. This will save the product image as an artifact, which will be automatically displayed to the user. Absolutely avoid placeholders in the text.
5.  Your final output MUST be a single, valid JSON object.
    - If you find products, the JSON should be: `{"status": "success", "output": "Product Options: ..."}`. The "output" value MUST be a string that starts with "Product Options:" followed by a numbered list of the products.
    - If you cannot find any matching products, the JSON should be: `{"status": "failure", "output": "I could not find any products matching that trend."}`.
    - It is critical that you only output the JSON object and nothing else. No preamble or explanations, just the JSON.

    Example Success Output:
    `{"status": "success", "output": "Product Options:\n1. SKU: SL-7890, Brand: Clinique, Name: The Autumn Cardigan, Price: 120, Inventory: 2500, Margin: 0.60, Category: apparel\n2. SKU: 5670, Brand: Estée Lauder, Name: The City Handbag, Inventory: 3300, Margin: 0.80, Category: apparel"}`""",
    tools=[AgentTool(agent=MatchingAgent), get_product_data_tool, get_product_image_tool],
)

# Agent 2: Ideation Agent
IdeationAgent = Agent(
    name="IdeationAgent",
    model="gemini-2.5-flash",
    description="Generates creative prompts for marketing images.",
    instruction="""You are the ideation agent. Your input is a product name, a competitive landscape summary, a desired style description, and a list of image types.
    1.  Your primary goal is to generate creative concepts based on the user's desired `style_description`.
    2.  You should use the `Competitive Landscape` for strategic inspiration to ensure your concepts are differentiated, but the user's `style_description` MUST be the core theme.
    3.  Use the `generate_prompt` tool in parallel to generate a prompt for the image_types. You MUST pass the `style_description`, `product_name`, and `image_type`.
    4.  Your final output MUST be a single string containing the generated prompts for the orchestrator to review. Example:
        'Generated Prompts:
        - Website Hero: A landscape, photorealistic shot of a model wearing the product in...
        - Instagram Post: A lifestyle, close-up shot of product's fabric on a...
        - Email Header: A product-centric shot of the product, clean background, on a ...'""",
    tools=[generate_prompt_tool],
)

# Agent 3: Generation Agent
GenerationAgent = Agent(
    name="GenerationAgent",
    model="gemini-2.5-flash-lite",
    description="Develops marketing campaign assets.",
    instruction="""You are the generation agent. Your input is a product SKU and a list of concepts.
    1.  For each concept in the list, use the `generate_campaign_images` tool in parallel using the concept as a prompt. You MUST pass the `sku_id` and `prompt`.
    2.  Your final output MUST be a structured summary of the results. Example for a mix of success and failure:
        'Image Generation Results:
        - Website Hero: Success
        - Instagram Post: Success
        - Email Header: Failed (error message)'
    3.  If all images are generated successfully, your output can be a simple confirmation. Example:
        'Campaign Brief for SKU 7890: All requested images have been generated and saved as artifacts.'""",
    tools=[generate_campaign_images_tool],
)

# Agent 4: Proposal Agent
ProposalAgent = Agent(
    name="ProposalAgent",
    model="gemini-2.5-flash",
    description="Develops a campaign proposal for user review.",
    instruction="""You are the third agent in a sequence. Your input is a campaign brief, the original product summary, and the competitive landscape summary.
1.  Analyze the campaign brief, the product's business data (margin, inventory), and the competitive landscape.
2.  Create a compelling proposal for the user that includes:
    - A catchy campaign slogan that is differentiated from the competition.
    - A brief summary of the target audience.
    - A final figure of projected revenue increase (assuming a 10% lift in sales), using the product's price and margin.
    - The final figure must be strictly formatted concisely as "Projected Revenue Increase: $X". This should be the first and only mention of "Projected Revenue Increase" in the text.
    - A one or two sentences on the potential risks (e.g., inventory shortages, low engagement, competitive, etc.), and possible mitigation strategies.
3.  Your final output MUST be a single string containing the full proposal for the orchestrator.""",
)

# Orchestrator Agent
root_agent = Agent(
    name="MarketingAgent",
    model="gemini-2.5-flash",
    description="An orchestrator agent that manages the trend-to-market team.",
    instruction=f"""You are the orchestrator of a multi-agent trend-to-market team at {COMPANY_NAME}. Your goal is to guide the user through a step-by-step process of identifying a market trend, creating a campaign, and launching it. You MUST manage the context between steps.

**Workflow & State Management:**

0.  **Greeting:**
    a. If the user greets you, introduce yourself including a simplified title (Trend-to-Market Agent is fine), the company you're with, and a very concise sentence outlining your purpose.

1.  **Opportunity Analysis:**
    a. Call the `OpportunityAgent` with the user's initial request about a trend.
    b. The result will be a JSON object. You MUST parse this JSON.
    c. If the `status` is `success`, capture the `output` (which will be the "Product Options" string) and present the options to the user in a simple friendly list.
    d. If the `status` is `failure`, you MUST stop and present the `output` (which will be the error message) to the user.

2.  **Competitive Analysis:**
    a. Once the user selects a product, you MUST **capture the full `Product Summary` for that selected product, including SKU, name, price, margin, and inventory.**
    b. Call the `CompetitorAnalysisAgent` with the selected product's name.
    c. **Capture the `Competitive Recommendations` summary from the result.**
    d. Present a one liner on the search results, a short sentence on how they lead to the recommendations, and the recommended themes to the user

3.  **Ideation:**
    a. Ask if they'd like to use any of the recommended styles, or their own description. Also ask for image types (Website Hero, Instagram Post, Email Header).
    b. **Capture the user's selected `style_description` and `image_types`.**
    c. Call the `IdeationAgent` tool. You MUST format the `request` as a single string that includes the captured `product_name`, `Competitive Landscape`, the user's selected `style_description`, and `image_types`.
    d. **Capture the `Generated Prompts` from the result.**
    e. Summarize the prompts as "Concepts" under 12 words, present the concept for each image type to the user, and ask the user to approve them.

4.  **Creative Generation:**
    a. If the user approves, call the `GenerationAgent` tool. You MUST pass a `request` that includes the captured `sku_id` and the full `Generated Prompts`.
    b. Ask if they are ready for a proposal.

5.  **Proposal:**
    a. If the user agrees, call the `ProposalAgent` tool. You MUST pass a `request` that includes the captured `Product Summary`, the `Campaign Brief`, and the `Competitive Landscape`.
    b. **Capture the full `Campaign Proposal` from the result.**
    c. Present the full proposal to the user.

6.  **Activation:**
    a. Ask the user for final approval to launch the campaign.
    b. **You MUST wait for an explicit "yes" or "approve" from the user.**
    c. Once approval is given, use the `launch_marketing_campaign` tool, passing the captured `Campaign Proposal` as the `campaign_brief`. This will trigger the final HITL confirmation.

7.  **Error Handling:**
    a. If the `OpportunityAgent` does not return a "Product Options:" string, you MUST stop and inform the user with a friendly message. Example: "I couldn't find a specific product for that trend. Could you try being more specific?"
    b. If any other agent or tool returns an error, stop the entire process and inform the user about the error.
""",
    tools=[
        AgentTool(agent=OpportunityAgent),
        AgentTool(agent=CompetitorAnalysisAgent),
        AgentTool(agent=IdeationAgent),
        AgentTool(agent=GenerationAgent),
        AgentTool(agent=ProposalAgent),
        launch_marketing_campaign_tool,
    ],
)