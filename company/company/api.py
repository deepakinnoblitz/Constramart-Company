import frappe
import json
import os
from frappe import _
from frappe.utils import (
    getdate,
    get_first_day,
    get_last_day,
    add_days,
    add_months,
    flt,
    today,
    formatdate,
    get_date_str
)

from datetime import datetime, timedelta
from calendar import monthrange
from frappe.utils import get_bench_path
from frappe.utils.file_manager import save_file
from frappe import _

# =================== ESTIMATION REFERENCE ===================
@frappe.whitelist()
def get_next_estimation_preview():
    """Get next Estimation number for preview or assignment"""
    today = getdate()
    year = today.year

    if today.month < 4:
        start_year = year - 1
        end_year = year
    else:
        start_year = year
        end_year = year + 1

    fy = f"{str(start_year)[-2:]}-{str(end_year)[-2:]}"  # e.g., 25-26

    # Get last saved Estimation for this FY
    last = frappe.db.sql("""
        SELECT ref_no FROM `tabEstimation`
        WHERE ref_no LIKE %s
        ORDER BY creation DESC LIMIT 1
    """, (f"IB-E/{fy}/%",), as_dict=True)

    if last:
        last_num = int(last[0].ref_no.split("/")[-1])
        next_num = last_num + 1
    else:
        next_num = 1

    return f"IB-E/{fy}/{str(next_num).zfill(3)}"


def before_insert_estimation(doc, method):
    """Assign Estimation ref_no automatically if not set"""
    if not doc.ref_no:
        doc.ref_no = get_next_estimation_preview()


# =================== INVOICE REFERENCE ===================
@frappe.whitelist()
def get_next_invoice_preview():
    """Get next Invoice number for preview or assignment"""
    today = getdate()
    year = today.year

    if today.month < 4:
        start_year = year - 1
        end_year = year
    else:
        start_year = year
        end_year = year + 1

    fy = f"{str(start_year)[-2:]}-{str(end_year)[-2:]}"  # e.g., 25-26

    # Get last saved Invoice for this FY
    last = frappe.db.sql("""
        SELECT ref_no FROM `tabInvoice`
        WHERE ref_no LIKE %s
        ORDER BY creation DESC LIMIT 1
    """, (f"IB-I/{fy}/%",), as_dict=True)

    if last:
        last_num = int(last[0].ref_no.split("/")[-1])
        next_num = last_num + 1
    else:
        next_num = 1

    return f"IB-I/{fy}/{str(next_num).zfill(3)}"


def before_insert_invoice(doc, method):
    """Assign Invoice ref_no automatically if not set"""
    if not doc.ref_no:
        doc.ref_no = get_next_invoice_preview()


@frappe.whitelist()
def get_total_collected(invoice_name):
    total = frappe.db.sql("""
        SELECT SUM(amount_collected)
        FROM `tabInvoice Collection`
        WHERE invoice=%s
    """, invoice_name)[0][0] or 0

    return total

def update_invoice_received_balance(doc, method):
    """
    Update received_amount and balance_amount in Invoice
    whenever an Invoice Collection is inserted/updated/deleted.
    """
    invoice_name = doc.invoice
    if not invoice_name:
        return

    # Call the existing function
    total_collected = flt(get_total_collected(invoice_name))

    grand_total = flt(frappe.db.get_value("Invoice", invoice_name, "grand_total") or 0)
    balance = grand_total - total_collected
    if balance < 0:
        balance = 0

    frappe.db.set_value("Invoice", invoice_name, {
        "received_amount": total_collected,
        "balance_amount": balance
    })

def validate_invoice_collection(doc, method):
    """
    Prevent Invoice Collection from exceeding Invoice grand_total
    """
    if not doc.invoice:
        return

    # Get grand total & already collected
    invoice = frappe.db.get_value("Invoice", doc.invoice, ["grand_total"], as_dict=True)
    if not invoice:
        return

    already_collected = frappe.db.sql("""
        SELECT SUM(amount_collected)
        FROM `tabInvoice Collection`
        WHERE invoice=%s AND name != %s
    """, (doc.invoice, doc.name))[0][0] or 0

    new_total = flt(already_collected) + flt(doc.amount_collected)

    if new_total > flt(invoice.grand_total):
        frappe.throw(
            f"Collection exceeds Invoice Amount.<br><br>"
            f"Grand Total: {invoice.grand_total}<br>"
            f"Already Collected: {already_collected}<br>"
            f"Trying to Add: {doc.amount_collected}<br><br>"
            f"Remaining Balance: {invoice.grand_total - already_collected}"
        )

@frappe.whitelist()
def get_todays_followups():
    today = frappe.utils.today()  # '2025-09-23'
    return frappe.db.sql("""
        SELECT f.parent, f.followup_date, f.remarks
        FROM `tabFollowup` f
        WHERE DATE(f.followup_date) = %s
        ORDER BY f.followup_date ASC
    """, today, as_dict=True)


# =================== EXPENSES REFERENCE ===================
@frappe.whitelist()
def get_next_expense_preview():
    """Get next Expense number for preview or assignment"""
    today = getdate()
    year = today.year

    # Financial Year (April → March)
    if today.month < 4:
        start_year = year - 1
        end_year = year
    else:
        start_year = year
        end_year = year + 1

    fy = f"{str(start_year)[-2:]}-{str(end_year)[-2:]}"  # e.g., 25-26

    # Get last saved Expense for this FY
    last = frappe.db.sql("""
        SELECT expense_no FROM `tabExpenses`
        WHERE expense_no LIKE %s
        ORDER BY creation DESC LIMIT 1
    """, (f"EXP/{fy}/%",), as_dict=True)

    if last:
        last_num = int(last[0].expense_no.split("/")[-1])
        next_num = last_num + 1
    else:
        next_num = 1

    return f"EXP/{fy}/{str(next_num).zfill(3)}"


def before_insert_expense(doc, method):
    """Assign Expense number automatically if not set"""
    if not doc.expense_no:
        doc.expense_no = get_next_expense_preview()
        doc.name = doc.expense_no  

# =================== Auto Allocate Leave ==================
@frappe.whitelist()
def auto_allocate_monthly_leaves(year: int, month: int):
    """
    Automatically allocate leaves (Sick + Unpaid) to all active employees
    for a given month/year.
    Sick Leave - Paid: carries forward for 3 months, then resets.
    Unpaid Leave: fixed every month, no carry-forward.
    """

    try:
        month_start = get_first_day(datetime(year, month, 1))
        month_end = get_last_day(datetime(year, month, 1))

        prev_month_start = get_first_day(add_months(month_start, -1))
        prev_month_end = get_last_day(add_months(month_start, -1))

        employees = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_id"]
        )

        leave_types = {
            "Sick Leave - Paid": 1,
            "Unpaid Leave": 30,
            "Permission" : 120
        }

        created_count, skipped_count = 0, 0
        errors = []

        for emp in employees:
            for leave_type, base_leave_count in leave_types.items():
                try:
                    # === Step 1: Skip if already exists for this month ===
                    if frappe.db.exists("Leave Allocation", {
                        "employee": emp.name,
                        "leave_type": leave_type,
                        "from_date": month_start,
                        "to_date": month_end,
                        "status": "Approved"
                    }):
                        skipped_count += 1
                        continue

                    # === Step 2: Get previous month's allocation ===
                    prev_alloc = frappe.get_value(
                        "Leave Allocation",
                        {
                            "employee": emp.name,
                            "leave_type": leave_type,
                            "from_date": prev_month_start,
                            "to_date": prev_month_end,
                            "status": "Approved"
                        },
                        ["total_leaves_allocated", "total_leaves_taken"],
                        as_dict=True
                    )

                    # === Step 3: Count how many allocations exist ===
                    allocation_count = frappe.db.count(
                        "Leave Allocation",
                        {
                            "employee": emp.name,
                            "leave_type": leave_type,
                            "status": "Approved"
                        }
                    )

                    carry_forward_balance = 0
                    leave_count = base_leave_count

                    # === ✅ Step 4: Logic for Sick Leave - Paid ===
                    if leave_type == "Sick Leave - Paid":
                        if allocation_count > 0 and allocation_count % 3 == 0:
                            # Restart after every 3 months
                            carry_forward_balance = 0
                            leave_count = base_leave_count
                        elif prev_alloc:
                            balance = flt(prev_alloc.total_leaves_allocated) - flt(prev_alloc.total_leaves_taken)
                            if balance > 0:
                                carry_forward_balance = balance

                    # === ✅ Step 5: Logic for Unpaid Leave ===
                    elif leave_type == "Unpaid Leave":
                        # Always fixed 30, no carry-forward
                        carry_forward_balance = 0
                        leave_count = base_leave_count

                    # === Step 6: Create new allocation ===
                    frappe.get_doc({
                        "doctype": "Leave Allocation",
                        "employee": emp.name,
                        "leave_type": leave_type,
                        "from_date": month_start,
                        "to_date": month_end,
                        "total_leaves_allocated": leave_count + carry_forward_balance,
                        "total_leaves_taken": 0,
                        "status": "Approved"
                    }).insert(ignore_permissions=True, ignore_mandatory=True)

                    created_count += 1

                except Exception as e:
                    errors.append(f"{emp.employee_id} - {leave_type} - {str(e)}")

        frappe.db.commit()

        msg = f"✅ Leave Allocation done.<br>Created: {created_count}, Skipped: {skipped_count}"
        if errors:
            msg += "<br><br>⚠️ Errors:<br>" + "<br>".join(errors)
        return msg

    except Exception as e:
        frappe.throw(f"❌ Error in auto leave allocation: {e}")


