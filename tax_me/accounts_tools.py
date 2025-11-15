import frappe
import json

def create_accounts_from_json(data, parent_account=None, root_type=None, company='Your Company Name'):
    # Fetch company abbreviation
    company_abbr = frappe.get_value('Company', company, 'abbr')
    if not company_abbr:
        print(f"Company abbreviation not found for company: {company}")
        return

    for account_name, account_data in data.items():
        # Strip any leading/trailing spaces from account_name
        account_name = account_name.strip()

        # Initialize account fields
        account_fields = {
            'doctype': 'Account',
            'account_name': account_name,
            'company': company,
            'is_group': 0,
        }

        # Update root_type if provided
        if root_type:
            account_fields['root_type'] = root_type

        # Set fields from account_data
        if 'root_type' in account_data:
            account_fields['root_type'] = account_data['root_type']
        if 'account_type' in account_data:
            account_fields['account_type'] = account_data['account_type']
        if 'account_number' in account_data:
            account_fields['account_number'] = account_data['account_number']
        if 'is_group' in account_data:
            account_fields['is_group'] = account_data['is_group']
        else:
            # Determine if account is a group based on sub-accounts
            if any(isinstance(v, dict) for v in account_data.values()):
                account_fields['is_group'] = 1

        # Set report type based on root_type
        if 'root_type' in account_fields:
            if account_fields['root_type'] in ['Asset', 'Liability', 'Equity']:
                account_fields['report_type'] = 'Balance Sheet'
            elif account_fields['root_type'] in ['Income', 'Expense']:
                account_fields['report_type'] = 'Profit and Loss'

        # For root accounts, parent_account should be None
        if parent_account is None:
            account_fields['parent_account'] = None
        else:
            # Since parent_account now includes the company abbreviation, we can use it directly
            account_fields['parent_account'] = parent_account

        # Build the full account name with company abbreviation
        full_account_name = f"{account_name} - {company_abbr}"

        # Check if account already exists
        existing_account = frappe.db.exists("Account", {'name': full_account_name})

        if not existing_account:
            # Create new account
            print(f"Creating account: {full_account_name} under parent: {account_fields['parent_account']}")
            new_account = frappe.get_doc(account_fields)
            new_account.insert(ignore_mandatory=True)
            frappe.db.commit()
            full_account_name = new_account.name.strip()
            print(f"Created account: {full_account_name}")
        else:
            print(f"Account already exists: {full_account_name}")

        # Recursively create child accounts
        sub_accounts = {k.strip(): v for k, v in account_data.items() if isinstance(v, dict)}
        if sub_accounts:
            # Pass down the root_type if not explicitly set in child
            child_root_type = account_fields.get('root_type')
            create_accounts_from_json(
                sub_accounts,
                parent_account=full_account_name,  # Use the full account name here
                root_type=child_root_type,
                company=company
            )