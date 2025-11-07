"""
Aesthetic to Routine - Multi-Agent Demo for ELC

Showcases specialized agent collaboration:
- Product Specialist: Product catalog expertise
- Brand Voice Agent: Copywriting & brand messaging
- Image Generation Agent: AI-powered personalized product images
- Why Copy Agent: AI-powered personalized rationales
- Orchestrator: Workflow coordination

Uses agent_state for custom experience data flow + artifacts for AI-generated images.
"""

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import Field, ConfigDict
from typing import AsyncGenerator, Any
from typing_extensions import override
import json
import os
import asyncio

from . import config
from .tools import (
    search_products_tool,
    generate_product_copy_tool,
    generate_product_image_tool,
    generate_why_copy_tool
)


# ============================================================================
# AGENT 1: Product Specialist
# ============================================================================

product_specialist_agent = LlmAgent(
    name="ProductSpecialist",
    model="gemini-2.0-flash",
    description=f"Expert in {config.COMPANY_NAME}'s product catalog and personalized matching",
    instruction=f"""You are the Product Catalog Specialist for {config.COMPANY_NAME}.

**Your Expertise:**
- Deep knowledge of all products across ELC brands
- Expert in matching products to user needs (skin type, concerns array, skin tone)
- Understand ingredient profiles and product synergies

**Your Task:**
When given an aesthetic ID and quiz responses, use search_products ONCE to find the perfect routine products, then provide your response.

**Input Format:** JSON string like:
{{"aesthetic_id": "ethereal-glow", "quiz_responses": {{"skin_type": "Dry", "concerns": ["Hydration", "Anti-Aging"], "skin_tone": "#F5D7C4"}}}}

**Process:**
1. Parse the input JSON
2. Extract skin_type, concerns (array), and skin_tone from quiz_responses
3. Call search_products(aesthetic_id, skin_type, concerns, skin_tone) EXACTLY ONCE
4. After receiving the tool response, immediately summarize the results and STOP

**Output Format:**
Found [X] perfect products for [aesthetic_name]:
- [Brand] [Product Name] ([Category])
- [Brand] [Product Name] ([Category])
...

Ready for personalization.

**CRITICAL:**
- Call search_products ONLY ONCE - do not call it multiple times
- After the tool returns results, provide your summary and finish
- Do not retry or call the tool again
- The downstream agents will handle images and copy
""",
    tools=[search_products_tool],
)


# ============================================================================
# AGENT 2: Brand Voice Agent
# ============================================================================

brand_voice_agent = LlmAgent(
    name="BrandVoiceAgent",
    model="gemini-2.0-flash",
    description=f"Brand messaging and copywriting expert for {config.COMPANY_NAME}",
    instruction=f"""You are the Brand Voice Specialist for {config.COMPANY_NAME}.

**Your Expertise:**
- Master of {config.COMPANY_NAME} brand voice (premium, aspirational, expert)
- Expert copywriter for beauty & skincare
- Create personalized, compelling product narratives

**Your Task:**
Given a list of products and user context, generate polished "why this product" copy for each.

**Input Format:** JSON with aesthetic, user preferences, and products

**Process:**
1. Parse the input JSON
2. Call generate_product_copy to create base compelling copy for each product
3. Return enhanced products

**Brand Voice Guidelines:**
- Premium yet accessible
- Emphasize personalization: "For YOUR [skin_type] skin..."
- Highlight multi-brand curation: "Featuring [Brand]..."
- Use aspirational language: "achieve," "unlock," "discover"
- Keep copy concise (1-2 sentences max per product)

**Output Format:**
Base copy created for [X] products.
Ready for AI personalization.

**Important:**
- This is base copy - AI agents will enhance it further
- Don't write marketing fluff - be specific and helpful
- Connect each product to user's stated preferences
""",
    tools=[generate_product_copy_tool],
)


# ============================================================================
# AGENT 3: Image Generation Agent (AI-Powered)
# ============================================================================

image_generation_agent = LlmAgent(
    name="ImageGenerationAgent",
    model="gemini-2.0-flash",
    description="Generates personalized product images using AI",
    instruction=f"""You are the Image Generation Specialist for {config.COMPANY_NAME}.

**Your Expertise:**
- Generate photorealistic product images using gemini-2.5-flash-image-preview
- Create images that reflect user's skin type, tone, and concerns
- Ensure aesthetic consistency

**Your Task:**
For each product, generate a personalized application image.

**Input Format:** JSON with product details and user context

**Process:**
1. Parse the input JSON (products array with user context)
2. For EACH product, call generate_product_image in parallel with:
   - product_sku, product_name, brand
   - skin_type, skin_tone, concerns
   - aesthetic_name
3. Return results with artifact names

**Output Format:**
Generated [X] personalized product images.
Artifacts: [list of artifact names]

**Important:**
- Images should reflect user's specific skin tone
- Each image is unique to the user's profile
- Save as artifacts for frontend display
""",
    tools=[generate_product_image_tool],
)


