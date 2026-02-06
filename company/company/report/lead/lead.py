import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    summary = get_summary(data)

    # IMPORTANT ORDER
    return columns, data, None, None, summary


# ------------------------------------------------------
# COLUMNS
# ------------------------------------------------------
def get_columns():
    return [
        {"label": "Lead Name", "fieldname": "lead_name", "fieldtype": "Data", "width": 180},
        {"label": "Company", "fieldname": "company_name", "fieldtype": "Data", "width": 180},
        {"label": "Phone", "fieldname": "phone_number", "fieldtype": "Phone", "width": 140},
        {"label": "Email", "fieldname": "email", "fieldtype": "Data", "width": 180},
        {"label": "Service", "fieldname": "service", "fieldtype": "Link", "options": "Service", "width": 140},
        {"label": "Leads Type", "fieldname": "leads_type", "fieldtype": "Data", "width": 100},
        {"label": "Leads From", "fieldname": "leads_from", "fieldtype": "Link", "options": "Lead From", "width": 100},
        {"label": "Owner", "fieldname": "owner_name", "fieldtype": "Link", "options": "User", "width": 150},
    ]


# ------------------------------------------------------
# DATA
# ------------------------------------------------------
def get_data(filters):
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("creation >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("creation <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("leads_type"):
        conditions.append("leads_type = %(leads_type)s")
        values["leads_type"] = filters["leads_type"]

    if filters.get("leads_from"):
        conditions.append("leads_from = %(leads_from)s")
        values["leads_from"] = filters["leads_from"]

    if filters.get("owner"):
        conditions.append("owner_name = %(owner)s")
        values["owner"] = filters["owner"]

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    return frappe.db.sql(
        f"""
        SELECT
            lead_name,
            company_name,
            phone_number,
            email,
            service,
            leads_type,
            leads_from,
            owner_name,
            creation
        FROM `tabLead`
        {where_clause}
        ORDER BY creation DESC
        """,
        values,
        as_dict=True
    )


# ------------------------------------------------------
# SUMMARY (KPI CARDS)
# ------------------------------------------------------
def get_summary(data):
    total = len(data)
    incoming = sum(1 for d in data if d.get("leads_type") == "Incoming")
    outgoing = sum(1 for d in data if d.get("leads_type") == "Outgoing")

    return [
        {
            "label": "Total Leads",
            "value": total,
            "indicator": "Blue"
        },
        {
            "label": "Incoming Leads",
            "value": incoming,
            "indicator": "Green"
        },
        {
            "label": "Outgoing Leads",
            "value": outgoing,
            "indicator": "Orange"
        }
    ]


