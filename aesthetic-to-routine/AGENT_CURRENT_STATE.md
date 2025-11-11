# Aesthetic-to-Routine Agent - Current State

**Last Updated:** January 11, 2025 - CRITICAL UX FIXES + PERFORMANCE TUNING ⚡

## Latest Updates (Jan 11, 2025 - Evening)

### Three Critical Fixes Implemented

**1. Progressive Rendering Restored (Hybrid Optimization) ✅**
- **Problem:** Full batching optimization broke progressive step rendering - users saw blank screen for 7-12s before ALL steps appeared at once
- **Solution:** Hybrid approach that balances speed with UX
  - Pre-batch cheap instructions (1-2s total for all products)
  - For each product: parallelize image + why copy for THAT product only
  - Immediately yield completed step (progressive update)
- **Result:** 
  - First step visible in ~2-3s (vs 26-45s serial, 7-12s blank in full batch)
  - Subsequent steps appear every ~2-3s as they complete
  - Total time: ~10-15s (still much faster than original 26-45s)
  - **User experience feels fast due to progressive rendering**

**2. Natural Product Placement in AI Images ✅**
- **Problem:** Overly prescriptive prompts caused awkward product overlays (compact floating on chin, foundation bottle in strange positions)
- **Solution:** Added flexible visibility rules to image generation:
  ```
  PRODUCT VISIBILITY (NATURAL & OPTIONAL):
  - Product MAY be visible if natural (e.g., holding brush with compact nearby)
  - Product does NOT need to be visible if awkward
  - If shown: only in natural positions (hand, vanity edge, lap)
  - NEVER overlay unnaturally on face/body
  - Focus is APPLICATION ACTION, not product showcase
  ```
- **Result:** More realistic, relatable application images without forced product displays

**3. Routine Length Variation Fixed ✅**
- **Problem:** Routine bonus logic was backwards - AM routines got +1 bonus, forcing ALL routines to exactly 5 steps regardless of complexity
- **Root Cause:** 
  ```python
  # WRONG (old code)
  if subcategory in ['pm', 'glam']: routine_bonus = 2
  elif subcategory in ['am', 'everyday']: routine_bonus = 1  # This forced AM to 5!
  ```
- **Solution:** Corrected the logic:
  ```python
  # CORRECT (new code)
  if subcategory in ['am', 'everyday']: routine_bonus = 0  # Keep minimal 4-5
  elif subcategory == 'pm': routine_bonus = 1  # Add 1: 5-6 steps
  elif subcategory == 'glam': routine_bonus = 2  # Add 2: 6-7 steps
  ```
- **Result:** Routine length now varies naturally:
  - Simple AM routine with 1 concern: 4 steps
  - Complex PM routine with 3 concerns: 6-7 steps
  - Glam makeup: 7-8 steps

### Performance Impact

| Metric | Morning Batch | Evening Hybrid | Change |
|--------|---------------|----------------|--------|
| First step visible | 7-12s (blank) | 2-3s | ✅ 70% faster perceived |
| Progressive updates | ❌ None (all at once) | ✅ Every 2-3s | ✅ Restored |
| Total time | 7-12s | 10-15s | ⚠️ 3-5s slower |
| User experience | ⭐⭐ (fast but jarring) | ⭐⭐⭐⭐⭐ (smooth & fast) | ✅ Much better |

**Trade-off Decision:** Sacrificed 3-5s of raw speed to restore progressive rendering, resulting in MUCH better perceived performance and user experience.

**Last Updated:** January 11, 2025 - MAJOR SPEED OPTIMIZATION ⚡

## Overview
A personalized beauty routine generator that transforms aesthetic preferences into curated product recommendations with AI-generated application imagery. Demonstrates the power of agentic workflows through a polished e-commerce experience.

## Agent Purpose
Given a user's desired aesthetic (e.g., "Ethereal Glow", "Bold Definition") and beauty preferences (skin type, concerns, tone), generate a complete, step-by-step routine with:
- Curated products from multiple brands
- Personalized "why this product" copy
- AI-generated application instruction images
- Complete usage instructions

