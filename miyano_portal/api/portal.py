import frappe
from miyano_portal.portal_context import get_portal_customer, han_muc_con
from miyano_portal.portal_dat_hang import (
    kiem_boi_so,
    kiem_ngay_giao,
    ngay_giao_mac_dinh,
)
from miyano_portal.portal_thong_bao import bao_thieu_gia


def _gia_hien_hanh(item_code: str, price_list: str):
    """Đơn giá bán hiện hành của một mặt hàng trong bảng giá của hợp đồng.

    Tách ra để vòng gom lỗi và vòng dựng đơn dùng CHUNG một phép tra: hai chỗ
    tra riêng là hai chỗ có thể lệch nhau khi một bên được sửa.

    Nợ đã biết, cố ý giữ nguyên hành vi cũ ở lần tách này: chưa lọc
    `valid_from`/`valid_upto`, nhiều bản ghi thì lấy tuỳ ý.
    """
    return frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": 1},
        "price_list_rate",
    )


def _customer_addresses(customer: str) -> list:
    """Addresses linked to this Customer via Dynamic Link.

    Returns [{name, display}] where display is a human-readable one-line
    address. Scoped strictly to the caller's customer.
    """
    parents = frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Address",
            "link_doctype": "Customer",
            "link_name": customer,
        },
        pluck="parent",
    )
    if not parents:
        return []
    rows = frappe.get_all(
        "Address",
        filters={"name": ["in", list(dict.fromkeys(parents))]},
        fields=["name", "address_title", "address_line1", "address_line2", "city"],
        order_by="creation asc",
    )
    out = []
    for a in rows:
        parts = [a.get("address_line1"), a.get("address_line2"), a.get("city")]
        display = ", ".join(p for p in parts if p)
        if a.get("address_title") and display:
            display = f"{a['address_title']} – {display}"
        elif a.get("address_title"):
            display = a["address_title"]
        out.append({"name": a["name"], "display": display or a["name"]})
    return out


def _resolve_company_fallback_warehouse(company: str):
    """Resolve a leaf Warehouse for `company` to use ONLY when an item has no
    warehouse of its own to ship from (see _resolve_item_warehouse below).

    This must never be forced onto every line of a Sales Order: items whose
    stock actually lives in a different warehouse (e.g. UAT items stocked in
    "Kho Miyano - MYN") would otherwise get a delivery warehouse where they
    have no stock, and the Delivery Note would raise NegativeStockError.
    """
    warehouse = None
    # This build's Company doctype may not carry a default_warehouse field
    # at all (custom fixtures vary by environment), so probe via the meta
    # before querying it - a bare frappe.db.get_value on a nonexistent
    # column raises OperationalError instead of returning None.
    if frappe.get_meta("Company").has_field("default_warehouse"):
        warehouse = frappe.db.get_value("Company", company, "default_warehouse")
    if not warehouse:
        abbr = frappe.db.get_value("Company", company, "abbr")
        candidates = frappe.get_all(
            "Warehouse",
            filters={"company": company, "is_group": 0, "disabled": 0},
            pluck="name",
        )
        preferred = f"Stores - {abbr}" if abbr else None
        if preferred and preferred in candidates:
            warehouse = preferred
        elif candidates:
            warehouse = candidates[0]
    return warehouse


def _resolve_item_warehouse(item_code: str, company: str):
    """Resolve the delivery warehouse for ONE Sales Order line.

    Each item ships from wherever its own stock actually lives, not from a
    single warehouse forced onto the whole order. Preference order:
      1. The item's own "Item Default" row for this company
         (Item Default.default_warehouse) - this is where the item's stock
         actually sits (e.g. UAT items in "Kho Miyano - MYN").
      2. The company's default warehouse, for items with no company-specific
         default of their own (e.g. some SupplyCore-migrated items).
      3. Any leaf, non-disabled Warehouse belonging to the company, as a last
         resort so a missing default doesn't block order placement outright.
    Returns None if nothing at all can be resolved - the caller must refuse
    to create the Sales Order line in that case rather than leave/guess a
    warehouse.
    """
    warehouse = frappe.db.get_value(
        "Item Default",
        {"parent": item_code, "parenttype": "Item", "company": company},
        "default_warehouse",
    )
    if warehouse:
        return warehouse
    return _resolve_company_fallback_warehouse(company)


