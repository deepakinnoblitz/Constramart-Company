import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    summary = get_summary(data)

    # Order is important
    return columns, data, None, None, summary


# ------------------------------------------------------
# COLUMNS
# ------------------------------------------------------
def get_columns():
    return [
        {
            "label": "Account Name",
            "fieldname": "account_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Phone Number",
            "fieldname": "phone_number",
            "fieldtype": "Phone",
            "width": 140
        },
        {
            "label": "Website",
            "fieldname": "website",
            "fieldtype": "Data",
            "width": 180
        },
        {
            "label": "GSTIN",
            "fieldname": "gstin",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": "Account Owner",
            "fieldname": "account_owner",
            "fieldtype": "Data",
            "width": 160
        },
        {
            "label": "Country",
            "fieldname": "country",
            "fieldtype": "Link",
            "options": "Country",
            "width": 120
        },
        {
            "label": "State",
            "fieldname": "state",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "City",
            "fieldname": "city",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Owner",
            "fieldname": "owner_name",
            "fieldtype": "Link",
            "options": "User",
            "width": 150
        }
    ]


# ------------------------------------------------------
# DATA
# ------------------------------------------------------
def get_data(filters):
    conditions = []
    values = {}

    if filters.get("account_name"):
        conditions.append("account_name LIKE %(account_name)s")
        values["account_name"] = f"%{filters['account_name']}%"

    if filters.get("country"):
        conditions.append("country = %(country)s")
        values["country"] = filters["country"]

    if filters.get("state"):
        conditions.append("state = %(state)s")
        values["state"] = filters["state"]

    if filters.get("city"):
        conditions.append("city = %(city)s")
        values["city"] = filters["city"]

    if filters.get("owner"):
        conditions.append("owner_name = %(owner)s")
        values["owner"] = filters["owner"]

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    return frappe.db.sql(
        f"""
        SELECT
            account_name,
            phone_number,
            website,
            gstin,
            account_owner,
            country,
            state,
            city,
            owner_name
        FROM `tabAccounts`
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
    with_gstin = sum(1 for d in data if d.get("gstin"))
    with_website = sum(1 for d in data if d.get("website"))
    with_phone = sum(1 for d in data if d.get("phone_number"))

    return [
        {
            "label": "Total Accounts",
            "value": total,
            "indicator": "Blue"
        },
        {
            "label": "With GSTIN",
            "value": with_gstin,
            "indicator": "Green"
        },
        {
            "label": "With Website",
            "value": with_website,
            "indicator": "Purple"
        },
        {
            "label": "With Phone",
            "value": with_phone,
            "indicator": "Orange"
        }
    ]