## Mapping to Custom Experience

### Backend → Frontend Flow

**1. User Input (Frontend)**
```typescript
// AestheticToRoutineView.tsx sends structured message
sendMessage(JSON.stringify({
  aesthetic_id: "ethereal-glow",
  aesthetic_name: "Ethereal Glow",  // For custom aesthetics
  quiz_responses: {
    skin_type: "Dry",
    concerns: ["Hydration", "Anti-Aging"],
    skin_tone: "#F5D7C4",
    routine_type: "skincare",
    subcategory: "am"
  }
}))
```

**2. Agent Processing (Backend)**
```python
# agent.py orchestrates workflow
1. search_products() - Smart template matching
2. generate_application_instructions() - Step titles + full text
3. generate_product_image() - AI imagery for select steps
4. generate_why_copy() - Personalized explanations
5. Save artifact with complete routine
```

**3. Artifact Generation (Backend)**
```python
# Structured artifact saved via tool_context
artifact = {
  "type": "routine_result",
  "data": {
    "aesthetic_name": "Ethereal Glow",
    "routine_type": "skincare",
    "subcategory": "am",
    "products": [
      {
        "sku": "EST-123",
        "name": "Advanced Night Repair",
        "brand": "Estée Lauder",
        "category": "serum",
        "price": "$98.00",
        "image_url": "artifact://product_EST-123.jpeg",
        "instruction_title": "Press into skin with fingertips",
        "instruction_full": "Apply 2-3 drops...",
        "why_this": "Targets fine lines on mature skin..."
      }
    ]
  }
}
```

**4. Frontend Rendering**
```typescript
// AestheticToRoutineView.tsx receives artifact
useEffect(() => {
  if (artifact?.type === 'routine_result') {
    // Convert image URIs to Blob URLs
    // Render step-by-step routine display
    setRoutineResult(artifact.data)
  }
}, [artifact])
```

### Synchronization Mechanism
- **Single Session**: Both views share the same session ID
- **Artifact Storage**: Backend saves to session artifacts
- **Real-time Updates**: WebSocket streams artifact events
- **View Toggle**: Switching preserves full state (messages, artifacts, routine)
- **Chat Mapping**: JSON message appears in chat view as user input

## Architecture

### Current Implementation (Single Orchestrator)

```
aesthetic-to-routine Agent
├── Main Orchestrator (agent.py)
│   ├── Parse JSON quiz submission
│   ├── Call search_products() tool
│   ├── For each product:
│   │   ├── generate_application_instructions()
│   │   ├── generate_product_image() (select steps)
│   │   └── generate_why_copy()
│   └── Save routine artifact
└── Tools (tools.py)
    ├── search_products() - Template-based matching
    ├── generate_product_image() - Imagen2 via gemini-2.5-flash-image
    ├── generate_why_copy() - Gemini 2.5 Flash with ELC brand voice
    └── generate_application_instructions() - Gemini 2.5 Flash
```

### Key Design Decisions

**1. Template-Based Routine Building**
Instead of asking LLM to build routines, we use embedded templates:
```python
ROUTINE_TEMPLATES = {
  "skincare_am": {
    "steps": [
      {"category": "cleanser", "required": True, "image_priority": "first"},
      {"category": "serum", "required": True, "image_priority": "middle"},
      {"category": "moisturizer", "required": True, "image_priority": "last"}
    ]
  }
}
```

**Benefits:**
- Consistent routine structure
- Predictable step order (matches real beauty workflows)
- Control over which steps get AI images (performance)
- Easy to extend with new routine types

**2. Selective Image Generation**
Not every step needs an AI image:
```python
"image_priority": "first" | "middle" | "last" | "none"
```
Typically generate 3 images per 5-step routine (60% coverage) for speed.

**3. Product-Specific Image Prompts**
Enhanced prompts for realistic imagery:
```python
if "mascara" in category:
    rules = """
    - EXACTLY ONE mascara wand
    - Application to ONE eye only
    - Natural hand position
    """
```
Prevents common AI errors (dual wands, awkward hands, text overlays).