def _get_outstanding(customer: str) -> float:
    """Sum of unpaid GL Entry balance for this customer across companies.

    Customer.outstanding_amount is not a real field/column in this build,
    so compute it directly from GL Entry instead of frappe.db.get_value.
    """
    total = frappe.db.sql(
        """select sum(debit_in_account_currency) - sum(credit_in_account_currency)
           from `tabGL Entry`
           where party_type='Customer' and party=%s and is_cancelled=0""",
        customer,
    )[0][0]
    return float(total or 0)


@frappe.whitelist()
def portal_me() -> dict:
    customer = get_portal_customer()
    cust = frappe.db.get_value(
        "Customer", customer, ["customer_name", "tax_id"], as_dict=True
    ) or {}
    return {
        "customer": customer,
        "customer_name": cust.get("customer_name"),
        "tax_id": cust.get("tax_id"),
        "outstanding": _get_outstanding(customer),
        "addresses": _customer_addresses(customer),
    }


@frappe.whitelist()
def portal_contracts() -> list:
    customer = get_portal_customer()
    today = frappe.utils.today()
    rows = frappe.get_all(
        "Blanket Order",
        filters={
            "customer": customer,
            "blanket_order_type": "Selling",
            "to_date": [">=", today],
        },
        fields=["name", "from_date", "to_date"],
        order_by="to_date asc",
    )
    for r in rows:
        # `qty > 0` là điểm mấu chốt (BR-O15): dòng khai 0 = KHÔNG GIỚI HẠN
        # nên không có mẫu số. Để nó vào thì % ra một con số vô nghĩa và cảnh
        # báo "đã dùng ≥ 80% hạn mức" sẽ báo động sai.
        agg = frappe.db.sql(
            """select sum(qty) q, sum(ordered_qty) o
               from `tabBlanket Order Item` where parent=%s and qty > 0""",
            r["name"],
        )[0]
        total, ordered = float(agg[0] or 0), float(agg[1] or 0)
        r["used_pct"] = round(ordered / total * 100, 1) if total else 0
        # Số mặt hàng vẫn đếm ĐỦ, kể cả dòng không giới hạn — khách vẫn đặt
        # được chúng, chỉ là không có trần.
        r["item_count"] = frappe.db.count("Blanket Order Item", {"parent": r["name"]})
    return rows


@frappe.whitelist()
def portal_catalog(contract: str) -> list:
    customer = get_portal_customer()
    # isolation: the contract must belong to the caller's customer
    if frappe.db.get_value("Blanket Order", contract, "customer") != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    out = []
    for row in frappe.get_all(
        "Blanket Order Item",
        filters={"parent": contract},
        fields=["item_code", "rate", "qty", "ordered_qty"],
    ):
        item = frappe.db.get_value(
            "Item", row["item_code"], ["item_name", "stock_uom", "item_group"], as_dict=True
        )
        rate = frappe.db.get_value(
            "Item Price",
            {"item_code": row["item_code"], "price_list": price_list, "selling": 1},
            "price_list_rate",
        ) or row["rate"]
        con_lai, da_dat = han_muc_con(contract, row["item_code"])
        out.append({
            "item_code": row["item_code"],
            "item_name": item.item_name if item else row["item_code"],
            "uom": item.stock_uom if item else "",
            "item_group": (item.item_group if item else "") or "",
            "rate": float(rate),
            "vat_pct": 0,
            "total": float(row["qty"] or 0),
            "used": da_dat,
            # `None` chứ không phải 0: giao diện phải phân biệt "không giới
            # hạn" (NL-1.11) với "hết hạn mức" (NL-1.2) — bản cũ trả
            # `max(total - used, 0.0)` nên hai trạng thái này trông y hệt
            # nhau, và mặt hàng khai 0 hiện ra là "Hết hạn mức".
            "remaining": None if con_lai is None else max(con_lai, 0.0),
            "khong_gioi_han": con_lai is None,
            "boi_so_dat": int(
                frappe.db.get_value("Item", row["item_code"], "custom_boi_so_dat") or 0
            ),
        })
    return out


