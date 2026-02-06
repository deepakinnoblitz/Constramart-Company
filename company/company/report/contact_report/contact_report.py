import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    summary = get_summary(data)

    # Return order is important
    return columns, data, None, None, summary


# ------------------------------------------------------
# COLUMNS
# ------------------------------------------------------
def get_columns():
    return [
        {"label": "Name", "fieldname": "first_name", "fieldtype": "Data", "width": 180},
        {"label": "Company", "fieldname": "company_name", "fieldtype": "Data", "width": 180},
        {"label": "Email", "fieldname": "email", "fieldtype": "Data", "width": 200},
        {"label": "Phone", "fieldname": "phone", "fieldtype": "Phone", "width": 140},
        {"label": "Designation", "fieldname": "designation", "fieldtype": "Data", "width": 140},
        {"label": "Country", "fieldname": "country", "fieldtype": "Link", "options": "Country", "width": 120},
        {"label": "State", "fieldname": "state", "fieldtype": "Data", "width": 120},
        {"label": "City", "fieldname": "city", "fieldtype": "Data", "width": 120},
        {"label": "Source Lead", "fieldname": "source_lead", "fieldtype": "Link", "options": "Lead", "width": 150},
        {"label": "Owner", "fieldname": "owner_name", "fieldtype": "Link", "options": "User", "width": 150},
    ]


# ------------------------------------------------------
# DATA
# ------------------------------------------------------
def get_data(filters):
    conditions = []
    values = {}

    if filters.get("country"):
        conditions.append("country = %(country)s")
        values["country"] = filters["country"]

    if filters.get("state"):
        conditions.append("state = %(state)s")
        values["state"] = filters["state"]

    if filters.get("city"):
        conditions.append("city = %(city)s")
        values["city"] = filters["city"]

    if filters.get("source_lead"):
        conditions.append("source_lead = %(source_lead)s")
        values["source_lead"] = filters["source_lead"]

    if filters.get("owner"):
        conditions.append("owner_name = %(owner)s")
        values["owner"] = filters["owner"]

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    return frappe.db.sql(
        f"""
        SELECT
            first_name,
            company_name,
            email,
            phone,
            designation,
            country,
            state,
            city,
            source_lead,
            owner_name
        FROM `tabContacts`
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
    with_email = sum(1 for d in data if d.get("email"))
    with_phone = sum(1 for d in data if d.get("phone"))
    converted_from_lead = sum(1 for d in data if d.get("source_lead"))

    return [
        {
            "label": "Total Contacts",
            "value": total,
            "indicator": "Blue"
        },
        {
            "label": "With Email",
            "value": with_email,
            "indicator": "Green"
        },
        {
            "label": "With Phone",
            "value": with_phone,
            "indicator": "Orange"
        },
        {
            "label": "Converted from Lead",
            "value": converted_from_lead,
            "indicator": "Purple"
        }
    ]
