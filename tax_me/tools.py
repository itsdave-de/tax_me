import frappe
from frappe.desk.form.linked_with import get_linked_docs, get_linked_doctypes

@frappe.whitelist()
def create_missing_debitor_accounts():

    settings = frappe.get_single("Tax Me Einstellungen")
    customers = get_customers_without_debitor_acc(settings)
    print(customers)
    for c in customers:
        if c["acc_no"]:
            if not try_assign_existent_account(c):
                create_and_assign_debitor_account(settings, c["name"])
                frappe.db.commit()
        else:
            create_and_assign_debitor_account(settings, c["name"])
            frappe.db.commit()


def get_next_debitor_acc_no(settings):
    filters = {
        "parent_account": settings.parent_account
    }
    fields = ["name", "account_number"]
    acc_list = frappe.get_all("Account", filters=filters, fields=fields)
    if not acc_list:
        return settings.no_series_start
    max_acc_no = settings.no_series_start
    for acc in acc_list:
        if acc["account_number"].isdigit():
            acc_int = int(acc["account_number"])
            if acc_int >= settings.no_series_start and acc_int <= settings.no_series_end:
                if acc_int > max_acc_no:
                    max_acc_no = acc_int
            else:
                message = "Die Nummerierung der Konten ist nicht sauber. " + acc["account_number"] + " | " + acc["name"]
                message += " Nummer außerhalb des Nummernkreises."
                frappe.throw(message)
        else:
            message = "Die Nummerierung der Konten ist nicht sauber. " + acc["account_number"] + " | " + acc["name"]
            message += " ist keine gültige Zahl."
            frappe.throw(message)
    next_debitor_acc_no = max_acc_no + 1
    if next_debitor_acc_no >= settings.no_series_end:
        return False
    else:
        return next_debitor_acc_no

def create_and_assign_debitor_account(settings, customer):
    account_number =  get_next_debitor_acc_no(settings)
    global_settings_doc = frappe.get_single("Global Defaults")
    cust_doc = frappe.get_doc("Customer", customer)

    acc_doc = frappe.get_doc({
        "doctype": "Account",
        "parent_account": settings.parent_account,
        "parent": settings.parent_account,
        "account_number": account_number,
        "account_name": cust_doc.customer_name,
        "account_type": "Receivable",
        "company": global_settings_doc.default_company,
        "root_type": "Asset",
        "report_type": "Balance Sheet",
        "account_currency": global_settings_doc.default_currency
    })
    doc_inserted = acc_doc.insert()

    found_pa = False
    if cust_doc.accounts:
        for pa in cust_doc.accounts:
            if pa.company == global_settings_doc.default_company:
                found_pa = True
                pa.account = doc_inserted.name
                pa.debtor_creditor_number = account_number

    if not found_pa:
        pa_doc = frappe.get_doc({
            "doctype": "Party Account",
            "account": doc_inserted.name,
            "debtor_creditor_number": account_number,
            "company": global_settings_doc.default_company
        })
        cust_doc.append("accounts", pa_doc)
    cust_doc.save()

def get_customers_without_debitor_acc(settings):
    global_settings_doc = frappe.get_single("Global Defaults")
    filters = {}
    if settings.customer_like_filter:
        filters["name"] = ["like", settings.customer_like_filter]
    customer_list = frappe.get_all("Customer", filters=filters)
    
    count_acc_fehlt = 0
    count_debnr_fehlt = 0
    cust_without_account = []
    for customer in customer_list:
        cust_doc = frappe.get_doc("Customer", customer)
        cust_name_str = str(cust_doc.name)
        if cust_doc.accounts:
            for pa in cust_doc.accounts:
                if pa.company == global_settings_doc.default_company:
                    if not pa.account:
                        cust_without_account.append({"name":cust_doc.name, "acc_no": pa.debtor_creditor_number})
                else:
                    cust_without_account.append({"name":cust_doc.name, "acc_no": pa.debtor_creditor_number})
        else:
            cust_without_account.append({"name":cust_doc.name, "acc_no": ""})
    return cust_without_account
                    

def try_assign_existent_account(c):
    global_settings_doc = frappe.get_single("Global Defaults")
    cust_doc = frappe.get_doc("Customer", c["name"])
    acc_doc_list = frappe.get_all("Account", filters={"account_number": c["acc_no"]} )
    if not acc_doc_list:
        return False
    for pa in cust_doc.accounts:
            if pa.company == global_settings_doc.default_company:
                pa.account = acc_doc_list[0]["name"]
    cust_doc.save()
    return True