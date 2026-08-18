import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import getdate, flt

class Invoice(Document):
    
    def validate(self):
        # Auto-fill purchase_id from reference_purchase if missing (Back-end Handshake)
        if self.reference_purchase and not self.purchase_id:
            self.purchase_id = self.reference_purchase

        if not self.is_new():
            self.ensure_no_linked_collections()
        
        if not self.get("table_qecz"):
            frappe.throw(_("At least one item is required in the Items table."))

        for item in self.table_qecz:
            if flt(item.price) <= 0:
                frappe.throw(_("Price cannot be 0 or less for item {0} in row {1}").format(
                    frappe.bold(item.service or "Unknown"), 
                    frappe.bold(item.idx)
                ))

        self.validate_purchase_link()
        self.calculate_child_rows()
        self.calculate_totals()
        self.handle_new_location()

    def validate_purchase_link(self):
        if self.purchase_id:
            # Check if this purchase is already linked to another Invoice
            # We check both 'reference_invoice' (updated on save) AND 'invoice_id' (if it was linked from Purchase form)
            purchase_data = frappe.db.get_value("Purchase", self.purchase_id, ["reference_invoice", "invoice_id"], as_dict=True)

            if not purchase_data:
                return

            existing_invoice = purchase_data.reference_invoice or purchase_data.invoice_id

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
            
        # Update Customer status when deleting invoice
        if self.customer_id:
            remaining_count = frappe.db.count("Invoice", filters={
                "customer_id": self.customer_id,
                "name": ["!=", self.name]
            })
            if remaining_count <= 1:
                frappe.db.set_value("Customer", self.customer_id, "customer_status", "New Customer")
                customer_doc = frappe.get_doc("Customer", self.customer_id)
                customer_doc.notify_update()
                frappe.publish_realtime("customer_status_updated", {"customer": self.customer_id, "status": "New Customer"}, after_commit=True)
                frappe.publish_realtime("doc_update", {"doctype": "Customer", "name": self.customer_id}, after_commit=True)
    
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

        # Sync Balance Amount considering direct advance_amount_paid
        adv_paid = flt(self.advance_amount_paid)
        self.balance_amount = max(0.0, flt(self.grand_total) - flt(self.received_amount) - adv_paid)

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
        """Ensure Purchase reference is synchronized with this Invoice"""
        if self.purchase_id:
            # Set this Invoice as the reference on the linked Purchase
            frappe.db.set_value("Purchase", self.purchase_id, "reference_invoice", self.name)
        else:
            # If purchase_id was cleared, remove the reference from the old purchase
            old_doc = self.get_doc_before_save()
            if old_doc and old_doc.purchase_id:
                frappe.db.set_value("Purchase", old_doc.purchase_id, "reference_invoice", None)
    
    def after_insert(self):
        # Update Purchase with Invoice reference
        if self.purchase_id:
            frappe.db.set_value("Purchase", self.purchase_id, "reference_invoice", self.name)
            
        # Create advance collection if advance_amount_paid > 0
        if flt(self.advance_amount_paid) > 0 and getattr(self, "advance_payment_type", None):
            adv_exists = frappe.db.exists("Invoice Collection", {
                "invoice": self.name,
                "is_advance": 1
            })
            if not adv_exists:
                adv_coll = frappe.get_doc({
                    "doctype": "Invoice Collection",
                    "invoice": self.name,
                    "customer_id": self.customer_id,
                    "collection_date": self.invoice_date or frappe.utils.today(),
                    "amount_collected": self.advance_amount_paid,
                    "mode_of_payment": self.advance_payment_type,
                    "is_advance": 1,
                    "business_person": self.business_person_name,
                    "remarks": f"Advance payment recorded on Sales Bill {self.name}"
                })
                adv_coll.insert(ignore_permissions=True)

        # Update Customer status on 2nd invoice creation
        if self.customer_id:
            invoice_count = frappe.db.count("Invoice", filters={"customer_id": self.customer_id})
            if invoice_count >= 2:
                frappe.db.set_value("Customer", self.customer_id, "customer_status", "Old Customer")
                customer_doc = frappe.get_doc("Customer", self.customer_id)
                customer_doc.notify_update()
                frappe.publish_realtime("customer_status_updated", {"customer": self.customer_id, "status": "Old Customer"}, after_commit=True)
                frappe.publish_realtime("doc_update", {"doctype": "Customer", "name": self.customer_id}, after_commit=True)



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
