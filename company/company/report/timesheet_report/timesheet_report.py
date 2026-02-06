import frappe
import json
from frappe.utils import getdate

def execute(filters=None):

    # Ensure filters is proper dict
    if isinstance(filters, str):
        filters = json.loads(filters)
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    # --- Calculate Total Hours ---
    total_hours = sum([d.get("hours", 0) for d in data])
    entry_count = len(data)

    # --- Add Summary Row at Bottom ---
    if data:
        data.append({
            "employee": "",
            "employee_name": "",
            "project": "",
            "activity_type": "",
            "timesheet_date": "TOTAL",
            "hours": total_hours,
            "description": ""
        })

    # --- Summary Box on Right Side ---
    report_summary = [
        {
            "label": "Total Hours",
            "value": total_hours,
            "indicator": "Green",
            "datatype": "Float"
        },
        {
            "label": "Total Entries",
            "value": entry_count,
            "indicator": "Blue",
            "datatype": "Int"
        }
    ]

    # --- Summary Section ABOVE TABLE ---
    summary_data = {
        "total_hours": total_hours,
        "total_entries": entry_count
    }

    # Return: columns, data, message/summary_section, chart, summary_cards
    return columns, data, summary_data, None, report_summary


def get_columns():
    return [
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 180},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 150},
        {"label": "Project", "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 150},
        {"label": "Activity Type", "fieldname": "activity_type", "fieldtype": "Link", "options": "Activity Type", "width": 250},
        {"label": "Timesheet Date", "fieldname": "timesheet_date", "fieldtype": "Data", "width": 120},
        {"label": "Hours", "fieldname": "hours", "fieldtype": "Float", "width": 100},
        {"label": "Description", "fieldname": "description", "fieldtype": "Data", "width": 300}
    ]


def get_conditions(filters):
    conditions = ""

    if filters.get("employee"):
        conditions += " AND ts.employee = %(employee)s"

    if filters.get("project"):
        conditions += " AND tse.project = %(project)s"

    if filters.get("activity_type"):
        conditions += " AND tse.activity_type = %(activity_type)s"

    if filters.get("from_date"):
        conditions += " AND ts.timesheet_date >= %(from_date)s"

    if filters.get("to_date"):
        conditions += " AND ts.timesheet_date <= %(to_date)s"

    return conditions


def get_data(filters):
    conditions = get_conditions(filters)

    query = f"""
        SELECT
            ts.employee,
            ts.employee_name,
            tse.project,
            tse.activity_type,
            DATE_FORMAT(ts.timesheet_date, '%%d-%%m-%%Y') AS timesheet_date,
            tse.hours,
            tse.description
        FROM `tabTimesheet` ts
        INNER JOIN `tabTimesheet Entries` tse
            ON tse.parent = ts.name
        WHERE 1 = 1 {conditions}
        ORDER BY ts.timesheet_date DESC
    """

    return frappe.db.sql(query, filters, as_dict=True)
