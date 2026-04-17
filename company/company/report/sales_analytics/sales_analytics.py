import frappe
import json
from frappe.utils import flt

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
        # {"fieldname": "customer_id", "label": "Customer ID", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"fieldname": "customer_name", "label": "Customer Name", "fieldtype": "Data", "width": 220},
        {"fieldname": "location", "label": "Location", "fieldtype": "Data", "width": 160},
        {"fieldname": "customer_status", "label": "Status", "fieldtype": "Data", "width": 80},
        # {"fieldname": "billing_name", "label": "Company Name", "fieldtype": "Data", "width": 200},
        {"fieldname": "qty", "label": "Qty", "fieldtype": "Float", "width": 120},
        {"fieldname": "amount_exclusive", "label": "Invoice Total Excl. Tax", "fieldtype": "Currency", "width": 180},
        {"fieldname": "total_tax_amount", "label": "Total Tax", "fieldtype": "Currency", "width": 120},
        {"fieldname": "grand_total", "label": "Invoice Total", "fieldtype": "Currency", "width": 140},
        {"fieldname": "overall_discount", "label": "Discount", "fieldtype": "Currency", "width": 120},
        {"fieldname": "received_amount", "label": "Received", "fieldtype": "Currency", "width": 130},
        {"fieldname": "balance_amount", "label": "Pending", "fieldtype": "Currency", "width": 130},
        {"fieldname": "business_person_name", "label": "Business Person", "fieldtype": "Link", "options": "Business Person", "width": 150},
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
        customer = filters["customer"]
        if isinstance(customer, list):
            # Multiple customers selected — use IN clause
            placeholders = ", ".join([f"%(customer_{i})s" for i in range(len(customer))])
            conditions.append(f"inv.customer_id IN ({placeholders})")
            for i, c in enumerate(customer):
                values[f"customer_{i}"] = c
        else:
            conditions.append("inv.customer_id = %(customer)s")
            values["customer"] = customer

    if filters.get("invoice"):
        conditions.append("inv.name = %(invoice)s")
        values["invoice"] = filters["invoice"]

    if filters.get("billing_name"):
        conditions.append("inv.billing_name LIKE %(billing_name)s")
        values["billing_name"] = f"%{filters['billing_name']}%"

    if filters.get("gst_non_gst"):
        if filters["gst_non_gst"] == "Non-GST":
            conditions.append("inv.default_tax_type = 'Exempted'")
        elif filters["gst_non_gst"] == "GST":
            conditions.append("inv.default_tax_type != 'Exempted'")

    if filters.get("business_person_name"):
        conditions.append("inv.business_person_name = %(business_person_name)s")
        values["business_person_name"] = filters["business_person_name"]

    if filters.get("location"):
        location = filters["location"]
        if isinstance(location, list):
            # Multiple locations selected — use IN clause
            placeholders = ", ".join([f"%(location_{i})s" for i in range(len(location))])
            conditions.append(f"inv.location IN ({placeholders})")
            for i, l in enumerate(location):
                values[f"location_{i}"] = l
        else:
            conditions.append("inv.location = %(location)s")
            values["location"] = location

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
            SUM(child.tax_amount) AS total_tax_amount,
            SUM(child.sub_total - child.tax_amount) AS amount_exclusive,
            inv.location,
            bp.business_person_name,
            inv.grand_total,
            inv.total_amount,
            inv.overall_discount,
            inv.overall_discount_type,
            inv.received_amount,
            inv.balance_amount
        FROM `tabInvoice` inv
        LEFT JOIN `tabInvoice Items` child ON child.parent = inv.name
        LEFT JOIN `tabCustomer` cust ON cust.name = inv.customer_id
        LEFT JOIN `tabBusiness Person` bp ON bp.name = inv.business_person_name
        {where_clause}
        GROUP BY inv.name
        ORDER BY inv.invoice_date DESC, inv.name DESC
        {limit_clause}
        """,
        {**values, "limit": page_length, "offset": offset},
        as_dict=True,
    )

    # -------------------------------
    # POST-PROCESS DATA (New vs Old Logic)
    # -------------------------------
    # 1. Identify all customers in this data set
    customer_ids = list(set([row.customer_id for row in data if row.customer_id]))
    
    # 2. Map each customer to their FIRST EVER invoice ID
    first_invoice_map = {}
    if customer_ids:
        # Optimization: Fetch min creation/name for each customer in one go
        first_records = frappe.db.sql("""
            SELECT customer_id, name as first_invoice
            FROM `tabInvoice`
            WHERE (customer_id, creation) IN (
                SELECT customer_id, MIN(creation)
                FROM `tabInvoice`
                WHERE customer_id IN %s
                GROUP BY customer_id
            )
        """, (customer_ids,), as_dict=True)
        
        for r in first_records:
            first_invoice_map[r.customer_id] = r.first_invoice

    # 3. Apply labels and badges
    for i, row in enumerate(data, start=(1 if is_export else offset + 1)):
        row["row_no"] = i
        
        # If this is their first ever invoice, it is 'New'. Otherwise 'Old'.
        first_id = first_invoice_map.get(row.customer_id)
        status_label = "NEW" if (row.invoice_no == first_id) else "OLD"

        if is_export:
            row["customer_status"] = status_label
        else:
            color_bg = "#10b981" if status_label == "NEW" else "#3b82f6"
            # High-end styling: Bold uppercase with modern rounded pill design
            row["customer_status"] = f'''
                <span style="
                    background-color: {color_bg}; 
                    color: white; 
                    padding: 4px 10px; 
                    border-radius: 12px; 
                    font-size: 10px; 
                    font-weight: 800; 
                    display: inline-block;
                    line-height: 1;
                    letter-spacing: 0.5px;
                ">{status_label}</span>
            '''.strip()

        # Calculate Overall Discount Amount
        disc_amt = 0
        total_before_disc = flt(row.get("total_amount", 0))
        raw_disc = flt(row.get("overall_discount", 0))
        disc_type = row.get("overall_discount_type") or "Flat"

        if disc_type == "Percentage":
            disc_amt = total_before_disc * (raw_disc / 100)
        else:
            disc_amt = raw_disc
        
        row["overall_discount"] = disc_amt

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
            SUM(inv.balance_amount) AS total_pending,
            SUM(CASE 
                WHEN inv.overall_discount_type = 'Percentage' THEN (inv.total_amount * inv.overall_discount / 100)
                ELSE inv.overall_discount
            END) AS total_discount,
            SUM(tax_sub.total_tax) AS total_tax,
            SUM(tax_sub.total_excl) AS total_excl
        FROM `tabInvoice` inv
        LEFT JOIN (
            SELECT parent, SUM(tax_amount) as total_tax, SUM(sub_total - tax_amount) as total_excl
            FROM `tabInvoice Items`
            GROUP BY parent
        ) tax_sub ON tax_sub.parent = inv.name
        {where_clause}
        """,
        values,
        as_dict=True,
    )[0]

    total_sales = totals.total_sales or 0
    total_tax = totals.total_tax or 0
    total_excl = totals.total_excl or 0
    total_received = totals.total_received or 0
    total_pending = totals.total_pending or 0

    report_summary = [
        {
            "label": "Total Invoices",
            "value": total_count,
            "indicator": "green",
            "datatype": "Int"
        },
        {
            "label": "Total Sales (Excl. Tax)",
            "value": total_excl,
            "indicator": "blue",
            "datatype": "Currency"
        },
        {
            "label": "Total Sales Tax",
            "value": total_tax,
            "indicator": "blue",
            "datatype": "Currency"
        },
        {
            "label": "Total Sales",
            "value": total_sales,
            "datatype": "Currency",
            "indicator": "blue"
        },
        {
            "label": "Total Discount",
            "value": totals.total_discount or 0,
            "datatype": "Currency",
            "indicator": "red"
        },
        {
            "label": "Received",
            "value": total_received,
            "datatype": "Currency",
            "indicator": "green"
        },
        {
            "label": "Pending",
            "value": total_pending,
            "datatype": "Currency",
            "indicator": "red" if total_pending > 0 else "green"
        },
    ]

    summary_data = {
        "invoice_count": total_count,
        "page": page,
        "page_length": page_length
    }

    return columns, data, summary_data, None, report_summary