## Data Structure

### Products Schema (`data/default/products.json`)
```json
{
  "products": [
    {
      "sku": "EST-ANR-50ML",
      "name": "Advanced Night Repair Serum",
      "brand": "Estée Lauder",
      "category": "base",
      "sub_category": "serum",
      "description": "Reduces fine lines and wrinkles...",
      "ingredients": "Water, Bifida Ferment Lysate...",
      "price": "$98.00",
      "skin_types": ["All", "Dry", "Combination"],
      "concerns": ["Anti-Aging", "Hydration"],
      "routine_type": "skincare",
      "best_for_subcategory": ["AM", "PM"]
    }
  ]
}
```

### Aesthetics Schema (`data/default/aesthetics.json`)
```json
{
  "aesthetics": [
    {
      "id": "ethereal-glow",
      "title": "Ethereal Glow",
      "description": "Luminous, dewy skin...",
      "trendingTags": ["K-Beauty", "Glass Skin"],
      "imageUrl": "/aesthetic_ethereal_glow.jpg"
    }
  ]
}
```

## Current Performance

### Speed (After January 11 Optimization) ⚡

**Before Optimization:**
- **Product Search**: <100ms (template matching, no LLM)
- **Instructions**: ~1-2s × 5 products = 5-10s (serial)
- **Why Copy**: ~1-2s × 5 products = 5-10s (serial)
- **AI Images**: ~5-8s × 3 images = 15-24s (serial)
- **Delays**: ~1s (artificial waits)
- **Total**: ~26-45s for 5-step routine with 3 images

**After Morning Optimization (Full Batching):**
- **Product Search**: <100ms (unchanged)
- **Instructions**: ~1-2s for all 5 products (parallel with `asyncio.gather()`)
- **Why Copy**: ~1-2s for all 5 products (parallel with `asyncio.gather()`)
- **AI Images**: ~5-8s for all 3 images (parallel with `asyncio.gather()`)
- **Delays**: 0s (removed)
- **Total**: ~7-12s for 5-step routine with 3 images
- **Issue**: Progressive rendering broken - blank screen until all steps ready

**After Evening Fix (Hybrid Progressive):**
- **Product Search**: <100ms (unchanged)
- **Instructions**: ~1-2s for all 5 products (pre-batched in parallel)
- **Per-Product (Progressive)**:
  - Image + Why Copy: ~2-3s per product (parallelized)
  - First step visible: ~2-3s from start
  - Subsequent steps: every ~2-3s
- **Total**: ~10-15s for 5-step routine with 3 images
- **User Experience**: ⭐⭐⭐⭐⭐ Progressive rendering + still fast

**Performance Improvement: 2-3× faster than original** (11-30 seconds saved)
- More importantly: FEELS faster due to progressive rendering

### Implementation Details

**Parallel Batch Processing:**
```python
# Before: Sequential (slow)
for product in products:
    instructions = await generate_application_instructions(...)  # 1-2s each
    image = await generate_product_image(...)  # 5-8s each
    why = await generate_why_copy(...)  # 1-2s each

# After: Parallel (fast)
all_instructions = await asyncio.gather(*[
    generate_application_instructions(...) for p in products
])  # All complete in ~1-2s total

all_images = await asyncio.gather(*[
    generate_product_image(...) for p in products if p.needs_image
])  # All complete in ~5-8s total

all_why = await asyncio.gather(*[
    generate_why_copy(...) for p in products
])  # All complete in ~1-2s total
```

**Progressive Rendering Maintained:**
- Users still see each step appearing incrementally
- But now each step appears rapidly after AI generation completes
- First product visible in ~2-3s instead of ~8-10s
- Subsequent products appear every ~0.1s instead of ~5-8s

**Performance Breakdown:**

