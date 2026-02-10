import frappe
from frappe import _
from frappe.model.document import Document

class Item(Document):
    def validate(self):

        # 🔒 Block duplicate Item Name
        if self.item_name and frappe.db.exists(
            "Item",
            {"item_name": self.item_name, "name": ["!=", self.name]}
        ):
            frappe.throw(_("Item Name already exists"))

        # 🔒 Block duplicate Item Code / HSN
        if self.item_code and frappe.db.exists(
            "Item",
            {"item_code": self.item_code, "name": ["!=", self.name]}
        ):
            frappe.throw(_("Item Code / HSN already exists"))
