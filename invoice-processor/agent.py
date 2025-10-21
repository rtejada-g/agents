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
    save_validation_result_tool,
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
Extract structured data from uploaded invoice PDF files and present a clean summary to the user.

**Process:**
1. Call read_invoice_pdf() with NO parameters - it auto-detects the uploaded PDF
2. Check the tool result status field
3. If status is "error", report the error to the user and STOP
4. If status is "success", format the data into the output below

**Output Format for SUCCESS (use exactly this structure):**
📋 **Invoice Extracted**

**Invoice #:** [invoice_number from tool]
**Vendor:** [vendor_name from tool]
**Amount:** $[total_amount from tool]
**PO Reference:** [po_number from tool]
**Date:** [invoice_date from tool]

*Extraction complete.*

**Output Format for ERROR:**
❌ **Extraction Failed**

[error_message from tool]

**Critical Rules:**
- ALWAYS call read_invoice_pdf() with NO parameters (it auto-detects)
- ALWAYS check the status field in the tool result
- If status is "error", output the error message and STOP - do NOT make up data
- If status is "success", use ONLY the data from the tool result
- NEVER invent or hallucinate invoice data

Available tool:
- read_invoice_pdf() - Extracts invoice data from uploaded PDF (auto-detects, call with no parameters)""",
    tools=[read_invoice_pdf_tool],
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
1. Parse the invoice JSON from the request into invoice_data dict
2. Use get_po_details to look up the PO → po_data dict
3. Use get_delivery_details to confirm delivery → delivery_data dict
4. Compare invoice vs PO:
   - Vendor names must match
   - Quantities within {config.QUANTITY_TOLERANCE_PERCENT}% tolerance
   - Amounts within {config.PRICE_TOLERANCE_PERCENT}% tolerance
5. Determine validation_status: "PASSED" or "FAILED"
6. If FAILED, create clear failure_reason (e.g., "Price mismatch: Invoice $15000 vs PO $14000 (7.1% over)")
7. Call save_validation_result tool with:
   - invoice_data (the parsed invoice dict)
   - po_data (the PO lookup result)
   - delivery_data (the delivery lookup result)
   - validation_status ("PASSED" or "FAILED")
   - failure_reason (if FAILED)
8. Present user-friendly summary (format below)

**Output Format for PASSED:**
✅ **Validation Complete**

**Invoice #:** [invoice_number] | **Amount:** $[total_amount]
**Vendor:** [vendor_name]
**PO Match:** ✓ Verified against PO #[po_number]
**Delivery:** ✓ Confirmed

*All checks passed. Ready for ERP posting.*

**Output Format for FAILED:**
⚠️ **Validation Issues Detected**

**Invoice #:** [invoice_number]
**Issue:** [failure_reason - be specific with numbers]
**PO Reference:** [po_number]

*Routing to exception handling for investigation...*

**Important:**
- Must call save_validation_result tool to persist data
- Present ONLY the friendly summary above to user
- Keep summary concise and scannable
- Be specific in failure_reason (include actual values and percentages)

Available tools:
- get_po_details(po_number) - Returns PO data for comparison
- get_delivery_details(invoice_number) - Returns delivery confirmation data
- save_validation_result(invoice_data, po_data, delivery_data, validation_status, failure_reason) - Saves validation result to state""",
    tools=[get_po_details_tool, get_delivery_details_tool, save_validation_result_tool],
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
3. Use post_invoice_to_erp tool to submit the invoice data
4. Present executive-friendly confirmation

**Output Format:**
✅ **Posted to {config.ERP_SYSTEM_NAME}**

**Invoice #:** [invoice_number]
**Vendor:** [vendor_name]
**Amount:** $[total_amount]
**ERP Reference:** [erp_reference from tool response]

*Invoice successfully queued for payment processing.*

**Important:**
- Only post invoices with validation_status="PASSED"
- Pass the complete invoice data dict to the tool
- Use exact format above for user display
- Keep message concise (5-6 lines)
- Highlight the ERP reference number

