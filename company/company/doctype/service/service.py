# Copyright (c) 2025, deepak and contributors
# For license information, please see license.txt

import frappe
from frappe.model.rename_doc import rename_doc
from frappe.model.document import Document


class Service(Document):
    def before_save(self):
        # Server-side fail-safe to ensure title is always synced
        if self.service_name:
            self.service_name_title = self.service_name


@frappe.whitelist()
def rename_service(docname, new_title):
    if not docname or not new_title:
        return

    # Use the title exactly as requested (matches autoname behavior)
    new_name = new_title

    # Prevent duplicate names
    if frappe.db.exists("Service", new_name):
        if new_name == docname:
            return docname
        return docname

    try:
        # 🔁 Rename document
        rename_doc(
            "Service",
            docname,
            new_name,
            force=True,
            merge=False
        )
        return new_name
    except Exception:
        return docname