# =================== SALARY SLIP GENERATION REFERENCE ===================

@frappe.whitelist()
def generate_salary_slips_from_employee(year=None, month=None, employees=None):
    import json

    if not year or not month:
        frappe.throw(_("Please provide year and month"))

    year = int(year)
    month = int(month)
    start_date = getdate(f"{year}-{month}-01")
    end_date = getdate(f"{year}-{month}-{monthrange(year, month)[1]}")

    # 🔹 Convert employees argument (JSON string) to Python list
    if isinstance(employees, str):
        try:
            employees = json.loads(employees)
        except Exception:
            frappe.throw(_("Invalid employees data"))

    # Fetch holidays
    holiday_dates = get_holiday_dates_for_month(year, month)
    number_of_holidays = len(holiday_dates)  # total holidays in month

    # 🔹 If employees are selected → filter only them, else include all
    if employees:
        employee_filters = {"name": ["in", employees]}
    else:
        employee_filters = {}

    # Get employees
    employees = frappe.get_all(
        "Employee",
        filters=employee_filters,
        fields=[
            "name", "employee_name", "basic_pay", "hra", "conveyance_allowances",
            "medical_allowances", "other_allowances", "pf", "health_insurance",
            "professional_tax", "loan_recovery", "email", "personal_email", "user"
        ]
    )

    created_count = 0
    skipped_count = 0
    errors = []

    for emp in employees:
        # Skip already submitted slips
        if frappe.db.exists("Salary Slip", {
            "employee": emp.name,
            "pay_period_start": start_date,
            "pay_period_end": end_date,
        }):
            skipped_count += 1
            continue

        # Fetch attendance
        attendance_records = frappe.get_all(
            "Attendance",
            filters={
                "employee": emp.name,
                "attendance_date": ["between", [start_date, end_date]],
                "docstatus": ["in", [0, 1]]
            },
            fields=["status", "leave_type", "attendance_date"]
        )

        # Initialize counters
        total_days = (end_date - start_date).days + 1
        present_days = 0
        absent_days = 0
        paid_leave_days = 0
        total_leave_days = 0

        for single_day in [start_date + timedelta(days=i) for i in range(total_days)]:
            is_holiday = single_day in holiday_dates
            record = next((r for r in attendance_records if r["attendance_date"] == single_day), None)

            if is_holiday:
                present_days += 1  # count holiday as present
                continue  # skip further attendance check

            if record:
                status = record.get("status")
                if status == "Present":
                    present_days += 1
                elif status == "Half Day":
                    total_leave_days += 0.5
                    leave_type = record.get("leave_type")

                    if leave_type == "Unpaid Leave":
                        absent_days += 0.5  # unpaid leave
                    else:
                        present_days += 0.5
                        paid_leave_days += 0.5
                elif status == "Absent":
                    absent_days += 1
                    total_leave_days += 1
                elif status in ["On Leave", "Leave"]:
                    leave_type = record.get("leave_type")
                    if leave_type:
                        # Check Leave Allocation for this day
                        allocations = frappe.get_all(
                            "Leave Allocation",
                            filters={
                                "employee": emp.name,
                                "leave_type": leave_type,
                                "status": "Approved",
                                "from_date": ["<=", single_day],
                                "to_date": [">=", single_day]
                            },
                            fields=["name", "total_leaves_allocated", "total_leaves_taken"]
                        )
                        allocation_found = None
                        for a in allocations:
                            if flt(a.total_leaves_taken) < flt(a.total_leaves_allocated):
                                allocation_found = a
                                break

                        if allocation_found:
                            paid_leave_days += 1
                            present_days += 1
                            total_leave_days += 1
                        else:
                            # Check if there’s an approved Leave Application for this date
                            approved_leave = frappe.db.exists("Leave Application", {
                                "employee": emp.name,
                                "leave_type": leave_type,
                                "workflow_state": "Approved",
                                "from_date": ["<=", single_day],
                                "to_date": [">=", single_day]
                            })
                            if approved_leave:
                                paid_leave_days += 1
                                present_days += 1
                                total_leave_days += 1
                            else:
                                absent_days += 1
                                total_leave_days += 1

            else:
                # No attendance record → absent
                absent_days += 1
                total_leave_days += 1

        # Calculate salary
        working_days = total_days
        unpaid_leave_days = total_leave_days - paid_leave_days

        # Earnings
        gross_pay = (
            flt(emp.basic_pay)
            + flt(emp.hra)
            + flt(emp.conveyance_allowances)
            + flt(emp.medical_allowances)
            + flt(emp.other_allowances)
        )

        # Deductions
        base_deductions = (
            flt(emp.pf)
            + flt(emp.health_insurance)
            + flt(emp.professional_tax)
            + flt(emp.loan_recovery)
        )

        # Prorate based on attendance
        grand_gross_pay = gross_pay * ((working_days - unpaid_leave_days) / working_days) if working_days else gross_pay
        grand_net_pay = grand_gross_pay - base_deductions

        lop_amount = gross_pay * (unpaid_leave_days / working_days) if working_days else 0

        total_deductions = base_deductions + lop_amount

        try:
            slip = frappe.get_doc({
                "doctype": "Salary Slip",
                "employee": emp.name,
                "employee_name": emp.employee_name,
                "email": emp.email,
                "personal_email": emp.personal_email,
                "user": emp.user,
                "pay_period_start": start_date,
                "pay_period_end": end_date,
                "no_of_leave": total_leave_days,
                "no_of_paid_leave": paid_leave_days,
                "gross_pay": gross_pay,
                "grand_gross_pay": grand_gross_pay,
                "net_pay": grand_gross_pay - base_deductions,
                "grand_net_pay": grand_net_pay,
                "total_deduction": total_deductions,
                "total_working_days": working_days,
                "lop": lop_amount,
                "lop_days": unpaid_leave_days,
                "status": "Draft",
                "basic_pay": emp.basic_pay,
                "hra": emp.hra,
                "conveyance_allowances": emp.conveyance_allowances,
                "medical_allowances": emp.medical_allowances,
                "other_allowances": emp.other_allowances,
                "pf": emp.pf,
                "health_insurance": emp.health_insurance,
                "professional_tax": emp.professional_tax,
                "loan_recovery": emp.loan_recovery
            })
            slip.insert(ignore_permissions=True)
            created_count += 1

        except Exception as e:
            errors.append(f"Error for {emp.name}: {str(e)}")

    result_msg = f"Salary Slips Created: {created_count}, Skipped: {skipped_count}"
    if errors:
        result_msg += "\nErrors:\n" + "\n".join(errors)

    return result_msg

@frappe.whitelist()
def salary_slip_after_submit(doc, method):
    """Triggered automatically when a Salary Slip is submitted (approved)."""

    try:
        # Get Month-Year for display
        month_year = frappe.utils.formatdate(doc.pay_period_start, "MMMM yyyy")

        # -------------------------
        # 1️⃣ Create Notification Log
        # -------------------------
        if doc.user:
            notification_doc = frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Salary Slip for {month_year}",
                "email_content": f"Your salary slip for {month_year} has been approved.",
                "for_user": doc.user,
                "document_type": "Salary Slip",
                "document_name": doc.name,
                "from_user": frappe.session.user,
                "type": "Alert",
                "seen": 0,
            })
            notification_doc.insert(ignore_permissions=True)

            # Real-time bell refresh
            frappe.publish_realtime(
                event="notification",
                message={"type": "New Notification"},
                user=doc.user,
                after_commit=True
            )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Salary Slip Notification Error")

    # -------------------------
    # 2️⃣ Firebase Push Notification
    # -------------------------
    try:
        from company.company.api import send_push_notification_to_user

        if doc.user:
            result = send_push_notification_to_user(
                user=doc.user,
                title=f"Salary Slip for {month_year}",
                body=f"Your salary slip for {month_year} has been approved successfully.",
                data={"salary_slip": doc.name}
            )

            frappe.log_error(
                message=f"Push notification sent successfully to {doc.user}\nResponse: {result}",
                title=f"Firebase Push Success for {doc.employee_name}"
            )

    except Exception as e:
        frappe.log_error(
            message=f"Error while sending push notification: {str(e)}",
            title=f"Firebase Push Error for {doc.employee_name}"
        )

    # -------------------------
    # 3️⃣ Email Notification
    # -------------------------
    try:
        recipients = []
        if doc.email:
            recipients.append(doc.email)
        if doc.personal_email:
            recipients.append(doc.personal_email)

        if recipients:
            print_format = frappe.get_meta("Salary Slip").default_print_format or "Standard"
            pdf_content = frappe.get_print(
                "Salary Slip",
                doc.name,
                print_format=print_format,
                as_pdf=True
            )

            message = f"""
            <div style="font-family: 'Montserrat', 'Segoe UI', Arial, sans-serif; background:#f4f6f8; padding:30px;">
                <div style="max-width:600px; margin:auto; background:white; border-radius:12px;
                            box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden;">
                    <div style="background:#007bff; color:white; padding:18px 24px; font-size:18px; font-weight:600; text-align:center;">
                        Your Salary Slip for {month_year}
                    </div>
                    <div style="padding:24px; color:#333; font-size:14px; line-height:1.6;">
                        <p>Dear <b>{doc.employee_name}</b>,</p>
                        <p>Your salary slip for <b>{month_year}</b> has been Released. Please find the attached PDF below.</p>
                        <p style="margin-top:20px;">Best regards,<br>
                        <b style="color:#007bff;">HR Team</b></p>
                    </div>
                </div>
            </div>
            """

            frappe.sendmail(
                recipients=recipients,
                subject=f"Salary Slip for {month_year}",
                message=message,
                attachments=[{
                    "fname": f"Salary_Slip_{doc.employee}_{month_year}.pdf",
                    "fcontent": pdf_content
                }],
                reference_doctype="Salary Slip",
                reference_name=doc.name
            )

    except Exception as e:
        frappe.log_error(message=str(e), title=f"Email Error for {doc.employee_name}")
        

