import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta, date, time

class WFHAttendance(Document):
    def validate(self):
        """Automatically set date and calculate total hours"""
        if not self.date:
            self.date = date.today()

        # 🚫 Check for duplicate request on same date for same employee
        existing = frappe.db.exists(
            "WFH Attendance",
            {
                "employee": self.employee,
                "date": self.date,
                "name": ["!=", self.name],  # exclude current record (for edits)
                "docstatus": ["<", 2]       # exclude cancelled
            }
        )

        if existing:
            frappe.throw(
                f"A WFH Attendance request already exists for <b>{self.date}</b> "
            )

        # ✅ Calculate total hours if both times exist
        if self.from_time and self.to_time:
            from_dt = self._get_datetime(self.from_time)
            to_dt = self._get_datetime(self.to_time)

            # Handle overnight (e.g., 22:00 → 02:00)
            if to_dt < from_dt:
                to_dt += timedelta(days=1)

            diff = to_dt - from_dt
            total_minutes = diff.total_seconds() / 60
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            self.total_hours = f"{hours}:{minutes:02d}"

    def after_insert(self):
        """Auto-submit the document immediately after creation"""
        try:
            if self.docstatus == 0:
                frappe.db.commit()  # ensure insert is saved before submit
                self.submit()
                frappe.msgprint("✅ WFH Attendance Submitted.")
                self.notify_hr_for_approval()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "WFH Auto Submit Failed")


    def on_update_after_submit(self):
        """Triggered when HR approves (docstatus=1)"""
        if self.workflow_state == "Approved":
            current_user = frappe.session.user

            # ✅ Set approved_by if not already set
            if not self.approved_by:
                frappe.db.set_value(
                    self.doctype,
                    self.name,
                    "approved_by",
                    current_user,
                    update_modified=False
                )

            # ✅ Create or update Attendance record
            self.create_or_update_attendance()
            self.notify_employee_on_approval()

    def on_cancel(self):
        """Triggered when HR rejects (docstatus=2)"""
        if self.workflow_state == "Rejected":
            frappe.db.set_value(
                self.doctype,
                self.name,
                "approved_by",
                frappe.session.user,
                update_modified=False
            )
            self.notify_employee_on_rejection()

    def create_or_update_attendance(self):
        """Creates or updates Attendance record when HR approves"""
        existing_attendance = frappe.db.exists(
            "Attendance",
            {"employee": self.employee, "attendance_date": self.date}
        )

        # Helper: ensure string format for time fields
        def to_str_time(t):
            if isinstance(t, timedelta):
                total_seconds = int(t.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            elif isinstance(t, time):
                return t.strftime("%H:%M:%S")
            elif isinstance(t, str):
                return t
            return None

        in_time_str = to_str_time(self.from_time)
        out_time_str = to_str_time(self.to_time)

        if existing_attendance:
            # 📝 Update existing attendance
            attendance = frappe.get_doc("Attendance", existing_attendance)
            attendance.status = "Present"
            attendance.in_time = in_time_str
            attendance.out_time = out_time_str
            attendance.total_working_hours = self.total_hours
            attendance.save(ignore_permissions=True)
        else:
            # ➕ Create new attendance
            attendance = frappe.get_doc({
                "doctype": "Attendance",
                "employee": self.employee,
                "attendance_date": self.date,
                "status": "Present",
                "in_time": in_time_str,
                "out_time": out_time_str,
                "manual": 1,
                "total_working_hours": self.total_hours
            })
            attendance.insert(ignore_permissions=True)

    def _get_datetime(self, t):
        """Helper to normalize time field"""
        if isinstance(t, str):
            return datetime.strptime(t, "%H:%M:%S")
        elif isinstance(t, timedelta):
            return datetime.min + t
        elif isinstance(t, time):
            return datetime.combine(date.today(), t)
        frappe.throw(f"Unsupported type for time: {type(t)}")

    def get_hr_settings(self):
        """Fetch HR email and CC from Company Email Settings"""
        settings = frappe.get_all(
            "Company Email Settings",
            fields=["hr_email", "hr_cc_emails"],
            limit=1
        )
        if settings:
            return settings[0]
        return {}

    def notify_hr_for_approval(self):
        """Send email notification to HR when employee submits WFH Attendance"""

        hr_settings = self.get_hr_settings()
        hr_email = hr_settings.get("hr_email")
        cc_emails = hr_settings.get("hr_cc_emails")

        if not hr_email:
            return

        cc_list = []
        if cc_emails:
            cc_list = [e.strip() for e in cc_emails.replace("\n", ",").split(",") if e.strip()]


        # Build sleek purple-styled table
        attendance_details = f"""
            <table style="width:100%; border-collapse:collapse; font-size:14px; border-radius:8px; overflow:hidden;">
                <tr style="background:#f4e8ff;">
                    <td style="padding:10px 12px; font-weight:600; width:160px;">Employee</td>
                    <td style="padding:10px 12px;">{self.employee_name} ({self.employee})</td>
                </tr>
                <tr style="background:#faf7ff;">
                    <td style="padding:10px 12px; font-weight:600;">Date</td>
                    <td style="padding:10px 12px;">{frappe.utils.formatdate(self.date)}</td>
                </tr>
                <tr style="background:#f4e8ff;">
                    <td style="padding:10px 12px; font-weight:600;">From Time</td>
                    <td style="padding:10px 12px;">{self.from_time}</td>
                </tr>
                <tr style="background:#faf7ff;">
                    <td style="padding:10px 12px; font-weight:600;">To Time</td>
                    <td style="padding:10px 12px;">{self.to_time}</td>
                </tr>
                <tr style="background:#f4e8ff;">
                    <td style="padding:10px 12px; font-weight:600;">Total Hours</td>
                    <td style="padding:10px 12px;">{self.total_hours or 'N/A'}</td>
                </tr>
                <tr style="background:#faf7ff;">
                    <td style="padding:10px 12px; font-weight:600;">Task Description</td>
                    <td style="padding:10px 12px;">{self.task_description or '—'}</td>
                </tr>
            </table>
        """

        
        message = f"""
        <div style="font-family: 'Poppins', 'Segoe UI', Arial, sans-serif; background:#f5f2ff; padding:40px;">
            <div style="max-width:600px; margin:auto; background:white; border-radius:14px; 
                        box-shadow:0 4px 10px rgba(110, 0, 180, 0.1); overflow:hidden;">
                
                <div style="background:#7B2CBF; color:white; padding:20px 26px; font-size:18px; 
                            font-weight:600; letter-spacing:0.4px;">
                    New WFH Attendance Request
                </div>

                <div style="padding:26px; color:#333;">
                    <p style="font-size:15px;">Dear <b>HR</b>,</p>
                    <p style="font-size:14px; line-height:1.6; margin-bottom:20px;">
                        A new <b>WFH Attendance</b> request has been submitted by 
                        <b>{self.employee_name}</b> and is pending your approval.
                    </p>

                    <div style="border:1px solid #e0d2ff; border-radius:8px;">
                        {attendance_details}
                    </div>

                    <p style="font-size:14px; color:#555; margin-top:24px;">
                        Please review the request and take the necessary action.
                    </p>

                    <div style="margin-top:30px; text-align:center;">
                        <a href="{frappe.utils.get_url('/app/wfh-attendance/' + self.name)}" 
                        style="background:#7B2CBF; color:white; padding:12px 24px; text-decoration:none; 
                                border-radius:8px; font-size:14px; font-weight:500; letter-spacing:0.3px; display:inline-block;">
                            View in ERP
                        </a>
                    </div>
                </div>

                <div style="background:#f4e8ff; padding:12px 20px; text-align:center; font-size:12px; color:#7B2CBF;">
                    This is an automated notification from your ERP system.
                </div>
            </div>
        </div>
        """

        try:
            frappe.sendmail(
                recipients=[hr_email],
                cc=cc_list,
                subject=f"WFH Approval Request - {self.employee_name} ({frappe.utils.formatdate(self.date)})",
                message=message,
                sender=hr_email,
                reply_to=hr_email,
                reference_doctype=self.doctype,
                reference_name=self.name
            )
        except Exception as e:
            frappe.log_error(f"WFH Submit Mail Error: {str(e)}", "WFH Email Debug")

    def notify_employee_on_approval(self):
        """Send mail to employee when HR approves"""

        emp = frappe.get_doc("Employee", self.employee)
        recipients = [r for r in [emp.email, emp.personal_email] if r]
        if not recipients:
            return

        message = f"""
        <div style="font-family: 'Poppins', 'Segoe UI', Arial, sans-serif; background:#f5f2ff; padding:40px;">
            <div style="max-width:600px; margin:auto; background:white; border-radius:14px;
                        box-shadow:0 4px 12px rgba(0,128,0,0.15); overflow:hidden;">
                
                <div style="background:#28a745; color:white; padding:20px 26px; font-size:18px; font-weight:600;">
                    ✅ WFH Request Approved
                </div>

                <div style="padding:26px; color:#333; font-size:14px; line-height:1.6;">
                    <p>Dear <b>{self.employee_name}</b>,</p>
                    <p>Your <b>Work From Home</b> request has been 
                    <b style="color:#28a745;">approved</b> by HR.</p>

                    <table style="width:100%; border-collapse:collapse; font-size:13px; margin-top:18px; border-radius:8px; overflow:hidden;">
                        <tr style="background:#eaf8f0;">
                            <td style="padding:10px 12px; font-weight:600; width:160px;">Date</td>
                            <td style="padding:10px 12px;">{frappe.utils.formatdate(self.date)}</td>
                        </tr>
                        <tr style="background:#f6fff9;">
                            <td style="padding:10px 12px; font-weight:600;">From Time</td>
                            <td style="padding:10px 12px;">{self.from_time or '-'}</td>
                        </tr>
                        <tr style="background:#eaf8f0;">
                            <td style="padding:10px 12px; font-weight:600;">To Time</td>
                            <td style="padding:10px 12px;">{self.to_time or '-'}</td>
                        </tr>
                        <tr style="background:#f6fff9;">
                            <td style="padding:10px 12px; font-weight:600;">Total Hours</td>
                            <td style="padding:10px 12px;">{self.total_hours or 'N/A'}</td>
                        </tr>
                    </table>

                    <div style="text-align:center; margin-top:28px;">
                        <a href="{frappe.utils.get_url('/app/wfh-attendance/' + self.name)}"
                        style="background:#28a745; color:white; padding:12px 24px; text-decoration:none;
                                border-radius:8px; font-size:14px; font-weight:500;">
                        View in ERP
                        </a>
                    </div>
                </div>

                <div style="background:#d4edda; padding:12px 20px; text-align:center;
                            font-size:12px; color:#155724;">
                    This is an automated message from your ERP system.
                </div>
            </div>
        </div>
        """

        hr_settings = self.get_hr_settings()
        hr_email = hr_settings.get("hr_email")

        frappe.sendmail(
            recipients=recipients,
            subject=f"✅ WFH Approved - {frappe.utils.formatdate(self.date)}",
            message=message,
            sender=hr_email,
            reply_to=hr_email,
            reference_doctype=self.doctype,
            reference_name=self.name
        )

    def notify_employee_on_rejection(self):
        """Send mail to employee when HR rejects"""

        emp = frappe.get_doc("Employee", self.employee)
        recipients = [r for r in [emp.email, emp.personal_email] if r]
        if not recipients:
            return

        message = f"""
        <div style="font-family: 'Poppins', 'Segoe UI', Arial, sans-serif; background:#f5f2ff; padding:40px;">
            <div style="max-width:600px; margin:auto; background:white; border-radius:14px;
                        box-shadow:0 4px 12px rgba(220,53,69,0.15); overflow:hidden;">
                
                <div style="background:#dc3545; color:white; padding:20px 26px; font-size:18px; font-weight:600;">
                    ❌ WFH Request Rejected
                </div>

                <div style="padding:26px; color:#333; font-size:14px; line-height:1.6;">
                    <p>Dear <b>{self.employee_name}</b>,</p>
                    <p>Your <b>Work From Home</b> request has been 
                    <b style="color:#dc3545;">rejected</b> by HR.</p>

                    <table style="width:100%; border-collapse:collapse; font-size:13px; margin-top:18px; border-radius:8px; overflow:hidden;">
                        <tr style="background:#f8d7da;">
                            <td style="padding:10px 12px; font-weight:600; width:160px;">Date</td>
                            <td style="padding:10px 12px;">{frappe.utils.formatdate(self.date)}</td>
                        </tr>
                        <tr style="background:#fff5f5;">
                            <td style="padding:10px 12px; font-weight:600;">From Time</td>
                            <td style="padding:10px 12px;">{self.from_time or '-'}</td>
                        </tr>
                        <tr style="background:#f8d7da;">
                            <td style="padding:10px 12px; font-weight:600;">To Time</td>
                            <td style="padding:10px 12px;">{self.to_time or '-'}</td>
                        </tr>
                    </table>

                    <div style="text-align:center; margin-top:28px;">
                        <a href="{frappe.utils.get_url('/app/wfh-attendance/' + self.name)}"
                        style="background:#dc3545; color:white; padding:12px 24px; text-decoration:none;
                                border-radius:8px; font-size:14px; font-weight:500;">
                        View Request
                        </a>
                    </div>
                </div>

                <div style="background:#f8d7da; padding:12px 20px; text-align:center;
                            font-size:12px; color:#721c24;">
                    This is an automated message from your ERP system.
                </div>
            </div>
        </div>
        """

        hr_settings = self.get_hr_settings()
        hr_email = hr_settings.get("hr_email")

        frappe.sendmail(
            recipients=recipients,
            subject=f"❌ WFH Rejected - {frappe.utils.formatdate(self.date)}",
            message=message,
            sender=hr_email,
            reply_to=hr_email,
            reference_doctype=self.doctype,
            reference_name=self.name
        )
