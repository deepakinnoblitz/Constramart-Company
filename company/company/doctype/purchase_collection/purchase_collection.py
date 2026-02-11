# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PurchaseCollection(Document):
	
	def validate(self):
		"""Only allow editing if it is the latest collection for the purchase order"""
		if not self.is_new():
			self.ensure_latest_collection()

	def on_trash(self):
		"""Only allow deleting if it is the latest collection for the purchase order"""
		self.ensure_latest_collection()

	def ensure_latest_collection(self):
		"""Check if there are any newer collections for the same purchase order"""
		if self.is_new() or not self.purchase:
			return

		# Find the latest collection's name
		latest_collection = frappe.db.get_value("Purchase Collection", 
			filters={"purchase": self.purchase},
			fieldname="name",
			order_by="creation desc"
		)

		if latest_collection and latest_collection != self.name:
			frappe.throw(_("Only the last collection ({0}) for Purchase Order {1} can be modified or deleted.").format(latest_collection, self.purchase))
	def after_insert(self):
		"""Update Purchase amounts after creating a new collection"""
		self.update_purchase_amounts()
	
	def on_update(self):
		"""Update Purchase amounts after modifying a collection"""
		self.update_purchase_amounts()
	
	def after_delete(self):
		"""Update Purchase amounts after deleting a collection"""
		self.update_purchase_amounts()
	
	def update_purchase_amounts(self):
		"""Recalculate and update paid_amount, balance_amount, and purchase_status in the Purchase"""
		if not self.purchase:
			return
		
		# Get the Purchase document
		purchase = frappe.get_doc("Purchase", self.purchase)
		
		# Calculate total paid amount from all Purchase Collection records
		total_paid = frappe.utils.flt(frappe.db.sql("""
			SELECT SUM(amount_paid) as total
			FROM `tabPurchase Collection`
			WHERE purchase = %s
		""", (self.purchase,))[0][0] or 0)
		
		grand_total = frappe.utils.flt(purchase.grand_total)
		balance = grand_total - total_paid
		
		# Determine purchase status
		if total_paid == 0:
			status = "Pending"
		elif balance > 0:
			status = "Partially Paid"
		else:
			status = "Fully Paid"
		
		# Update Purchase fields atomically
		frappe.db.set_value("Purchase", self.purchase, {
			"paid_amount": total_paid,
			"balance_amount": balance,
			"purchase_status": status
		})
		
		frappe.db.commit()

