import frappe
from frappe import _
from frappe.model.document import Document


class Leads(Document):
	def validate(self):
		self.restrict_followup_editing()

	def restrict_followup_editing(self):
		if frappe.session.user == "Administrator":
			return

		if not self.is_new():
			# Get the version currently in the database
			old_doc = self.get_doc_before_save()
			if not old_doc:
				return

			# Build a map of old followup rows for easy comparison
			old_followups = {d.name: d for d in old_doc.get("followup") or []}
			new_followup_names = [d.name for d in self.get("followup") or [] if d.name]

			# 1. Check for unauthorized modifications
			for d in self.get("followup") or []:
				if d.name in old_followups:
					old_row = old_followups[d.name]
					
					# Only owner can edit
					if old_row.owner_name and old_row.owner_name != frappe.session.user:
						# check if any restricted fields changed
						for field in ["followup_date", "lead_status", "remark"]:
							val1 = d.get(field)
							val2 = old_row.get(field)
							
							# Normalization
							if field == "followup_date":
								if val1 and val2:
									if frappe.utils.get_datetime(val1) == frappe.utils.get_datetime(val2):
										continue
							elif field == "remark":
								if (val1 or "").strip() == (val2 or "").strip():
									continue
							
							if val1 != val2:
								frappe.throw(
									_("Access Denied: You cannot modify Followup Row #{0} created by {1}. Field '{2}' changed from '{3}' to '{4}'").format(
										d.idx, old_row.owner_name, field, val2, val1
									)
								)
				else:
					# New row being added - enforce owner_name
					d.owner_name = frappe.session.user

			# 2. Check for unauthorized deletions
			for row_name, old_row in old_followups.items():
				if row_name not in new_followup_names:
					if old_row.owner_name and old_row.owner_name != frappe.session.user:
						frappe.throw(
							_("Access Denied: You cannot delete Followup Row #{0} created by {1}").format(
								old_row.idx, old_row.owner_name
							)
						)
