"""Clean UAT scenario: one customer, one framework contract (Blanket Order),
one warehouse with opening stock. Idempotent — safe to run repeatedly.

Run with:
    bench --site <site> execute miyano_portal.setup.uat_scenario.setup_uat
"""

import frappe

COMPANY = "Miyano Việt Nam"
COMPANY_ABBR = "MYN"

WAREHOUSE_NAME = "Kho Miyano - MYN"  # already carries the " - MYN" suffix ERPNext expects

ITEM_GROUP = "Vật tư y tế"
UOMS = ["Hộp", "Cái"]

PRICE_LIST = "HĐNT-DKMiyano-2026"

CUSTOMER = "Bệnh viện Đa khoa Miyano"
CUSTOMER_TAX_ID = "0100999888"
CUSTOMER_ADDRESS_LINE1 = "10 Trần Duy Hưng, Cầu Giấy, Hà Nội"
CONTACT_FIRST_NAME = "Khoa Dược BV Đa khoa Miyano"
PORTAL_EMAIL = "uat@demo.miyano"
PORTAL_PASSWORD = "Portal@123"

ITEMS = [
    {
        "item_code": "MYN-GLOVE-M",
        "item_name": "Găng tay khám nitrile size M – hộp 100 cái",
        "rate": 95000,
        "opening_rate": 70000,
    },
    {
        "item_code": "MYN-SYR-10",
        "item_name": "Bơm tiêm 10ml G21 – hộp 100 cái",
        "rate": 88000,
        "opening_rate": 65000,
    },
    {
        "item_code": "MYN-ALT",
        "item_name": "Hoá chất sinh hoá ALT (GPT) – hộp 4×50ml",
        "rate": 1250000,
        "opening_rate": 950000,
    },
]
STOCK_UOM = "Hộp"

BLANKET_ORDER_QTY = 500
OPENING_STOCK_QTY = 300

BLANKET_FROM_DATE = "2026-01-01"
BLANKET_TO_DATE = "2027-12-31"


def _ensure_uom(uom_name):
    if not frappe.db.exists("UOM", uom_name):
        frappe.get_doc({"doctype": "UOM", "uom_name": uom_name}).insert(ignore_permissions=True)
    return uom_name


def _ensure_item_group(group):
    if not frappe.db.exists("Item Group", group):
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": group,
                "parent_item_group": "All Item Groups",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    return group


def _ensure_warehouse():
    if not frappe.db.exists("Warehouse", WAREHOUSE_NAME):
        parent = frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 1}, "name")
        wh = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": WAREHOUSE_NAME,
                "company": COMPANY,
                "is_group": 0,
                "parent_warehouse": parent,
            }
        )
        wh.insert(ignore_permissions=True)
        return wh.name
    return WAREHOUSE_NAME


def _ensure_items(warehouse):
    _ensure_item_group(ITEM_GROUP)
    for uom in UOMS:
        _ensure_uom(uom)

    item_codes = []
    for it in ITEMS:
        if not frappe.db.exists("Item", it["item_code"]):
            item_doc = frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": it["item_code"],
                    "item_name": it["item_name"],
                    "item_group": ITEM_GROUP,
                    "stock_uom": STOCK_UOM,
                    "is_stock_item": 1,
                }
            )
            item_doc.append(
                "item_defaults", {"company": COMPANY, "default_warehouse": warehouse}
            )
            item_doc.insert(ignore_permissions=True)
        else:
            # Idempotent re-run: ensure the default warehouse is set for this company.
            item_doc = frappe.get_doc("Item", it["item_code"])
            if not any(d.company == COMPANY and d.default_warehouse for d in item_doc.item_defaults):
                item_doc.append(
                    "item_defaults", {"company": COMPANY, "default_warehouse": warehouse}
                )
                item_doc.save(ignore_permissions=True)
        item_codes.append(it["item_code"])
    return item_codes


def _ensure_price_list():
    if not frappe.db.exists("Price List", PRICE_LIST):
        frappe.get_doc(
            {
                "doctype": "Price List",
                "price_list_name": PRICE_LIST,
                "selling": 1,
                "currency": "VND",
            }
        ).insert(ignore_permissions=True)
    return PRICE_LIST


def _ensure_item_prices():
    for it in ITEMS:
        if not frappe.db.exists(
            "Item Price", {"item_code": it["item_code"], "price_list": PRICE_LIST, "selling": 1}
        ):
            frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": it["item_code"],
                    "price_list": PRICE_LIST,
                    "uom": STOCK_UOM,
                    "selling": 1,
                    "price_list_rate": it["rate"],
                    "currency": "VND",
                }
            ).insert(ignore_permissions=True)


def _ensure_customer():
    if not frappe.db.exists("Customer", CUSTOMER):
        frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": CUSTOMER,
                "customer_type": "Company",
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
                "tax_id": CUSTOMER_TAX_ID,
                "default_price_list": PRICE_LIST,
            }
        ).insert(ignore_permissions=True)
    else:
        # Idempotent re-run: make sure the default price list stays wired up.
        if frappe.db.get_value("Customer", CUSTOMER, "default_price_list") != PRICE_LIST:
            frappe.db.set_value("Customer", CUSTOMER, "default_price_list", PRICE_LIST)
    return CUSTOMER


