# Implementation Plan - Bug Fixes from User Testing

## Executive Summary
Four critical issues identified during Korean Glow PM routine test. All must be fixed before executive demo.

---

## 🔴 ISSUE 1: Routine Order Broken (CRITICAL ARCHITECTURAL FIX)

### The Real Problem (Deeper than I Initially Understood)
The current logic **destroys the semantic correctness of routine sequences**. This affects:
1. **Visual coherence**: Images on wrong steps
2. **Narrative flow**: Instructions don't tell a coherent story
3. **Realistic application order**: Products applied in illogical sequence

### Why Template Order is Sacred

Templates are **beauty expertise encoded as data**. They define:
- The canonical sequence for applying products (cleanser → toner → serum → moisturizer)
- The narrative arc of a routine (prep → treat → seal → protect)
- Which steps are foundational vs. enhancement

**Example: PM Skincare Template (Correct Order)**
```python
[
  {"category": "cleanser", "required": True},    # 1. Remove day
  {"category": "toner", "required": False},      # 2. Prep skin
  {"category": "serum", "required": True},       # 3. Active treatment
  {"category": "eye cream", "required": False},  # 4. Target delicate area
  {"category": "night cream", "required": True}  # 5. Lock it all in
]
```

**Current Logic (WRONG):**
```python
required = [cleanser, serum, night cream]  # Extracted
optional = [toner, eye cream]              # Extracted
final = required + optional                # Concatenated
# Result: [cleanser, serum, night cream, toner, eye cream]
```

**What's Wrong:**
- Night cream (step 3/5) happens BEFORE toner (step 4/5)
- Narrative breaks: "Lock in moisture" happens before "Prep skin"
- Image on step 3 (night cream) says "last" but it's not actually last
- Eye cream at the end feels tacked-on, not integrated

### The Fix: Preserve Template Order

**New Logic:**
```python
# Don't separate - mark steps for inclusion while preserving order
included_count = 0
for step in routine_steps:
    if included_count >= target_length:
        step["include"] = False
    elif step.get("required", False):
        step["include"] = True
        included_count += 1
    else:
        # Include optional step if we have budget
        if included_count < target_length:
            step["include"] = True
            included_count += 1
        else:
            step["include"] = False

# Filter to included steps (preserves original order)
final_steps = [s for s in routine_steps if s.get("include", False)]
```

**Result:**
```
[cleanser, toner, serum, eye cream, night cream]
```
- Order makes sense: prep → treat → target → seal
- "Last" step is actually last
- Narrative flows naturally

### Implementation

**File:** `agents/aesthetic-to-routine/tools.py`
**Lines to Change:** 173-201

**Before:**
```python
# Step 2: Determine how many optional steps to include
required_steps = [s for s in routine_steps if s.get("required", False)]
optional_steps = [s for s in routine_steps if not s.get("required", False)]

# ... complexity calculation ...

# Step 3: Build final step list (required + selected optional)
final_steps = required_steps + optional_steps[:optional_to_add]
```

**After:**
```python
# Step 2: Calculate target length based on user complexity
num_concerns = len(concerns_lower) if concerns_lower else 0
complexity_bonus = min(num_concerns - 1, 2)

routine_bonus = 0
if subcategory:
    if subcategory.lower() in ['pm', 'glam']:
        routine_bonus = 2
    elif subcategory.lower() in ['am', 'everyday']:
        routine_bonus = 1

# Count required steps
num_required = sum(1 for s in routine_steps if s.get("required", False))
target_length = num_required + complexity_bonus + routine_bonus
target_length = max(config.MIN_ROUTINE_STEPS, min(config.MAX_ROUTINE_STEPS, target_length))

print(f"[SEARCH_PRODUCTS] Target routine length: {target_length}")

# Step 3: Mark steps for inclusion while preserving template order
included_count = 0
for step in routine_steps:
    if step.get("required", False):
        # Always include required steps
        step["include"] = True
        included_count += 1
    else:
        # Include optional step if we have budget
        if included_count < target_length:
            step["include"] = True
            included_count += 1
        else:
            step["include"] = False

# Build final steps list (preserves template order)
final_steps = [s for s in routine_steps if s.get("include", False)]
```

**Testing:** After fix, verify:
- ✅ Steps appear in template-defined order
- ✅ "First" image is on actual first step
- ✅ "Last" image is on actual last step  
- ✅ Narrative flows logically (prep → treat → seal)

---