def get_holiday_dates_for_month(year, month):
    """
    Fetch all holiday dates for given month/year from Holiday List (auto + manual holidays)
    """
    holiday_list = frappe.get_all("Holiday List",
        filters={"year": year, "month_year": month},
        fields=["name"]
    )

    if not holiday_list:
        return []

    holiday_doc = frappe.get_doc("Holiday List", holiday_list[0].name)
    holiday_dates = []

    for row in holiday_doc.holidays:
        if row.is_working_day == 0:
            holiday_dates.append(row.holiday_date)

    
    return holiday_dates


@frappe.whitelist()
def populate_holidays_for_ui(month, year):
    

    month = int(month)
    year = int(year)
    num_days = monthrange(year, month)[1]

    holidays = []
    saturday_count = 0
    working_days_count = 0

    for day in range(1, num_days + 1):
        d = getdate(f"{year}-{month:02d}-{day:02d}")
        weekday = d.weekday()  # Monday=0, Sunday=6
        is_holiday = False
        description = ""

        if weekday == 6:  # Sunday
            is_holiday = True
            description = "Sunday"
        elif weekday == 5:  # Saturday
            saturday_count += 1
            if saturday_count in [2,4]:
                is_holiday = True
                description = "2nd/4th Saturday"

        is_working_day = 0 if is_holiday else 1
        if is_working_day:
            working_days_count += 1

        holidays.append({
            "holiday_date": d,
            "description": description if is_holiday else "",
            "is_working_day": is_working_day
        })

    # Return both holidays and working_days
    return {
        "holidays": holidays,
        "working_days": working_days_count
    }


@frappe.whitelist()
def fetch_salary_slips(start_date, end_date):
    """
    Fetch all employees with Salary Slips in the given period
    """
    start_date = getdate(start_date)
    end_date = getdate(end_date)

    salary_slips = frappe.get_all(
        "Salary Slip",
        filters={
            "pay_period_start": ["<=", end_date],
            "pay_period_end": [">=", start_date],
        },
        fields=["name", "employee", "employee_name", "grand_gross_pay", "grand_net_pay"]
    )

    # Prepare data for child table
    employee_rows = []
    for slip in salary_slips:
        employee_rows.append({
            "employee": slip.employee,
            "salary_slip": slip.name,
            "gross_pay": slip.grand_gross_pay,
            "net_pay": slip.grand_net_pay
        })

    return employee_rows

# @frappe.whitelist()
# def get_today_leave_employees():
#     """
#     Returns a list of employees who are on leave today
#     """
#     today_date = getdate(today())

#     leave_apps = frappe.get_all(
#         "Leave Application",
#         filters={
#             "workflow_state": "Approved",
#             "from_date": ["<=", today_date],
#             "to_date": [">=", today_date],
#         },
#         fields=["employee", "employee_name", "leave_type", "from_date", "to_date"]
#     )

#      # Convert dates to string so JS can handle
#     for app in leave_apps:
#         app["from_date"] = str(app["from_date"])
#         app["to_date"] = str(app["to_date"])

#     return leave_apps

@frappe.whitelist()
def get_today_leave_employees():
    """
    Returns a list of employees who are on approved leave today,
    only for Sick Leave - Paid and Unpaid Leave
    """

    today_date = getdate(today())

    allowed_leave_types = ["Sick Leave - Paid", "Unpaid Leave"]

    leave_apps = frappe.get_all(
        "Leave Application",
        filters={
            "workflow_state": "Approved",
            "leave_type": ["in", allowed_leave_types],
            "from_date": ["<=", today_date],
            "to_date": [">=", today_date],
        },
        fields=["employee", "employee_name", "leave_type", "from_date", "to_date"]
    )

    # Convert dates to string for JS
    for app in leave_apps:
        app["from_date"] = str(app["from_date"])
        app["to_date"] = str(app["to_date"])

    return leave_apps


# @frappe.whitelist()
# def update_leave_allocation_on_approval(doc):
#     frappe.log_error(f"Workflow Approved: {doc.name}, state: {doc.workflow_state}", "Leave Allocation Debug")

#     if not doc.leave_type or not doc.employee:
#         frappe.log_error("Skipping allocation: missing leave_type or employee", "Leave Allocation Debug")
#         return

#     from_date = getdate(doc.from_date)
#     to_date = getdate(doc.to_date)
#     leave_days = (to_date - from_date).days + 1
#     if getattr(doc, "half_day", 0):
#         leave_days -= 0.5

#     allocations = frappe.get_all(
#         "Leave Allocation",
#         filters={
#             "employee": doc.employee,
#             "leave_type": doc.leave_type,
#             "status": "Approved",
#             "from_date": ["<=", to_date],
#             "to_date": [">=", from_date]
#         },
#         fields=["name", "total_leaves_allocated", "total_leaves_taken"]
#     )

#     if not allocations:
#         frappe.throw(f"No approved leave allocation found for {doc.employee} and {doc.leave_type}")

#     remaining_days = leave_days
#     for allocation in allocations:
#         available = flt(allocation.total_leaves_allocated) - flt(allocation.total_leaves_taken)
#         if available <= 0:
#             continue

#         to_add = min(available, remaining_days)
#         new_total_taken = flt(allocation.total_leaves_taken) + to_add

#         frappe.db.set_value(
#             "Leave Allocation",
#             allocation.name,
#             "total_leaves_taken",
#             new_total_taken
#         )

#         remaining_days -= to_add
#         if remaining_days <= 0:
#             break

#     if remaining_days > 0:
#         frappe.throw(f"Not enough leave balance for {doc.employee} and {doc.leave_type}")

#     frappe.db.commit()



def update_leave_allocation_from_attendance(doc, method=None):
    if not doc.employee or not doc.attendance_date:
        return

    previous = getattr(doc, "_previous_status", None)

    allocation = frappe.get_all(
        "Leave Allocation",
        filters={
            "employee": doc.employee,
            "leave_type": doc.leave_type,
            "status": "Approved",
            "from_date": ["<=", doc.attendance_date],
            "to_date": [">=", doc.attendance_date]
        },
        fields=["name", "total_leaves_allocated", "total_leaves_taken"],
        limit_page_length=1
    )

    if not allocation:
        return

    allocation = allocation[0]
    total_taken = allocation.total_leaves_taken or 0
    total_alloc = allocation.total_leaves_allocated or 0

    # Only act if status changed
    if doc.status in ["On Leave", "Leave"] and previous not in ["On Leave", "Leave"]:
        if total_taken < total_alloc:
            frappe.db.set_value("Leave Allocation", allocation.name, "total_leaves_taken", total_taken + 1)

    elif previous in ["On Leave", "Leave"] and doc.status == "Present":
        if total_taken > 0:
            frappe.db.set_value("Leave Allocation", allocation.name, "total_leaves_taken", total_taken - 1)



@frappe.whitelist()
def check_leave_balance(employee, leave_type, from_date, to_date, permission_hours=None, half_day=False):
    """
    Check available leave balance for given employee and leave type.
    Returns {"allowed": True/False, "remaining": <float>}
    """
    from_date = getdate(from_date)
    to_date = getdate(to_date)

    # Fetch leave allocation
    allocations = frappe.get_all(
        "Leave Allocation",
        filters={
            "employee": employee,
            "leave_type": leave_type,
            "status": "Approved",
            "from_date": ["<=", to_date],
            "to_date": [">=", from_date]
        },
        fields=["total_leaves_allocated", "total_leaves_taken"]
    )

    remaining = 0
    if allocations:
        total_allocated = sum(flt(a.total_leaves_allocated) for a in allocations)
        total_taken = sum(flt(a.total_leaves_taken) for a in allocations)
        remaining = total_allocated - total_taken

    # --- Permission logic ---
    if leave_type.lower() == "permission":
        requested = flt(permission_hours or 0)
        if not requested:
            frappe.throw("Please enter Permission Hours in minutes")

        allowed = remaining >= requested
        return {
            "allowed": allowed,
            "remaining": remaining,
            "requested": requested,
            "unit": "Minutes"
        }

    # --- Normal Leave Day Calculation ---
    leave_days = (to_date - from_date).days + 1

    # 🔥 APPLY HALF-DAY LOGIC
    is_half_day = str(half_day) in ("1", "true", "True")
    if is_half_day:
        leave_days = 0.5

    allowed = remaining >= leave_days

    return {
        "allowed": allowed,
        "remaining": remaining,
        "requested": leave_days,
        "unit": "Days"
    }


