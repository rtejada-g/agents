# Image Assets for Aesthetic to Routine Agent

This directory contains all image assets used by the agent. Place images here according to the structure below.

## Directory Structure

```
images/
├── aesthetics/        # Aesthetic mood/lifestyle images
├── products/          # Product photography
├── applications/      # Product application shots (optional for MVP)
└── brands/           # Brand logos
```

## Required Images

### 1. Aesthetics (7 images)
**Specifications:** 1200x800px, JPEG, lifestyle/mood shots

Place in `aesthetics/`:
- `aesthetic_ethereal_glow.jpg` - Soft, luminous, dewy skin
- `aesthetic_matte_perfection.jpg` - Flawless matte finish
- `aesthetic_korean_glow.jpg` - Glass skin, hydrated glow
- `aesthetic_bold_definition.jpg` - Dramatic eyes, precision
- `aesthetic_fresh_faced.jpg` - Minimal makeup, natural
- `aesthetic_romantic_rose.jpg` - Soft pinks and roses
- `aesthetic_purple_statement.jpg` - Bold purple lips

**Style Guide:**
- Premium, editorial-quality photography
- Show the aesthetic being worn/applied
- Aspirational yet authentic
- Consistent lighting and color grading

### 2. Products (23 images)
**Specifications:** 800x800px, JPEG, clean product shots on white background

Place in `products/`:

**Estée Lauder (4 products)**
- `product_EL-ANR-001.jpg` - Advanced Night Repair Synchronized Multi-Recovery Complex
- `product_EL-DW-002.jpg` - Double Wear Stay-in-Place Makeup
- `product_EL-PCE-012.jpg` - Pure Color Envy Sculpting Lipstick
- `product_EL-PCDML-021.jpg` - Pure Color Desire Matte Lipstick in 414 Prove It

**Clinique (5 products)**
- `product_CL-MS-003.jpg` - Moisture Surge 100H Auto-Replenishing Hydrator
- `product_CL-DML-007.jpg` - Dramatically Different Moisturizing Lotion+
- `product_CL-TDO-011.jpg` - Take The Day Off Cleansing Balm
- `product_CL-HM-018.jpg` - High Impact Mascara
- `product_CL-CNP-023.jpg` - Cheek Pop in Pink Pop

**La Mer (3 products)**
- `product_LM-CDLM-004.jpg` - Crème de la Mer
- `product_LM-TL-013.jpg` - The Treatment Lotion
- `product_LM-LRM-024.jpg` - The Lifting and Firming Mask

**MAC (4 products)**
- `product_MAC-RW-005.jpg` - M·A·Cximal Silky Matte Lipstick in Ruby Woo
- `product_MAC-SFF-008.jpg` - Studio Fix Fluid SPF 15
- `product_MAC-PFP-014.jpg` - Prep + Prime Fix+
- `product_MAC-SP-019.jpg` - M·A·Cximal Silky Matte Lipstick in Smoked Purple

**Bobbi Brown (4 products)**
- `product_BB-VEFB-006.jpg` - Vitamin Enriched Face Base
- `product_BB-LWGE-010.jpg` - Long-Wear Gel Eyeliner
- `product_BB-SBC-015.jpg` - Shimmer Brick Compact
- `product_BB-CB-022.jpg` - Crushed Lip Color in Babe

**Tom Ford (2 products)**
- `product_TF-ECQ-009.jpg` - Eye Color Quad
- `product_TF-BO-017.jpg` - Black Orchid Eau de Parfum
- `product_TF-SL-025.jpg` - Shade and Illuminate

**Jo Malone London (1 product)**
- `product_JML-EPC-016.jpg` - English Pear & Freesia Cologne

**Style Guide:**
- Pure white background (RGB 255, 255, 255)
- Product centered in frame
- Professional studio lighting
- Show product packaging clearly
- High resolution for zoom capability

