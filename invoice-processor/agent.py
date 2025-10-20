"""
Invoice Processor Agent - AP Automation Demo

A multi-agent system that demonstrates end-to-end invoice processing using Gemini 2.0's
native PDF processing capabilities.
"""

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.apps import App
from google.adk.events import Event, EventActions
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from google.genai import types
from pydantic import Field, ConfigDict
from typing import AsyncGenerator, Any, List
from typing_extensions import override
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

invoice_extraction_agent = LlmAgent(
    name="InvoiceExtractionAgent",
    model="gemini-2.0-flash",
    description=f"Extracts structured invoice data from uploaded PDF files for {config.COMPANY_NAME}",
    instruction=f"""You are an expert invoice data extraction specialist for {config.COMPANY_NAME}.

**Your Task:**
Extract structured data from uploaded invoice PDF files and present a clean summary.

**Process:**
1. Identify the PDF filename from the request (look for .pdf files, text in brackets, etc.)
2. Call read_invoice_pdf with that exact filename
3. The tool will return JSON with invoice data
4. Present a brief, executive-friendly summary to the user

**Output Format (for user):**
📋 **Invoice Extracted**

**Invoice #:** [invoice_number]
**Vendor:** [vendor_name]
**Amount:** $[total_amount]
**PO Reference:** [po_number]
**Date:** [invoice_date]

*Extraction complete. Proceeding to validation...*

**Important:**
- Use EXACT filename as mentioned (don't modify it)
- Keep summary concise (5-6 lines max)
- DO NOT output raw JSON to the user
- The JSON will be automatically saved to state for the next agent

Available tool:
- read_invoice_pdf(filename) - Loads PDF artifact and extracts invoice data using Gemini Vision""",
    tools=[read_invoice_pdf_tool],
    output_key="invoice_data"
)


# ============================================================================
# AGENT 2: Invoice Validation Agent  
# ============================================================================

invoice_validation_agent = LlmAgent(
    name="InvoiceValidationAgent",
    model="gemini-2.0-flash",
    description="Validates invoices against purchase orders and delivery receipts",
    instruction=f"""You are an invoice validation specialist for {config.COMPANY_NAME}.

Your job is to cross-reference invoice data with internal records and present results clearly.

**Validation Process:**
1. Parse the invoice JSON from the request
2. Use get_po_details to look up the PO
3. Use get_delivery_details to confirm delivery
4. Compare invoice vs PO (vendor, quantity within {config.QUANTITY_TOLERANCE_PERCENT}%, amount within {config.PRICE_TOLERANCE_PERCENT}%)
5. Determine validation_status: "PASSED" or "FAILED"
6. Create validation JSON with added fields (validation_status, failure_reason, po_verified, delivery_confirmed)
7. Present user-friendly summary

**Output Format for PASSED:**
✅ **Validation Complete**

**Invoice #:** [invoice_number] **Amount:** $[total_amount]
**Vendor:** [vendor_name]
**PO Match:** ✓ Verified against PO #[po_number]
**Delivery:** ✓ Confirmed

*All checks passed. Ready for ERP posting.*

**Output Format for FAILED:**
⚠️ **Validation Issues Detected**

**Invoice #:** [invoice_number]
**Issue:** [Brief description of failure]
**PO Reference:** [po_number]

*Routing to exception handling for investigation...*

**Important:**
- Present ONLY the summary above (no raw JSON)
- Keep it concise and scannable
- The full JSON with validation_status will be automatically saved to state

Available tools:
- get_po_details(po_number) - Look up PO in our system
- get_delivery_details(invoice_number) - Check if goods were delivered""",
    tools=[get_po_details_tool, get_delivery_details_tool],
    output_key="validation_result"
)


# ============================================================================
# AGENT 3: ERP Posting Agent
# ============================================================================

erp_agent = LlmAgent(
    name="ERPAgent",
    model="gemini-2.0-flash",
    description=f"Posts validated invoices to {config.ERP_SYSTEM_NAME}",
    instruction=f"""You are the {config.ERP_SYSTEM_NAME} integration specialist for {config.COMPANY_NAME}.

Your role is to post validated invoices to ERP and confirm to executives.

**Your Task:**
1. Parse the validated invoice JSON from the request
2. Verify validation_status is "PASSED"
3. Use post_invoice_to_erp tool to submit
4. Present executive-friendly confirmation

**Output Format:**
✅ **Posted to {config.ERP_SYSTEM_NAME}**

**Invoice #:** [invoice_number]
**Vendor:** [vendor_name]
**Amount:** $[total_amount]
**ERP Reference:** [erp_reference_number]

*Invoice successfully queued for payment processing.*

**Important:**
- Only post invoices with validation_status="PASSED"
- Keep message concise (5-6 lines)
- Highlight the ERP reference number
- NO raw JSON in output

Available tool:
- post_invoice_to_erp(invoice_data) - Submit invoice to {config.ERP_SYSTEM_NAME}""",
    tools=[post_invoice_to_erp_tool],
    output_key="erp_result"
)