## 🔴 ISSUE 2: Price Data Hallucination (BACKEND SCHEMA GAP)

### The Problem
**Backend doesn't send price** → **Frontend generates fake price** → **User sees wrong prices**

### Broader Concern: Metadata Completeness
Not just price - need to verify ALL product metadata is being sent correctly.

### Audit: What's Missing from Artifact Schema?

**File:** `agents/aesthetic-to-routine/agent.py:497-515`

**Currently Sent:**
```python
"product": {
    "name": product.get("name", ""),
    "brand": brand,
    "sku": sku,
    "brand_logo_artifact": brand_logo_artifact,
    "product_image_artifact": product_image_artifact,
    "ai_image_artifact": ai_image_artifact_name,
    "title": instruction_title,
    "description": instruction_full,
    "why": why_text,
    "skin_types": product.get("skin_types", []),
    "concerns": product.get("concerns", []),
    "sub_category": product.get("sub_category", "")
}
```

**Available in products.json but NOT sent:**
```python
"price": 390.00,                    # ❌ MISSING
"sensory_descriptors": {...},       # ❌ MISSING (texture, finish, scent, application)
"ingredients_highlight": "...",     # ❌ MISSING
"category": "base",                 # ❌ MISSING (only sub_category sent)
"routine_type": "skincare",         # ❌ MISSING
"best_for_subcategory": ["PM"],     # ❌ MISSING
"best_for_aesthetic": "..."         # ❌ MISSING
```

### Implementation: Complete Metadata Transfer

**File:** `agents/aesthetic-to-routine/agent.py`
**Line:** 510 (product dictionary)

**Add These Fields:**
```python
"product": {
    # ... existing fields ...
    "price": product.get("price"),  # ✅ Critical for display
    "category": product.get("category", ""),  # ✅ Useful for UI grouping
    "sensory_descriptors": product.get("sensory_descriptors", {}),  # ✅ Rich detail for modal
    "ingredients_highlight": product.get("ingredients_highlight", ""),  # ✅ Product detail
    # Don't need: routine_type, best_for_subcategory (internal filtering only)
}
```

**Frontend Cleanup:** `ProductDetailModal.tsx:36-48`

**Before:**
```typescript
const generatePriceForProduct = (name: string): number => {
  // ... hash-based fake price generation ...
};

const displayPrice = product.price
  ? `$${product.price}.00`
  : `$${generatePriceForProduct(product.name)}.00`;  // ❌ FALLBACK
```

**After:**
```typescript
const displayPrice = product.price
  ? `$${Number(product.price).toFixed(2)}`
  : 'Price unavailable';  // ✅ Honest fallback
```

**Enhanced Product Details (Bonus):**
Use `sensory_descriptors` and `ingredients_highlight` in modal:

```typescript
// Add to modal display
{product.sensory_descriptors?.texture && (
  <Typography variant="body2">
    <strong>Texture:</strong> {product.sensory_descriptors.texture}
  </Typography>
)}

{product.ingredients_highlight && (
  <Typography variant="body2">
    <strong>Key Ingredients:</strong> {product.ingredients_highlight}
  </Typography>
)}
```

---

## 🟡 ISSUE 3: Chat History Not Visible After Switching (STATE PERSISTENCE)

### Clarified Requirements
User does NOT want side-by-side views. They want:
1. **Full progression visible in BOTH views** (all messages/events)
2. **Only active view updates in real-time** (performance)
3. **Switching views shows complete history** (no missing messages)

### Root Cause
Messages ARE in the store, but ChatPanel's rendering may be hiding/collapsing tool calls or intermediate messages.

### Verification Steps

1. **Check Message Store:** Confirm all events are persisted
2. **Check Rendering Logic:** Ensure tool calls visible
3. **Check Message Grouping:** Verify progressive messages not collapsed

### Implementation

**File:** `agent-stage/agent-stage-ui/src/components/ChatPanel.tsx`

**Current Message Grouping:** Lines 61-88
```typescript
const groupMessages = (messages: any[]): MessageGroup[] => {
  // Groups consecutive messages from same author
  // This may hide intermediate agent messages!
}
```

**Fix 1: Don't Collapse Tool Messages**
```typescript
// In message rendering (lines 440-452), ensure tool calls ALWAYS render
{msg.content?.parts?.map((part: any, i: number) => {
  if (part.functionCall || part.functionResponse) {
    return (
      <ToolCallPellet
        key={`${msgIndex}-${i}`}
        part={part}
        eventId={msg.id}
        onClick={handlePelletClick}
        // ✅ Make these more prominent
        sx={{ my: 1 }}  // Add vertical spacing
      />
    );
  }
  return null;
})}
```

