"""PORTAL-FOUNDATION master-data import: loads the JSON produced by
``export_supplycore.export_masters`` and idempotently creates/ensures the
equivalent native ERPNext records.

Every create is guarded by a ``frappe.db.exists`` (or an equivalent lookup)
check, so ``import_masters`` is safe to call more than once on the same file.

Mapping (see module docstring of export_supplycore.py for the source side):
    SC Item Group       -> Item Group
    SC UOM               -> UOM
    SC Item               -> Item (+ Item Price on "Standard Selling" when
                              selling_price > 0)
    SC Customer           -> Customer (+ Contact when email present,
                              + Address("Shipping") when shipping_address present)
    SC Sales Framework Contract (+ SFC Item)
                          -> Blanket Order (Selling) + a per-contract Price
                              List "HĐNT-<contract_number>" with Item Price
                              rows, and Customer.default_price_list set to it.
"""

import json

import frappe

STANDARD_SELLING_PRICE_LIST = "Standard Selling"
DEFAULT_CURRENCY = "VND"
DEFAULT_COUNTRY = "Vietnam"
PREFERRED_COMPANY = "Miyano Việt Nam"


def _resolve_company() -> str:
    """Pick the ERPNext Company to use for Blanket Orders.

    Prefers the exact "Miyano Việt Nam" company (matches the existing seed
    data / production naming). Falls back to any company whose name contains
    "Miyano", then to the first Company found. Raises if none exist.
    """
    companies = [c["name"] for c in frappe.get_all("Company", fields=["name"])]
    if PREFERRED_COMPANY in companies:
        return PREFERRED_COMPANY
    for name in companies:
        if "Miyano" in name:
            return name
    if companies:
        return companies[0]
    frappe.throw("No Company found in the target site; cannot import Blanket Orders.")


def _ensure_item_group(item_group_name: str | None) -> bool:
    if not item_group_name:
        return False
    if frappe.db.exists("Item Group", item_group_name):
        return False
    frappe.get_doc(
        {
            "doctype": "Item Group",
            "item_group_name": item_group_name,
            "parent_item_group": "All Item Groups",
            "is_group": 0,
        }
    ).insert(ignore_permissions=True)
    return True


def _ensure_uom(uom_name: str | None) -> bool:
    if not uom_name:
        return False
    if frappe.db.exists("UOM", uom_name):
        return False
    frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)
    return True


def _ensure_price_list(name: str, selling: int = 1, currency: str = DEFAULT_CURRENCY) -> bool:
    if frappe.db.exists("Price List", name):
        return False
    frappe.get_doc(
        {
            "doctype": "Price List",
            "price_list_name": name,
            "selling": selling,
            "currency": currency,
        }
    ).insert(ignore_permissions=True)
    return True


def _ensure_item(item: dict) -> tuple[bool, bool]:
    """Ensure the Item (and, when selling_price > 0, its Standard Selling
    Item Price) exist. Returns (item_created, item_price_created)."""
    item_code = item.get("item_code")
    if not item_code:
        return False, False

    _ensure_item_group(item.get("item_group"))
    _ensure_uom(item.get("uom"))

    item_created = False
    if not frappe.db.exists("Item", item_code):
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item.get("item_name") or item_code,
                "description": item.get("description"),
                "item_group": item.get("item_group"),
                "stock_uom": item.get("uom"),
                "is_stock_item": 1 if item.get("is_stock_item") else 0,
                "has_batch_no": 1 if item.get("has_batch_no") else 0,
                "disabled": 1 if item.get("disabled") else 0,
            }
        ).insert(ignore_permissions=True)
        item_created = True

    price_created = False
    selling_price = item.get("selling_price") or 0
    if float(selling_price) > 0:
        _ensure_price_list(STANDARD_SELLING_PRICE_LIST)
        if not frappe.db.exists(
            "Item Price",
            {"item_code": item_code, "price_list": STANDARD_SELLING_PRICE_LIST, "selling": 1},
        ):
            frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": item_code,
                    "price_list": STANDARD_SELLING_PRICE_LIST,
                    "uom": item.get("uom"),
                    "selling": 1,
                    "price_list_rate": selling_price,
                    "currency": DEFAULT_CURRENCY,
                }
            ).insert(ignore_permissions=True)
            price_created = True

    return item_created, price_created


def _ensure_customer(customer: dict) -> bool:
    customer_name = customer.get("customer_name")
    if not customer_name:
        return False
    if frappe.db.exists("Customer", customer_name):
        return False
    frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Company",
            "customer_group": "All Customer Groups",
            "territory": "All Territories",
            "tax_id": customer.get("tax_code"),
        }
    ).insert(ignore_permissions=True)
    return True


def _ensure_contact(customer: dict) -> bool:
    customer_name = customer.get("customer_name")
    email = customer.get("email")
    if not customer_name or not email:
        return False
    contact_name = f"{customer_name}-Contact"
    if frappe.db.exists("Contact", contact_name):
        return False
    ct = frappe.new_doc("Contact")
    ct.first_name = customer_name
    ct.append("email_ids", {"email_id": email, "is_primary": 1})
    ct.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    ct.name = contact_name
    ct.insert(ignore_permissions=True, set_name=contact_name)
    return True


