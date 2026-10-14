"""Lõi đặt hàng — dựng dòng hàng, định giá theo Price List của khách, tạo
Sales Order.

Tách khỏi `api/portal.py` ngày 18/08/2026 (bước 1,
`docs/superpowers/plans/2026-08-18-nen-phan-quyen-khoa-phong.md`) vì sắp có
đường thứ hai đi vào đây: quản lý bệnh viện DUYỆT một `Đề nghị mua` của khoa
phòng. Ở đường đó, người bấm nút KHÁC người đặt hàng, nên lõi không được suy
khách hàng từ phiên đăng nhập nữa — nó NHẬN `customer` làm tham số, và việc
xác định khách hàng thuộc về người gọi.

Hai đường định giá là hai đường sẽ lệch nhau. Chỉ có một — và từ spec
2026-10-09 (giá theo Price List) nó hỏi đúng MỘT nguồn: `bang_gia_khach`.
Cổng không còn định giá hay kiểm hạn mức theo hợp đồng khung.
"""

import frappe
from frappe.model.naming import validate_name
from frappe.utils import flt

from miyano_portal import bang_gia_khach
from miyano_portal.portal_dat_hang import (
    kiem_boi_so,
    kiem_ngay_giao,
    ngay_giao_mac_dinh,
)
from miyano_portal.portal_mua_le import (
    ITEM_GIU_CHO,
    LOAI_DON_BAO_GIA,
    can_chen_giu_cho,
    la_dong_giu_cho,
    resolve_ban_le_company,
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


def _insert_so_idempotent(so, request_id) -> dict:
    """Ghi `so` (chưa insert) rồi trả phong bì chuẩn, đúng một khuôn xử lý
    đua `UniqueValidationError` (xem giải thích gốc ở khối này trước khi
    tách). Trước Task 4 câu này viết "dùng CHUNG bởi cả hai nhánh HĐNT và
    Mua lẻ" — hai nhánh đó đã gộp làm một (`_xay_don`), chỉ còn một đường
    gọi tới đây.
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
        #
        # UAT phát hiện: BẮT ĐÚNG LOẠI vẫn chưa đủ. Đo bằng hai tiến trình
        # THẬT (hai kết nối CSDL riêng, không phải mô phỏng), tiến trình
        # thua vẫn ném UniqueValidationError thô ra ngoài — 6/6 lần lặp.
        # Nguyên nhân: MariaDB REPEATABLE READ. `so.insert()` phát hiện đúng
        # xung đột vì kiểm tra khoá duy nhất của INSERT luôn đọc bản mới
        # nhất ("current read"), bất kể snapshot. Nhưng câu SELECT thường
        # (không khoá) NGAY SAU ĐÓ để tra lại đơn gốc vẫn đọc theo snapshot
        # CŨ của giao dịch — snapshot đó chốt từ lần đọc ĐẦU TIÊN trong cùng
        # giao dịch (chính là `da_co` ở đầu `portal_order_place`), tức TRƯỚC
        # KHI tiến trình thắng cuộc commit. Nên `cu` ra `None` dù bản ghi đã
        # nằm trong CSDL thật, và nhánh `if not cu: raise` ở dưới biến một
        # cuộc đua đã xử lý đúng thành lỗi thô lộ ra ngoài.
        #
        # Vá: `for_update=True` ép câu SELECT này thành "current read" giống
        # hệt cách INSERT tự kiểm tra khoá — luôn thấy bản mới nhất đã
        # commit, không phụ thuộc snapshot cũ của giao dịch. Đơn gốc đã
        # commit rồi (đó là lý do ta nhận UniqueValidationError), nên khoá
        # này được cấp ngay, không chờ.
        cu = frappe.db.get_value(
            "Sales Order",
            {"custom_request_id": request_id},
            ["name", "grand_total"],
            as_dict=True,
            for_update=True,
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


def _xay_don(customer, aggregated, dat_ngoai, delivery_date,
             address, po, note, request_id):
    """MỘT hàm dựng đơn duy nhất của cổng; giá và tầng quyết định ở TỪNG
    DÒNG, theo Price List của khách (spec 2026-10-09 §3.2, §4.2).

    Hai loại dòng có mã, cộng dòng gõ tay:

      | Dòng                       | Xử lý                                   |
      |----------------------------|-----------------------------------------|
      | Có giá trong Price List    | `rate = price_list_rate` = giá bảng giá, |
      |                            | dấu `custom_nguon_gia = "Bảng giá"`      |
      | Chưa có giá                | `rate = price_list_rate = 0`, dấu        |
      |                            | `"Báo giá"`, Miyano báo giá sau          |
      | Chưa có mã (khách gõ tay)  | `so.flags.dong_dat_ngoai`, KHÔNG vào     |
      |                            | `items` — chỉ Quotation mang được dòng   |
      |                            | này (`bao_gia.tao_bao_gia`)              |

    "Có giá" hỏi `bang_gia_khach.gia_bang_gia_nhieu()` — đúng nguồn mà danh
    mục `portal_catalog_gop` đang dùng, nên khách không thể thấy một tầng
    trên màn lập phiếu rồi nhận một tầng khác trên đơn.

    Hợp đồng khung (Blanket Order) KHÔNG còn được hỏi ở đây (§4.2): không
    lấy giá từ hợp đồng, không kiểm hạn mức, không gắn `blanket_order` /
    `against_blanket_order` lên dòng (ERPNext tự chặn đặt vượt số lượng hợp
    đồng khi dòng mang liên kết đó), không ghi `custom_hdnt`, không suy
    `company` từ hợp đồng. Hệ quả đã được chấp nhận: `ordered_qty` trên hợp
    đồng ở ERP không còn tăng theo đơn từ cổng. Một mặt hàng hợp đồng có
    khai giá nhưng Price List của khách trống là dòng CHỜ BÁO GIÁ.

    Loại đơn (`custom_loai_don`) suy từ dòng: còn ít nhất một dòng chưa có
    giá hoặc một dòng gõ tay thì `"Mua lẻ"` (đi vòng báo giá), ngược lại
    `"Theo bảng giá"`.
    """
    # Spec 2026-10-09 §4.2 — giá và tầng của từng dòng đến từ Price List của
    # khách. Bảo đảm bảng riêng TRƯỚC khi tra: đơn phải mang đúng bảng đó
    # (mục 7.3), kể cả khi mọi dòng còn chờ báo giá.
    price_list = bang_gia_khach.dam_bao_bang_gia_rieng(customer)
    gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(customer, list(aggregated))

    # BR-O3 — báo HẾT trong một lần. `loi` là phong bì máy đọc được theo
    # `30_API_Spec` §1.1 (`ly_do` + số liệu kèm theo); văn xuôi cho
    # `frappe.throw` dựng từ chính `thong_diep` của các mục này, nên hai
    # đường không thể lệch nội dung nhau. GIỮ NGUYÊN, nhiều test đọc thẳng
    # `frappe.local.response["loi"]`.
    loi: list[dict] = []
    loi_ngay = kiem_ngay_giao(delivery_date)
    if loi_ngay:
        loi.append(loi_ngay)

    # Mỗi phần tử: {item_code, qty, rate, nguon_gia}.
    #   `nguon_gia` — dấu ghi lên `Sales Order Item.custom_nguon_gia`:
    #                 "Bảng giá" (có giá) / "Báo giá" (chưa có giá); `None`
    #                 cho dòng giữ chỗ kỹ thuật. Quyết định `custom_loai_don`.
    hop_le: list[dict] = []
    for item_code, qty in aggregated.items():
        if qty <= 0:
            loi.append({
                "item_code": item_code,
                "ly_do": "so_luong_khong_hop_le",
                "thong_diep": f"{item_code}: số lượng phải > 0",
            })
            continue
        # Mỗi mặt hàng chỉ báo MỘT lý do, xét theo thứ tự: bội số (lỗi nhập
        # liệu, khách sửa được ngay) → mã giữ chỗ → ngừng kinh doanh. "Chưa
        # có giá" KHÔNG còn là lỗi (spec 2026-10-09 §4.2): dòng đó thành
        # dòng chờ báo giá ở cuối vòng này.
        loi_boi_so = kiem_boi_so(item_code, qty)
        if loi_boi_so:
            loi.append(loi_boi_so)
            continue
        # review C-1 — chốt Ở ĐƯỜNG GHI, cạnh chốt danh mục ở
        # `portal_catalog_gop`. `ITEM_GIU_CHO` là chi tiết kỹ thuật nội bộ
        # (§3.4) mà hàm NÀY tự chèn vào `hop_le` phía dưới KHI CẦN (đơn toàn
        # hàng chưa có mã) — nhưng client cũng có thể gửi thẳng mã này trong
        # payload `items`, y như bất kỳ item_code nào khác. Không có chốt
        # này, nó vào `so.items` như một dòng khách "tự yêu cầu", rồi lọt vào
        # phép giao company của `resolve_ban_le_company()` — đúng ràng buộc
        # cứng mà `can_chen_giu_cho` dựng lên để CHÍNH hàm này tôn trọng khi
        # tự chèn, bị phá từ hướng khác nếu chỉ sửa danh mục mà bỏ qua đây.
        if la_dong_giu_cho(item_code):
            loi.append({
                "item_code": item_code,
                "ly_do": "mat_hang_giu_cho_khong_the_dat",
                "thong_diep": (
                    f"{item_code} là mã kỹ thuật nội bộ, không phải mặt hàng "
                    f"đặt được. Nếu không tìm thấy mã cần mua, dùng khối "
                    f"\"Không tìm thấy vật tư cần mua?\" để ghi thẳng tên hàng."
                ),
            })
            continue
        # Phòng thủ tầng hai, retarget theo §4.1: danh mục
        # `portal_catalog_gop` chỉ lọc `disabled=0` (KHÔNG còn lọc
        # `custom_ban_le_portal` — cờ đó không còn là điều kiện thành viên
        # danh mục, §6 "chỉ ngừng dùng để lọc"). Client có thể gửi THẲNG một
        # mã hàng bất kỳ tới đây — không tin payload, tự kiểm lại đúng điều
        # kiện danh mục THẬT SỰ đang dùng (disabled=0), không phải điều kiện
        # đã bỏ.
        if frappe.db.get_value("Item", item_code, "disabled"):
            loi.append({
                "item_code": item_code,
                "ly_do": "mat_hang_ngung_kinh_doanh",
                "thong_diep": f"{item_code} đã ngừng kinh doanh, không đặt được.",
            })
            continue
        # ---- PHÂN TẦNG THEO DÒNG (spec 2026-10-09 §3.2) -----------------
        # Có giá dương trong Price List của khách → dòng "Bảng giá", mang
        # đúng giá đó. Không có → dòng "Báo giá", `rate = 0`, sales điền giá
        # khi báo giá. Giá `<= 0` là "chưa có giá", không phải "bán 0 đồng"
        # — `gia_bang_gia_nhieu` chỉ trả mã có giá DƯƠNG.
        gia = gia_theo_ma.get(item_code)
        hop_le.append({
            "item_code": item_code, "qty": qty,
            "rate": gia or 0,
            "nguon_gia": (
                bang_gia_khach.NGUON_BANG_GIA if gia
                else bang_gia_khach.NGUON_BAO_GIA
            ),
        })

    dong_dat_ngoai: list[dict] = []
    for dn in dat_ngoai:
        ten_hang = (dn.get("ten_hang") or "").strip()
        dvt = (dn.get("dvt") or "").strip()
        # review Minor — `float()` ném `ValueError` CHƯA BẮT với đầu vào
        # không phải số (vd. khách/gõ nhầm "abc" vào ô số lượng, hoặc payload
        # bị sửa tay) — lỗi đó lọt thẳng thành HTTP 500 thay vì mã lỗi
        # `dat_ngoai_so_luong_khong_hop_le` đã có sẵn cho đúng tình huống
        # "số lượng không hợp lệ".
        try:
            so_luong = float(dn.get("so_luong") or 0)
        except (TypeError, ValueError):
            loi.append({
                "ly_do": "dat_ngoai_so_luong_khong_hop_le",
                "thong_diep": f"{ten_hang or dvt or 'Dòng đặt ngoài'}: số lượng không hợp lệ.",
            })
            continue
        if not ten_hang:
            loi.append({
                "ly_do": "dat_ngoai_thieu_ten_hang",
                "thong_diep": "Dòng đặt ngoài thiếu tên hàng.",
            })
            continue
        if not dvt:
            loi.append({
                "ly_do": "dat_ngoai_thieu_dvt",
                "thong_diep": f"{ten_hang}: thiếu đơn vị tính.",
            })
            continue
        if so_luong <= 0:
            loi.append({
                "ly_do": "dat_ngoai_so_luong_khong_hop_le",
                "thong_diep": f"{ten_hang}: số lượng phải > 0.",
            })
            continue
        # CHÍN TRƯỜNG CR-03 PHẢI ĐI THEO (chủ đầu tư báo 06/09/2026: "vẫn
        # chưa nhìn thấy thông tin khách đưa cho hàng chưa có trong hệ thống
        # ở phần back Miyano, không thấy ví dụ như trường ảnh mặt hàng").
        #
        # Trước bản này danh sách trắng chỉ có BỐN trường, nên model, hãng,
        # nước SX, quy cách, NCC, giá đang mua, ẢNH, cờ không-có-ảnh và mô tả
        # nhận dạng đều bị bỏ lại ở phiếu và KHÔNG BAO GIỜ tới đơn hàng.
        # Miyano — người phải đi tìm nguồn — không có gì để đọc, đúng thứ
        # CR-03 sinh ra để đưa cho họ.
        #
        # Hỏng KIỂU KHÓ THẤY NHẤT: dữ liệu CÓ ở phiếu, người tiêu thụ CÓ ở
        # Desk (`sales_order.js`), chỉ cây cầu giữa hai đầu lặng lẽ đánh rơi.
        # Không lỗi, không cảnh báo — khối bên Desk lọc theo chính những
        # trường này, thấy rỗng hết nên thoát sớm và không vẽ gì.
        #
        # DÙNG DANH SÁCH TƯỜNG MINH, không `dn.copy()`: `dn` là dict client
        # gửi lên, chép cả cụm là mở đường cho client tự đặt `item_khop` /
        # `da_xu_ly` — hai field QUYẾT ĐỊNH việc đơn có xác nhận được không
        # (`kiem_dat_ngoai_da_xu_ly`). Thêm trường mới thì thêm vào đây.
        dong_dat_ngoai.append({
            "ten_hang": ten_hang, "dvt": dvt, "so_luong": so_luong,
            "ghi_chu": (dn.get("ghi_chu") or "").strip(),
            "model_ma": (dn.get("model_ma") or "").strip(),
            "hang_san_xuat": (dn.get("hang_san_xuat") or "").strip(),
            "nuoc_san_xuat": (dn.get("nuoc_san_xuat") or "").strip(),
            "quy_cach": (dn.get("quy_cach") or "").strip(),
            "ncc_hien_tai": (dn.get("ncc_hien_tai") or "").strip(),
            "gia_hien_tai": flt(dn.get("gia_hien_tai")),
            "anh": dn.get("anh") or None,
            "khong_co_anh": 1 if dn.get("khong_co_anh") else 0,
            "mo_ta_nhan_dang": (dn.get("mo_ta_nhan_dang") or "").strip(),
        })

    if loi:
        frappe.local.response["loi"] = loi
        frappe.throw(
            "<br>".join(d["thong_diep"] for d in loi), frappe.ValidationError
        )
    frappe.local.response.pop("loi", None)

    # §3.4 — đơn TOÀN hàng chưa có mã: chèn đúng MỘT dòng giữ chỗ để ERPNext
    # lưu được đơn. Phải đặt TRƯỚC `resolve_ban_le_company()` vì hàm đó suy
    # company từ chính `aggregated`. Xem `can_chen_giu_cho` để biết vì sao
    # điều kiện là "giỏ không còn hàng thật", không phải "có dòng đặt ngoài".
    if can_chen_giu_cho(aggregated, dong_dat_ngoai):
        if not frappe.db.exists("Item", ITEM_GIU_CHO):
            frappe.throw(
                "Hệ thống chưa sẵn sàng nhận đơn toàn hàng chưa có mã. "
                "Vui lòng liên hệ Miyano.",
                frappe.ValidationError,
            )
        aggregated[ITEM_GIU_CHO] = 1
        # `hop_le` (dựng ở vòng lặp phía trên, TRƯỚC khi `dong_dat_ngoai` tồn
        # tại) là nguồn DUY NHẤT vòng lặp `so.append("items", ...)` bên dưới
        # đọc — ghi riêng vào `aggregated` (cho `resolve_ban_le_company`) mà
        # không ghi vào đây thì dòng giữ chỗ không bao giờ thành một dòng
        # thật trên đơn, và `so.items` vẫn rỗng như trước khi có Task 5.
        hop_le.append({"item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0, "nguon_gia": None})

    # ---- suy `company` -------------------------------------------------
    #
    # §3 — dòng "đặt ngoài" nằm TRÊN CHÍNH phiếu mua, không tự thành một
    # chứng từ riêng: `company`/kho giao vẫn suy từ CÁC MẶT HÀNG THẬT trong
    # giỏ. Xác nhận thực nghiệm trên bench (không phải suy diễn): ERPNext
    # không lưu được một Sales Order với bảng `items` RỖNG (crash ở
    # `accounts_controller.set_payment_schedule`, `grand_total` là `None`
    # vì `calculate_taxes_and_totals` không có gì để tính) — nên giỏ
    # `items` (KHÔNG tính `dat_ngoai`) vẫn phải khác rỗng.
    #
    # Spec 2026-10-09 §4.2 — MỌI đơn suy `company` qua
    # `resolve_ban_le_company()`; hợp đồng khung không còn quyết định
    # company của đơn. Hàm đó TỰ rơi về `default_company` khi phép giao
    # rỗng (chủ dự án đã quyết: đừng chốt cứng company vào mặt khách), để
    # nhân viên back-office sửa trên đơn nháp nếu cần. Chỉ còn dừng ở đây
    # khi site KHÔNG CÓ Company nào — lúc đó ERPNext không lưu nổi một
    # Sales Order thật (`company` là `reqd=1`), và đây đúng là lỗi cấu hình
    # hệ thống, không phải lỗi của giỏ hàng khách.
    company = resolve_ban_le_company(list(aggregated.keys()))
    if not company:
        frappe.throw(
            "Hệ thống chưa có công ty (Company) nào được cấu hình. "
            "Vui lòng liên hệ quản trị viên hệ thống.",
            frappe.ValidationError,
        )

    # ---- suy `custom_loai_don` ở ĐẦU ĐƠN (spec 2026-10-09 §3.2, §4.2) --
    #
    # Còn ít nhất một dòng chưa có giá ("Báo giá"), một dòng gõ tay, hoặc
    # đơn chỉ có dòng giữ chỗ (`nguon_gia = None`) thì đơn PHẢI đi qua vòng
    # báo giá của Miyano → "Mua lẻ" (giữ nguyên chuỗi cũ, nhiều chốt đang
    # đọc đúng nó). Mọi dòng đều có giá → "Theo bảng giá".
    #
    # ĐÂY LÀ CHỖ DUY NHẤT ĐÓNG DẤU, và dấu đóng MỘT LẦN lúc lập đơn. Mọi
    # CHỐT đọc dấu này đều đi qua `portal_mua_le.di_vong_bao_gia()` — đừng
    # so chuỗi `== "Mua lẻ"` ở chỗ mới: giá trị đó KHÔNG có nghĩa "đơn mua
    # lẻ", nó có nghĩa "đơn còn dòng chờ báo giá".
    con_dong_chua_co_gia = bool(dong_dat_ngoai) or any(
        d["nguon_gia"] != bang_gia_khach.NGUON_BANG_GIA for d in hop_le
    )

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = delivery_date
    # §4.2 / mục 7.3 — đơn LUÔN mang bảng giá riêng của khách, kể cả khi
    # mọi dòng còn chờ báo giá: đó là bảng nhân viên Miyano nhìn và ghi vào
    # khi báo giá.
    so.selling_price_list = price_list
    # Ruling R19 — cổng có ĐÚNG MỘT nguồn giá. Không tắt thì một Pricing Rule
    # bán hàng của ERPNext khớp mặt hàng/khách sẽ chiết khấu `rate` ngay lúc
    # lưu đơn (và mỗi lần nhân viên lưu lại trên Desk): khách thấy một giá
    # trên màn đặt hàng, nhận một giá khác trên đơn, và dòng "Bảng giá" thôi
    # bằng giá bảng. Cờ nằm trên ĐƠN nên phủ cả dòng thêm sau khi khớp mã.
    so.ignore_pricing_rule = 1
    so.custom_nguon_don = "Client Portal"
    # §4.2 — đơn mới từ cổng không còn mang hợp đồng khung ở đầu đơn.
    so.custom_hdnt = None
    so.custom_loai_don = (
        LOAI_DON_BAO_GIA if con_dong_chua_co_gia
        else bang_gia_khach.LOAI_DON_BANG_GIA
    )
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
    for d in hop_le:
        # Ship each line from THIS item's own default warehouse (where its
        # stock actually is), never a single warehouse forced onto the whole
        # order - otherwise items stocked elsewhere (e.g. UAT items in "Kho
        # Miyano - MYN") end up shipping from an empty warehouse and the
        # Delivery Note raises NegativeStockError.
        item_warehouse = _resolve_item_warehouse(d["item_code"], company)
        if not item_warehouse:
            frappe.throw(
                f"Không tìm thấy kho giao hàng cho mặt hàng {d['item_code']} tại "
                f"công ty {company}. Vui lòng liên hệ quản trị viên hệ thống."
            )
        # R15 — cổng đặt theo đơn vị GỐC và giá bảng tính theo đơn vị gốc
        # (`gia_bang_gia_nhieu`). ERPNext thì mặc định `uom` của dòng mới
        # theo `Item.sales_uom`; để nó tự điền, một mã khai `sales_uom` là
        # thùng sẽ ra dòng "3 thùng" mang giá của MỘT đơn vị gốc.
        dvt_goc = frappe.db.get_value("Item", d["item_code"], "stock_uom")
        dong = {
            "item_code": d["item_code"], "qty": d["qty"], "rate": d["rate"],
            "uom": dvt_goc, "stock_uom": dvt_goc, "conversion_factor": 1,
            "warehouse": item_warehouse, "delivery_date": delivery_date,
            "custom_nguon_gia": d["nguon_gia"],
            # Đặt CẢ HAI `rate` và `price_list_rate` (§4.2):
            # `price_list_rate` là thứ ERPNext coi là nguồn khi tính lại
            # dòng lúc `insert()`.
            #
            # BẪY ERPNext với dòng giá 0: `taxes_and_totals.
            # calculate_item_values` có nhánh `elif item.price_list_rate:
            # if not item.rate: item.rate = price_list_rate` — `rate = 0` là
            # FALSY, nên nếu để `price_list_rate` là `None` thì
            # `set_missing_item_details` tự tra bảng giá của đơn rồi ERPNext
            # ÂM THẦM thay 0 bằng giá đó. Đơn giờ luôn mang bảng giá của
            # chính khách, và phép tra của ERPNext KHÔNG trùng luật với
            # `gia_bang_gia_nhieu` — nên dòng chờ báo giá phải mang 0 TƯỜNG
            # MINH (`set_missing_item_details` chỉ điền khi field đang là
            # `None`). Không gắn `blanket_order` / `against_blanket_order`.
            "price_list_rate": d["rate"],
        }
        so.append("items", dong)
    # Sales Order không còn bảng dòng gõ tay (patch v1_43): dòng đã kiểm đi
    # theo đơn CHƯA lưu qua `flags`, để `bao_gia.tao_bao_gia` chép sang
    # `Quotation.custom_dat_ngoai`.
    so.flags.dong_dat_ngoai = dong_dat_ngoai
    return so


def tao_sales_order(
    customer: str, *, mode: str = "hdnt", contract=None, items=None,
    dat_ngoai=None, po=None, delivery_date=None, note=None, address=None,
    request_id=None, khoa_phong=None, ma=None,
) -> dict:
    """Trả {"sales_order": str, "da_ton_tai": bool, "total": float}

    Lõi tạo Sales Order cho cổng khách hàng — tách khỏi `portal_order_place`
    (xem docstring đầu file). `customer` là THAM SỐ, không suy từ
    `frappe.session.user`: việc xác định khách hàng thuộc TRÁCH NHIỆM của
    người gọi (endpoint cổng suy từ phiên đăng nhập qua `get_portal_customer`;
    đường duyệt đề nghị mua sau này sẽ suy từ chính `Đề nghị mua` được duyệt).

    `ma` — [Task 9, chủ đầu tư chốt 21/08/2026] TÊN của Sales Order sắp
    tạo, chính là `ma_de_xuat` của phiếu đứng sau nó
    (`DXA-HUYETHOC-260821-01`). KHÔNG BẮT BUỘC: thiếu thì rơi về đặt tên
    gốc `SAL-ORD-...` — đơn Miyano tự lập trong Desk không có mã ngắn
    khách + mã khoa nên không suy ra được mã, và đó là điều kiện TƯƠNG
    THÍCH NGƯỢC chứ không phải một trường hợp biên. Người gọi phải truyền
    LẠI mã ĐÃ CÓ của phiếu, tuyệt đối không gọi `sinh_ma()` lần nữa: hàm
    đó cấp số qua `getseries`, gọi lại sẽ ra số khác và đơn mang một mã
    không khớp phiếu nào.

    `khoa_phong` — ghi lên `Sales Order.custom_khoa_phong` (Task 8), nguồn
    DUY NHẤT cho mọi phép lọc theo khoa về sau (xem docstring patch
    `them_khoa_phong_vao_don_hang`). `None` = đơn cấp bệnh viện, không quy về
    khoa nào — hợp lệ (đường duyệt đề nghị mua của quản lý bệnh viện, hoặc
    khách chưa dùng mô hình khoa phòng).

    `mode` — [KHÔNG CÒN TÁC DỤNG]. Hàm dựng đơn chỉ có một và quyết định
    theo TỪNG DÒNG (xem `_xay_don`), nên không còn "chế độ" nào để chọn.
    Tham số ở lại vì nó là tham số của endpoint công khai
    `portal_order_place` mà client đang chạy thật vẫn gửi, và nhiều lời gọi
    trong bộ test vẫn truyền nó — giữ một tham số bị làm ngơ tường minh an
    toàn hơn là làm gãy chữ ký. Giá trị vẫn được kiểm hợp lệ để một client
    gửi sai chính tả không lặng lẽ đi tiếp.

    `contract` — [KHÔNG CÒN QUYẾT ĐỊNH GÌ VỀ ĐƠN, spec 2026-10-09 §4.2]. Đơn
    không còn lấy giá, kiểm hạn mức hay ghi `custom_hdnt` theo hợp đồng
    khung. Tham số ở lại cùng lý do với `mode`; khi người gọi CÓ truyền thì
    hợp đồng đó vẫn phải thuộc đúng `customer` (xem phép kiểm bên dưới).
    """
    mode = (mode or "hdnt").strip()
    if mode not in ("hdnt", "ban_le"):
        frappe.throw("Chế độ đặt hàng không hợp lệ.", frappe.ValidationError)
    # BR-R1 (chốt "khách phải được bật cờ mới mua lẻ được") đã bỏ hẳn 21/08
    # — xem `portal_mua_le.py` đầu file. Mọi khách đều đi thẳng qua đây.

    # BR-O12 — chống tạo đơn trùng. Bắt buộc, không tuỳ chọn: để tuỳ chọn thì
    # một client cũ vẫn tạo được đơn trùng và quy tắc chỉ còn là trang trí.
    # Mỗi Sales Order một `request_id`: giỏ trộn được tầng gọi tách thành
    # hai lần gọi hàm này, mỗi lần một mã riêng (`request_id` gốc + hậu tố
    # `tach_phieu.HAU_TO_GIA` / `HAU_TO_BAO_GIA`, spec 2026-10-09 §4.1).
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

    # Chỉ kiểm khi người gọi THẬT SỰ truyền một hợp đồng (Ruling P19: phiếu
    # đề xuất tạo qua UI thật luôn có `hdnt = None`, và `frappe.db.get_value
    # ("Blanket Order", None, ...)` trả `None` → PermissionError chỉ vào sai
    # chỗ). `contract` không còn đi vào đơn (spec 2026-10-09 §4.2), nhưng
    # phép kiểm quyền sở hữu GIỮ NGUYÊN: một client gửi tên hợp đồng của
    # khách khác vẫn phải bị từ chối rõ ràng, không được đi tiếp như thể
    # tham số đó hợp lệ.
    if contract:
        bo = frappe.db.get_value(
            "Blanket Order", contract, ["customer"], as_dict=True
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
    if isinstance(dat_ngoai, str):
        dat_ngoai = frappe.parse_json(dat_ngoai)
    dat_ngoai = dat_ngoai or []
    # Task 4 — chốt "Dòng đặt ngoài chỉ áp dụng cho chế độ Mua lẻ" ĐÃ BỎ.
    # Chính nó là vách ngăn: một khoa cần vừa hàng trong hợp đồng vừa hàng
    # Miyano chưa có mã phải chia làm hai đơn, hoặc không đặt được gì. Dòng
    # đặt ngoài giờ đi kèm được với MỌI giỏ (xem `_xay_don`).
    if not items and not dat_ngoai:
        # ERPNext không lưu được `Sales Order` với bảng `items` rỗng (xác
        # nhận thực nghiệm, xem docstring `_xay_don`). Trước spec
        # 15/08 điều đó được dịch thẳng thành "phải có ít nhất một mặt hàng
        # thật" — nhưng khách cần TOÀN hàng Miyano chưa có mã thì không đặt
        # được gì cả, ngược nguyên tắc "khách đặt hàng, Miyano có trách
        # nhiệm gửi". §3.4: giỏ toàn dòng đặt ngoài đi tiếp, `_xay_don`
        # chèn một dòng giữ chỗ để ERPNext lưu được đơn.
        #
        # Giỏ rỗng HOÀN TOÀN (không hàng thật, không dòng đặt ngoài) vẫn bị
        # từ chối: không có nhu cầu nào để phục vụ.
        frappe.throw("Giỏ hàng trống.")

    # BR-O13 — mặc định +2 NGÀY LÀM VIỆC (bỏ T7/CN), không phải +2 ngày lịch.
    delivery_date = delivery_date or ngay_giao_mac_dinh()

    # Gộp giỏ theo `item_code`: một mặt hàng gửi lên nhiều dòng thành MỘT
    # dòng đơn với tổng số lượng — bội số đặt hàng được kiểm trên tổng đó,
    # và giá/tầng được tra một lần cho mỗi mã.
    #
    # review C-2 — CHUẨN HOÁ `item_code` VỀ `Item.name` CHÍNH TẮC ngay tại
    # đây, TRƯỚC khi gộp. `tabItem` chạy collation `utf8mb4_unicode_ci`
    # (case-insensitive, PAD SPACE): MariaDB coi "VT0005", "vt0005",
    # "VT0005 " là CÙNG MỘT BẢN GHI, nhưng khoá gộp `aggregated` là chuỗi
    # Python thô — không chuẩn hoá thì "VT0005" và "vt0005" tách thành HAI
    # khoá, tức hai dòng đơn cho cùng một mặt hàng thật, mỗi dòng qua phép
    # kiểm bội số ĐỘC LẬP; và "vt0005" tra hụt giá trong
    # `gia_bang_gia_nhieu` (kết quả khoá theo `Item.name` chính tắc, so
    # bằng Python) nên một dòng CÓ giá bị đóng dấu "Báo giá".
    # Mã không tra ra Item thật bị từ chối NGAY, không để lọt xuống các
    # tầng kiểm phía dưới rồi lộ ra một thông điệp khó hiểu về một mặt hàng
    # không tồn tại.
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

    so = _xay_don(
        customer, aggregated, dat_ngoai, delivery_date,
        address, po, note, request_id,
    )
    if so.flags.dong_dat_ngoai:
        # Người gọi chia giỏ trước (`bao_gia.can_bao_gia`): giỏ có dòng gõ tay
        # đi Quotation. Tới đây là người gọi bỏ qua bước chia đó.
        frappe.throw(
            "Hàng chưa có trong danh mục phải gửi qua yêu cầu báo giá, "
            "không đặt thẳng thành đơn hàng.",
            frappe.ValidationError,
        )

    # Khoa phòng đứng tên đơn — nguồn của MỌI phép lọc theo khoa về sau
    # (phiếu giao, hoá đơn, biên bản kiểm đều lọc qua đơn cha, không có
    # field riêng). `None` = đơn cấp bệnh viện, chỉ quản lý thấy.
    #
    # Vòng sửa 1 (C1, review độc lập) — kiểm CẢ khoa↔khách hàng LẪN
    # `active`. Bản trước chỉ kiểm khoa↔khách hàng: một khoa đã bị quản lý
    # TẮT (`Customer Department.active = 0`, ví dụ khoa vừa giải thể/sáp
    # nhập) vẫn đóng dấu được lên đơn mới — đơn đó sẽ không ai còn "đúng
    # khoa" để mở, cùng lỗ với đơn CŨ chưa gắn khoa (`TestDonCuKhongGanKhoa`)
    # nhưng lần này KHÔNG đọc được ngay từ MỌI THÀNH VIÊN của khoa đó, kể cả
    # người vừa đặt.
    if khoa_phong:
        kp = frappe.db.get_value(
            "Customer Department", khoa_phong, ["customer", "active"], as_dict=True
        )
        if not kp or kp.customer != customer or not kp.active:
            raise frappe.PermissionError("Khoa phòng không thuộc đơn vị của bạn.")
        so.custom_khoa_phong = khoa_phong

    if ma:
        # Task 9 — CHỈ CÓ MỘT ĐƯỜNG ĐÚNG để ép tên trong Frappe v15:
        # `name` + `flags.name_set`. `Document.set_new_name()`
        # (`frappe/model/document.py:530`) thoát sớm khi thấy cờ đó; gán
        # `name` mà QUÊN cờ thì `set_new_name()` chạy tiếp, `naming_series`
        # của Sales Order ghi đè và mã bị vứt IM LẶNG — hỏng kiểu tệ nhất
        # vì đơn vẫn tạo được, chỉ mang tên khác, và một bài test nhìn
        # thoáng vẫn xanh.
        #
        # Cờ này cũng làm Frappe bỏ luôn bước đặt tên cho các DÒNG CON —
        # vô hại: `BaseDocument.db_insert()` tự đặt tên hash cho dòng nào
        # chưa có (`base_document.py:556`), đúng cách `frappe/api/v2.py`
        # dùng chính cặp `name` + `name_set` này.
        #
        # Trùng tên thì NỔ (`DuplicateEntryError`, KHÔNG phải
        # `UniqueValidationError` nên khối `except` chống-trùng-request_id
        # trong `_insert_so_idempotent` cố ý không nuốt nó): hệ thống có
        # hai đơn mà chỉ một cái mang mã khách đang cầm là tình huống phải
        # ồn ào, không được âm thầm cấp một tên khác rồi báo thành công.
        #
        # Vòng sửa 1 (review độc lập) — `flags.name_set` làm `Document.
        # set_new_name()` thoát sớm, tức ĐI VÒNG QUA `validate_name` mà
        # đường đặt tên bình thường luôn chạy qua. `ma_de_xuat` dựng từ
        # `Customer.custom_ma_ngan` + `Customer Department.ma_khoa`, CẢ HAI
        # là text nhân viên Miyano tự gõ ở Desk — nên một ký tự lạc (`<`,
        # `>`, khoảng trắng thừa) chui thẳng vào KHOÁ CHÍNH của Sales
        # Order, nơi nó đi vào URL, tên file PDF và mọi liên kết. Gọi lại
        # đúng hàm đó thay vì tự viết một phép làm sạch thứ hai: nó vừa
        # `.strip()` vừa từ chối ký tự cấm, và nếu Frappe siết thêm luật
        # thì đường này siết theo.
        so.name = validate_name("Sales Order", ma)
        so.flags.name_set = True

    return _insert_so_idempotent(so, request_id)
