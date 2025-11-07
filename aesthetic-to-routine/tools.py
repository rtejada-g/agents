"""
Tools for Multi-Agent Aesthetic to Routine System

Specialized tools for Product Specialist, Brand Voice, Image Generation, and Why Copy agents.
"""

import json
import os
import base64
import time
from typing import Dict, Any, List, Optional
from google.adk.tools import FunctionTool, ToolContext
from google.adk.events import Event, EventActions
from google.genai import types
from google import genai
from . import config


# ============================================================================
# Shared GenAI Client (from trend-to-market pattern)
# ============================================================================

http_options = types.HttpOptions(
    async_client_args={'read_bufsize': 16 * 1024 * 1024}
)
shared_client = genai.Client(vertexai=True, http_options=http_options)

# ============================================================================
# Artifact Saving Tools (matching trend-to-market pattern)
# ============================================================================

async def save_brand_logo(
    tool_context: ToolContext,
    brand: str
) -> Dict[str, Any]:
    """
    Saves a brand logo as an artifact.
    Matches naming convention: brand_clinique.png (underscores, no "logo" suffix)
    """
    # Match orchestrator naming: underscores, not hyphens
    brand_slug = brand.lower().replace(' ', '_').replace('.', '')
    logo_filename = f"brand_{brand_slug}.png"
    
    # Path to logo in data folder
    logo_path = os.path.join(
        os.path.dirname(__file__),
        f"data/{config.BRAND_DATA_SET}/images/brands/{logo_filename}"
    )
    
    if not os.path.exists(logo_path):
        print(f"[SAVE_LOGO] Logo not found: {logo_path}")
        return {"status": "not_found", "brand": brand}
    
    try:
        with open(logo_path, "rb") as f:
            logo_bytes = f.read()
        
        logo_part = types.Part.from_bytes(data=logo_bytes, mime_type="image/png")
        # Use same name as file for consistency
        artifact_name = logo_filename
        await tool_context.save_artifact(artifact_name, logo_part)
        
        print(f"[SAVE_LOGO] ✓ Saved logo for {brand}")
        return {
            "status": "success",
            "artifact_name": artifact_name,
            "brand": brand
        }
    except Exception as e:
        print(f"[SAVE_LOGO] ✗ Error saving logo for {brand}: {e}")
        return {"status": "error", "error": str(e), "brand": brand}


async def save_product_image(
    tool_context: ToolContext,
    product_sku: str
) -> Dict[str, Any]:
    """
    Saves a product image as an artifact.
    Matches trend-to-market pattern (line 37-52).
    """
    # Path to product image in data folder
    image_path = os.path.join(
        os.path.dirname(__file__),
        f"data/{config.BRAND_DATA_SET}/images/products/{product_sku}.jpg"
    )
    
    if not os.path.exists(image_path):
        print(f"[SAVE_PRODUCT_IMAGE] Image not found: {image_path}")
        return {"status": "not_found", "sku": product_sku}
    
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        artifact_name = f"product_{product_sku}.jpg"
        await tool_context.save_artifact(artifact_name, image_part)
        
        print(f"[SAVE_PRODUCT_IMAGE] ✓ Saved product image for SKU {product_sku}")
        return {
            "status": "success",
            "artifact_name": artifact_name,
            "sku": product_sku
        }
    except Exception as e:
        print(f"[SAVE_PRODUCT_IMAGE] ✗ Error saving product image for {product_sku}: {e}")
        return {"status": "error", "error": str(e), "sku": product_sku}



def load_json_data(filename: str) -> Dict[str, Any]:
    """Loads JSON data from the configured brand dataset."""
    data_path = os.path.join(
        os.path.dirname(__file__),
        "data",
        config.BRAND_DATA_SET,
        filename
    )
    
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[DATA_LOADER] ERROR loading {filename}: {e}")
        return {}


# ============================================================================
# TOOL 1: Search Products (for Product Specialist)
# ============================================================================

