# Aesthetic-to-Routine Agent - Current State

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

### Speed
- **Product Search**: <100ms (template matching, no LLM)
- **Instructions**: ~1-2s per product (Gemini Flash)
- **Why Copy**: ~1-2s per product (Gemini Flash)
- **AI Images**: ~5-8s per image (Imagen2)
- **Total**: ~30-45s for 5-step routine with 3 images

### Quality
- ✅ Consistent routine structure (template-based)
- ✅ Personalized copy (skin type + concerns)
- ✅ Realistic application images (enhanced prompts)
- ✅ Multi-brand recommendations (ELC portfolio)
- ✅ Proper step sequencing (matches real workflows)

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

### 2. Investigate Routine Length Consistency

**Observation:**
Almost all generated routines are exactly 5 steps, despite varying:
- Skin types
- Number of concerns
- Routine type (AM/PM/Everyday/Glam)
- User complexity

**Current Logic:**
```python
# config.py
MAX_ROUTINE_STEPS = 10
MIN_ROUTINE_STEPS = 4

# tools.py
complexity_bonus = min(num_concerns - 1, 2)  # 0-2 extra steps
routine_bonus = 2 if subcategory in ['pm', 'glam'] else 1
target_length = num_required + complexity_bonus + routine_bonus
```

**Expected Behavior:**
- Simple user (1 concern, AM) → 4-5 steps
- Complex user (3+ concerns, PM) → 7-8 steps
- Glam makeup → 8-10 steps

**Actual Behavior:**
Most routines → exactly 5 steps

**Investigation Needed:**
1. Check template step counts (may all have 5 required steps)
2. Verify complexity/routine bonuses are calculated correctly
3. Test if optional steps are being excluded too aggressively
4. Add logging to track target_length vs actual_length

**Files to Investigate:**
- `tools.py` - search_products() lines 180-230
- `agent.py` - Routine building logic
- Add debug logging for step selection process

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
⏳ **Multi-Agent Refactor**: Split orchestrator into specialized agents for parallel execution (performance optimization)
⏳ **Adaptive Routine Length**: Vary step count based on user complexity (currently ~5 steps for all)
⏳ **Routine History**: Browse previously generated routines within session
⏳ **Enhanced Personalization**: Leverage purchase history for brand-specific recommendations
⏳ **Speed Optimization**: Analyze ADK execution flow to identify bottlenecks in routine generation (30-45s currently)