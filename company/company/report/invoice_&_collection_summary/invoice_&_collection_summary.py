import frappe
from frappe.utils import flt
import json


def execute(filters=None):

    # Convert JSON to dict (Frappe sends filters as string)
    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)

    # Return 5 values → (columns, rows, message, chart, summary)
    return columns, data, None, None, summary


# ---------------------------------------------------
#  COLUMNS
# ---------------------------------------------------
def get_columns():
    return [
        {"label": "Collection ID", "fieldname": "collection_id", "fieldtype": "Link", "options": "Invoice Collection", "width": 140},
        {"label": "Invoice", "fieldname": "invoice", "fieldtype": "Link", "options": "Invoice", "width": 150},
        {"label": "Invoice Date", "fieldname": "invoice_date", "fieldtype": "Date", "width": 110},

        {"label": "Customer", "fieldname": "customer_id", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": "Customer Name", "fieldname": "customer_name", "fieldtype": "Data", "width": 150},

        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
        {"label": "Amount Collected", "fieldname": "amount_collected", "fieldtype": "Currency", "width": 130},
        {"label": "Pending Amount", "fieldname": "amount_pending", "fieldtype": "Currency", "width": 120},
        {"label": "Collection Date", "fieldname": "collection_date", "fieldtype": "Date", "width": 130},
        {"label": "Total Collected", "fieldname": "total_collected", "fieldtype": "Currency", "width": 130},
        {"label": "Payment Mode", "fieldname": "payment_mode", "fieldtype": "Data", "width": 120},
    ]


# ---------------------------------------------------
#  MAIN DATA
# ---------------------------------------------------
def get_data(filters):
    conditions = "1=1"

    if filters.get("from_date"):
        conditions += f" AND inv.invoice_date >= '{filters['from_date']}'"

    if filters.get("to_date"):
        conditions += f" AND inv.invoice_date <= '{filters['to_date']}'"

    if filters.get("customer"):
        conditions += f" AND inv.customer_id = '{filters['customer']}'"

    if filters.get("invoice"):
        conditions += f" AND inv.name = '{filters['invoice']}'"

    # Fetch all collections for relevant invoices to calculate running balance accurately
    # Sort ASC for sequence calculation
    raw_data = frappe.db.sql(f"""
        SELECT
            ic.name AS collection_id,
            inv.name AS invoice,
            inv.invoice_date,
            inv.customer_id,
            inv.customer_name,
            inv.grand_total,
            ic.collection_date,
            ic.amount_collected,
            ic.mode_of_payment AS payment_mode,
            ic.creation
        FROM `tabInvoice` inv
        INNER JOIN `tabInvoice Collection` ic ON ic.invoice = inv.name
        WHERE {conditions}
        ORDER BY inv.invoice_date ASC, ic.collection_date ASC, ic.creation ASC
    """, as_dict=True)

    invoice_running_total = {}
    processed_data = []

    # Calculate running balance per invoice
    for d in raw_data:
        inv_name = d.invoice
        if inv_name not in invoice_running_total:
            invoice_running_total[inv_name] = 0.0

        invoice_running_total[inv_name] += flt(d.amount_collected)

        # Total collected up to this point
        d.total_collected = invoice_running_total[inv_name]
        # Pending after this specific collection
        d.amount_pending = flt(d.grand_total) - d.total_collected
        processed_data.append(d)

    # Handle 'show_only_last_collection' in Python
    if filters.get("show_only_last_collection"):
        last_collection_map = {}
        for d in processed_data:
            # Since we iterate ASC, the latest one will overwrite others
            last_collection_map[d.invoice] = d
        processed_data = list(last_collection_map.values())

    # Final sort for display (Latest First)
    processed_data.sort(
        key=lambda x: (x.invoice_date, x.collection_date, x.creation),
        reverse=True
    )

    return processed_data


# ---------------------------------------------------
#  SUMMARY CARDS
# ---------------------------------------------------
def get_summary(data):
    total_inv = 0
    total_collected = 0
    total_pending = 0
    
    unique_invoices = set()
    
    for d in data:
        inv = d.get("invoice")
        if inv not in unique_invoices:
            unique_invoices.add(inv)
            # Add invoice-level totals only once (from the latest available record for this invoice)
            total_inv += flt(d.get("grand_total"))
            total_collected += flt(d.get("total_collected"))
            total_pending += flt(d.get("amount_pending"))

    return [
        {
            "label": "Total Invoice Amount",
            "value": total_inv,
            "indicator": "blue",
            "datatype": "Currency",
        },
        {
            "label": "Total Collected",
            "value": total_collected,
            "indicator": "green",
            "datatype": "Currency",
        },
        {
            "label": "Total Pending",
            "value": total_pending,
            "indicator": "red",
            "datatype": "Currency",
        }
    ]


