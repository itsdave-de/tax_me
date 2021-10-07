// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('Tax Me Einstellungen', {
	refresh: function(frm) {
		cur_frm.add_custom_button(__("Create Missing Debitor Accounts"), function() {
			frappe.call({
				"method": "tax_me.tools.create_missing_debitor_accounts",
				callback: (response) => {
					console.log(response.message);
				} 
			})
		});

	}
});
