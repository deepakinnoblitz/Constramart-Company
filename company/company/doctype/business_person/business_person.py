# Copyright (c) 2026, deepak and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe import _
from frappe.model.document import Document


class BusinessPerson(Document):
    def validate(self):
        # Handle whitespace
        if self.business_person_name:
            self.business_person_name = self.business_person_name.strip()
            
            # Check for duplicate name
            # Use self.name or "" to avoid SQL issues with None (name != NULL is always False)
            exists = frappe.db.exists(
                "Business Person",
                {
                    "business_person_name": self.business_person_name,
                    "name": ["!=", self.name or ""]
                }
            )
            if exists:
                frappe.throw(_("Business Person '{0}' already exists.").format(self.business_person_name))

        if self.phone_number:
            self.phone_number = self.phone_number.strip()
            exists = frappe.db.exists(
                "Business Person",
                {
                    "phone_number": self.phone_number,
                    "name": ["!=", self.name]
                }
            )
            if exists:
                frappe.throw(_("Phone Number {0} already exists for {1}").format(self.phone_number, exists))

