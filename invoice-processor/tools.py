"""
Tools for Invoice Processor Agent

This module contains all the Python functions that agents use to:
- Load and query data from customer-specific CSV files
- Search email archives
- Interact with mock ERP systems
- Extract data from PDF invoices using Gemini Vision
"""

import pandas as pd
import json
from typing import Dict, Any, Optional
import os
from google.adk.tools import FunctionTool, ToolContext
from datetime import datetime
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from . import config

# --- Gemini Client for Direct API Calls ---
http_options = types.HttpOptions(
    async_client_args={'read_bufsize': 16 * 1024 * 1024}
)
shared_client = genai.Client(vertexai=True, http_options=http_options)

# --- PDF Extraction Schema ---

class InvoiceData(BaseModel):
    """Structured schema for invoice data extraction"""
    invoice_number: str = Field(description="The invoice number (e.g., 'INV-101', 'PBSI-250242')")
    vendor_name: str = Field(description="The vendor/supplier company name")
    invoice_date: str = Field(description="The date the invoice was issued (YYYY-MM-DD format)")
    po_number: str = Field(description="The purchase order number referenced on the invoice")
    item_description: str = Field(description="Description of the item/service")
    quantity: float = Field(description="Quantity of items")
    unit_price: float = Field(description="Price per unit")
    total_amount: float = Field(description="Total invoice amount")


# --- PDF Extraction Tool ---

