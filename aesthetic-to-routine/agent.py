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
from google.adk.tools import ToolContext
from google.genai import types
from pydantic import Field, ConfigDict
from typing import AsyncGenerator, Any, Dict
from typing_extensions import override
import json
import os
import asyncio

from . import config
from .tools import (
    search_products_tool,
    generate_product_copy_tool,
    generate_product_image_tool,
    generate_why_copy_tool,
    search_products,
    generate_product_copy,
    generate_product_image,
    generate_why_copy,
    generate_application_instructions
)


# ============================================================================
# CUSTOMER PROFILE LOADER (UDP Story)
# ============================================================================

def load_customer_profile() -> Dict[str, Any]:
    """Load customer profile from unified CDP for pre-population."""
    profile_path = os.path.join(
        os.path.dirname(__file__),
        f"data/{config.BRAND_DATA_SET}/customer_profile.json"
    )
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[CUSTOMER_PROFILE] Failed to load: {e}")
        # Return default profile if file doesn't exist
        return {
            "customer_name": "there",
            "preferences": {
                "skin_type": "Normal",
                "concerns": ["Hydration"],
                "skin_tone": "#F5D7C4"
            },
            "brand_affinity": [],
            "purchase_history": []
        }


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
        
        # STEP 1: Handle greeting - Load and return customer profile for pre-population
        if "hello" in user_text_lower or "hi" in user_text_lower:
            # Load customer profile from unified CDP
            customer_profile = load_customer_profile()
            customer_name = customer_profile.get("customer_name", "there")
            
            # Return profile data in agent_state for frontend to use
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"""Welcome back, {customer_name}! ✨

Your preferences have been synced from your unified profile. Browse the aesthetics below and I'll create a personalized routine based on your skin type, purchase history, and preferences.""")]),
                actions=EventActions(
                    agent_state={"customer_profile": customer_profile}
                )
            )
            return
        
        # STEP 2: Parse quiz submission
        try:
            request_data = json.loads(user_text)
            aesthetic_id = request_data.get("aesthetic_id")
            aesthetic_name_override = request_data.get("aesthetic_name")  # Frontend can override name
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
        
        # STEP 3: Call search_products with smart routine building (PHASE 2)
        # Determine routine type/subcategory (default to skincare AM for now)
        # FUTURE: This will come from UI selection in Phase 3
        routine_type = quiz_responses.get("routine_type", "skincare")
        subcategory = quiz_responses.get("subcategory", "am")
        
        search_result = search_products(
            aesthetic_id=aesthetic_id,
            skin_type=quiz_responses.get("skin_type"),
            concerns=quiz_responses.get("concerns", []),
            skin_tone=quiz_responses.get("skin_tone"),
            routine_type=routine_type,
            subcategory=subcategory,
            aesthetic_name=aesthetic_name_override  # Pass custom name if provided
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
        
        # Track previous step titles for progressive context
        previous_step_titles = []
        
        # HYBRID OPTIMIZATION: Pre-batch cheap calls, then progressive with per-product parallelization
        # This balances speed (~10-15s instead of 7-12s) with UX (progressive rendering restored)
        
        total_steps = len(enhanced_products)
        tool_ctx = ToolContext(ctx)
        
        print(f"[ORCHESTRATOR] 🚀 Starting hybrid generation for {total_steps} products...")
        
        # BATCH 1: Pre-generate ALL application instructions in parallel (cheap, 1-2s total)
        print(f"[ORCHESTRATOR] Pre-generating instructions for all products...")
        instruction_tasks = []
        for product in enhanced_products:
            task = generate_application_instructions(
                product_name=product.get("name", ""),
                brand=product.get("brand", ""),
                category=product.get("category", ""),
                description=product.get("description", "")
            )
            instruction_tasks.append(task)
        
        # Wait for all instructions to complete
        instructions_results = await asyncio.gather(*instruction_tasks, return_exceptions=True)
        
        # Store instructions indexed by product
        instructions_map = {}
        for i, (product, result) in enumerate(zip(enhanced_products, instructions_results)):
            if isinstance(result, Exception):
                print(f"[ORCHESTRATOR] Instructions failed for {product.get('name')}: {result}")
                instructions_map[i] = {
                    "title": product.get("description", ""),
                    "full_instruction": product.get("description", "")
                }
            elif result.get("status") == "success":
                instructions_map[i] = {
                    "title": result.get("title", product.get("description", "")),
                    "full_instruction": result.get("full_instruction", product.get("description", ""))
                }
            else:
                instructions_map[i] = {
                    "title": product.get("description", ""),
                    "full_instruction": product.get("description", "")
                }
        
        print(f"[ORCHESTRATOR] ✓ Instructions ready. Now generating products progressively...")
        
        # PROGRESSIVE GENERATION: For each product, parallelize image + why, then yield
        # This shows steps as they complete while still being faster than pure serial
        previous_step_titles = []
        
        for i, product in enumerate(enhanced_products, 1):
            sku = product.get("sku", "")
            brand = product.get("brand", "")
            
            # Announce step start
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"✨ Step {i}/{total_steps}: {product.get('name')}...")])
            )
            
            # Parallel tasks for THIS product only
            product_tasks = []
            task_types = []
            
            # Task 1: Image generation (if needed)
            needs_image = product.get("needs_image", False)
            if needs_image:
                # Load actual product image for visual reference
                product_image_part = None
                try:
                    image_path = os.path.join(
                        os.path.dirname(__file__),
                        f"data/{config.BRAND_DATA_SET}/images/products/product_{sku}.jpg"
                    )
                    if os.path.exists(image_path):
                        with open(image_path, "rb") as f:
                            product_image_part = types.Part.from_bytes(
                                data=f.read(),
                                mime_type="image/jpeg"
                            )
                except Exception as e:
                    print(f"[ORCHESTRATOR] Image load failed for {sku}: {e}")
                
                image_task = generate_product_image(
                    tool_context=tool_ctx,
                    product_sku=sku,
                    product_name=product.get("name", ""),
                    brand=brand,
                    category=product.get("sub_category", product.get("category", "")),
                    instruction=instructions_map[i-1]["title"],
                    full_instruction=instructions_map[i-1]["full_instruction"],
                    skin_type=quiz_responses.get("skin_type", ""),
                    skin_tone=quiz_responses.get("skin_tone", "#F5D7C4"),
                    concerns=quiz_responses.get("concerns", []),
                    aesthetic_name=aesthetic_name,
                    step_number=i,
                    total_steps=total_steps,
                    previous_steps=previous_step_titles.copy(),
                    product_image_part=product_image_part
                )
                product_tasks.append(image_task)
                task_types.append("image")
            
            # Task 2: Why copy generation
            why_task = generate_why_copy(
                product_name=product.get("name", ""),
                brand=brand,
                description=product.get("description", ""),
                skin_type=quiz_responses.get("skin_type", ""),
                concerns=quiz_responses.get("concerns", []),
                skin_tone=quiz_responses.get("skin_tone", ""),
                aesthetic_name=aesthetic_name
            )
            product_tasks.append(why_task)
            task_types.append("why")
            
            # Execute image + why in parallel for THIS product
            results = await asyncio.gather(*product_tasks, return_exceptions=True)
            
            # Extract results
            ai_image_artifact_name = None
            why_text = product.get("why_this_base", "Perfect for your routine")
            
            for task_type, result in zip(task_types, results):
                if isinstance(result, Exception):
                    print(f"[ORCHESTRATOR] {task_type} failed for {product.get('name')}: {result}")
                elif task_type == "image" and result.get("status") == "success":
                    ai_image_artifact_name = result.get("artifact_name")
                elif task_type == "why" and result.get("status") == "success":
                    why_text = result.get("why_text", why_text)
            
            # Save brand logo as artifact
            brand_logo_artifact = None
            try:
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
                    artifact_name = logo_filename
                    await callback_ctx.save_artifact(artifact_name, logo_part)
                    brand_logo_artifact = artifact_name
            except Exception as e:
                print(f"[ORCHESTRATOR] Logo save failed for {brand}: {e}")
            
            # Save product image as artifact (if exists)
            product_image_artifact = None
            try:
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
            except Exception as e:
                print(f"[ORCHESTRATOR] Product image save failed for {sku}: {e}")
            
            # Get instruction from pre-generated map
            instruction_title = instructions_map[i-1]["title"]
            instruction_full = instructions_map[i-1]["full_instruction"]
            
            # Track this step's title for next iteration
            previous_step_titles.append(instruction_title)
            
            # Add completed step with artifact names and product metadata
            step = {
                "step_number": i,
                "category": product.get("step_category_display", product.get("category", "Beauty")),
                "product": {
                    "name": product.get("name", ""),
                    "brand": brand,
                    "sku": sku,
                    "brand_logo_artifact": brand_logo_artifact,
                    "product_image_artifact": product_image_artifact,
                    "ai_image_artifact": ai_image_artifact_name,
                    "title": instruction_title,
                    "description": instruction_full,
                    "original_description": product.get("description", ""),
                    "why": why_text,
                    "skin_types": product.get("skin_types", []),
                    "concerns": product.get("concerns", []),
                    "sub_category": product.get("sub_category", ""),
                    "price": product.get("price"),
                    "category": product.get("category", ""),
                    "sensory_descriptors": product.get("sensory_descriptors", {}),
                    "ingredients_highlight": product.get("ingredients_highlight", "")
                }
            }
            routine_steps.append(step)
            
            # Yield progressive update with routine metadata
            custom_experience_data = {
                "type": "routine_progress",
                "aesthetic_id": aesthetic_id,
                "aesthetic_name": aesthetic_name,
                "routine_type": search_result.get("routine_type", "skincare"),
                "subcategory": search_result.get("subcategory", "am"),
                "steps": routine_steps,
                "total_steps": total_steps,
                "current_step": i,
                "quiz_responses": quiz_responses
            }
            
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"✓ Step {i}/{total_steps} complete")]),
                actions=EventActions(
                    agent_state={"custom_experience_data": custom_experience_data}
                )
            )
        
        # PHASE 2: Final completion event with routine metadata
        final_data = {
            "type": "routine_result",
            "aesthetic_id": aesthetic_id,
            "aesthetic_name": aesthetic_name,
            "routine_type": search_result.get("routine_type", "skincare"),
            "subcategory": search_result.get("subcategory", "am"),
            "steps": routine_steps,
            "quiz_responses": quiz_responses
        }
        
        skin_type = quiz_responses.get("skin_type", "your")
        concerns = quiz_responses.get("concerns", [])
        main_concern = concerns[0] if concerns else "skin"
        
        # Load customer profile for UDP messaging
        customer_profile = load_customer_profile()
        brand_affinity = customer_profile.get("brand_affinity", [])
        purchase_history = customer_profile.get("purchase_history", [])
        
        # Count unique brands in routine
        unique_brands = set(step.get("product", {}).get("brand", "") for step in routine_steps)
        num_brands = len(unique_brands)
        
        # Build UDP story message
        udp_details = []
        udp_details.append(f"• Your saved preferences ({skin_type} skin, {main_concern} priority)")
        if purchase_history:
            loved_brand = purchase_history[0].get("brand", "")
            udp_details.append(f"• Purchase history (you loved {loved_brand} products)")
        udp_details.append(f"• Product catalog across {num_brands} ELC brands")
        if brand_affinity:
            udp_details.append(f"• Brand affinity patterns")
        
        udp_message = "\n".join(udp_details)
        
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text=f"""✨ Your {aesthetic_name} routine is ready!

I've curated a {len(routine_steps)}-step routine by unifying data from:
{udp_message}

Each recommendation is AI-personalized using our Unified Data Platform, combining your profile, product intelligence, and behavioral insights.""")]),
            actions=EventActions(
                agent_state={"custom_experience_data": final_data}
            )
        )


# Initialize orchestrator
orchestrator = AestheticToRoutineOrchestrator(
    name="Orchestrator",
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