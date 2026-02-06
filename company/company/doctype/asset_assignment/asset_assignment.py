# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document

class AssetAssignment(Document):
    def validate(self):
        self.check_asset_availability()

    def check_asset_availability(self):
        """
        Check if the Asset is already assigned and not yet returned
        """
        if self.asset:
            existing = frappe.db.exists(
                "Asset Assignment",
                {
                    "asset": self.asset,
                    "returned_on": None,
                    "name": ["!=", self.name]  # exclude current doc
                }
            )
            if existing:
                frappe.throw(f"Asset '{self.asset}' is already assigned and not returned yet!")