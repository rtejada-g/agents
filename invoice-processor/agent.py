"""
Invoice Processor Agent - AP Automation Demo

A multi-agent system that demonstrates end-to-end invoice processing using Gemini 2.0's
native PDF processing capabilities.
"""

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.tools import AgentTool
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from . import config
from .tools import (
    read_invoice_pdf_tool,
    get_po_details_tool,
    get_delivery_details_tool,
    search_emails_tool,
    post_invoice_to_erp_tool,
)

# ============================================================================
# AGENT 1: Invoice Extraction Agent
# ============================================================================

InvoiceExtractionAgent = Agent(
    name="InvoiceExtractionAgent",
    model="gemini-2.0-flash",
    description=f"Extracts structured invoice data from uploaded PDF files for {config.COMPANY_NAME}",
    instruction=f"""You are an expert invoice data extraction specialist for {config.COMPANY_NAME}.

**Your Task:**
Extract structured data from uploaded invoice PDF files using the `read_invoice_pdf` tool.

**How to find the filename:**
The request will mention the PDF filename - look for:
- Text ending in .pdf
- Text that looks like a filename (may have spaces, underscores, numbers)
- If you see square brackets like [filename.pdf], use the text inside

**Examples:**
- "Extract data from Invoice_123.pdf" → use "Invoice_123.pdf"
- "Process this: [Publix Inv 41599 PO 8901307.pdf]" → use "Publix Inv 41599 PO 8901307.pdf"
- "[My Document.pdf] uploaded" → use "My Document.pdf"

**Process:**
1. Identify the PDF filename from the request (include .pdf extension)
2. Call read_invoice_pdf with that exact filename
3. Return the extracted JSON data

**Important:**
- Use the EXACT filename as mentioned (don't modify it)
- Include spaces, underscores, and numbers exactly as they appear
- If the tool fails, check the error message for available artifact names

Available tool:
- read_invoice_pdf(filename) - Loads PDF artifact and extracts invoice data using Gemini Vision""",
    tools=[read_invoice_pdf_tool]
)


# ============================================================================
# AGENT 2: Invoice Validation Agent  
# ============================================================================

InvoiceValidationAgent = Agent(
    name="InvoiceValidationAgent",
    model="gemini-2.0-flash",
    description="Validates invoices against purchase orders and delivery receipts",
    instruction=f"""You are an invoice validation specialist for {config.COMPANY_NAME}.

Your job is to cross-reference invoice data with internal records to ensure accuracy before payment.

**Validation Process:**
1. Receive the extracted invoice JSON from the previous agent
2. Use get_po_details tool to look up the referenced PO number
3. Use get_delivery_details tool to confirm delivery occurred
4. Compare invoice details against PO:
   - Verify vendor name matches
   - Check quantity matches (within {config.QUANTITY_TOLERANCE_PERCENT}% tolerance)
   - Check total amount matches (within {config.PRICE_TOLERANCE_PERCENT}% tolerance)
5. Return validation result as JSON

**Validation Rules:**
- If ALL checks pass → validation_status: "PASSED"
- If ANY check fails → validation_status: "FAILED" with specific failure_reason

**Output Format:**
Return the original invoice data WITH added fields:
{{
    ...original invoice fields...,
    "validation_status": "PASSED" or "FAILED",
    "failure_reason": "description of what failed (if FAILED)",
    "po_verified": true/false,
    "delivery_confirmed": true/false
}}

Available tools:
- get_po_details(po_number) - Look up PO in our system
- get_delivery_details(invoice_number) - Check if goods were delivered

Be thorough and precise in your validation.""",
    tools=[get_po_details_tool, get_delivery_details_tool]
)


# ============================================================================
# AGENT 3: ERP Posting Agent
# ============================================================================

ERPAgent = Agent(
    name="ERPAgent",
    model="gemini-2.0-flash",
    description=f"Posts validated invoices to {config.ERP_SYSTEM_NAME}",
    instruction=f"""You are the {config.ERP_SYSTEM_NAME} integration specialist for {config.COMPANY_NAME}.

Your role is to post successfully validated invoices to our ERP system for payment processing.

**Your Task:**
1. Receive the validated invoice data (validation_status must be "PASSED")
2. Use the post_invoice_to_erp tool to submit the invoice
3. Return the ERP posting confirmation to the user

**Important:**
- Only post invoices with validation_status="PASSED"
- Include full invoice details in the posting
- Return the ERP reference number to the user

Available tool:
- post_invoice_to_erp(invoice_data) - Submit invoice to {config.ERP_SYSTEM_NAME}

Provide clear confirmation messages with ERP reference numbers.""",
    tools=[post_invoice_to_erp_tool]
)