@frappe.whitelist()
def portal_order_place(
    contract, items, po=None, delivery_date=None, note=None, address=None,
    request_id=None,
) -> dict:
    customer = get_portal_customer()

    # BR-O12 — chống tạo đơn trùng. Bắt buộc, không tuỳ chọn: để tuỳ chọn thì
    # một client cũ vẫn tạo được đơn trùng và quy tắc chỉ còn là trang trí.
    if not request_id:
        frappe.throw(
            "Thiếu mã yêu cầu đặt hàng. Tải lại trang rồi thử lại.",
            frappe.ValidationError,
        )
    # Trả lại đơn cũ TRƯỚC khi làm bất cứ việc gì khác — người dùng bấm lại vì
    # lần trước có vẻ hỏng, không phải vì muốn đặt thêm một đơn nữa.
    da_co = frappe.db.get_value(
        "Sales Order",
        {"custom_request_id": request_id},
        ["name", "customer", "grand_total"],
        as_dict=True,
    )
    if da_co:
        if da_co.customer != customer:
            # Mã yêu cầu của khách khác: không xác nhận cả sự tồn tại của nó.
            raise frappe.PermissionError("Mã yêu cầu không hợp lệ.")
        return {
            "sales_order": da_co.name,
            "da_ton_tai": True,
            "total": float(da_co.grand_total or 0),
        }

    bo = frappe.db.get_value(
        "Blanket Order", contract, ["customer", "company"], as_dict=True
    )
    if not bo or bo.customer != customer:
        raise frappe.PermissionError("Hợp đồng không thuộc đơn vị của bạn.")

    # Validate the optional shipping address actually belongs to this customer
    # (isolation) before it is written onto the Sales Order.
    if address:
        allowed = {a["name"] for a in _customer_addresses(customer)}
        if address not in allowed:
            raise frappe.PermissionError("Địa chỉ giao hàng không thuộc đơn vị của bạn.")
    if isinstance(items, str):
        items = frappe.parse_json(items)
    if not items:
        frappe.throw("Giỏ hàng trống.")

    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    # BR-O13 — mặc định +2 NGÀY LÀM VIỆC (bỏ T7/CN), không phải +2 ngày lịch.
    delivery_date = delivery_date or ngay_giao_mac_dinh()

    # Aggregate the incoming cart by item_code so duplicate lines for the same
    # item can't each pass the quota check individually while together
    # exceeding the remaining quota (duplicate-line quota bypass).
    aggregated = {}
    for line in items:
        qty = float(line.get("qty") or 0)
        item_code = line.get("item_code")
        aggregated[item_code] = aggregated.get(item_code, 0) + qty

    # BR-O3 — báo HẾT trong một lần. `loi` là phong bì máy đọc được theo
    # `30_API_Spec` §1.1 (`ly_do` + số liệu kèm theo); văn xuôi cho `frappe.throw`
    # dựng từ chính `thong_diep` của các mục này, nên hai đường không thể lệch
    # nội dung nhau.
    loi: list[dict] = []
    loi_ngay = kiem_ngay_giao(delivery_date)
    if loi_ngay:
        loi.append(loi_ngay)

    gia: dict[str, float] = {}
    khong_gioi_han = set()
    for item_code, qty in aggregated.items():
        if qty <= 0:
            loi.append({
                "item_code": item_code,
                "ly_do": "so_luong_khong_hop_le",
                "thong_diep": f"{item_code}: số lượng phải > 0",
            })
            continue
        # Mỗi mặt hàng chỉ báo MỘT lý do, xét theo thứ tự này:
        #   bội số  — lỗi nhập liệu, khách sửa được ngay; và kiểm hạn mức trên
        #             một số lượng sai bội số cho ra `con_lai` gây hiểu nhầm;
        #   giá     — bế tắc tuyệt đối, giảm số lượng không cứu được;
        #   hạn mức — xét sau cùng, khi số lượng đã hợp lệ và hàng đã có giá.
        loi_boi_so = kiem_boi_so(item_code, qty)
        if loi_boi_so:
            loi.append(loi_boi_so)
            continue
        # US-E1.4 — kiểm giá phải nằm TRONG vòng gom này. Bản trước ném ngay ở
        # mặt hàng thiếu giá đầu tiên tại vòng dựng đơn phía dưới, nên giỏ vừa
        # vượt hạn mức vừa thiếu giá bắt khách gửi hai lần — đúng thứ BR-O3 cấm.
        rate = _gia_hien_hanh(item_code, price_list)
        if not rate:
            # Khách không phải tự đi đòi giá. Báo sales phụ trách ngay, tối đa
            # một lần mỗi ngày cho mỗi cặp (khách, mặt hàng).
            bao_thieu_gia(customer, item_code)
            loi.append({
                "item_code": item_code,
                "ly_do": "thieu_gia",
                # Nguyên văn ma trận FormSpec §5, dòng NL-1.4.
                "thong_diep": (
                    f"{item_code} chưa có giá trong hợp đồng. "
                    f"Miyano đã nhận được thông báo để bổ sung."
                ),
            })
            continue
        gia[item_code] = rate
        con_lai, _da_dat = han_muc_con(contract, item_code)
        if con_lai is None:
            # BR-O15 — hạn mức khai 0 = KHÔNG GIỚI HẠN. Không kiểm, và ghi
            # nhớ để lát nữa KHÔNG gắn against_blanket_order cho dòng này.
            khong_gioi_han.add(item_code)
            continue
        if qty > con_lai:
            loi.append({
                "item_code": item_code,
                # §5 tách hai mã: hết sạch là `het_han_muc`, còn ít hơn số
                # khách đòi là `vuot_han_muc` — giao diện xử lý khác nhau.
                "ly_do": "het_han_muc" if con_lai <= 0 else "vuot_han_muc",
                "con_lai": con_lai,
                # Nguyên văn ma trận FormSpec §5, dòng NL-1.3.
                "thong_diep": (
                    f"Không đặt được: {item_code} chỉ còn {con_lai:g} "
                    f"theo hạn mức HĐNT."
                ),
            })
    if loi:
        # `report_error` không xoá `frappe.local.response` và `as_json`
        # serialize cả dict, nên khoá này về tới client cùng với HTTP 417.
        frappe.local.response["loi"] = loi
        frappe.throw(
            "<br>".join(d["thong_diep"] for d in loi), frappe.ValidationError
        )
    # Lần gọi trước trong cùng request có thể đã để lại `loi`; sót lại thì giao
    # diện báo lỗi trên một đơn vừa tạo thành công.
    frappe.local.response.pop("loi", None)

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = bo.company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = delivery_date
    so.selling_price_list = price_list
    so.custom_nguon_don = "Client Portal"
    so.custom_hdnt = contract
    so.custom_request_id = request_id
    so.custom_so_po_khach = po
    so.custom_yeu_cau_khach = note
    if address:
        so.shipping_address_name = address
        so.customer_address = address
    # Set the contact so the "Portal - Đơn mới" Notification (recipient
    # field contact_email) actually has an email to send to. The portal
    # user's email == frappe.session.user == the linked Contact's email.
    contact_name = frappe.db.get_value("Contact", {"user": frappe.session.user})
    if contact_name:
        so.contact_person = contact_name
        so.contact_email = frappe.session.user
    for item_code, qty in aggregated.items():
        # Giá đã tra ở vòng gom lỗi phía trên — tới đây mọi mặt hàng còn lại
        # chắc chắn có giá, vì thiếu giá đã thành một mục trong `loi`.
        rate = gia[item_code]
        # Ship each line from THIS item's own default warehouse (where its
        # stock actually is), never a single warehouse forced onto the whole
        # order - otherwise items stocked elsewhere (e.g. UAT items in "Kho
        # Miyano - MYN") end up shipping from an empty warehouse and the
        # Delivery Note raises NegativeStockError.
        item_warehouse = _resolve_item_warehouse(item_code, so.company)
        if not item_warehouse:
            frappe.throw(
                f"Không tìm thấy kho giao hàng cho mặt hàng {item_code} tại "
                f"công ty {so.company}. Vui lòng liên hệ quản trị viên hệ thống."
            )
        dong = {
            "item_code": item_code,
            "qty": qty,
            "rate": rate,
            "warehouse": item_warehouse,
            "delivery_date": delivery_date,
        }
        if item_code not in khong_gioi_han:
            dong["blanket_order"] = contract
            dong["against_blanket_order"] = 1
        # Dòng KHÔNG GIỚI HẠN cố ý bỏ hai khoá trên (BR-O15): cơ chế gốc của
        # ERPNext đối chiếu `against_blanket_order` với `qty` của Blanket
        # Order Item, thấy 0 thì hiểu là CẤM ĐẶT và chặn ngay lúc submit.
        # Truy vết về hợp đồng vẫn còn qua `so.custom_hdnt` ở đầu đơn.
        so.append("items", dong)
    so.flags.ignore_permissions = True
    try:
        so.insert(ignore_permissions=True)
    except frappe.UniqueValidationError:
        # Đua: một tiến trình khác vừa ghi xong cùng mã yêu cầu, giữa lúc ta
        # kiểm ở đầu hàm và lúc ta ghi. Ràng buộc `unique` của CSDL mới là
        # trọng tài thật — phép kiểm ở đầu hàm chỉ là đường tắt cho trường
        # hợp thường gặp.
        #
        # `UniqueValidationError` chứ KHÔNG phải `DuplicateEntryError`:
        # `Document.insert` map lỗi 1062 của MariaDB thành cái trước
        # (`base_document.py:672`); `DuplicateEntryError` dành cho trùng
        # `name`. Bắt nhầm loại thì nhánh này không bao giờ chạy và tình
        # huống đua hiện ra thành lỗi 500 cho khách.
        cu = frappe.db.get_value(
            "Sales Order",
            {"custom_request_id": request_id},
            ["name", "grand_total"],
            as_dict=True,
        )
        if not cu:
            # Một trường unique KHÁC trên Sales Order bị vi phạm, không phải
            # mã yêu cầu của ta. Nuốt nó ở đây sẽ biến một lỗi dữ liệu thật
            # thành "đơn đã tồn tại" — sai và rất khó truy.
            raise
        return {
            "sales_order": cu.name,
            "da_ton_tai": True,
            "total": float(cu.grand_total or 0),
        }
    return {"sales_order": so.name, "da_ton_tai": False, "total": float(so.grand_total)}


