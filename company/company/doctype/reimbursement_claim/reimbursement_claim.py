import frappe
from frappe.model.document import Document

class ReimbursementClaim(Document):

    # ----------------------------------------
    # 1️⃣ Notify HR when employee submits claim
    # ----------------------------------------
    def on_submit(self):
        self.notify_hr_on_submission()

    # ----------------------------------------
    # 2️⃣ + 3️⃣ + 4️⃣ Handle workflow updates after submit
    # ----------------------------------------
    def on_update_after_submit(self):

        current_state = self.workflow_state
        previous_state = self.get_db_value("workflow_state")
        user = frappe.session.user

        approver_name = frappe.db.get_value("User", user, "full_name")
        approver_email = frappe.db.get_value("User", user, "email")

		# ----------------------------------------
		# 2️⃣ Send approval email ONLY once
		# ----------------------------------------
        if current_state == "Approved" and previous_state != "Paid":
            frappe.db.set_value(self.doctype, self.name, "approved_by", user, update_modified=False)
            self.notify_employee_on_approval(approver_name, approver_email)

		# ----------------------------------------
		# 4️⃣ Send Paid mail — ONLY when state is PAID
		# ----------------------------------------
        if current_state == "Paid":
            frappe.db.set_value(self.doctype, self.name, "paid_by", user, update_modified=False)
            self.notify_employee_on_payment(approver_name, approver_email)

    def on_cancel(self):
        current_state = self.workflow_state
        previous_state = self.get_db_value("workflow_state")
        user = frappe.session.user

        approver_name = frappe.db.get_value("User", user, "full_name")
        approver_email = frappe.db.get_value("User", user, "email")
		
        # ----------------------------------------
		# 3️⃣ Send Rejection mail normally
		# ----------------------------------------
        if current_state == "Rejected":
            frappe.db.set_value(self.doctype, self.name, "approved_by", user, update_modified=False)
            self.notify_employee_on_rejection(approver_name, approver_email)


    # -------------------------------------------------------------------
    # 1️⃣ Email — Notify HR on Submission (Blue Theme)
    # -------------------------------------------------------------------
    def notify_hr_on_submission(self):
        settings = frappe.get_all(
            "Company Email Settings",
            fields=["hr_email", "hr_cc_emails"],
            limit=1
        )

        if not settings:
            return

        hr_email = settings[0].get("hr_email")
        cc_raw = settings[0].get("hr_cc_emails") or ""
        cc_emails = [e.strip() for e in cc_raw.replace("\n", ",").split(",") if e.strip()]

        message = f"""
        <div style="font-family:'Poppins',Arial;background:#e6f3ff;padding:40px;">
            <div style="max-width:600px;margin:auto;background:white;border-radius:14px;
                        box-shadow:0 4px 12px rgba(0,128,255,0.15);overflow:hidden;">
                
                <div style="background:#0d6efd;color:white;padding:20px 26px;font-size:18px;font-weight:600;">
                    🧾 New Reimbursement Claim Submitted
                </div>

                <div style="padding:26px;color:#333;line-height:1.6;">
                    <p>Dear HR,</p>
                    <p><b>{self.employee_name}</b> has submitted a reimbursement claim.</p>

                    <table style="width:100%;font-size:13px;margin-top:18px;border-collapse:collapse;">
                        <tr style="background:#f0f7ff;">
                            <td style="padding:10px 12px;font-weight:600;">Claim Type</td>
                            <td style="padding:10px 12px;">{self.claim_type}</td>
                        </tr>
                        <tr style="background:#f7fbff;">
                            <td style="padding:10px 12px;font-weight:600;">Amount</td>
                            <td style="padding:10px 12px;">₹ {self.amount}</td>
                        </tr>
                        <tr style="background:#f0f7ff;">
                            <td style="padding:10px 12px;font-weight:600;">Date of Expense</td>
                            <td style="padding:10px 12px;">{self.date_of_expense}</td>
                        </tr>
                    </table>

                    <div style="text-align:center;margin-top:28px;">
                        <a href="{frappe.utils.get_url('/app/reimbursement-claim/' + self.name)}"
                            style="background:#0d6efd;color:white;padding:12px 24px;text-decoration:none;
                            border-radius:8px;font-weight:500;">Open Claim</a>
                    </div>
                </div>
            </div>
        </div>
        """

        frappe.sendmail(
            recipients=[hr_email],
            cc=cc_emails,
            subject=f"🧾 Reimbursement Claim Submitted - {self.employee_name}",
            message=message,
            reference_doctype=self.doctype,
            reference_name=self.name,
        )

    # -------------------------------------------------------------------
    # 2️⃣ Email — Notify Employee on Approval (Green Theme)
    # -------------------------------------------------------------------
    def notify_employee_on_approval(self, approver_name, approver_email):

        company_email = frappe.db.get_value("Employee", self.employee, "email")
        personal_email = frappe.db.get_value("Employee", self.employee, "personal_email")

        recipients = [email for email in [company_email, personal_email] if email]

        if not recipients:
            return

        message = f"""
        <div style="font-family:'Poppins',Arial;background:#f1fff4;padding:40px;">
            <div style="max-width:600px;margin:auto;background:white;border-radius:14px;
                box-shadow:0 4px 12px rgba(0,128,0,0.15);overflow:hidden;">
                
                <div style="background:#28a745;color:white;padding:20px 26px;font-size:18px;font-weight:600;">
                    ✅ Reimbursement Approved
                </div>

                <div style="padding:26px;color:#333;">
                    <p>Hello <b>{self.employee_name}</b>,</p>
                    <p>Your reimbursement claim has been <b style="color:#28a745;">approved</b>.</p>

                    <p><b>Approved By:</b> {approver_name} ({approver_email})</p>

                    <table style="width:100%;font-size:13px;margin-top:20px;border-collapse:collapse;">
                        <tr style="background:#e7f9ed;">
                            <td style="padding:10px 12px;font-weight:600;">Claim Type</td>
                            <td style="padding:10px 12px;">{self.claim_type}</td>
                        </tr>
                        <tr style="background:#f5fff7;">
                            <td style="padding:10px 12px;font-weight:600;">Amount</td>
                            <td style="padding:10px 12px;">₹ {self.amount}</td>
                        </tr>
                    </table>

                    <div style="text-align:center;margin-top:28px;">
                        <a href="{frappe.utils.get_url('/app/reimbursement-claim/' + self.name)}"
                        style="background:#28a745;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;">
                        View Claim</a>
                    </div>
                </div>
            </div>
        </div>
        """

        frappe.sendmail(
            recipients=recipients,
            subject=f"✅ Reimbursement Approved - {self.claim_type}",
            message=message,
        )

    # -------------------------------------------------------------------
    # 3️⃣ Email — Notify Employee on Rejection (Red Theme)
    # -------------------------------------------------------------------
    def notify_employee_on_rejection(self, rejector_name, rejector_email):

        company_email = frappe.db.get_value("Employee", self.employee, "email")
        personal_email = frappe.db.get_value("Employee", self.employee, "personal_email")

        recipients = [email for email in [company_email, personal_email] if email]

        if not recipients:
            return

        message = f"""
        <div style="font-family:'Poppins',Arial;background:#fff1f1;padding:40px;">
            <div style="max-width:600px;margin:auto;background:white;border-radius:14px;
                box-shadow:0 4px 12px rgba(255,0,0,0.15);overflow:hidden;">
                
                <div style="background:#dc3545;color:white;padding:20px 26px;font-size:18px;font-weight:600;">
                    ❌ Reimbursement Rejected
                </div>

                <div style="padding:26px;color:#333;">
                    <p>Hello <b>{self.employee_name}</b>,</p>
                    <p>Your reimbursement claim has been <b style="color:#dc3545;">rejected</b>.</p>

                    <p><b>Rejected By:</b> {rejector_name} ({rejector_email})</p>

                    <table style="width:100%;font-size:13px;margin-top:20px;border-collapse:collapse;">
                        <tr style="background:#ffe8e8;">
                            <td style="padding:10px 12px;font-weight:600;">Claim Type</td>
                            <td style="padding:10px 12px;">{self.claim_type}</td>
                        </tr>
                        <tr style="background:#fff5f5;">
                            <td style="padding:10px 12px;font-weight:600;">Amount</td>
                            <td style="padding:10px 12px;">₹ {self.amount}</td>
                        </tr>
                    </table>

                    <div style="text-align:center;margin-top:28px;">
                        <a href="{frappe.utils.get_url('/app/reimbursement-claim/' + self.name)}"
                        style="background:#dc3545;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;">
                        View Claim</a>
                    </div>
                </div>
            </div>
        </div>
        """

        frappe.sendmail(
            recipients=recipients,
            subject=f"❌ Reimbursement Rejected - {self.claim_type}",
            message=message,
        )

    # -------------------------------------------------------------------
    # 4️⃣ Email — Notify Employee on Payment (Green-Blue Theme)
    # -------------------------------------------------------------------
    def notify_employee_on_payment(self, approver_name, approver_email):

        company_email = frappe.db.get_value("Employee", self.employee, "email")
        personal_email = frappe.db.get_value("Employee", self.employee, "personal_email")

        recipients = [email for email in [company_email, personal_email] if email]

        if not recipients:
            return

        message = f"""
        <div style="font-family:'Poppins',Arial;background:#e7f7ff;padding:40px;">
            <div style="max-width:600px;margin:auto;background:white;border-radius:14px;
                box-shadow:0 4px 12px rgba(0,128,255,0.15);overflow:hidden;">
                
                <div style="background:#007bff;color:white;padding:20px 26px;font-size:18px;font-weight:600;">
                    💰 Reimbursement Paid
                </div>

                <div style="padding:26px;color:#333;">
                    <p>Hello <b>{self.employee_name}</b>,</p>
                    <p>Your reimbursement amount has been <b style="color:#007bff;">paid</b>.</p>

                    <table style="width:100%;font-size:13px;margin-top:20px;border-collapse:collapse;">
                        <tr style="background:#eaf4ff;">
                            <td style="padding:10px 12px;font-weight:600;">Claim Type</td>
                            <td style="padding:10px 12px;">{self.claim_type}</td>
                        </tr>
                        <tr style="background:#f5faff;">
                            <td style="padding:10px 12px;font-weight:600;">Amount Paid</td>
                            <td style="padding:10px 12px;">₹ {self.amount}</td>
                        </tr>
                        <tr style="background:#eaf4ff;">
                            <td style="padding:10px 12px;font-weight:600;">Payment Reference</td>
                            <td style="padding:10px 12px;">{self.payment_reference or '-'}</td>
                        </tr>
                    </table>

                    <div style="text-align:center;margin-top:28px;">
                        <a href="{frappe.utils.get_url('/app/reimbursement-claim/' + self.name)}"
                        style="background:#007bff;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;">
                        View Claim</a>
                    </div>
                </div>
            </div>
        </div>
        """

        frappe.sendmail(
            recipients=recipients,
            subject=f"💰 Reimbursement Paid - {self.claim_type}",
            message=message,
        )
