import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import getdate, flt

class Invoice(Document):
    
    def validate(self):
        if not self.is_new():
            self.ensure_no_linked_collections()
        
        if not self.get("table_qecz"):
            frappe.throw(_("At least one item is required in the Items table."))

        self.validate_purchase_link()
        self.calculate_child_rows()
        self.calculate_totals()
        self.handle_new_location()

    def validate_purchase_link(self):
        if self.purchase_id:
            # Check if this purchase is already linked to another Invoice
            existing_invoice = frappe.db.get_value("Purchase", self.purchase_id, "reference_invoice")
            if existing_invoice and existing_invoice != self.name:
                # Fetch Names for better display
                purchase_vendor = frappe.db.get_value("Purchase", self.purchase_id, "vendor_name")
                invoice_name = frappe.db.get_value("Invoice", existing_invoice, "customer_name")

                frappe.throw(
                    _("Purchase {0} ({1}) is already linked to Invoice {2} ({3}). Please select a different Purchase.").format(
                        frappe.bold(self.purchase_id),
                        frappe.bold(purchase_vendor or "Unknown"),
                        frappe.bold(existing_invoice),
                        frappe.bold(invoice_name or "Unknown")
                    )
                )

    def ensure_no_linked_collections(self):
        """Prevent editing or deleting if Invoice Collection entries exist"""
        collections = frappe.db.count("Invoice Collection", {"invoice": self.name})
        if collections > 0:
            frappe.throw(
                _("Cannot modify Invoice {0} because {1} Payment Collection(s) exist. "
                "Please delete the Payment Collections before modifying this Invoice.").format(
                    frappe.bold(self.name), 
                    frappe.bold(collections)
                )
            )

    def on_trash(self):
        self.ensure_no_linked_collections()
        
        # Clear Purchase reference when Invoice is deleted
        if self.purchase_id:
            frappe.db.set_value("Purchase", self.purchase_id, "reference_invoice", None)
            
        # Update Customer 'OLD' status when deleting invoice
        if self.customer_id:
            # Count remaining invoices (excluding this one)
            remaining_count = frappe.db.count("Invoice", filters={
                "customer_id": self.customer_id,
                "name": ["!=", self.name]
            })
            if remaining_count <= 1:
                frappe.db.set_value("Customer", self.customer_id, "is_old_customer", 0)
    
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
        seq = make_autoname(".###", doc=self)  # IB-I/.001, .002, etc.

        # Assign to ref_no (which will also become name)
        self.ref_no = f"IB-I/{fy}/{seq.split('.')[-1]}"
        
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

        self.grand_total = total + (flt(self.roundoff) if hasattr(self, 'roundoff') else 0)

        # Sync Balance Amount
        self.balance_amount = flt(self.grand_total) - flt(self.received_amount)

    def handle_new_location(self):
        if getattr(self, "is_new_location", 0):
            if self.customer_id and self.location:
                # Add location to Customer (using existing whitelisted method internally)
                add_customer_location(
                    self.customer_id, 
                    self.location, 
                    self.get("location_address")
                )
                # Clear flag so it doesn't try to add again
                self.is_new_location = 0

    def on_update(self):
        """Update Purchase reference when purchase_id changes"""
        if self.has_value_changed("purchase_id"):
            # Clear old purchase reference
            old_purchase_id = self.get_doc_before_save().purchase_id if self.get_doc_before_save() else None
            if old_purchase_id:
                frappe.db.set_value("Purchase", old_purchase_id, "reference_invoice", None)
            
            # Set new purchase reference
            if self.purchase_id:
                frappe.db.set_value("Purchase", self.purchase_id, "reference_invoice", self.name)
    
    def after_insert(self):
        # Update Purchase with Invoice reference
        if self.purchase_id:
            frappe.db.set_value("Purchase", self.purchase_id, "reference_invoice", self.name)
        
        if not self.customer_id:
            return

        # Count confirmed invoices for this customer
        invoice_count = frappe.db.count("Invoice", filters={"customer_id": self.customer_id})

        # Update status (1 if more than one invoice, 0 otherwise)
        is_old = 1 if invoice_count > 1 else 0
        frappe.db.set_value("Customer", self.customer_id, "is_old_customer", is_old)



@frappe.whitelist()
def add_customer_location(customer, location_name, address=None):
    if not customer or not location_name:
        frappe.throw(_("Customer and Location Name are required."))
        
    # Check if location already exists to avoid duplicates
    exists = frappe.db.exists("Customer Location", {
        "parent": customer,
        "location_name": location_name
    })
            
    if not exists:
        # Calculate next idx for the child table
        next_idx = frappe.db.sql("""
            SELECT IFNULL(MAX(idx), 0) + 1 
            FROM `tabCustomer Location` 
            WHERE parent = %s AND parentfield = 'location'
        """, (customer,))[0][0]

        # Insert child record directly to bypass parent document validation
        new_row = frappe.get_doc({
            "doctype": "Customer Location",
            "parent": customer,
            "parenttype": "Customer",
            "parentfield": "location",
            "idx": next_idx,
            "customer": customer,
            "location_name": location_name,
            "address": address
        })
        new_row.insert(ignore_permissions=True)
        return True
    
    return False


@frappe.whitelist()
def refresh_customer_status(customer):
    if not customer:
        return False
    
    # Count confirmed invoices
    invoice_count = frappe.db.count("Invoice", filters={"customer_id": customer})
    
    # Update status (1 if more than one invoice, 0 otherwise)
    is_old = 1 if invoice_count > 1 else 0
    frappe.db.set_value("Customer", customer, "is_old_customer", is_old)
    return True


@frappe.whitelist()
def get_customer_locations(customer):
    if not customer:
        return []
        
    # Handle list of customers (for MultiSelectList)
    if isinstance(customer, str) and customer.startswith("[") and customer.endswith("]"):
        import json
        try:
            customer = json.loads(customer)
        except:
            pass

    filters = {"parenttype": "Customer", "parentfield": "location"}
    if isinstance(customer, list):
        filters["parent"] = ["in", customer]
    else:
        filters["parent"] = customer

    return frappe.get_all("Customer Location", 
        filters=filters, 
        fields=["location_name"], 
        distinct=True
    )
