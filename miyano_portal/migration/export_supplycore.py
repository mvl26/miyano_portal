"""PORTAL-FOUNDATION master-data export from the legacy Supplycore (SC*) doctypes.

STRICTLY READ-ONLY. This module is executed against the PRODUCTION supplycore
site by the controller, so it must never mutate the database:

- Only ``frappe.get_all`` / ``frappe.db.get_value`` / ``frappe.get_doc(...).as_dict()``
  are used to read data.
- No ``insert`` / ``save`` / ``delete`` / ``db_set`` / ``db.set_value`` / ``db.commit``
  call appears anywhere in this file.
- The only side effect is writing the resulting JSON to ``outfile`` on disk.

Source doctypes read (all prefixed ``SC`` in the legacy supplycore app):
    SC Item Group, SC UOM, SC Item, SC Customer,
    SC Sales Framework Contract (+ child table SFC Item)
"""

import json

import frappe

ITEM_GROUP_FIELDS = ["name", "group_name", "parent_group", "is_group", "disabled"]
UOM_FIELDS = ["name", "uom_name", "abbreviation", "disabled"]
ITEM_FIELDS = [
    "name",
    "item_code",
    "item_name",
    "description",
    "item_group",
    "uom",
    "is_stock_item",
    "has_batch_no",
    "disabled",
    "selling_price",
]
CUSTOMER_FIELDS = [
    "name",
    "customer_name",
    "tax_code",
    "email",
    "phone",
    "billing_address",
    "shipping_address",
    "credit_limit",
    "status",
]
CONTRACT_FIELDS = ["name", "customer", "contract_number", "valid_from", "valid_to", "status"]
SFC_ITEM_FIELDS = ["item", "uom", "contract_qty", "sold_qty", "unit_price"]


def _export_item_groups() -> list[dict]:
    """Read-only: frappe.get_all against SC Item Group."""
    return frappe.get_all("SC Item Group", fields=ITEM_GROUP_FIELDS)


def _export_uoms() -> list[dict]:
    """Read-only: frappe.get_all against SC UOM."""
    return frappe.get_all("SC UOM", fields=UOM_FIELDS)


def _export_items() -> list[dict]:
    """Read-only: frappe.get_all against SC Item."""
    return frappe.get_all("SC Item", fields=ITEM_FIELDS)


def _export_customers() -> list[dict]:
    """Read-only: frappe.get_all against SC Customer."""
    return frappe.get_all("SC Customer", fields=CUSTOMER_FIELDS)


def _export_framework_contracts() -> list[dict]:
    """Read-only: frappe.get_all against SC Sales Framework Contract + child SFC Item."""
    contracts = frappe.get_all("SC Sales Framework Contract", fields=CONTRACT_FIELDS)
    for contract in contracts:
        contract["items"] = frappe.get_all(
            "SFC Item",
            filters={"parenttype": "SC Sales Framework Contract", "parent": contract["name"]},
            fields=SFC_ITEM_FIELDS,
            order_by="idx",
        )
    return contracts


def export_masters(outfile: str) -> dict:
    """Read PORTAL-FOUNDATION master data out of the legacy SC* doctypes and
    write it to ``outfile`` as JSON. Performs zero writes to the database.

    Returns a count summary, e.g.::

        {"item_groups": 12, "uoms": 5, "items": 340, "customers": 58, "framework_contracts": 21}
    """
    data = {
        "item_groups": _export_item_groups(),
        "uoms": _export_uoms(),
        "items": _export_items(),
        "customers": _export_customers(),
        "framework_contracts": _export_framework_contracts(),
    }

    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    return {key: len(value) for key, value in data.items()}
