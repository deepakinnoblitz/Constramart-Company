import frappe
import json


@frappe.whitelist()
def execute(filters=None):

    # ---------------------------------------------
    # Parse filters
    # ---------------------------------------------
    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = filters or {}

    # -------------------------------
    # PAGINATION
    # -------------------------------
    page = int(filters.get("page", 1))
    page_length = int(filters.get("page_length", 10))
    offset = (page - 1) * page_length

    # ---------------------------------------------
    # COLUMNS
    # ---------------------------------------------
    columns = [
        {"fieldname": "row_no", "label": "#", "fieldtype": "Int", "width": 60},
        {
            "fieldname": "purchase_no",
            "label": "Purchase ID",
            "fieldtype": "Link",
            "options": "Purchase",
            "width": 150,
        },
        {
            "fieldname": "bill_date",
            "label": "Bill Date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "fieldname": "vendor_id",
            "label": "Vendor ID",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 140,
        },
        {
            "fieldname": "vendor_name",
            "label": "Vendor Name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "fieldname": "bill_no",
            "label": "Bill No",
            "fieldtype": "Data",
            "width": 140,
        },
        {"fieldname": "qty", "label": "Qty", "fieldtype": "Float", "width": 80},
        {
            "fieldname": "grand_total",
            "label": "Purchase Total",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "fieldname": "paid_amount",
            "label": "Paid Amount",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "fieldname": "balance_amount",
            "label": "Balance Amount",
            "fieldtype": "Currency",
            "width": 130,
        },
        {
            "fieldname": "purchase_status",
            "label": "Status",
            "fieldtype": "Data",
            "width": 130,
        },
    ]

    # ---------------------------------------------
    # CONDITIONS
    # ---------------------------------------------
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("p.bill_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("p.bill_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("purchase_id"):
        conditions.append("p.name = %(purchase_id)s")
        values["purchase_id"] = filters["purchase_id"]

    if filters.get("vendor_id"):
        conditions.append("p.vendor_id = %(vendor_id)s")
        values["vendor_id"] = filters["vendor_id"]

    if filters.get("vendor_name"):
        conditions.append("p.vendor_name LIKE %(vendor_name)s")
        values["vendor_name"] = f"%{filters['vendor_name']}%"

    if filters.get("purchase_status"):
        conditions.append("p.purchase_status = %(purchase_status)s")
        values["purchase_status"] = filters["purchase_status"]
    
    # GST / Non-GST filter
    if filters.get("gst_non_gst"):
        if filters["gst_non_gst"] == "Non-GST":
            # Non-GST = Exempted tax
            conditions.append("p.default_tax_type = 'Exempted'")
        elif filters["gst_non_gst"] == "GST":
            # GST = any tax other than Exempted
            conditions.append("p.default_tax_type != 'Exempted'")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # ---------------------------------------------
    # MAIN QUERY (WITH PAGINATION AND AGGREGATION)
    # ---------------------------------------------
    data = frappe.db.sql(
        f"""
        SELECT
            p.name              AS purchase_no,
            p.bill_date,
            p.vendor_id,
            p.vendor_name,
            p.bill_no,
            SUM(i.quantity)     AS qty,
            SUM(i.sub_total) / NULLIF(SUM(i.quantity), 0) AS price,
            p.grand_total,
            p.paid_amount,
            p.balance_amount,
            p.purchase_status
        FROM `tabPurchase` p
        LEFT JOIN `tabPurchase Items` i
            ON i.parent = p.name
        {where_clause}
        GROUP BY p.name
        ORDER BY p.bill_date DESC, p.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {**values, "limit": page_length, "offset": offset},
        as_dict=True,
    )

    # -------------------------------
    # ROW NUMBERS
    # -------------------------------
    for i, row in enumerate(data, start=offset + 1):
        row["row_no"] = i

    # ---------------------------------------------
    # TOTAL COUNT
    # ---------------------------------------------
    total_count = frappe.db.sql(
        f"SELECT COUNT(*) FROM `tabPurchase` p {where_clause}",
        values
    )[0][0]

    # ---------------------------------------------
    # SUMMARY (PURCHASE-LEVEL, FILTER AWARE)
    # ---------------------------------------------
    totals = frappe.db.sql(
        f"""
        SELECT
            SUM(p.grand_total) AS total_purchase,
            SUM(p.paid_amount) AS total_paid,
            SUM(p.balance_amount) AS total_pending
        FROM `tabPurchase` p
        {where_clause}
        """,
        values,
        as_dict=True,
    )[0]

    total_purchase = totals.total_purchase or 0
    total_paid = totals.total_paid or 0
    total_pending = totals.total_pending or 0

    paid_percent = (total_paid / total_purchase * 100) if total_purchase else 0
    pending_percent = (total_pending / total_purchase * 100) if total_purchase else 0

    report_summary = [
        {
            "label": "Total Purchase Amount",
            "value": total_purchase,
            "indicator": "blue",
            "datatype": "Currency",
        },
        {
            "label": f"Paid Amount ({paid_percent:.1f}%)",
            "value": total_paid,
            "indicator": "green" if paid_percent >= 50 else "orange",
            "datatype": "Currency",
        },
        {
            "label": f"Pending Amount ({pending_percent:.1f}%)",
            "value": total_pending,
            "indicator": "red" if total_pending > 0 else "green",
            "datatype": "Currency",
        },
    ]

    summary_data = {
        "purchase_count": total_count,
        "page": page,
        "page_length": page_length
    }

    return columns, data, summary_data, None, report_summary