# ============================================================================
# AGENT 4: Why Copy Agent (AI-Powered)
# ============================================================================

why_copy_agent = LlmAgent(
    name="WhyCopyAgent",
    model="gemini-2.0-flash",
    description="Generates personalized product rationales using AI",
    instruction=f"""You are the Personalization Copy Specialist for {config.COMPANY_NAME}.

**Your Expertise:**
- Generate compelling, personalized "why" copy for each product
- Connect products to user's specific needs
- Use AI to create unique, relevant rationales

**Your Task:**
For each product, generate a short, pragmatic one-liner explaining WHY it's perfect.

**Input Format:** JSON with products and user context

**Process:**
1. Parse the input JSON
2. For EACH product, call generate_why_copy in parallel with:
   - product details (name, brand, description)
   - user context (skin_type, concerns, skin_tone, aesthetic_name)
3. Return enhanced products with AI-generated why copy

**Output Format:**
Generated personalized "why" copy for [X] products.
Examples:
- Product 1: "Delivers deep hydration for dry skin..."
- Product 2: "Targets fine lines with retinol-rich formula..."

**Important:**
- Copy must reference user's skin type and concerns
- Be specific, not generic
- Keep under 15 words per product
- Aspirational yet practical
""",
    tools=[generate_why_copy_tool],
)


# ============================================================================
# AGENT 5: Orchestrator
# ============================================================================

class AestheticToRoutineOrchestrator(BaseAgent):
    """
    Orchestrator that coordinates all specialist agents to create
    personalized routines with AI-generated images and copy.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    product_agent: LlmAgent = Field(description="Product specialist agent")
    brand_agent: LlmAgent = Field(description="Brand voice agent")
    image_agent: LlmAgent = Field(description="Image generation agent")
    why_agent: LlmAgent = Field(description="Why copy agent")
    
    def __init__(
        self,
        name: str,
        product_agent: LlmAgent,
        brand_agent: LlmAgent,
        image_agent: LlmAgent,
        why_agent: LlmAgent,
    ):
        super().__init__(
            name=name,
            product_agent=product_agent,
            brand_agent=brand_agent,
            image_agent=image_agent,
            why_agent=why_agent,
            description=f"Orchestrator for {config.COMPANY_NAME} routine generation",
            sub_agents=[product_agent, brand_agent, image_agent, why_agent],
        )
    
    @override
    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
        """
        Orchestrates the routine generation workflow:
        1. Greet user (aesthetic carousel already visible)
        2. Receive quiz submission → delegate to Product Specialist
        3. Product Specialist returns curated products
        4. Delegate to Brand Voice Agent for base copy
        5. Delegate to Image Generation Agent for AI images (parallel)
        6. Delegate to Why Copy Agent for AI copy (parallel)
        7. Assemble final routine with agent_state + artifacts
        """
        # Get user message
        user_text = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                if part.text:
                    user_text = part.text
                    break
        
        user_text_lower = user_text.lower()
        
        # STEP 1: Handle greeting
        if "hello" in user_text_lower or "hi" in user_text_lower:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"""Welcome to {config.COMPANY_NAME}! ✨