def _so_status_vi(so_status, per_delivered=None):
    """Vietnamese label for a Sales Order, delivery-aware.

    Per the BA doc the progression is:
      Chờ xác nhận -> Đang xử lý -> Đang giao -> Hoàn thành
    Raw ERPNext status alone conflates "Đang xử lý" and "Đang giao": both
    "To Deliver and Bill" and "To Bill" can appear while a delivery has
    already started (per_delivered > 0). So once delivery has started but
    the order isn't Completed/Cancelled/Closed, show "Đang giao" regardless
    of the raw status string.
    """
    if so_status == "Completed":
        return "Hoàn thành"
    if so_status in ("Cancelled", "Closed"):
        return "Đã huỷ"
    if float(per_delivered or 0) > 0:
        return "Đang giao"
    if so_status == "Draft":
        return "Chờ xác nhận"
    # To Deliver and Bill / To Bill / To Deliver, all with 0 delivered so far.
    return "Đang xử lý"


# Sales Invoice uses a different status vocabulary than Sales Order, so it needs
# its own Vietnamese map (a "Draft" invoice must not read "Chờ xác nhận").
INVOICE_STATUS_VI = {
    "Draft": "Nháp",
    "Unpaid": "Chưa thanh toán",
    "Unpaid and Discounted": "Chưa thanh toán",
    "Partly Paid": "TT một phần",
    "Partially Paid": "TT một phần",
    "Partly Paid and Discounted": "TT một phần",
    "Paid": "Đã thanh toán",
    "Overdue": "Quá hạn",
    "Overdue and Discounted": "Quá hạn",
    "Return": "Trả hàng",
    "Credit Note Issued": "Đã phát hành giấy báo có",
    "Submitted": "Đã ghi sổ",
    "Cancelled": "Đã huỷ",
}


