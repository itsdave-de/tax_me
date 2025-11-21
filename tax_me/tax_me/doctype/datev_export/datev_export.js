// Copyright (c) 2025, itsdave GmbH and contributors
// For license information, please see license.txt

// frappe.ui.form.on("DATEV Export", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("DATEV Export", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__("CSV erzeugen"), function () {
                frappe.call({
                    method: "tax_me.tax_me.doctype.datev_export.datev_export.run_datev_export",
                    args: {
                        docname: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __("Erzeuge DATEV-Buchungsstapel..."),
                    callback(r) {
                        frm.reload_doc();
                        if (r.message) {
                            if (r.message.file_url) {
                                frappe.msgprint(
                                    __("Export fertig. Datei: {0}", [r.message.file_url])
                                );
                            }
                            if (r.message.log) {
                                console.log("DATEV Export Log:", r.message.log);
                            }
                        }
                    }
                });
            });
        }
    }
});
