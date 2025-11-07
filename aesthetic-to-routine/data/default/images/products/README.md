# Product Images

This directory contains product images for the ELC portfolio.

## File Naming Convention

Product images should be named using the SKU ID from `products.json`:
- `EL-ANR-001.jpg` (Estée Lauder Advanced Night Repair)
- `CL-MS-003.jpg` (Clinique Moisture Surge)
- `LM-CDLM-004.jpg` (La Mer Crème de la Mer)
- etc.

## Format Requirements

- **Format**: JPG or JPEG
- **Recommended size**: 800px x 800px (square)
- **Background**: Clean, product-focused
- **Quality**: High resolution for premium presentation

## Usage

These images are served as artifacts to the frontend when products are matched, similar to how trend-to-market-team serves product images.

The backend code automatically:
1. Uses the product SKU to find the image
2. Loads from this directory
3. Saves as artifact for frontend display
4. Falls back to AI-generated personalized image if product image not found

## AI-Generated Images

If a product image doesn't exist in this directory, the system will generate a personalized AI image using:
- User's skin type, tone, and concerns
- Selected aesthetic style
- Product name and brand
- gemini-2.0-flash-exp model

This provides a fallback and personalization layer on top of standard product photography.