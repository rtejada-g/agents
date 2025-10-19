# Invoice Processor - Data Setup Guide

This document explains how to set up customer-specific data for the Invoice Processor agent.

## Overview

The Invoice Processor reads from pre-generated, customer-specific CSV files and email archives. These files must be created **before** running the agent and placed in a designated customer data directory.

## Directory Structure

```
agents/invoice-processor/
├── data/
│   ├── default/              # Default dataset
│   │   ├── purchase_orders.csv
│   │   ├── delivery_receipts.csv
│   │   └── internal_emails.txt
│   ├── customerA/            # Customer A's dataset
│   │   ├── purchase_orders.csv
│   │   ├── delivery_receipts.csv
│   │   └── internal_emails.txt
│   └── customerB/            # Customer B's dataset
│       ├── purchase_orders.csv
│       ├── delivery_receipts.csv
│       └── internal_emails.txt
```

## Configuration

Set the customer dataset in `config.py`:

```python
CUSTOMER_DATA_SET = "default"  # or "customerA", "customerB", etc.
```

## Required Files and Schemas

### 1. purchase_orders.csv

Contains purchase order records that invoices will be validated against.

**Required columns:**
```
po_number,vendor_name,item_description,quantity,unit_price,total_amount
```

**Example:**
```csv
po_number,vendor_name,item_description,quantity,unit_price,total_amount
PO-10001,Office Supplies Inc,Premium Copy Paper A4,1000,0.50,500.00
PO-10002,Tech Solutions Ltd,Business Laptops,50,1200.00,60000.00
```

**Field descriptions:**
- `po_number`: Unique PO identifier (must match invoice references)
- `vendor_name`: Name of the supplier
- `item_description`: Description of items ordered
- `quantity`: Number of units ordered
- `unit_price`: Price per unit
- `total_amount`: Total cost (quantity × unit_price)

### 2. delivery_receipts.csv

Contains delivery confirmation records linked to invoices.

**Required columns:**
```
invoice_number,po_number,status,signed_by,delivery_date
```

**Example:**
```csv
invoice_number,po_number,status,signed_by,delivery_date
INV-101,PO-10001,DELIVERED,John Smith,2025-01-15
INV-102,PO-10002,DELIVERED,Sarah Johnson,2025-01-18
```

**Field descriptions:**
- `invoice_number`: Invoice ID (must match uploaded PDF)
- `po_number`: Related purchase order (must exist in purchase_orders.csv)
- `status`: Delivery status (typically "DELIVERED")
- `signed_by`: Person who signed for delivery
- `delivery_date`: Date of delivery (YYYY-MM-DD format)

### 3. internal_emails.txt

Contains email communications about orders and invoices.

**Format:**
Plain text file with emails separated by `---` delimiters.

**Example:**
```
From: vendor.relations@supplier.com
To: purchasing@company.com
Date: 2025-01-12
Subject: RE: PO #10001 - Price Adjustment Notice
---
Dear Team,

Due to supply chain issues, we need to adjust pricing on PO #10001...

Best regards,
Supplier Inc
---

From: purchasing@company.com
To: vendor.relations@supplier.com
Date: 2025-01-13
Subject: RE: PO #10001 - Approved
---
Approved. Please proceed with delivery.
---
```

**Guidelines:**
- Each email should be separated by `---` on its own line
- Include PO numbers and invoice numbers in subject/body for searchability
- Can include approval communications, price adjustments, delivery notices, etc.

## Demo Workflow Scenarios

### Happy Path (Automatic Approval)
1. Invoice matches PO exactly (price, quantity, vendor)
2. Delivery receipt exists and shows "DELIVERED"
3. Agent automatically posts to ERP

**Required data:**
- Matching PO in purchase_orders.csv
- Matching delivery in delivery_receipts.csv
- No discrepancies

### Exception Path (Investigation Required)
1. Invoice has price/quantity mismatch with PO
2. Agent searches emails for context
3. Agent generates Resolution Brief artifact

**Required data:**
- PO with different price/quantity than invoice will show
- Emails containing PO number explaining the variance
- Delivery receipt (optional but recommended)

### Missing PO Path
1. Invoice references non-existent PO
2. Agent cannot validate
3. Agent generates exception report

**Required data:**
- Invoice will reference PO that doesn't exist in purchase_orders.csv
- Optional: Emails about missing PO

## Generating Customer Data

Use a separate prompt/process to:
1. Analyze customer's sample invoice PDFs
2. Extract PO numbers, vendors, amounts
3. Generate matching CSV records
4. Create email context for exception scenarios
5. Save all files to `data/{customer_name}/`

## Testing Your Setup

Before running the agent:

1. ✅ Verify files exist: `data/{CUSTOMER_DATA_SET}/purchase_orders.csv`
2. ✅ Verify files exist: `data/{CUSTOMER_DATA_SET}/delivery_receipts.csv`
3. ✅ Verify files exist: `data/{CUSTOMER_DATA_SET}/internal_emails.txt`
4. ✅ Check CSV headers match required schema
5. ✅ Ensure PO numbers in delivery_receipts.csv exist in purchase_orders.csv
6. ✅ Set `config.CUSTOMER_DATA_SET` to correct folder name

## Troubleshooting

**Error: "File not found"**
- Check that `CUSTOMER_DATA_SET` in config.py matches your folder name
- Verify files exist in `data/{folder_name}/`

**Error: "PO not found"**
- Ensure the PO number in your test invoice exists in purchase_orders.csv
- Check for exact string match (case-sensitive)

**Error: "Failed to load CSV"**
- Verify CSV files have correct headers
- Check for encoding issues (use UTF-8)
- Ensure no extra commas or malformed rows