# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class InvoiceCollection(Document):
	
	def validate(self):
		"""Only allow editing if it is the latest collection for the invoice"""
		if not self.is_new():
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

		# Fetch Customer Opening Balance
		cust_ob = frappe.db.get_value("Customer", customer_id, "opening_balance") or 0.0
		self.available_opening_balance = float(cust_ob)

		# Fetch Available Advance
		adv_collections = frappe.db.sql("""
			SELECT COALESCE(SUM(amount_collected), 0)
			FROM `tabInvoice Collection`
			WHERE customer_id = %s AND is_advance = 1 AND name != %s
		""", (customer_id, self.name or ""))[0][0] or 0

		adv_used = frappe.db.sql("""
			SELECT COALESCE(SUM(advance_adjusted), 0)
			FROM `tabInvoice Collection`
			WHERE customer_id = %s AND (is_advance = 0 OR is_advance IS NULL) AND name != %s
		""", (customer_id, self.name or ""))[0][0] or 0

		avail_adv = max(0.0, float(adv_collections) - float(adv_used))
		self.available_advance = avail_adv

		if not self.is_advance:
			# Pending before this collection
			prev_applied = frappe.db.sql("""
				SELECT COALESCE(SUM(amount_collected + advance_adjusted + opening_balance_deducted - excess_amount), 0)
				FROM `tabInvoice Collection`
				WHERE invoice = %s AND name != %s
			""", (self.invoice, self.name or ""))[0][0] or 0

			pending_before = float(invoice.grand_total) - float(prev_applied)
			pending_before = max(0.0, pending_before)

			# 1. Advance Adjustment
			self.advance_adjusted = min(avail_adv, pending_before)
			rem_after_adv = pending_before - self.advance_adjusted

			# 2. Opening Balance Deduction
			if self.use_opening_balance:
				self.opening_balance_deducted = min(self.available_opening_balance, rem_after_adv)
			else:
				self.opening_balance_deducted = 0.0

			rem_after_ob = rem_after_adv - self.opening_balance_deducted

			# 3. Excess Calculation
			collected = float(self.amount_collected or 0)
			if collected > rem_after_ob:
				self.excess_amount = collected - rem_after_ob
			else:
				self.excess_amount = 0.0
		else:
			self.advance_adjusted = 0.0
			self.opening_balance_deducted = 0.0
			self.excess_amount = 0.0

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
		self.update_invoice_amounts()
	
	def update_invoice_amounts(self):
		"""Recalculate and update received_amount and balance_amount in the Invoice & Customer Opening Balance"""
		if not self.invoice:
			return
		
		invoice = frappe.get_doc("Invoice", self.invoice)
		customer_id = self.customer_id or invoice.customer_id
		
		# Total effective collection applied to Invoice
		total_applied = frappe.utils.flt(frappe.db.sql("""
			SELECT SUM(amount_collected + advance_adjusted + opening_balance_deducted - excess_amount) as total
			FROM `tabInvoice Collection`
			WHERE invoice = %s
		""", (self.invoice,))[0][0] or 0)
		
		grand_total = frappe.utils.flt(invoice.grand_total)
		balance = max(0.0, grand_total - total_applied)
		
		frappe.db.set_value("Invoice", self.invoice, {
			"received_amount": total_applied,
			"balance_amount": balance
		})
		
		if customer_id:
			from company.company.api import sync_customer_opening_balance
			sync_customer_opening_balance(customer_id, self)

		frappe.db.commit()

