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

		self.calculate_collection_breakdown()

	def calculate_collection_breakdown(self):
		if not self.purchase:
			return

		purchase = frappe.get_doc("Purchase", self.purchase)
		vendor_id = self.vendor_id or purchase.vendor_id
		if not vendor_id:
			return

		self.vendor_id = vendor_id

		# Fetch Vendor Available Opening Balance
		cust_data = frappe.db.get_value("Customer", vendor_id, ["opening_balance", "initial_opening_balance"], as_dict=True) or {}
		init_ob = float(cust_data.get("initial_opening_balance") or cust_data.get("opening_balance") or 0.0)

		# Fetch net OB changes from Purchase Collection
		other_ob_deducted = frappe.db.sql("""
			SELECT COALESCE(SUM(opening_balance_deduction), 0)
			FROM `tabPurchase Collection`
			WHERE vendor_id = %s AND name != %s
		""", (vendor_id, self.name or ""))[0][0] or 0

		other_excess = frappe.db.sql("""
			SELECT COALESCE(SUM(excess_amount), 0)
			FROM `tabPurchase Collection`
			WHERE vendor_id = %s AND name != %s
		""", (vendor_id, self.name or ""))[0][0] or 0

		cust_current_ob = float(cust_data.get("opening_balance") or 0.0)
		if self.is_new():
			self.available_opening_balance = max(0.0, cust_current_ob)
		else:
			old_doc = self.get_doc_before_save()
			old_ded = float(old_doc.opening_balance_deduction or 0.0) if old_doc else 0.0
			old_exc = float(old_doc.excess_amount or 0.0) if old_doc else 0.0
			self.available_opening_balance = max(0.0, cust_current_ob + old_ded - old_exc)

		# Advance collections
		adv_collections = frappe.db.sql("""
			SELECT COALESCE(SUM(amount_paid), 0)
			FROM `tabPurchase Collection`
			WHERE vendor_id = %s AND is_advance = 1 AND (purchase IS NULL OR purchase = '')
		""", vendor_id)[0][0] or 0
		
		adv_used = frappe.db.sql("""
			SELECT COALESCE(SUM(advance_adjusted), 0)
			FROM `tabPurchase Collection`
			WHERE vendor_id = %s AND (is_advance = 0 OR is_advance IS NULL) AND name != %s
		""", (vendor_id, self.name or ""))[0][0] or 0
		
		avail_adv = max(0.0, float(adv_collections) - float(adv_used))
		self.available_advance = avail_adv

		# Pending before this payment (Amount to Pay)
		if self.is_new() or not self.amount_to_pay:
			prev_applied = frappe.db.sql("""
				SELECT COALESCE(SUM(CASE WHEN is_advance = 1 THEN amount_paid ELSE (amount_paid + advance_adjusted - excess_amount) END), 0)
				FROM `tabPurchase Collection`
				WHERE purchase = %s AND name != %s AND creation < %s
			""", (self.purchase, self.name or "", self.creation or "9999-12-31 23:59:59"))[0][0] or 0

			pending_before = max(0.0, float(purchase.grand_total) - float(prev_applied))
			self.amount_to_pay = pending_before
		else:
			pending_before = float(self.amount_to_pay or 0.0)

		if not self.is_advance:
			# 1. Advance Adjustment
			self.advance_adjusted = min(avail_adv, pending_before)
			rem_after_adv = pending_before - self.advance_adjusted

			# 2. Opening Balance Deduction
			if self.use_opening_balance:
				current_ob = float(getattr(self, "opening_balance_deduction", 0.0) or 0.0)
				if current_ob == 0 and self.available_opening_balance > 0 and rem_after_adv > 0:
					current_ob = min(self.available_opening_balance, rem_after_adv)
				ob_ded = min(self.available_opening_balance, min(rem_after_adv, current_ob))
				self.opening_balance_deduction = ob_ded
			else:
				ob_ded = 0.0
				self.opening_balance_deduction = 0.0

			self.amount_paid_using_opening_balance = ob_ded
			rem_after_ob = rem_after_adv - ob_ded

			# 3. Excess Calculation & Amount Pending
			paid_normally = float(getattr(self, "amount_paid_normally", 0.0) or 0.0)
			self.amount_paid = ob_ded + paid_normally

			if paid_normally > rem_after_ob:
				self.excess_amount = paid_normally - rem_after_ob
				self.amount_pending = 0.0
			else:
				self.excess_amount = 0.0
				self.amount_pending = rem_after_ob - paid_normally
		else:
			self.opening_balance_deduction = 0.0
			self.amount_paid_using_opening_balance = 0.0
			self.excess_amount = 0.0
			paid = float(getattr(self, "amount_paid_normally", 0.0) or getattr(self, "amount_paid", 0.0) or 0.0)
			self.advance_adjusted = paid
			self.amount_paid = paid
			self.amount_pending = max(0.0, pending_before - paid)

	def validate(self):
		if not self.is_new() and self.is_advance:
			frappe.throw(_("Advance Payment collections cannot be edited directly. Please edit the Purchase Bill instead."))
		self.calculate_collection_breakdown()

	def on_trash(self):
		"""Only allow deleting if it is the latest collection for the purchase order"""
		self.ensure_latest_collection()

	def ensure_latest_collection(self):
		"""Check if there are any newer collections for the same vendor"""
		if self.is_new() or not self.vendor_id:
			return

		latest_collection = frappe.db.get_value("Purchase Collection", 
			filters={"vendor_id": self.vendor_id},
			fieldname="name",
			order_by="creation desc"
		)

		if latest_collection and latest_collection != self.name:
			frappe.throw(_("Only the overall last collection ({0}) for Vendor {1} can be modified or deleted.").format(latest_collection, self.vendor_id))

	def after_insert(self):
		"""Update Purchase amounts after creating a new collection"""
		self.update_purchase_amounts()
	
	def on_update(self):
		"""Update Purchase amounts after modifying a collection"""
		self.update_purchase_amounts()
	
	def after_delete(self):
		"""Update Purchase amounts after deleting a collection"""
		if self.purchase and self.is_advance:
			frappe.db.set_value("Purchase", self.purchase, {
				"advance_amount_paid": 0.0,
				"advance_payment_type": None
			})
		self.update_purchase_amounts()
	
	def update_purchase_amounts(self):
		"""Recalculate and update paid_amount, balance_amount, and purchase_status in the Purchase"""
		if not self.purchase:
			return
		
		purchase = frappe.get_doc("Purchase", self.purchase)
		vendor_id = self.vendor_id or purchase.vendor_id
		
		# Total effective payment applied to Purchase
		total_applied = frappe.utils.flt(frappe.db.sql("""
			SELECT SUM(CASE WHEN is_advance = 1 THEN amount_paid ELSE (amount_paid + advance_adjusted - excess_amount) END) as total
			FROM `tabPurchase Collection`
			WHERE purchase = %s
		""", (self.purchase,))[0][0] or 0)
		
		grand_total = frappe.utils.flt(purchase.grand_total)
		balance = max(0.0, grand_total - total_applied)
		
		# Determine purchase status
		if total_applied == 0:
			status = "Pending"
		elif balance > 0:
			status = "Partially Paid"
		else:
			status = "Fully Paid"
		
		frappe.db.set_value("Purchase", self.purchase, {
			"paid_amount": total_applied,
			"balance_amount": balance,
			"purchase_status": status
		})

		frappe.publish_realtime("doc_update", {"doctype": "Purchase", "name": self.purchase}, after_commit=True)
		
		if vendor_id:
			from company.company.api import sync_customer_opening_balance
			sync_customer_opening_balance(vendor_id)
