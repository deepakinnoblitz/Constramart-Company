import frappe
from frappe.model.document import Document
from frappe.utils import formatdate, get_url


class LeaveApplication(Document):

    # =================================================
    # EMPLOYEE SUBMITS LEAVE → MAIL HR
    # =================================================
    def before_save(self):
        self.send_submit_mail_to_hr()

    # =================================================
    # ALL WORKFLOW CHANGES AFTER SUBMIT
    # =================================================
    def on_update_after_submit(self):
        before = self.get_doc_before_save()

        # 🚫 HARD STOP: first submit
        if before and before.docstatus == 0 and self.docstatus == 1:
            return

        self.send_workflow_mail()

    # =================================================
    # HANDLE REJECTION / CANCELLATION
    # =================================================
    def on_cancel(self):
        hr_settings = self.get_hr_settings()
        hr_email = hr_settings.get("hr_email")
        
        employee_email = frappe.get_value("Employee", self.employee, "personal_email")

        self.send_email(
            recipients=[employee_email],
            subject="❌ Leave Rejected",
            header="Leave Rejected",
            icon="❌",
            intro="Your leave application has been rejected/cancelled.",
            color="#dc3545",
            sender=hr_email,
            reply_to=hr_email
        )

    # =================================================
    # GET HR EMAIL SETTINGS
    # =================================================
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

    # =================================================
    # 1️⃣ EMPLOYEE SUBMIT → HR
    # =================================================
    def send_submit_mail_to_hr(self):
        hr_settings = self.get_hr_settings()
        hr_email = hr_settings.get("hr_email")
        cc_emails = hr_settings.get("hr_cc_emails")

        if not hr_email:
            return

        cc_list = []
        if cc_emails:
            cc_list = [e.strip() for e in cc_emails.replace("\n", ",").split(",") if e.strip()]

        self.send_email(
            recipients=[hr_email],
            cc=cc_list,
            subject=f"📩 New Leave Request - {self.employee_name}",
            header="New Leave Request",
            icon="📩",
            intro=f"{self.employee_name} has submitted a leave application.",
            color="#0062cc",
            sender=hr_email,
            reply_to=hr_email
        )

    # =================================================
    # WORKFLOW MAIL HANDLER
    # =================================================
    def send_workflow_mail(self):

        before = self.get_doc_before_save()
        if not before:
            return

        previous_state = before.workflow_state
        current_state = self.workflow_state

        # 🚫 Skip if no workflow transition
        if previous_state == current_state:
            return

        hr_settings = self.get_hr_settings()
        hr_email = hr_settings.get("hr_email")
        
        employee_email = frappe.get_value("Employee", self.employee, "personal_email")

        # -------------------------------------------------
        # HR → ASK CLARIFICATION → EMPLOYEE
        # -------------------------------------------------
        if current_state == "Clarification Requested":
            hr_msg = self.get_latest_hr_query()

            self.send_email(
                recipients=[employee_email],
                subject="📩 Reply from HR - Leave Application",
                header="Reply from HR",
                icon="📩",
                intro="HR has replied to your leave application.",
                extra_message=self.hr_message_block(hr_msg),
                color="#ffc107",
                sender=hr_email,
                reply_to=hr_email
            )

        # -------------------------------------------------
        # EMPLOYEE → REPLY → HR
        # -------------------------------------------------
        elif current_state == "Pending" and previous_state == "Clarification Requested":
            emp_reply = self.get_latest_employee_reply()
            
            cc_emails = hr_settings.get("hr_cc_emails")
            cc_list = []
            if cc_emails:
                cc_list = [e.strip() for e in cc_emails.replace("\n", ",").split(",") if e.strip()]

            self.send_email(
                recipients=[hr_email],
                cc=cc_list,
                subject=f"📩 Reply from Employee - {self.employee_name}",
                header="Reply Received",
                icon="📩",
                intro=f"{self.employee_name} has replied to your clarification request.",
                extra_message=self.employee_reply_block(emp_reply),
                color="#0062cc",
                sender=hr_email,
                reply_to=hr_email
            )

        # -------------------------------------------------
        # HR → APPROVE → EMPLOYEE ONLY
        # -------------------------------------------------
        elif current_state == "Approved":
            self.send_email(
                recipients=[employee_email],
                subject="✅ Leave Approved",
                header="Leave Approved",
                icon="✅",
                intro="Your leave application has been approved.",
                color="#28a745",
                sender=hr_email,
                reply_to=hr_email
            )

    # =================================================
    # FETCH LATEST HR QUERY
    # =================================================
    def get_latest_hr_query(self):
        for i in range(5, 0, -1):
            field = f"hr_query_{i}" if i > 1 else "hr_query"
            val = getattr(self, field, None)
            if val:
                return val
        return None

    # =================================================
    # FETCH LATEST EMPLOYEE REPLY
    # =================================================
    def get_latest_employee_reply(self):
        for i in range(5, 0, -1):
            field = f"employee_reply_{i}" if i > 1 else "employee_reply"
            val = getattr(self, field, None)
            if val:
                return val
        return None

    # =================================================
    # HR MESSAGE BLOCK (YELLOW)
    # =================================================
    def hr_message_block(self, message):
        if not message:
            return ""

        return f"""
        <div style="
            margin-top:18px;
            padding:16px;
            background:#fff3cd;
            border-left:5px solid #ffc107;
            border-radius:6px;
        ">
            <b style="color:#856404;">HR Clarification:</b><br>
            <p style="margin:6px 0 0; font-style:italic;">
                “{message}”
            </p>
        </div>
        """

    # =================================================
    # EMPLOYEE REPLY BLOCK (BLUE)
    # =================================================
    def employee_reply_block(self, message):
        if not message:
            return ""

        return f"""
        <div style="
            margin-top:18px;
            padding:16px;
            background:#e1f5fe;
            border-left:5px solid #03a9f4;
            border-radius:6px;
        ">
            <b style="color:#01579b;">Employee Reply:</b><br>
            <p style="margin:6px 0 0; font-style:italic;">
                “{message}”
            </p>
        </div>
        """

    # =================================================
    # COMMON EMAIL SENDER
    # =================================================
    def send_email(
        self,
        recipients,
        subject,
        header,
        intro,
        color="#28a745",
        icon="✅",
        cc=None,
        extra_message="",
        sender=None,
        reply_to=None
    ):
        
        # Determine background color for leave details block
        bg_color = "#f0fff4" # default green-ish
        if color == "#dc3545": bg_color = "#fff5f5" # red-ish
        elif color == "#ffc107": bg_color = "#fffdeb" # yellow-ish
        elif color == "#0062cc": bg_color = "#f0f7ff" # blue-ish

        leave_details = f"""
        <div style="background:{bg_color}; padding:15px; border-radius:8px; margin-top:20px; border:1px solid rgba(0,0,0,0.05);">
            <table style="width:100%; border-collapse:collapse;">
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding:10px 0; color:#555;"><b>Employee</b></td>
                    <td style="padding:10px 0; text-align:right;">{self.employee_name}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding:10px 0; color:#555;"><b>Leave Type</b></td>
                    <td style="padding:10px 0; text-align:right;">{self.leave_type}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding:10px 0; color:#555;"><b>From</b></td>
                    <td style="padding:10px 0; text-align:right;">{formatdate(self.from_date)}</td>
                </tr>
                <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
                    <td style="padding:10px 0; color:#555;"><b>To</b></td>
                    <td style="padding:10px 0; text-align:right;">{formatdate(self.to_date)}</td>
                </tr>
                <tr>
                    <td style="padding:10px 0; color:#555;"><b>Total Days</b></td>
                    <td style="padding:10px 0; text-align:right;">{self.total_days}</td>
                </tr>
            </table>
        </div>
        """

        message = f"""
        <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; padding: 40px 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <!-- Header -->
                <div style="background-color: {color}; padding: 15px 20px; color: #ffffff; border-bottom: 4px solid rgba(0,0,0,0.1);">
                    <table style="width:100%; border-collapse:collapse;">
                        <tr>
                            <td style="vertical-align: middle; width: 30px; font-size: 22px; line-height: 1;">
                                {icon}
                            </td>
                            <td style="vertical-align: middle; padding-left: 8px; font-size: 18px; font-weight: bold; line-height: 1;">
                                {header}
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="padding: 30px; color: #333;">
                    <p style="font-size: 16px; margin-bottom: 5px;">Hello ,</p>
                    <p style="font-size: 15px; line-height: 1.5; color: #555;">{intro}</p>
                    
                    {leave_details}
                    
                    {extra_message}
                    
                    <!-- Action Button -->
                    <div style="text-align: center; margin-top: 30px;">
                        <a href="{get_url('/app/leave-application/' + self.name)}" 
                           style="background-color: {color}; color: #ffffff; padding: 12px 25px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                            View Leave Application
                        </a>
                    </div>
                </div>
            </div>
            <div style="text-align: center; margin-top: 20px; color: #888; font-size: 12px;">
                This is an automated notification from Innoblitz ERP.
            </div>
        </div>
        """

        frappe.sendmail(
            recipients=[r for r in recipients if r],
            cc=cc,
            subject=subject,
            message=message,
            sender=sender,
            reply_to=reply_to,
            reference_doctype="Leave Application",
            reference_name=self.name
        )
