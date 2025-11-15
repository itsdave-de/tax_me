import frappe

def update_contacts_to_primary_and_billing():
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

        # If no primary or billing contact, set the first contact as primary and billing
        if not has_primary and not has_billing:
            customer_count += 1
            first_contact_set = False
            print(f"Customer: {customer['name']}")
            for contact_link in contacts:
                contact = frappe.get_doc("Contact", contact_link["parent"])
                contact_count += 1

                # Set as primary and billing contact if not already set
                if not first_contact_set:
                    contact.is_primary_contact = 1
                    contact.is_billing_contact = 1
                    contact.save()
                    frappe.db.commit()  # Commit the changes to the database
                    first_contact_set = True
                    print(f"  Updated Contact: {contact.first_name} {contact.last_name or ''} as Primary and Billing Contact")
                else:
                    print(f"  Contact: {contact.first_name} {contact.last_name or ''} (Not Updated)")

    print(f"\nTotal Customers updated: {customer_count}")
    print(f"Total Contacts processed: {contact_count}")