def search_products(
    aesthetic_id: str,
    skin_type: Optional[str] = None,
    concerns: Optional[List[str]] = None,
    skin_tone: Optional[str] = None
) -> Dict[str, Any]:
    """
    Searches product catalog for matches based on aesthetic and preferences.
    Used by Product Specialist agent.
    
    Args:
        aesthetic_id: Selected aesthetic (e.g., "ethereal-glow")
        skin_type: User's skin type (e.g., "Dry")
        concerns: User's main concerns (e.g., ["Hydration", "Anti-Aging"])
        skin_tone: User's skin tone hex (e.g., "#F5D7C4")
    
    Returns:
        Dictionary with matched products list
    """
    print(f"[SEARCH_PRODUCTS] Aesthetic: {aesthetic_id}, Skin: {skin_type}, Concerns: {concerns}, Tone: {skin_tone}")
    
    # Load data
    products_data = load_json_data("products.json")
    aesthetics_data = load_json_data("aesthetics.json")
    
    if not products_data or "products" not in products_data:
        return {
            "status": "error",
            "error_message": "Failed to load product catalog",
            "products": []
        }
    
    products = products_data["products"]
    
    # Get aesthetic name
    aesthetic_name = aesthetic_id.replace("-", " ").title()
    if aesthetics_data and "aesthetics" in aesthetics_data:
        aesthetic_obj = next(
            (a for a in aesthetics_data["aesthetics"] if a["id"] == aesthetic_id),
            None
        )
        if aesthetic_obj:
            aesthetic_name = aesthetic_obj.get("title", aesthetic_obj.get("name", aesthetic_name))
    
    # Normalize filters
    skin_type_lower = skin_type.lower() if skin_type else None
    concerns_lower = [c.lower() for c in concerns] if concerns else []
    
    # DYNAMIC ROUTINE BUILDING: Build a routine based on quiz inputs
    # Standard routine structure based on actual product data
    # Products use: category="base/lip/eye/cheek/other" with sub_category
    routine_steps = [
        {"category": "other", "sub_category": "cleanser", "display": "Cleanser"},
        {"category": "base", "sub_category": "serum", "display": "Serum"},
        {"category": "base", "sub_category": "moisturizer", "display": "Moisturizer"},
        {"category": "eye", "sub_category": "mascara", "display": "Eye"},
        {"category": "base", "sub_category": "primer", "display": "Primer"},
    ]
    
    matched_products = []
    
    for step_config in routine_steps[:config.MAX_ROUTINE_STEPS]:
        category = step_config["category"]
        sub_category = step_config.get("sub_category")
        display_name = step_config.get("display", category.title())
        
        # Find matching products
        candidates = [
            p for p in products
            if p.get("category", "").lower() == category.lower()
            and (not sub_category or p.get("sub_category", "").lower() == sub_category.lower())
        ]
        
        # Filter by skin type (prioritize exact matches, fallback to "All")
        if skin_type_lower and candidates:
            exact_matches = [
                p for p in candidates
                if skin_type_lower in [st.lower() for st in p.get("skin_types", [])]
            ]
            if exact_matches:
                candidates = exact_matches
            else:
                # Fallback to "All" skin types
                all_matches = [
                    p for p in candidates
                    if "all" in [st.lower() for st in p.get("skin_types", [])]
                ]
                if all_matches:
                    candidates = all_matches
        
        # Filter by concerns (prioritize products that address user's concerns)
        if concerns_lower and candidates:
            concern_matches = [
                p for p in candidates
                if any(concern in [c.lower() for c in p.get("concerns", [])] for concern in concerns_lower)
            ]
            if concern_matches:
                candidates = concern_matches
        
        # Pick best match
        if candidates:
            product = candidates[0].copy()
            product["step_category_display"] = display_name
            matched_products.append(product)
        else:
            # Log if no match found for debugging
            print(f"[SEARCH_PRODUCTS] No products found for {category}/{sub_category}")
    
    print(f"[SEARCH_PRODUCTS] Dynamically matched {len(matched_products)} products")
    
    return {
        "status": "success",
        "aesthetic_name": aesthetic_name,
        "products": matched_products,
        "product_count": len(matched_products)
    }

