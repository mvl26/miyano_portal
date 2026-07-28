"""PORTAL-FOUNDATION master-data import: loads the JSON produced by
``export_supplycore.export_masters`` and idempotently creates/ensures the
equivalent native ERPNext records.

Every create is guarded by a ``frappe.db.exists`` (or an equivalent lookup)
check, so ``import_masters`` is safe to call more than once on the same file.

Real exported production data is dirty: some SC Items are missing
``item_group`` / ``stock_uom`` / ``item_name``, and some SFC contract lines
reference items that don't otherwise exist. ``import_masters`` is hardened
against both problems:

* Missing/unresolvable mandatory fields on an Item are defaulted to a
  fallback Item Group / UOM (created once, lazily) instead of raising.
* Every individual record create (item / customer / contract) is wrapped in
  a try/except backed by a DB savepoint, so one bad record is recorded in a
  ``skipped`` list and the rest of the import keeps going instead of
  aborting (and leaving a partially-applied run behind).

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
from contextlib import contextmanager

import frappe
from frappe.utils import random_string

STANDARD_SELLING_PRICE_LIST = "Standard Selling"
DEFAULT_CURRENCY = "VND"
DEFAULT_COUNTRY = "Vietnam"
PREFERRED_COMPANY = "Miyano Việt Nam"

# Fallback mandatories used when a source record is missing (or references a
# nonexistent) Item Group / UOM. Created lazily, once, on first use.
FALLBACK_ITEM_GROUP = "Sản phẩm"
FALLBACK_UOM = "Cái"


@contextmanager
def _savepoint():
    """Run a block of DB writes inside a MariaDB savepoint.

    On success the savepoint is released. On failure the DB is rolled back
    to the savepoint (undoing only this record's partial writes, not the
    whole import so far) and the exception is re-raised for the caller to
    catch and record in a ``skipped`` list.
    """
    sp = "mig" + random_string(12)
    frappe.db.savepoint(sp)
    try:
        yield
    except Exception:
        frappe.db.rollback(save_point=sp)
        raise
    else:
        frappe.db.release_savepoint(sp)


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


def _resolve_item_group(item_group_name: str | None) -> str:
    """Return an Item Group guaranteed to exist for use on an Item.

    Only trusts the source value when it's non-empty AND already exists
    (i.e. it was properly declared in the export's ``item_groups`` section,
    which is imported before items). An empty/missing value, or one that
    names a group that doesn't exist after the item-group import step,
    falls back to ``FALLBACK_ITEM_GROUP`` (created lazily, once) rather than
    either raising MandatoryError or silently vivifying an arbitrary
    one-off Item Group from a possibly-dirty/typo'd per-item string.
    """
    name = (item_group_name or "").strip()
    if name and frappe.db.exists("Item Group", name):
        return name
    _ensure_item_group(FALLBACK_ITEM_GROUP)
    return FALLBACK_ITEM_GROUP


def _resolve_stock_uom(uom_name: str | None) -> str:
    """Return a UOM guaranteed to exist for use as an Item's stock_uom.

    Same policy as ``_resolve_item_group``: only trusts a source value that
    is non-empty and already exists (declared in the export's ``uoms``
    section); anything else falls back to ``FALLBACK_UOM``.
    """
    name = (uom_name or "").strip()
    if name and frappe.db.exists("UOM", name):
        return name
    _ensure_uom(FALLBACK_UOM)
    return FALLBACK_UOM


def _ensure_item(item: dict) -> tuple[bool, bool]:
    """Ensure the Item (and, when selling_price > 0, its Standard Selling
    Item Price) exist. Returns (item_created, item_price_created).

    Dirty-source defaulting: an empty/missing (or otherwise unresolvable)
    item_group / uom is defaulted to the fallback Item Group / UOM instead
    of letting frappe raise MandatoryError. An empty item_name defaults to
    the item_code.
    """
    item_code = item.get("item_code")
    if not item_code:
        return False, False

    item_group = _resolve_item_group(item.get("item_group"))
    stock_uom = _resolve_stock_uom(item.get("uom"))
    item_name = (item.get("item_name") or "").strip() or item_code

    item_created = False
    if not frappe.db.exists("Item", item_code):
        frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_name,
                "description": item.get("description"),
                "item_group": item_group,
                "stock_uom": stock_uom,
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
                    "uom": stock_uom,
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

    Contract lines whose item_code doesn't resolve to an existing Item are
    dropped (and reported in ``skipped_lines``) rather than failing the
    whole contract. If no line survives, the whole contract is skipped
    (``skip_reason`` set) rather than creating an empty Blanket Order.

    Returns a per-contract result dict:
        {"blanket_orders": int, "price_lists": int, "item_prices": int,
         "skipped_lines": [...], "skip_reason": str | None}
    """
    result = {
        "blanket_orders": 0,
        "price_lists": 0,
        "item_prices": 0,
        "skipped_lines": [],
        "skip_reason": None,
    }

    customer_name = customer_name_by_sc_id.get(contract.get("customer"))
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        # Unknown / unmapped customer: nothing sensible to link to, skip.
        result["skip_reason"] = f"unknown/unmapped customer reference: {contract.get('customer')!r}"
        return result

    contract_number = contract.get("contract_number") or contract.get("name")
    items = contract.get("items") or []

    valid_items = []
    for sfc_item in items:
        item_code = sfc_item.get("item")
        if not item_code or not frappe.db.exists("Item", item_code):
            result["skipped_lines"].append(
                {
                    "item_code": item_code or "<missing>",
                    "error": "missing item_code" if not item_code else "item_code does not resolve to an existing Item",
                }
            )
            continue
        valid_items.append(sfc_item)

    if not valid_items:
        result["skip_reason"] = "no valid item lines (all referenced items are missing/unresolvable)"
        return result

    price_list_name = f"HĐNT-{contract_number}"
    if _ensure_price_list(price_list_name):
        result["price_lists"] += 1

    for sfc_item in valid_items:
        item_code = sfc_item.get("item")
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
                    for sfc_item in valid_items
                ],
            }
        )
        bo.insert(ignore_permissions=True)
        result["blanket_orders"] += 1

    return result


