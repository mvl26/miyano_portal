"""Lõi đặt hàng — dựng dòng hàng, kiểm hạn mức HĐNT, định giá, tạo Sales Order.

Tách khỏi `api/portal.py` ngày 18/08/2026 (bước 1,
`docs/superpowers/plans/2026-08-18-nen-phan-quyen-khoa-phong.md`) vì sắp có
đường thứ hai đi vào đây: quản lý bệnh viện DUYỆT một `Đề nghị mua` của khoa
phòng. Ở đường đó, người bấm nút KHÁC người đặt hàng, nên lõi không được suy
khách hàng từ phiên đăng nhập nữa — nó NHẬN `customer` làm tham số, và việc
xác định khách hàng thuộc về người gọi.

Hai đường tính giá và kiểm hạn mức là hai đường sẽ lệch nhau. Chỉ có một.
"""

import frappe
from frappe.model.naming import validate_name

from miyano_portal import gia_hdnt
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
    nguon_gia_theo_ma_cho_khach,
)
from miyano_portal.portal_context import han_muc_con, ten_khoa_da_tieu
from miyano_portal.portal_dat_hang import (
    kiem_boi_so,
    kiem_ngay_giao,
    ngay_giao_mac_dinh,
)
from miyano_portal.portal_mua_le import (
    ITEM_GIU_CHO,
    can_chen_giu_cho,
    la_dong_giu_cho,
    resolve_ban_le_company,
)
from miyano_portal.portal_thong_bao import bao_thieu_gia


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


def _selling_price_list_mac_dinh() -> str:
    """Thiết kế lại mua lẻ §4.5 — `Sales Order.selling_price_list` vẫn
    `reqd=1` ở tầng ERPNext (không phải field app này khai), nên đơn mua lẻ
    vẫn cần MỘT price list hợp lệ để insert được, dù không còn dùng nó để
    TRA GIÁ (rate = 0, sales điền sau). KHÔNG dùng `price_list_ban_le()`
    (Miyano Portal Settings) cho việc này nữa — §4.1 đã "ngừng phụ thuộc"
    field đó cho nhánh mua lẻ; dùng lại đúng price list mặc định hệ thống
    (`Selling Settings.selling_price_list`, ERPNext tự set khi cài đặt),
    rơi về "Standard Selling" nếu Settings đó trống."""
    return frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"


