# Phase 6: Deep Issue Analysis & Resolution Plan

## Overview
This document analyzes the 7 issues identified during testing and provides detailed investigation, root cause analysis, questions for stakeholder, and proposed solutions.

---

## Issue 1: Product Image Mismatch (CRITICAL - Requires Debugging)

### Symptom
"Double Wear Stay-in-Place Makeup" (foundation, SKU: EL-DW-002) displays with a lipstick product image instead of a foundation bottle. This has occurred twice for this exact product.

### Code Investigation
**File**: `agents/aesthetic-to-routine/agent.py`, lines 401-422

```python
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
```

### Analysis
The code logic is correct - it:
1. Constructs filename from SKU: `product_EL-DW-002.jpg`
2. Looks in correct directory: `data/default/images/products/`
3. Loads and saves as artifact

**Likely Root Cause**: The actual JPG file `product_EL-DW-002.jpg` in the filesystem contains the wrong image (lipstick instead of foundation).

### Questions for Stakeholder
1. **Can you verify the actual file?** Check `agents/aesthetic-to-routine/data/default/images/products/product_EL-DW-002.jpg` - does it show a foundation or lipstick?
2. **Should we add logging?** I can add console logs showing which file path is being loaded for each product to help debug this.

### Proposed Solution
1. **Immediate**: Add detailed logging to show which file is loaded for each product
2. **Debug Mode**: Add a validation script that checks all product SKUs against their actual image files
3. **Long-term**: Add product image validation to prevent mismatches

---

## Issue 2: Carousel Speed Mismatch

### Symptom
Skincare and Makeup carousels appear to scroll at different speeds, even though both are set to "medium".

### Code Investigation
**File**: `agent-stage/agent-stage-ui/src/components/CustomExperience/demos/aesthetic-to-routine/InfiniteScrollCarousel.tsx`

**Speed Configuration** (lines 27-31):
```typescript
const speedDuration = {
  slow: '60s',
  medium: '40s',
  fast: '20s',
};
```

**Animation** (line 142):
```typescript
animation: `scroll ${speedDuration[speed]} linear infinite`,
animationDirection: direction === 'right' ? 'reverse' : 'normal',
```

**Usage in AestheticToRoutineView.tsx**:
- Skincare (line 937): `speed="medium"` + `direction="left"`
- Makeup (line 963): `speed="medium"` + `direction="right"`

### Analysis
Both carousels use the same speed (40s), but opposite directions. The **perceptual difference** may be due to:
1. Different number of items in each carousel
2. CSS animation direction reversal affecting perceived speed
3. Parallax effect from opposite directions

### Proposed Solution
**Option A - Normalize Speed Calculation**: 
Make speed based on pixel distance rather than time, accounting for number of items.

**Option B - Match Everything**:
Same speed, same direction, same number of visible items at once.

**Recommendation**: Option A - calculates actual pixels/second to ensure identical visual speed regardless of item count or direction.

---

## Issue 3: Carousel Reset/Jump

### Symptom
Top carousel (skincare) appears to "end" and then suddenly reset when last image hits middle. Bottom carousel (makeup) doesn't have this issue.

### Code Investigation
**File**: `agent-stage/agent-stage-ui/src/components/CustomExperience/demos/aesthetic-to-routine/InfiniteScrollCarousel.tsx`

**Seamless Loop Logic** (lines 147-151):
```typescript
{/* Render original items */}
{items.map((item) => renderCard(item, false))}

{/* Render duplicates for seamless loop */}
{items.map((item) => renderCard(item, true))}
```

### Analysis
The current implementation duplicates items once (100% duplication). If there are only 3 skincare aesthetics but 7 makeup aesthetics:
- Skincare: 3 original + 3 duplicates = 6 total (visible "seam" when loop resets)
- Makeup: 7 original + 7 duplicates = 14 total (smooth transition)

The animation translates to -50% (line 131), which works IF you have enough content. With fewer items, the reset is visible.

### Proposed Solution
**Triple Rendering**: Render items 3 times instead of 2 times to ensure enough "buffer" before the reset is visible:
```typescript
{items.map((item) => renderCard(item, false))}
{items.map((item) => renderCard(item, true))}
{items.map((item) => renderCard(item, true))} // Add third set
```
And adjust animation to `-66.67%` instead of `-50%`.

---

## Issue 4: Manual Carousel Controls

### Symptom
Users want ability to manually scroll carousels (drag or arrows) and have auto-scroll resume after interaction.

### Current State
No manual controls - pure auto-scroll only.

### Proposed Solution
**Approach**: Add drag-to-scroll with mouse/touch + optional arrow buttons.

**Features**:
1. **Drag to scroll**: Mouse down + drag, touch swipe
2. **Pause on interaction**: Auto-scroll pauses during drag
3. **Resume after delay**: Auto-scroll resumes 3 seconds after last interaction
4. **Optional arrows**: Left/right buttons on hover (can be enabled/disabled via prop)

**Implementation**:
- Add state: `isDragging`, `dragStartX`, `lastInteraction`
- Add handlers: `onMouseDown`, `onMouseMove`, `onMouseUp`, `onTouchStart`, etc.
- Add timer: Resume auto-scroll 3s after `lastInteraction`

---

## Issue 5: Routine Length Not Dynamic (CRITICAL LOGIC ISSUE)

### Symptom
Most routines are still 5 steps, but should vary based on template and user needs.

### Code Investigation

**Current Logic**:

1. **config.py** (line 17):
```python
MAX_ROUTINE_STEPS = 5  # HARDCODED LIMIT
```

2. **tools.py** (line 176):
```python
for step_config in routine_steps[:config.MAX_ROUTINE_STEPS]:  # CUTS AT 5
```

