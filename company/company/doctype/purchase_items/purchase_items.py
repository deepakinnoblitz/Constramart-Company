# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PurchaseItems(Document):

    def validate(self):
        self.calculate_tax()

    def calculate_tax(self):
        """Calculate tax_amount and sub_total"""

        qty = self.quantity or 0
        price = self.price or 0
        discount = self.discount or 0
        discount_type = self.discount_type or "Flat"
        tax_percent = float(self.tax_percent or 0)

        # Base amount
        base = qty * price

        # Discount
        if discount_type == "Percentage":
            disc = base * (discount / 100)
        else:  # Flat
            disc = discount

        taxable = base - disc

        # Tax
        tax_amount = taxable * (tax_percent / 100)
        self.tax_amount = tax_amount

        # Subtotal
        self.sub_total = taxable + tax_amount
