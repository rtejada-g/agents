# Invoice Processor Architecture

## Multi-Agent Pattern

**Orchestrator:** `InvoiceProcessor` (BaseAgent)
- Routes workflow based on validation status
- Handles file upload artifact loading
- Manages state between agents

**Sub-Agents:** LlmAgents for specific tasks
- `InvoiceExtractionAgent` - PDF → Structured JSON
- `InvoiceValidationAgent` - Cross-reference with POs
- `ERPAgent` - Post to ERP system
- `ExceptionResolutionAgent` - Investigate failures

## Data Flow: Dual-Channel Communication

### Channel 1: Structured Data (State)
Tools save JSON to session state for agent-to-agent communication:

```python
# Tools save structured data
tool_context.actions.state_delta["invoice_data_json"] = json.dumps(data)
tool_context.actions.state_delta["validation_result_json"] = json.dumps(result)

# Orchestrator reads structured data
invoice_data_json = ctx.session.state.get("invoice_data_json")
data = json.loads(invoice_data_json)  # Reliable parsing
```

### Channel 2: User Display (Events)
Agents output friendly markdown for UI:

```python
# Agents present summaries
instruction="Call tool, then present friendly summary. Data auto-saved."

# Output example
📋 **Invoice Extracted**
**Invoice #:** INV-101
**Vendor:** ACME Corp
```

## File Upload Handling (Critical for Multi-Agent)

### Problem: Scope Isolation
`SaveFilesAsArtifactsPlugin` saves at session level, but sub-agents query at invocation level → empty artifact list

### Solution: Orchestrator Pre-Loading

```python
# 1. Detect artifact placeholder from plugin
for part in ctx.user_content.parts:
    if '[Uploaded Artifact:' in part.text:
        artifact_name = extract_filename(part.text)

# 2. Load from SESSION scope (not invocation!)
pdf_artifact = await ctx.artifact_service.load_artifact(
    session_id=ctx.session.id,
    filename=artifact_name,
)

# 3. Restore inline_data in new context
extraction_context = ctx.copy(
    update={"user_content": types.Content(parts=[pdf_artifact])}
)

# 4. Pass to sub-agent with clean inline_data
async for event in self.extraction_agent.run_async(extraction_context):
    yield event
```

### Tool Access Pattern

```python
# Tool accesses from invocation context (not artifact list)
if hasattr(tool_context, '_invocation_context'):
    ctx = tool_context._invocation_context
    for part in ctx.user_content.parts:
        if part.inline_data and part.inline_data.mime_type == 'application/pdf':
            pdf_artifact = part  # Works because orchestrator restored it
```

## Best Practices

### 1. Tools Handle Data
- Save structured JSON to `state_delta`
- Return user-friendly display fields
- Use `Optional[str]` for nullable parameters (not `str = None`)

### 2. Agents Handle UX
- No `output_key` needed
- Present friendly summaries
- Clear, specific instructions with example outputs

### 3. Orchestrator Handles Flow
- Pre-load file uploads
- Read JSON from state (no text parsing)
- Route based on structured data fields
- Create isolated contexts for sub-agents

### 4. State Keys Convention
Use `*_json` suffix for structured data:
- `invoice_data_json` - Extracted invoice data
- `validation_result_json` - Validation result with status

## Testing

Verify all scenarios:
1. **Happy Path** - Valid invoice with matching PO
2. **Price Mismatch** - Invoice amount exceeds PO tolerance
3. **Invalid PO** - PO number not found in system

Check logs for:
```bash
[ORCHESTRATOR] Detected uploaded artifact
[ORCHESTRATOR] Successfully loaded artifact
[PDF_EXTRACT] Found PDF in context
[ORCHESTRATOR] Retrieved *_json from state
[ORCHESTRATOR] Parsed validation_status: PASSED/FAILED