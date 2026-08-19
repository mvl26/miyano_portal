import frappe

COMPANY = "Miyano Việt Nam"
COMPANY_ABBR = "MYN"
PRICE_LIST = "HĐNT-BVBM-2026"
DEMO_PASSWORD = "Portal@123"

ITEMS = [
    {
        "item_code": "VT0005",
        "item_name": "Găng tay khám nghiệm",
        "item_group": "Vật tư tiêu hao",
        "uom": "Cái",
        "rate": 1200,
    },
    {
        "item_code": "HC0009",
        "item_name": "Thuốc thử sinh hoá X",
        "item_group": "Hoá chất xét nghiệm",
        "uom": "Hộp",
        "rate": 350000,
    },
]

# `ma_ngan` — Task 7 (vòng sửa 19/08/2026): `ma_de_xuat.sinh_ma()` cần
# `Customer.custom_ma_ngan` để sinh mã đề xuất; thiếu nó không còn CHẶN đơn
# trực tiếp của quản lý (QĐ điều phối viên, xem `api/portal.py::
# portal_order_place`), nhưng khách demo vẫn nên MANG mã ngắn cho giống thật
# — nếu không, mọi phiếu tự duyệt sinh ra từ suite demo sẽ luôn có
# `ma_de_xuat` rỗng, che mất đúng nhánh "có mã" mà phần lớn khách thật sẽ đi.
CUSTOMERS = [
    {"name": "Bệnh viện Bạch Mai", "email": "bvbm@demo.miyano", "ma_ngan": "BVBM"},
    {"name": "PXN ABC", "email": "pxnabc@demo.miyano", "ma_ngan": "PXNABC"},
]

# Blanket Order (Selling) is seeded for the first customer only.
BLANKET_ORDER_QTY = {"VT0005": 10000, "HC0009": 500}
BLANKET_ORDER_FROM_DATE = "2026-01-01"
# NOT a module-level constant: portal_contracts() (api/portal.py) filters
# Blanket Order by `to_date >= today`, so a fixed date rots the instant
# "today" passes it, going red across setUp() in three test modules and
# three assertions in test_portal_read.py. Computed at call time, relative
# to today, so it can never rot again. (Evaluating frappe.utils.today() at
# import time would also be unsafe outside an active site context.)


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


def _ensure_company():
    if not frappe.db.exists("Company", COMPANY):
        frappe.get_doc(
            {
                "doctype": "Company",
                "company_name": COMPANY,
                "abbr": COMPANY_ABBR,
                "default_currency": "VND",
                "country": "Vietnam",
            }
        ).insert(ignore_permissions=True)
    return COMPANY


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


def _default_warehouse():
    """Leaf (non-group) warehouse for the demo company, used as each item's default."""
    return frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0, "warehouse_name": "Stores"})


def _ensure_items():
    item_codes = []
    warehouse = _default_warehouse()
    for it in ITEMS:
        _ensure_uom(it["uom"])
        _ensure_item_group(it["item_group"])

        if not frappe.db.exists("Item", it["item_code"]):
            item_doc = frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": it["item_code"],
                    "item_name": it["item_name"],
                    "item_group": it["item_group"],
                    "stock_uom": it["uom"],
                    "is_stock_item": 1,
                }
            )
            if warehouse:
                item_doc.append(
                    "item_defaults", {"company": COMPANY, "default_warehouse": warehouse}
                )
            item_doc.insert(ignore_permissions=True)
        elif warehouse:
            # Idempotent re-run: make sure the default warehouse is set for existing items.
            item_doc = frappe.get_doc("Item", it["item_code"])
            if not any(d.company == COMPANY and d.default_warehouse for d in item_doc.item_defaults):
                item_doc.append(
                    "item_defaults", {"company": COMPANY, "default_warehouse": warehouse}
                )
                item_doc.save(ignore_permissions=True)
        item_codes.append(it["item_code"])

        if not frappe.db.exists(
            "Item Price", {"item_code": it["item_code"], "price_list": PRICE_LIST, "selling": 1}
        ):
            frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": it["item_code"],
                    "price_list": PRICE_LIST,
                    "uom": it["uom"],
                    "selling": 1,
                    "price_list_rate": it["rate"],
                    "currency": "VND",
                }
            ).insert(ignore_permissions=True)
    return item_codes


def _ensure_customer(cust, ma_ngan=None):
    if not frappe.db.exists("Customer", cust):
        frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": cust,
                "customer_type": "Company",
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
                "default_price_list": PRICE_LIST,
            }
        ).insert(ignore_permissions=True)
    if ma_ngan:
        frappe.db.set_value("Customer", cust, "custom_ma_ngan", ma_ngan)
    return cust


def _ensure_portal_user(cust, email):
    if not frappe.db.exists("User", email):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": cust,
                "send_welcome_email": 0,
                "user_type": "Website User",
                "new_password": DEMO_PASSWORD,
            }
        )
        user.append("roles", {"role": "Customer"})
        user.insert(ignore_permissions=True)
    else:
        # Idempotent re-run: make sure the Customer role is still present.
        user = frappe.get_doc("User", email)
        if not any(r.role == "Customer" for r in user.roles):
            user.append("roles", {"role": "Customer"})
            user.save(ignore_permissions=True)
    return email


def _ensure_contact(cust, email):
    contact_name = f"{cust}-portal"
    if not frappe.db.exists("Contact", contact_name):
        ct = frappe.new_doc("Contact")
        ct.first_name = cust
        ct.user = email
        ct.append("email_ids", {"email_id": email, "is_primary": 1})
        ct.append("links", {"link_doctype": "Customer", "link_name": cust})
        ct.name = contact_name
        ct.insert(ignore_permissions=True, set_name=contact_name)
    return contact_name


