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
    # Detect if we are exporting
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

    columns = get_columns()
    
    if is_export:
        data = get_data(filters, limit=None, offset=None)
        # For export, row numbers should start from 1
        for i, row in enumerate(data, start=1):
            row["row_no"] = i
    else:
        data = get_data(filters, limit=page_length, offset=offset)
        # Calculate row numbers for paginated view
        for i, row in enumerate(data, start=offset + 1):
            row["row_no"] = i

    # Total Count logic (approximate for pagination)
    total_count = get_total_count(filters)

    # Summaries
    report_summary = get_report_summary(filters)

    summary_data = {
        "total_count": total_count,
        "page": page,
        "page_length": page_length
    }

    return columns, data, summary_data, None, report_summary


def get_columns():
    return [
        {"fieldname": "row_no", "label": "#", "fieldtype": "Int", "width": 60},
        {"fieldname": "invoice_no", "label": "Invoice No", "fieldtype": "Link", "options": "Invoice", "width": 140},
        {"fieldname": "invoice_date", "label": "Inv Date", "fieldtype": "Date", "width": 110},
        {"fieldname": "customer_id", "label": "Customer", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"fieldname": "sales_amount", "label": "Sales Amt", "fieldtype": "Currency", "width": 120},
        {"fieldname": "purchase_nos", "label": "Purchase IDs", "fieldtype": "Data", "width": 180},
        {"fieldname": "vendor_names", "label": "Vendor(s)", "fieldtype": "Data", "width": 180},
        {"fieldname": "purchase_amount", "label": "Purchase Amt", "fieldtype": "Currency", "width": 120},
        {"fieldname": "gross_profit", "label": "Profit", "fieldtype": "Currency", "width": 110},
        {"fieldname": "margin_percent", "label": "Margin %", "fieldtype": "Percent", "width": 90},
    ]


def get_data(filters, limit=None, offset=None):
    conditions, values = get_conditions(filters)
    
    # Main logic: Link Invoices and Purchases using UNION to catch both directions
    # Then group by Invoice to handle Many-to-One and One-to-Many
    
    limit_clause = f"LIMIT {limit} OFFSET {offset}" if limit is not None else ""

    having_clause = "HAVING SUM(CASE WHEN pur.name IS NOT NULL THEN 1 ELSE 0 END) > 0" if filters.get("only_linked") else ""

    query = f"""
        SELECT 
            inv.name as invoice_no,
            inv.invoice_date,
            inv.customer_id,
            inv.grand_total as sales_amount,
            GROUP_CONCAT(DISTINCT pur.name) as purchase_nos,
            GROUP_CONCAT(DISTINCT pur.vendor_name) as vendor_names,
            SUM(COALESCE(pur.grand_total, 0)) as purchase_amount,
            (inv.grand_total - SUM(COALESCE(pur.grand_total, 0))) as gross_profit,
            CASE 
                WHEN inv.grand_total > 0 THEN ((inv.grand_total - SUM(COALESCE(pur.grand_total, 0))) / inv.grand_total) * 100
                ELSE 0 
            END as margin_percent
        FROM `tabInvoice` inv
        LEFT JOIN `tabPurchase` pur ON (pur.reference_invoice = inv.name OR inv.purchase_id = pur.name)
        {conditions}
        GROUP BY inv.name
        {having_clause}
        ORDER BY inv.invoice_date DESC, inv.creation DESC
        {limit_clause}
    """
    
    return frappe.db.sql(query, values, as_dict=True)


def get_conditions(filters):
    conditions = []
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

    if filters.get("vendor"):
        # This is tricky because vendor is on the purchase side
        # We need a subquery or stay with the join
        conditions.append("EXISTS (SELECT name FROM `tabPurchase` p WHERE (p.reference_invoice = inv.name OR inv.purchase_id = p.name) AND p.vendor_id = %(vendor)s)")
        values["vendor"] = filters["vendor"]

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where_clause, values


def get_total_count(filters):
    conditions, values = get_conditions(filters)
    having_clause = "HAVING SUM(CASE WHEN pur.name IS NOT NULL THEN 1 ELSE 0 END) > 0" if filters.get("only_linked") else ""
    return frappe.db.sql(f"""
        SELECT COUNT(*) FROM (
            SELECT inv.name 
            FROM `tabInvoice` inv 
            LEFT JOIN `tabPurchase` pur ON (pur.reference_invoice = inv.name OR inv.purchase_id = pur.name)
            {conditions} 
            GROUP BY inv.name
            {having_clause}
        ) as sub
    """, values)[0][0]


def get_report_summary(filters):
    conditions, values = get_conditions(filters)
    having_clause = "HAVING SUM(CASE WHEN pur.name IS NOT NULL THEN 1 ELSE 0 END) > 0" if filters.get("only_linked") else ""
    
    # We need to sum up based on the grouped view
    totals = frappe.db.sql(f"""
        SELECT 
            SUM(sales_amount) as total_sales,
            SUM(purchase_amount) as total_purchase,
            SUM(gross_profit) as total_profit
        FROM (
            SELECT 
                inv.grand_total as sales_amount,
                SUM(COALESCE(pur.grand_total, 0)) as purchase_amount,
                (inv.grand_total - SUM(COALESCE(pur.grand_total, 0))) as gross_profit
            FROM `tabInvoice` inv
            LEFT JOIN `tabPurchase` pur ON (pur.reference_invoice = inv.name OR inv.purchase_id = pur.name)
            {conditions}
            GROUP BY inv.name
            {having_clause}
        ) as sub
    """, values, as_dict=True)[0]

    total_sales = totals.total_sales or 0
    total_purchase = totals.total_purchase or 0
    total_profit = totals.total_profit or 0
    avg_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0

    return [
        {"label": "Total Revenue", "value": total_sales, "indicator": "blue", "datatype": "Currency"},
        {"label": "Total Purchase Cost", "value": total_purchase, "indicator": "red", "datatype": "Currency"},
        {"label": "Gross Profit", "value": total_profit, "indicator": "green" if total_profit >= 0 else "red", "datatype": "Currency"},
        {"label": "Average Margin", "value": f"{avg_margin:.1f}%", "indicator": "green" if avg_margin >= 10 else "orange", "datatype": "Data"}
    ]
