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

    # Handle checkbox: When checked=1, unchecked might be 0 or simply missing from filters
    # Default to showing all collections (unchecked) if parameter is not explicitly 1
    show_only_last = filters.get("show_only_last_collection")
    if show_only_last == 1:
        show_only_last = True
    else:
        # Treat 0, None, or any other value as False (show all)
        show_only_last = False

    # Get all collections with invoice details
    if show_only_last:
        # Show only the last collection per invoice (by creation timestamp to handle same dates)
        data = frappe.db.sql(f"""
            SELECT
                ic.name AS collection_id,
                inv.name AS invoice,
                inv.invoice_date,
                inv.customer_id,
                inv.customer_name,
                inv.grand_total,
                inv.received_amount AS total_collected,
                inv.balance_amount AS amount_pending,
                ic.collection_date,
                ic.amount_collected,
                ic.mode_of_payment AS payment_mode
            FROM `tabInvoice` inv
            INNER JOIN `tabInvoice Collection` ic ON ic.invoice = inv.name
            INNER JOIN (
                SELECT invoice, MAX(creation) AS max_creation
                FROM `tabInvoice Collection`
                GROUP BY invoice
            ) latest ON ic.invoice = latest.invoice AND ic.creation = latest.max_creation
            WHERE {conditions}
            ORDER BY inv.invoice_date DESC, ic.collection_date DESC
        """, as_dict=True)
    else:
        # Show all collections
        data = frappe.db.sql(f"""
            SELECT
                ic.name AS collection_id,
                inv.name AS invoice,
                inv.invoice_date,
                inv.customer_id,
                inv.customer_name,
                inv.grand_total,
                inv.received_amount AS total_collected,
                inv.balance_amount AS amount_pending,
                ic.collection_date,
                ic.amount_collected,
                ic.mode_of_payment AS payment_mode
            FROM `tabInvoice` inv
            INNER JOIN `tabInvoice Collection` ic ON ic.invoice = inv.name
            WHERE {conditions}
            ORDER BY inv.invoice_date DESC, ic.collection_date DESC
        """, as_dict=True)

    return data


# ---------------------------------------------------
#  SUMMARY CARDS
# ---------------------------------------------------
def get_summary(data):

    # Get unique invoices to calculate totals
    unique_invoices = {}
    for d in data:
        inv = d.get("invoice")
        if inv not in unique_invoices:
            unique_invoices[inv] = {
                "grand_total": flt(d.get("grand_total")),
                "total_collected": flt(d.get("total_collected")),
                "amount_pending": flt(d.get("amount_pending"))
            }

    total_inv = sum(v["grand_total"] for v in unique_invoices.values())
    total_collected = sum(v["total_collected"] for v in unique_invoices.values())
    total_pending = sum(v["amount_pending"] for v in unique_invoices.values())

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