def validate_leave_balance(doc, method=None):
    """
    Hook for Leave Application — blocks submission if insufficient balance or duplicate permission.
    """
    if not doc.employee or not doc.leave_type:
        frappe.throw("Employee and Leave Type are required.")

    # --- 1️⃣ Check balance ---
    res = check_leave_balance(
        employee=doc.employee,
        leave_type=doc.leave_type,
        from_date=doc.from_date,
        to_date=doc.to_date,
        permission_hours=doc.permission_hours,
        half_day=doc.half_day
    )

    if not res.get("allowed"):
        frappe.throw(
            f"Not enough {res['unit'].lower()} balance for {doc.employee_name or doc.employee}.<br>"
            f"Available: {res['remaining']} {res['unit']}, Requested: {res['requested']} {res['unit']}."
        )

    # --- 2️⃣ Prevent overlapping (normal leave only) ---
    if doc.leave_type.lower() != "permission":
        if has_approved_leave(doc.employee, doc.from_date, doc.to_date, exclude_doc=doc.name):
            frappe.throw(
                f"Employee {doc.employee} already has an approved leave in the selected date range."
            )

    # --- 3️⃣ Prevent duplicate permission ---
    if doc.leave_type.lower() == "permission":
        existing = frappe.db.exists(
            "Leave Application",
            {
                "employee": doc.employee,
                "leave_type": "Permission",
                "from_date": doc.from_date,
                "workflow_state": ["in", ["Approved", "Pending Approval"]],
                "name": ["!=", doc.name]
            }
        )
        if existing:
            frappe.throw(
                f"Employee {doc.employee} already has a Permission applied on {doc.from_date}."
            )



def has_approved_leave(employee, from_date, to_date, exclude_doc=None):
    """
    Checks if employee already has approved leave overlapping the given range.
    """
    filters = {
        "employee": employee,
        "status": "Approved",
        "from_date": ["<=", to_date],
        "to_date": [">=", from_date]
    }
    if exclude_doc:
        filters["name"] = ["!=", exclude_doc]

    return frappe.db.exists("Leave Application", filters)


def update_permission_allocation(doc, method=None):
    # ✅ Run only when leave type is Permission and workflow state is Approved
    if doc.leave_type.lower() != "permission" or doc.workflow_state != "Approved":
        return

    if not doc.permission_hours:
        frappe.throw("Permission Hours are required for Permission leave type.")

    # 🔍 Fetch the active Approved Leave Allocation
    allocation = frappe.db.get_value(
        "Leave Allocation",
        {
            "employee": doc.employee,
            "leave_type": doc.leave_type,
            "status": "Approved"
        },
        ["name", "total_leaves_taken"],
        as_dict=True
    )

    if not allocation:
        frappe.msgprint(f"No Leave Allocation found for {doc.employee} - {doc.leave_type}")
        return

    # ➕ Add new taken minutes
    new_taken = flt(allocation.total_leaves_taken) + flt(doc.permission_hours)

    frappe.db.set_value("Leave Allocation", allocation.name, "total_leaves_taken", new_taken)
    frappe.db.commit()

    frappe.msgprint(
        f"✅ Permission hours updated for {doc.employee}.<br>"
        f"Added: {doc.permission_hours} minutes.<br>"
        f"Total taken now: {new_taken} minutes."
    )


@frappe.whitelist()
def auto_submit_leave_application(doc, method=None):
    """
    Automatically submit Leave Application after save if all validations pass.
    """
    try:
        # Skip if already submitted
        if doc.docstatus == 1:
            return

        # Double-check validation again (safety)
        validate_leave_balance(doc)

        # Submit the document programmatically
        doc.submit()

        frappe.msgprint(
            f"✅ Leave Application {doc.name} has been submitted successfully."
        )

    except frappe.ValidationError as e:
        # Do not submit — validation failed
        frappe.msgprint(f"❌ Leave not submitted: {str(e)}")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Auto Submit Leave Application Error")

# @frappe.whitelist()
# def handle_leave_status_change(doc, method=None):
#     """
#     Consolidated trigger for all Leave Application workflow changes.
#     Sends modern styled HTML emails to Employee and/or HR.
#     """
#     if getattr(doc, "docstatus", 0) not in [1, 2]:
#         return

#     _before_save = getattr(doc, "get_doc_before_save", lambda: None)()
#     previous_state = _before_save.workflow_state if _before_save else None

#     # Determine recipients and content based on state change
#     hr_email = "deepakkjc088@gmail.com"
#     employee_email = frappe.get_value("Employee", doc.employee, "email")
    
#     # Defaults
#     color = "#007bff"
#     header_text = ""
#     intro_text = ""
#     recipients = [hr_email] if hr_email else []
    
#     # ---------------------------------------------------------
#     # 1️⃣ Handle Approved / Rejected (Send to both Employee + HR)
#     # ---------------------------------------------------------
#     if doc.workflow_state == "Approved":
#         color = "#28a745"
#         header_text = "✅ Leave Approved"
#         intro_text = f"Good news, <b>{doc.employee_name}</b>! Your leave request has been approved."
#         recipients = [email for email in [employee_email, hr_email] if email]
        
#     elif doc.workflow_state == "Rejected":
#         color = "#dc3545"
#         header_text = "❌ Leave Rejected"
#         intro_text = f"Dear <b>{doc.employee_name}</b>, unfortunately your leave request has been rejected."
#         recipients = [email for email in [employee_email, hr_email] if email]

#     # ---------------------------------------------------------
#     # 2️⃣ Handle Clarification (Send to Employee)
#     # ---------------------------------------------------------
#     elif doc.workflow_state == "Clarification Requested":
#         color = "#ffc107" # Yellow for clarification
#         header_text = "ℹ️ Clarification Requested"
#         intro_text = f"Dear <b>{doc.employee_name}</b>, HR has requested clarification regarding your leave application."
#         recipients = [employee_email] if employee_email else []

#     # ---------------------------------------------------------
#     # 3️⃣ Handle New Submission or Reply (Send to HR)
#     # ---------------------------------------------------------
#     elif doc.workflow_state == "Pending":
#         if previous_state in [None, "Draft"]:
#             # Initial Submission
#             header_text = "📩 New Leave Request Submitted"
#             intro_text = f"Dear <b>HR</b>, a new leave application has been submitted by <b>{doc.employee_name}</b> and is pending your approval."
#         elif previous_state == "Clarification Requested":
#             # Employee Reply
#             header_text = "📩 Clarification Reply Received"
#             intro_text = f"Dear <b>HR</b>, <b>{doc.employee_name}</b> has replied to your clarification request."
#         else:
#             return
#     else:
#         return

#     # ============================================
#     # 🔹 Add Permission Hours if Leave Type = Permission
#     # ============================================
#     permission_row = ""
#     if str(doc.leave_type).strip().lower() == "permission":
#         permission_hours = getattr(doc, "permission_hours", None)
#         if permission_hours is not None:
#             hrs = int(permission_hours) // 60
#             mins = int(permission_hours) % 60
#             if hrs >= 1 and mins > 0: formatted_time = f"{hrs} hr(s) {mins} min(s)"
#             elif hrs >= 1: formatted_time = f"{hrs} hr(s)"
#             elif mins > 0: formatted_time = f"{mins} min(s)"
#             else: formatted_time = "0 min"

#             permission_row = f"""
#                 <tr>
#                     <td style="padding:8px 10px; font-weight:bold; background:#f9f9f9;">Permission Duration</td>
#                     <td style="padding:8px 10px;">{formatted_time}</td>
#                 </tr>
#             """

#     # ============================================
#     # 🔹 Add Messages (Reason / Question / Reply)
#     # ============================================
#     # Reason for leave
#     message_content = f"""
#         <div style="margin-top:20px; padding:15px; background:#f8f9fa; border-left:5px solid #6c757d; border-radius:4px;">
#             <b style="color:#495057;">Reason for Leave:</b><br>
#             <p style="margin:5px 0 0; font-style:italic;">"{getattr(doc, 'reson', '') or 'No reason provided.'}"</p>
#         </div>
#     """

#     # Check for latest clarification/reply
#     query_msg = ""
#     reply_msg = ""
#     for i in range(5, 0, -1):
#         suffix = f"_{i}" if i > 1 else ""
#         q = getattr(doc, f"hr_query{suffix}", None)
#         r = getattr(doc, f"employee_reply{suffix}", None)
#         if q and not query_msg: query_msg = q
#         if r and not reply_msg: reply_msg = r
#         if query_msg and reply_msg: break

#     if doc.workflow_state == "Clarification Requested" and query_msg:
#         message_content += f"""
#             <div style="margin-top:10px; padding:15px; background:#fff3cd; border-left:5px solid #ffc107; border-radius:4px;">
#                 <b style="color:#856404;">HR Question:</b><br>
#                 <p style="margin:5px 0 0; font-style:italic;">"{query_msg}"</p>
#             </div>
#         """
#     elif doc.workflow_state == "Pending" and previous_state == "Clarification Requested" and reply_msg:
#         message_content += f"""
#             <div style="margin-top:10px; padding:15px; background:#e1f5fe; border-left:5px solid #03a9f4; border-radius:4px;">
#                 <b style="color:#01579b;">Employee Reply:</b><br>
#                 <p style="margin:5px 0 0; font-style:italic;">"{reply_msg}"</p>
#             </div>
#         """

