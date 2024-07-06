import frappe
from erpnext.stock.utils import get_stock_balance

def move_stock():
   
    # Settings
    dry_run = False  # Set to False to execute the transfer
    target_warehouse = "Lagerräume - IG"

    # Get all warehouses except 'Lagerräume'
    warehouses = frappe.get_all('Warehouse', filters={'name': ['!=', target_warehouse]}, fields=['name'])

    for warehouse in warehouses:
        # Get items in the current warehouse
        items = frappe.get_all('Bin', filters={'warehouse': warehouse['name']}, fields=['item_code', 'actual_qty'])

        for item in items:
            if item['actual_qty'] > 0:
                if dry_run:
                    # Dry run mode: Only display the action
                    print(f"Dry run: Would move {item['actual_qty']} of {item['item_code']} from {warehouse['name']} to {target_warehouse}")
                else:
                    # Create and submit a new Stock Entry
                    stock_entry = frappe.get_doc({
                        'doctype': 'Stock Entry',
                        'stock_entry_type': 'Material Transfer',
                        'items': [{
                            'item_code': item['item_code'],
                            'qty': item['actual_qty'],
                            's_warehouse': warehouse['name'],
                            't_warehouse': target_warehouse
                        }]
                    })
                    stock_entry.insert()
                    stock_entry.submit()
                    frappe.db.commit()

    if dry_run:
        print("Dry run completed. No actual changes were made.")
    else:
        print("All items moved to", target_warehouse)


def show_negative_with_positive_balance():

    # Settings
    dry_run = False  # Set to False to execute the transfer
    target_warehouse = "Lagerräume - IG"

    # Fetch all items
    items = frappe.get_all('Item', fields=['name'])

    # Check stock levels for each item
    for item in items:
        item_code = item['name']
        negative_stock_warehouses = []
        positive_stock_in_target = False

        # Check stock in all warehouses
        warehouses = frappe.get_all('Warehouse', fields=['name'])
        for warehouse in warehouses:
            warehouse_name = warehouse['name']
            stock_qty = get_stock_balance(item_code, warehouse_name)

            if warehouse_name == target_warehouse and stock_qty > 0:
                positive_stock_in_target = True

            if stock_qty < 0:
                negative_stock_warehouses.append(warehouse_name)

        if positive_stock_in_target and negative_stock_warehouses:
            print(f"Item: {item_code} has negative stock in {negative_stock_warehouses} and positive stock in {target_warehouse}")

    print("Search completed.")


def resolve_negative_stock_from_positive_stock():

    # Settings
    dry_run = False  # Set to False to execute the transfer
    target_warehouse = "Lagerräume - IG"

    # Fetch all items
    items = frappe.get_all('Item', fields=['name'])

    for item in items:
        item_code = item['name']
        total_negative_stock = 0
        negative_stock_warehouses = []

        # Check stock in all warehouses except 'Lagerräume'
        warehouses = frappe.get_all('Warehouse', filters={'name': ['!=', target_warehouse]}, fields=['name'])
        for warehouse in warehouses:
            warehouse_name = warehouse['name']
            stock_qty = get_stock_balance(item_code, warehouse_name)
            
            if stock_qty < 0:
                total_negative_stock += abs(stock_qty)
                negative_stock_warehouses.append({'name': warehouse_name, 'qty': abs(stock_qty)})

        # Check available stock in 'Lagerräume'
        available_stock_in_target = get_stock_balance(item_code, target_warehouse)

        if dry_run:
            print(f"Dry run for {item_code}:")
            print(f"    Available stock in {target_warehouse}: {available_stock_in_target}")
            for warehouse in negative_stock_warehouses:
                print(f"    Negative stock in {warehouse['name']}: {warehouse['qty']}")

        # Move stock from 'Lagerräume' to other warehouses with negative stock
        for warehouse in negative_stock_warehouses:
            if available_stock_in_target <= 0:
                if dry_run:
                    print(f"    Cannot transfer more from {target_warehouse} - stock depleted.")
                break  # No more stock available in 'Lagerräume'

            transfer_qty = min(warehouse['qty'], available_stock_in_target)
            available_stock_in_target -= transfer_qty

            if dry_run:
                # Dry run mode: Only display the action
                print(f"    Would move {transfer_qty} of {item_code} from {target_warehouse} to {warehouse['name']} to cover negative stock.")
            else:
                # Create and submit a new Stock Entry
                stock_entry = frappe.get_doc({
                    'doctype': 'Stock Entry',
                    'stock_entry_type': 'Material Transfer',
                    'items': [{
                        'item_code': item_code,
                        'qty': transfer_qty,
                        's_warehouse': target_warehouse,
                        't_warehouse': warehouse['name']
                    }]
                })
                stock_entry.insert()
                stock_entry.submit()
                frappe.db.commit()

                print(f"Moved {transfer_qty} of {item_code} from {target_warehouse} to {warehouse['name']}")

    print("Stock adjustment process completed.")
