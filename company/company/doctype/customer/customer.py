# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

from company.company.api import check_customer_links
import frappe
from frappe.model.document import Document


class Customer(Document):
    def validate(self):
        # Check for duplicate phone number only if phone_number is provided
        if self.phone_number:
            if frappe.db.exists(
                "Customer",
                {
                    "phone_number": self.phone_number,
                    "name": ["!=", self.name]
                }
            ):
                frappe.throw("Phone number already exists")
            
        if check_customer_links(self.name):
            frappe.throw("This Customer has linked records and cannot be modified.")

    def on_trash(self):
        if check_customer_links(self.name):
            frappe.throw("This Customer cannot be deleted because linked transactions exist.")