def _ensure_portal_member(cust, email):
    """Bản ghi `Portal Member` cho tài khoản cổng demo.

    VÒNG SỬA 3 (F5, review độc lập, Critical): trước bản sửa này,
    `_ensure_portal_user` dừng lại ở `User`/`Contact`/`User Permission`,
    không tạo `Portal Member` — trong khi `demo_kho_flow.py::_ensure_portal_user`
    lại đi qua `portal_provision` (từ vòng sửa 2, giờ CÓ tạo `Portal
    Member`). Hai đường gieo dữ liệu demo khác nhau là đúng hình hai-nguồn-
    sự-thật mà cả Task 5 tồn tại để dẹp: trên site MỚI (DB rỗng, ví dụ CI),
    patch backfill chèn 0 dòng vì chưa có `Contact` nào để đọc, rồi
    `seed_demo()` sinh ra các tài khoản cổng KHÔNG có `Portal Member` —
    danh tính chết ngay từ lúc seed, không phải lỗi test.

    Không gọi thẳng `portal_provision` ở đây (khác với `demo_kho_flow.py`)
    vì nó còn tạo `Contact` theo tên khác (`{customer}-{email}` thay vì
    `{cust}-portal` mà `_ensure_contact` dùng) — giữ nguyên các hàm `_ensure_*`
    hiện có, chỉ thêm đúng phần còn thiếu: `Portal Member`. Luôn tạo dạng
    `Quản lý`/`active=1` — mỗi khách demo trong `CUSTOMERS` chỉ có đúng một
    tài khoản cổng nên không có ai để `_chan_hai_quan_ly` chặn. Đi qua
    `doc.insert()`, không `db_set`/`frappe.db.set_value()` (giới hạn đã biết
    của `_chan_hai_quan_ly`, xem `portal_member.py`)."""
    if frappe.db.exists("Portal Member", {"user": email}):
        return
    frappe.get_doc({
        "doctype": "Portal Member", "user": email, "customer": cust,
        "vai_tro": "Quản lý", "active": 1,
    }).insert(ignore_permissions=True)


def _ensure_user_permission(email, cust):
    if not frappe.db.exists(
        "User Permission", {"user": email, "allow": "Customer", "for_value": cust}
    ):
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": email,
                "allow": "Customer",
                "for_value": cust,
            }
        ).insert(ignore_permissions=True)


def _ensure_address(cust):
    address_name = f"{cust}-Billing"
    if not frappe.db.exists("Address", address_name):
        addr = frappe.new_doc("Address")
        addr.address_title = cust
        addr.address_type = "Billing"
        addr.address_line1 = "Demo address"
        addr.city = "Hà Nội"
        addr.country = "Vietnam"
        addr.append("links", {"link_doctype": "Customer", "link_name": cust})
        addr.name = address_name
        addr.insert(ignore_permissions=True, set_name=address_name)
    return address_name


def _ensure_blanket_order(customer):
    existing = frappe.db.get_value(
        "Blanket Order", {"customer": customer, "blanket_order_type": "Selling"}, "name"
    )
    if not existing:
        bo = frappe.get_doc(
            {
                "doctype": "Blanket Order",
                "blanket_order_type": "Selling",
                "customer": customer,
                "company": COMPANY,
                "from_date": BLANKET_ORDER_FROM_DATE,
                "to_date": frappe.utils.add_months(frappe.utils.today(), 12),
                "items": [
                    {"item_code": code, "qty": qty, "rate": next(i["rate"] for i in ITEMS if i["item_code"] == code)}
                    for code, qty in BLANKET_ORDER_QTY.items()
                ],
            }
        )
        bo.insert(ignore_permissions=True)
        existing = bo.name

    # Idempotent: only submit while still a draft, so re-running seed_demo()
    # never re-submits an already-submitted (or cancelled) document.
    if frappe.db.get_value("Blanket Order", existing, "docstatus") == 0:
        frappe.get_doc("Blanket Order", existing).submit()

    return existing


def _ensure_party_specific_items(customer):
    for it in ITEMS:
        if not frappe.db.exists(
            "Party Specific Item",
            {
                "party_type": "Customer",
                "party": customer,
                "restrict_based_on": "Item",
                "based_on_value": it["item_code"],
            },
        ):
            frappe.get_doc(
                {
                    "doctype": "Party Specific Item",
                    "party_type": "Customer",
                    "party": customer,
                    "restrict_based_on": "Item",
                    "based_on_value": it["item_code"],
                }
            ).insert(ignore_permissions=True)


def seed_demo() -> dict:
    """Idempotently create/ensure Miyano demo data. Safe to call repeatedly."""
    _ensure_company()
    _ensure_price_list()
    item_codes = _ensure_items()

    customers = []
    users = []
    for c in CUSTOMERS:
        cust = _ensure_customer(c["name"], c.get("ma_ngan"))
        customers.append(cust)
        _ensure_address(cust)
        users.append(_ensure_portal_user(cust, c["email"]))
        _ensure_contact(cust, c["email"])
        _ensure_user_permission(c["email"], cust)
        _ensure_portal_member(cust, c["email"])

    # Blanket Order + Party Specific Item restriction for the first demo customer.
    bo_customer = CUSTOMERS[0]["name"]
    blanket_orders = [_ensure_blanket_order(bo_customer)]
    _ensure_party_specific_items(bo_customer)

    return {
        "customers": customers,
        "items": item_codes,
        "blanket_orders": blanket_orders,
        "users": users,
    }
