import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    summary = get_summary(data)

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
            "label": "Meet For",
            "fieldname": "meet_for",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Lead / Reference",
            "fieldname": "lead_name",
            "fieldtype": "Dynamic Link",
            "options": "meet_for",
            "width": 160
        },
        {
            "label": "Meeting Venue",
            "fieldname": "meeting_venue",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "Location",
            "fieldname": "location",
            "fieldtype": "Data",
            "width": 160
        },
        {
            "label": "Meet Status",
            "fieldname": "outgoing_call_status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "Completed Status",
            "fieldname": "completed_meet_status",
            "fieldtype": "Data",
            "width": 220
        },
        {
            "label": "From",
            "fieldname": "from_time",
            "fieldtype": "Datetime",
            "width": 160
        },
        {
            "label": "To",
            "fieldname": "to_time",
            "fieldtype": "Datetime",
            "width": 160
        },
        {
            "label": "Owner",
            "fieldname": "owner_name",
            "fieldtype": "Link",
            "options": "User",
            "width": 150
        },
        {
            "label": "Reminder Enabled",
            "fieldname": "enable_reminder",
            "fieldtype": "Data",
            "width": 140
        }
    ]


# ------------------------------------------------------
# DATA
# ------------------------------------------------------
def get_data(filters):
    conditions = []
    values = {}

    if filters.get("from_date"):
        conditions.append("`from` >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("`from` <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("meet_for"):
        conditions.append("meet_for = %(meet_for)s")
        values["meet_for"] = filters["meet_for"]

    if filters.get("status"):
        conditions.append("outgoing_call_status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("owner"):
        conditions.append("owner_name = %(owner)s")
        values["owner"] = filters["owner"]

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
            meet_for,
            lead_name,
            meeting_venue,
            location,
            outgoing_call_status,
            completed_meet_status,
            `from` AS from_time,
            `to` AS to_time,
            owner_name,
            CASE
                WHEN enable_reminder = 1 THEN 'Yes'
                ELSE 'No'
            END AS enable_reminder
        FROM `tabMeeting`
        {where_clause}
        ORDER BY `from` DESC
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
    reminders = sum(1 for d in data if d.get("enable_reminder") == "Yes")

    return [
        {
            "label": "Total Meetings",
            "value": total,
            "indicator": "Blue"
        },
        {
            "label": "Scheduled Meetings",
            "value": scheduled,
            "indicator": "Orange"
        },
        {
            "label": "Completed Meetings",
            "value": completed,
            "indicator": "Green"
        },
        {
            "label": "Reminder Enabled",
            "value": reminders,
            "indicator": "Purple"
        }
    ]
