import frappe
from frappe.utils import flt
import json


def execute(filters=None):

    # Convert JSON to dict (Frappe sends filters as string)
    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = filters or {}

    # -------------------------------
    # PAGINATION (Skip if exporting)
    # -------------------------------
    is_export = (
        filters.get("is_export") in ["true", "1", 1]
        or frappe.form_dict.get("is_export") in ["true", "1"]
        or frappe.form_dict.get("file_format_type") is not None
        or frappe.form_dict.get("cmd") == "frappe.desk.query_report.export_query"
    )

    page = int(filters.get("page", 1))
    page_length = int(filters.get("page_length", 10))
    offset = (page - 1) * page_length

    columns = get_columns()
    processed_data = get_data(filters)
    
    total_count = len(processed_data)

    # -------------------------------
    # SLICE DATA (PAGINATION)
    # -------------------------------
    if not is_export:
        data = processed_data[offset : offset + page_length]
    else:
        data = processed_data

    # -------------------------------
    # ROW NUMBERS
    # -------------------------------
    if is_export:
        for i, row in enumerate(data, start=1):
            row["row_no"] = i
    else:
        for i, row in enumerate(data, start=offset + 1):
            row["row_no"] = i

    summary = get_summary(processed_data)

    summary_data = {
        "invoice_count": total_count,
        "page": page,
        "page_length": page_length
    }

    # Return 5 values → (columns, rows, pagination_data, chart, report_summary)
    return columns, data, summary_data, None, summary


# ---------------------------------------------------
#  COLUMNS
# ---------------------------------------------------
def get_columns():
    return [
        {"label": "#", "fieldname": "row_no", "fieldtype": "Int", "width": 60},
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
        {"label": "Business Person", "fieldname": "business_person", "fieldtype": "Link", "options": "Business Person", "width": 140},
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

    if filters.get("business_person"):
        conditions += f" AND ic.business_person = '{filters['business_person']}'"

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
            bp.business_person_name AS business_person,
            ic.creation
        FROM `tabInvoice` inv
        INNER JOIN `tabInvoice Collection` ic ON ic.invoice = inv.name
        LEFT JOIN `tabBusiness Person` bp ON bp.name = ic.business_person
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
            "label": "Total Invoices",
            "value": len(unique_invoices),
            "indicator": "blue",
            "datatype": "Int",
        },
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


