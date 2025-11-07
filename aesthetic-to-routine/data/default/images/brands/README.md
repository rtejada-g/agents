# Brand Logos

This directory contains brand logos for ELC portfolio brands.

## File Naming Convention

- `brand_estee_lauder.png`
- `brand_clinique.png`
- `brand_la_mer.png`
- `brand_mac.png`
- `brand_bobbi_brown.png`
- `brand_tom_ford.png`
- `brand_jo_malone.png`

## Format Requirements

- **Format**: PNG with transparency
- **Recommended size**: 200px wide (height proportional)
- **Background**: Transparent
- **Color**: Brand's official logo colors

## Usage

These logos are served as artifacts to the frontend, matching the pattern used in trend-to-market-team agent.

The backend code automatically:
1. Converts brand name to slug (e.g., "Estée Lauder" → "estee-lauder")
2. Appends "-logo.png"
3. Loads from this directory
4. Saves as artifact for frontend display