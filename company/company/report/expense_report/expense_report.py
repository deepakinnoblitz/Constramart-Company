import frappe
from frappe.utils import flt
import json


def execute(filters=None):

    # Convert JSON to dict if needed
    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = filters or {}

    columns = get_columns()
    data = get_data(filters)
    summary = get_summary(data)

    # MUST return 5 items for Frappe Query Report
    return columns, data, None, None, summary


# ---------------------------------------------------
#  COLUMNS
# ---------------------------------------------------
def get_columns():
    return [
        {"label": "Expense No", "fieldname": "expense_no", "fieldtype": "Link", "options": "Expenses", "width": 130},
        {"label": "Expense Category", "fieldname": "expense_category", "fieldtype": "Data", "width": 140},
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 110},
        {"label": "Payment Type", "fieldname": "payment_type", "fieldtype": "Link", "options": "Payment Type", "width": 120},

        {"label": "Item", "fieldname": "items", "fieldtype": "Data", "width": 150},
        {"label": "Quantity", "fieldname": "quantity", "fieldtype": "Float", "width": 80},
        {"label": "Price", "fieldname": "price", "fieldtype": "Currency", "width": 100},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},

        {"label": "Total", "fieldname": "total", "fieldtype": "Currency", "width": 130},
    ]


# ---------------------------------------------------
#  DATA
# ---------------------------------------------------
def get_data(filters):
    conditions = []

    if filters.get("expense_category"):
        conditions.append(f"e.expense_category LIKE '%{filters['expense_category']}%'")

    if filters.get("payment_type"):
        conditions.append(f"e.payment_type = '{filters['payment_type']}'")

    if filters.get("from_date"):
        conditions.append(f"e.date >= '{filters['from_date']}'")

    if filters.get("to_date"):
        conditions.append(f"e.date <= '{filters['to_date']}'")

    condition_sql = " AND ".join(conditions)
    if condition_sql:
        condition_sql = "WHERE " + condition_sql

    query = f"""
        SELECT
            e.expense_no,
            e.expense_category,
            e.date,
            e.payment_type,
            e.total,

            c.items,
            c.quantity,
            c.price,
            c.amount

        FROM `tabExpenses` e
        LEFT JOIN `tabExpenses Items` c ON c.parent = e.name
        {condition_sql}
        ORDER BY e.date DESC
    """

    return frappe.db.sql(query, as_dict=True)


# ---------------------------------------------------
#  SUMMARY
# ---------------------------------------------------
def get_summary(data):

    total_expense = sum(flt(d.get("total")) for d in data)
    total_amount = sum(flt(d.get("amount")) for d in data)
    total_qty = sum(flt(d.get("quantity")) for d in data)

    return [
        {"label": "Total Expense Amount", "value": total_expense, "indicator": "blue", "datatype": "Currency"},
        {"label": "Total Quantity", "value": total_qty, "indicator": "green", "datatype": "Float"},
        {"label": "Total Item Amount", "value": total_amount, "indicator": "orange", "datatype": "Currency"},
    ]


