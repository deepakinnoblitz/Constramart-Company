import frappe
import json

@frappe.whitelist()
def execute(filters=None):

    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = filters or {}

    # -------------------------------
    # PAGINATION (Skip if exporting)
    # -------------------------------
    is_export = (
        frappe.flags.is_export 
        or frappe.form_dict.get("is_export") in ["true", "1"]
        or filters.get("is_export") in ["true", "1", 1]
        or frappe.form_dict.get("file_format_type") is not None
        or frappe.form_dict.get("cmd") == "frappe.desk.query_report.export_query"
    )

    page = int(filters.get("page", 1))
    page_length = int(filters.get("page_length", 10))
    offset = (page - 1) * page_length

    # -------------------------------
    # COLUMNS
    # -------------------------------
    columns = [
        {"fieldname": "row_no", "label": "#", "fieldtype": "Int", "width": 60},
        {"fieldname": "invoice_no", "label": "Invoice No", "fieldtype": "Link", "options": "Invoice", "width": 150},
        {"fieldname": "invoice_date", "label": "Invoice Date", "fieldtype": "Date", "width": 120},
        {"fieldname": "customer_id", "label": "Customer ID", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"fieldname": "customer_name", "label": "Customer Name", "fieldtype": "Data", "width": 180},
        {"fieldname": "billing_name", "label": "Company Name", "fieldtype": "Data", "width": 200},
        {"fieldname": "qty", "label": "Qty", "fieldtype": "Float", "width": 80},
        {"fieldname": "price", "label": "Avg Price", "fieldtype": "Currency", "width": 120},
        {"fieldname": "grand_total", "label": "Invoice Total", "fieldtype": "Currency", "width": 140},
        {"fieldname": "received_amount", "label": "Received", "fieldtype": "Currency", "width": 130},
        {"fieldname": "balance_amount", "label": "Pending", "fieldtype": "Currency", "width": 130},
    ]

    # -------------------------------
    # CONDITIONS
    # -------------------------------
    conditions = ["inv.docstatus < 2"] # Exclude Cancelled
    values = {}

    if filters.get("from_date"):
        conditions.append("inv.invoice_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("inv.invoice_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("customer"):
        conditions.append("inv.customer_id = %(customer)s")
        values["customer"] = filters["customer"]

    if filters.get("billing_name"):
        conditions.append("inv.billing_name LIKE %(billing_name)s")
        values["billing_name"] = f"%{filters['billing_name']}%"

    if filters.get("gst_non_gst"):
        if filters["gst_non_gst"] == "Non-GST":
            conditions.append("inv.default_tax_type = 'Exempted'")
        elif filters["gst_non_gst"] == "GST":
            conditions.append("inv.default_tax_type != 'Exempted'")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # -------------------------------
    # MAIN QUERY (CORRECT PAGINATION)
    # -------------------------------
    limit_clause = "LIMIT %(limit)s OFFSET %(offset)s" if not is_export else ""

    data = frappe.db.sql(
        f"""
        SELECT
            inv.name AS invoice_no,
            inv.invoice_date,
            inv.customer_id,
            cust.customer_name,
            inv.billing_name,
            SUM(child.quantity) AS qty,
            SUM(child.sub_total) / NULLIF(SUM(child.quantity), 0) AS price,
            inv.grand_total,
            inv.received_amount,
            inv.balance_amount
        FROM `tabInvoice` inv
        LEFT JOIN `tabInvoice Items` child ON child.parent = inv.name
        LEFT JOIN `tabCustomer` cust ON cust.name = inv.customer_id
        {where_clause}
        GROUP BY inv.name
        ORDER BY inv.invoice_date DESC, inv.name DESC
        {limit_clause}
        """,
        {**values, "limit": page_length, "offset": offset},
        as_dict=True,
    )

    # -------------------------------
    # ROW NUMBERS
    # -------------------------------
    if is_export:
        for i, row in enumerate(data, start=1):
            row["row_no"] = i
    else:
        for i, row in enumerate(data, start=offset + 1):
            row["row_no"] = i

    # -------------------------------
    # TOTAL COUNT (INVOICES)
    # -------------------------------
    total_count = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabInvoice` inv {where_clause}",
        values
    )[0][0]

    # -------------------------------
    # SUMMARY
    # -------------------------------
    totals = frappe.db.sql(
        f"""
        SELECT
            SUM(inv.grand_total) AS total_sales,
            SUM(inv.received_amount) AS total_received,
            SUM(inv.balance_amount) AS total_pending
        FROM `tabInvoice` inv
        {where_clause}
        """,
        values,
        as_dict=True,
    )[0]

    report_summary = [
        {
            "label": "Total Sales",
            "value": totals.total_sales or 0,
            "datatype": "Currency",
            "indicator": "blue"
        },
        {
            "label": "Received",
            "value": totals.total_received or 0,
            "datatype": "Currency",
            "indicator": "green"
        },
        {
            "label": "Pending",
            "value": totals.total_pending or 0,
            "datatype": "Currency",
            "indicator": "red" if (totals.total_pending or 0) > 0 else "green"
        },
    ]

    summary_data = {
        "invoice_count": total_count,
        "page": page,
        "page_length": page_length
    }

    return columns, data, summary_data, None, report_summary
