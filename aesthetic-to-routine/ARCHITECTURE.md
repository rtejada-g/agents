# Aesthetic to Routine - Multi-Agent Architecture

## Overview

This demo showcases advanced agentic AI capabilities for ELC's executive presentation, demonstrating:

1. **Multi-Agent Collaboration**: Specialized agents working together
2. **Custom Experience UI**: Premium, interactive frontend
3. **Hybrid Data Architecture**: Static frontend data + dynamic agent_state backend
4. **Executive-Grade UX**: Dual views for presentation flexibility

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (agent-stage-ui)                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ AestheticToRoutineView (Custom Experience)            │  │
│  │  - Static aesthetic carousel (embedded data)          │  │
│  │  - Quiz modal                                         │  │
│  │  - Routine result display                            │  │
│  │  - Reads agent_state from messages                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ▲                                    │
│                          │ agent_state                        │
│                          │ (via messages)                     │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────┐
│                  BACKEND (aesthetic-to-routine/)             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Orchestrator Agent                                     │ │
│  │  - Coordinates workflow                                │ │
│  │  - Delegates to specialists                           │ │
│  │  - Assembles final routine with agent_state           │ │
│  └────────────────────────────────────────────────────────┘ │
│           │                               │                   │
│           ▼                               ▼                   │
│  ┌──────────────────────┐   ┌──────────────────────────┐    │
│  │ Product Specialist    │   │ Brand Voice Agent        │    │
│  │ - search_products     │   │ - generate_product_copy  │    │
│  │ - Catalog expertise   │   │ - Messaging expertise    │    │
│  └──────────────────────┘   └──────────────────────────┘    │
│           │                               │                   │
│           ▼                               ▼                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Data Layer (JSON files)                                │ │
│  │ - products.json (ELC catalog)                          │ │
│  │ - aesthetic_mappings.json (recipes)                    │ │
│  │ - aesthetics.json (metadata only)                      │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## Data Flow Architecture

### Static Data (Frontend)
**Location**: `agent-stage-ui/src/components/CustomExperience/demos/aesthetic-to-routine/data/`

- `aesthetics.ts` - Aesthetic catalog for instant carousel display
- `quiz-config.ts` - Quiz configuration

**Why Frontend?**
- Instant load (no backend dependency)
- Static reference data
- Better demo UX

### Dynamic Data (Backend via agent_state)
**Mechanism**: `EventActions.agent_state.custom_experience_data`

```python
# Backend sends routine via agent_state
yield Event(
    author="Orchestrator",
    content=types.Content(parts=[...]),  # User-friendly summary
    actions=EventActions(
        agent_state={
            "custom_experience_data": {
                "type": "routine_result",
                "aesthetic_id": "ethereal-glow",
                "aesthetic_name": "Ethereal Glow",
                "steps": [
                    {
                        "step_number": 1,
                        "category": "Cleanser",
                        "product": {
                            "name": "Advanced Night Cleansing Foam",
                            "brand": "Estée Lauder",
                            "description": "...",
                            "why": "Essential cleanser, formulated for dry skin..."
                        }
                    },
                    # ... more steps
                ],
                "quiz_responses": {"skin_type": "Dry", ...}
            }
        }
    )
)
```

```typescript
// Frontend reads from messages
messages.forEach(msg => {
    if (msg.actions?.agentState?.custom_experience_data) {
        const data = msg.actions.agentState.custom_experience_data;
        if (data.type === 'routine_result') {
            setRoutineResult(data);
        }
    }
});
```

**Why agent_state?**
- ✅ Synchronous with message flow
- ✅ No artifact timing issues
- ✅ Purpose-built for agent metadata
- ✅ Chat/custom-experience views stay in sync

## Multi-Agent Workflow

### Step 1: User Greeting
```
User: "Hello"
→ Orchestrator: Warm welcome (aesthetics already visible)
```

### Step 2: Quiz Submission
```
User: {"aesthetic_id": "ethereal-glow", "quiz_responses": {...}}
→ Orchestrator: "Creating your personalized routine..."
```

### Step 3: Product Selection (Internal)
```
Orchestrator → Product Specialist: 
    Input: {"aesthetic_id": "...", "quiz_responses": {...}}
    Tool: search_products(aesthetic_id, skin_type, main_concern)
    Output: List of matched products with recipe context
```

### Step 4: Brand Messaging (Internal)
```
Orchestrator → Brand Voice Agent:
    Input: {aesthetic, preferences, products}
    Tool: generate_product_copy(aesthetic_id, skin_type, concern, products)
    Output: Enhanced products with polished "why_this" copy
```

### Step 5: Final Assembly
```
Orchestrator:
    - Assembles routine_steps from enhanced products
    - Creates agent_state with custom_experience_data
    - Yields final event with:
        * User-friendly summary message
        * Complete routine data in agent_state
```

## Demo Value Proposition

### For Executives (CTO)
1. **Multi-Brand Personalization**: Products from across ELC portfolio
2. **AI Agent Collaboration**: Specialized agents working together
3. **Premium UX**: Executive-grade interface
4. **Scalability**: Architecture extends to other use cases

### For Technical Stakeholders
1. **Multi-Agent Pattern**: Demonstrates orchestration + specialization
2. **Hybrid Architecture**: Smart data placement (static vs dynamic)
3. **Custom Experience Framework**: Reusable for other demos
4. **Clean State Management**: agent_state eliminates timing issues

## Key Technical Decisions

### Why Multi-Agent?
- **Separation of Concerns**: Product expertise vs brand voice
- **Better Quality**: Specialized prompts yield better results
- **Demo Value**: Shows agent collaboration patterns
- **Extensibility**: Easy to add more specialists (e.g., pricing agent)

### Why agent_state vs Artifacts?
- **Artifacts**: For file-like content (PDFs, images)
- **agent_state**: For structured metadata and UI state
- **Benefit**: Synchronous, reliable, no async timing issues

### Why Static Frontend Data?
- **Aesthetics**: Fixed reference data, instant load
- **Quiz**: Configuration doesn't change
- **Alternative**: Could use agent_state on greeting, but static is faster

## Testing Checklist

- [ ] Greeting returns welcome message
- [ ] Quiz submission triggers routine generation
- [ ] Product Specialist finds correct products
- [ ] Brand Voice Agent generates personalized copy
- [ ] Orchestrator assembles complete routine
- [ ] agent_state contains all required fields
- [ ] Custom Experience UI renders correctly
- [ ] Toggle between chat/custom views works
- [ ] All 7 aesthetics selectable
- [ ] Different quiz responses produce varied copy

## Future Enhancements

1. **Pricing Specialist Agent**: Dynamic pricing/promotions
2. **Image Generation**: AI-generated application images
3. **Multi-Language**: Localization agent
4. **Inventory Integration**: Real-time availability checking
5. **A/B Testing**: Multiple Brand Voice variants