def _xay_don(customer, contract, aggregated, dat_ngoai, delivery_date,
             address, po, note, request_id):
    """Task 4 (gộp luồng đặt hàng, 21/08/2026) — MỘT hàm dựng đơn duy nhất,
    quyết định hạ xuống TỪNG DÒNG.

    Thay `_xay_don_hdnt` + `_xay_don_ban_le` (đã xoá). Hai hàm đó rẽ theo
    tham số `mode` ở ĐẦU HÀM, tức "đơn này theo hợp đồng hay chờ báo giá"
    được chốt MỘT LẦN CHO CẢ ĐƠN — chính là mô hình cấp-ĐƠN mà cả kế hoạch
    này sinh ra để xoá (cùng họ với `Portal De Xuat Mua.loai_don` đã bỏ ở
    Task 2). Hai vách ngăn nó dựng lên, cả hai đều bị xoá ở đây:

      * `mode="hdnt"` từ chối thẳng mọi dòng `dat_ngoai` ("Dòng đặt ngoài
        chỉ áp dụng cho chế độ Mua lẻ") — nên một giỏ vừa có hàng hợp đồng
        vừa có hàng chưa có mã KHÔNG đặt được;
      * `mode="ban_le"` từ chối thẳng mọi mặt hàng đang thuộc hợp đồng còn
        hiệu lực (BR-R7) — nên cùng giỏ đó cũng không đi lối kia được.
        BR-R7 sinh ra để chặn "khách hết hạn mức né sang mua lẻ"; dưới một
        hàm dựng DUY NHẤT nó không còn cần thiết vì không còn "lối kia" để
        né: dòng thuộc hợp đồng LUÔN được định giá theo hợp đồng và LUÔN bị
        trừ hạn mức, dù người gọi có nghĩ mình đang mua lẻ hay không.

    Ba loại dòng (§13 spec, bảng của Task 4):

      | Dòng                  | Xử lý                                     |
      |-----------------------|-------------------------------------------|
      | Có trong hợp đồng     | giá hợp đồng, gắn `blanket_order`, trừ hạn mức |
      | Có mã, ngoài hợp đồng | `rate = 0`, Miyano báo giá sau            |
      | Chưa có mã            | vào `custom_dat_ngoai`, KHÔNG vào `items` |

    "Dòng nào thuộc hợp đồng nào" hỏi `nguon_gia_theo_ma_cho_khach()` —
    ĐÚNG hàm mà `Portal De Xuat Mua._suy_nguon_gia()` (màn lập phiếu) và
    `api/portal.portal_catalog_gop` (màn tìm kiếm) đang dùng. Ba nơi cùng
    một luật (Ruling P14: customer-wide, hết hạn sớm nhất thắng, trùng
    `to_date` thì `name` nhỏ hơn thắng; Ruling P18: "còn hiệu lực" là
    `docstatus == 1`). Tự viết lại luật ở đây là dựng đúng thứ Task 2/3 đã
    tách ra để tránh: khách thấy một tầng trên màn lập phiếu rồi nhận một
    tầng khác trên đơn.

    `contract` KHÔNG còn quyết định gì về từng dòng — nó chỉ còn là thứ
    người gọi CŨ truyền vào để ghi `custom_hdnt` khi không suy được. Xem
    `tao_sales_order` để biết vì sao nó vẫn được kiểm quyền sở hữu.
    """
    thang_cuoc = nguon_gia_theo_ma_cho_khach(customer)
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")

    # BR-O3 — báo HẾT trong một lần. `loi` là phong bì máy đọc được theo
    # `30_API_Spec` §1.1 (`ly_do` + số liệu kèm theo); văn xuôi cho
    # `frappe.throw` dựng từ chính `thong_diep` của các mục này, nên hai
    # đường không thể lệch nội dung nhau. GIỮ NGUYÊN, nhiều test đọc thẳng
    # `frappe.local.response["loi"]`.
    loi: list[dict] = []
    loi_ngay = kiem_ngay_giao(delivery_date)
    if loi_ngay:
        loi.append(loi_ngay)

    # Mỗi phần tử: {item_code, qty, rate, hop_dong, gan_hop_dong}.
    #   `hop_dong`     — hợp đồng THẮNG CUỘC của dòng (None = tầng 2). Quyết
    #                    định `company`/`custom_hdnt`/`custom_loai_don`.
    #   `gan_hop_dong` — hợp đồng GẮN LÊN DÒNG ĐƠN, None cả với dòng hợp
    #                    đồng KHÔNG GIỚI HẠN (BR-O15, xem dưới).
    hop_le: list[dict] = []
    for item_code, qty in aggregated.items():
        if qty <= 0:
            loi.append({
                "item_code": item_code,
                "ly_do": "so_luong_khong_hop_le",
                "thong_diep": f"{item_code}: số lượng phải > 0",
            })
            continue
        # Mỗi mặt hàng chỉ báo MỘT lý do, xét theo thứ tự này:
        #   bội số  — lỗi nhập liệu, khách sửa được ngay; và kiểm hạn mức
        #             trên một số lượng sai bội số cho ra `con_lai` gây
        #             hiểu nhầm;
        #   giá     — bế tắc tuyệt đối, giảm số lượng không cứu được;
        #   hạn mức — xét sau cùng, khi số lượng đã hợp lệ và hàng đã có giá.
        loi_boi_so = kiem_boi_so(item_code, qty)
        if loi_boi_so:
            loi.append(loi_boi_so)
            continue
        # review C-1 — chốt Ở ĐƯỜNG GHI, cạnh chốt danh mục ở
        # `portal_catalog_ban_le`. `ITEM_GIU_CHO` là chi tiết kỹ thuật nội bộ
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
        # `portal_catalog_ban_le` giờ chỉ lọc `disabled=0` (KHÔNG còn lọc
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
        # ---- PHÂN TẦNG THEO DÒNG (thay cho BR-R7 + rẽ nhánh theo `mode`) --
        #
        # BR-R7 cũ chặn ở ĐÂY: mặt hàng thuộc hợp đồng còn hiệu lực bị từ
        # chối thẳng khỏi giỏ "mua lẻ", để khách hết hạn mức không né sang
        # lối kia mua tiếp (NL-10.7). Giờ không còn "lối kia": cùng một mặt
        # hàng đó rơi vào nhánh `if bo_dong` ngay dưới — được định giá theo
        # hợp đồng và bị TRỪ HẠN MỨC như thường, bất kể người gọi tưởng
        # mình đang ở chế độ nào. Cơ chế hạn mức của E1 được bảo vệ bằng
        # chính phép kiểm `han_muc_con` dưới đây, không còn bằng một lời từ
        # chối. Phép chuẩn hoá `item_code` về `Item.name` chính tắc (review
        # C-2, chống lách qua hoa/thường) vẫn nằm ở `tao_sales_order` TRƯỚC
        # khi gộp `aggregated`, không đụng.
        bo_dong = thang_cuoc.get(item_code)
        if not bo_dong:
            # Tầng 2 — có mã nhưng ngoài mọi hợp đồng còn hiệu lực. §4.5:
            # `rate = 0`, sales điền giá khi báo giá; KHÔNG kiểm hạn mức
            # (dòng này không thuộc hợp đồng nào để mà trừ), KHÔNG gắn
            # `blanket_order`/`against_blanket_order` (BR-R4).
            hop_le.append({
                "item_code": item_code, "qty": qty, "rate": 0,
                "hop_dong": None, "gan_hop_dong": None,
            })
            continue

        # Tầng 1 — dòng hợp đồng.
        # US-E1.4 — kiểm giá phải nằm TRONG vòng gom này. Bản trước ném ngay
        # ở mặt hàng thiếu giá đầu tiên tại vòng dựng đơn, nên giỏ vừa vượt
        # hạn mức vừa thiếu giá bắt khách gửi hai lần — đúng thứ BR-O3 cấm.
        # QĐ-G12 (Task 12) — giá của dòng hợp đồng lấy từ CHÍNH hợp đồng
        # `bo_dong` vừa suy ra, bảng giá chỉ là bước lui. KHÔNG còn gác
        # `if price_list` ở đây: bước 1 không cần bảng giá nào, phép kiểm
        # nằm trong `gia_dong_hop_dong()` (xem docstring hàm đó).
        rate = gia_hdnt.gia_dong_hop_dong(item_code, bo_dong, price_list)
        if not rate:
            # Khách không phải tự đi đòi giá. Báo sales phụ trách ngay, tối
            # đa một lần mỗi ngày cho mỗi cặp (khách, mặt hàng).
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
        con_lai, _da_dat = han_muc_con(bo_dong, item_code)
        if con_lai is None:
            # BR-O15 — hạn mức khai 0 = KHÔNG GIỚI HẠN. Không kiểm, và
            # KHÔNG gắn `against_blanket_order` cho dòng này: cơ chế gốc của
            # ERPNext đối chiếu cờ đó với `qty` của Blanket Order Item, thấy
            # 0 thì hiểu là CẤM ĐẶT và chặn ngay lúc submit. Truy vết về hợp
            # đồng vẫn còn qua `so.custom_hdnt` ở đầu đơn.
            hop_le.append({
                "item_code": item_code, "qty": qty, "rate": rate,
                "hop_dong": bo_dong, "gan_hop_dong": None,
            })
            continue
        if qty > con_lai:
            loi.append({
                "item_code": item_code,
                # §5 tách hai mã: hết sạch là `het_han_muc`, còn ít hơn số
                # khách đòi là `vuot_han_muc` — giao diện xử lý khác nhau.
                "ly_do": "het_han_muc" if con_lai <= 0 else "vuot_han_muc",
                "con_lai": con_lai,
                # Nguyên văn ma trận FormSpec §5, dòng NL-1.3, CỘNG vế
                # "Đã dùng bởi" (vòng sửa 1, review độc lập): §5.6 đòi mọi
                # thất bại hạn mức phải nêu TÊN KHOA đã tiêu mất, không có
                # ngoại lệ cho nhánh nào. Trước đó chỉ `de_xuat_duyet.
                # _kiem_han_muc` nêu, nên đơn đặt qua giỏ hàng quản lý —
                # và mọi dòng mà nhánh kia bỏ qua — nhận một thông điệp
                # không cho người dùng đường nào để gỡ. Câu gốc giữ NGUYÊN
                # VĂN ở đầu (test cũ khẳng định đúng chuỗi đó), vế mới nối
                # vào sau.
                "thong_diep": (
                    f"Không đặt được: {item_code} chỉ còn {con_lai:g} "
                    f"theo hạn mức hợp đồng khung. "
                    f"Đã dùng bởi: {ten_khoa_da_tieu(bo_dong)}."
                ),
            })
            continue
        hop_le.append({
            "item_code": item_code, "qty": qty, "rate": rate,
            "hop_dong": bo_dong, "gan_hop_dong": bo_dong,
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
        dong_dat_ngoai.append({
            "ten_hang": ten_hang, "dvt": dvt, "so_luong": so_luong,
            "ghi_chu": (dn.get("ghi_chu") or "").strip(),
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
        hop_le.append({
            "item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0,
            "hop_dong": None, "gan_hop_dong": None,
        })

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
    # Task 4 — giỏ có dòng HỢP ĐỒNG thì company lấy theo HỢP ĐỒNG (đúng
    # hành vi `_xay_don_hdnt` cũ: `so.company = bo.company`), KHÔNG qua
    # `resolve_ban_le_company()`. Lý do không phải "giữ cho giống": hàm đó
    # GIAO tập company của mọi mặt hàng trong giỏ, nên một dòng tầng 2
    # thiếu `Item Default` sẽ làm phép giao RỖNG và kéo cả đơn hợp đồng
    # rơi về `default_company` — sai sổ, sai kho, cho một đơn mà hợp đồng
    # đã nói rõ company nào. `sorted()[0]` khi nhiều hợp đồng khác company:
    # TẤT ĐỊNH tuyệt đối (một Sales Order chỉ có MỘT company); trường hợp
    # này không tồn tại ở Miyano hôm nay (một company duy nhất) nhưng để
    # `set` tự chọn thì hai lần đặt cùng một giỏ có thể ra hai company.
    company_hop_dong = sorted({
        frappe.db.get_value("Blanket Order", d["hop_dong"], "company")
        for d in hop_le if d["hop_dong"]
    } - {None})
    if company_hop_dong:
        company = company_hop_dong[0]
    else:
        # Chủ dự án đã quyết: đừng chốt cứng company vào mặt khách nữa —
        # `resolve_ban_le_company()` giờ TỰ rơi về `default_company` khi
        # phép giao rỗng, để nhân viên back-office sửa trên đơn nháp nếu
        # cần. Chỉ còn dừng ở đây khi site KHÔNG CÓ Company nào — lúc đó
        # ERPNext không lưu nổi một Sales Order thật (`company` là
        # `reqd=1`), và đây đúng là lỗi cấu hình hệ thống, không phải lỗi
        # của giỏ hàng khách.
        company = resolve_ban_le_company(list(aggregated.keys()))
    if not company:
        frappe.throw(
            "Hệ thống chưa có công ty (Company) nào được cấu hình. "
            "Vui lòng liên hệ quản trị viên hệ thống.",
            frappe.ValidationError,
        )

    # ---- suy `custom_hdnt` / `custom_loai_don` ở ĐẦU ĐƠN ---------------
    #
    # Ruling P8 — `Sales Order.custom_loai_don` KHÔNG bị xoá (khác
    # `Portal De Xuat Mua.loai_don`): ~15 chỗ đọc, gồm thông báo tự động và
    # vòng báo giá. Ở đây giữ đúng HAI giá trị cũ và suy chúng từ DÒNG:
    # còn bất kỳ dòng nào chưa có giá (tầng 2, hoặc dòng đặt ngoài) thì đơn
    # PHẢI đi qua vòng báo giá của Miyano → "Mua lẻ"; đơn thuần hợp đồng
    # giữ nguyên "Theo HĐNT" như hôm nay.
    #
    # ĐÂY LÀ CHỖ DUY NHẤT ĐÓNG DẤU, và dấu đóng MỘT LẦN lúc lập đơn. Mọi
    # CHỐT đọc dấu này đều đi qua `portal_mua_le.di_vong_bao_gia()` (Task 6,
    # QĐ-G2b) — đừng so chuỗi `== "Mua lẻ"` ở chỗ mới: từ Task 4 giá trị đó
    # KHÔNG còn nghĩa "đơn mua lẻ" nữa.
    bo_tren_don = sorted({d["hop_dong"] for d in hop_le if d["hop_dong"]})
    con_dong_chua_co_gia = bool(dong_dat_ngoai) or any(
        not d["hop_dong"] for d in hop_le
    )

    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = delivery_date
    # Đơn có dòng hợp đồng phải mang bảng giá của hợp đồng — `rate` từng
    # dòng đã tính sẵn ở trên, nhưng `selling_price_list` là thứ nhân viên
    # Miyano nhìn/dùng lại khi báo giá phần còn lại của đơn.
    so.selling_price_list = (
        (price_list if bo_tren_don else None) or _selling_price_list_mac_dinh()
    )
    so.custom_nguon_don = "Client Portal"
    # Suy được ĐÚNG MỘT hợp đồng thì dùng nó; nhiều hợp đồng trên một đơn
    # thì không có "hợp đồng của đơn" nào để ghi (truy vết thật nằm trên
    # từng DÒNG, `Sales Order Item.blanket_order`). `contract` chỉ còn là
    # đường lui cho người gọi CŨ truyền tường minh.
    so.custom_hdnt = bo_tren_don[0] if len(bo_tren_don) == 1 else contract
    so.custom_loai_don = "Mua lẻ" if con_dong_chua_co_gia else "Theo HĐNT"
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
        dong = {
            "item_code": d["item_code"],
            "qty": d["qty"],
            # Tầng 1 mang giá hợp đồng; tầng 2 và dòng giữ chỗ mang 0
            # (§4.5 — sales điền giá khi báo giá).
            "rate": d["rate"],
            "warehouse": item_warehouse,
            "delivery_date": delivery_date,
        }
        if not d["rate"]:
            # BẪY ERPNext, phát hiện bằng test khi gộp hai hàm dựng (giá
            # 777 cố ý gài cho mặt hàng TẦNG 2 trong `test_dat_hang_gop`):
            # `taxes_and_totals.calculate_item_values` có nhánh
            # `elif item.price_list_rate: if not item.rate: item.rate =
            # price_list_rate` — `rate = 0` là FALSY, nên ERPNext ÂM THẦM
            # thay 0 bằng giá trong bảng giá của đơn. Trước Task 4 nhánh
            # mua lẻ thoát nạn chỉ vì nó dùng bảng giá mặc định hệ thống
            # (thường không có dòng giá cho hàng lẻ) — một sự may mắn, không
            # phải một chốt. Đơn TRỘN mang bảng giá hợp đồng của khách nên
            # cái may đó hết. Gán tường minh `price_list_rate = 0` để
            # `set_missing_item_details` không điền hộ (nó chỉ điền khi
            # field đang là `None`) và nhánh trên không kích hoạt.
            #
            # CHỈ áp cho dòng giá 0 — dòng tầng 1 để nguyên cho ERPNext tự
            # điền `price_list_rate` y như trước Task 4 (giữ nguyên vẹn
            # hành vi đơn thuần hợp đồng, kể cả phần chiết khấu/quy đổi ĐVT
            # mà app này không tính).
            dong["price_list_rate"] = 0
        if d["gan_hop_dong"]:
            # BR-R4 — CHỈ dòng hợp đồng mới gắn; dòng tầng 2 không thuộc hạn
            # mức nào, và dòng hợp đồng KHÔNG GIỚI HẠN cố ý bỏ (BR-O15, xem
            # nhánh `con_lai is None` ở trên).
            dong["blanket_order"] = d["gan_hop_dong"]
            dong["against_blanket_order"] = 1
        so.append("items", dong)
    for dong in dong_dat_ngoai:
        so.append("custom_dat_ngoai", dong)
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

    `mode` — [KHÔNG CÒN TÁC DỤNG từ Task 4]. Hàm dựng đơn đã gộp làm một và
    quyết định theo TỪNG DÒNG (xem `_xay_don`), nên không còn "chế độ" nào
    để chọn. Tham số ở lại vì hai lý do, không phải vì lười: (a) nó là
    tham số của endpoint công khai `portal_order_place`, mà `Cart.vue` đang
    chạy thật vẫn gửi — bỏ chữ ký là làm gãy cổng đang chạy trước khi
    Task 10 gộp hai màn đặt hàng; (b) hơn 40 lời gọi trong bộ test cũ vẫn
    truyền nó, và im lặng đổi hành vi của chúng đáng lo hơn là giữ một tham
    số bị làm ngơ tường minh. Giá trị vẫn được kiểm hợp lệ để một client
    gửi sai chính tả không lặng lẽ đi tiếp.
    """
    mode = (mode or "hdnt").strip()
    if mode not in ("hdnt", "ban_le"):
        frappe.throw("Chế độ đặt hàng không hợp lệ.", frappe.ValidationError)
    # BR-R1 (chốt "khách phải được bật cờ mới mua lẻ được") đã bỏ hẳn 21/08
    # — xem `portal_mua_le.py` đầu file. Mọi khách đều đi thẳng qua đây.

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

    # Task 4 — chỉ kiểm khi người gọi THẬT SỰ truyền một hợp đồng. Bản
    # trước kiểm theo `mode`, và đó chính là lỗi Ruling P19: một phiếu đề
    # xuất tạo qua UI thật luôn có `hdnt = None` (`de_xuat_tao_nhap()` tạo
    # phiếu Nháp TRƯỚC khi người dùng chọn mặt hàng, `de_xuat_luu_nhap()`
    # không có tham số `hdnt` để sửa lại), nên phiếu THUẦN hợp đồng đi
    # `mode="hdnt"` + `contract=None` → `frappe.db.get_value("Blanket
    # Order", None, ...)` rơi vào `get_values_from_single()` của Frappe và
    # trả `None` → PermissionError chỉ vào hoàn toàn sai chỗ. Không có
    # hợp đồng nào để kiểm thì không có gì để từ chối: từng dòng tự tìm
    # hợp đồng của nó ở `_xay_don()`, và hàm đó chỉ nhìn hợp đồng CỦA
    # CHÍNH `customer` (`nguon_gia_theo_ma_cho_khach`) nên phép cách ly
    # khách hàng KHÔNG hề bị nới ra.
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

    so = _xay_don(
        customer, contract, aggregated, dat_ngoai, delivery_date,
        address, po, note, request_id,
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