| Phase | Serial (Original) | Full Batch (Morning) | Hybrid (Evening) | User Experience |
|-------|-------------------|----------------------|------------------|-----------------|
| Instructions (5×) | 5-10s | 1-2s (pre-batch) | 1-2s (pre-batch) | Hidden prep |
| First Step Visible | 8-10s | 7-12s blank | 2-3s ✅ | Immediate feedback |
| Images (3×) | 15-24s | 5-8s (all at once) | 6-9s (progressive) | Smooth reveals |
| Why Copy (5×) | 5-10s | 1-2s (all at once) | 6-9s (progressive) | With each step |
| Progressive Updates | ✅ Yes | ❌ No | ✅ Yes | Much better UX |
| **TOTAL TIME** | **26-45s** | **7-12s** | **10-15s** | **Optimal balance** |

### Quality
- ✅ Consistent routine structure (template-based)
- ✅ Personalized copy (skin type + concerns)
- ✅ Realistic application images (enhanced prompts)
- ✅ Multi-brand recommendations (ELC portfolio)
- ✅ Proper step sequencing (matches real workflows)
- ✅ **No quality loss from parallelization** - all AI calls still happen, just concurrently

## Pending Improvements

### 1. Multi-Agent Refactor

**Current Problem:**
Single orchestrator does everything sequentially. If one tool fails, whole routine fails.

**Proposed Architecture:**
```
Main Orchestrator
├── Product Specialist Agent (search + filtering)
├── Content Creator Agent (instructions + why copy)
├── Image Generator Agent (AI imagery)
└── Quality Assurance Agent (validate routine)
```

