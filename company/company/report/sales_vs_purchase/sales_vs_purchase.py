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
    else:
        data = get_data(filters, limit=page_length, offset=offset)

    # -------------------------------
    # POST-PROCESS DATA (New vs Old Logic)
    # -------------------------------
    customer_ids = list(set([row.customer_id for row in data if row.customer_id]))
    first_invoice_map = {}
    if customer_ids:
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

    # Apply row numbers and badges
    for i, row in enumerate(data, start=(1 if is_export else offset + 1)):
        row["row_no"] = i
        
        # Determine status: Only the first ever invoice for a customer is 'New'
        first_id = first_invoice_map.get(row.customer_id)
        status_label = "NEW" if (row.invoice_no == first_id) else "OLD"

        if is_export:
            row["customer_status"] = status_label
        else:
            color_bg = "#10b981" if status_label == "NEW" else "#3b82f6"
            # High-end styling: Bold uppercase with modern rounded pill design
            row["customer_status"] = f'''
                <span style="background-color: {color_bg}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 10px; font-weight: 800; display: inline-block; line-height: 1; letter-spacing: 0.5px;">{status_label}</span>
            '''.strip()

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
        {"fieldname": "customer_name", "label": "Customer Name", "fieldtype": "Data", "width": 180},
        {"fieldname": "location", "label": "Location", "fieldtype": "Data", "width": 160},
        {"fieldname": "customer_status", "label": "Status", "fieldtype": "Data", "width": 80},
        {"fieldname": "amount_exclusive", "label": "Sales Amt (Excl. Tax)", "fieldtype": "Currency", "width": 160},
        {"fieldname": "total_tax_amount", "label": "Tax Amount", "fieldtype": "Currency", "width": 130},
        {"fieldname": "sales_amount", "label": "Sales Amt", "fieldtype": "Currency", "width": 140},
        {"fieldname": "purchase_nos", "label": "Purchase No", "fieldtype": "Data", "width": 120},
        {"fieldname": "purchase_dates", "label": "Pur Date", "fieldtype": "Data", "width": 110},
        {"fieldname": "vendor_names", "label": "Vendor(s)", "fieldtype": "Data", "width": 180},
        {"fieldname": "purchase_amount_exclusive", "label": "Pur Amt (Excl. Tax)", "fieldtype": "Currency", "width": 160},
        {"fieldname": "purchase_total_tax_amount", "label": "Pur Tax Amount", "fieldtype": "Currency", "width": 130},
        {"fieldname": "purchase_amount", "label": "Purchase Amt", "fieldtype": "Currency", "width": 140},
        {"fieldname": "gross_profit", "label": "Profit", "fieldtype": "Currency", "width": 140},
        {"fieldname": "margin_percent", "label": "Margin %", "fieldtype": "Percent", "width": 110},
        {"fieldname": "sales_business_person", "label": "Sales BP", "fieldtype": "Link", "options": "Business Person", "width": 130},
        {"fieldname": "purchase_business_person", "label": "Purchase BP", "fieldtype": "Data", "width": 150},
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
            inv.customer_name,
            inv.location,
            inv_totals.amount_exclusive,
            inv_totals.total_tax_amount,
            inv.grand_total as sales_amount,
            GROUP_CONCAT(DISTINCT pur.name) as purchase_nos,
            GROUP_CONCAT(DISTINCT pur.bill_date) as purchase_dates,
            GROUP_CONCAT(DISTINCT pur.vendor_name) as vendor_names,
            SUM(COALESCE(pur_totals.pur_excl, 0)) as purchase_amount_exclusive,
            SUM(COALESCE(pur_totals.pur_tax, 0)) as purchase_total_tax_amount,
            SUM(COALESCE(pur.grand_total, 0)) as purchase_amount,
            (inv.grand_total - SUM(COALESCE(pur.grand_total, 0))) as gross_profit,
            CASE 
                WHEN inv.grand_total > 0 THEN ((inv.grand_total - SUM(COALESCE(pur.grand_total, 0))) / inv.grand_total) * 100
                ELSE 0 
            END as margin_percent,
            sbp.business_person_name as sales_business_person,
            GROUP_CONCAT(DISTINCT pbp.business_person_name) as purchase_business_person
        FROM `tabInvoice` inv
        LEFT JOIN (
            SELECT parent, SUM(tax_amount) as total_tax_amount, SUM(sub_total - tax_amount) as amount_exclusive
            FROM `tabInvoice Items`
            GROUP BY parent
        ) inv_totals ON inv_totals.parent = inv.name
        LEFT JOIN `tabPurchase` pur ON (pur.reference_invoice = inv.name OR pur.invoice_id = inv.name OR inv.purchase_id = pur.name OR inv.reference_purchase = pur.name)
        LEFT JOIN (
            SELECT parent, SUM(tax_amount) as pur_tax, SUM(sub_total - tax_amount) as pur_excl
            FROM `tabPurchase Items`
            GROUP BY parent
        ) pur_totals ON pur_totals.parent = pur.name
        LEFT JOIN `tabBusiness Person` sbp ON sbp.name = inv.business_person_name
        LEFT JOIN `tabBusiness Person` pbp ON pbp.name = pur.business_person_name
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
        customer = filters["customer"]
        if isinstance(customer, list):
            placeholders = ", ".join([f"%(customer_{i})s" for i in range(len(customer))])
            conditions.append(f"inv.customer_id IN ({placeholders})")
            for i, c in enumerate(customer):
                values[f"customer_{i}"] = c
        else:
            conditions.append("inv.customer_id = %(customer)s")
            values["customer"] = customer
    
    if filters.get("location"):
        location = filters["location"]
        if isinstance(location, list):
            placeholders = ", ".join([f"%(location_{i})s" for i in range(len(location))])
            conditions.append(f"inv.location IN ({placeholders})")
            for i, loc in enumerate(location):
                values[f"location_{i}"] = loc
        else:
            conditions.append("inv.location = %(location)s")
            values["location"] = location

    if filters.get("vendor"):
        vendor = filters["vendor"]
        if isinstance(vendor, list):
            placeholders = ", ".join([f"%(vendor_{i})s" for i in range(len(vendor))])
            conditions.append(f"EXISTS (SELECT name FROM `tabPurchase` p WHERE (p.reference_invoice = inv.name OR p.invoice_id = inv.name OR inv.purchase_id = p.name OR inv.reference_purchase = p.name) AND p.vendor_id IN ({placeholders}))")
            for i, v in enumerate(vendor):
                values[f"vendor_{i}"] = v
        else:
            conditions.append(f"EXISTS (SELECT name FROM `tabPurchase` p WHERE (p.reference_invoice = inv.name OR p.invoice_id = inv.name OR inv.purchase_id = p.name OR inv.reference_purchase = p.name) AND p.vendor_id = %(vendor)s)")
            values["vendor"] = vendor

    if filters.get("sales_business_person"):
        conditions.append("inv.business_person_name = %(sales_business_person)s")
        values["sales_business_person"] = filters["sales_business_person"]

    if filters.get("purchase_business_person"):
        conditions.append(f"EXISTS (SELECT name FROM `tabPurchase` p WHERE (p.reference_invoice = inv.name OR p.invoice_id = inv.name OR inv.purchase_id = p.name OR inv.reference_purchase = p.name) AND p.business_person_name = %(purchase_business_person)s)")
        values["purchase_business_person"] = filters["purchase_business_person"]

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where_clause, values