#     # Leave details table
#     leave_details = f"""
#         <table style="width:100%; border-collapse:collapse; font-size:14px;">
#             <tr><td style="padding:8px 10px; font-weight:bold; width:160px; background:#f9f9f9;">Employee</td><td style="padding:8px 10px;">{doc.employee_name} ({doc.employee})</td></tr>
#             <tr><td style="padding:8px 10px; font-weight:bold; background:#f9f9f9;">Leave Type</td><td style="padding:8px 10px;">{doc.leave_type}</td></tr>
#             <tr><td style="padding:8px 10px; font-weight:bold; background:#f9f9f9;">From</td><td style="padding:8px 10px;">{formatdate(doc.from_date)}</td></tr>
#             <tr><td style="padding:8px 10px; font-weight:bold; background:#f9f9f9;">To</td><td style="padding:8px 10px;">{formatdate(doc.to_date)}</td></tr>
#             <tr><td style="padding:8px 10px; font-weight:bold; background:#f9f9f9;">Total Days</td><td style="padding:8px 10px;">{doc.total_days}</td></tr>
#             {permission_row}
#         </table>
#     """

#     # Main styled email layout
#     message = f"""
#     <div style="font-family: 'Montserrat', 'Segoe UI', Arial, sans-serif; background:#f4f6f8; padding:40px;">
#         <div style="max-width:600px; margin:auto; background:white; border-radius:12px; 
#                     box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden;">
            
#             <div style="background:{color}; color:white; padding:18px 24px; font-size:18px; 
#                         font-weight:600; letter-spacing:0.3px;">
#                 {header_text}
#             </div>

#             <div style="padding:24px; color:#333;">
#                 <p style="font-size:15px;">{intro_text}</p>

#                 <div style="margin:20px 0; border-radius:8px; overflow:hidden; border:1px solid #e0e0e0;">
#                     {leave_details}
#                 </div>

#                 {message_content}

#                 <div style="margin-top:30px;">
#                     <a href="{frappe.utils.get_url('/app/leave-application/' + doc.name)}" 
#                        style="background:{color}; color:white; padding:10px 20px; text-decoration:none; 
#                               border-radius:6px; font-size:14px;">
#                         View in Website
#                     </a>
#                 </div>
#             </div>
#         </div>
#     </div>
#     """

#     subject = f"{header_text} - {doc.employee_name}"

#     try:
#         frappe.sendmail(
#             recipients=recipients,
#             subject=subject,
#             message=message,
#             reference_doctype="Leave Application",
#             reference_name=doc.name
#         )
#     except Exception as e:
#         frappe.log_error(f"Leave Workflow Mail Error: {str(e)}", "Leave Email Debug")





def has_approved_leave(employee, from_date, to_date, exclude_doc=None):
    """
    Returns True if there is already an approved leave for the employee
    that overlaps with the given date range.
    exclude_doc: optional Leave Application name to exclude from check (useful during updates)
    """
    filters = {
        "employee": employee,
        "workflow_state": "Approved",
        "docstatus": 1,
        "from_date": ["<=", to_date],
        "to_date": [">=", from_date],
    }

    if exclude_doc:
        filters["name"] = ["!=", exclude_doc]

    existing = frappe.get_all("Leave Application", filters=filters, fields=["name"])
    return bool(existing)


@frappe.whitelist()
def get_today_birthdays():
    """
    Returns a list of employees who have birthday today
    """
    employees = frappe.get_all(
        "Employee",
        filters={
            "status": "Active"
        },
        fields=["employee_name", "employee_id", "dob"]
    )
    

    today_mmdd = getdate(today()).strftime("%m-%d")  # e.g., "10-02"
    result = []
    
    for emp in employees:
        if not emp.dob:
            continue

        dob_date = getdate(emp.dob)  # convert to date object
        emp_mmdd = dob_date.strftime("%m-%d")

        

        if emp_mmdd == today_mmdd:
            res = result.append({
                "employee_name": emp.employee_name,
                "employee": emp.employee_id,
                "dob": str(emp.dob)
            })

    return result


@frappe.whitelist()
def get_current_month_holidays():

    today = datetime.today()
    current_month = today.month
    current_year = today.year

    # fetch only parent holiday lists for the current year
    holiday_lists = frappe.get_all("Holiday List", filters={"year": current_year}, fields=["name"])

    result = []

    for hl in holiday_lists:
        doc = frappe.get_doc("Holiday List", hl.name)
        for h in doc.holidays:
            # Only consider current month and non-working days
            if h.holiday_date.month == current_month and h.is_working_day == 0:
                result.append({
                    "holiday_date": h.holiday_date.strftime("%Y-%m-%d"),
                    "description": h.description
                })

    return result


@frappe.whitelist()
def get_recent_announcements(limit=5):
    """Return the most recent active announcements"""
    announcements = frappe.get_all(
        "Announcement",
        fields=["announcement_name", "announcement", "creation"],
        order_by="creation desc",
        limit=limit
    )
    return announcements


@frappe.whitelist()
def get_upcoming_and_expired_renewals(days=7):
    days = int(days)
    today_date = today()
    end_date = add_days(today(), days)
    
    # Get upcoming renewals
    upcoming_items = frappe.get_all(
        "Renewal Tracker",
        fields=["item_name", "category", "renewal_date", "amount", "status"],
        filters={"renewal_date": ["between", [today_date, end_date]]},
        order_by="renewal_date asc"
    )

    # Get expired items
    expired_items = frappe.get_all(
        "Renewal Tracker",
        fields=["item_name", "category", "renewal_date", "amount", "status"],
        filters={"renewal_date": ["<", today_date]},
        order_by="renewal_date asc"
    )

    # Add a flag to indicate type
    for item in upcoming_items:
        item["type"] = "upcoming"

    for item in expired_items:
        item["type"] = "expired"

    return upcoming_items + expired_items

def update_expired_renewals():
    today_date = today()
    # Find items whose renewal date has passed and status is not Expired
    expired_items = frappe.get_all(
        "Renewal Tracker",
        filters={
            "renewal_date": ["<", today_date],
            "status": ["!=", "Expired"]
        },
        fields=["name"]
    )

    for item in expired_items:
        frappe.db.set_value("Renewal Tracker", item.name, "status", "Expired")
        frappe.db.commit()



def format_timedelta(td):
    """Convert timedelta to HH:MM:SS format. Shows 00:00:00 if zero, '—' if None."""
    if td is None:
        return "—"
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"



@frappe.whitelist()
def get_today_checkin_time():
    """Return today's check-in/out details for the logged-in employee with formatted debug logging."""
    try:
        user = frappe.session.user

        # Try both possible link fields: 'user' or 'user_id'
        employee = frappe.db.get_value("Employee", {"user": user}, "name")
        if not employee:
            employee = frappe.db.get_value("Employee", {"user_id": user}, "name")

        if not employee:
            all_emps = frappe.get_all("Employee", ["name", "user", "user_id"])
            return {"status": "Not Linked", "checkin_time": None, "checkout_time": None}


        today = getdate()
        attendance = frappe.db.get_value(
            "Attendance",
            {"employee": employee, "attendance_date": today},
            ["in_time", "out_time", "status"],
            as_dict=True
        )

        # Format in/out times for logging
        if attendance:
            formatted_checkin = format_timedelta(attendance.in_time)
            formatted_checkout = format_timedelta(attendance.out_time)
            # frappe.log_error(
            #     f"Today's attendance (formatted): "
            #     f"in_time={formatted_checkin}, "
            #     f"out_time={formatted_checkout}, "
            #     f"status={attendance.status}",
            #     "Checkin Debug"
            # )
        else:
            # frappe.log_error("Today's attendance: None", "Checkin Debug")
            pass

        if not attendance:
            return {"status": "Not Checked In", "checkin_time": None, "checkout_time": None}

        checkin_time = format_timedelta(attendance.in_time)
        checkout_time = format_timedelta(attendance.out_time)
        status = attendance.status or "—"

        return {
            "status": status,
            "checkin_time": checkin_time,
            "checkout_time": checkout_time
        }

    except Exception as e:
        return {"status": "Error", "checkin_time": None, "checkout_time": None}


