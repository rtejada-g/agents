# Aesthetic to Routine Agent

A custom demo agent for Estée Lauder Companies (ELC) that creates personalized beauty routines based on trending aesthetics.

## Overview

This agent demonstrates the "Art of the Possible" for agentic AI in the beauty industry by:
- Presenting trending aesthetic options in a premium, carousel-style UI
- Gathering personalization preferences through a streamlined quiz
- Generating multi-brand product routines using intelligent product matching
- Creating a cart customization experience for end consumers

## Architecture

### Multi-Agent System
- **AestheticCatalogAgent**: Loads and presents trending aesthetics
- **QuizAgent**: Gathers user preferences (skin type, tone, concerns)
- **RoutineGeneratorAgent**: Searches products and builds personalized routines
- **Main Orchestrator**: Manages workflow and state transitions

### Data-Driven Design
- Configuration-based data pivoting (default vs. ELC datasets)
- Recipe system maps aesthetics to product categories
- Rich sensory descriptors for LLM-powered recommendations

## Quick Start

### Prerequisites
- Python 3.9+
- ADK Python installed (from parent `adk-python/` directory)
- Agent Stage UI running (from parent `agent-stage/` directory)

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env to use 'default' or 'elc' dataset
   ```

3. **Add product images:**
   ```bash
   # Place 23 product images + 7 aesthetic images + 7 brand logos
   # in data/default/images/ (see images/README.md for exact list)
   ```

### Running the Agent

From the parent `agents/` directory:

```bash
adk serve aesthetic-to-routine
```

Or from this directory:

```bash
adk serve .
```

The agent will be available at `http://localhost:8000`

### Testing with Agent Stage

1. Start the agent (as above)
2. Navigate to Agent Stage UI: `http://localhost:5173`
3. Select "aesthetic-to-routine" from the agents dropdown
4. Start a new session
5. The custom experience UI will automatically load

## Data Configuration

### Switching Between Datasets

Edit `.env` to switch data sources:

```bash
# Use synthetic test data
BRAND_DATA_SET=default

# Use real ELC data (requires manual data population)
BRAND_DATA_SET=elc
```

### Dataset Structure

```
data/
├── default/                       # Real ELC product data
│   ├── aesthetics.json           # 7 trending aesthetics
│   ├── products.json             # 23 real ELC products
│   ├── quiz_config.json          # 3 personalization questions
│   ├── aesthetic_mappings.json   # Recipe system
│   └── images/
│       ├── aesthetics/           # 7 aesthetic mood images
│       ├── products/             # 23 product photos
│       ├── applications/         # Product application shots (optional)
│       └── brands/               # 7 brand logos
└── elc/                          # Alternative ELC dataset (optional)
    └── (same structure as default)
```

## Image Requirements

### Real ELC Products (Default Dataset)

The default dataset now contains **23 real ELC products** across 7 brands:
- **Estée Lauder** (4 products) - Advanced Night Repair, Double Wear, Pure Color Envy, Pure Color Desire
- **Clinique** (5 products) - Moisture Surge, Take The Day Off, High Impact Mascara, Dramatically Different, Cheek Pop
- **La Mer** (3 products) - Crème de la Mer, The Treatment Lotion, Lifting and Firming Mask
- **MAC** (4 products) - Ruby Woo, Studio Fix Fluid, Prep + Prime Fix+, Smoked Purple
- **Bobbi Brown** (4 products) - Vitamin Enriched Face Base, Long-Wear Gel Eyeliner, Shimmer Brick, Crushed Lip Color
- **Tom Ford** (2 products) - Eye Color Quad, Black Orchid, Shade and Illuminate
- **Jo Malone London** (1 product) - English Pear & Freesia Cologne

See [`data/default/images/README.md`](data/default/images/README.md:1) for the complete list of required images with exact product names and SKUs.

**Quick Summary:**
- 7 aesthetic images (1200x800px JPEG)
- 23 product images (800x800px JPEG)
- 7 brand logos (200x200px PNG)

**Application Images** (OPTIONAL for v1)
- `applications/application_[SKU]_[category].jpg`
- Can use placeholders initially

## Custom Experience UI

This agent is designed for a **pure custom experience** (no chat visible):

1. **Landing**: Carousel of trending aesthetics
2. **Quiz Modal**: 3 optional personalization questions
3. **Routine Generation**: Products appear one-by-one as generated
4. **Cart Customization**: Finalize which products to purchase

