# Testing Issues - Deep Dive Analysis

## Context
User tested Korean Glow PM routine. Identified 4 critical issues that need resolution before executive demo.

---

## 🔴 ISSUE 1: Image Generation Logic Broken

### Observed Behavior
- 5-step routine generated
- First 3 steps had AI images
- Last 2 steps had NO images
- Expected: First, last, and 1-2 middle steps should have images

### Root Cause Analysis

**Location:** [`tools.py:173-201`](agents/aesthetic-to-routine/tools.py:173)

The smart routine building logic **destroys the original template ordering**:

```python
# CURRENT (BROKEN):
required_steps = [s for s in routine_steps if s.get("required", False)]
optional_steps = [s for s in routine_steps if not s.get("required", False)]

# Calculate how many optional to add...
final_steps = required_steps + optional_steps[:optional_to_add]  # ❌ CONCATENATION BREAKS ORDER
```

**Example with `skincare_pm` template:**

Original template order:
1. Cleanser (required, `image_priority: "first"`) ✓
2. Toner (optional, `image_priority: "none"`)
3. Serum (required, `image_priority: "middle"`) ✓
4. Eye cream (optional, `image_priority: "none"`)
5. Night cream (required, `image_priority: "last"`) ✓

Current logic separates:
- `required_steps` = [Cleanser, Serum, Night cream]
- `optional_steps` = [Toner, Eye cream]

Then concatenates:
```python
final_steps = [Cleanser, Serum, Night cream] + [Toner, Eye cream]
# Results in: [Cleanser, Serum, Night cream, Toner, Eye cream]
```

Now Night cream is step 3/5 (not last!), so:
- Step 1: Cleanser - `image_priority: "first"` → IMAGE ✓
- Step 2: Serum - `image_priority: "middle"` → IMAGE ✓
- Step 3: Night cream - `image_priority: "last"` → IMAGE ✓ (but semantically wrong)
- Step 4: Toner - `image_priority: "none"` → NO IMAGE ✓
- Step 5: Eye cream - `image_priority: "none"` → NO IMAGE ✗ (should have image as actual last step)

**The template's semantic meaning of "first/middle/last" is broken when steps are reordered.**

### Solution Design

**Option A: Preserve Template Order (Recommended)**
Instead of separating required/optional, mark steps for inclusion in-place:

```python
# Mark which steps to include based on target length
for i, step in enumerate(routine_steps):
    if i < target_length:
        step["include"] = True
    else:
        step["include"] = False

# Filter to included steps (preserves original order)
final_steps = [s for s in routine_steps if s.get("include", False)]
```

**Option B: Recalculate Image Priority After Reordering**
After building `final_steps`, recalculate which steps get images:

```python
# After building final_steps, assign new image priorities
num_steps = len(final_steps)
for i, step in enumerate(final_steps):
    if i == 0:
        step["image_priority"] = "first"
    elif i == num_steps - 1:
        step["image_priority"] = "last"
    elif i == num_steps // 2:
        step["image_priority"] = "middle"
    else:
        step["image_priority"] = "none"
```

**Recommendation:** Use Option A to preserve template author's intent. Templates define the canonical order; we should respect it.

---

## 🔴 ISSUE 2: Price Data Hallucination

### Observed Behavior
- Origins Checks and Balances™ Face Wash shows **$96.00** (actual: $39.00)
- La Mer Crème de la Mer shows **$64.00** (actual: $390.00)
- Prices are **completely wrong**, not correlated with actual products

### Root Cause Analysis

**Backend:** [`agent.py:497-515`](agents/aesthetic-to-routine/agent.py:497)

The artifact schema sent to frontend **DOES NOT include price**:

```python
step = {
    "step_number": i,
    "category": product.get("step_category_display", ...),
    "product": {
        "name": product.get("name", ""),
        "brand": brand,
        "sku": sku,
        # ... many fields ...
        "skin_types": product.get("skin_types", []),
        "concerns": product.get("concerns", []),
        # ❌ NO PRICE FIELD!
    }
}
```

**Frontend:** [`ProductDetailModal.tsx:36-48`](agent-stage/agent-stage-ui/src/components/CustomExperience/demos/aesthetic-to-routine/ProductDetailModal.tsx:36)

When `product.price` is missing, frontend **generates a fake price using hash function**:

```typescript
const generatePriceForProduct = (name: string): number => {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = ((hash << 5) - hash) + name.charCodeAt(i);
    hash = hash & hash;
  }
  return 45 + (Math.abs(hash) % 81);  // Random price $45-$126
};

const displayPrice = product.price
  ? `$${product.price}.00`
  : `$${generatePriceForProduct(product.name)}.00`;  // ❌ FALLBACK
```

**Data Source:** [`products.json`](agents/aesthetic-to-routine/data/default/products.json)

All products have accurate prices:
- Line 11: `"price": 55.00` (Estée Lauder ANR)
- Line 74: `"price": 390.00` (La Mer)
- Line 536: `"price": 39.00` (Origins Face Wash)

### Solution

**Backend Fix:** Add price to artifact schema in [`agent.py:497-515`](agents/aesthetic-to-routine/agent.py:497):

```python
step = {
    "step_number": i,
    "category": product.get("step_category_display", ...),
    "product": {
        "name": product.get("name", ""),
        "brand": brand,
        "sku": sku,
        "price": product.get("price"),  # ✅ ADD THIS LINE
        # ... rest of fields ...
    }
}
```

**Frontend Cleanup:** Remove hash fallback in [`ProductDetailModal.tsx`](agent-stage/agent-stage-ui/src/components/CustomExperience/demos/aesthetic-to-routine/ProductDetailModal.tsx:36):

```typescript
const displayPrice = product.price
  ? `$${product.price.toFixed(2)}`
  : 'Price unavailable';  // Better fallback
```

---

## 🟡 ISSUE 3: Chat View Not Synchronized

### Observed Behavior
- User starts routine generation while in Custom Experience view
- Switches to Chat view after completion
- Sees only final answer message
- **Missing:** Progressive messages showing agent delegation, tool calls, step completion

### Root Cause Analysis

**Architecture:** [`ChatPanel.tsx:310-312`](agent-stage/agent-stage-ui/src/components/ChatPanel.tsx:310)

```typescript
if (customExperienceActive && customExperienceAvailable) {
  return <CustomExperienceContainer />;  // ❌ COMPLETE REPLACEMENT
}
```

When Custom Experience is active, **ChatPanel is completely unmounted**:
1. WebSocket messages arrive → store updated
2. ChatPanel not rendered → no UI update
3. User switches back → ChatPanel re-mounts with final state
4. All intermediate messages ARE in store, but...

**Message Rendering:** [`ChatPanel.tsx:61-88, 394-612`](agent-stage/agent-stage-ui/src/components/ChatPanel.tsx:61)

Messages are grouped by author and complex rendering logic may hide tool calls if not interactive.

### The Real Problem

User expectation: **"I want to see BOTH views simultaneously during execution"**
- Custom Experience shows progressive routine building (visual)
- Chat shows agent orchestration (technical)
- Presenter can toggle between views OR see both at once

Current architecture: **Mutually exclusive views** (either/or, not both)

### Solution Options

**Option A: Side-by-side Layout (Recommended for Demo)**
```
┌─────────────────────────────────────────┐
│ Custom Experience │ Chat View (Mini)    │
│ (Routine Display) │ (Live Agent Logs)   │
│                   │                     │
│  [Routine Steps]  │ ✨ Step 1/5...      │
│                   │ 🔧 ProductSpec...   │
│                   │ ✓ Step 1 complete   │
└─────────────────────────────────────────┘
```

**Option B: Picture-in-Picture Chat**
Custom Experience full-screen with floating, minimizable chat window showing live agent activity.

**Option C: Persist Messages When Switching**
Ensure ChatPanel shows ALL messages (including progressive ones) when switching back from Custom Experience. This requires:
- Message store keeps ALL events
- ChatPanel doesn't collapse/group tool call messages
- Clear visual separation between intermediate and final messages

**Recommendation:** Option C (quick fix) + Option A (future enhancement for executive demo polish).

### Quick Fix Implementation

1. **Ensure Tool Calls Visible:** Update ChatPanel rendering to always show tool call pellets prominently
2. **Message Persistence:** Verify store doesn't filter messages when Custom Experience is active
3. **Visual Indicator:** Add timestamp/separators to show message flow

### Future Enhancement (Option A)