def _invoice_status_vi(status):
    return INVOICE_STATUS_VI.get(status, status)


@frappe.whitelist()
def portal_order_history(limit=20, start=0) -> list:
    rows = frappe.get_list(
        "Sales Order",
        fields=["name", "transaction_date", "grand_total", "status", "per_delivered"],
        order_by="transaction_date desc, creation desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _so_status_vi(r.pop("status"), r.get("per_delivered"))
    return rows


@frappe.whitelist()
def portal_order_track(order) -> dict:
    so = frappe.get_doc("Sales Order", order)
    # frappe.get_doc does not auto-check permissions on load; check_permission()
    # is what actually invokes the has_permission hook (Task 5) that scopes
    # this to the caller's own customer.
    so.check_permission("read")
    delivered = (so.per_delivered or 0) > 0
    billed = (so.per_billed or 0) > 0
    # "Soạn hàng" (order-preparation): done once the goods have been picked
    # for this SO (a Pick List exists) or delivery has already started.
    preparing_done = bool(frappe.db.exists("Pick List Item", {"sales_order": order})) or delivered
    milestones = [
        {"key": "ordered", "label": "Đặt hàng", "done": True},
        {"key": "confirmed", "label": "Xác nhận", "done": so.docstatus == 1},
        {"key": "preparing", "label": "Soạn hàng", "done": preparing_done},
        {"key": "delivering", "label": "Giao hàng", "done": delivered},
        {"key": "invoiced", "label": "Hoá đơn", "done": billed},
    ]

    # Delivery Notes fulfilling this Sales Order. Delivery Note Item carries
    # against_sales_order; distinct parents give the batches ("đợt giao"). The
    # SO was already permission-checked above, so its own DNs are in scope.
    total_qty = sum(float(i.qty or 0) for i in so.items) or 0
    dn_names = frappe.get_all(
        "Delivery Note Item",
        filters={"against_sales_order": so.name, "docstatus": ["<", 2]},
        pluck="parent",
    )
    deliveries = []
    for dn_name in list(dict.fromkeys(dn_names)):
        dn = frappe.db.get_value(
            "Delivery Note", dn_name,
            ["name", "posting_date", "status", "lr_no", "transporter_name"],
            as_dict=True,
        )
        if not dn:
            continue
        dn_qty = frappe.db.sql(
            """select sum(qty) from `tabDelivery Note Item`
               where parent=%s and against_sales_order=%s""",
            (dn_name, so.name),
        )[0][0]
        pct = round(float(dn_qty or 0) / total_qty * 100, 1) if total_qty else 0
        deliveries.append({
            "name": dn["name"],
            "posting_date": dn.get("posting_date"),
            "status": dn.get("status"),
            "percent": pct,
            "carrier": dn.get("transporter_name") or "",
            "awb": dn.get("lr_no") or "",
        })

    return {
        "order": so.name,
        "status_vi": _so_status_vi(so.status, so.per_delivered),
        "order_date": so.transaction_date,
        "po_khach": so.get("custom_so_po_khach") or "",
        "hdnt": so.get("custom_hdnt") or "",
        # US-E2.2 — khách phải đọc được lý do ngay trên chi tiết đơn, không
        # phải đi tìm lại email.
        "ly_do_tu_choi": so.get("custom_ly_do_tu_choi") or "",
        "milestones": milestones,
        "items": [
            {"item_code": i.item_code,
             "item_name": i.item_name or frappe.db.get_value("Item", i.item_code, "item_name"),
             "qty": i.qty, "delivered_qty": i.delivered_qty,
             "rate": float(i.rate or 0), "uom": i.uom, "amount": float(i.amount or 0)}
            for i in so.items
        ],
        "deliveries": deliveries,
    }


@frappe.whitelist()
def portal_deliveries(limit=20, start=0) -> list:
    return frappe.get_list(
        "Delivery Note",
        fields=["name", "posting_date", "status"],
        order_by="posting_date desc",
        limit_page_length=int(limit), limit_start=int(start),
    )


@frappe.whitelist()
def portal_invoices(limit=20, start=0) -> list:
    rows = frappe.get_list(
        "Sales Invoice",
        fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "status"],
        order_by="posting_date desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _invoice_status_vi(r.pop("status"))
    return rows


@frappe.whitelist()
def portal_request_cancel(order, reason) -> dict:
    so = frappe.get_doc("Sales Order", order)
    so.check_permission("read")
    if so.docstatus != 0:
        frappe.throw("Chỉ yêu cầu huỷ được khi đơn còn Chờ xác nhận.")
    so.add_comment("Comment", f"[Portal] Khách yêu cầu huỷ: {reason}")
    frappe.get_doc({
        "doctype": "ToDo", "description": f"Khách yêu cầu huỷ {order}: {reason}",
        "reference_type": "Sales Order", "reference_name": order,
    }).insert(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist()
def portal_provision(customer, email, send_invite=False) -> dict:
    # Caller-role guard: only staff (not portal customers) may provision accounts.
    if not (set(frappe.get_roles()) & {"System Manager", "Sales Manager", "Sales User"}):
        frappe.throw("Không có quyền", frappe.PermissionError)

    if not frappe.db.exists("Customer", customer):
        frappe.throw("Không tìm thấy khách hàng.")
    if not frappe.db.exists("User", email):
        u = frappe.get_doc({
            "doctype": "User", "email": email, "first_name": customer,
            "user_type": "Website User", "send_welcome_email": int(send_invite),
        })
        u.append("roles", {"role": "Customer"})
        u.insert(ignore_permissions=True)
    contact_name = f"{customer}-{email}"
    if not frappe.db.exists("Contact", contact_name):
        ct = frappe.get_doc({"doctype": "Contact", "first_name": customer, "user": email})
        ct.name = contact_name
        ct.append("email_ids", {"email_id": email, "is_primary": 1})
        ct.append("links", {"link_doctype": "Customer", "link_name": customer})
        ct.insert(ignore_permissions=True)
    if not frappe.db.exists("User Permission", {"user": email, "allow": "Customer", "for_value": customer}):
        frappe.get_doc({
            "doctype": "User Permission", "user": email,
            "allow": "Customer", "for_value": customer,
        }).insert(ignore_permissions=True)
    return {"user": email}


@frappe.whitelist()
def portal_document_download(doctype, name) -> None:
    if doctype not in ("Sales Order", "Delivery Note", "Sales Invoice"):
        frappe.throw("Loại chứng từ không hợp lệ.")
    doc = frappe.get_doc(doctype, name)
    # frappe.get_doc does NOT auto-enforce has_permission in this build, so the
    # isolation check must be done explicitly before any data leaves the server.
    doc.check_permission("read")
    from frappe.utils.pdf import get_pdf
    from frappe.www.printview import get_html_and_style
    # Each doctype renders through its installed bilingual Miyano print
    # format (see setup/install_print_formats.py).
    PRINT_FORMATS = {
        "Sales Order": "Miyano - Xác nhận đơn hàng",
        "Delivery Note": "Miyano - Phiếu giao hàng",
        "Sales Invoice": "Miyano - Hoá đơn",
    }
    print_format = PRINT_FORMATS.get(doctype)
    html = get_html_and_style(
        doc=doc.as_json(), print_format=print_format, no_letterhead=0
    )["html"]
    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def portal_reorder(order: str) -> dict:
    """UC-14 / US-E1.5 — điền lại giỏ theo một đơn cũ, theo GIÁ HIỆN HÀNH.

    Dòng nào không còn đặt được thì vào `bi_loai` kèm mã lý do để giao diện
    dịch sang thông điệp FormSpec §5. Im lặng bỏ bớt dòng là cách chắc chắn
    khiến khách đặt thiếu hàng mà không biết.

    Dòng còn đặt được một phần thì HẠ số lượng xuống phần còn lại chứ không
    loại cả dòng — còn 1 mà đơn cũ đặt 3 thì khách vẫn nên đặt được 1.
    """
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG chạy hook `has_permission` ở build này — phải
    # kiểm tường minh trước khi đọc bất cứ thứ gì của tài liệu.
    so.check_permission("read")
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng không thuộc đơn vị của bạn.")

    contract = so.custom_hdnt
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    gio_hang, bi_loai = [], []

    for dong in so.items:
        if not contract:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "ngoai_hdnt"})
            continue

        con_lai, _ = han_muc_con(contract, dong.item_code)
        if con_lai is not None and con_lai <= 0:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "het_han_muc"})
            continue

        gia = frappe.db.get_value(
            "Item Price",
            {"item_code": dong.item_code, "price_list": price_list, "selling": 1},
            "price_list_rate",
        )
        if not gia:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "thieu_gia"})
            continue

        qty = float(dong.qty)
        if con_lai is not None:
            qty = min(qty, con_lai)
        # Kèm tên và ĐVT: giỏ hàng dựng thẳng từ payload này, thiếu chúng thì
        # khách nhìn thấy mã hàng trần và không có đơn vị tính.
        gio_hang.append({
            "item_code": dong.item_code,
            "item_name": dong.item_name
            or frappe.db.get_value("Item", dong.item_code, "item_name"),
            "uom": dong.uom or "",
            "qty": qty,
            "gia_hien_hanh": float(gia),
            "remaining": None if con_lai is None else con_lai,
        })

    return {"gio_hang": gio_hang, "bi_loai": bi_loai}