3. **Templates** (tools.py, lines 53-94):
```python
"skincare_pm": {
    "steps": [
        # 7 total steps defined, some required=True, some required=False
    ]
}
```

### Analysis
**The Problem**: We have proper templates with 5-12 steps and `required` flags, BUT we're cutting everything off at MAX_ROUTINE_STEPS=5. This completely undermines the template logic.

**Expected Behavior** (from user's example):
- Skincare AM: 5-6 steps
- Skincare PM: 6-7 steps  
- Makeup Everyday: 5-8 steps
- Makeup Glam: 8-12 steps

The routine length should be determined by:
1. **Template structure** (required vs optional steps)
2. **User complexity** (more concerns = more targeted treatments)
3. **Aesthetic requirements** (glam looks need more steps than natural)

### Questions for Stakeholder
1. **Should we remove MAX_ROUTINE_STEPS entirely?** Let templates dictate length?
2. **Or implement smart bounds?** e.g., MIN=4, MAX=10, but respect template logic within those bounds?
3. **How should optional steps be decided?** Should we add optional steps based on:
   - User's number of concerns (more concerns = add optional treatment steps)?
   - Routine subcategory (PM/Glam = add more optional steps)?

### Proposed Solution (3 Options)

**Option A - Remove Limit, Trust Templates**:
```python
# config.py
# Remove MAX_ROUTINE_STEPS or set to 15
MAX_ROUTINE_STEPS = 15

# tools.py - respect template + smart filtering
for step_config in routine_steps:  # No slicing
    if step_config["required"] or should_include_optional(step_config, user_context):
        # add to routine
```

**Option B - Smart Bounds with Template Logic**:
```python
def build_routine(template, user_context):
    routine = []
    
    # Always include required steps
    for step in template["steps"]:
        if step["required"]:
            routine.append(step)
    
    # Add optional steps based on user context
    for step in template["steps"]:
        if not step["required"] and meets_criteria(step, user_context):
            routine.append(step)
    
    # Enforce bounds
    routine = routine[:config.MAX_ROUTINE_STEPS]
    if len(routine) < config.MIN_ROUTINE_STEPS:
        # Add most relevant optional steps to reach min
        pass
    
    return routine
```

**Option C - Dynamic Based on Complexity**:
Calculate "complexity score" from user inputs:
- Base routine length from template
- +1 step per additional concern beyond first
- +1 step for glam/PM (more elaborate)
- Cap at template max

**Recommendation**: **Option B** - respects template structure while allowing intelligent optional step inclusion.

---

## Issue 6: Eyeshadow Application Detail

### Symptom
Eyeshadow steps should show nuanced application (inner lid, middle lid, outer lid, crease, brow bone) in both instructions AND images.

### Current State
**tools.py** (line 397):
```python
"eyeshadow": "eyelids",  # Too generic
```

### Proposed Solution
**1. Enhanced Eyeshadow Prompting** (tools.py):
```python
# Special handling for eyeshadow in generate_application_instructions
if "eyeshadow" in category.lower():
    prompt += """
    
SPECIAL: This is EYESHADOW - provide DETAILED placement instructions:
- Specify colors/shades by eye zone (inner corner, lid, outer corner, crease, brow bone)
- Include blending techniques ("blend into crease", "diffuse edges")
- Be specific about brush movements and application order
- Example: "Apply lightest shade to inner corner and brow bone. Sweep medium shade across lid. Pack darkest shade onto outer corner and blend into crease."
"""
```

**2. Enhanced Image Generation** (tools.py, image prompt):
```python
if "eyeshadow" in category.lower():
    prep_hints.append("EYESHADOW APPLICATION ZONES - show: inner lid (light), middle lid (medium), outer corner (dark), crease (transition), brow bone (highlight)")
    prep_hints.append("Use fingers or brush applying to MULTIPLE eye zones simultaneously")
```

---

## Issue 7: Toggle Icon Change

### Symptom
Toggle button currently uses `<ChatIcon />` but should use something representing "under the hood" / technical view.

### Current Code
**File**: `agent-stage/agent-stage-ui/src/components/CustomExperience/CustomExperienceContainer.tsx` (line 115)

```typescript
<ChatIcon />
```

### Proposed Icons
1. **`<BuildIcon />`** - Wrench/construction (most "under the hood")
2. **`<CodeIcon />`** - Brackets/code (technical)  
3. **`<SettingsIcon />`** - Gear (configuration)
4. **`<TuneIcon />`** - Sliders (fine-tuning)

### Recommendation
**`<BuildIcon />`** - Most clearly represents "under the hood" / technical view.

Update tooltip from "View Technical Details" to "View Under the Hood" or "View Agent Details".

---

## Priority & Execution Order

### MUST DEBUG FIRST (Can't code without data):
1. **Issue 1** - Product image mismatch (need to verify actual files or add logging)

### CAN CODE NOW:
2. **Issue 7** - Icon change (trivial, 2 lines)
3. **Issue 3** - Carousel reset fix (triple rendering, 5 minutes)
4. **Issue 2** - Carousel speed (normalize calculation, 15 minutes)

### REQUIRES STAKEHOLDER DECISION:
5. **Issue 5** - Routine length logic (need decision on which option)
6. **Issue 6** - Eyeshadow detail (straightforward once decided)
7. **Issue 4** - Manual carousel controls (larger scope, 1-2 hours)

---

## Next Steps

1. **Stakeholder**: Answer questions for Issues 1 and 5
2. **Implement Quick Wins**: Issues 7, 3, 2 (can do immediately)
3. **Implement After Decisions**: Issues 5, 6 (after stakeholder input)
4. **Implement Large Feature**: Issue 4 (manual controls - schedule separately)