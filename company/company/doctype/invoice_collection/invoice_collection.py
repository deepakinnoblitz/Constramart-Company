# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InvoiceCollection(Document):
	
	def validate(self):
		"""Only allow editing if it is the latest collection for the invoice"""
		if not self.is_new():
			if self.is_advance:
				old_doc = self.get_doc_before_save()
				if old_doc and (
					old_doc.amount_collected != self.amount_collected or
					old_doc.invoice != self.invoice or
					old_doc.customer_id != self.customer_id or
					old_doc.mode_of_payment != self.mode_of_payment or
					old_doc.is_advance != self.is_advance
				):
					frappe.throw(_("Advance Collections cannot be edited directly in Sales Collection."))
			self.ensure_latest_collection()

		self.calculate_collection_breakdown()

	def calculate_collection_breakdown(self):
		if not self.invoice:
			return

		invoice = frappe.get_doc("Invoice", self.invoice)
		customer_id = self.customer_id or invoice.customer_id
		if not customer_id:
			return

		self.customer_id = customer_id

		# Fetch Customer Available Opening Balance from live Customer.opening_balance
		cust_current_ob = float(frappe.db.get_value("Customer", customer_id, "opening_balance") or 0.0)
		if self.is_new():
			self.available_opening_balance = max(0.0, cust_current_ob)
		else:
			old_doc = self.get_doc_before_save()
			old_ded = float(old_doc.opening_balance_deduction or 0.0) if old_doc else 0.0
			old_exc = float(old_doc.excess_amount or 0.0) if old_doc else 0.0
			self.available_opening_balance = max(0.0, cust_current_ob + old_ded - old_exc)

		# Fetch Available Advance (Standalone unlinked advances only)
		adv_collections = frappe.db.sql("""
			SELECT COALESCE(SUM(amount_collected), 0)
			FROM `tabInvoice Collection`
			WHERE customer_id = %s AND is_advance = 1 AND (invoice IS NULL OR invoice = '') AND name != %s
		""", (customer_id, self.name or ""))[0][0] or 0

		adv_used = frappe.db.sql("""
			SELECT COALESCE(SUM(advance_adjusted), 0)
			FROM `tabInvoice Collection`
			WHERE customer_id = %s AND (is_advance = 0 OR is_advance IS NULL) AND name != %s
		""", (customer_id, self.name or ""))[0][0] or 0

		avail_adv = max(0.0, float(adv_collections) - float(adv_used))
		self.available_advance = avail_adv

		# Pending before this collection (Amount to Pay)
		prev_applied = frappe.db.sql("""
			SELECT COALESCE(SUM(CASE WHEN is_advance = 1 THEN amount_collected ELSE (amount_collected + advance_adjusted - excess_amount) END), 0)
			FROM `tabInvoice Collection`
			WHERE invoice = %s AND name != %s
		""", (self.invoice, self.name or ""))[0][0] or 0

		pending_before = float(invoice.grand_total) - float(prev_applied)
		pending_before = max(0.0, pending_before)

		# Store amount_to_pay in DB
		self.amount_to_pay = pending_before

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

			self.amount_collected_using_opening_balance = ob_ded
			rem_after_ob = rem_after_adv - ob_ded

			# 3. Excess Calculation & Amount Pending
			collected_normally = float(getattr(self, "amount_collected_normally", 0.0) or 0.0)
			self.amount_collected = ob_ded + collected_normally

			if collected_normally > rem_after_ob:
				self.excess_amount = collected_normally - rem_after_ob
				self.amount_pending = 0.0
			else:
				self.excess_amount = 0.0
				self.amount_pending = rem_after_ob - collected_normally
		else:
			self.opening_balance_deduction = 0.0
			self.amount_collected_using_opening_balance = 0.0
			self.excess_amount = 0.0
			collected = float(getattr(self, "amount_collected_normally", 0.0) or getattr(self, "amount_collected", 0.0) or 0.0)
			self.advance_adjusted = collected
			self.amount_collected = collected
			self.amount_pending = max(0.0, pending_before - collected)

	def on_trash(self):
		"""Only allow deleting if it is the latest collection for the invoice"""
		self.ensure_latest_collection()

	def ensure_latest_collection(self):
		"""Check if there are any newer collections for the same invoice"""
		if self.is_new() or not self.invoice:
			return

		# Find the latest collection's name
		latest_collection = frappe.db.get_value("Invoice Collection", 
			filters={"invoice": self.invoice},
			fieldname="name",
			order_by="creation desc"
		)

		if latest_collection and latest_collection != self.name:
			frappe.throw(_("Only the last collection ({0}) for Invoice {1} can be modified or deleted.").format(latest_collection, self.invoice))

	def after_insert(self):
		"""Update Invoice amounts after creating a new collection"""
		self.update_invoice_amounts()
	
	def on_update(self):
		"""Update Invoice amounts after modifying a collection"""
		self.update_invoice_amounts()
	
	def after_delete(self):
		"""Update Invoice amounts after deleting a collection"""
		if self.invoice and self.is_advance:
			frappe.db.set_value("Invoice", self.invoice, {
				"advance_amount_paid": 0.0,
				"advance_payment_type": None
			})
		self.update_invoice_amounts()
	
	def update_invoice_amounts(self):
		"""Recalculate and update received_amount and balance_amount in the Invoice & Customer Opening Balance"""
		if not self.invoice:
			return
		
		invoice = frappe.get_doc("Invoice", self.invoice)
		customer_id = self.customer_id or invoice.customer_id
		
		# Total effective collection applied to Invoice
		total_applied = frappe.utils.flt(frappe.db.sql("""
			SELECT SUM(CASE WHEN is_advance = 1 THEN amount_collected ELSE (amount_collected + advance_adjusted - excess_amount) END) as total
			FROM `tabInvoice Collection`
			WHERE invoice = %s
		""", (self.invoice,))[0][0] or 0)
		
		grand_total = frappe.utils.flt(invoice.grand_total)
		balance = max(0.0, grand_total - total_applied)
		
		frappe.db.set_value("Invoice", self.invoice, {
			"received_amount": total_applied,
			"balance_amount": balance
		})

		frappe.publish_realtime("doc_update", {"doctype": "Invoice", "name": self.invoice}, after_commit=True)
		
		if customer_id:
			from company.company.api import sync_customer_opening_balance
			sync_customer_opening_balance(customer_id, self)

		frappe.db.commit()