def import_masters(infile: str) -> dict:
    """Idempotently create/ensure native ERPNext records from the JSON
    produced by ``export_supplycore.export_masters``. Safe to call repeatedly
    on the same file (every create is guarded by frappe.db.exists), and
    resilient to dirty source records: a failure on one item / customer /
    contract is recorded in that entity's ``skipped`` list instead of
    aborting the whole run, so a partial run can simply be re-run to
    completion.
    """
    with open(infile, encoding="utf-8") as f:
        data = json.load(f)

    company = _resolve_company()

    counts = {
        "item_groups": 0,
        "uoms": 0,
        "items": {"created": 0, "skipped": []},
        "item_prices": 0,
        "customers": {"created": 0, "skipped": []},
        "contacts": {"created": 0, "skipped": []},
        "addresses": {"created": 0, "skipped": []},
        "price_lists": 0,
        "contracts": {"created": 0, "skipped": [], "skipped_lines": []},
        "blanket_orders": 0,
        "contract_item_prices": 0,
    }

    for item_group in data.get("item_groups", []):
        name = item_group.get("group_name") or item_group.get("name")
        try:
            with _savepoint():
                created = _ensure_item_group(name)
            counts["item_groups"] += int(created)
        except Exception:
            # Reference data: fall through, individual Items will still get
            # a usable Item Group via the fallback-defaulting in _ensure_item.
            continue

    for uom in data.get("uoms", []):
        name = uom.get("uom_name") or uom.get("name")
        try:
            with _savepoint():
                created = _ensure_uom(name)
            counts["uoms"] += int(created)
        except Exception:
            continue

    for item in data.get("items", []):
        item_label = item.get("item_code") or item.get("name") or "<unknown>"
        try:
            with _savepoint():
                created, priced = _ensure_item(item)
            counts["items"]["created"] += int(created)
            counts["item_prices"] += int(priced)
        except Exception as e:
            counts["items"]["skipped"].append({"item_code": item_label, "error": str(e)})

    customer_name_by_sc_id = {}
    for customer in data.get("customers", []):
        customer_label = customer.get("customer_name") or customer.get("name") or "<unknown>"

        try:
            with _savepoint():
                created = _ensure_customer(customer)
            counts["customers"]["created"] += int(created)
        except Exception as e:
            counts["customers"]["skipped"].append({"customer": customer_label, "error": str(e)})

        try:
            with _savepoint():
                created = _ensure_contact(customer)
            counts["contacts"]["created"] += int(created)
        except Exception as e:
            counts["contacts"]["skipped"].append({"customer": customer_label, "error": str(e)})

        try:
            with _savepoint():
                created = _ensure_address(customer)
            counts["addresses"]["created"] += int(created)
        except Exception as e:
            counts["addresses"]["skipped"].append({"customer": customer_label, "error": str(e)})

        sc_id = customer.get("name")
        if sc_id:
            customer_name_by_sc_id[sc_id] = customer.get("customer_name")

    for contract in data.get("framework_contracts", []):
        contract_label = contract.get("contract_number") or contract.get("name") or "<unknown>"
        try:
            with _savepoint():
                contract_result = _ensure_contract(contract, company, customer_name_by_sc_id)

            counts["blanket_orders"] += contract_result["blanket_orders"]
            counts["price_lists"] += contract_result["price_lists"]
            counts["contract_item_prices"] += contract_result["item_prices"]

            for line in contract_result["skipped_lines"]:
                counts["contracts"]["skipped_lines"].append({"contract": contract_label, **line})

            if contract_result["skip_reason"]:
                counts["contracts"]["skipped"].append(
                    {"contract": contract_label, "error": contract_result["skip_reason"]}
                )
            else:
                counts["contracts"]["created"] += contract_result["blanket_orders"]
        except Exception as e:
            counts["contracts"]["skipped"].append({"contract": contract_label, "error": str(e)})

    return counts