@frappe.whitelist()
def get_employee_last_seven_days_attendance():
    """
    Returns the logged-in employee's in/out times for the last 7 days,
    including holidays and working day info — in reverse order (latest first).
    """
    try:
        from datetime import datetime, timedelta

        user = frappe.session.user

        # Get employee linked to logged-in user
        employee = frappe.db.get_value("Employee", {"user": user}, "name") or \
                   frappe.db.get_value("Employee", {"user_id": user}, "name")

        if not employee:
            return {"status": "Not Linked", "timeline": []}

        today_date = datetime.today().date()
        start_date = today_date - timedelta(days=6)  # last 7 days including today
        end_date = today_date

        # Fetch attendance records
        attendance_records = frappe.get_all(
            "Attendance",
            filters={
                "employee": employee,
                "attendance_date": ["between", [start_date, end_date]]
            },
            fields=["attendance_date", "in_time", "out_time", "status"],
            order_by="attendance_date asc"
        )
        attendance_dict = {str(rec.attendance_date): rec for rec in attendance_records}

        # Fetch holidays
        holidays = frappe.get_all(
            "Holidays",
            filters={"holiday_date": ["between", [start_date, end_date]]},
            fields=["holiday_date", "description", "is_working_day"]
        )
        holiday_dict = {str(h["holiday_date"]): h for h in holidays}

        timeline_data = []

        # Build timeline (oldest to newest)
        for i in range(7):
            date = start_date + timedelta(days=i)
            date_str = str(date)

            att_rec = attendance_dict.get(date_str)
            hol_rec = holiday_dict.get(date_str)

            checkin_time = str(att_rec.in_time) if att_rec and att_rec.in_time else None
            checkout_time = str(att_rec.out_time) if att_rec and att_rec.out_time else None
            status = att_rec.status if att_rec else "Absent"

            # Holiday info
            if hol_rec:
                if hol_rec.get("is_working_day"):
                    holiday_info = f"Working Day: {hol_rec.get('description') or ''}"
                else:
                    holiday_info = f"Holiday: {hol_rec.get('description') or ''}"
            else:
                holiday_info = "—"

            timeline_data.append({
                "date": date_str,
                "checkin_time": checkin_time,
                "checkout_time": checkout_time,
                "status": status,
                "holiday_info": holiday_info
            })

        # ✅ Reverse the order (latest first)
        timeline_data.reverse()

        # frappe.log_error(f"Last 7 Days Timeline Data (Reversed) for {employee}: {timeline_data}", "Timeline Debug")
        return timeline_data

    except Exception as e:
        frappe.log_error(f"Error fetching last 7 days timeline: {str(e)}", "Timeline Error")
        return {"status": "Error", "timeline": []}



#=========Firebase Notification==========

import frappe
import requests
from google.oauth2 import service_account
import google.auth.transport.requests
from typing import Optional

def _get_credentials():
    """
    Load service account credentials from site_config fcm_key_path.
    Returns google Credentials object.
    """
    key_relative = frappe.get_site_config().get("fcm_key_path")
    if not key_relative:
        frappe.throw("FCM key path not configured in site_config.json (fcm_key_path)")
    key_path = frappe.get_site_path(key_relative)
    creds = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"]
    )
    return creds