LY_DO_TOI_THIEU_KHACH = 10


@frappe.whitelist()
def portal_order_accept(order, action, ly_do=None) -> dict:
    """US-E2.5 / API Spec §2.4 — khách đồng ý hoặc không đồng ý báo giá.

    Chuyển trạng thái chạy DƯỚI QUYỀN HỆ THỐNG: transition được mở cho
    `System Manager`, không phải cho role `Customer` — khách không bao giờ có
    quyền workflow trên Desk. Nhưng người bấm vẫn được ghi vào Comment, nếu
    không thì mọi thao tác đồng ý đều mang danh "Administrator" và không truy
    được ai đã đồng ý.
    """
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG chạy hook has_permission ở build này — phải tự kiểm.
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng không thuộc đơn vị của bạn.")
    if so.get("workflow_state") != "Chờ khách đồng ý":
        frappe.throw(
            "Đơn này không ở trạng thái chờ quý khách đồng ý.", frappe.ValidationError
        )

    if action == "dong_y":
        hanh_dong, ghi_chu = "Khách đồng ý", ""
    elif action == "khong_dong_y":
        ly_do = (ly_do or "").strip()
        if len(ly_do) < LY_DO_TOI_THIEU_KHACH:
            frappe.throw(
                f"Vui lòng nêu lý do (tối thiểu {LY_DO_TOI_THIEU_KHACH} ký tự).",
                frappe.ValidationError,
            )
        hanh_dong, ghi_chu = "Khách không đồng ý", ly_do
    else:
        frappe.throw("Hành động không hợp lệ.", frappe.ValidationError)

    nguoi_bam = frappe.session.user
    from frappe.model.workflow import apply_workflow

    # CỐ Ý KHÔNG dùng frappe.set_user() ở đây (code review sau lần merge đầu
    # phát hiện): frappe.local.session LÀ CÙNG MỘT OBJECT với
    # Session.data trong frappe/sessions.py — set_user() ghi đè
    # local.session.sid bằng chính chuỗi username (không phải sid thật) và
    # xoá sạch local.session.data (mất csrf_token...). Session.update()
    # (app.py, cuối MỌI request thật) vẫn dùng self.sid GỐC (biến riêng của
    # Session, không đổi) làm khoá `frappe.cache.hset("session", self.sid,
    # self.data)` — nên nó ghi ĐÈ cache session THẬT của chính khách đang gọi
    # bằng self.data đã hỏng. Gọi set_user() lần hai để "trả lại" chỉ khiến
    # nó tệ hơn: sid bị đặt lại thành username (không phải sid gốc), data
    # thành dict rỗng — không phải dữ liệu session gốc. Kết quả: khách mở
    # báo giá lâu (vượt threshold update session giữa chừng) rồi bấm Đồng ý
    # thì mọi POST sau đó trên tab đang mở lỗi CSRF tới khi tải lại trang.
    #
    # apply_workflow() chỉ tra vai trò qua frappe.get_roles() ->
    # frappe.session.user (frappe/model/workflow.py, frappe/permissions.py
    # get_roles() cache theo user nên an toàn khi đổi qua đổi lại) — không
    # đọc sid hay session.data ở đâu cả. Nên chỉ cần đổi ĐÚNG MỘT thuộc tính
    # `session.user`, không đụng `sid`/`data`, là đủ để apply_workflow chạy
    # dưới quyền hệ thống mà không có gì trên session thật của khách để
    # khôi phục sai.
    session = frappe.local.session
    frappe.local.user_perms = None  # tránh dùng nhầm cache quyền của người cũ
    session.user = "Administrator"
    try:
        so = apply_workflow(so, hanh_dong)
        noi_dung = f"{hanh_dong} bởi {nguoi_bam}"
        if ghi_chu:
            noi_dung += f" — lý do: {ghi_chu}"
        so.add_comment("Comment", noi_dung)
    finally:
        # Trả phiên về NGAY, kể cả khi apply_workflow ném: bỏ finally là để
        # phần còn lại của request chạy dưới quyền Administrator. CHỈ đổi
        # lại `session.user` — `sid`/`data` của khách chưa từng bị đụng tới
        # nên không có gì để khôi phục sai (xem giải thích ở trên).
        session.user = nguoi_bam
        frappe.local.user_perms = None

    return {"trang_thai_moi": so.get("workflow_state")}
