import os

import frappe
from miyano_portal import einvoice
from miyano_portal.kho import similarity
from miyano_portal.miyano_portal.doctype.portal_item_request.portal_item_request import (
    TRANG_THAI_KET_THUC,
)
from miyano_portal.portal_context import get_portal_customer, han_muc_con
from miyano_portal.portal_dat_hang import (
    kiem_boi_so,
    kiem_ngay_giao,
    ngay_giao_mac_dinh,
)
from miyano_portal.portal_mua_le import (
    cap_nhat_yeu_cau_goc,
    dam_bao_duoc_mua_le,
    han_hieu_luc_bao_gia,
    items_san_sang_giao,
    items_thuoc_hdnt_hieu_luc,
    price_list_ban_le,
    qua_han_hieu_luc,
    resolve_ban_le_company,
    trang_thai_hang,
)
from miyano_portal.portal_sla import cong_gio_lam_viec, gio_lam_viec_troi_qua, sla_yeu_cau_gio
from miyano_portal.portal_thong_bao import bao_thieu_gia, bao_yeu_cau_ho_tro_hddt, bao_yeu_cau_moi


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
        "Customer", customer, ["customer_name", "tax_id", "custom_cho_phep_mua_le"], as_dict=True
    ) or {}
    return {
        "customer": customer,
        "customer_name": cust.get("customer_name"),
        "tax_id": cust.get("tax_id"),
        "outstanding": _get_outstanding(customer),
        "addresses": _customer_addresses(customer),
        # review (Phần C báo thiếu) — không có field này, client phải GỌI
        # THỬ `portal_catalog_ban_le` mỗi lần chỉ để biết có nên hiện bộ
        # chuyển "Theo HĐNT | Mua lẻ" hay không (BR-R1) — một vòng round-trip
        # thừa, và một khách chưa bật cờ tự nhiên nhận 403 ngay từ lúc mở app.
        "cho_phep_mua_le": bool(cust.get("custom_cho_phep_mua_le")),
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
            # review M-1 (E6 phần B) — thêm `docstatus: 1` + `from_date <=
            # hôm nay`: trước bản này danh sách "hợp đồng của tôi" có thể lẫn
            # một Blanket Order còn NHÁP (chưa ai ký ở Desk) hoặc chưa tới
            # ngày hiệu lực, khiến khách tưởng mình đã có hợp đồng đang chạy.
            # Cùng bộ điều kiện với `portal_mua_le.items_thuoc_hdnt_hieu_luc`
            # (BR-R7) — hai nơi định nghĩa "HĐNT còn hiệu lực" PHẢI khớp
            # nhau: lệch nhau nghĩa là khách thấy hợp đồng ở màn này nhưng
            # BR-R7 lại không (hoặc ngược lại) coi mặt hàng của nó là "thuộc
            # HĐNT hiệu lực" ở màn mua lẻ.
            "docstatus": 1,
            "from_date": ["<=", today],
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
def portal_catalog_ban_le(tim_kiem=None, nhom=None) -> dict:
    """API Spec §2.2 / US-E6.1 — danh mục mua lẻ (QT10 nhánh A).

    403 `khong_duoc_mua_le` (NL-10.1) nếu `Customer.custom_cho_phep_mua_le`
    chưa bật — kiểm phía SERVER, không tin UI đã ẩn nút chuyển chế độ.
    """
    customer = get_portal_customer()
    dam_bao_duoc_mua_le(customer)  # BR-R1/NL-10.1

    price_list = price_list_ban_le()  # VĐ-12 — lỗi rõ nếu Settings chưa cấu hình.

    filters = {"custom_ban_le_portal": 1, "disabled": 0}
    if nhom:
        filters["item_group"] = nhom
    or_filters = None
    if tim_kiem:
        # Tìm theo cả mã lẫn tên — `filters` của `get_all` AND với nhau, nên
        # điều kiện "khớp mã HOẶC tên" phải đi qua `or_filters`.
        or_filters = [
            ["item_code", "like", f"%{tim_kiem}%"],
            ["item_name", "like", f"%{tim_kiem}%"],
        ]
    rows = frappe.get_all(
        "Item", filters=filters, or_filters=or_filters,
        fields=["item_code", "item_name", "description", "stock_uom"],
        order_by="item_name asc",
    )

    thuoc_hdnt = items_thuoc_hdnt_hieu_luc(customer)
    # review I-3 — tín hiệu "chưa sẵn sàng giao" NGAY TẠI DANH MỤC, một truy
    # vấn cho cả trang thay vì gọi resolve_ban_le_company() N lần.
    san_sang = items_san_sang_giao([r.item_code for r in rows])

    out = []
    for r in rows:
        gia = _gia_hien_hanh(r.item_code, price_list)
        # review M-3 — `Item.description` là Text Editor (HTML) và ERPNext
        # TỰ ĐỘNG chép `item_name` vào đây làm giá trị khởi tạo khi tạo
        # Item — bản trước trả thẳng `r.description or ""` nên cột "Quy
        # cách" trên danh mục lẻ thường hiện lại CHÍNH TÊN HÀNG (hoặc một
        # đoạn `<div>…</div>` thô nếu ai đó gõ mô tả có định dạng), sai loại
        # dữ liệu khách nhìn thấy. Bóc HTML rồi bỏ nếu nó chỉ là bản sao của
        # tên hàng — thà trống còn hơn thông tin sai.
        quy_cach = frappe.utils.strip_html(r.description or "").strip()
        if quy_cach == (r.item_name or "").strip():
            quy_cach = ""
        out.append({
            "item_code": r.item_code,
            "ten": r.item_name,
            "quy_cach": quy_cach,
            "dvt": r.stock_uom,
            "gia_ban_le": float(gia) if gia else None,
            # VAT chưa có nguồn dữ liệu thật trong app này — `portal_catalog`
            # (nhánh HĐNT, [Hiện có]) cũng hardcode 0 cho `vat_pct`, giữ nhất
            # quán chứ không phải một khiếm khuyết mới của nhánh lẻ.
            "vat": 0,
            "trang_thai_hang": trang_thai_hang(r.item_code),
            "thuoc_hdnt": r.item_code in thuoc_hdnt,
            "co_gia": bool(gia),
            # review I-3 — False: admin bật bán lẻ + đặt giá nhưng CHƯA khai
            # Item Default (company/kho) cho mặt hàng này. Phần C nên khoá
            # nút thêm giỏ và hiện "Miyano đang cập nhật, vui lòng liên hệ"
            # thay vì để khách điền hết giỏ mới nhận lỗi ở bước Xác nhận.
            "san_sang_ban": r.item_code in san_sang,
        })
    return {"items": out}


def _insert_so_idempotent(so, request_id) -> dict:
    """Ghi `so` (chưa insert) rồi trả phong bì chuẩn — dùng CHUNG bởi cả hai
    nhánh HĐNT và Mua lẻ của `portal_order_place`, đúng một khuôn xử lý đua
    `UniqueValidationError` (xem giải thích gốc ở khối này trước khi tách).
    """
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


def _xay_don_hdnt(customer, contract, bo, aggregated, delivery_date, address, po, note, request_id):
    """Nhánh Theo HĐNT [Hiện có, tách nguyên khối khỏi `portal_order_place`
    để đứng cạnh `_xay_don_ban_le` — hành vi giữ NGUYÊN VẸN, không đổi một
    dòng logic nào so với bản trước khi tách (E6 phần B chỉ THÊM nhánh mới,
    không viết lại nhánh cũ)."""
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")

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
    so.custom_loai_don = "Theo HĐNT"
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
    return so


def _xay_don_ban_le(customer, aggregated, delivery_date, address, po, note, request_id):
    """Nhánh Mua lẻ (US-E6.2, BR-R2/R3/R4/R7) — [MỚI].

    KHÔNG kiểm hạn mức, KHÔNG gắn `blanket_order`/`against_blanket_order`
    (BR-R4). VẪN kiểm bội số/ngày giao/địa chỉ/request_id — những chốt đó
    không đặc thù cho HĐNT, chúng bảo vệ cả hai lối.
    """
    price_list = price_list_ban_le()  # VĐ-12 — ném lỗi rõ nếu chưa cấu hình.
    thuoc_hdnt = items_thuoc_hdnt_hieu_luc(customer)

    loi: list[dict] = []
    loi_ngay = kiem_ngay_giao(delivery_date)
    if loi_ngay:
        loi.append(loi_ngay)

    gia: dict[str, float] = {}
    for item_code, qty in aggregated.items():
        if qty <= 0:
            loi.append({
                "item_code": item_code,
                "ly_do": "so_luong_khong_hop_le",
                "thong_diep": f"{item_code}: số lượng phải > 0",
            })
            continue
        loi_boi_so = kiem_boi_so(item_code, qty)
        if loi_boi_so:
            loi.append(loi_boi_so)
            continue
        # BR-R6, phòng thủ tầng hai: danh mục `portal_catalog_ban_le` đã lọc
        # `custom_ban_le_portal=1`, nhưng client có thể gửi THẲNG một mã hàng
        # bất kỳ tới đây — không được tin payload, phải tự kiểm lại (NL-10.3:
        # đây chính là chốt chặn "trộn dòng" khi ai đó nhét một mã không
        # thuộc danh mục lẻ vào giỏ Mua lẻ).
        if not frappe.db.get_value("Item", item_code, "custom_ban_le_portal"):
            loi.append({
                "item_code": item_code,
                "ly_do": "khong_thuoc_danh_muc_le",
                "thong_diep": f"{item_code} không thuộc danh mục mua lẻ.",
            })
            continue
        # BR-R7 — CHỐT AN NINH NGHIỆP VỤ CỦA E6 PHẦN B: mặt hàng đang thuộc
        # HĐNT còn hiệu lực của khách phải đặt ở giỏ Theo HĐNT. Thiếu chốt
        # này thì khách hết hạn mức chỉ cần bấm sang Mua lẻ là mua tiếp cùng
        # mặt hàng — vô hiệu hoá toàn bộ cơ chế hạn mức của E1 (NL-10.7).
        if item_code in thuoc_hdnt:
            loi.append({
                "item_code": item_code,
                "ly_do": "thuoc_hdnt_hieu_luc",
                # Nguyên văn ma trận FormSpec §5, dòng NL-10.7.
                "thong_diep": (
                    f"{item_code} đang thuộc HĐNT — vui lòng đặt ở chế độ "
                    f"Theo HĐNT để hưởng giá hợp đồng."
                ),
            })
            continue
        rate = _gia_hien_hanh(item_code, price_list)
        if not rate:
            loi.append({
                "item_code": item_code,
                "ly_do": "thieu_gia",
                # Nguyên văn ma trận FormSpec §5, dòng NL-10.2.
                "thong_diep": (
                    f"{item_code} chưa có giá bán lẻ. Gửi yêu cầu báo giá — "
                    f"Miyano sẽ phản hồi trong thời gian SLA quy định."
                ),
            })
            continue
        gia[item_code] = rate

    if loi:
        frappe.local.response["loi"] = loi
        frappe.throw(
            "<br>".join(d["thong_diep"] for d in loi), frappe.ValidationError
        )
    frappe.local.response.pop("loi", None)

    company = resolve_ban_le_company(list(aggregated.keys()))
    if not company:
        frappe.throw(
            "Không xác định được công ty giao hàng cho giỏ mua lẻ này. "
            "Vui lòng liên hệ quản trị viên hệ thống.",
        )

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = delivery_date
    so.selling_price_list = price_list
    so.custom_nguon_don = "Client Portal"
    so.custom_loai_don = "Mua lẻ"
    so.custom_request_id = request_id
    so.custom_so_po_khach = po
    so.custom_yeu_cau_khach = note
    if address:
        so.shipping_address_name = address
        so.customer_address = address
    contact_name = frappe.db.get_value("Contact", {"user": frappe.session.user})
    if contact_name:
        so.contact_person = contact_name
        so.contact_email = frappe.session.user
    for item_code, qty in aggregated.items():
        rate = gia[item_code]
        item_warehouse = _resolve_item_warehouse(item_code, company)
        if not item_warehouse:
            frappe.throw(
                f"Không tìm thấy kho giao hàng cho mặt hàng {item_code} tại "
                f"công ty {company}. Vui lòng liên hệ quản trị viên hệ thống."
            )
        # BR-R4 — KHÔNG gắn blanket_order/against_blanket_order: đơn mua lẻ
        # không thuộc hạn mức HĐNT nào.
        so.append("items", {
            "item_code": item_code,
            "qty": qty,
            "rate": rate,
            "warehouse": item_warehouse,
            "delivery_date": delivery_date,
        })
    return so


@frappe.whitelist()
def portal_order_place(
    contract=None, items=None, po=None, delivery_date=None, note=None, address=None,
    request_id=None, mode="hdnt",
) -> dict:
    """API Spec §1.1 — `mode`: `"hdnt"` (mặc định, [Hiện có]) | `"ban_le"`
    (E6 phần B, [MỚI]). Tham số vẫn tên `contract` (không phải `hdnt` như
    JSON mẫu của API Spec) để KHÔNG đổi chữ ký mà `frontend/src/views/
    Cart.vue` (đã chạy thật) đang gọi — đổi tên tham số ở đây là đổi API mà
    không có gì buộc phần C phải đổi theo, một chỗ lệch tài liệu đã có từ
    trước E6, không phải lỗi tạo mới ở đây.
    """
    customer = get_portal_customer()
    mode = (mode or "hdnt").strip()
    if mode not in ("hdnt", "ban_le"):
        frappe.throw("Chế độ đặt hàng không hợp lệ.", frappe.ValidationError)
    if mode == "ban_le":
        # review C-1 — CHỐT DUY NHẤT của BR-R1 trên đường GHI. Phải gọi
        # SỚM NHẤT có thể, trước cả kiểm request_id: một khách chưa bật cờ
        # không được phép tương tác với chế độ mua lẻ theo BẤT KỲ đường nào,
        # kể cả thử lại một request_id cũ.
        dam_bao_duoc_mua_le(customer)

    # BR-O12 — chống tạo đơn trùng. Bắt buộc, không tuỳ chọn: để tuỳ chọn thì
    # một client cũ vẫn tạo được đơn trùng và quy tắc chỉ còn là trang trí.
    # Áp dụng CHUNG cho cả hai chế độ — mỗi lần bấm xác nhận (dù ngăn HĐNT
    # hay ngăn Mua lẻ) đều mang một request_id riêng (30_API_Spec §2 — "mỗi
    # ngăn xác nhận riêng → hai Sales Order riêng, mỗi cái một request_id").
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

    bo = None
    if mode == "hdnt":
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

    # BR-O13 — mặc định +2 NGÀY LÀM VIỆC (bỏ T7/CN), không phải +2 ngày lịch.
    delivery_date = delivery_date or ngay_giao_mac_dinh()

    # Aggregate the incoming cart by item_code so duplicate lines for the same
    # item can't each pass the quota check individually while together
    # exceeding the remaining quota (duplicate-line quota bypass).
    #
    # review C-2 — CHUẨN HOÁ `item_code` VỀ `Item.name` CHÍNH TẮC ngay tại
    # đây, TRƯỚC khi gộp. `tabItem` chạy collation `utf8mb4_unicode_ci`
    # (case-insensitive, PAD SPACE): MariaDB coi "VT0005", "vt0005",
    # "VT0005 " là CÙNG MỘT BẢN GHI, nhưng khoá gộp `aggregated` trước đây
    # là chuỗi Python thô — "VT0005" và "vt0005" tách thành HAI khoá riêng
    # trong dict, mỗi khoá đi qua `han_muc_con`/kiểm BR-R7 ĐỘC LẬP trên cùng
    # một mặt hàng thật. Hai hậu quả của cùng một lỗ:
    #   (a) nhánh HĐNT — "duplicate-line quota bypass" mà comment ở trên
    #       tuyên bố đã chặn thực ra CHƯA chặn hết: 2 dòng "VT0005"/"vt0005"
    #       mỗi dòng dưới hạn mức riêng lẻ vẫn lọt dù tổng vượt hạn mức thật;
    #   (b) nhánh mua lẻ (BR-R7) — "vt0005" không khớp phần tử "VT0005" của
    #       set `thuoc_hdnt` (so sánh bằng Python `in`, không qua DB), nên
    #       một mặt hàng đang thuộc HĐNT hiệu lực lách được BR-R7 chỉ bằng
    #       cách gõ mã hàng bằng chữ thường — và Frappe vẫn LƯU đơn với
    #       item_code chính tắc thật (`_validate_links` tự chuẩn hoá Link
    #       field về `name`), tức đây không phải "đơn rác", mà là một Sales
    #       Order thật trên đúng mặt hàng BR-R7 phải chặn.
    # Mã không tra ra Item thật bị từ chối NGAY, không để lọt xuống các
    # tầng kiểm phía dưới rồi lộ ra một thông điệp khó hiểu (hạn mức/giá của
    # một mặt hàng không tồn tại).
    aggregated = {}
    for line in items:
        raw_code = (line.get("item_code") or "").strip()
        item_code = frappe.db.get_value("Item", raw_code, "name") if raw_code else None
        if not item_code:
            frappe.throw(
                f"Không tìm thấy mặt hàng '{raw_code or '(trống)'}'.",
                frappe.ValidationError,
            )
        qty = float(line.get("qty") or 0)
        aggregated[item_code] = aggregated.get(item_code, 0) + qty

    if mode == "ban_le":
        so = _xay_don_ban_le(customer, aggregated, delivery_date, address, po, note, request_id)
    else:
        so = _xay_don_hdnt(customer, contract, bo, aggregated, delivery_date, address, po, note, request_id)

    return _insert_so_idempotent(so, request_id)


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
    if so_status == "Closed":
        # NL-2.8 — đóng sớm KHÁC huỷ: phần đã giao vẫn là hàng khách đã nhận.
        # Gộp chung vào "Đã huỷ" khiến khách tưởng không nhận được gì.
        # TODO(VĐ-7): phần chưa giao hiện KHÔNG được hoàn vào hạn mức Blanket
        # Order. Chỉ làm khi chủ đầu tư chốt cơ chế — xem BA §VĐ-7.
        return "Hoàn thành (đóng sớm)"
    if so_status == "Cancelled":
        return "Đã huỷ"
    if float(per_delivered or 0) > 0:
        return "Đang giao"
    if so_status == "Draft":
        return "Chờ xác nhận"
    # To Deliver and Bill / To Bill / To Deliver, all with 0 delivered so far.
    return "Đang xử lý"


def _so_status_vi_full(so_status, per_delivered, workflow_state) -> str:
    """`_so_status_vi` chỉ đọc từ điển trạng thái GỐC của ERPNext
    (`so.status`), không biết gì về `workflow_state` của Client Portal.
    Job daily `portal_bao_gia.quet_bao_gia_het_han` chuyển `workflow_state`
    sang "Báo giá hết hạn" nhưng `docstatus` VẪN 0 (nháp không submit) —
    không bọc ở đây thì một đơn ĐÃ CHẾT đọc ra y hệt "Chờ xác nhận" đang
    sống, ở CẢ danh sách đơn (`portal_order_history`) lẫn chi tiết đơn
    (`portal_order_track`). Một hàm DÙNG CHUNG ở cả hai, không phải hai lần
    viết tay điều kiện này — lệch nhau là đúng kiểu lỗi đã bắt ở
    `portal_mua_le.han_hieu_luc_bao_gia`.
    """
    if workflow_state == "Báo giá hết hạn":
        return "Báo giá đã hết hiệu lực"
    return _so_status_vi(so_status, per_delivered)


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


def _phieu_nhap_trang_thai_vi(docstatus: int, co_chenh_lech) -> str:
    """US-E3.4 (FormSpec F-07 khối đợt giao): ba trạng thái đúng nguyên văn
    AC — "Nháp" (client tự ghép thành "Phiếu nhập PNK-xxx — Nháp, chờ kiểm
    nhận" kèm link), "Đã ghi sổ", hoặc "Có chênh lệch ⚠" (docstatus=1 VÀ
    co_chenh_lech — ghi đè "Đã ghi sổ" vì đây là tín hiệu khách CẦN thấy
    ngay, không phải một chi tiết phụ). docstatus=2 (đã huỷ) không tới được
    hàm này — receipts_by_dn ở portal_order_track chỉ lấy docstatus < 2."""
    if docstatus == 0:
        return "Nháp"
    return "Có chênh lệch ⚠" if co_chenh_lech else "Đã ghi sổ"


@frappe.whitelist()
def portal_order_history(limit=20, start=0) -> list:
    rows = frappe.get_list(
        "Sales Order",
        # review (Phần C báo thiếu) — custom_loai_don/workflow_state/
        # custom_yeu_cau_goc: danh sách đơn không phân biệt được đơn "Mua
        # lẻ" với "Theo HĐNT" (badge/icon giỏ 2 ngăn), và không biết đơn nào
        # đang "Chờ khách đồng ý" để hiện banner ngay trên danh sách thay vì
        # bắt khách mở từng đơn.
        fields=["name", "transaction_date", "grand_total", "status", "per_delivered",
                "custom_loai_don", "workflow_state", "custom_yeu_cau_goc"],
        order_by="transaction_date desc, creation desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _so_status_vi_full(r.pop("status"), r.get("per_delivered"), r.get("workflow_state"))
        # Đổi tên khoá `custom_loai_don` -> `loai_don`: KHÔNG rò tiền tố nội
        # bộ `custom_` của Frappe ra response công khai, và khớp đúng tên
        # khoá `portal_order_track` đã dùng cho CÙNG khái niệm — hai endpoint
        # trả hai tên khác nhau cho một field là bẫy tiếp theo đang chờ xảy
        # ra (client đọc đúng ở màn này, sai ở màn kia).
        r["loai_don"] = r.pop("custom_loai_don") or "Theo HĐNT"
        r["yeu_cau_goc"] = r.pop("custom_yeu_cau_goc") or ""
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
    # order_by=creation: so "Đợt n" (array index, see OrderDetail.vue) reads
    # in the order the DNs actually happened, not arbitrary row order.
    total_qty = sum(float(i.qty or 0) for i in so.items) or 0
    dn_names = frappe.get_all(
        "Delivery Note Item",
        filters={"against_sales_order": so.name, "docstatus": ["<", 2]},
        pluck="parent",
        order_by="creation asc",
    )
    dn_names = list(dict.fromkeys(dn_names))

    # US-E3.4 — trạng thái phiếu nhập chỉ hiện khi khách CÓ kho (không dùng
    # get_portal_kho(): hàm đó ném PermissionError khi khách chưa mở kho, mà
    # phần lớn khách hàng portal KHÔNG có kho — đây không phải một tình huống
    # ngoại lệ cho endpoint này). `active: 1` khớp đúng định nghĩa "có kho"
    # mà get_portal_kho()/delivery_hook._kho_cua_khach() đã dùng ở mọi nơi
    # khác trong app — một kho đã tắt được coi như "không có kho" ở đây,
    # nhất quán với việc hook cũng ngừng tự sinh phiếu cho kho đó.
    kho = frappe.db.get_value("Customer Warehouse", {"customer": so.customer, "active": 1}, "name")
    receipts_by_dn = {}
    if kho and dn_names:
        for r in frappe.get_all(
            "Customer Stock Receipt",
            filters={"kho": kho, "delivery_note": ["in", dn_names], "docstatus": ["<", 2]},
            fields=["name", "delivery_note", "docstatus", "co_chenh_lech", "so_dot"],
        ):
            receipts_by_dn[r.delivery_note] = r

    # `deliveries` (đã có [Hiện có]) và `dot_giao` (mới, đúng chữ ký
    # `30_API_Spec` §1.2) dựng từ CÙNG một vòng lặp/CÙNG một nguồn — hai key
    # riêng trên response, không phải `"dot_giao": deliveries` (alias thẳng
    # object sẽ dính bug nếu một bên bị sửa tại chỗ sau này) và KHÔNG PHẢI
    # hai khối UI song song: OrderDetail.vue chỉ đọc `deliveries` (đã mở
    # rộng thêm so_dot/phieu_nhap ở đó), `dot_giao` tồn tại để đúng hợp đồng
    # API cho các bên gọi khác (client tương lai, kiểm thử theo đặc tả).
    deliveries = []
    dot_giao = []
    for dn_name in dn_names:
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

        receipt = receipts_by_dn.get(dn_name)
        # so_dot lưu DB thành 0 khi "không xác định" (Int không nullable —
        # bàn giao Phần A), không phải "đợt 0" — trả None cho client thay vì
        # con số 0 gây hiểu lầm.
        so_dot = (receipt.so_dot or None) if receipt else None
        phieu_nhap = None
        if receipt:
            phieu_nhap = {
                "name": receipt.name,
                "trang_thai": _phieu_nhap_trang_thai_vi(int(receipt.docstatus), receipt.co_chenh_lech),
                "co_chenh_lech": bool(receipt.co_chenh_lech),
            }

        row = {
            "name": dn["name"],
            "posting_date": dn.get("posting_date"),
            "status": dn.get("status"),
            "percent": pct,
            "carrier": dn.get("transporter_name") or "",
            "awb": dn.get("lr_no") or "",
        }
        if receipt:
            row["so_dot"] = so_dot
            row["phieu_nhap"] = phieu_nhap
        deliveries.append(row)

        dot = {
            "so_dot": so_dot,
            "delivery_note": dn["name"],
            "ngay": dn.get("posting_date"),
            "phan_tram": pct,
            "van_chuyen": dn.get("transporter_name") or "",
            "awb": dn.get("lr_no") or "",
        }
        if phieu_nhap:
            dot["phieu_nhap"] = phieu_nhap
        dot_giao.append(dot)

    # US-E6.5 / `30_API_Spec` §1.2 — banner "Chờ bạn đồng ý" (F-07) cần biết
    # hạn hiệu lực để hiện "Báo giá hiệu lực đến dd/mm/yyyy"; chỉ có ý nghĩa
    # khi đơn ĐANG ở trạng thái này, các trạng thái khác trả `None`.
    #
    # review I-2(b) — `can_dong_y` KHÔNG được là `True` vô điều kiện: đơn có
    # thể vẫn còn `workflow_state == "Chờ khách đồng ý"` (job daily CHƯA kịp
    # quét) nhưng đã quá `han_hieu_luc` — client phải biết để tắt nút Đồng ý
    # ngay, không đợi đến khi khách bấm rồi mới nhận 417.
    # review I-2(c) — `han_hieu_luc`/hết hạn chỉ có ý nghĩa với đơn "Mua lẻ"
    # (BR-R5 nằm trong QT10); đơn HĐNT ở "Chờ khách đồng ý" (luồng E2 gốc)
    # không có khái niệm hiệu lực N ngày.
    la_mua_le = so.get("custom_loai_don") == "Mua lẻ"
    chap_nhan = None
    if so.get("workflow_state") == "Chờ khách đồng ý":
        het_han = la_mua_le and qua_han_hieu_luc(so)
        chap_nhan = {
            "can_dong_y": not het_han,
            "han_hieu_luc": str(han_hieu_luc_bao_gia(so)) if la_mua_le else None,
        }

    # `_so_status_vi_full` bọc đúng tình huống job daily chuyển
    # `workflow_state` sang "Báo giá hết hạn" mà `docstatus` vẫn 0 — dùng
    # CHUNG với `portal_order_history`, không viết tay điều kiện này hai lần.
    status_vi = _so_status_vi_full(so.status, so.per_delivered, so.get("workflow_state"))

    return {
        "order": so.name,
        "status_vi": status_vi,
        "order_date": so.transaction_date,
        "po_khach": so.get("custom_so_po_khach") or "",
        "hdnt": so.get("custom_hdnt") or "",
        # US-E2.2 — khách phải đọc được lý do ngay trên chi tiết đơn, không
        # phải đi tìm lại email.
        "ly_do_tu_choi": so.get("custom_ly_do_tu_choi") or "",
        # review (Phần C báo thiếu)
        "loai_don": so.get("custom_loai_don") or "Theo HĐNT",
        "workflow_state": so.get("workflow_state") or "",
        "yeu_cau_goc": so.get("custom_yeu_cau_goc") or "",
        "chap_nhan": chap_nhan,
        "milestones": milestones,
        "items": [
            {"item_code": i.item_code,
             "item_name": i.item_name or frappe.db.get_value("Item", i.item_code, "item_name"),
             "qty": i.qty, "delivered_qty": i.delivered_qty,
             "rate": float(i.rate or 0), "uom": i.uom, "amount": float(i.amount or 0)}
            for i in so.items
        ],
        "deliveries": deliveries,
        # `30_API_Spec` §1.2 — cùng dữ liệu với `deliveries`, đúng tên field
        # đặc tả yêu cầu (xem ghi chú ngay phía trên vòng lặp).
        "dot_giao": dot_giao,
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
        # `customer` chỉ dùng NỘI BỘ để đối chiếu sở hữu bản ghi HĐĐT
        # (`einvoice.block_for` — F-08/E7), bị `pop` trước khi trả về, KHÔNG
        # phải một field mới lộ ra response.
        fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount",
                "status", "customer"],
        order_by="posting_date desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _invoice_status_vi(r.pop("status"))
        # E7/F-08 — khối HĐĐT đi kèm NGAY trong danh sách (đúng hành vi bản
        # mẫu: `toggleEinv()` chỉ ẩn/hiện một dòng đã có sẵn dữ liệu, không
        # gọi thêm API khi khách bấm xổ dòng). `block_for` tự đối chiếu
        # `fei.customer == r["customer"]` — một sai sót dữ liệu ở module HĐĐT
        # (kế toán gõ nhầm `sales_invoice` sang hoá đơn của khách khác) không
        # lọt ra cổng dù `Sales Invoice` này đọc được là đúng chủ.
        r["einvoice"] = einvoice.block_for(r["name"], r.pop("customer"))
    return rows


@frappe.whitelist()
def portal_einvoice_download(invoice, loai="pdf") -> None:
    """US-E7.2/BR-E4 — tải PDF hoá đơn điện tử. `loai` chỉ còn `"pdf"`: module
    HĐĐT không lưu XML ở đâu cả (không field nào chứa 'xml' trên
    `Fast EInvoice Document`, đã kiểm JSON) — không có XML để giao.

    Kiểm TỪNG LẦN tải (BR-E4, NL-12.5): hoá đơn thuộc customer của phiên +
    Fast EInvoice Document khớp thuộc ĐÚNG hoá đơn đó + trạng thái cho phép
    tải + file thật sự đọc được — không chỉ tin cờ `tai_duoc` đã tính lúc
    liệt kê (dữ liệu có thể đã đổi giữa hai lần gọi, và đây là chứng từ
    thuế). Không có URL file công khai: `/printview` hay dán link sang máy
    khác không đăng nhập đều 403 ở `check_permission`/`get_portal_customer`.
    """
    if loai != "pdf":
        frappe.throw(
            "Cổng chỉ cung cấp bản PDF thể hiện. Cần bản gốc XML có giá trị "
            "pháp lý, vui lòng liên hệ kế toán Miyano."
        )

    customer = get_portal_customer()
    si = frappe.get_doc("Sales Invoice", invoice)
    # `frappe.get_doc` KHÔNG tự kiểm quyền — `check_permission` là nơi hook
    # `has_permission` (miyano_portal.permissions.generic_has_permission)
    # thực sự chạy.
    si.check_permission("read")
    if si.customer != customer:
        raise frappe.PermissionError("Hoá đơn không thuộc đơn vị của bạn.")

    fei = einvoice.resolve(invoice)
    if not fei or fei.customer != si.customer:
        frappe.throw("Chưa có hoá đơn điện tử cho chứng từ này.", frappe.ValidationError)
    if not einvoice.sua_duoc_tai(fei):
        frappe.throw(
            "Hoá đơn điện tử này chưa có file để tải. Bấm [Yêu cầu hỗ trợ] "
            "nếu cần Miyano hỗ trợ.",
            frappe.ValidationError,
        )
    if not fei.official_pdf:
        frappe.throw(
            "File PDF đang được tạo, vui lòng thử lại sau ít phút. Bấm "
            "[Yêu cầu hỗ trợ] nếu vẫn chưa có sau một thời gian.",
            frappe.ValidationError,
        )

    # File có thể đã bị xoá/hỏng dù field `official_pdf` vẫn còn giá trị cũ
    # (NL-12.4) — kiểm file THẬT SỰ đọc được, không chỉ tin field. Lọc thêm
    # `attached_to_*` (không chỉ `file_url`): Frappe gộp file trùng nội dung
    # theo content hash, nên nhiều `File` khác nhau (đính vào chứng từ HĐĐT
    # khác nhau) có thể trỏ CHUNG một `file_url` — chỉ lọc theo url sẽ tìm
    # thấy record của chứng từ KHÁC dù bản ghi của CHÍNH chứng từ này đã bị
    # xoá (đã bắt gặp thật khi hai chứng từ HĐĐT test có PDF trùng byte).
    file_doc = frappe.db.get_value(
        "File",
        {
            "file_url": fei.official_pdf,
            "attached_to_doctype": einvoice.FEI,
            "attached_to_name": fei.name,
        },
        "name",
    )
    if not file_doc:
        frappe.throw(
            "File PDF bị thiếu hoặc hỏng trên hệ thống. Bấm [Yêu cầu hỗ trợ] "
            "để Miyano xử lý.",
            frappe.ValidationError,
        )
    content = frappe.get_doc("File", file_doc).get_content()

    from frappe.core.doctype.access_log.access_log import make_access_log

    make_access_log(
        doctype=einvoice.FEI, document=fei.name, file_type="pdf",
        method="portal_einvoice_download",
    )

    frappe.local.response.filename = f"{fei.fast_invoice_no or fei.name}.pdf"
    frappe.local.response.filecontent = content
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def portal_einvoice_ho_tro(invoice) -> dict:
    """NL-12.4 — nút [Yêu cầu hỗ trợ] trên khối HĐĐT, tự đính mã hoá đơn."""
    customer = get_portal_customer()
    si = frappe.get_doc("Sales Invoice", invoice)
    si.check_permission("read")
    if si.customer != customer:
        raise frappe.PermissionError("Hoá đơn không thuộc đơn vị của bạn.")

    fei = einvoice.resolve(invoice)
    fei_name = fei.name if (fei and fei.customer == si.customer) else None
    bao_yeu_cau_ho_tro_hddt(customer, invoice, fei_name)
    return {"ok": True}


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
    # US-E6.5/BR-R5 — báo giá có hiệu lực N ngày kể từ ngày lập
    # (Settings.hieu_luc_bao_gia_ngay, mặc định 7). Chặn CẢ đồng ý lẫn không
    # đồng ý: một báo giá đã hết hiệu lực không còn gì để khách phản hồi,
    # job daily (`portal_bao_gia.quet_bao_gia_het_han`) sẽ tự đóng nó —
    # khách phải gửi yêu cầu báo giá mới, không phải bấm nút trên đơn cũ.
    #
    # review I-2(c) — CHỈ áp cho đơn "Mua lẻ". State "Chờ khách đồng ý"
    # KHÔNG phải riêng của E6: E2 (US-E2.5, trước cả E6) đã dùng nó cho MỌI
    # loại đơn cần khách duyệt giá, không có khái niệm hiệu lực N ngày nào.
    # Thiếu điều kiện `custom_loai_don == "Mua lẻ"` ở đây thì một đơn HĐNT
    # đang chờ khách duyệt (luồng E2 gốc, có thể mở nhiều tuần) cũng bị chặn
    # 417 và bị `quet_bao_gia_het_han` tự đóng — một hành vi BR-R5 (nằm
    # trong §4.10, phạm vi QT10/mua lẻ) chưa từng yêu cầu.
    if so.get("custom_loai_don") == "Mua lẻ" and qua_han_hieu_luc(so):
        han = han_hieu_luc_bao_gia(so)
        frappe.local.response["ly_do"] = "qua_han_hieu_luc"
        frappe.throw(
            f"Báo giá cho đơn {so.name} đã hết hiệu lực ngày "
            f"{frappe.utils.formatdate(han, 'dd/mm/yyyy')}. Gửi yêu cầu báo "
            f"giá mới nếu vẫn cần hàng.",
            frappe.ValidationError,
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

    if action == "dong_y":
        # US-E6.5 — cạnh "Đã chuyển thành đơn" mà Phần A đã dựng sẵn trong
        # máy trạng thái Portal Item Request nhưng chưa ai ghi. Chạy SAU khi
        # phiên khách đã được trả lại (không cần ignore_permissions cảnh báo
        # giả — `cap_nhat_yeu_cau_goc` tự `ignore_permissions=True`), và
        # KHÔNG được để một trục trặc ở đây làm hỏng việc đồng ý đã ghi
        # nhận thành công phía trên (xem docstring của hàm).
        cap_nhat_yeu_cau_goc(so, "Đã chuyển thành đơn")
    elif action == "khong_dong_y":
        # review I-5/NL-10.4 — BA §4.10 ghi rõ "lý do lưu vào đơn VÀ yêu
        # cầu gốc". Bản trước chỉ ghi Comment lên `so` (dòng phía trên) —
        # `Portal Item Request` liên kết đứng yên ở "Đã báo giá" không dấu
        # vết, F-23 (màn chi tiết yêu cầu, đọc `binh_luan`) không có gì để
        # sales thấy khách chê gì. KHÔNG đổi `trang_thai`: máy trạng thái
        # (portal_item_request.py) không có cạnh nào rời "Đã báo giá" để
        # "sales sửa giá" — sales sửa thẳng trên SO đã liên kết, yêu cầu gốc
        # giữ nguyên "Đã báo giá", chỉ thêm dấu vết bằng Comment.
        ten_yc = so.get("custom_yeu_cau_goc")
        if ten_yc and frappe.db.exists("Portal Item Request", ten_yc):
            frappe.get_doc("Portal Item Request", ten_yc).add_comment(
                "Comment",
                f"[Portal] Khách không đồng ý báo giá {so.name} — lý do: {ghi_chu}",
            )

    return {"trang_thai_moi": so.get("workflow_state")}


# ---------------------------------------------------------------------------
# E6/US-E6.3, US-E6.4 — Yêu cầu hàng hoá (`Portal Item Request`). Xem
# docs/Miyano-Portal(Client)_V2/DevHandoff/15_PRD_E6_MuaLe_YeuCauHang.md,
# 20_DataDict.md §1.2, 30_API_Spec.md §2.3, BA §4.11 (BR-Y1…Y5, NL-11.x).
# ---------------------------------------------------------------------------

YEU_CAU_FIELDS = (
    "loai", "ten_hang", "quy_cach", "dvt", "so_luong_du_kien", "tan_suat",
    "chu_ky_thang", "ngay_can", "hang_xuat_xu", "ghi_chu", "vat_tu_kho",
)

DINH_KEM_TOI_DA = 5
DINH_KEM_MB_TOI_DA = 10
DINH_KEM_DUOI_HOP_LE = {".pdf", ".jpg", ".jpeg", ".png", ".xlsx"}
# NL-11.6 — nguyên văn thông điệp trong FormSpec §5.
THONG_DIEP_DINH_KEM_SAI = "Tối đa 5 file, mỗi file ≤ 10MB, định dạng pdf/jpg/png/xlsx."


def _parse_yeu_cau_payload(payload) -> dict:
    if isinstance(payload, str):
        payload = frappe.parse_json(payload)
    if not isinstance(payload, dict):
        frappe.throw("Dữ liệu yêu cầu không hợp lệ.", frappe.ValidationError)
    return payload


@frappe.whitelist()
def portal_yeu_cau_list(trang_thai=None) -> list:
    """API Spec §2.3."""
    customer = get_portal_customer()
    filters = {"customer": customer}
    if trang_thai:
        filters["trang_thai"] = trang_thai
    rows = frappe.get_all(
        "Portal Item Request",
        filters=filters,
        fields=[
            "name", "creation", "ten_hang", "loai", "so_luong_du_kien",
            "trang_thai", "sla_den_han", "don_lien_ket",
        ],
        order_by="creation desc",
    )
    sla_gio = sla_yeu_cau_gio()
    out = []
    for r in rows:
        d = dict(r)
        d["ngay"] = d.pop("creation")
        # SLA phản hồi đầu tiên chỉ còn ý nghĩa trong khi yêu cầu còn "Mới" —
        # chuyển trạng thái nghĩa là ai đó ĐÃ phản hồi.
        d["qua_sla"] = (
            d["trang_thai"] == "Mới"
            and gio_lam_viec_troi_qua(d["ngay"]) >= sla_gio
        )
        out.append(d)
    return out


@frappe.whitelist()
def portal_yeu_cau_detail(name) -> dict:
    """F-2 (review) — F-23 (chi tiết yêu cầu) cần đọc `phan_hoi`, `gia_bao`,
    `lead_time_ngay`, `ly_do_khong_dap_ung`, chuỗi comment và danh sách đính
    kèm — không field nào trong số đó có trong `portal_yeu_cau_list`.
    Không có endpoint này, `portal_yeu_cau_tra_loi` chỉ có chiều GHI: email
    "Cần thêm thông tin" báo khách "xem chi tiết trên cổng khách hàng" nhưng
    không API nào trả lại câu hỏi để khách xem trước khi trả lời.

    Đính kèm trả về THEO TÊN FILE (`File.name`), KHÔNG kèm `file_url` — xem
    `portal_yeu_cau_file` bên dưới: F-5 cho thấy `file_url` không phải khoá
    tra AN TOÀN cho một bản ghi đính kèm cụ thể (nhiều `File.name` có thể
    trỏ chung một `file_url` do Frappe gộp theo nội dung), và một `file_url`
    riêng tư lộ ra ngoài cũng vô dụng với khách: `/private/files/...` chỉ
    render được cho đúng `File.owner`, trong khi BR-Y5 đòi hỏi MỌI user
    portal của cùng khách hàng đọc được (F-3)."""
    customer = get_portal_customer()
    doc = _yeu_cau_cua_khach(name, customer)

    binh_luan = frappe.get_all(
        "Comment",
        filters={"reference_doctype": "Portal Item Request", "reference_name": name},
        fields=["content", "comment_by", "owner", "creation"],
        order_by="creation asc",
    )
    dinh_kem = frappe.get_all(
        "File",
        filters={"attached_to_doctype": "Portal Item Request", "attached_to_name": name},
        fields=["name", "file_name"],
        order_by="creation asc",
    )
    return {
        "name": doc.name,
        # review (Phần C báo thiếu) — F-23 hiện đầu trang "Mã + ... ngày gửi"
        # (xem FormSpec §F-22 "Danh sách yêu cầu" cột "Ngày gửi" đã có ở
        # `portal_yeu_cau_list`, nhưng chi tiết F-23 lại thiếu) và cần biết
        # AI đã gửi yêu cầu khi một Customer có nhiều user portal
        # (`portal_provision` cấp nhiều user/một Customer).
        "ngay": doc.creation,
        "nguoi_yeu_cau": doc.nguoi_yeu_cau,
        "loai": doc.loai,
        "ten_hang": doc.ten_hang,
        "quy_cach": doc.quy_cach,
        "dvt": doc.dvt,
        "so_luong_du_kien": doc.so_luong_du_kien,
        "tan_suat": doc.tan_suat,
        "chu_ky_thang": doc.chu_ky_thang,
        "ngay_can": doc.ngay_can,
        "hang_xuat_xu": doc.hang_xuat_xu,
        "ghi_chu": doc.ghi_chu,
        "trang_thai": doc.trang_thai,
        "sla_den_han": doc.sla_den_han,
        "phan_hoi": doc.phan_hoi,
        "gia_bao": doc.gia_bao,
        "lead_time_ngay": doc.lead_time_ngay,
        "item_lien_ket": doc.item_lien_ket,
        "don_lien_ket": doc.don_lien_ket,
        "ly_do_khong_dap_ung": doc.ly_do_khong_dap_ung,
        "binh_luan": binh_luan,
        "dinh_kem": dinh_kem,
    }


def _dem_dinh_kem_hien_co(name) -> int:
    if not name:
        return 0
    return frappe.db.count(
        "File",
        {"attached_to_doctype": "Portal Item Request", "attached_to_name": name},
    )


def _resolve_owned_attachment(file_url: str, doc_name: str | None):
    """NL-11.6/BR-Y5 — nạp một `File` do CHÍNH người gọi vừa tải lên (chuẩn
    Frappe `/api/method/upload_file?is_private=1`), kiểm sở hữu + định dạng +
    kích thước + riêng tư.

    `doc_name`: tên `Portal Item Request` đang tạo/sửa (None khi tạo mới).
    Dùng để phân biệt "đã gắn đúng vào yêu cầu này" (idempotent, cho qua) với
    "đã gắn vào một yêu cầu KHÁC" (từ chối) — xem giải thích dedup bên dưới.

    F-5 (review) — KHÔNG tra theo `file_url` một mình: `File.
    validate_duplicate_entry()` gộp NHIỀU `File.name` khác nhau vào CHUNG một
    `file_url` khi nội dung trùng `content_hash` (không phân biệt owner hay
    lần upload). Bản trước tra `frappe.db.get_value("File", {"file_url":
    url}, "name")` không `ORDER BY` — với cùng một khách, hai lần tải lên
    trùng byte ở hai yêu cầu khác nhau có thể khiến lần sau DỜI đính kèm của
    yêu cầu trước sang yêu cầu đang sửa (mất dữ liệu âm thầm); với hai khách
    khác nhau tải trùng một tài liệu công khai của hãng, khách sau có thể bị
    chặn nhầm bởi bản ghi của khách trước. Sửa bằng CẢ HAI: (1) lọc thêm
    `owner=phiên hiện tại` — loại hẳn khả năng thấy File của khách khác;
    (2) trong các File cùng owner+file_url, ưu tiên bản CHƯA gắn vào đâu
    (`attached_to_name` rỗng — luôn là lần upload mới nhất, vì upload_file
    không tự gắn), nếu không còn bản nào rỗng thì chỉ chấp nhận bản đã gắn
    ĐÚNG vào `doc_name` hiện tại (sửa nháp, gửi lại chính danh sách cũ);
    ngược lại từ chối thẳng thay vì âm thầm dời.

    GIỚI HẠN CÒN LẠI, nói thẳng: nếu CÙNG một khách có HAI File CÙNG CHƯA GẮN
    VÀO ĐÂU trùng nội dung (ví dụ đang tạo hai yêu cầu khác nhau gần như
    cùng lúc, mỗi yêu cầu tải lên "cùng một ảnh"), `file_url` không đủ thông
    tin để biết client muốn nói File.name nào — hàm này chọn bản mới nhất
    theo `creation`, một lựa chọn tuỳ ý nhưng AN TOÀN (không mất dữ liệu, chỉ
    có thể "lệch" File.name cụ thể giữa hai bản trùng byte, nội dung phục vụ
    ra vẫn đúng). Muốn hết mơ hồ hoàn toàn phải đổi giao thức để client gửi
    `File.name` thay vì `file_url` — ngoài phạm vi bản vá này.
    """
    rows = frappe.get_all(
        "File",
        filters={"file_url": file_url, "owner": frappe.session.user},
        fields=["name", "file_name", "is_private", "attached_to_doctype", "attached_to_name"],
        order_by="creation desc",
    )
    if not rows:
        frappe.throw(
            "Không tìm thấy tệp đã tải lên. Vui lòng chọn lại tệp và thử lại.",
            frappe.ValidationError,
        )

    chua_gan = [r for r in rows if not r.attached_to_name]
    da_gan_dung_yeu_cau = [r for r in rows if doc_name and r.attached_to_name == doc_name]
    if chua_gan:
        file_row = chua_gan[0]
    elif da_gan_dung_yeu_cau:
        file_row = da_gan_dung_yeu_cau[0]
    else:
        frappe.throw(
            "Tệp này đã được đính kèm vào một yêu cầu khác. Vui lòng tải lên lại.",
            frappe.ValidationError,
        )

    ext = os.path.splitext(file_row.file_name or "")[1].lower()
    if ext not in DINH_KEM_DUOI_HOP_LE:
        frappe.throw(THONG_DIEP_DINH_KEM_SAI, frappe.ValidationError)

    file_doc = frappe.get_doc("File", file_row.name)

    # F-1 (review) — `file_doc.file_size` KHÔNG đáng tin: File.validate() ghi
    # `self.file_size = frappe.form_dict.file_size or self.file_size` SAU khi
    # save_file()/check_max_file_size() đã đo kích thước thật, tức giá trị
    # client tự khai trong multipart form đè lên số đã đo — một field client
    # kiểm soát hoàn toàn. Đo lại NỘI DUNG THẬT, vô điều kiện, không đọc field
    # này nữa; đây là chốt chặn 10MB thật, không phải đọc lại một số có thể bị
    # giả mạo.
    try:
        kich_thuoc = len(file_doc.get_content() or b"")
    except Exception:
        frappe.throw(
            "Không đọc được tệp đã tải lên. Vui lòng chọn lại tệp và thử lại.",
            frappe.ValidationError,
        )
    if kich_thuoc > DINH_KEM_MB_TOI_DA * 1024 * 1024:
        frappe.throw(THONG_DIEP_DINH_KEM_SAI, frappe.ValidationError)

    # BR-Y5: đính kèm PHẢI riêng tư — không có URL công khai. Từ chối thẳng
    # thay vì tự bật lại is_private: việc đó đòi hỏi Frappe di chuyển file
    # trên đĩa và viết lại file_url, một hiệu ứng phụ không nên xảy ra âm
    # thầm bên trong một hàm validate. Đường hợp lệ (upload_file?is_private=1)
    # không bao giờ chạm nhánh này.
    if not file_doc.is_private:
        frappe.throw(THONG_DIEP_DINH_KEM_SAI, frappe.ValidationError)

    return file_doc


def _kiem_va_lay_dinh_kem(file_urls, so_hien_co: int, doc_name: str | None) -> list:
    if not file_urls:
        return []
    if so_hien_co + len(file_urls) > DINH_KEM_TOI_DA:
        frappe.throw(THONG_DIEP_DINH_KEM_SAI, frappe.ValidationError)
    return [_resolve_owned_attachment(u, doc_name) for u in file_urls]


def _vat_tu_thuoc_khach(vat_tu_kho: str, customer: str) -> None:
    """F-4 (review) — `vat_tu_kho` đến thẳng từ payload client (autoname
    `VTK-.#####`, tuần tự, đoán được). `frappe.get_doc`/`doc.set()` KHÔNG tự
    kiểm sở hữu của một Link field — client đặt bất kỳ mã nào tồn tại trên
    site, kể cả vật tư kho của khách hàng KHÁC, vẫn lưu được (link validation
    chỉ kiểm bản ghi tồn tại). Cùng khuôn `_vat_tu_cua_kho()` trong
    api/kho.py: xác nhận vật tư đó thuộc kho của CHÍNH khách đang gọi TRƯỚC
    khi gán vào yêu cầu."""
    kho_cua_vat_tu = frappe.db.get_value("Customer Warehouse Item", vat_tu_kho, "kho")
    if not kho_cua_vat_tu:
        frappe.throw("Không tìm thấy vật tư kho khách đã chọn.", frappe.ValidationError)
    chu_kho = frappe.db.get_value("Customer Warehouse", kho_cua_vat_tu, "customer")
    if chu_kho != customer:
        raise frappe.PermissionError("Vật tư không thuộc kho của đơn vị bạn.")


def _yeu_cau_cua_khach(name: str, customer: str):
    """M-1 (review) — tra sở hữu bằng `frappe.db.get_value` TRƯỚC
    `frappe.get_doc`, cùng khuôn `_resolve_owned_spreadsheet`/
    `_phieu_cua_kho` trong api/kho.py. Tên KHÔNG TỒN TẠI và tên CỦA KHÁCH
    KHÁC giờ trả về CÙNG một `frappe.PermissionError` tiếng Việt — bản trước
    gọi thẳng `frappe.get_doc(name)` rồi mới so `customer`, nên tên không
    tồn tại ném `DoesNotExistError` (tiếng Anh, khác loại) TRƯỚC khi kịp so
    sánh, để lộ qua LOẠI LỖI xem một mã `YCH-nnnnn` có tồn tại hay không —
    đúng lỗ cách ly mà TC-E6-12 nhắm tới nhưng chưa phủ ở nhánh sửa/huỷ/
    trả lời/đọc chi tiết."""
    doc_customer = frappe.db.get_value("Portal Item Request", name, "customer")
    if doc_customer != customer:
        raise frappe.PermissionError("Bạn không có quyền truy cập yêu cầu này.")
    return frappe.get_doc("Portal Item Request", name)


def _tim_yeu_cau_trung(customer: str, ten_hang: str, loai_tru: str | None) -> list:
    """NL-11.1 — so gần đúng với các yêu cầu ĐANG MỞ (chưa kết thúc) của
    cùng khách hàng. Dùng lại `kho/similarity.py` (E4) — ngưỡng 85%, so
    không dấu — thay vì viết một bản so khớp thứ hai."""
    filters = {
        "customer": customer,
        "trang_thai": ["not in", list(TRANG_THAI_KET_THUC)],
    }
    if loai_tru:
        filters["name"] = ["!=", loai_tru]
    rows = frappe.get_all(
        "Portal Item Request", filters=filters, fields=["name", "ten_hang"],
    )
    return [r.name for r in rows if similarity.la_gan_giong(ten_hang, r.ten_hang)]


@frappe.whitelist()
def portal_yeu_cau_save(data, name=None, file_urls=None) -> dict:
    """API Spec §2.3 — tạo mới (thiếu `name`) hoặc sửa (kèm `name`, chỉ khi
    còn ở trạng thái "Mới"). `customer`/`nguoi_yeu_cau` LUÔN suy từ phiên,
    không bao giờ nhận từ client (xem CLAUDE.md quyết định 7).
    """
    customer = get_portal_customer()
    payload = _parse_yeu_cau_payload(data)
    name = name or payload.get("name")
    urls = file_urls if file_urls is not None else payload.get("file_urls")
    if isinstance(urls, str):
        urls = frappe.parse_json(urls)
    urls = urls or []

    if name:
        doc = _yeu_cau_cua_khach(name, customer)
        if doc.trang_thai != "Mới":
            frappe.throw(
                "Chỉ sửa được yêu cầu khi còn ở trạng thái Mới.",
                frappe.ValidationError,
            )
    else:
        doc = frappe.new_doc("Portal Item Request")
        doc.customer = customer
        doc.nguoi_yeu_cau = frappe.session.user
        # Gán tường minh trước insert() — Portal Item Request KHÔNG dùng
        # Frappe Workflow (xem controller), nên đây KHÔNG phải bẫy
        # WorkflowPermissionError của các epic trước; chỉ để
        # _kiem_chuyen_trang_thai() thấy is_new() với trang_thai đã đúng.
        doc.trang_thai = "Mới"

    for f in YEU_CAU_FIELDS:
        if f in payload:
            doc.set(f, payload.get(f))

    if not doc.ngay_can:
        doc.ngay_can = frappe.utils.add_days(frappe.utils.nowdate(), 7)

    # F-4: vat_tu_kho là Link do CLIENT chọn — xác nhận thuộc kho của chính
    # khách này TRƯỚC khi ghi, link validation của Frappe chỉ kiểm tồn tại.
    if doc.vat_tu_kho:
        _vat_tu_thuoc_khach(doc.vat_tu_kho, customer)

    # Kiểm đính kèm TRƯỚC khi ghi bất cứ gì — TC-E6-05 đòi hỏi ba ca lỗi
    # (thiếu dvt / 6 file / file 11MB) đều chặn sạch, không tạo bản ghi rác.
    dinh_kem_moi = _kiem_va_lay_dinh_kem(urls, _dem_dinh_kem_hien_co(doc.name), doc.name)

    la_tao_moi = doc.is_new()
    if la_tao_moi:
        doc.sla_den_han = cong_gio_lam_viec(frappe.utils.now_datetime(), sla_yeu_cau_gio())
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    for f in dinh_kem_moi:
        frappe.db.set_value(
            "File", f.name,
            {"attached_to_doctype": "Portal Item Request", "attached_to_name": doc.name},
            update_modified=False,
        )

    # loai_tru=doc.name LUÔN LUÔN, kể cả khi vừa tạo mới: bản ghi vừa insert
    # đã nằm trong tập "đang mở" của chính khách này, và tên hàng của nó
    # trùng TUYỆT ĐỐI với chính nó — không loại trừ sẽ khiến MỌI yêu cầu mới
    # tự báo trùng với chính mình.
    canh_bao_trung = _tim_yeu_cau_trung(customer, doc.ten_hang, loai_tru=doc.name)

    if la_tao_moi:
        bao_yeu_cau_moi(customer, doc.name, doc.ten_hang)

    return {"name": doc.name, "canh_bao_trung": canh_bao_trung}


@frappe.whitelist()
def portal_yeu_cau_cancel(name, ly_do) -> dict:
    """API Spec §2.3 — chỉ khi trạng thái chưa kết thúc (BR-Y4: đóng, không
    xoá); `ly_do` bắt buộc, trạng thái đích "Khách huỷ"."""
    customer = get_portal_customer()
    doc = _yeu_cau_cua_khach(name, customer)
    if doc.trang_thai in TRANG_THAI_KET_THUC:
        frappe.throw(
            "Yêu cầu đã kết thúc, không huỷ được nữa.", frappe.ValidationError
        )
    ly_do = (ly_do or "").strip()
    if not ly_do:
        frappe.throw("Vui lòng nhập lý do huỷ.", frappe.ValidationError)

    doc.add_comment("Comment", f"[Portal] Khách huỷ yêu cầu: {ly_do}")
    doc.trang_thai = "Khách huỷ"
    doc.save(ignore_permissions=True)
    return {"trang_thai": doc.trang_thai}


@frappe.whitelist()
def portal_yeu_cau_tra_loi(name, noi_dung) -> dict:
    """NL-11.3 — khách trả lời câu hỏi của Miyano trên màn chi tiết (comment
    hai chiều). Khi yêu cầu đang "Cần thêm thông tin", trả lời xong tự
    chuyển về "Đang tìm nguồn" (DataDict §1.2: "Comment 2 chiều: dùng Comment
    chuẩn trên doctype, lộ qua endpoint"; BA §4.11 luồng chính).

    LỆCH SO VỚI 30_API_Spec.md §2.3 (ghi trong báo cáo bàn giao): API Spec chỉ
    liệt kê `portal_yeu_cau_list/save/cancel`, thiếu route cho hành vi "trả
    lời" mà chính DataDict/BA cùng epic mô tả là bắt buộc để cạnh "Cần thêm
    thông tin ⇄ Đang tìm nguồn" của BR-Y1 có thể xảy ra từ phía khách — đây
    là API Spec liệt kê thiếu, không phải chủ ý bỏ tính năng khỏi Phần A.
    """
    customer = get_portal_customer()
    doc = _yeu_cau_cua_khach(name, customer)
    if doc.trang_thai in TRANG_THAI_KET_THUC:
        frappe.throw(
            "Yêu cầu đã kết thúc, không trả lời được nữa.", frappe.ValidationError
        )

    noi_dung = (noi_dung or "").strip()
    if not noi_dung:
        frappe.throw("Vui lòng nhập nội dung trả lời.", frappe.ValidationError)

    doc.add_comment("Comment", f"[Khách hàng] {noi_dung}")
    if doc.trang_thai == "Cần thêm thông tin":
        doc.trang_thai = "Đang tìm nguồn"
        doc.save(ignore_permissions=True)
    return {"trang_thai": doc.trang_thai}


@frappe.whitelist()
def portal_yeu_cau_file(name, file_name) -> None:
    """F-3 (review) — tải đính kèm của một yêu cầu. Đường trực tiếp
    `/private/files/...` chỉ render cho đúng `File.owner` (`File.
    has_permission`: chủ sở hữu → True; khác chủ → `has_permission("read")`
    trên `Portal Item Request`, mà role `Customer` không có DocPerm nào —
    → False). Nhưng `portal_provision` cấp NHIỀU user portal cho MỘT
    Customer — người thứ hai của cùng bệnh viện (không phải người đã bấm
    upload) bị 403 khi mở đính kèm của chính yêu cầu đơn vị mình gửi. Kiểm
    theo CUSTOMER của yêu cầu (đúng nghĩa BR-Y5 "khách sở hữu xem được"),
    không theo `File.owner`.

    Nhận `file_name` — TÊN File (docname), KHÔNG PHẢI `file_url`: F-5 cho
    thấy nhiều File.name có thể trỏ chung một file_url (gộp theo nội dung),
    nên file_url không phải khoá tra an toàn cho một bản ghi đính kèm cụ
    thể. `portal_yeu_cau_detail` trả `dinh_kem` theo đúng hình dạng này.
    """
    customer = get_portal_customer()
    doc_customer = frappe.db.get_value("Portal Item Request", name, "customer")
    if doc_customer != customer:
        raise frappe.PermissionError("Bạn không có quyền tải đính kèm của yêu cầu này.")

    row = frappe.db.get_value(
        "File", file_name,
        ["attached_to_doctype", "attached_to_name", "file_name"],
        as_dict=True,
    )
    if (
        not row
        or row.attached_to_doctype != "Portal Item Request"
        or row.attached_to_name != name
    ):
        frappe.throw("Không tìm thấy đính kèm.", frappe.ValidationError)

    file_doc = frappe.get_doc("File", file_name)
    frappe.local.response.filename = file_doc.file_name
    frappe.local.response.filecontent = file_doc.get_content()
    frappe.local.response.type = "download"
