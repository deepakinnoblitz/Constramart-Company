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
        last_collection_map = {}
        for d in processed_data:
            # Since we iterate in DESC order (latest first), 
            # we keep the first one we find for each purchase.
            purchase_id = d.get("purchase")
            if purchase_id not in last_collection_map:
                last_collection_map[purchase_id] = d
        processed_data = list(last_collection_map.values())

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
            "label": "Collection ID",
            "fieldname": "collection_id",
            "fieldtype": "Link",
            "options": "Purchase Collection",
            "width": 140,
        },
        {
            "label": "Purchase",
            "fieldname": "purchase",
            "fieldtype": "Link",
            "options": "Purchase",
            "width": 140,
        },
        {
            "label": "Purchase Date",
            "fieldname": "purchase_date",
            "fieldtype": "Date",
            "width": 120,
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
            "width": 180,
        },
        {
            "label": "Grand Purchase Total",
            "fieldname": "grand_total",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Amount Collected",
            "fieldname": "amount_paid",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Pending Amount",
            "fieldname": "amount_pending",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Collection Date",
            "fieldname": "payment_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Total Collection",
            "fieldname": "total_collected",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Mode of Payment",
            "fieldname": "mode_of_payment",
            "fieldtype": "Link",
            "options": "Payment Type",
            "width": 140,
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
        vendors = filters.get("vendor_id")
        if isinstance(vendors, str):
            vendors = [v.strip() for v in vendors.split(",") if v.strip()]
        if vendors:
            conditions.append("pc.vendor_id IN %(vendors)s")
            values["vendors"] = vendors

    if filters.get("from_date"):
        conditions.append("pc.payment_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("pc.payment_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("business_person"):
        conditions.append("pc.business_person = %(business_person)s")
        values["business_person"] = filters["business_person"]

    if filters.get("only_pending"):
        conditions.append("""
            pc.purchase IN (
                SELECT name FROM `tabPurchase`
                WHERE balance_amount > 0
            )
        """)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Fetch raw data in chronological order for accurate running total
    raw_results = frappe.db.sql(f"""
        SELECT
            pc.name AS collection_id,
            pc.purchase,
            p.bill_date AS purchase_date,
            pc.vendor_id,
            pc.vendor_name,
            pc.payment_date,
            pc.mode_of_payment,
            p.grand_total,
            pc.amount_paid,
            bp.business_person_name AS business_person,
            pc.creation
        FROM `tabPurchase Collection` pc
        INNER JOIN `tabPurchase` p ON p.name = pc.purchase
        LEFT JOIN `tabBusiness Person` bp ON bp.name = pc.business_person
        {where_clause}
        ORDER BY p.bill_date ASC, p.name ASC, pc.creation ASC
    """, values, as_dict=True)

    processed_data = []
    purchase_running_total = {}

    for d in raw_results:
        purchase_id = d.purchase
        if purchase_id not in purchase_running_total:
            purchase_running_total[purchase_id] = 0.0

        purchase_running_total[purchase_id] += flt(d.amount_paid)

        # Running total collected for this purchase
        d.total_collected = purchase_running_total[purchase_id]
        
        # New pending balance after this payment
        d.amount_pending = flt(d.grand_total) - d.total_collected
        
        processed_data.append(d)

    # Final sort for display (Newest Purchase & Newest Collection First)
    processed_data.sort(
        key=lambda x: (x.purchase_date, x.purchase, x.creation),
        reverse=True
    )

    return processed_data



# ============================================================
# SUMMARY (PURCHASE-WISE — FINAL TOTALS)
# ============================================================
def get_summary(data):
    total_to_pay = 0
    total_paid_sum = 0
    total_pending = 0
    
    unique_purchases = set()
    
    for d in data:
        total_paid_sum += flt(d.get("amount_paid"))
        
        purchase = d.get("purchase")
        if purchase not in unique_purchases:
            unique_purchases.add(purchase)
            # Take the state from the first record seen (which is the latest due to DESC sort)
            total_to_pay += flt(d.get("grand_total"))
            total_pending += flt(d.get("amount_pending"))

    return [
        {
            "label": "Total Collections",
            "value": len(unique_purchases),
            "indicator": "green",
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
            "value": total_paid_sum,
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
