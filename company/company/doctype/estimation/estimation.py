import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import getdate

class Estimation(Document):
    
    def validate(self):
        self.calculate_child_rows()
        self.calculate_totals()
    
    def autoname(self):
        # Set name = ref_no
        if self.ref_no:
            self.name = self.ref_no

    def before_insert(self):
        today = getdate()
        year = today.year

        # Financial Year (April → March)
        if today.month < 4:
            start_year = year - 1
            end_year = year
        else:
            start_year = year
            end_year = year + 1

        fy = f"{str(start_year)[-2:]}-{str(end_year)[-2:]}"

        # ✅ Use correct make_autoname format with dot
        seq = make_autoname(".###", doc=self)  # IB-E/.001, .002, etc.

        # Assign to ref_no (which will also become name)
        self.ref_no = f"IB-E/{fy}/{seq.split('.')[-1]}"
        
        
    def calculate_child_rows(self):
        for item in self.table_qecz:
            item.calculate_tax_split()

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

    def on_trash(self):
        # Prevent deletion if an Invoice has been created from this estimation
        linked_invoice = frappe.db.get_value("Invoice", {"converted_estimation_id": self.name}, "name")
        if linked_invoice:
            frappe.throw(
                frappe._("Cannot delete Estimation {0} because it has already been converted to Invoice {1}. "
                         "Please delete the Invoice first if you wish to remove this Estimation.").format(
                    frappe.bold(self.name),
                    frappe.bold(linked_invoice)
                )
            )