def _ensure_address():
    address_name = f"{CUSTOMER}-Shipping"
    if not frappe.db.exists("Address", address_name):
        addr = frappe.new_doc("Address")
        addr.address_title = CUSTOMER
        addr.address_type = "Shipping"
        addr.address_line1 = CUSTOMER_ADDRESS_LINE1
        addr.city = "Hà Nội"
        addr.country = "Vietnam"
        addr.is_shipping_address = 1
        addr.append("links", {"link_doctype": "Customer", "link_name": CUSTOMER})
        addr.name = address_name
        addr.insert(ignore_permissions=True, set_name=address_name)
    return address_name


def _ensure_portal_user():
    if not frappe.db.exists("User", PORTAL_EMAIL):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": PORTAL_EMAIL,
                "first_name": CONTACT_FIRST_NAME,
                "send_welcome_email": 0,
                "user_type": "Website User",
                "new_password": PORTAL_PASSWORD,
            }
        )
        user.append("roles", {"role": "Customer"})
        user.insert(ignore_permissions=True)
    else:
        user = frappe.get_doc("User", PORTAL_EMAIL)
        if not any(r.role == "Customer" for r in user.roles):
            user.append("roles", {"role": "Customer"})
            user.save(ignore_permissions=True)
    return PORTAL_EMAIL


def _ensure_contact():
    contact_name = f"{CUSTOMER}-portal"
    if not frappe.db.exists("Contact", contact_name):
        ct = frappe.new_doc("Contact")
        ct.first_name = CONTACT_FIRST_NAME
        ct.user = PORTAL_EMAIL
        ct.append("email_ids", {"email_id": PORTAL_EMAIL, "is_primary": 1})
        ct.append("links", {"link_doctype": "Customer", "link_name": CUSTOMER})
        ct.name = contact_name
        ct.insert(ignore_permissions=True, set_name=contact_name)
    return contact_name


def _ensure_user_permission():
    if not frappe.db.exists(
        "User Permission", {"user": PORTAL_EMAIL, "allow": "Customer", "for_value": CUSTOMER}
    ):
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": PORTAL_EMAIL,
                "allow": "Customer",
                "for_value": CUSTOMER,
            }
        ).insert(ignore_permissions=True)


def _ensure_blanket_order():
    existing = frappe.db.get_value(
        "Blanket Order", {"customer": CUSTOMER, "blanket_order_type": "Selling"}, "name"
    )
    if not existing:
        bo = frappe.get_doc(
            {
                "doctype": "Blanket Order",
                "blanket_order_type": "Selling",
                "customer": CUSTOMER,
                "company": COMPANY,
                "from_date": BLANKET_FROM_DATE,
                "to_date": BLANKET_TO_DATE,
                "items": [
                    {
                        "item_code": it["item_code"],
                        "qty": BLANKET_ORDER_QTY,
                        "rate": it["rate"],
                    }
                    for it in ITEMS
                ],
            }
        )
        bo.insert(ignore_permissions=True)
        existing = bo.name

    # Idempotent: only submit while still a draft so re-running never re-submits.
    if frappe.db.get_value("Blanket Order", existing, "docstatus") == 0:
        frappe.get_doc("Blanket Order", existing).submit()

    return existing


def _current_stock(warehouse):
    return {
        it["item_code"]: frappe.db.get_value(
            "Bin", {"item_code": it["item_code"], "warehouse": warehouse}, "actual_qty"
        )
        or 0
        for it in ITEMS
    }


def _has_any_opening_stock(warehouse):
    """True if the warehouse already has stock recorded for these items.

    Guards the idempotent Material Receipt: only fire it while the warehouse
    has no stock yet for these items, per the UAT spec's literal wording.
    Deliberately does NOT re-top-up if stock is later consumed by the
    order-to-cash flow (e.g. deliveries) — this guard only prevents duplicate
    opening entries, it is not a "keep qty >= 300" invariant.
    """
    stock = _current_stock(warehouse)
    return any(qty for qty in stock.values())


def _ensure_opening_stock(warehouse):
    if _has_any_opening_stock(warehouse):
        return _current_stock(warehouse)

    se = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": COMPANY,
            "to_warehouse": warehouse,
            "items": [
                {
                    "item_code": it["item_code"],
                    "qty": OPENING_STOCK_QTY,
                    "t_warehouse": warehouse,
                    "basic_rate": it["opening_rate"],
                }
                for it in ITEMS
            ],
        }
    )
    se.insert(ignore_permissions=True)
    se.submit()

    return _current_stock(warehouse)


def setup_uat() -> dict:
    """Idempotently create/ensure the Miyano UAT scenario. Safe to call repeatedly.

    Creates: one warehouse, one item group + 2 UOMs, 3 stock items (with
    item_defaults pointing at the new warehouse), one customer with address /
    contact / portal (Website) user / user permission, one selling price list
    with item prices, one submitted Blanket Order (Selling) acting as the
    framework contract, and opening stock (submitted Material Receipt Stock
    Entry) for the 3 items in the new warehouse.
    """
    warehouse = _ensure_warehouse()
    item_codes = _ensure_items(warehouse)
    _ensure_price_list()
    _ensure_item_prices()

    customer = _ensure_customer()
    _ensure_address()
    portal_user = _ensure_portal_user()
    _ensure_contact()
    _ensure_user_permission()

    contract = _ensure_blanket_order()
    stock = _ensure_opening_stock(warehouse)

    return {
        "customer": customer,
        "portal_user": portal_user,
        "password": PORTAL_PASSWORD,
        "contract": contract,
        "warehouse": warehouse,
        "items": item_codes,
        "stock": stock,
    }