Update [`Layout.tsx`](agent-stage/agent-stage-ui/src/components/Layout.tsx) to support split-pane mode:
- Left: Custom Experience (60% width)
- Right: Live Chat Feed (40% width, auto-scroll)
- Toggle between: Full Custom | Split | Full Chat

---

## 🟢 ISSUE 4: Print Cheatsheet Needs Images

### Observed Behavior
- Print cheatsheet is text-only
- Shows product names, steps, instructions, "why" copy
- **Missing:** Product images or AI application images

### Current State
Minimalist implementation prioritized speed over visual richness.

### Enhancement Design

**Print Layout Options:**

**Option A: Product Thumbnails Only**
```
┌────────────────────────────────────┐
│ STEP 1 • CLEANSER                  │
├────────────────────────────────────┤
│ [img] Origins Checks and Balances™ │
│       Frothy Face Wash             │
│                                    │
│ Massage onto damp face...          │
│ Why: Perfect for combination skin  │
└────────────────────────────────────┘
```

**Option B: AI Application Images (Premium)**
```
┌────────────────────────────────────┐
│ STEP 1 • CLEANSER                  │
├────────────────────────────────────┤
│ [AI image showing application]     │
│                                    │
│ Origins Checks and Balances™       │
│ Massage onto damp face...          │
└────────────────────────────────────┘
```

**Option C: Both (Recommended)**
```
┌────────────────────────────────────┐
│ STEP 1 • CLEANSER                  │
├────────────────────────────────────┤
│ [AI img]          [Product img]    │
│                                    │
│ Origins Checks and Balances™       │
│ Massage onto damp face...          │
└────────────────────────────────────┘
```

### Implementation

**Print Styles:** Add CSS for print media query in AestheticToRoutineView.tsx:

```css
@media print {
  .routine-step-image {
    display: block !important;
    max-width: 200px;
    height: auto;
    page-break-inside: avoid;
  }
  
  .ai-image {
    max-width: 300px;
  }
  
  .product-thumbnail {
    max-width: 120px;
  }
}
```

**Data Access:** Images are already in artifact schema:
- `product_image_artifact` (product photo)
- `ai_image_artifact` (personalized application)

Just need to render them in print view with `@media print` styles.

### Recommendation

Implement Option C (both images) with smart fallbacks:
- If AI image exists → show it prominently
- Always show product thumbnail (if available)
- Use CSS to ensure good printing (avoid page breaks mid-step)

---

## Priority Matrix

| Issue | Severity | Effort | Priority | Phase |
|-------|----------|--------|----------|-------|
| **#2: Price Hallucination** | 🔴 Critical | Low (1 line backend) | **P0** | PHASE 7 |
| **#1: Image Generation** | 🔴 Critical | Medium (refactor logic) | **P1** | PHASE 8 |
| **#3: Chat Sync (Quick Fix)** | 🟡 High | Low (ensure visibility) | **P1** | PHASE 9 |
| **#4: Print Images** | 🟢 Nice-to-have | Low (CSS + render) | **P2** | PHASE 10 |
| **#3: Split View (Future)** | 🟡 High | High (layout refactor) | **P3** | Future |

---

## Implementation Plan

### PHASE 7: Fix Price Data (5 minutes)
**File:** `agents/aesthetic-to-routine/agent.py`
**Change:** Add `"price": product.get("price")` to line 510

### PHASE 8: Fix Image Generation (30 minutes)
**File:** `agents/aesthetic-to-routine/tools.py`
**Change:** Preserve template order instead of concatenating required+optional

### PHASE 9: Fix Chat Visibility (15 minutes)
**Files:** `agent-stage-ui/src/components/ChatPanel.tsx`
**Change:** Ensure tool calls render prominently, add visual flow indicators

### PHASE 10: Add Print Images (20 minutes)
**File:** `agent-stage-ui/src/components/CustomExperience/demos/AestheticToRoutineView.tsx`
**Change:** Add images to print template with @media print CSS

---

## Testing Checklist

After implementing fixes:
- [ ] Korean Glow PM routine generates 5-7 steps
- [ ] Images appear on first, last, and 1-2 middle steps ONLY
- [ ] All prices match products.json exactly
- [ ] Chat view shows progressive agent messages when switching from Custom Experience
- [ ] Print cheatsheet includes product and AI images
- [ ] Verify with other aesthetics (Ethereal Glow AM, Bold Definition Glam)