**Benefits:**
- Parallel execution where possible
- Specialized prompts per agent
- Better error handling (one agent failure doesn't crash routine)
- Easier to extend (add new agents for new capabilities)

**Challenge:**
Preserve current quality and consistency. Current prompts are highly tuned.

**Approach:**
1. Keep existing tools as-is
2. Wrap each in dedicated LlmAgent
3. Main orchestrator delegates to sub-agents
4. Maintain template-based routine building
5. Test extensively to ensure no quality regression

**Files to Modify:**
- `agent.py` - Split into orchestrator + sub-agents
- `tools.py` - Keep as-is, wrapped by agents
- Add new agent definitions for each specialty

### 2. Routine Length Variation ✅ FIXED (Jan 11, 2025)

**Problem:** All routines were exactly 5 steps regardless of complexity
**Root Cause:** Routine bonus logic was backwards - AM routines got +1 bonus when they should get 0
**Solution:** Corrected the bonus calculation:
```python
# BEFORE (wrong)
routine_bonus = 2 if subcategory in ['pm', 'glam'] else 1  # AM got +1!

# AFTER (correct)
if subcategory in ['am', 'everyday']: routine_bonus = 0  # Minimal
elif subcategory == 'pm': routine_bonus = 1              # +1 step
elif subcategory == 'glam': routine_bonus = 2            # +2 steps
```

**Result:** Routines now vary naturally:
- Simple AM (1 concern): 4 steps
- Complex PM (3 concerns): 6-7 steps
- Glam makeup: 7-8 steps

## Configuration

### Environment Variables (`config.py`)
```python
BRAND_DATA_SET = "default"  # Which product catalog to use
MAX_ROUTINE_STEPS = 10      # Upper bound on routine length
MIN_ROUTINE_STEPS = 4       # Minimum for complete routine
```

### Agent Registration (`agent-stage-ui/src/config.ts`)
```typescript
'aesthetic-to-routine': {
  name: 'Aesthetic to Routine',
  description: 'Personalized beauty routines',
  demo_type: 'aesthetic-to-routine',  // Triggers custom experience
  port: 8081
}
```

## Key Files

### Backend
- `agent.py` - Main orchestrator (270 lines)
- `tools.py` - All tool implementations (900 lines)
- `config.py` - Configuration and constants
- `data/default/products.json` - Product catalog (100+ products)
- `data/default/aesthetics.json` - Aesthetic definitions

### Frontend (in agent-stage-ui)
- `CustomExperience/demos/AestheticToRoutineView.tsx` - Main UI (1200 lines)
- `CustomExperience/demos/aesthetic-to-routine/ProductDetailModal.tsx`
- `CustomExperience/demos/aesthetic-to-routine/CartModal.tsx`
- `CustomExperience/demos/aesthetic-to-routine/ScrollingCarousel.tsx`

## Testing

### Manual Test Cases
1. **Pre-defined Aesthetic** (e.g., "Ethereal Glow")
   - Select from carousel
   - Complete quiz
   - Verify routine matches aesthetic
   
2. **Custom Aesthetic** (e.g., "Latte Makeup")
   - Enter custom text
   - Select routine type (Makeup → Everyday)
   - Verify title shows custom name
   - Verify routine uses correct template

3. **View Toggle**
   - Generate routine in custom view
   - Toggle to "Under the Hood"
   - Verify chat messages visible
   - Verify traces show tool calls
   - Toggle back to custom view
   - Verify routine still displayed

4. **Product Interactions**
   - Click product for modal
   - Verify image, description, ingredients
   - Click "Add to Cart"
   - Verify cart modal shows products
   - Click "Print Cheatsheet"
   - Verify PDF generation

### Known Issues
None currently blocking. Quality improvements needed (see Pending Improvements).

## Running Locally

```bash
# Terminal 1: Start backend agent
cd agents/aesthetic-to-routine
python -m google.adk.cli.cli_run agent.py

# Terminal 2: Start frontend
cd agent-stage/agent-stage-ui
npm run dev

# Open browser to http://localhost:5173
# Select "Aesthetic to Routine" agent
# Custom experience loads automatically
```

## Success Criteria

### Current Status
✅ **Functional**: Generates complete routines with images
✅ **Polished UI**: Executive-ready presentation
✅ **Dual-View**: Toggle between custom and technical views
✅ **Personalized**: Skin type + concerns drive recommendations
✅ **Multi-Brand**: Spans entire ELC portfolio
✅ **AI Imagery**: Realistic application photos
✅ **Custom Aesthetics**: User can enter free-text aesthetics
✅ **UDP Storytelling**: Demonstrates unified data platform value through personalized greetings, pre-populated preferences, and multi-source messaging
✅ **Trending Tags**: Display behavioral data on aesthetic tiles (#hashtag format, increased size to 0.85rem label / 0.95rem hashtags)
✅ **Consolidated Quiz**: Single-page modal for streamlined UX
✅ **Carousel Interactions**: Smooth drag/click distinction with 5px threshold
✅ **Customer Profile Loading**: Backend serves profile, frontend consumes (with timing caveat - see Known Issues)

### Recent Enhancements

**UI/UX Improvements:**
- **Trending Tags Typography**: Increased from default to 0.85rem (label) and 0.95rem bold (hashtags) for better readability
- **Carousel Click Handling**: Added 5px drag threshold to prevent position jumps when clicking cards
- **Smooth Scroll**: Auto-resume carousel scrolling after 3 seconds of inactivity

**UDP Integration:**
- **Customer Profile**: Loads from `customer_profile.json` (simulates unified CDP data)
- **Personalized Greeting**: Shows "Welcome Back, [Name]" with tailored subtitle
- **Pre-Populated Quiz**: Auto-fills preferences from profile (skin type, concerns, skin tone)
- **Completion Messaging**: References unified data sources in final routine message

### Known Issues
⚠️ **Customer Profile Auto-Load Timing**: Profile loads when switching to chat view but not immediately on custom experience mount. Root cause: Zustand store session loading happens after component initialization. Workaround: Click wrench button to trigger profile load.

### Pending Improvements
✅ **Speed Optimization**: Parallelized AI calls - COMPLETED Jan 11, 2025
✅ **Progressive Rendering**: Hybrid approach balancing speed + UX - COMPLETED Jan 11, 2025
✅ **Natural Product Images**: Flexible visibility rules - COMPLETED Jan 11, 2025
✅ **Routine Length Variation**: Fixed bonus logic - COMPLETED Jan 11, 2025
⏳ **Routine History**: Browse previously generated routines within session
⏳ **Enhanced Personalization**: Leverage purchase history for brand-specific recommendations
⏳ **Multi-Agent Refactor**: Split into specialized agents for better error handling