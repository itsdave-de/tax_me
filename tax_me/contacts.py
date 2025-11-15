import frappe

def list_customers_without_primary_or_billing_contacts():
    # Get all enabled customers
    customers = frappe.get_all("Customer", filters={"disabled": 0}, fields=["name"])

    customer_count = 0
    contact_count = 0

    for customer in customers:
        # Get all contacts associated with the current customer
        contacts = frappe.get_all(
            "Dynamic Link", 
            filters={
                "link_doctype": "Customer", 
                "link_name": customer['name'],
                "parenttype": "Contact"
            }, 
            fields=["parent"]
        )

        if not contacts:
            continue  # Skip customers with no contacts

        # Check if any contact is marked as primary or billing
        has_primary = False
        has_billing = False
        for contact_link in contacts:
            contact = frappe.get_doc("Contact", contact_link["parent"])
            if contact.is_primary_contact:
                has_primary = True
            if contact.is_billing_contact:
                has_billing = True

        # If no primary or billing contact, print the customer and its contacts
        if not has_primary and not has_billing:
            customer_count += 1
            print(f"Customer: {customer['name']}")
            for contact_link in contacts:
                contact = frappe.get_doc("Contact", contact_link["parent"])
                contact_count += 1
                print(f"  Contact: {contact.first_name} {contact.last_name or ''}")
                print(f"    Email: {contact.email_id}")
                print(f"    Phone: {contact.phone}")
                print(f"    Mobile: {contact.mobile_no}")

    print(f"\nTotal Customers without Primary or Billing Contact: {customer_count}")
    print(f"Total Contacts: {contact_count}")

# Run the function
list_customers_without_primary_or_billing_contacts()
