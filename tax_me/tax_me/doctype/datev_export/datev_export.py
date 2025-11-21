# Copyright (c) 2025, itsdave GmbH and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document

from tax_me.utils.datev_export import generate_datev_buchungsstapel


class DATEVExport(Document):
    def generate_csv(self):
        """Serverseitiger Export-Aufruf vom Button aus."""
        self.status = "In Progress"
        self.log = ""
        self.save(ignore_permissions=True)

        try:
            file_url = generate_datev_buchungsstapel(
                company=self.company,
                from_date=self.from_date,
                to_date=self.to_date,
                export_type=self.export_type or "Purchase Invoices",
                export_name=self.name,
            )
            self.export_file = file_url
            self.status = "Completed"
            self.log = "Export erfolgreich erstellt."
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "DATEV Export Fehler")
            self.status = "Error"
            self.log = f"Fehler beim Export: {str(e)}"

        self.save(ignore_permissions=True)
    


@frappe.whitelist()
def run_datev_export(docname: str):
    """Whitelisted-Methode für den Button im Client Script."""
    doc = frappe.get_doc("DATEV Export", docname)
    doc.generate_csv()
    return {
        "status": doc.status,
        "file_url": doc.export_file,
        "log": doc.log,
    }