# ============================================================================
# AGENT 4: Exception Resolution Agent
# ============================================================================

exception_resolution_agent = LlmAgent(
    name="ExceptionResolutionAgent",
    model="gemini-2.0-flash",
    description="Investigates and documents invoice validation failures",
    instruction=f"""You are an AP investigation specialist for {config.COMPANY_NAME}.

When invoices fail validation, you investigate and create an executive-friendly Resolution Brief.

**Investigation Process:**
1. Parse the failed invoice JSON
2. Use get_po_details for PO information
3. Use search_emails to find relevant communications
4. Synthesize findings into clear, actionable brief

**Resolution Brief Format (Markdown):**

# 🔍 Invoice Exception Report

## Summary
[1-2 sentence issue description]

**Invoice #:** [invoice_number] | **Vendor:** [vendor_name] | **Amount:** $[total_amount]
**PO Reference:** [po_number]
**Issue Type:** [specific validation failure - e.g., "Price Mismatch" or "Missing PO"]

## Problem Analysis
[Clear explanation of the discrepancy with specific numbers]

**Invoice Shows:** [specific value]
**PO Shows:** [specific value]
**Variance:** [difference and %]

## Investigation Findings

**Purchase Order Status:**
[Key PO details - vendor, amount, status]

**Email Communications:**
[Summary of relevant emails found, if any. If none: "No email correspondence found."]

## Recommended Actions
1. [Specific, actionable step]
2. [Specific, actionable step]
3. [Specific, actionable step]

## Next Steps
- [ ] Review variance details
- [ ] Contact vendor if needed
- [ ] Approve with adjustment OR reject

---
*Report generated by {config.COMPANY_NAME} AP Automation*

**Important:**
- Keep brief scannable and concise
- Use bullet points and clear formatting
- Focus on facts and next steps
- No raw JSON or technical jargon

Available tools:
- get_po_details(po_number) - Get full PO information
- search_emails(keyword) - Find relevant email communications""",
    tools=[get_po_details_tool, search_emails_tool],
    output_key="resolution_brief"
)


# ============================================================================
# MAIN ORCHESTRATOR: Invoice Processor
# ============================================================================

