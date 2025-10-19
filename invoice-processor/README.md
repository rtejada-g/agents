# Invoice Processor Agent

**Intelligent AP Automation Demo** - End-to-end invoice processing powered by multi-agent AI and Gemini Vision.

## Overview

This agent demonstrates a production-ready AP automation workflow:
- 📄 **Extract** invoice data from PDFs using Gemini Vision
- ✅ **Validate** against purchase orders and delivery receipts  
- 🔀 **Route** to either automatic ERP posting or human investigation
- 📊 **Generate** Resolution Briefs for exceptions

## Quick Start

### 1. Configure Customer

Edit [`config.py`](config.py):
```python
COMPANY_NAME = "Your Company Name"
CUSTOMER_DATA_SET = "default"  # or customer folder name
```

### 2. Prepare Data

Create customer-specific data in `data/{CUSTOMER_DATA_SET}/`:
- `purchase_orders.csv` - PO records for validation
- `delivery_receipts.csv` - Delivery confirmations
- `internal_emails.txt` - Email communications

See [`DATA_SETUP.md`](DATA_SETUP.md) for detailed schema.

### 3. Run the Agent

Start the ADK server:
```bash
source /path/to/.venv/bin/activate
adk api_server --allow_origins='http://localhost:5173' /path/to/agents/
```

Open agent-stage UI and select the invoice processor agent.

### 4. Demo Workflow

**Upload an invoice PDF** and watch the agent:

**Happy Path** (invoice matches PO):
```
Extract → Validate (PASSED) → Post to ERP → ✅ Success Message
```

**Exception Path** (price/quantity mismatch):
```
Extract → Validate (FAILED) → Investigate → 📋 Resolution Brief
```

## Key Features

- **Gemini Vision OCR** - Extracts structured data from any invoice PDF
- **Smart Validation** - Cross-references PO, delivery, and pricing with tolerance rules
- **Dynamic Routing** - Automatic approval or human escalation based on validation
- **Context-Aware Investigation** - Searches emails for variance approvals
- **Customer-Agnostic** - All outputs branded with configured company name

## Architecture

```
InvoiceProcessorApp (Orchestrator)
  ├── InvoiceExtractionAgent    # Gemini Vision extraction
  ├── InvoiceValidationAgent     # PO/delivery validation
  ├── ERPAgent                   # Auto-post to ERP
  └── ExceptionResolutionAgent   # Investigation + Resolution Brief
```

## Configuration

| Setting | Purpose | Default |
|---------|---------|---------|
| `COMPANY_NAME` | Customer branding | "Global Retail Corp" |
| `CUSTOMER_DATA_SET` | Data folder | "default" |
| `ERP_SYSTEM_NAME` | ERP branding | "SAP" |
| `PRICE_TOLERANCE_PERCENT` | Allowed variance | 5% |
| `QUANTITY_TOLERANCE_PERCENT` | Allowed variance | 2% |

## Demo Scenarios

### Scenario 1: Perfect Match
Upload invoice that exactly matches a PO in `purchase_orders.csv`
→ Automatic ERP posting

### Scenario 2: Approved Variance  
Upload invoice with price increase that's documented in `internal_emails.txt`
→ Resolution Brief with email evidence

### Scenario 3: Missing PO
Upload invoice with PO number not in system
→ Resolution Brief recommending vendor contact

## Development

Install dependencies:
```bash
pip install -r requirements.txt
```

Set environment variables (see `.env.example`):
```bash
export GOOGLE_CLOUD_PROJECT=your-project
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

## Files

```
invoice-processor/
├── agent.py              # Main agents and orchestrator
├── tools.py              # Data access and Gemini Vision tools
├── config.py             # Customer configuration
├── requirements.txt      # Python dependencies
├── DATA_SETUP.md        # Data schema documentation
└── data/
    └── {customer}/      # Customer-specific CSVs and emails
```

## Support

For questions or issues, refer to the main agent-stage documentation.