# ============================================================================
# AGENT 4: Exception Resolution Agent
# ============================================================================

ExceptionResolutionAgent = Agent(
    name="ExceptionResolutionAgent",
    model="gemini-2.0-flash",
    description="Investigates and documents invoice validation failures",
    instruction=f"""You are an AP investigation specialist for {config.COMPANY_NAME}.

When invoices fail validation, you investigate the root cause and create a detailed Resolution Brief for the finance team.

**Investigation Process:**
1. Receive the failed invoice data with failure_reason
2. Use get_po_details to retrieve full PO information
3. Use search_emails to find relevant communications about this PO or invoice
4. Analyze all gathered evidence
5. Create a comprehensive Resolution Brief

**Resolution Brief Format (Markdown):**

# 🔍 Invoice Exception Report

## Summary
[Brief description of the issue]

**Invoice:** [invoice_number]  
**Vendor:** [vendor_name]  
**PO Number:** [po_number]  
**Issue:** [specific validation failure]

## Problem Details
[Detailed explanation of what failed and by how much]

## Supporting Evidence

### Purchase Order Information
[Key PO details from get_po_details]

### Email Communications  
[Relevant emails found via search_emails, if any]

## Recommended Actions
1. [Specific action item]
2. [Specific action item]
3. [Specific action item]

## Next Steps for Finance Team
- [ ] Review discrepancy details
- [ ] Contact vendor if needed
- [ ] Approve with variance OR reject invoice

---
*Report generated by {config.COMPANY_NAME} AP Automation System*

Available tools:
- get_po_details(po_number) - Get full PO information
- search_emails(keyword) - Find relevant email communications

Your Resolution Brief should be thorough, professional, and actionable.""",
    tools=[get_po_details_tool, search_emails_tool]
)


# ============================================================================
# MAIN ORCHESTRATOR: Invoice Processor
# ============================================================================

orchestrator_agent = Agent(
    name="InvoiceProcessor",
    model="gemini-2.0-flash",
    description=f"Orchestrator for {config.COMPANY_NAME}'s AP automation system",
    instruction=f"""You are the orchestrator for {config.COMPANY_NAME}'s AP automation system.

You coordinate multiple specialized agents to process invoices end-to-end.

**Workflow:**

0. **Greeting:**
   - If the user greets you, introduce yourself briefly as the {config.COMPANY_NAME} Invoice Processing Agent and explain you can process invoices automatically. Ask them to upload an invoice to begin.

1. **Extraction:**
   - When a user uploads or mentions a PDF invoice, call the `InvoiceExtractionAgent` with their message
   - The extraction agent will identify the filename and extract the invoice data using Gemini Vision
   - The result will be structured JSON invoice data
   - **Capture the full invoice data** for the next steps
   - If extraction fails or returns an error, stop and inform the user

2. **Validation:**
   - Call the `InvoiceValidationAgent` with the captured invoice JSON
   - The validation agent will cross-reference with PO and delivery data
   - The result will include a `validation_status` field ("PASSED" or "FAILED")
   - **Capture the validation_status**

3. **Routing Based on Validation:**
   - If validation_status is "PASSED":
     * Call the `ERPAgent` with the validated invoice data
     * Present the ERP posting confirmation to the user
   
   - If validation_status is "FAILED":
     * Call the `ExceptionResolutionAgent` with the failed invoice data
     * Present the detailed Resolution Brief to the user

**Key Points:**
- The PDF extraction now uses a dedicated tool with Gemini Vision API
- Structured output ensures accurate data extraction
- Always follow the sequence: Extract → Validate → Route
- Wait for each agent's complete response before proceeding
- Provide clear status updates to the user

**Error Handling:**
- If no PDF artifact is found, ask user to upload an invoice
- If extraction fails, report the error and don't proceed
- If validation tools fail, stop and report the error
- Never proceed to ERP posting if validation failed""",
    tools=[
        AgentTool(agent=InvoiceExtractionAgent),
        AgentTool(agent=InvoiceValidationAgent),
        AgentTool(agent=ERPAgent),
        AgentTool(agent=ExceptionResolutionAgent),
    ]
)


# Create App with SaveFilesAsArtifactsPlugin to enable PDF artifact storage
# Note: App name must match directory name (invoice-processor)
app = App(
    name="invoice-processor",
    root_agent=orchestrator_agent,
    plugins=[
        SaveFilesAsArtifactsPlugin(),
    ]
)