Available tool:
- post_invoice_to_erp(invoice_data) - Submit invoice to {config.ERP_SYSTEM_NAME}""",
    tools=[post_invoice_to_erp_tool],
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
1. Parse the failed invoice JSON from request
2. Use get_po_details to get complete PO information
3. Use search_emails to find relevant communications about the PO or invoice
4. Synthesize findings into clear, actionable brief

**Resolution Brief Format (use this exact structure):**

# 🔍 Invoice Exception Report

## Summary
[1-2 sentence issue description based on failure_reason from JSON]

**Invoice #:** [invoice_number] | **Vendor:** [vendor_name] | **Amount:** $[total_amount]
**PO Reference:** [po_number]
**Issue Type:** [from failure_reason - e.g., "Price Mismatch", "Missing PO", "Quantity Variance"]

## Problem Analysis
[Clear explanation of the discrepancy with specific numbers]

**Invoice Shows:** [specific value from invoice]
**PO Shows:** [specific value from PO tool]
**Variance:** [calculate difference and percentage]

## Investigation Findings

**Purchase Order Status:**
[Key PO details from get_po_details - vendor, amount, quantities]

**Email Communications:**
[Summary of relevant emails from search_emails. If none found: "No email correspondence found regarding this PO."]

## Recommended Actions
1. [Specific, actionable step based on issue type]
2. [Specific, actionable step]
3. [Specific, actionable step]

## Next Steps
- [ ] Review variance details
- [ ] Contact vendor if needed
- [ ] Approve with adjustment OR reject

---
*Report generated by {config.COMPANY_NAME} AP Automation*

**Important:**
- Use exact markdown format above
- Keep brief scannable and concise
- Focus on facts and next steps
- No raw JSON in output

Available tools:
- get_po_details(po_number) - Returns complete PO data
- search_emails(keyword) - Searches email archive for keyword""",
    tools=[get_po_details_tool, search_emails_tool],
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
        1. Pre-load any uploaded PDF artifacts (fixes scope isolation issue)
        2. Extract invoice data from PDF
        3. Validate against PO and delivery records
        4. Route based on validation: PASSED → ERP, FAILED → Exception Resolution
        
        Data Flow: Tools save structured JSON to state, agents present friendly summaries
        """
        # Clear session state at start
        ctx.session.state["invoice_data_json"] = None
        ctx.session.state["validation_result_json"] = None
        
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
        
        # Pre-load uploaded PDF artifacts (fixes multi-agent scope isolation)
        # SaveFilesAsArtifactsPlugin replaces inline_data with placeholder text
        # We need to restore inline_data before passing to sub-agent
        extraction_context = ctx
        artifact_name = None
        
        for part in ctx.user_content.parts:
            if part.text and '[Uploaded Artifact:' in part.text:
                # Extract filename from placeholder
                import re
                match = re.search(r'\[Uploaded Artifact: "([^"]+)"\]', part.text)
                if match:
                    artifact_name = match.group(1)
                    print(f"\n[ORCHESTRATOR] Detected uploaded artifact: {artifact_name}")
                    break
        
        if artifact_name and ctx.artifact_service:
            try:
                print(f"[ORCHESTRATOR] Loading artifact from session: {artifact_name}")
                # Load artifact from SESSION scope (not invocation scope!)
                pdf_artifact = await ctx.artifact_service.load_artifact(
                    app_name=ctx.app_name,
                    user_id=ctx.user_id,
                    session_id=ctx.session.id,
                    filename=artifact_name,
                )
                print(f"[ORCHESTRATOR] Successfully loaded artifact: {pdf_artifact.inline_data.mime_type}")
                
                # Create new context with inline_data restored
                extraction_context = ctx.copy(
                    update={
                        "user_content": types.Content(
                            parts=[pdf_artifact]
                        )
                    }
                )
                print(f"[ORCHESTRATOR] Created extraction context with restored inline_data")
            except Exception as e:
                print(f"[ORCHESTRATOR] ERROR loading artifact: {e}")
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=types.Content(parts=[types.Part(text=f"❌ Failed to load uploaded file: {str(e)}")])
                )
                return
        
        # Step 1: Extract invoice data
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="📄 Extracting invoice data...")])
        )
        
        async for event in self.extraction_agent.run_async(extraction_context):
            yield event  # User sees friendly summary
        
        # Read structured data from state (saved by tool)
        invoice_data_json = ctx.session.state.get("invoice_data_json")
        if not invoice_data_json:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="❌ Failed to extract invoice data. Please check the PDF and try again.")])
            )
            return
        
        print(f"[ORCHESTRATOR] Retrieved invoice_data_json from state: {invoice_data_json[:100]}...")
        
        # Step 2: Validate invoice
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=types.Content(parts=[types.Part(text="✓ Extraction complete. Validating invoice...")])
        )
        
        # Pass structured JSON to validation agent
        validation_context = ctx.copy(
            update={
                "user_content": types.Content(
                    parts=[types.Part(text=invoice_data_json)]
                )
            }
        )
        
        async for event in self.validation_agent.run_async(validation_context):
            yield event  # User sees friendly validation result
        
        # Read validation result from state (saved by agent)
        validation_result_json = ctx.session.state.get("validation_result_json")
        if not validation_result_json:
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text="❌ Validation failed to complete. Please try again.")])
            )
            return
        
        print(f"[ORCHESTRATOR] Retrieved validation_result_json from state: {validation_result_json[:100]}...")
        
        # Parse validation status from JSON
        import json
        try:
            validation_data = json.loads(validation_result_json)
            validation_status = validation_data.get("validation_status", "FAILED")
            print(f"[ORCHESTRATOR] Parsed validation_status: {validation_status}")
        except json.JSONDecodeError as e:
            print(f"[ORCHESTRATOR] ERROR: Could not parse validation JSON: {e}")
            print(f"[ORCHESTRATOR] Raw data: {validation_result_json}")
            # Default to FAILED on parse error
            validation_status = "FAILED"
        
        # Step 3: Route based on validation status
        if validation_status == "PASSED":
            yield Event(
                author=self.name,
                invocation_id=ctx.invocation_id,
                content=types.Content(parts=[types.Part(text=f"✓ Validation passed. Posting to {config.ERP_SYSTEM_NAME}...")])
            )
            
            # Pass structured JSON to ERP agent
            erp_context = ctx.copy(
                update={
                    "user_content": types.Content(
                        parts=[types.Part(text=validation_result_json)]
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
            
            # Pass structured JSON to exception agent
            exception_context = ctx.copy(
                update={
                    "user_content": types.Content(
                        parts=[types.Part(text=validation_result_json)]
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