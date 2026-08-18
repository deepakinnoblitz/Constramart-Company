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
            
        if not self.is_new():
            old_doc = self.get_doc_before_save()
            if old_doc and float(old_doc.opening_balance or 0) != float(self.opening_balance or 0):
                if frappe.db.exists("Invoice", {"customer_id": self.name}):
                    frappe.throw("Opening Balance cannot be edited manually because Sales Bills exist for this Customer.")

        if check_customer_links(self.name):
            frappe.throw("This Customer has linked records and cannot be modified.")

    def on_trash(self):
        if check_customer_links(self.name):
            frappe.throw("This Customer cannot be deleted because linked transactions exist.")


@frappe.whitelist()
def refresh_customer_status(customer):
    if not customer:
        return False
    invoice_count = frappe.db.count("Invoice", filters={"customer_id": customer})
    new_status = "Old Customer" if invoice_count >= 2 else "New Customer"
    frappe.db.set_value("Customer", customer, "customer_status", new_status)
    customer_doc = frappe.get_doc("Customer", customer)
    customer_doc.notify_update()
    frappe.publish_realtime("customer_status_updated", {"customer": customer, "status": new_status})
    return new_status
