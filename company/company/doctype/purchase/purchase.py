# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Purchase(Document):
    
    def validate(self):
        # Auto-fill invoice_id from reference_invoice if missing (Back-end Handshake)
        if self.reference_invoice and not self.invoice_id:
            self.invoice_id = self.reference_invoice

        for item in self.get("table_qecz"):
            if frappe.utils.flt(item.price) <= 0:
                frappe.throw(frappe._("Price cannot be 0 or less for item {0} in row {1}").format(
                    frappe.bold(item.service or "Unknown"),
                    frappe.bold(item.idx)
                ))

        # Check if Purchase Collection exists - prevent editing
        if not self.is_new():
            self.check_purchase_collections()
        
        self.validate_invoice_link()
        self.calculate_child_rows()
        self.calculate_totals()

    def validate_invoice_link(self):
        if self.invoice_id:
            # Check if this invoice is already linked to another Purchase
            # We check both the 'reference_purchase' (updated on save) AND 'purchase_id' (if it was linked from Invoice form)
            invoice_data = frappe.db.get_value("Invoice", self.invoice_id, ["reference_purchase", "purchase_id"], as_dict=True)
            
            if not invoice_data:
                return

            existing_purchase = invoice_data.reference_purchase or invoice_data.purchase_id
            
            if existing_purchase and existing_purchase != self.name:
                # Fetch Names for better display
                invoice_name = frappe.db.get_value("Invoice", self.invoice_id, "customer_name")
                purchase_vendor = frappe.db.get_value("Purchase", existing_purchase, "vendor_name")
                
                frappe.throw(
                    frappe._("Invoice {0} ({1}) is already linked to Purchase {2} ({3}). Please select a different Invoice.").format(
                        frappe.bold(self.invoice_id),
                        frappe.bold(invoice_name or "Unknown"),
                        frappe.bold(existing_purchase),
                        frappe.bold(purchase_vendor or "Unknown")
                    )
                )
    
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
        # Clear Invoice reference when Purchase is deleted
        if self.invoice_id:
            frappe.db.set_value("Invoice", self.invoice_id, "reference_purchase", None)

    def on_update(self):
        """Ensure Invoice reference is synchronized with this Purchase"""
        if self.invoice_id:
            # Set this Purchase as the reference on the linked Invoice
            frappe.db.set_value("Invoice", self.invoice_id, "reference_purchase", self.name)
        else:
            # If invoice_id was cleared, remove the reference from the old invoice
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.invoice_id:
                frappe.db.set_value("Invoice", old_doc.invoice_id, "reference_purchase", None)
    
    def after_insert(self):
        # Update Invoice with Purchase reference
        if self.invoice_id:
            frappe.db.set_value("Invoice", self.invoice_id, "reference_purchase", self.name)
    
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
        
        # Sync Paid Amount and Balance Amount (Final Authority - Always recalculate on save)
        if self.name:
            total_paid = frappe.db.sql("""
                SELECT SUM(amount_paid) FROM `tabPurchase Collection`
                WHERE purchase = %s
            """, (self.name,))[0][0] or 0
            self.paid_amount = frappe.utils.flt(total_paid)
        else:
            self.paid_amount = 0
            
        self.balance_amount = frappe.utils.flt(self.grand_total) - self.paid_amount
        
        # Update status
        if self.paid_amount == 0:
            self.purchase_status = "Pending"
        elif self.balance_amount > 0:
            self.purchase_status = "Partially Paid"
        else:
            self.purchase_status = "Fully Paid"