### 3. Brand Logos (7 images)
**Specifications:** 200x200px, PNG with transparency

Place in `brands/`:
- `brand_estee_lauder.png`
- `brand_clinique.png`
- `brand_la_mer.png`
- `brand_mac.png`
- `brand_bobbi_brown.png`
- `brand_tom_ford.png`
- `brand_jo_malone.png`

**Style Guide:**
- Official brand logos
- Transparent background
- High resolution
- Maintain brand guidelines

### 4. Application Images (OPTIONAL - Phase 2)
**Specifications:** 800x600px, JPEG, product being applied or on skin

Place in `applications/`:
- `application_[SKU]_[category].jpg`

Examples:
- `application_EL-ANR-001_serum.jpg` - Serum on skin/hand
- `application_EL-DW-002_foundation.jpg` - Foundation application
- `application_MAC-RW-005_lip.jpg` - Ruby Woo on lips

**Style Guide:**
- Show product in use
- Diverse skin tones
- Natural lighting
- Close-up detail shots

## Placeholder Strategy

For initial testing without real images:

1. **Use solid color placeholders:**
   - Aesthetics: Use gradient backgrounds matching aesthetic theme
   - Products: Use white background with text overlay showing SKU
   - Brands: Use text-only logos with brand colors

2. **AI-generated placeholders:**
   - Use Midjourney/DALL-E for mood boards
   - Generate product mockups with AI

3. **Stock photography:**
   - Use royalty-free beauty images temporarily
   - Clearly mark as placeholder for legal compliance

## File Naming Convention

All filenames must:
- Use lowercase for brand codes (e.g., `product_EL-`, not `product_el-`)
- Match SKUs exactly from products.json
- Use underscores (not spaces or hyphens) between words
- Use appropriate file extensions (.jpg, .png)

## Optimizations

Before placing images:
- Compress JPEGs to ~200KB max (use TinyJPG or similar)
- Optimize PNGs for web (use TinyPNG)
- Ensure images are already sized correctly (don't rely on CSS scaling)
- Use sRGB color space

## Testing

After adding images:
1. Verify all filenames match JSON exactly (case-sensitive)
2. Check images load in browser dev tools
3. Confirm no 404 errors in network tab
4. Test on different screen resolutions

## ELC Dataset

For the production ELC dataset:
1. Create `../../elc/images/` with same structure
2. Use real ELC product photography
3. Follow ELC brand guidelines strictly
4. Get approval from brand teams before use

## Quick Reference: Products by Aesthetic

**Ethereal Glow:**
- EL-ANR-001 (Serum), CL-MS-003 (Moisturizer), LM-CDLM-004 (Moisturizer)
- BB-SBC-015 (Highlighter), MAC-PFP-014 (Setting Spray)

**Matte Perfection:**
- EL-DW-002 (Foundation), MAC-SFF-008 (Foundation)
- BB-VEFB-006 (Primer)

**Korean Glow:**
- LM-TL-013 (Essence), LM-LRM-024 (Mask)
- CL-MS-003 (Moisturizer), MAC-PFP-014 (Spray)

**Bold Definition:**
- BB-LWGE-010 (Eyeliner), CL-HM-018 (Mascara)
- TF-ECQ-009 (Eyeshadow), MAC-RW-005 (Lipstick)

**Fresh Faced:**
- CL-TDO-011 (Cleanser), CL-DML-007 (Moisturizer)
- BB-VEFB-006 (Primer), BB-CB-022 (Lipstick)

**Romantic Rose:**
- BB-VEFB-006 (Primer), CL-CNP-023 (Blush)
- BB-SBC-015 (Highlighter), EL-PCE-012 or BB-CB-022 (Lipstick)

**Purple Statement:**
- EL-DW-002 or MAC-SFF-008 (Foundation), TF-SL-025 (Contour)
- TF-ECQ-009 (Eyeshadow), MAC-SP-019 or EL-PCDML-021 (Purple Lips)