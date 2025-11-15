import logging
import frappe
from frappe.utils import nowdate, nowtime

def fix_and_consolidate_stock(main_warehouse="Lagerräume", dry_run=False, log_file="/tmp/fix_negative_stock.log"):
    """
    1. Identify all warehouses where an item is negative (actual_qty < 0).
       Transfer up to the required quantity from main_warehouse to fix it.
    2. Move all positive stock from every other warehouse to the main_warehouse.
    3. Provide a dry_run mode to simulate transfers without actually creating Stock Entries.
    4. Log all actions to both console and a dedicated log file.
    """

    # ----------------------------
    # 1) SET UP LOGGER
    # ----------------------------
    logger = logging.getLogger("fix_negative_stock")
    logger.setLevel(logging.INFO)

    # Remove existing handlers if any (avoid duplicating logs if function is called multiple times)
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logger.info("===== Starting fix_and_consolidate_stock script =====")
    logger.info("Main Warehouse: %s | Dry Run: %s | Log File: %s", main_warehouse, dry_run, log_file)

    # ----------------------------
    # 2) FIX NEGATIVE STOCK
    # ----------------------------
    negative_bins = frappe.db.sql("""
        SELECT
            item_code,
            warehouse,
            actual_qty
        FROM `tabBin`
        WHERE actual_qty < 0
    """, as_dict=True)

    if not negative_bins:
        logger.info("No negative stock found in any warehouse. Proceeding to consolidation.")
    else:
        for bin_record in negative_bins:
            item_code = bin_record.item_code
            negative_qty = bin_record.actual_qty  # A negative value
            target_warehouse = bin_record.warehouse

            # Check main warehouse stock for this item
            main_bin = frappe.db.sql("""
                SELECT actual_qty
                FROM `tabBin`
                WHERE item_code = %s
                AND warehouse = %s
            """, (item_code, main_warehouse), as_dict=True)

            if not main_bin:
                # No record of this item in the main warehouse
                logger.info(
                    "Cannot fix negative stock for Item %s in Warehouse %s "
                    "(no bin in main warehouse %s). Skipping.",
                    item_code, target_warehouse, main_warehouse
                )
                continue

            main_warehouse_qty = main_bin[0].actual_qty or 0
            if main_warehouse_qty <= 0:
                logger.info(
                    "No positive stock in main warehouse (%s) to fix Item %s (negative in %s). Skipping.",
                    main_warehouse, item_code, target_warehouse
                )
                continue

            # Calculate how much to transfer: limited by available main warehouse qty
            transfer_qty = min(main_warehouse_qty, abs(negative_qty))
            if transfer_qty <= 0:
                continue  # Nothing to transfer

            logger.info(
                "Fixing negative stock for Item %s in Warehouse %s. "
                "Transferring %s from %s to %s.",
                item_code, target_warehouse, transfer_qty, main_warehouse, target_warehouse
            )

            if not dry_run:
                # Create the Stock Entry
                se = frappe.get_doc({
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Material Transfer",
                    "posting_date": nowdate(),
                    "posting_time": nowtime(),
                    "items": []
                })
                # Add item line
                se.append("items", {
                    "item_code": item_code,
                    "qty": transfer_qty,
                    "uom": frappe.db.get_value("Item", item_code, "stock_uom"),
                    "conversion_factor": 1,
                    "s_warehouse": main_warehouse,
                    "t_warehouse": target_warehouse
                })
                # Insert and submit
                se.insert()
                se.submit()
                frappe.db.commit()
            else:
                logger.info("(Dry Run) - Would have created and submitted Stock Entry.")

    # ----------------------------
    # 3) MOVE ALL POSITIVE STOCK TO MAIN WAREHOUSE
    # ----------------------------
    logger.info("Consolidating all positive stock to main warehouse: %s", main_warehouse)

    positive_bins = frappe.db.sql("""
        SELECT
            item_code,
            warehouse,
            actual_qty
        FROM `tabBin`
        WHERE actual_qty > 0
          AND warehouse != %s
    """, main_warehouse, as_dict=True)

    if not positive_bins:
        logger.info("No positive stock found outside the main warehouse. Consolidation not required.")
    else:
        for bin_record in positive_bins:
            item_code = bin_record.item_code
            source_warehouse = bin_record.warehouse
            positive_qty = bin_record.actual_qty

            logger.info(
                "Transferring all %s of Item %s from Warehouse %s to %s.",
                positive_qty, item_code, source_warehouse, main_warehouse
            )

            if not dry_run:
                # Create the Stock Entry
                se = frappe.get_doc({
                    "doctype": "Stock Entry",
                    "stock_entry_type": "Material Transfer",
                    "posting_date": nowdate(),
                    "posting_time": nowtime(),
                    "items": []
                })
                se.append("items", {
                    "item_code": item_code,
                    "qty": positive_qty,
                    "uom": frappe.db.get_value("Item", item_code, "stock_uom"),
                    "conversion_factor": 1,
                    "s_warehouse": source_warehouse,
                    "t_warehouse": main_warehouse
                })
                se.insert()
                se.submit()
                frappe.db.commit()
            else:
                logger.info("(Dry Run) - Would have created and submitted Stock Entry.")

    logger.info("===== fix_and_consolidate_stock script completed. =====")