search_products_tool = FunctionTool(func=search_products)


# ============================================================================
# TOOL 2: Generate Product Copy (for Brand Voice Agent)
# ============================================================================

def generate_product_copy(
    aesthetic_id: str,
    skin_type: str,
    concerns: List[str],
    skin_tone: str,
    products: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generates polished, personalized copy for each product.
    Used by Brand Voice agent.
    
    Args:
        aesthetic_id: The aesthetic ID
        skin_type: User's skin type
        concerns: User's concerns (array)
        skin_tone: User's skin tone hex
        products: List of products to enhance with copy
    
    Returns:
        Dictionary with enhanced products including "why_this" copy
    """
    print(f"[GENERATE_COPY] Creating copy for {len(products)} products")
    
    enhanced_products = []
    
    for product in products:
        # Get base "why" from recipe if available
        base_why = product.get("step_note", "")
        
        # Create personalized copy
        why_segments = []
        
        # Start with recipe reason or category
        if base_why:
            why_segments.append(base_why)
        else:
            category = product.get("step_category_display", product.get("category", "product"))
            why_segments.append(f"Essential {category.lower()} for your routine")
        
        # Add skin type personalization
        if skin_type and skin_type.lower() != "normal":
            why_segments.append(f"formulated for {skin_type.lower()} skin")
        
        # Add concern targeting (first concern)
        if concerns and len(concerns) > 0:
            primary_concern = concerns[0].lower()
            concern_mapping = {
                "hydration": "delivers deep moisture",
                "anti-aging": "targets fine lines and firmness",
                "acne": "helps clear and prevent breakouts",
                "redness": "calms and soothes irritation",
                "dullness": "brightens and revitalizes",
                "dark spots": "evens skin tone"
            }
            concern_text = concern_mapping.get(primary_concern)
            if concern_text:
                why_segments.append(concern_text)
        
        # Combine into polished sentence
        if len(why_segments) == 1:
            why_this = f"{why_segments[0]}."
        elif len(why_segments) == 2:
            why_this = f"{why_segments[0]}, {why_segments[1]}."
        else:
            why_this = f"{why_segments[0]} — {', '.join(why_segments[1:])}."
        
        # Capitalize first letter
        why_this = why_this[0].upper() + why_this[1:]
        
        # Add to enhanced product
        enhanced = product.copy()
        enhanced["why_this_base"] = why_this  # Base copy for fallback
        enhanced_products.append(enhanced)
    
    print(f"[GENERATE_COPY] Enhanced {len(enhanced_products)} products with personalized copy")
    
    return {
        "status": "success",
        "enhanced_products": enhanced_products,
        "product_count": len(enhanced_products)
    }

generate_product_copy_tool = FunctionTool(func=generate_product_copy)


# ============================================================================
# TOOL 3: Generate Product Image (AI-powered, from trend-to-market pattern)
# ============================================================================

async def generate_product_image(
    tool_context: ToolContext,
    product_sku: str,
    product_name: str,
    brand: str,
    category: str,
    instruction: str,
    full_instruction: str,
    skin_type: str,
    skin_tone: str,
    concerns: List[str],
    aesthetic_name: str
) -> Dict[str, Any]:
    """
    Generates personalized product application image using gemini-2.5-flash-image-preview.
    Uses the main instruction (title) for action, full instruction for prep context.
    """
    max_retries = 3
    retry_delay = 2  # seconds
    
    # Determine application area from category
    application_areas = {
        "cleanser": "face and eyes",
        "serum": "face and neck",
        "moisturizer": "face",
        "foundation": "face",
        "primer": "face",
        "essence": "face",
        "lipstick": "lips",
        "mascara": "eyelashes",
        "eyeliner": "eyes",
        "eyeshadow": "eyelids",
        "blush": "cheeks",
        "highlighter": "cheekbones",
        "contour": "face structure",
        "setting spray": "face"
    }
    
    # Get application area (default to face if category not found)
    app_area = "face"
    cat_lower = category.lower()
    for key in application_areas:
        if key in cat_lower:
            app_area = application_areas[key]
            break
    
    concerns_text = ", ".join(concerns[:2]) if concerns else "healthy skin"
    
    # Extract prep context + product type for realistic texture
    prep_hints = []
    full_lower = full_instruction.lower()
    product_lower = product_name.lower()
    category_lower = category.lower()
    
    # Product type detection (affects texture)
    product_type = "cream"  # default
    if any(term in product_lower or term in category_lower for term in ['serum', 'oil', 'essence', 'repair', 'night repair']):
        product_type = "serum/oil"
        prep_hints.append("SERUM/OIL texture (lightweight, barely visible, translucent - NOT thick cream)")
    elif any(term in product_lower or term in category_lower for term in ['moisturizer', 'cream', 'balm']):
        product_type = "cream"
    elif any(term in product_lower or term in category_lower for term in ['primer', 'base']):
        product_type = "primer"
    
    # Amount detection
    if 'pea-sized' in full_lower or 'pearl-sized' in full_lower:
        prep_hints.append("VERY SMALL amount (pea/pearl-sized)")
    elif 'dime-sized' in full_lower or 'cherry-sized' in full_lower:
        prep_hints.append("moderate amount (dime/cherry-sized)")
    elif 'drops' in full_lower or 'pumps' in full_lower or 'dropper' in full_lower:
        prep_hints.append("liquid drops (barely visible, absorbed quickly)")
    
    # Prep technique detection
    if 'warm' in full_lower and ('fingertips' in full_lower or 'palms' in full_lower or 'hands' in full_lower):
        prep_hints.append("warmed/dissolved between fingertips BEFORE applying (translucent, already absorbed)")
    if 'emulsif' in full_lower or 'dissolve' in full_lower:
        prep_hints.append("emulsified/dissolved first (translucent, NOT thick white cream)")
    if 'press' in full_lower or 'pat' in full_lower:
        prep_hints.append("pressed/patted in (absorbed, not sitting on surface)")
    
    prep_context = " ".join(prep_hints) if prep_hints else "Show product being applied"
    
    prompt = f"""Create a REALISTIC, RELATABLE beauty routine step image:

MAIN ACTION TO SHOW: "{instruction}"

FULL CONTEXT: "{full_instruction}"
PREP NOTES: {prep_context}

PRODUCT: {brand} {product_name}
APPLICATION AREA: {app_area}

CRITICAL STYLE REQUIREMENTS:
- REALISTIC bathroom/vanity setting (NOT a studio shoot)
- RELATABLE everyday woman (NOT a professional model)
- NATURAL candid moment (NOT posed/staged)
- Actual hands in motion performing the action
- Woman focused on application (eyes may be closed or looking down)
- EXACT skin tone: {skin_tone} (CRITICAL - this MUST match precisely across all images)

SCENE COMPOSITION:
- Medium close-up showing face/neck and hands in action
- Natural bathroom lighting (soft, diffused, NOT editorial)
- Simple background (mirror, sink edge - keep it realistic)
- Casual, intimate perspective (like a bathroom selfie angle)

ACTION & PRODUCT TEXTURE:
- Show the EXACT action: {instruction}
- Hands IN MOTION, not static
- Product texture MUST respect prep notes above (e.g., if "warmed", show translucent/absorbed, NOT thick cream)
- Natural hand gestures (not perfectly manicured model hands)

SKIN REQUIREMENTS (CRITICAL):
- Skin tone: {skin_tone} (EXACT hex match - this is critical for consistency)
- Skin type: {skin_type} (show realistic texture)
- Same skin tone MUST be used across all routine steps
- Imperfect is perfect - slight asymmetry, natural expressions
- Focus on the APPLICATION, not beauty/glamour

ABSOLUTELY FORBIDDEN:
- NO TEXT OR CAPTIONS on the image (image only, no words)
- NO marketing/advertising aesthetics
- NO professional model poses
- NO perfect studio lighting
- NO overly styled/glamorous shots
- NO stock photo look
- NO symmetrical, posed compositions
- NO thick white cream if product is a serum/oil/essence (these are lightweight and barely visible)

Generate ONE realistic, relatable application image of a woman in her actual routine."""
    
    for attempt in range(max_retries):
        print(f"[{time.time()}] Generating image for {product_name} (Attempt {attempt + 1}/{max_retries})...")
        start_time = time.time()
        
        try:
            text_part = types.Part.from_text(text=prompt)
            contents = types.Content(role="user", parts=[text_part])
            
            print(f"[{time.time()}] [{product_name}] Sending request to GenAI API...")
            
            generate_content_config = types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                ],
            )
            
            response_chunks = await shared_client.aio.models.generate_content_stream(
                model="gemini-2.5-flash-image-preview",
                contents=[contents],
                config=generate_content_config
            )
            
            print(f"[{time.time()}] [{product_name}] GenAI API stream opened.")
            
            image_found = False
            async for chunk in response_chunks:
                print(f"[{time.time()}] [{product_name}] Received chunk: {chunk}")
                for part in chunk.candidates[0].content.parts:
                    if part.inline_data is not None:
                        image_found = True
                        generated_part = types.Part(inline_data=types.Blob(
                            mime_type=part.inline_data.mime_type,
                            data=part.inline_data.data
                        ))
                        artifact_name = f"product_{product_sku}_personalized.jpeg"
                        artifact_uri = await tool_context.save_artifact(artifact_name, generated_part)
                        end_time = time.time()
                        print(f"[{time.time()}] Finished generating image for {product_name} in {end_time - start_time:.2f}s")
                        return {
                            "status": "success",
                            "artifact_name": artifact_name,
                            "artifact_uri": artifact_uri,
                            "sku": product_sku
                        }
                else:
                    continue
            
            if not image_found:
                print(f"[{time.time()}] [{product_name}] Stream finished but no image data was found.")
        
        except ValueError as e:
            if "Chunk too big" in str(e):
                print(f"[{time.time()}] [{product_name}] 'Chunk too big' error on attempt {attempt + 1}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            else:
                print(f"API call failed for prompt '{prompt}' with a non-retryable ValueError:")
                import traceback
                traceback.print_exc()
                return {"status": "error", "error_message": f"API call failed: {e}", "sku": product_sku}
        except Exception as e:
            print(f"API call failed for prompt '{prompt}':")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error_message": f"API call failed: {e}", "sku": product_sku}
    
    return {"status": "error", "error_message": f"Image generation failed after {max_retries} attempts.", "sku": product_sku}

generate_product_image_tool = FunctionTool(func=generate_product_image)


# ============================================================================
# TOOL 4: Generate Why Copy (AI-powered, from IdeationAgent pattern)
# ============================================================================

async def generate_why_copy(
    product_name: str,
    brand: str,
    description: str,
    skin_type: str,
    concerns: List[str],
    skin_tone: str,
    aesthetic_name: str
) -> Dict[str, Any]:
    """
    Generates a personalized, compelling one-liner explaining WHY this product
    is perfect for the user's specific needs.
    
    Based on trend-to-market IdeationAgent pattern.
    """
    print(f"[GENERATE_WHY] Creating why copy for {product_name}")
    
    concerns_text = ", ".join(concerns) if concerns else "skin health"
    
    prompt = f"""In ONE sentence, explain why {brand} {product_name} is perfect for THIS specific user:

USER PROFILE:
- Skin type: {skin_type}
- Skin tone: {skin_tone}
- Concerns: {concerns_text}
- Desired aesthetic: {aesthetic_name}

PRODUCT:
{brand} {product_name}
{description}

REQUIREMENTS:
- Focus on the PERSONALIZED benefit for THIS user's specific needs
- Connect to their chosen aesthetic ({aesthetic_name})
- Be specific about why THIS product works for THEIR skin type/concerns
- NOT generic marketing language
- One sentence, maximum 20 words
- Conversational, expert tone

GOOD EXAMPLES:
"Melts makeup while maintaining your dry skin's moisture barrier for that ethereal glow."
"Gentle enough for sensitive eyes while delivering bold volume that completes your matte perfection look."

BAD EXAMPLES (too generic - avoid):
"A great product for healthy skin."
"Perfect for anyone who wants beautiful results."

Output ONLY the sentence, no preamble or quotes:"""
    
    try:
        response = await shared_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        why_text = response.text.strip().strip('"')
        
        print(f"[GENERATE_WHY] ✓ Generated: {why_text}")
        
        return {
            "status": "success",
            "why_text": why_text
        }
        
    except Exception as e:
        print(f"[GENERATE_WHY] ✗ Error: {e}")
        return {
            "status": "error",
            "why_text": "Perfect for your routine",
            "error_message": str(e)
        }

generate_why_copy_tool = FunctionTool(func=generate_why_copy)


# ============================================================================
# TOOL 5: Generate Application Instructions (AI-powered)
# ============================================================================

async def generate_application_instructions(
    product_name: str,
    brand: str,
    category: str,
    description: str
) -> Dict[str, Any]:
    """
    Generates application instructions split into:
    - title: Main application action (for step title & image generation)
    - full_instruction: Complete multi-step instruction (for description)
    """
    print(f"[GENERATE_INSTRUCTIONS] Creating instructions for {product_name}")
    
    prompt = f"""Generate application instructions for {brand} {product_name}.

Category: {category}
Product: {description}

OUTPUT TWO PARTS:

1. TITLE (main application action - single sentence):
   - The core APPLICATION step only
   - Action verb + application area + technique
   - Example: "Massage onto dry face and eyes in circular motions"
   - Example: "Gently press and massage into cleansed face and neck"
   - Example: "Sweep across cheekbones and blend upward"

2. FULL_INSTRUCTION (complete steps - 1-3 sentences):
   - May include: prep → application → post
   - Example: "Scoop a cherry-sized amount onto dry fingertips. Massage onto dry face and eyes in circular motions. Rinse thoroughly with warm water."
   - Example: "Apply 2-3 drops to fingertips. Gently press and massage into cleansed face and neck until absorbed."

FORMAT YOUR RESPONSE EXACTLY AS:
TITLE: [single action sentence]
FULL: [complete instruction]

REQUIREMENTS:
- Specific amounts (drops, pumps, pea-sized, etc.)
- Active verbs (massage, press, sweep, pat, blend)
- Clear application areas
- NO marketing language
- Maximum 3 sentences for FULL

Generate the instructions:"""
    
    try:
        response = await shared_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        text = response.text.strip()
        
        # Parse TITLE and FULL
        title = ""
        full_instruction = ""
        
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('TITLE:'):
                title = line.replace('TITLE:', '').strip()
            elif line.startswith('FULL:'):
                full_instruction = line.replace('FULL:', '').strip()
        
        # Fallback if parsing fails
        if not title or not full_instruction:
            # Use full text as fallback
            sentences = text.split('.')
            title = sentences[0].strip() + '.' if sentences else text
            full_instruction = text
        
        print(f"[GENERATE_INSTRUCTIONS] ✓ Title: {title[:50]}...")
        print(f"[GENERATE_INSTRUCTIONS] ✓ Full: {full_instruction[:50]}...")
        
        return {
            "status": "success",
            "title": title,
            "full_instruction": full_instruction
        }
        
    except Exception as e:
        print(f"[GENERATE_INSTRUCTIONS] ✗ Error: {e}")
        return {
            "status": "error",
            "title": description,
            "full_instruction": description,
            "error_message": str(e)
        }

generate_application_instructions_tool = FunctionTool(func=generate_application_instructions)


# Export tools
__all__ = [
    'search_products_tool',
    'generate_product_copy_tool',
    'generate_product_image_tool',
    'generate_why_copy_tool',
    'generate_application_instructions_tool',
    'generate_application_instructions'  # Export function directly too
]