### Artifact Types

The agent emits these artifact types:

- `aesthetics_catalog`: Available aesthetics (triggers carousel)
- `quiz_config`: Quiz questions (triggers modal)
- `routine_step`: Individual routine step (appears incrementally)
- `routine_complete`: Final summary (enables cart customization)

## State Flow

```
Session Start
    ↓
Show Aesthetics Catalog (catalog_agent)
    ↓
User selects aesthetic
    ↓
Show Quiz (quiz_agent)
    ↓
User submits answers (JSON)
    ↓
Generate Routine (routine_agent)
    ↓
    ├─ Search products
    ├─ Generate step 1 (artifact)
    ├─ Generate step 2 (artifact)
    ├─ Generate step 3 (artifact)
    └─ Complete routine (artifact)
    ↓
Cart Customization UI
```

## Customization

### Adding New Aesthetics

Edit `data/[dataset]/aesthetics.json`:

```json
{
  "id": "new-aesthetic",
  "title": "New Aesthetic",
  "subtitle": "Trending: X, Y, Z",
  "trending_terms": ["x", "y", "z"],
  "image_filename": "aesthetic_new.jpg",
  "popularity_score": 90
}
```

### Modifying Recipe System

Edit `data/[dataset]/aesthetic_mappings.json` to change which product categories appear for each aesthetic:

```json
{
  "aesthetic_id": "ethereal-glow",
  "base_recipe": {
    "steps": [
      { "category": "base", "sub_category": "serum", "priority": 1 },
      // ... add more steps
    ]
  }
}
```

### Adjusting Routine Length

Edit `.env`:

```bash
MAX_ROUTINE_STEPS=5  # Maximum products in a routine
MIN_ROUTINE_STEPS=3  # Minimum products in a routine
```

## Technical Details

### Tools Available

- `get_aesthetics_catalog()`: Loads aesthetic options
- `get_quiz_config(aesthetic_id)`: Loads quiz for selected aesthetic
- `search_products(aesthetic_id, skin_type, concerns, tone)`: Finds matching products
- `generate_routine_step(step_number, product, aesthetic_id)`: Creates step artifact
- `complete_routine(aesthetic_id, products)`: Finalizes routine

### Session State

The orchestrator tracks:
- `selected_aesthetic`: User's aesthetic choice
- `quiz_answers`: User's quiz responses

### Message Formats

**Aesthetic Selection** (from UI):
```
I want ethereal-glow aesthetic
```

**Quiz Submission** (from UI):
```json
{
  "aesthetic_id": "ethereal-glow",
  "skin_type": "combination",
  "skin_tone": "#E8B896",
  "concerns": ["hydration", "brightening"]
}
```

## Demo Presentation Tips

### For Executives
1. **Start clean**: Show the aesthetic carousel first
2. **Emphasize personalization**: Walk through quiz quickly
3. **Show incremental generation**: Watch steps appear one-by-one
4. **Highlight multi-brand**: Point out Clinique, Estée Lauder, MAC, etc.
5. **Toggle to technical view**: Show agent graph, traces, artifacts

### For Technical Deep-Dive
1. Show artifact-driven UI architecture
2. Demonstrate recipe system and product matching logic
3. Explain state management between UI and backend
4. Show how data pivoting works (default → elc)

## Troubleshooting

### Agent won't start
- Ensure ADK Python is installed: `pip install -e ../adk-python`
- Check Python version: `python --version` (need 3.9+)
- Verify environment variables in `.env`

### Images not displaying
- Check file paths match exactly (case-sensitive)
- Ensure images are in correct subdirectory
- Verify image format (JPG for photos, PNG for logos)

### Products not matching aesthetic
- Review `aesthetic_mappings.json` recipe for that aesthetic
- Check product categories in `products.json`
- Ensure mapping categories exist in product catalog

## Next Steps

### For Production
1. Populate `data/elc/` with real ELC product catalog
2. Add 100+ aesthetics from lookbook research
3. Integrate with real product API/database
4. Add authentication and user profiles
5. Implement real cart integration with e-commerce platform

### Future Enhancements
- A/B testing different quiz questions
- Personalized aesthetic recommendations based on history
- Social sharing of routines
- Tutorial videos for each product
- Virtual try-on integration

## License

Proprietary - For ELC demonstration purposes only.