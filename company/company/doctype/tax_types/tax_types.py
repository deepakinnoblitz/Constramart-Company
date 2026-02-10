import frappe
from frappe.model.document import Document


class TaxTypes(Document):
	def before_insert(self):
		if self.name == "Exempted" or self.tax_type == "Exempted":
			frappe.throw("Creation of Exempted tax is not allowed")