def _ensure_address(customer: dict) -> bool:
    customer_name = customer.get("customer_name")
    shipping_address = customer.get("shipping_address")
    if not customer_name or not shipping_address:
        return False
    address_name = f"{customer_name}-Shipping"
    if frappe.db.exists("Address", address_name):
        return False
    addr = frappe.new_doc("Address")
    addr.address_title = customer_name
    addr.address_type = "Shipping"
    addr.address_line1 = shipping_address
    addr.city = "N/A"
    addr.country = DEFAULT_COUNTRY
    addr.append("links", {"link_doctype": "Customer", "link_name": customer_name})
    addr.name = address_name
    addr.insert(ignore_permissions=True, set_name=address_name)
    return True


def _ensure_contract(contract: dict, company: str, customer_name_by_sc_id: dict) -> dict:
    """Ensure the per-contract Price List (+ Item Price rows) and the
    Blanket Order for a single SC Sales Framework Contract. Also points the
    customer's default_price_list at the contract price list.

    Returns a per-contract count dict.
    """
    result = {"blanket_orders": 0, "price_lists": 0, "item_prices": 0}

    customer_name = customer_name_by_sc_id.get(contract.get("customer"))
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        # Unknown / unmapped customer: nothing sensible to link to, skip.
        return result

    contract_number = contract.get("contract_number") or contract.get("name")
    items = contract.get("items") or []

    price_list_name = f"HĐNT-{contract_number}"
    if _ensure_price_list(price_list_name):
        result["price_lists"] += 1

    for sfc_item in items:
        item_code = sfc_item.get("item")
        if not item_code:
            continue
        if frappe.db.exists(
            "Item Price", {"item_code": item_code, "price_list": price_list_name, "selling": 1}
        ):
            continue
        frappe.get_doc(
            {
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": price_list_name,
                "uom": sfc_item.get("uom"),
                "selling": 1,
                "price_list_rate": sfc_item.get("unit_price") or 0,
                "currency": DEFAULT_CURRENCY,
            }
        ).insert(ignore_permissions=True)
        result["item_prices"] += 1

    if frappe.db.get_value("Customer", customer_name, "default_price_list") != price_list_name:
        frappe.db.set_value("Customer", customer_name, "default_price_list", price_list_name)

    existing_bo = frappe.db.get_value(
        "Blanket Order",
        {"customer": customer_name, "order_no": contract_number, "blanket_order_type": "Selling"},
        "name",
    )
    if not existing_bo:
        bo = frappe.get_doc(
            {
                "doctype": "Blanket Order",
                "blanket_order_type": "Selling",
                "customer": customer_name,
                "company": company,
                "from_date": contract.get("valid_from"),
                "to_date": contract.get("valid_to"),
                "order_no": contract_number,
                "items": [
                    {
                        "item_code": sfc_item.get("item"),
                        "qty": sfc_item.get("contract_qty") or 0,
                        "rate": sfc_item.get("unit_price") or 0,
                    }
                    for sfc_item in items
                ],
            }
        )
        bo.insert(ignore_permissions=True)
        result["blanket_orders"] += 1

    return result


def import_masters(infile: str) -> dict:
    """Idempotently create/ensure native ERPNext records from the JSON
    produced by ``export_supplycore.export_masters``. Safe to call repeatedly
    on the same file (every create is guarded by frappe.db.exists).
    """
    with open(infile, encoding="utf-8") as f:
        data = json.load(f)

    company = _resolve_company()

    counts = {
        "item_groups": 0,
        "uoms": 0,
        "items": 0,
        "item_prices": 0,
        "customers": 0,
        "contacts": 0,
        "addresses": 0,
        "price_lists": 0,
        "blanket_orders": 0,
        "contract_item_prices": 0,
    }

    for item_group in data.get("item_groups", []):
        name = item_group.get("group_name") or item_group.get("name")
        if _ensure_item_group(name):
            counts["item_groups"] += 1

    for uom in data.get("uoms", []):
        name = uom.get("uom_name") or uom.get("name")
        if _ensure_uom(name):
            counts["uoms"] += 1

    for item in data.get("items", []):
        created, priced = _ensure_item(item)
        counts["items"] += int(created)
        counts["item_prices"] += int(priced)

    customer_name_by_sc_id = {}
    for customer in data.get("customers", []):
        counts["customers"] += int(_ensure_customer(customer))
        counts["contacts"] += int(_ensure_contact(customer))
        counts["addresses"] += int(_ensure_address(customer))
        sc_id = customer.get("name")
        if sc_id:
            customer_name_by_sc_id[sc_id] = customer.get("customer_name")

    for contract in data.get("framework_contracts", []):
        contract_result = _ensure_contract(contract, company, customer_name_by_sc_id)
        counts["blanket_orders"] += contract_result["blanket_orders"]
        counts["price_lists"] += contract_result["price_lists"]
        counts["contract_item_prices"] += contract_result["item_prices"]

    return counts