**Fix 2: Visual Separation of Progressive Updates**

Add timestamp or step markers to show message flow:
```typescript
{!isUser && group.messages.length > 1 && (
  <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
    {group.messages.length} updates
  </Typography>
)}
```

**Fix 3: Scroll to Latest When Switching Back**

In `ChatPanel.tsx`, ensure auto-scroll triggers when switching from Custom Experience:
```typescript
useEffect(() => {
  if (!customExperienceActive && autoScrollEnabled) {
    scrollToBottom(false);  // Instant scroll on view switch
  }
}, [customExperienceActive]);
```

---

## 🟢 ISSUE 4: Print Cheatsheet Missing Images (ENHANCEMENT)

### Goal
Add product images and/or AI application images to printed routine.

### Implementation

**File:** `agent-stage/agent-stage-ui/src/components/CustomExperience/demos/AestheticToRoutineView.tsx`

**Add Print-Specific Styles:**
```typescript
const printStyles = `
@media print {
  .routine-step-image {
    display: block !important;
    max-width: 200px;
    height: auto;
    page-break-inside: avoid;
    margin: 10px auto;
  }
  
  .ai-application-image {
    max-width: 300px;
    border: 1px solid #ddd;
  }
  
  .product-thumbnail {
    max-width: 120px;
    border: 1px solid #ddd;
  }
  
  .step-container {
    page-break-inside: avoid;
    page-break-after: auto;
  }
  
  /* Hide interactive elements */
  button, .no-print {
    display: none !important;
  }
}
`;
```

**Update Print Template:**
```tsx
<div className="step-container" style={{ pageBreakInside: 'avoid' }}>
  <Typography variant="h6">STEP {step.step_number} • {step.category}</Typography>
  
  {/* AI Application Image (if available) */}
  {step.product.ai_image_artifact && (
    <img 
      src={getArtifactUrl(step.product.ai_image_artifact)}
      alt={step.product.title}
      className="routine-step-image ai-application-image"
    />
  )}
  
  {/* Product Thumbnail (if available) */}
  {step.product.product_image_artifact && (
    <img 
      src={getArtifactUrl(step.product.product_image_artifact)}
      alt={step.product.name}
      className="routine-step-image product-thumbnail"
    />
  )}
  
  {/* Product info */}
  <Typography><strong>{step.product.name}</strong></Typography>
  <Typography>{step.product.description}</Typography>
  <Typography><em>{step.product.why}</em></Typography>
</div>
```

---

## Priority & Sequencing

| Phase | Issue | Time | Impact | Status |
|-------|-------|------|--------|--------|
| **PHASE 7** | Price + Metadata | 10 min | 🔴 Critical | Ready |
| **PHASE 8** | Routine Order | 30 min | 🔴 Critical | Ready |
| **PHASE 9** | Chat History | 15 min | 🟡 High | Ready |
| **PHASE 10** | Print Images | 20 min | 🟢 Nice-to-have | Ready |

**Total Estimated Time:** ~75 minutes

---

## Testing Protocol

After each phase, test with **Korean Glow PM** routine:

### Phase 7 Verification
- [ ] All prices match products.json exactly
- [ ] Product modal shows correct metadata
- [ ] No "Price unavailable" fallbacks

### Phase 8 Verification  
- [ ] Steps appear in logical order (cleanser → toner → serum → eye → night cream)
- [ ] First step has AI image
- [ ] Last step has AI image
- [ ] 1-2 middle steps have AI images
- [ ] Narrative flows naturally ("After cleansing..." → "Lock in moisture...")

### Phase 9 Verification
- [ ] Generate routine in Custom Experience view
- [ ] Switch to Chat view
- [ ] Confirm all progressive messages visible (✨ Step 1/5, 🔧 Tool calls, ✓ Complete)
- [ ] Tool call pellets are prominent and clickable

### Phase 10 Verification
- [ ] Click "Print Cheatsheet"
- [ ] Verify AI images render in print preview
- [ ] Verify product thumbnails render in print preview
- [ ] Confirm page breaks don't split steps awkwardly
- [ ] Save as PDF to verify final output

---

## Next Steps

Ready to switch to Code mode and implement these fixes sequentially. Each phase is well-defined and testable.

Awaiting approval to proceed.