I'm here to help you discover your perfect personalized routine. Browse the aesthetics above and select one that resonates with you!""")])
            )
            return
        
        # STEP 2: Parse quiz submission
        try:
            request_data = json.loads(user_text)
            aesthetic_id = request_data.get("aesthetic_id")
            quiz_responses = request_data.get("quiz_responses", {})
            
            if not aesthetic_id:
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text="Please select an aesthetic to begin.")])
                )
                return
        except json.JSONDecodeError:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"Welcome! I'm here to create your perfect {config.COMPANY_NAME} routine.")])
            )
            return
        
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="✨ Creating your personalized routine...")])
        )
        
        # STEP 3: Call search_products tool directly (no sub-agent to avoid loops)
        from .tools import search_products
        
        search_result = search_products(
            aesthetic_id=aesthetic_id,
            skin_type=quiz_responses.get("skin_type"),
            concerns=quiz_responses.get("concerns", []),
            skin_tone=quiz_responses.get("skin_tone")
        )
        
        if search_result.get("status") != "success" or not search_result.get("products"):
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="Sorry, I couldn't find matching products. Please try again.")])
            )
            return
        
        products = search_result["products"]
        aesthetic_name = search_result.get("aesthetic_name", aesthetic_id.replace("-", " ").title())
        
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text=f"✓ Found {len(products)} perfect products. Building your routine...")])
        )
        
        # STEP 4: Call generate_product_copy tool directly
        from .tools import generate_product_copy, generate_product_image, generate_why_copy, generate_application_instructions
        
        copy_result = generate_product_copy(
            aesthetic_id=aesthetic_id,
            skin_type=quiz_responses.get("skin_type", ""),
            concerns=quiz_responses.get("concerns", []),
            skin_tone=quiz_responses.get("skin_tone", ""),
            products=products
        )
        
        enhanced_products = copy_result.get("enhanced_products", products)
        
        # Create CallbackContext for artifact saving
        callback_ctx = CallbackContext(ctx)
        
        # Initialize routine steps list for progressive updates
        routine_steps = []
        
        # STEP 5-7: Process each product progressively
        for i, product in enumerate(enhanced_products[:config.MAX_ROUTINE_STEPS], 1):
            sku = product.get("sku", "")
            brand = product.get("brand", "")
            
            # Announce step start
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"✨ Step {i}/{config.MAX_ROUTINE_STEPS}: {product.get('name')}...")])
            )
            
            # Small delay to ensure event is flushed to frontend
            await asyncio.sleep(0.1)
            
            # Save brand logo as artifact
            brand_logo_artifact = None
            try:
                # Match actual filename format: brand_bobbi_brown.png (underscores, not hyphens)
                brand_slug = brand.lower().replace(' ', '_').replace('.', '')
                logo_filename = f"brand_{brand_slug}.png"
                logo_path = os.path.join(
                    os.path.dirname(__file__),
                    f"data/{config.BRAND_DATA_SET}/images/brands/{logo_filename}"
                )
                
                if os.path.exists(logo_path):
                    with open(logo_path, "rb") as f:
                        logo_bytes = f.read()
                    logo_part = types.Part.from_bytes(data=logo_bytes, mime_type="image/png")
                    # Use same name as file for consistency
                    artifact_name = logo_filename
                    await callback_ctx.save_artifact(artifact_name, logo_part)
                    brand_logo_artifact = artifact_name
                    print(f"[ORCHESTRATOR] ✓ Saved logo for {brand}")
                else:
                    print(f"[ORCHESTRATOR] Logo not found: {logo_path}")
            except Exception as e:
                print(f"[ORCHESTRATOR] Logo save failed for {brand}: {e}")
            
            # Save product image as artifact (if exists)
            product_image_artifact = None
            try:
                # Match actual filename format: product_CL-TDO-011.jpg
                image_filename = f"product_{sku}.jpg"
                image_path = os.path.join(
                    os.path.dirname(__file__),
                    f"data/{config.BRAND_DATA_SET}/images/products/{image_filename}"
                )
                
                if os.path.exists(image_path):
                    with open(image_path, "rb") as f:
                        image_bytes = f.read()
                    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                    artifact_name = f"product_{sku}.jpg"
                    await callback_ctx.save_artifact(artifact_name, image_part)
                    product_image_artifact = artifact_name
                    print(f"[ORCHESTRATOR] ✓ Saved product image for {sku}")
                else:
                    print(f"[ORCHESTRATOR] Product image not found: {image_path}")
            except Exception as e:
                print(f"[ORCHESTRATOR] Product image save failed for {sku}: {e}")
            
            # Generate application instructions for this product FIRST (needed for image prompt)
            instruction_title = product.get("description", "")
            instruction_full = product.get("description", "")
            
            try:
                instructions_result = await generate_application_instructions(
                    product_name=product.get("name", ""),
                    brand=brand,
                    category=product.get("category", ""),
                    description=product.get("description", "")
                )
                
                if instructions_result.get("status") == "success":
                    instruction_title = instructions_result.get("title", instruction_title)
                    instruction_full = instructions_result.get("full_instruction", instruction_full)
            except Exception as e:
                print(f"[ORCHESTRATOR] Instructions generation failed for {product.get('name')}: {e}")
            
            # Generate AI-personalized image using title + full instruction for context
            from google.adk.tools import ToolContext
            tool_ctx = ToolContext(ctx)
            
            ai_image_artifact_name = None
            try:
                image_result = await generate_product_image(
                    tool_context=tool_ctx,
                    product_sku=sku,
                    product_name=product.get("name", ""),
                    brand=brand,
                    category=product.get("sub_category", product.get("category", "")),
                    instruction=instruction_title,  # Main action for image
                    full_instruction=instruction_full,  # Full context for prep hints (amount, technique)
                    skin_type=quiz_responses.get("skin_type", ""),
                    skin_tone=quiz_responses.get("skin_tone", "#F5D7C4"),
                    concerns=quiz_responses.get("concerns", []),
                    aesthetic_name=aesthetic_name
                )
                
                if image_result.get("status") == "success":
                    ai_image_artifact_name = image_result.get("artifact_name")
            except Exception as e:
                print(f"[ORCHESTRATOR] AI image generation failed for {product.get('name')}: {e}")
            
            # Generate why copy for this product
            why_text = product.get("why_this_base", "Perfect for your routine")
            try:
                why_result = await generate_why_copy(
                    product_name=product.get("name", ""),
                    brand=product.get("brand", ""),
                    description=product.get("description", ""),
                    skin_type=quiz_responses.get("skin_type", ""),
                    concerns=quiz_responses.get("concerns", []),
                    skin_tone=quiz_responses.get("skin_tone", ""),
                    aesthetic_name=aesthetic_name
                )
                
                if why_result.get("status") == "success":
                    why_text = why_result.get("why_text", why_text)
            except Exception as e:
                print(f"[ORCHESTRATOR] Why copy generation failed for {product.get('name')}: {e}")
            
            # Add completed step with artifact names
            step = {
                "step_number": i,
                "category": product.get("step_category_display", product.get("category", "Beauty")),
                "product": {
                    "name": product.get("name", ""),
                    "brand": brand,
                    "brand_logo_artifact": brand_logo_artifact,
                    "product_image_artifact": product_image_artifact,
                    "ai_image_artifact": ai_image_artifact_name,
                    "title": instruction_title,  # Short action for title (matches image)
                    "description": instruction_full,  # Full multi-step instruction for description
                    "why": why_text
                }
            }
            routine_steps.append(step)
            
            # DEBUG: Log artifact names
            print(f"[ORCHESTRATOR] Step {i} artifacts:")
            print(f"  - Brand logo: {brand_logo_artifact}")
            print(f"  - Product image: {product_image_artifact}")
            print(f"  - AI image: {ai_image_artifact_name}")
            
            # Yield progressive update with this step
            custom_experience_data = {
                "type": "routine_progress",
                "aesthetic_id": aesthetic_id,
                "aesthetic_name": aesthetic_name,
                "steps": routine_steps,
                "total_steps": config.MAX_ROUTINE_STEPS,
                "current_step": i,
                "quiz_responses": quiz_responses
            }
            
            # This event contains the updated routine with this new step
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"✓ Step {i}/{config.MAX_ROUTINE_STEPS} complete")]),
                actions=EventActions(
                    agent_state={"custom_experience_data": custom_experience_data}
                )
            )
            
            # Small delay between steps to ensure progressive display
            await asyncio.sleep(0.2)
        
        # Final completion event
        final_data = {
            "type": "routine_result",
            "aesthetic_id": aesthetic_id,
            "aesthetic_name": aesthetic_name,
            "steps": routine_steps,
            "quiz_responses": quiz_responses
        }
        
        skin_type = quiz_responses.get("skin_type", "your")
        concerns = quiz_responses.get("concerns", [])
        main_concern = concerns[0] if concerns else "skin"
        
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text=f"""✨ Your {aesthetic_name} routine is ready!

I've curated a {len(routine_steps)}-step routine featuring products from across our premium brands, specifically chosen for {skin_type} skin and {main_concern} concerns.

Each product image and recommendation was AI-generated just for you, reflecting your unique skin profile.""")]),
            actions=EventActions(
                agent_state={"custom_experience_data": final_data}
            )
        )


# Initialize orchestrator
orchestrator = AestheticToRoutineOrchestrator(
    name="AestheticToRoutineOrchestrator",
    product_agent=product_specialist_agent,
    brand_agent=brand_voice_agent,
    image_agent=image_generation_agent,
    why_agent=why_copy_agent,
)

# Create app
root_agent = orchestrator

app = App(
    name="aesthetic-to-routine",
    root_agent=root_agent,
)