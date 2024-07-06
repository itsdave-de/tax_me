import frappe
from frappe.utils.pdf import get_pdf
from datetime import datetime

def get_sales_invoices(start_date, end_date):
    """Fetch sales invoices within a specific date range."""
    filters = {
        'docstatus': 1,  # 1 for submitted documents,
        "status": ['not in', ["Draft", "Cancelled"]],
        'posting_date': ['between', [start_date, end_date]]
    }
    fields = ['name', 'posting_date']

    return frappe.get_all('Sales Invoice', filters=filters, fields=fields)

def download_invoice_pdf(invoice, print_format, letterhead):
    """Download a sales invoice as a PDF with specified print format and letterhead."""
    invoice_name = invoice['name']
    invoice_date = invoice['posting_date'].strftime('%Y%m%d')  # Formatting the date as YYYYMMDD
    html = frappe.get_print('Sales Invoice', invoice_name, print_format)
    filedata = get_pdf(html)
    file_path = f'{invoice_date}_{invoice_name}.pdf'  # Prepending date to filename
    with open(file_path, 'wb') as file:
        file.write(filedata)

def download_invoices_in_date_range(start_date, end_date, print_format, letterhead):
    invoices = get_sales_invoices(start_date, end_date)
    for invoice in invoices:
        print(invoice)
        download_invoice_pdf(invoice, print_format, letterhead)

# Example usage
# download_invoices_in_date_range('2023-01-01', '2023-01-31', 'Your Print Format', 'Your Letterhead')