class InvoiceProcessor(BaseAgent):
    """
    Custom orchestrator agent that executes invoice processing workflow.
    Routes based on validation status: PASSED → ERP, FAILED → Exception Resolution
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    extraction_agent: LlmAgent = Field(description="Invoice extraction agent")
    validation_agent: LlmAgent = Field(description="Invoice validation agent")
    erp_agent: LlmAgent = Field(description="ERP posting agent")
    exception_agent: LlmAgent = Field(description="Exception resolution agent")
    
    def __init__(
        self,
        name: str,
        extraction_agent: LlmAgent,
        validation_agent: LlmAgent,
        erp_agent: LlmAgent,
        exception_agent: LlmAgent,
    ):
        super().__init__(
            name=name,
            extraction_agent=extraction_agent,
            validation_agent=validation_agent,
            erp_agent=erp_agent,
            exception_agent=exception_agent,
            description=f"Orchestrator for {config.COMPANY_NAME}'s AP automation system",
            sub_agents=[extraction_agent, validation_agent, erp_agent, exception_agent],
        )
    
    @override
    async def _run_async_impl(self, ctx: Any) -> AsyncGenerator[Event, None]:
        """
        Executes the invoice processing workflow:
        1. Extract invoice data from PDF
        2. Validate against PO and delivery records
        3. Route based on validation: PASSED → ERP, FAILED → Exception Resolution
        """
        # Clear session state at start
        ctx.session.state["invoice_data"] = None
        ctx.session.state["validation_result"] = None
        ctx.session.state["validation_status"] = None
        
        # Get user query (handle file uploads where text might be None)
        user_query = ""
        if ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                if part.text:
                    user_query = part.text
                    break
        
        user_query_lower = user_query.lower() if user_query else ""
        
        # Handle greetings
        if user_query and ("hello" in user_query_lower or "hi" in user_query_lower):
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"Hello! I'm the {config.COMPANY_NAME} Invoice Processing Agent. I can automatically process invoices by extracting data, validating against purchase orders, and posting to {config.ERP_SYSTEM_NAME}. Please upload an invoice PDF to begin.")])
            )
            return
        
        # Step 1: Extract invoice data
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="📄 Extracting invoice data...")])
        )
        
        async for event in self.extraction_agent.run_async(ctx):
            yield event
        
        # Get extracted invoice data from state
        invoice_data = ctx.session.state.get("invoice_data")
        if not invoice_data:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="❌ Failed to extract invoice data. Please check the PDF and try again.")])
            )
            return
        
        # Step 2: Validate invoice
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="✓ Extraction complete. Validating invoice...")])
        )
        
        # Create context with invoice data for validation
        validation_context = ctx.copy(
            update={
                "user_content": types.Content(
                    parts=[types.Part(text=invoice_data)]
                )
            }
        )
        
        async for event in self.validation_agent.run_async(validation_context):
            yield event
        
        # Get validation result from state
        validation_result = ctx.session.state.get("validation_result")
        if not validation_result:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="❌ Validation failed. Could not process invoice.")])
            )
            return
        
        # DEBUG: Print what we got from state
        print(f"\n[ORCHESTRATOR] validation_result from state:")
        print(f"[ORCHESTRATOR] Type: {type(validation_result)}")
        print(f"[ORCHESTRATOR] Content (first 500 chars): {str(validation_result)[:500]}")
        
        # Parse validation status from JSON
        import json
        import re
        validation_status = "FAILED"  # Default
        
        try:
            # Try direct JSON parsing
            validation_data = json.loads(validation_result)
            validation_status = validation_data.get("validation_status", "FAILED")
            print(f"[ORCHESTRATOR] Parsed JSON directly, validation_status={validation_status}")
        except json.JSONDecodeError as e:
            print(f"[ORCHESTRATOR] JSON parse failed: {e}")
            # If not valid JSON, try to extract JSON from text
            json_match = re.search(r'\{[^{}]*"validation_status"[^{}]*\}', validation_result, re.DOTALL)
            if json_match:
                try:
                    validation_data = json.loads(json_match.group(0))
                    validation_status = validation_data.get("validation_status", "FAILED")
                    print(f"[ORCHESTRATOR] Extracted JSON from text, validation_status={validation_status}")
                except Exception as e2:
                    print(f"[ORCHESTRATOR] Failed to parse extracted JSON: {e2}")
            
            # Fallback: Look for the pattern in text
            if validation_status == "FAILED":
                status_match = re.search(r'"validation_status":\s*"(PASSED|FAILED)"', validation_result)
                if status_match:
                    validation_status = status_match.group(1)
                    print(f"[ORCHESTRATOR] Found status via regex: {validation_status}")
                else:
                    # Final fallback: check for success indicators in text
                    if "✅" in validation_result or "All checks passed" in validation_result or "Validation Complete" in validation_result:
                        validation_status = "PASSED"
                        print(f"[ORCHESTRATOR] Detected PASSED from success indicators in text")
                    else:
                        print(f"[ORCHESTRATOR] No validation_status found, defaulting to: {validation_status}")
        
        print(f"[ORCHESTRATOR] Final validation_status={validation_status}")
        
        # Step 3: Route based on validation status
        if validation_status == "PASSED":
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"✓ Validation passed. Posting to {config.ERP_SYSTEM_NAME}...")])
            )
            
            # Post to ERP
            erp_context = ctx.copy(
                update={
                    "user_content": types.Content(
                        parts=[types.Part(text=validation_result)]
                    )
                }
            )
            
            async for event in self.erp_agent.run_async(erp_context):
                yield event
            
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="✅ Invoice processing complete.")])
            )
        else:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="⚠️ Validation failed. Investigating exception...")])
            )
            
            # Investigate exception
            exception_context = ctx.copy(
                update={
                    "user_content": types.Content(
                        parts=[types.Part(text=validation_result)]
                    )
                }
            )
            
            async for event in self.exception_agent.run_async(exception_context):
                yield event
            
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="📋 Exception investigation complete. Review the Resolution Brief above.")])
            )


# Initialize the orchestrator
orchestrator_agent = InvoiceProcessor(
    name="InvoiceProcessor",
    extraction_agent=invoice_extraction_agent,
    validation_agent=invoice_validation_agent,
    erp_agent=erp_agent,
    exception_agent=exception_resolution_agent,
)


# Create App with SaveFilesAsArtifactsPlugin to enable PDF artifact storage
# Note: App name must match directory name (invoice-processor)
root_agent = orchestrator_agent

app = App(
    name="invoice-processor",
    root_agent=root_agent,
    plugins=[
        SaveFilesAsArtifactsPlugin(),
    ]
)