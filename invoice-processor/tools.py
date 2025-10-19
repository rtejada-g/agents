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

async def read_invoice_pdf(tool_context: ToolContext, filename: str) -> Dict[str, Any]:
    """
    Reads and extracts structured data from an uploaded invoice PDF artifact.
    
    This tool:
    1. Loads the PDF artifact from storage
    2. Makes a direct Gemini API call with structured output schema
    3. Returns extracted invoice data as JSON
    
    Args:
        tool_context: The tool context (provides access to artifacts)
        filename: The PDF artifact filename (e.g., 'invoice.pdf')
    
    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - invoice_data: Extracted invoice fields (if successful)
        - error_message: Error description (if error)
    """
    print(f"\n{'='*80}")
    print(f"[PDF_EXTRACT] Tool called with filename: '{filename}'")
    print(f"[PDF_EXTRACT] Filename type: {type(filename)}")
    print(f"[PDF_EXTRACT] Filename length: {len(filename)}")
    print(f"{'='*80}\n")
    
    try:
        # First, list all available artifacts to see what's actually there
        print(f"[PDF_EXTRACT] Listing all available artifacts...")
        try:
            available_artifacts = await tool_context.list_artifacts()
            print(f"[PDF_EXTRACT] Available artifacts: {available_artifacts}")
        except Exception as e:
            print(f"[PDF_EXTRACT] Could not list artifacts: {e}")
        
        # 1. Load the PDF artifact
        print(f"[PDF_EXTRACT] Attempting to load artifact: '{filename}'")
        pdf_artifact = await tool_context.load_artifact(filename=filename)
        
        if not pdf_artifact or not pdf_artifact.inline_data:
            print(f"[PDF_EXTRACT] ERROR: Artifact not found - '{filename}'")
            print(f"[PDF_EXTRACT] pdf_artifact is None: {pdf_artifact is None}")
            if pdf_artifact:
                print(f"[PDF_EXTRACT] pdf_artifact.inline_data is None: {pdf_artifact.inline_data is None}")
            
            # Try to provide helpful error message
            error_msg = f"PDF artifact '{filename}' not found."
            if available_artifacts:
                error_msg += f" Available artifacts: {', '.join(available_artifacts)}"
            
            return {
                "status": "error",
                "error_message": error_msg
            }
        
        print(f"[PDF_EXTRACT] Loaded PDF: {filename} ({pdf_artifact.inline_data.mime_type})")
        
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
        
        return {
            "status": "success",
            "invoice_data": invoice_data
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
        A dictionary with:
        - status: 'success' or 'error'
        - po_data: Dict with PO details (if found)
        - error_message: Error description (if error)
    
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
    
    return {
        "status": "success",
        "po_data": po_details
    }

get_po_details_tool = FunctionTool(func=get_po_details)


# --- Delivery Receipt Tools ---

def get_delivery_details(invoice_number: str) -> Dict[str, Any]:
    """
    Retrieves delivery receipt details for a specific invoice number.
    
    Args:
        invoice_number: The invoice number to look up (e.g., 'INV-101')
    
    Returns:
        A dictionary with:
        - status: 'success' or 'error'
        - delivery_data: Dict with delivery details (if found)
        - error_message: Error description (if error)
    
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
    
    return {
        "status": "success",
        "delivery_data": delivery_details
    }

get_delivery_details_tool = FunctionTool(func=get_delivery_details)


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
    'search_emails_tool',
    'post_invoice_to_erp_tool',
]