@frappe.whitelist(allow_guest=False)
def save_fcm_token(token: str):
    """Save the browser/device FCM token on the logged-in User record."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw("Login required")
    frappe.db.set_value("User", user, "fcm_token", token)
    frappe.db.commit()
    return {"status": "ok", "message": "Token saved", "token": token}

def _send_v1_message_to_token(token: str, title: str, body: str, data: dict = None) -> dict:
    """
    Send a message to a device token using FCM HTTP v1.
    Returns FCM response JSON.
    """
    creds = _get_credentials()
    request = google.auth.transport.requests.Request()
    creds.refresh(request)
    access_token = creds.token
    project_id = creds.project_id

    message = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body}
        }
    }
    if data:
        # Optional custom data payload
        message["message"]["data"] = {k: str(v) for k, v in data.items()}

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; UTF-8"
    }
    resp = requests.post(url, headers=headers, json=message, timeout=10)
    try:
        return resp.json()
    except ValueError:
        return {"error": "non-json-response", "status_code": resp.status_code, "text": resp.text}

def send_push_notification_to_user(user: str, title: str, body: str, data: dict = None):
    """
    Public helper to send a push notification to a Frappe User (by email/ID).
    """
    token = frappe.db.get_value("User", user, "fcm_token")
    if not token:
        frappe.log_error(message=f"No FCM token for user {user}", title="FCM No Token")
        return {"error": "no_token", "message": f"No token for user {user}"}
    return _send_v1_message_to_token(token, title, body, data)

def send_chat_notification_to_user(user: str, title: str, body: str):
    """
    Send a browser push notification for chat messages.
    Strips HTML from body content before sending.
    """
    try:
        from bs4 import BeautifulSoup
        
        # Strip HTML tags from body
        if body:
            soup = BeautifulSoup(body, 'html.parser')
            body = soup.get_text().strip()
        
        # Send the notification
        return send_push_notification_to_user(user, title, body)
    except Exception as e:
        frappe.log_error(
            message=f"Error sending chat notification to {user}: {str(e)}",
            title="Chat Notification Error"
        )
        return {"error": str(e)}


def extend_bootinfo(bootinfo):
    """Expose firebase config from site_config to frontend"""
    site_config = frappe.get_site_config()
    firebase_config = site_config.get("firebase")

    if firebase_config:
        # Ensure the site_config dict exists
        bootinfo["site_config"] = bootinfo.get("site_config", {})
        bootinfo["site_config"]["firebase"] = firebase_config


@frappe.whitelist()
def create_unread_entry_for_hr(doc, method=None):
    # skip if HR created it
    if "HR" in frappe.get_roles(doc.owner):
        return

    # avoid duplicates
    if frappe.db.exists("HR Read Tracker", {
        "reference_doctype": doc.doctype,
        "reference_name": doc.name
    }):
        return

    hr_users = frappe.get_all("Has Role",
        filters={"role": "HR", "parenttype": "User"},
        pluck="parent"
    )

    for user in hr_users:
        frappe.get_doc({
            "doctype": "HR Read Tracker",
            "reference_doctype": doc.doctype,
            "reference_name": doc.name,
            "read_by": user,
            "is_read": 0
        }).insert(ignore_permissions=True)




@frappe.whitelist()
def mark_hr_item_as_read(doctype, name):
    """Mark document as read for logged-in HR."""
    user = frappe.session.user
    tracker = frappe.db.exists("HR Read Tracker", {
        "reference_doctype": doctype,
        "reference_name": name,
        "read_by": user
    })
    if tracker:
        frappe.db.set_value("HR Read Tracker", tracker, {
            "is_read": 1,
            "read_time": frappe.utils.now()
        })
    frappe.db.commit()


@frappe.whitelist()
def get_unread_count():
    """Return unread count per doctype for the logged-in HR."""
    user = frappe.session.user
    counts = frappe.db.sql("""
        SELECT reference_doctype, COUNT(*) as count
        FROM `tabHR Read Tracker`
        WHERE is_read = 0 AND read_by = %s
        GROUP BY reference_doctype
    """, user, as_dict=True)

    return {row.reference_doctype: row.count for row in counts}

@frappe.whitelist()
def get_attendance_stats(range=None, from_date=None, to_date=None):
    import datetime

    # -----------------------------
    # LOGGED-IN USER
    # -----------------------------
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user": user}, "name")

    today = frappe.utils.getdate()

    # -----------------------------
    # RANGE HANDLING
    # -----------------------------
    if range == "today":
        from_date = to_date = today

    elif range == "week":
        from_date = today - datetime.timedelta(days=today.weekday())
        to_date = today

    elif range == "month":
        from_date = today.replace(day=1)
        to_date = today

    from_date = frappe.utils.getdate(from_date)
    to_date = frappe.utils.getdate(to_date)

    # ============================================================
    # 1️⃣ IF EMPLOYEE NOT LINKED → RETURN GLOBAL COMPANY DATA
    # ============================================================
    if not employee:
        return get_global_attendance_stats(from_date, to_date)

    # ============================================================
    # 2️⃣ EMPLOYEE-WISE ATTENDANCE
    # ============================================================
    return get_employee_attendance_stats(employee, from_date, to_date)



# ==================================================================
# 🔹 GLOBAL ATTENDANCE (ALL EMPLOYEES)
# ==================================================================
def get_global_attendance_stats(from_date, to_date):
    import datetime

    # Get all possible holiday lists
    holiday_list_names = frappe.db.get_list("Holiday List", pluck="name")
    holidays = set()

    if holiday_list_names:
        holiday_rows = frappe.db.get_all(
            "Holidays",
            filters={
                "parent": ["in", holiday_list_names],
                "holiday_date": ["between", [from_date, to_date]],
                "is_working_day": 0
            },
            fields=["holiday_date"]
        )
        holidays = { frappe.utils.getdate(h["holiday_date"]) for h in holiday_rows }

    holiday_count = len(holidays)

    # Count attendance for all employees
    def count(status):
        return frappe.db.count("Attendance", {
            "status": status,
            "attendance_date": ["between", [from_date, to_date]]
        })

    present = count("Present")
    absent = count("Absent")
    half_day = count("Half Day")
    on_leave = count("On Leave")

    # Add holidays into Present count
    present_final = present + holiday_count

    # Missing calculation
    total_days = (to_date - from_date).days + 1
    missing = total_days - (present + absent + half_day + on_leave + holiday_count)
    missing = max(missing, 0)

    return {
        "present": present_final,
        "absent": absent,
        "half_day": half_day,
        "on_leave": on_leave,
        "missing": missing,
        "last_sync": frappe.utils.now()
    }



# ==================================================================
# 🔹 EMPLOYEE-WISE ATTENDANCE
# ==================================================================
def get_employee_attendance_stats(employee, from_date, to_date):
    import datetime

    # Joining date
    doj = frappe.utils.getdate(
        frappe.db.get_value("Employee", employee, "date_of_joining")
    )

    # Holiday list from "Holiday List" (your custom)
    holiday_list_doc = frappe.db.get_value(
        "Holiday List",
        {"year": from_date.year, "month_year": from_date.month},
        "name"
    )

    holidays = set()

    if holiday_list_doc:
        holiday_rows = frappe.db.get_all(
            "Holidays",
            filters={
                "parent": holiday_list_doc,
                "holiday_date": ["between", [from_date, to_date]],
                "is_working_day": 0
            },
            fields=["holiday_date"]
        )
        holidays = { frappe.utils.getdate(h["holiday_date"]) for h in holiday_rows }

    holiday_count = len(holidays)

    # Attendance counts for employee
    def count(status):
        return frappe.db.count("Attendance", {
            "employee": employee,
            "status": status,
            "attendance_date": ["between", [from_date, to_date]]
        })

    present = count("Present")
    absent = count("Absent")
    half_day = count("Half Day")
    on_leave = count("On Leave")

    # Add holidays to present
    present_final = present + holiday_count

    # Missing days
    missing = 0
    cur = from_date

    while cur <= to_date:

        if cur < doj:
            cur += datetime.timedelta(days=1)
            continue

        if cur in holidays:
            cur += datetime.timedelta(days=1)
            continue

        exists = frappe.db.exists(
            "Attendance",
            {"employee": employee, "attendance_date": cur}
        )

        if not exists:
            missing += 1

        cur += datetime.timedelta(days=1)

    return {
        "present": present_final,
        "absent": absent,
        "half_day": half_day,
        "on_leave": on_leave,
        "missing": missing,
        "last_sync": frappe.utils.now()
    }


@frappe.whitelist()
def get_month_holidays(month=None, year=None):
    """
    Fetch holidays for any given month/year.
    """

    today = datetime.today()
    month = int(month) if month else today.month
    year = int(year) if year else today.year

    holiday_lists = frappe.get_all(
        "Holiday List",
        filters={"year": year},
        fields=["name"]
    )

    result = []

    for hl in holiday_lists:
        doc = frappe.get_doc("Holiday List", hl.name)
        for h in doc.holidays:
            if h.holiday_date.month == month and h.holiday_date.year == year and h.is_working_day == 0:
                result.append({
                    "holiday_date": h.holiday_date.strftime("%Y-%m-%d"),
                    "description": h.description
                })

    return result


# Keep the file loaded in memory for performance
LOCATION_CACHE = None

def load_location_data():
    global LOCATION_CACHE
    if LOCATION_CACHE:
        return LOCATION_CACHE

    path = os.path.join(
        get_bench_path(),
        "apps", "company", "company", "utils", "location_data.json"
    )

    with open(path, "r", encoding="utf-8") as f:
        LOCATION_CACHE = json.load(f)

    return LOCATION_CACHE


@frappe.whitelist()
def get_states(country):
    data = load_location_data()

    for c in data:
        if c["country"] == country:
            # return array of state names EXACTLY like old API
            return [state["name"] for state in c["states"]]

    return []


@frappe.whitelist()
def get_cities(country, state):
    data = load_location_data()

    for c in data:
        if c["country"] == country:
            for st in c["states"]:
                if st["name"].lower().strip() == state.lower().strip():
                    # return list of city names EXACTLY like old API
                    return st["cities"]

    return []
    
    
#=================== Convert Estimation to Invoice ==========================

import frappe

@frappe.whitelist()
def convert_estimation_to_invoice(estimation):
    if not estimation:
        frappe.throw("Estimation ID required")

    # Load estimation document
    est = frappe.get_doc("Estimation", estimation)

    # Prevent duplicate conversion
    existing_invoice = frappe.db.get_value(
        "Invoice",
        {"converted_estimation_id": est.name},
        "name"
    )
    if existing_invoice:
        frappe.msgprint(f"Invoice <b>{existing_invoice}</b> already created for this estimation.")
        return existing_invoice

    # Create new invoice
    inv = frappe.new_doc("Invoice")
    inv.flags.ignore_mandatory = True

    # Copy main fields
    fields_to_copy = [
        "total_qty",
        "total_amount",
        "overall_discount_type",
        "overall_discount",
        "grand_total",
        "description"
    ]

    for f in fields_to_copy:
        inv.set(f, est.get(f))
        
    # Customer details
    inv.customer_id = est.client_name

    # Invoice date
    inv.invoice_date = frappe.utils.nowdate()

    # Conversion flags
    inv.converted_from_estimation = 1
    inv.converted_estimation_id = est.name

    # Copy items
    for item in est.get("table_qecz"):
        inv.append("table_qecz", {
            "service": item.service,
            "hsn_code": item.hsn_code,
            "description": item.description,
            "quantity": item.quantity,
            "price": item.price,
            "discount_type": item.discount_type,
            "discount": item.discount,
            "tax_type": item.tax_type,
            "tax_category": item.tax_category,
            "tax_percent": item.tax_percent,
            "tax_amount": item.tax_amount,
            "cgst": item.cgst,
            "sgst": item.sgst,
            "igst": item.igst,
            "sub_total": item.sub_total
        })

    # Save invoice
    inv.insert(ignore_permissions=True, ignore_mandatory=True)

    # SUCCESS MESSAGE
    frappe.msgprint(
        msg=f"Estimation <b>{est.name}</b> successfully converted to Invoice <b>{inv.name}</b>!",
        title="Conversion Complete",
        indicator="green"
    )

    return inv.name


@frappe.whitelist()
def get_current_month_missing_timesheets():
    import calendar
    from datetime import date, timedelta

    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user": user}, "name")

    if not employee:
        return {"error": "No employee linked"}

    today = date.today()
    year = today.year
    month = today.month

    # Month start & end
    first_day = date(year, month, 1)
    last_day = today - timedelta(days=1)

    # ---------------------------
    # 1️⃣ FETCH HOLIDAYS (Your Custom DocType)
    # ---------------------------
    holiday_list_doc = frappe.get_all(
        "Holiday List",
        fields=["name"],
        filters={"year": year, "month_year": month},
        limit=1
    )

    holidays = []
    if holiday_list_doc:
        holiday_list_name = holiday_list_doc[0].name

        holiday_rows = frappe.get_all(
            "Holidays",
            fields=["holiday_date", "is_working_day"],
            filters={"parent": holiday_list_name}
        )

        holidays = [
            h.holiday_date
            for h in holiday_rows
            if not h.is_working_day   # exclude working days
        ]

    # ---------------------------
    # 2️⃣ FETCH EXISTING TIMESHEETS
    # ---------------------------
    existing_ts = [
        d.timesheet_date
        for d in frappe.get_all(
            "Timesheet",
            fields=["timesheet_date"],
            filters={
                "employee": employee,
                "timesheet_date": ["between", [first_day, last_day]]
            }
        )
    ]

    # ---------------------------
    # 3️⃣ CALCULATE MISSING DATES
    # ---------------------------
    missing = []
    current = first_day

    while current <= last_day:

        # Skip Sundays
        if current.weekday() == 6:
            current += timedelta(days=1)
            continue

        # Skip holidays (non-working)
        if current in holidays:
            current += timedelta(days=1)
            continue

        # Skip days already having timesheet
        if current not in existing_ts:
            missing.append(str(current))

        current += timedelta(days=1)

    return missing


@frappe.whitelist()
def get_leave_allocation_by_type(leave_type):
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user": user}, "name")

    if not employee:
        return {
            "allocated": 0,
            "taken": 0,
            "balance": 0
        }

    today = getdate()
    month_start = today.replace(day=1)
    month_end = today

    # Fetch allocations that match leave type AND overlap this month
    allocations = frappe.db.get_all(
        "Leave Allocation",
        filters={
            "employee": employee,
            "leave_type": leave_type,
            "status": "Approved",
            "from_date": ["<=", month_end],
            "to_date": [">=", month_start]
        },
        fields=["total_leaves_allocated", "total_leaves_taken"]
    )

    if not allocations:
        return {
            "allocated": 0,
            "taken": 0,
            "balance": 0
        }

    allocated = sum(a.total_leaves_allocated for a in allocations)
    taken = sum(a.total_leaves_taken for a in allocations)
    balance = allocated - taken

    return {
        "allocated": allocated,
        "taken": taken,
        "balance": balance
    }


from dateutil.relativedelta import relativedelta

@frappe.whitelist()
def is_employee_in_probation():
    user = frappe.session.user

    employee = frappe.db.get_value(
        "Employee",
        {"user": user},
        ["date_of_joining"],
        as_dict=True
    )

    if not employee or not employee.date_of_joining:
        return {"in_probation": False}

    doj = employee.date_of_joining
    today = frappe.utils.getdate()

    # Probation ends exactly 3 months after DOJ
    probation_end = doj + relativedelta(months=+3)

    return {
        "in_probation": today < probation_end
    }


@frappe.whitelist()
def get_today_event():
    user = frappe.session.user

    event = frappe.db.get_value(
        "Flash Message",
        {"enabled": 1, "event_date": frappe.utils.today()},
        ["name", "event_name", "title", "message", "music"],
        as_dict=True
    )

    if not event:
        return

    # Fetch child table entries
    allowed_users = frappe.get_all(
        "Event Popup Allowed User",
        filters={"parent": event.name, "parenttype": "Flash Message"},
        fields=["user"]
    )

    if allowed_users:
        allowed_list = [u.user for u in allowed_users]
        if user not in allowed_list:
            return  # Block popup for this user

    return event

import frappe
import qrcode
import base64
from io import BytesIO

@frappe.whitelist()
def get_upi_qr(upi_string):
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=2
    )
    qr.add_data(upi_string)
    qr.make(fit=True)

    img = qr.make_image(fill='black', back_color='white')

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return encoded

@frappe.whitelist()
def has_invoice_collections(invoice_name):
    count = frappe.db.count("Invoice Collection", {"invoice": invoice_name})
    return count > 0


@frappe.whitelist()
def get_dashboard_stats():

    # ----------------------------------
    # ESTIMATION COUNTS
    # ----------------------------------

    # Converted estimations = Those that appear in Invoice.converted_estimation_id
    converted_list = frappe.db.get_all(
        "Invoice",
        filters={"converted_from_estimation": 1},
        fields=["converted_estimation_id"]
    )

    converted_ids = [d.converted_estimation_id for d in converted_list if d.converted_estimation_id]

    # Total converted estimation count
    converted_estimations = len(converted_ids)

    # Pending estimations = Estimations NOT in converted list
    if converted_ids:
        pending_estimations = frappe.db.count(
            "Estimation",
            filters=[["ref_no", "not in", converted_ids]]
        )
    else:
        # if nothing converted, all are pending
        pending_estimations = frappe.db.count("Estimation")

    # ----------------------------------
    # INVOICE COUNTS
    # ----------------------------------

    invoices = frappe.db.get_all(
        "Invoice",
        filters={"docstatus": 0},
        fields=["name", "balance_amount"]
    )

    total_pending = 0

    for inv in invoices:

        # Fetch latest Invoice Collection entry
        latest = frappe.db.sql("""
            SELECT amount_pending
            FROM `tabInvoice Collection`
            WHERE invoice = %s
            ORDER BY creation DESC
            LIMIT 1
        """, (inv.name,), as_dict=True)

        if latest and latest[0].amount_pending is not None:
            # If collection exists → use latest pending
            pending = latest[0].amount_pending
        else:
            # If no collection → full balance is pending
            pending = inv.balance_amount

        total_pending += pending or 0


    # Count open invoices
    open_invoices = frappe.db.count("Invoice", {"docstatus": 0})


    return {
        "pending_estimations": pending_estimations,
        "converted_estimations": converted_estimations,
        "open_invoices": open_invoices,
        "invoice_pending_amount": total_pending
    }
    
@frappe.whitelist()
def get_job_openings():
    jobs = frappe.get_all(
        "Job Opening",
        filters={"status": "Open"},
        fields="*",
        order_by="posted_on desc"
    )
    return jobs


@frappe.whitelist(allow_guest=True)
def submit_job_application():
    data = frappe.form_dict

    # 1) Validate file
    if "resume_attachment" not in frappe.request.files:
        frappe.throw("Please upload your Resume / CV")

    uploaded_file = frappe.request.files["resume_attachment"]

    # 2) Save file temporarily (without linking)
    temp_file = save_file(
        uploaded_file.filename,
        uploaded_file.read(),
        None,
        None,
        folder=None,
        is_private=1
    )

    # 3) Create Job Applicant with mandatory resume field filled
    doc = frappe.get_doc({
        "doctype": "Job Applicant",
        "applicant_name": data.get("applicant_name"),
        "email_id": data.get("email_id"),
        "phone_number": data.get("phone_number"),
        "state": data.get("state"),
        "city": data.get("city"),
        "job_title": data.get("job_title"),
        "source": data.get("source"),
        "cover_letter": data.get("cover_letter"),
        "resume_attachment": temp_file.file_url,
        "lower_range": data.get("lower_range"),
        "upper_range": data.get("upper_range")
    })

    doc.insert(ignore_permissions=True)

    # 4) Attach file to Job Applicant safely (no timestamp mismatch)
    temp_file.update({
        "attached_to_doctype": "Job Applicant",
        "attached_to_name": doc.name
    })

    frappe.db.commit()

    return {
        "status": "success",
        "message": "Application submitted",
        "applicant_id": doc.name
    }


@frappe.whitelist()
def get_expense_income_summary(filter_type=None, from_date=None, to_date=None):

    conditions_income = ""
    conditions_expense = ""

    # ---------------------- FILTER HANDLING ----------------------
    if filter_type == "today":
        conditions_income = "WHERE date = CURDATE()"
        conditions_expense = "WHERE date = CURDATE()"

    elif filter_type == "this_week":
        conditions_income = "WHERE YEARWEEK(date) = YEARWEEK(CURDATE())"
        conditions_expense = "WHERE YEARWEEK(date) = YEARWEEK(CURDATE())"

    elif filter_type == "this_month":
        conditions_income = "WHERE MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())"
        conditions_expense = "WHERE MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())"

    elif filter_type == "this_year":
        conditions_income = "WHERE YEAR(date) = YEAR(CURDATE())"
        conditions_expense = "WHERE YEAR(date) = YEAR(CURDATE())"

    elif filter_type == "custom" and from_date and to_date:
        conditions_income = f"WHERE date BETWEEN '{from_date}' AND '{to_date}'"
        conditions_expense = f"WHERE date BETWEEN '{from_date}' AND '{to_date}'"


    # ---------------------- QUERY ----------------------
    total_income = frappe.db.sql(f"""
        SELECT IFNULL(SUM(amount), 0)
        FROM `tabIncome`
        {conditions_income}
    """)[0][0]

    total_expense = frappe.db.sql(f"""
        SELECT IFNULL(SUM(total), 0)
        FROM `tabExpense`
        {conditions_expense}
    """)[0][0]

    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense
    }


@frappe.whitelist()
def convert_lead_to_customer(lead_name):
    """
    Convert Lead to Customer
    """

    lead = frappe.get_doc("Leads", lead_name)

    # 🔒 Basic validations
    if not lead.lead_name:
        frappe.throw(_("Lead Name is required"))

    # 🔁 Prevent duplicate Customer (Email / GSTIN)
    if lead.email and frappe.db.exists("Customer", {"email": lead.email}):
        frappe.throw(_("Customer already exists with this Email"))

    if lead.gstin and frappe.db.exists("Customer", {"gstin": lead.gstin}):
        frappe.throw(_("Customer already exists with this GSTIN"))

    # 🧾 Create Customer
    customer = frappe.new_doc("Customer")
    customer.customer_name = lead.lead_name
    customer.company_name = lead.company_name
    customer.gstin = lead.gstin
    customer.phone_number = lead.phone_number
    customer.email = lead.email
    customer.country = lead.country
    customer.state = lead.state
    customer.city = lead.city
    customer.location = lead.location
    customer.billing_address = lead.billing_address
    customer.remarks = lead.remarks
    customer.customer_type = "Sales"
    customer.lead = lead.name
    customer.owner_name = frappe.session.user

    customer.insert(ignore_permissions=True)

    frappe.db.commit()

    return customer.name


@frappe.whitelist()
def send_mail_from_ui(doctype, docname, to, subject, message):
    doc = frappe.get_doc(doctype, docname)

    frappe.sendmail(
        recipients=[to],
        subject=subject,
        message=message,
        attachments=[
            frappe.attach_print(doctype, docname)
        ]
    )

    return "ok"


@frappe.whitelist()
def get_expense_tracker_summary(filter_type="", from_date="", to_date="", expense_type=""):
    filters = []

    if expense_type and expense_type != "All":
        filters.append(["type", "=", expense_type])
    
    # Fallback to creation if date_time is not set
    # Note: Using get_list with filters is easier for standard fields
    
    if filter_type == "today":
        filters.append(["date_time", "between", [today() + " 00:00:00", today() + " 23:59:59"]])
    
    elif filter_type == "this_week":
        start = add_days(today(), -7)
        filters.append(["date_time", "between", [get_date_str(start) + " 00:00:00", today() + " 23:59:59"]])
        
    elif filter_type == "this_month":
        start = get_first_day(today())
        end = get_last_day(today())
        filters.append(["date_time", "between", [get_date_str(start) + " 00:00:00", get_date_str(end) + " 23:59:59"]])

        
    elif filter_type == "this_year":
        year = getdate(today()).year
        filters.append(["date_time", "between", [f"{year}-01-01 00:00:00", f"{year}-12-31 23:59:59"]])
        
    elif filter_type == "custom" and from_date and to_date:
        filters.append(["date_time", "between", [from_date + " 00:00:00", to_date + " 23:59:59"]])


    # We fetch type and amount for all matching records and sum in Python
    # This is very fast for reasonable amounts of data and much easier to debug
    records = frappe.get_all("Expense Tracker", 
        fields=["type", "amount"], 
        filters=filters
    )

    income = 0
    expense = 0
    
    for d in records:
        val = float(d.amount or 0)
        if d.type == "Income":
            income += val
        elif d.type == "Expense":
            expense += val

    return {
        "total_income": income,
        "total_expense": expense,
        "balance": income - expense,
        "debug": {
            "filters": filters,
            "filter_type": filter_type,
            "count": len(records),
            "total_count": frappe.db.count("Expense Tracker")
        }
    }


@frappe.whitelist()
def check_customer_links(customer):
    linked_doctypes = [
        ("Invoice", "customer_id"),
        ("Invoice Collection", "customer_id"),
        ("Estimation", "customer_id"),
        ("Purchase", "customer_id"),
        ("Purchase Collection", "customer_id")
    ]

    for dt, field in linked_doctypes:
        if frappe.db.exists(dt, {field: customer}):
            return True

    return False



