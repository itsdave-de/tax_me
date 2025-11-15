import frappe
from frappe.utils.file_manager import save_file

@frappe.whitelist(allow_guest=True)
def export_print_format(print_format_name):
    try:
        print_format = frappe.get_doc("Print Format", print_format_name)
        # Export as JSON or desired format
        data = frappe.as_json(print_format.as_dict())
        # Optional: Save the file on the server or return it as a response
        return data
    except Exception as e:
        frappe.throw(f"Error exporting Print Format: {str(e)}")


@frappe.whitelist(allow_guest=True)
def import_print_format(json_data):
    try:
        data = frappe.parse_json(json_data)
        # Check if Print Format already exists
        if frappe.db.exists("Print Format", data.get('name')):
            print_format = frappe.get_doc("Print Format", data.get('name'))
            print_format.update(data)
            print_format.save()
        else:
            new_print_format = frappe.get_doc(data)
            new_print_format.insert()
        frappe.db.commit()
        return "Print Format imported successfully"
    except Exception as e:
        frappe.throw(f"Error importing Print Format: {str(e)}")
