# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

class Lead(Document):

    def on_update(self):
        self.date_and_time = now_datetime()

    def calculate_lead_score(self):
        score = 0
        max_score = 30  # total possible score

        # Email available
        if self.email:
            score += 10

        # Phone available
        if self.phone_number:
            score += 10

        # Company Name available
        if self.company_name:
            score += 5

        # GSTIN available
        if self.gstin:
            score += 5

        # Convert to percentage
        self.lead_score = (score / max_score) * 100

    def before_save(self):
        self.calculate_lead_score()
        self.log_pipeline_timeline()

    def log_pipeline_timeline(self):
        # New document → no previous state
        if self.is_new():
            return

        # Get previous workflow_state
        old_state = frappe.db.get_value(
            "Lead",
            self.name,
            "workflow_state"
        )

        new_state = self.workflow_state


        # If no change → do nothing
        if not old_state or old_state == new_state:
            return

        # Append child table row
        self.append("converted_pipeline_timeline", {
            "state_from": old_state,
            "state_to": new_state,
            "date_and_time": now_datetime(),
            "change_by": frappe.session.user
        })