async def read_invoice_pdf(tool_context: ToolContext, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Reads and extracts structured data from an uploaded invoice PDF artifact.
    
    This tool accesses PDF artifacts at SESSION scope (not invocation scope) to work
    around multi-agent scope isolation issues.
    
    Process:
    1. Accesses orchestrator-loaded PDF from context inline_data
    2. Makes Gemini API call with structured output schema
    3. Saves structured data to session state for orchestrator
    4. Returns user-friendly summary for display
    
    Args:
        tool_context: The tool context (provides access to artifacts and state)
        filename: (Optional) Specific PDF filename (currently unused - PDF comes from context)
    
    Returns:
        A dictionary with user-friendly display fields:
        - status: 'success' or 'error'
        - invoice_number, vendor_name, total_amount, po_number (if successful)
        - error_message: Error description (if error)
    """
    print(f"\n{'='*80}")
    print(f"[PDF_EXTRACT] Tool called")
    print(f"{'='*80}\n")
    
    try:
        # The orchestrator pre-loads the PDF and passes it in the context with inline_data
        # We need to get the PDF from the invocation context's user message
        # Access through the shared invocation context
        from google.adk.agents import InvocationContext
        
        # Try to get the PDF from the current invocation context
        # The orchestrator passed it in the user_content
        pdf_artifact = None
        actual_filename = "uploaded_invoice.pdf"
        
        # Check if there's inline_data in the context
        # Note: This is a workaround - ideally we'd have direct access to context
        # For now, try to access from tool_context internals
        if hasattr(tool_context, '_invocation_context'):
            ctx = tool_context._invocation_context
            if ctx and ctx.user_content and ctx.user_content.parts:
                for part in ctx.user_content.parts:
                    if part.inline_data and part.inline_data.mime_type == 'application/pdf':
                        pdf_artifact = part
                        actual_filename = part.inline_data.display_name or "uploaded_invoice.pdf"
                        print(f"[PDF_EXTRACT] Found PDF in context: {actual_filename}")
                        break
        
        if not pdf_artifact:
            error_msg = "No PDF found in context. Please upload an invoice PDF."
            print(f"[PDF_EXTRACT] ERROR: {error_msg}")
            return {"status": "error", "error_message": error_msg}
        
        print(f"[PDF_EXTRACT] Successfully found PDF: {actual_filename} ({pdf_artifact.inline_data.mime_type})")
        
        # 2. Prepare Gemini API call with structured output
        extraction_prompt = """Extract all invoice data from this PDF document.
        
        Return ONLY the structured JSON data with these exact fields:
        - invoice_number: The invoice number
        - vendor_name: The vendor company name
        - invoice_date: Invoice date (YYYY-MM-DD)
        - po_number: Purchase order number
        - item_description: Item/service description
        - quantity: Quantity
        - unit_price: Unit price
        - total_amount: Total amount
        
        Be precise and extract the exact values from the document."""
        
        content = types.Content(
            role="user",
            parts=[
                pdf_artifact,  # The PDF Part
                types.Part(text=extraction_prompt)
            ]
        )
        
        # 3. Call Gemini with structured output schema
        print(f"[PDF_EXTRACT] Calling Gemini API for extraction...")
        
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InvoiceData
        )
        
        response = await shared_client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[content],
            config=generate_content_config
        )
        
        print(f"[PDF_EXTRACT] Received response from Gemini")
        
        # 4. Parse and validate the response
        invoice_data = json.loads(response.text)
        
        print(f"[PDF_EXTRACT] Successfully extracted invoice: {invoice_data.get('invoice_number')}")
        
        # 5. Save structured data to session state for orchestrator
        tool_context.actions.state_delta["invoice_data_json"] = json.dumps(invoice_data)
        print(f"[PDF_EXTRACT] Saved invoice data to session state")
        
        # 6. Return user-friendly display fields
        return {
            "status": "success",
            "invoice_number": invoice_data.get("invoice_number"),
            "vendor_name": invoice_data.get("vendor_name"),
            "total_amount": invoice_data.get("total_amount"),
            "po_number": invoice_data.get("po_number"),
            "invoice_date": invoice_data.get("invoice_date")
        }
        
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse Gemini response as JSON: {str(e)}"
        print(f"[PDF_EXTRACT] ERROR: {error_msg}")
        return {
            "status": "error",
            "error_message": error_msg
        }
    except Exception as e:
        error_msg = f"Error extracting PDF data: {str(e)}"
        print(f"[PDF_EXTRACT] ERROR: {error_msg}")
        return {
            "status": "error",
            "error_message": error_msg
        }

read_invoice_pdf_tool = FunctionTool(func=read_invoice_pdf)


# --- Data Loading ---

def load_csv_data(filename: str) -> pd.DataFrame:
    """
    Loads data from a customer-specific CSV file into a Pandas DataFrame.
    
    Args:
        filename: The CSV file name (e.g., 'purchase_orders.csv')
    
    Returns:
        A Pandas DataFrame containing the data, or None if an error occurs.
    """
    # Build path: agents/invoice-processor/data/{CUSTOMER_DATA_SET}/{filename}
    data_path = os.path.join(
        os.path.dirname(__file__),
        "data",
        config.CUSTOMER_DATA_SET,
        filename
    )
    
    try:
        df = pd.read_csv(data_path)
        print(f"[DATA_LOADER] Loaded {len(df)} rows from {data_path}")
        return df
    except FileNotFoundError:
        print(f"[DATA_LOADER] ERROR: File not found - {data_path}")
        print(f"[DATA_LOADER] Please ensure data exists in: data/{config.CUSTOMER_DATA_SET}/")
        return None
    except Exception as e:
        print(f"[DATA_LOADER] ERROR loading {data_path}: {e}")
        return None


# --- Purchase Order Tools ---

def get_po_details(po_number: str) -> Dict[str, Any]:
    """
    Retrieves purchase order details for a specific PO number.
    
    Args:
        po_number: The PO number to look up (e.g., 'PO-10001')
    
    Returns:
        A dictionary with user-friendly display fields:
        - status: 'success' or 'error'
        - po_number, vendor_name, total_amount, etc. (if found)
        - error_message: Error description (if error)
        
    Note: Full PO data is automatically available in tool result for agent processing
    
    Expected CSV schema:
    po_number,vendor_name,item_description,quantity,unit_price,total_amount
    """
    print(f"[GET_PO] Looking up PO: {po_number}")
    
    po_data = load_csv_data("purchase_orders.csv")
    if po_data is None:
        return {
            "status": "error",
            "error_message": "Failed to load purchase orders data"
        }
    
    # Find the PO - convert both to string for comparison
    po_row = po_data[po_data["po_number"].astype(str) == str(po_number)]
    
    if po_row.empty:
        print(f"[GET_PO] PO not found: {po_number}")
        return {
            "status": "error",
            "error_message": f"Purchase Order {po_number} not found in system"
        }
    
    # Convert to dict
    po_details = po_row.iloc[0].to_dict()
    print(f"[GET_PO] Found PO: {po_details}")
    
    # Return user-friendly format (full data is in result for agent to use)
    return {
        "status": "success",
        "po_number": str(po_details.get("po_number")),
        "vendor_name": str(po_details.get("vendor_name")),
        "item_description": str(po_details.get("item_description")),
        "quantity": float(po_details.get("quantity", 0)),
        "unit_price": float(po_details.get("unit_price", 0)),
        "total_amount": float(po_details.get("total_amount", 0))
    }

get_po_details_tool = FunctionTool(func=get_po_details)


# --- Delivery Receipt Tools ---

def get_delivery_details(invoice_number: str) -> Dict[str, Any]:
    """
    Retrieves delivery receipt details for a specific invoice number.
    
    Args:
        invoice_number: The invoice number to look up (e.g., 'INV-101')
    
    Returns:
        A dictionary with user-friendly display fields:
        - status: 'success' or 'error'
        - invoice_number, status, signed_by, delivery_date (if found)
        - error_message: Error description (if error)
        
    Note: Full delivery data is automatically available in tool result for agent processing
    
    Expected CSV schema:
    invoice_number,po_number,status,signed_by,delivery_date
    """
    print(f"[GET_DELIVERY] Looking up delivery for invoice: {invoice_number}")
    
    delivery_data = load_csv_data("delivery_receipts.csv")
    if delivery_data is None:
        return {
            "status": "error",
            "error_message": "Failed to load delivery receipts data"
        }
    
    # Find the delivery receipt - convert both to string for comparison
    delivery_row = delivery_data[delivery_data["invoice_number"].astype(str) == str(invoice_number)]
    
    if delivery_row.empty:
        print(f"[GET_DELIVERY] Delivery receipt not found for: {invoice_number}")
        return {
            "status": "error",
            "error_message": f"Delivery receipt for invoice {invoice_number} not found"
        }
    
    # Convert to dict
    delivery_details = delivery_row.iloc[0].to_dict()
    print(f"[GET_DELIVERY] Found delivery: {delivery_details}")
    
    # Return user-friendly format (full data is in result for agent to use)
    return {
        "status": "success",
        "invoice_number": str(delivery_details.get("invoice_number")),
        "po_number": str(delivery_details.get("po_number")),
        "delivery_status": str(delivery_details.get("status")),
        "signed_by": str(delivery_details.get("signed_by")),
        "delivery_date": str(delivery_details.get("delivery_date"))
    }

get_delivery_details_tool = FunctionTool(func=get_delivery_details)


# --- Validation Helper Tool ---

def save_validation_result(
    tool_context: ToolContext,
    invoice_data: dict,
    po_data: dict,
    delivery_data: dict,
    validation_status: str,
    failure_reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Saves complete validation result to session state.
    
    This helper tool allows the validation agent to persist structured data
    while still outputting user-friendly messages.
    
    Args:
        tool_context: The tool context for state access
        invoice_data: Complete invoice data dict
        po_data: Complete PO data dict
        delivery_data: Complete delivery data dict
        validation_status: "PASSED" or "FAILED"
        failure_reason: Description of failure (if FAILED)
    
    Returns:
        Confirmation message for agent
    """
    print(f"[SAVE_VALIDATION] Saving validation result with status: {validation_status}")
    
    # Build complete validation result
    validation_result = {
        **invoice_data,  # Include all invoice fields
        "validation_status": validation_status,
        "po_verified": po_data.get("status") == "success",
        "delivery_confirmed": delivery_data.get("status") == "success",
    }
    
    if failure_reason:
        validation_result["failure_reason"] = failure_reason
    
    # Save to state for orchestrator
    validation_json = json.dumps(validation_result)
    tool_context.actions.state_delta["validation_result_json"] = validation_json
    
    print(f"[SAVE_VALIDATION] Saved validation result to state ({len(validation_json)} bytes)")
    
    return {
        "status": "success",
        "message": f"Validation result ({validation_status}) saved to state",
        "validation_status": validation_status
    }

save_validation_result_tool = FunctionTool(func=save_validation_result)


# --- Email Search Tools ---

def search_emails(keyword: str) -> Dict[str, Any]:
    """
    Searches internal email archive for messages containing a keyword.
    
    Args:
        keyword: The keyword to search for (e.g., PO number, invoice number)
    
    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - matching_emails: List of email text snippets (if found)
        - count: Number of matches
        - error_message: Error description (if error)
    
    Expected file format:
    Plain text file with emails separated by '---' delimiters
    """
    print(f"[EMAIL_SEARCH] Searching emails for keyword: {keyword}")
    
    email_file_path = os.path.join(
        os.path.dirname(__file__),
        "data",
        config.CUSTOMER_DATA_SET,
        "internal_emails.txt"
    )
    
    try:
        with open(email_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by email delimiter
        emails = content.split('---')
        
        # Find emails containing the keyword (case-insensitive)
        matching_emails = [
            email.strip() 
            for email in emails 
            if keyword.lower() in email.lower() and email.strip()
        ]
        
        print(f"[EMAIL_SEARCH] Found {len(matching_emails)} matching emails")
        
        if not matching_emails:
            return {
                "status": "success",
                "matching_emails": [],
                "count": 0,
                "message": f"No emails found containing '{keyword}'"
            }
        
        return {
            "status": "success",
            "matching_emails": matching_emails,
            "count": len(matching_emails)
        }
        
    except FileNotFoundError:
        print(f"[EMAIL_SEARCH] ERROR: Email file not found - {email_file_path}")
        return {
            "status": "error",
            "error_message": f"Email archive not found in data/{config.CUSTOMER_DATA_SET}/"
        }
    except Exception as e:
        print(f"[EMAIL_SEARCH] ERROR: {e}")
        return {
            "status": "error",
            "error_message": f"Error searching emails: {str(e)}"
        }

search_emails_tool = FunctionTool(func=search_emails)



# --- ERP System Tools ---

def post_invoice_to_erp(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Posts a validated invoice to the ERP system (SAP/mock).
    
    This is a MOCK function that simulates posting to an ERP system.
    In production, this would make actual API calls.
    
    Args:
        invoice_data: Dictionary containing invoice details
    
    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - message: Success/error message
        - erp_reference: Mock ERP posting reference
        - posted_at: Timestamp of posting
    """
    print(f"[ERP_POST] Posting invoice to {config.ERP_SYSTEM_NAME}...")
    
    try:
        # Extract key fields
        invoice_number = invoice_data.get("invoice_number", "UNKNOWN")
        total_amount = invoice_data.get("total_amount", 0)
        vendor_name = invoice_data.get("vendor_name", "UNKNOWN")
        
        # Generate mock ERP reference
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        erp_reference = f"{config.ERP_SYSTEM_NAME}-{invoice_number}-{timestamp}"
        
        # Simulate posting delay
        print(f"[ERP_POST] Posting to {config.ERP_SYSTEM_NAME}...")
        print(f"[ERP_POST] Invoice: {invoice_number}")
        print(f"[ERP_POST] Vendor: {vendor_name}")
        print(f"[ERP_POST] Amount: ${total_amount:,.2f}")
        
        success_message = (
            f"✅ **SUCCESS**: Invoice {invoice_number} for ${total_amount:,.2f} "
            f"has been posted to {config.ERP_SYSTEM_NAME} for payment.\n\n"
            f"**Vendor:** {vendor_name}\n"
            f"**ERP Reference:** {erp_reference}\n"
            f"**Posted At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        print(f"[ERP_POST] SUCCESS - Reference: {erp_reference}")
        
        return {
            "status": "success",
            "message": success_message,
            "erp_reference": erp_reference,
            "posted_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        error_message = f"Failed to post invoice to {config.ERP_SYSTEM_NAME}: {str(e)}"
        print(f"[ERP_POST] ERROR: {error_message}")
        return {
            "status": "error",
            "error_message": error_message
        }

post_invoice_to_erp_tool = FunctionTool(func=post_invoice_to_erp)


# Export all tools for easy import
__all__ = [
    'read_invoice_pdf_tool',
    'get_po_details_tool',
    'get_delivery_details_tool',
    'save_validation_result_tool',
    'search_emails_tool',
    'post_invoice_to_erp_tool',
]