def get_total_count(filters):
    conditions, values = get_conditions(filters)
    having_clause = "HAVING SUM(CASE WHEN pur.name IS NOT NULL THEN 1 ELSE 0 END) > 0" if filters.get("only_linked") else ""
    return frappe.db.sql(f"""
        SELECT COUNT(*) FROM (
            SELECT inv.name 
            FROM `tabInvoice` inv 
            LEFT JOIN `tabPurchase` pur ON (pur.reference_invoice = inv.name OR pur.invoice_id = inv.name OR inv.purchase_id = pur.name OR inv.reference_purchase = pur.name)
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
            SUM(amount_exclusive) as total_sales_excl_tax,
            SUM(total_tax_amount) as total_tax,
            SUM(purchase_amount_exclusive) as total_purchase_excl_tax,
            SUM(purchase_total_tax_amount) as total_purchase_tax,
            SUM(purchase_amount) as total_purchase,
            SUM(gross_profit) as total_profit
        FROM (
            SELECT 
                inv.grand_total as sales_amount,
                inv_totals.amount_exclusive,
                inv_totals.total_tax_amount,
                SUM(COALESCE(pur_totals.pur_excl, 0)) as purchase_amount_exclusive,
                SUM(COALESCE(pur_totals.pur_tax, 0)) as purchase_total_tax_amount,
                SUM(COALESCE(pur.grand_total, 0)) as purchase_amount,
                (inv.grand_total - SUM(COALESCE(pur.grand_total, 0))) as gross_profit
            FROM `tabInvoice` inv
            LEFT JOIN (
                SELECT parent, SUM(tax_amount) as total_tax_amount, SUM(sub_total - tax_amount) as amount_exclusive
                FROM `tabInvoice Items`
                GROUP BY parent
            ) inv_totals ON inv_totals.parent = inv.name
            LEFT JOIN `tabPurchase` pur ON (pur.reference_invoice = inv.name OR pur.invoice_id = inv.name OR inv.purchase_id = pur.name OR inv.reference_purchase = pur.name)
            LEFT JOIN (
                SELECT parent, SUM(tax_amount) as pur_tax, SUM(sub_total - tax_amount) as pur_excl
                FROM `tabPurchase Items`
                GROUP BY parent
            ) pur_totals ON pur_totals.parent = pur.name
            {conditions}
            GROUP BY inv.name
            {having_clause}
        ) as sub
    """, values, as_dict=True)[0]

    total_sales = totals.total_sales or 0
    total_sales_excl_tax = totals.total_sales_excl_tax or 0
    total_tax = totals.total_tax or 0
    total_purchase = totals.total_purchase or 0
    total_purchase_excl_tax = totals.total_purchase_excl_tax or 0
    total_purchase_tax = totals.total_purchase_tax or 0
    total_profit = totals.total_profit or 0
    avg_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0

    return [
        {"label": "Total Invoice and Purchase", "value": get_total_count(filters), "indicator": "green", "datatype": "Int"},
        
        {"label": "Total Sales (Excl. Tax)", "value": total_sales_excl_tax, "indicator": "blue", "datatype": "Currency"},
        {"label": "Total Sales Tax", "value": total_tax, "indicator": "blue", "datatype": "Currency"},
        {"label": "Total Revenue", "value": total_sales, "indicator": "blue", "datatype": "Currency"},
        
        {"label": "Total Purchase (Excl. Tax)", "value": total_purchase_excl_tax, "indicator": "red", "datatype": "Currency"},
        {"label": "Total Purchase Tax", "value": total_purchase_tax, "indicator": "red", "datatype": "Currency"},
        {"label": "Total Purchase Cost", "value": total_purchase, "indicator": "red", "datatype": "Currency"},
        
        {"label": "Gross Profit", "value": total_profit, "indicator": "green" if total_profit >= 0 else "red", "datatype": "Currency"},
        # {"label": "Average Margin", "value": f"{avg_margin:.1f}%", "indicator": "green" if avg_margin >= 10 else "orange", "datatype": "Data"}
    ]
