# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Purchase(Document):
    
    def validate(self):
        # Check if Purchase Collection exists - prevent editing
        if not self.is_new():
            self.check_purchase_collections()
        
        self.calculate_child_rows()
        self.calculate_totals()
    
    def check_purchase_collections(self):
        """Prevent editing or deleting if Purchase Collection entries exist"""
        collections = frappe.db.count("Purchase Collection", {"purchase": self.name})
        if collections > 0:
            frappe.throw(
                frappe._("Cannot modify Purchase {0} because {1} Payment Collection(s) exist. "
                "Please delete the Payment Collections before modifying this Purchase.").format(
                    frappe.bold(self.name),
                    frappe.bold(collections)
                )
            )

    def on_trash(self):
        self.check_purchase_collections()
    
    def calculate_child_rows(self):
        for item in self.table_qecz:
            item.calculate_tax()

    def calculate_totals(self):
        total = 0
        total_qty = 0

        for item in self.table_qecz:
            total += item.sub_total or 0
            total_qty += item.quantity or 0

        # Assign raw totals
        self.total_qty = total_qty
        self.total_amount = total

        # Apply Overall Discount
        overall_disc = float(self.overall_discount or 0)
        disc_type = self.overall_discount_type or "Flat"

        if disc_type == "Flat":
            total -= overall_disc
        elif disc_type == "Percentage":
            total -= (total * overall_disc / 100)

        if total < 0:
            total = 0

        self.grand_total = total + (frappe.utils.flt(self.roundoff) if hasattr(self, 'roundoff') else 0)
