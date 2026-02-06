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
        {
            "label": "Title",
            "fieldname": "title",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Call For",
            "fieldname": "call_for",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Lead / Reference",
            "fieldname": "lead_name",
            "fieldtype": "Dynamic Link",
            "options": "call_for",
            "width": 160
        },
        {
            "label": "Call Status",
            "fieldname": "outgoing_call_status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Completed Status",
            "fieldname": "completed_call_status",
            "fieldtype": "Data",
            "width": 220
        },
        {
            "label": "Call Start",
            "fieldname": "call_start_time",
            "fieldtype": "Datetime",
            "width": 160
        },
        {
            "label": "Call End",
            "fieldname": "call_end_time",
            "fieldtype": "Datetime",
            "width": 160
        },
        {
            "label": "Call Owner",
            "fieldname": "owner_name",
            "fieldtype": "Link",
            "options": "User",
            "width": 150
        },
        {
            "label": "Reminder Enabled",
            "fieldname": "enable_reminder",
            "fieldtype": "Check",
            "width": 120
        }
    ]


# ------------------------------------------------------
# DATA
# ------------------------------------------------------
def get_data(filters):
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("call_start_time >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("call_start_time <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("call_for"):
        conditions.append("call_for = %(call_for)s")
        values["call_for"] = filters["call_for"]

    if filters.get("status"):
        conditions.append("outgoing_call_status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("owner_name"):
        conditions.append("owner_name = %(owner_name)s")
        values["owner_name"] = filters["owner_name"]

    if filters.get("enable_reminder") is not None:
        conditions.append("enable_reminder = %(enable_reminder)s")
        values["enable_reminder"] = filters["enable_reminder"]

    where_clause = " AND ".join(conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause

    return frappe.db.sql(
        f"""
        SELECT
            title,
            call_for,
            lead_name,
            outgoing_call_status,
            completed_call_status,
            call_start_time,
            call_end_time,
            owner_name,
            enable_reminder
        FROM `tabCalls`
        {where_clause}
        ORDER BY call_start_time DESC
        """,
        values,
        as_dict=True
    )


# ------------------------------------------------------
# SUMMARY (KPI CARDS)
# ------------------------------------------------------
def get_summary(data):
    total = len(data)
    scheduled = sum(1 for d in data if d.get("outgoing_call_status") == "Scheduled")
    completed = sum(1 for d in data if d.get("outgoing_call_status") == "Completed")
    reminders = sum(1 for d in data if d.get("enable_reminder"))

    return [
        {
            "label": "Total Calls",
            "value": total,
            "indicator": "Blue"
        },
        {
            "label": "Scheduled Calls",
            "value": scheduled,
            "indicator": "Orange"
        },
        {
            "label": "Completed Calls",
            "value": completed,
            "indicator": "Green"
        },
        {
            "label": "Reminder Enabled",
            "value": reminders,
            "indicator": "Purple"
        }
    ]
