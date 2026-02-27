import frappe
from frappe.utils import flt


# ============================================================
# EXECUTE
# ============================================================
def execute(filters=None):
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
    
    # Calculate summary based on FULL data before filtering for "last collected" only
    summary = get_summary(processed_data)

    if filters.get("show_last_collected"):
        processed_data = [row for row in processed_data if row.get("row_num") == 1]

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

    summary_data = {
        "collection_count": total_count,
        "page": page,
        "page_length": page_length
    }

    return columns, data, summary_data, None, summary


# ============================================================
# COLUMNS
# ============================================================
def get_columns():
    return [
        {
            "label": "#",
            "fieldname": "row_no",
            "fieldtype": "Int",
            "width": 60,
        },
        {
            "label": "Purchase",
            "fieldname": "purchase",
            "fieldtype": "Link",
            "options": "Purchase",
            "width": 140,
        },
        {
            "label": "Vendor ID",
            "fieldname": "vendor_id",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 130,
        },
        {
            "label": "Vendor Name",
            "fieldname": "vendor_name",
            "width": 200,
        },
        {
            "label": "Payment Date",
            "fieldname": "payment_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Mode of Payment",
            "fieldname": "mode_of_payment",
            "fieldtype": "Link",
            "options": "Payment Type",
            "width": 140,
        },
        {
            "label": "Purchase Total",
            "fieldname": "amount_to_pay",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Amount Paid",
            "fieldname": "amount_paid",
            "fieldtype": "Currency",
            "width": 160,
        },
        {
            "label": "Current Balance",
            "fieldname": "amount_pending",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Business Person",
            "fieldname": "business_person",
            "fieldtype": "Link",
            "options": "Business Person",
            "width": 140,
        },
    ]

# ============================================================
# DATA (PAYMENT-WISE WITH RUNNING BALANCE)
# ============================================================
def get_data(filters):
    conditions = []
    values = {}

    if filters.get("purchase"):
        conditions.append("pc.purchase = %(purchase)s")
        values["purchase"] = filters["purchase"]

    if filters.get("vendor_id"):
        conditions.append("pc.vendor_id = %(vendor_id)s")
        values["vendor_id"] = filters["vendor_id"]

    if filters.get("from_date"):
        conditions.append("pc.payment_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("pc.payment_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("business_person"):
        conditions.append("pc.business_person = %(business_person)s")
        values["business_person"] = filters["business_person"]

    # ⭐ CORE FIX: ignore fully collected purchases
    if filters.get("only_pending"):
        conditions.append("""
            pc.purchase IN (
                SELECT name FROM `tabPurchase`
                WHERE balance_amount > 0
            )
        """)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = f"""
        SELECT
            pc.purchase,
            pc.vendor_id,
            pc.vendor_name,
            pc.payment_date,
            pc.mode_of_payment,
            p.grand_total AS amount_to_pay,
            pc.amount_paid,
            (
                p.grand_total -
                SUM(pc.amount_paid)
                OVER (
                    PARTITION BY pc.purchase
                    ORDER BY pc.payment_date, pc.creation
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                )
            ) AS amount_pending,
            bp.business_person_name AS business_person,
            ROW_NUMBER() OVER (
                PARTITION BY pc.purchase
                ORDER BY pc.payment_date DESC, pc.creation DESC
            ) as row_num
        FROM `tabPurchase Collection` pc
        INNER JOIN `tabPurchase` p ON p.name = pc.purchase
        LEFT JOIN `tabBusiness Person` bp ON bp.name = pc.business_person
        {where_clause}
        ORDER BY pc.purchase, pc.payment_date, pc.creation
    """

    return frappe.db.sql(query, values, as_dict=True)



# ============================================================
# SUMMARY (PURCHASE-WISE — FINAL TOTALS)
# ============================================================
def get_summary(data):
    purchase_map = {}
    total_paid = 0

    if data:
        for row in data:
            total_paid += flt(row.amount_paid)

            # keep last balance per purchase (latest payment)
            purchase_map[row.purchase] = {
                "to_pay": flt(row.amount_to_pay),
                "pending": flt(row.amount_pending),
            }

    total_to_pay = sum(v["to_pay"] for v in purchase_map.values())
    total_pending = sum(v["pending"] for v in purchase_map.values())

    return [
        {
            "label": "Total Collections",
            "value": len(data),
            "indicator": "Blue",
            "datatype": "Int",
        },
        {
            "label": "Total Amount To Pay",
            "value": total_to_pay,
            "indicator": "Blue",
            "datatype": "Currency",
        },
        {
            "label": "Total Amount Paid",
            "value": total_paid,
            "indicator": "Green",
            "datatype": "Currency",
        },
        {
            "label": "Total Amount Pending",
            "value": total_pending,
            "indicator": "Red",
            "datatype": "Currency",
        },
    ]
