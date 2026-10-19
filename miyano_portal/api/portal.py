import frappe

from miyano_portal.kho import can_cu_duyet
from miyano_portal.nang_quyen import quyen_he_thong
from miyano_portal import bang_gia_khach, bao_gia, dat_hang, einvoice, ten_hang
from miyano_portal.dat_hang import (
    _customer_addresses,
    _insert_so_idempotent,
)
from miyano_portal.api.de_xuat import _phieu_cua_toi
from miyano_portal.portal_context import (
    LOI_KHONG_THAY,
    _cot_de_xuat_ton_tai,
    _cot_khoa_phong_ton_tai,
    cot_lan_dat_ton_tai,
    cot_ten_don_hang_ton_tai,
    dam_bao_xem_duoc,
    get_portal_customer,
    get_portal_member,
    khoa_phong_cho_don,
    la_quan_ly,
    lien_he_nguoi_dung,
    pham_vi_don,
)
from miyano_portal.ma_de_xuat import sinh_ma
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, trang_thai_hang
from miyano_portal.portal_hen_giao import hen_giao_cua_don
from miyano_portal.portal_thoi_gian_giao import COT_CAN as COT_THOI_GIAN_GIAO
from miyano_portal.portal_thoi_gian_giao import thoi_gian_giao_cua_dn
from miyano_portal.miyano_portal.doctype.portal_delivery_inspection.portal_delivery_inspection import (
    TT_TU_CHOI,
)
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
    TRANG_THAI_CHO_DUYET,
    TRANG_THAI_CHO_DUYET_SUA,
    TRANG_THAI_DA_DUYET,
    TRANG_THAI_DA_HUY,
    TRANG_THAI_NHAP,
    TRANG_THAI_TU_CHOI,
)
from miyano_portal.portal_kiem_hang import (
    bien_ban_cua_dn,
    dong_tu_delivery_note,
)
from miyano_portal.portal_thong_bao import bao_yeu_cau_ho_tro_hddt

# `_customer_addresses`, `_insert_so_idempotent` đã chuyển sang `dat_hang.py` (lõi đặt hàng, xem module đó). Import lại ở
# đây vì chỗ khác trong file này vẫn dùng trực tiếp: `portal_me()` gọi
# `_customer_addresses`, và `tests/test_e1_idempotency.py` patch
# `frappe.db.get_value` rồi gọi thẳng `portal._insert_so_idempotent(...)` —
# đổi tên thuộc tính này trên module `portal` là phá test đó.


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
    # Man luong duyet (Task 1) — Frontend cần biết vai trò để gating menu
    # (màn Duyệt chỉ cho người có quyền duyệt). `la_quan_ly` là khoá RIÊNG,
    # không để client tự suy từ `vai_tro`: kế hoạch C thêm uỷ quyền tạm
    # thời, khi đó một Nhân viên khoa ĐANG ĐƯỢC UỶ QUYỀN phải thấy menu
    # Duyệt — client tự suy `vai_tro === "Quản lý"` sẽ bỏ sót đúng ca đó.
    # `la_quan_ly()` (portal_context) là NGUỒN DUY NHẤT được hỏi, KHÔNG tự
    # so `tv.vai_tro == "Quản lý"` ở đây.
    tv = get_portal_member()
    return {
        "customer": customer,
        # Task 3 (màn /de-xuat) — `frontend/src/de-xuat-actions.js` cần
        # phân biệt CHỦ PHIẾU để hiện "Gửi duyệt"/"Xoá", nhưng không có
        # nguồn nào khác lộ session user ra frontend (đã kiểm: không
        # frappe.session/window.frappe/boot.user nào trong frontend/src).
        # Không phải rò rỉ: `frappe.session.user` chính là email người
        # ĐANG GỌI endpoint này, tức người đã đăng nhập bằng chính email
        # đó — trả lại cho họ không lộ gì họ chưa biết.
        "user": frappe.session.user,
        "customer_name": cust.get("customer_name"),
        "tax_id": cust.get("tax_id"),
        "outstanding": _get_outstanding(customer),
        "addresses": _customer_addresses(customer),
        # BR-R1 bỏ hẳn 21/08 (task-1-brief.md mục a) — không còn cờ nào để
        # trả, mọi khách đều mua lẻ được, `cho_phep_mua_le` xoá khỏi phong
        # bì này.
        "vai_tro": tv.vai_tro,
        "khoa_phong": tv.khoa_phong or None,
        "la_quan_ly": la_quan_ly(),
    }


@frappe.whitelist()
def portal_catalog_gop(
    tu_khoa=None, start=0, limit=50, nhom_vat_tu=None, nha_cung_cap=None,
    may_su_dung=None, ten_thuong_goi=None,
) -> dict:
    """Endpoint tìm kiếm danh mục cho màn Lập phiếu (`LapPhieu.vue`) — mỗi
    mặt hàng thuộc MỘT trong HAI TẦNG, suy từ Price List của khách (spec
    `docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md` §3,
    chủ đầu tư chốt 09/10/2026). Trả về:

        {"rows": [{item_code, item_name, dvt, boi_so, nhom_vat_tu,
                   ten_thuong_goi, trang_thai_hang, tang, don_gia}],
         "tong": int, "nhom_vat_tu_ds": [...], "nha_cung_cap_ds": [...],
         "may_su_dung_ds": [...]}

    Tầng và giá:

    * `tang == "bang_gia"` — mặt hàng CÓ giá trong bảng giá của khách;
      `don_gia` là con số đó (`float`).
    * `tang == "cho_bao_gia"` — chưa có giá; `don_gia` là `None` (KHÔNG
      phải `0`: `<= 0` nghĩa là "chưa khai giá", không phải "bán 0 đồng").
    * Nguồn giá DUY NHẤT là `bang_gia_khach.gia_bang_gia_nhieu()` — cùng
      module mà mọi nơi cần giá của cổng hỏi — gọi MỘT lần cho cả trang.
      "Có giá" theo đúng luật của hàm đó: dòng `Item Price` bán, giá
      dương, còn hiệu lực hôm nay, trong `Customer.default_price_list`
      của khách đang đăng nhập, không gắn khách khác/nhà cung cấp/lô.
    * Hợp đồng khung (`Blanket Order`) KHÔNG được hỏi ở đây (Q3): nó
      không quyết định tầng, giá hay thứ tự, và dòng trả về không mang
      khoá hợp đồng/hạn mức nào.
    * Hàng chưa có mã KHÔNG đến từ đây — đó là dòng khách gõ tay, đi qua
      bảng "đặt ngoài" của phiếu.

    Cách ly (BR — vai trò khách): `get_portal_customer()` suy khách từ
    CHÍNH phiên đăng nhập, không nhận `customer` từ client. `role Customer`
    có ZERO DocPerm trên `Item` nên dùng `frappe.get_all`/`frappe.db.*`
    (không `frappe.get_list`/`doc.check_permission()` — hai đường đó ném
    `PermissionError` cho một Website User trước khi chạy tới đây).

    Thứ tự và phân trang: MỘT truy vấn, `item_name asc, name asc`, như nhau
    cho mọi khách; cắt trang PHÍA SERVER, NGAY TRONG SQL (`limit_start`/
    `limit_page_length`) — KHÔNG dựng toàn bộ danh mục trong Python rồi cắt
    lát: `tabItem` là TOÀN BỘ danh mục Miyano. `tong` đếm theo đúng bộ lọc
    của truy vấn trang.

    Các khoá/tham số còn lại:

    * `boi_so` — `Item.custom_boi_so_dat`; `None` (không phải `0`) khi
      không ràng buộc bội số.
    * `trang_thai_hang` — ĐÚNG cơ chế màn mua lẻ đang dùng (`portal_mua_le.
      trang_thai_hang`, đọc tồn Miyano thật ở `tabBin`), KHÔNG dựng cơ chế
      thứ hai: hai cách trả lời "còn hàng không" sớm muộn cũng trả lời khác
      nhau cho cùng một mã.
    * Nhóm vật tư (patch v1_36): tham số `nhom_vat_tu` lọc theo
      `Item.custom_nhom_vat_tu`; mỗi dòng mang khoá `nhom_vat_tu` (`None`
      khi hàng chưa phân nhóm), và kết quả mang `nhom_vat_tu_ds` — danh
      sách nhóm đọc từ meta, để cổng dựng nút lọc từ ĐÚNG nguồn mà phép
      kiểm tham số dùng.
    * Nhà cung cấp (patch v1_37): tham số `nha_cung_cap` (tên `Supplier`)
      lọc theo bảng `Item.supplier_items`; `nha_cung_cap_ds` = `[{value,
      label}]`, CHỈ gồm NCC đang gắn với ít nhất một mặt hàng khách thấy
      được (chọn một NCC không có hàng nào là một ngõ cụt).
    * Máy sử dụng (patch v1_38) — cùng khuôn NCC: tham số `may_su_dung`
      (tên `Dong May`) lọc theo bảng `Item.custom_may_su_dung`;
      `may_su_dung_ds` = `[{value, label}]`, chỉ gồm máy đang gắn với ít
      nhất một mặt hàng.
    * Tên thường gọi (patch v1_39): `tu_khoa` khớp mã hoặc `item_name` —
      đúng tên XUẤT HOÁ ĐƠN. Tham số `ten_thuong_goi` khớp bảng
      `Item.custom_ten_thuong_goi`, CHỈ các dòng có `customer` = khách đang
      đăng nhập (cách ly: tên bệnh viện A tự đặt không lộ sang B). Mỗi dòng
      trả `ten_thuong_goi` = danh sách tên thường gọi CỦA CHÍNH khách này.
    * Giá trị lạ của `nhom_vat_tu`/`nha_cung_cap`/`may_su_dung` bị từ chối
      rõ ràng, không lặng lẽ thành "không lọc".
    """
    customer = get_portal_customer()
    start = max(0, int(start or 0))
    limit = max(1, int(limit or 50))

    # Loại item KỸ THUẬT NỘI BỘ (`HANG-DAT-NGOAI`) khỏi danh mục khách nhìn
    # thấy: nó `disabled=0`, `is_sales_item=1` (đơn toàn hàng chưa có mã cần
    # vậy mới lưu được) nên không loại tường minh thì lọt ra như một sản phẩm. Dùng danh sách
    # điều kiện (không phải dict) vì các bộ lọc NCC/máy/tên thường gọi bên
    # dưới thêm điều kiện THỨ HAI trên cùng field `name` — dict filters của
    # `frappe.get_all` không biểu diễn được hai điều kiện trên một field.
    filters = [["disabled", "=", 0], ["name", "!=", ITEM_GIU_CHO]]
    or_filters = None
    if tu_khoa:
        or_filters = [
            ["item_code", "like", f"%{tu_khoa}%"],
            ["item_name", "like", f"%{tu_khoa}%"],
        ]

    ds_nhom = _nhom_vat_tu_ds()
    if nhom_vat_tu:
        # Giá trị lạ không được lặng lẽ thành "không lọc" (khách thấy cả
        # danh mục mà tưởng đã lọc) — từ chối rõ ràng.
        if nhom_vat_tu not in ds_nhom:
            frappe.throw(f"Nhóm vật tư không hợp lệ: {nhom_vat_tu}")
        filters.append(["custom_nhom_vat_tu", "=", nhom_vat_tu])

    ds_ncc = _nha_cung_cap_ds()
    if nha_cung_cap:
        if nha_cung_cap not in {x["value"] for x in ds_ncc}:
            frappe.throw(f"Nhà cung cấp không hợp lệ: {nha_cung_cap}")
        # Tách thành tập mã rồi `name in`; KHÔNG lọc thẳng qua bảng con trong
        # `get_all` (join bảng con nhân dòng khi một item khai trùng NCC,
        # `tong` và phân trang sẽ lệch). `or [""]` — mảng rỗng cho `["name",
        # "in", []]` không tất định trên mọi bản Frappe; không mã nào khớp
        # thì kết quả phải là RỖNG, không phải "bỏ qua điều kiện".
        ma_cua_ncc = frappe.get_all(
            "Item Supplier",
            filters={"parenttype": "Item", "supplier": nha_cung_cap},
            pluck="parent", distinct=True,
        )
        filters.append(["name", "in", ma_cua_ncc or [""]])

    co_bang_ten = frappe.db.table_exists("Item Ten Thuong Goi")
    ten_thuong_goi = (ten_thuong_goi or "").strip()
    if ten_thuong_goi:
        ma_theo_ten = frappe.get_all(
            "Item Ten Thuong Goi",
            filters={
                "parenttype": "Item", "customer": customer,
                "ten_thuong_goi": ["like", f"%{ten_thuong_goi}%"],
            },
            pluck="parent", distinct=True,
        ) if co_bang_ten else []
        filters.append(["name", "in", ma_theo_ten or [""]])

    ds_may = _may_su_dung_ds()
    if may_su_dung:
        if may_su_dung not in {x["value"] for x in ds_may}:
            frappe.throw(f"Máy sử dụng không hợp lệ: {may_su_dung}")
        # Cùng lý do nhánh NCC ở trên: tập mã rồi `name in`, không join bảng con.
        ma_cua_may = frappe.get_all(
            "Item May Su Dung",
            filters={"parenttype": "Item", "may": may_su_dung},
            pluck="parent", distinct=True,
        )
        filters.append(["name", "in", ma_cua_may or [""]])

    COT = ["item_code", "item_name", "stock_uom", "custom_boi_so_dat"]
    # Site chưa chạy patch v1_36 chưa có cột này — chọn nó sẽ làm SẬP cả màn
    # Đặt hàng chứ không chỉ mất bộ lọc.
    if ds_nhom:
        COT.append("custom_nhom_vat_tu")
    # `item_name` không unique — thêm `name` làm tiebreak để thứ tự TẤT
    # ĐỊNH giữa hai trang: không có nó, hai mã cùng tên có thể rơi vào CẢ
    # HAI trang hoặc KHÔNG trang nào tuỳ thứ tự trả về của MariaDB.
    THU_TU = "item_name asc, name asc"

    def _dem(dk):
        # `frappe.db.count` KHÔNG nhận `or_filters` — đếm qua `get_all` với
        # ĐÚNG bộ filters/or_filters của truy vấn trang dưới, nếu không
        # `tong` sẽ lặng lẽ bỏ qua điều kiện tìm kiếm khi `tu_khoa` có giá
        # trị.
        return frappe.get_all(
            "Item", filters=dk, or_filters=or_filters, fields=["count(name) as tong"],
        )[0].tong

    def _trang(dk, bat_dau, so_dong):
        return frappe.get_all(
            "Item", filters=dk, or_filters=or_filters, fields=COT, order_by=THU_TU,
            limit_start=bat_dau, limit_page_length=so_dong,
        )

    tong = _dem(filters)
    rows = _trang(filters, start, limit)

    # MỘT truy vấn cho cả trang, chỉ tên của CHÍNH khách này — cùng hàm với
    # mọi bảng mặt hàng khác của cổng (`ten_hang.py`).
    ten_goi_theo_ma = ten_hang.ten_thuong_goi_theo_ma(
        customer, [r.item_code for r in rows]
    )

    # Spec 2026-10-09 §3 — MỘT truy vấn giá cho cả trang; mã vắng mặt trong
    # dict = chưa có giá. Hợp đồng không còn được hỏi ở đây (Q3).
    gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(
        customer, [r.item_code for r in rows]
    )
    out = []
    for r in rows:
        gia = gia_theo_ma.get(r.item_code)
        out.append({
            "item_code": r.item_code, "item_name": r.item_name, "dvt": r.stock_uom,
            # `0`/chưa khai đều là "không ràng buộc bội số" → `None`, cùng
            # quy ước `kiem_boi_so()` (`portal_dat_hang.py`).
            "boi_so": int(r.custom_boi_so_dat or 0) or None,
            "nhom_vat_tu": r.get("custom_nhom_vat_tu") or None,
            "ten_thuong_goi": ten_goi_theo_ma.get(r.item_code, []),
            "trang_thai_hang": trang_thai_hang(r.item_code),
            "tang": "bang_gia" if gia is not None else "cho_bao_gia",
            "don_gia": gia,
        })
    return {
        "rows": out, "tong": tong,
        "nhom_vat_tu_ds": ds_nhom, "nha_cung_cap_ds": ds_ncc, "may_su_dung_ds": ds_may,
    }


def _may_su_dung_ds() -> list:
    """Dòng máy gắn với ít nhất một mặt hàng đang bật trong `Item.
    custom_may_su_dung` — nguồn của ô lọc máy ở màn Đặt hàng. Site chưa chạy
    patch v1_38 chưa có bảng → rỗng (màn Đặt hàng vẫn chạy, chỉ không có ô
    lọc)."""
    if not frappe.db.table_exists("Item May Su Dung"):
        return []
    rows = frappe.db.sql(
        """
        select distinct m.name as value,
            concat_ws(' · ', m.name, nullif(m.hang_san_xuat, '')) as label
        from `tabItem May Su Dung` ims
        join `tabItem` i on i.name = ims.parent and ims.parenttype = 'Item'
        join `tabDong May` m on m.name = ims.may
        where i.disabled = 0 and i.name != %s
        order by m.name asc
        """,
        (ITEM_GIU_CHO,), as_dict=True,
    )
    return [{"value": r.value, "label": r.label} for r in rows]


def _nha_cung_cap_ds() -> list:
    """NCC (đang bật) gắn với ít nhất một mặt hàng đang bật trong
    `Item.supplier_items` — nguồn của ô lọc NCC ở màn Đặt hàng. `frappe.db.
    sql` vì role `Customer` không có DocPerm trên `Supplier`/`Item`."""
    rows = frappe.db.sql(
        """
        select distinct s.name as value, coalesce(nullif(s.supplier_name, ''), s.name) as label
        from `tabItem Supplier` isp
        join `tabItem` i on i.name = isp.parent and isp.parenttype = 'Item'
        join `tabSupplier` s on s.name = isp.supplier
        where i.disabled = 0 and i.name != %s and s.disabled = 0
        order by label asc
        """,
        (ITEM_GIU_CHO,), as_dict=True,
    )
    return [{"value": r.value, "label": r.label} for r in rows]


def _nhom_vat_tu_ds() -> list:
    """Các nhóm vật tư hợp lệ — ĐÚNG danh sách tuỳ chọn của
    `Item.custom_nhom_vat_tu` (patch v1_36), đọc từ meta nên thêm nhóm ở
    Customize Form là cổng thấy ngay. Site chưa chạy patch → rỗng."""
    field = frappe.get_meta("Item").get_field("custom_nhom_vat_tu")
    if not field:
        return []
    return [x.strip() for x in (field.options or "").split("\n") if x.strip()]


@frappe.whitelist()
def portal_order_place(
    contract=None, items=None, po=None, delivery_date=None, note=None, address=None,
    request_id=None, mode="hdnt", dat_ngoai=None, khoa_phong=None, ten_don_hang=None,
    hsd_toi_thieu_thang=None,
) -> dict:
    """API Spec §1.1 — quản lý đặt hàng trực tiếp từ giỏ.

    `hsd_toi_thieu_thang` — HSD tối thiểu khách yêu cầu cho cả đơn (tháng
    0-60); mỗi phần tử `items` có thể mang khoá riêng cùng tên. Kiểm TRƯỚC
    khi tạo chứng từ nào (lỗi ra `frappe.local.response["loi"]` như lỗi giỏ
    hàng khác). Đơn mang số tháng sang Sales Order; nhánh Quotation chỉ ghi
    Comment (chưa mang qua Quotation).

    Trả `{"sales_order", "bao_gia", "de_xuat", "da_ton_tai", "total",
    "loai_don", "don": [{"sales_order", "bao_gia", "de_xuat", "loai_don"}]}`.
    `don` có 1 hoặc 2 phần tử; các khoá cấp cao nhất là của phần tử ĐẦU
    (client cũ chỉ đọc chúng).

    Spec 2026-10-12 §5 — phần còn hàng chưa có giá trong Price List hoặc có
    dòng gõ tay `dat_ngoai` sinh một Quotation ở "Chờ Miyano báo giá", KHÔNG
    sinh Sales Order "Mua lẻ" nữa. Phần tử đó có `sales_order = None`,
    `bao_gia` là tên Quotation, `loai_don = "Yêu cầu báo giá"`; phần tử là
    đơn có `bao_gia = None`.

    Spec 2026-10-09 §4.1 — giỏ trộn hàng có giá với hàng chờ báo giá (kể cả
    dòng gõ tay) ra HAI chứng từ, mỗi chứng từ một `Portal De Xuat Mua` đứng
    sau; hai phiếu mang chung `ma_lan_dat` và trỏ nhau qua
    `phieu_cung_lan_dat`. Chứng từ đầu là đơn "Theo bảng giá", chứng từ sau
    là Quotation. Hai chứng từ nhận `request_id` gốc kèm hậu tố `:gia` /
    `:baogia`; giỏ một loại giữ nguyên `request_id` của client. Bấm lại cùng
    `request_id` trả đúng (các) chứng từ và phiếu đã tạo, không tạo thêm.
    Thiếu `request_id` thì `dat_hang.tao_sales_order` / `bao_gia.tao_bao_gia`
    từ chối, giỏ trộn hay không cũng vậy.

    `contract`, `mode` — [KHÔNG CÒN QUYẾT ĐỊNH GÌ, spec 2026-10-09 §4.2].
    Giá lấy từ Price List theo từng dòng; đơn và phiếu không còn gắn hợp
    đồng khung. Hai tham số ở lại trong chữ ký vì client đang chạy thật vẫn
    gửi; `contract` không được đọc ở đây, `mode` chỉ còn được
    `tao_sales_order` kiểm chính tả.

    Vỏ mỏng (bước 1, tách lõi đặt hàng — xem `dat_hang.py`): xác định khách
    hàng từ PHIÊN ĐĂNG NHẬP rồi giao việc tạo từng Sales Order cho
    `dat_hang.tao_sales_order`.

    C1 (review vòng sửa 1, CRITICAL — SỬA LẠI ở Task 7, xem QĐ điều phối
    viên 19/08/2026 trong `task-7-report.md`): §5.5 đòi giỏ hàng của QUẢN LÝ
    có ô chọn khoa (mặc định "Toàn viện") nên tham số `khoa_phong` CÓ mặt,
    và phép chặn A-đóng-dấu-thành-B nằm ở `portal_context.
    khoa_phong_cho_don()`, hàm role-aware DUY NHẤT được phép đọc/ghi
    `khoa_phong` cho đường ghi này:
      * Nhân viên khoa KHÔNG được gọi endpoint này chút nào nữa (chặn ở
        dòng đầu, xem dưới) — họ đi qua `de_xuat_gui_duyet` để quản lý
        duyệt. Gọi thẳng vẫn bị từ chối rõ ràng, không phải lỗi khó hiểu.
      * Quản lý ĐƯỢC chọn khoa qua `khoa_phong`, nhưng `khoa_phong_cho_don()`
        tự kiểm khoa đó thuộc ĐÚNG bệnh viện của họ và đang `active` —
        không nhận thẳng giá trị client gửi mà không kiểm.

    §5.5 (thân bài, "mọi đơn trên hệ thống đều có đúng MỘT chứng từ đề nghị
    đứng sau") — sau khi `dat_hang.tao_sales_order` tạo xong một Sales
    Order, hàm này GHI một `Portal De Xuat Mua` "Đã duyệt" đứng sau,
    `nguoi_duyet` là chính quản lý (`_dam_bao_phieu_tu_duyet`). CỐ Ý KHÔNG
    route qua `de_xuat_duyet.duyet_va_tao_don`: phiếu này SINH RA đã "Đã
    duyệt", không có ai chờ duyệt; và `duyet_va_tao_don` coi `da_ton_tai`
    là LỖI, trong khi ở đây bấm lại cùng `request_id` phải trả đơn cũ
    (BR-O12). Lỗi theo dòng hàng vẫn ra `frappe.local.response["loi"]` do
    `tao_sales_order` ghi trước khi ném.
    """
    if not la_quan_ly():
        # §5.5 câu cuối — chặn HẲN, không phải một lỗi CSDL khó hiểu lộ
        # ra từ tầng dưới. Chặn TRƯỚC khi chạm bất kỳ thứ gì khác
        # (customer, khoa_phong_cho_don, dat_hang) — không để lỡ tạo ra bất
        # kỳ chứng từ nào rồi mới từ chối.
        frappe.throw(
            "Nhân viên khoa không đặt hàng trực tiếp qua giỏ hàng được. "
            "Vui lòng tạo phiếu đề xuất và gửi duyệt để quản lý phê duyệt.",
            frappe.ValidationError,
        )
    customer = get_portal_customer()
    khoa = khoa_phong_cho_don(khoa_phong)
    from miyano_portal import tach_phieu

    ds_items = frappe.parse_json(items) if isinstance(items, str) else (items or [])
    ds_ngoai = (
        frappe.parse_json(dat_ngoai) if isinstance(dat_ngoai, str) else (dat_ngoai or [])
    )
    # Kiểm HSD cho CẢ giỏ trước khi tạo bất kỳ chứng từ nào (giỏ trộn tạo
    # hai chứng từ liên tiếp: lỗi ở lô sau không được để lại lô trước).
    dat_hang.kiem_hsd_gio(hsd_toi_thieu_thang, ds_items)
    co_gia, cho_bao_gia = tach_phieu.chia_dong(customer, ds_items)
    # Lưới an toàn lúc triển khai (`bao_gia.san_sang`): site chưa `bench
    # migrate` chưa có cột `Quotation.custom_request_id`, mà hàm này hỏi cột đó
    # cho MỌI giỏ. Chưa sẵn sàng thì không câu nào dưới đây chạm bảng Quotation
    # và mọi lô đi đường cũ (`tao_sales_order`, hàng chưa giá ra đơn "Mua lẻ").
    co_bao_gia = bao_gia.san_sang()
    rid_gia = f"{request_id}{tach_phieu.HAU_TO_GIA}"
    rid_bao_gia = f"{request_id}{tach_phieu.HAU_TO_BAO_GIA}"

    def _da_co_don(*ds_rid):
        # Lọc CẢ `customer`: câu hỏi là "lần bấm trước CỦA KHÁCH NÀY đã chia
        # giỏ thế nào". Không lọc thì khách B gửi `X` trong khi khách A đã
        # có đơn `X:gia` sẽ bị coi là "đã tách" — giỏ một loại của B bị ép
        # sang `X:gia` rồi chết ở chốt BR-O12 của `tao_sales_order` ("Mã yêu
        # cầu không hợp lệ") dù B chưa từng dùng mã đó. Trùng mã THẬT với
        # khách khác vẫn do `tao_sales_order` từ chối như cũ.
        #
        # Spec 2026-10-12 §5 — một lô đã chạy có thể đã sinh Quotation chứ
        # không phải Sales Order.
        if frappe.db.exists(
            "Sales Order", {"custom_request_id": ["in", list(ds_rid)], "customer": customer}
        ):
            return True
        if not co_bao_gia:
            return False
        return bool(frappe.db.exists(
            "Quotation", {"custom_request_id": ["in", list(ds_rid)], "party_name": customer}
        ))

    # Spec 2026-10-09 §4.1 — giỏ trộn ra HAI đơn. Giỏ một loại giữ nguyên
    # `request_id` của client (tương thích với mọi đơn đã tạo trước đây).
    #
    # Lần BẤM LẠI theo đúng cách chia của lần đầu, KHÔNG chia lại theo Price
    # List hiện tại: giá có thể xuất hiện/mất đi giữa hai lần bấm, và chia
    # lại sẽ đổi `request_id` thực dùng → đơn thứ ba. Thiếu `request_id` thì
    # không dựng hậu tố ("None:gia" sẽ lọt chốt BR-O12): đi một lô, để
    # `tao_sales_order` từ chối như mọi giỏ khác.
    if not request_id or _da_co_don(request_id):
        tron = False
    elif _da_co_don(rid_gia, rid_bao_gia):
        tron = True
    else:
        tron = bool(co_gia and (cho_bao_gia or ds_ngoai))

    if tron:
        lo = [(co_gia, [], rid_gia), (cho_bao_gia, ds_ngoai, rid_bao_gia)]
    else:
        lo = [(ds_items, ds_ngoai, request_id)]

    don = []
    for lo_items, lo_ngoai, rid in lo:
        # Spec 2026-10-12 §5 — lô còn dòng chưa có giá hoặc dòng gõ tay sinh
        # Quotation. Lần bấm lại đi đúng nhánh của lần đầu, dù Price List vừa
        # có thêm hay mất giá: lô đã sinh Quotation thì trả Quotation đó, lô
        # đã sinh Sales Order thì trả đơn đó. Hỏi lại Price List ở đây sẽ sinh
        # thêm một chứng từ thứ hai cho cùng một mã yêu cầu.
        if not co_bao_gia:
            di_bao_gia = False
        elif frappe.db.exists("Quotation", {"custom_request_id": rid, "party_name": customer}):
            di_bao_gia = True
        elif frappe.db.exists("Sales Order", {"custom_request_id": rid, "customer": customer}):
            di_bao_gia = False
        else:
            di_bao_gia = bao_gia.can_bao_gia(customer, lo_items, lo_ngoai)
        if di_bao_gia:
            kq = bao_gia.tao_bao_gia(
                customer, items=lo_items, dat_ngoai=lo_ngoai,
                delivery_date=delivery_date, note=note, address=address,
                request_id=rid, khoa_phong=khoa,
            )
            if not kq.get("da_ton_tai"):
                bao_gia.ghi_comment_hsd(kq["bao_gia"], hsd_toi_thieu_thang, lo_items)
            kq["sales_order"] = None
            kq["loai_don"] = "Yêu cầu báo giá"
        else:
            kq = dat_hang.tao_sales_order(
                customer, mode=mode, items=lo_items, dat_ngoai=lo_ngoai,
                po=po, delivery_date=delivery_date, note=note, address=address,
                request_id=rid, khoa_phong=khoa,
                hsd_toi_thieu_thang=hsd_toi_thieu_thang,
            )
            kq["bao_gia"] = None
            kq["loai_don"] = frappe.db.get_value(
                "Sales Order", kq["sales_order"], "custom_loai_don"
            )
        kq["de_xuat"] = _dam_bao_phieu_tu_duyet(
            customer=customer, khoa_phong=khoa, mode=mode, contract=None,
            dat_ngoai=lo_ngoai, delivery_date=delivery_date, address=address,
            note=note, request_id=rid, ten_don_hang=ten_don_hang,
            sales_order=kq["sales_order"], da_ton_tai=bool(kq.get("da_ton_tai")),
            bao_gia_ten=kq["bao_gia"],
        )
        if kq["bao_gia"] and not kq.get("da_ton_tai"):
            bao_gia.bao_nhan_vien(
                frappe.get_doc("Quotation", kq["bao_gia"]), "Portal - Yêu cầu báo giá mới",
                f"Khách hàng <b>{customer}</b> vừa gửi yêu cầu báo giá <b>{kq['bao_gia']}</b>.",
            )
        don.append(kq)

    if len(don) == 2 and don[0]["de_xuat"] and don[1]["de_xuat"]:
        # Mã lần đặt = mã của phiếu đầu (cùng quy ước đường khoa gửi duyệt);
        # khách chưa có Mã ngắn thì phiếu không có mã, rơi về tên phiếu. Bấm
        # lại ghi đúng các giá trị cũ.
        ma = frappe.db.get_value("Portal De Xuat Mua", don[0]["de_xuat"], "ma_de_xuat")
        tach_phieu.lien_ket(don[0]["de_xuat"], don[1]["de_xuat"], ma or don[0]["de_xuat"])

    return {
        **don[0],
        "don": [
            {"sales_order": d["sales_order"], "bao_gia": d["bao_gia"],
             "de_xuat": d["de_xuat"], "loai_don": d["loai_don"]}
            for d in don
        ],
    }


def _dam_bao_phieu_tu_duyet(
    customer, khoa_phong, mode, contract, dat_ngoai, delivery_date, address,
    note, request_id, sales_order, da_ton_tai, ten_don_hang=None, bao_gia_ten=None,
) -> str | None:
    """§5.5 — một `Portal De Xuat Mua` "Đã duyệt" đứng sau MỌI đơn quản lý
    đặt trực tiếp, `nguoi_duyet` là chính họ, `tu_duyet = 1`.

    KHÔNG dùng `PortalDeXuatMua.gui_duyet()`/`.duyet()` (Task 3): hai
    phương thức đó gắn CỨNG vào máy trạng thái Nháp → Chờ duyệt → Đã duyệt
    (phiếu này SINH RA đã "Đã duyệt", không có ai chờ duyệt) và `gui_duyet()`
    bắt buộc `sinh_ma()` không được lỗi — điều đó ĐÚNG cho nhân viên GỬI
    DUYỆT (guard cấp tài khoản đã bắt buộc Mã ngắn từ trước), nhưng SAI cho
    đường đặt trực tiếp của quản lý (QĐ điều phối viên 19/08): xem carve-out
    thiếu Mã ngắn ngay dưới.

    `da_ton_tai=True` (BR-O12, bấm lại) — KHÔNG tạo phiếu thứ hai, tìm phiếu
    đã đứng sau `sales_order` đó mà trả về. Một `sales_order` cũ TRƯỚC
    Task 7 (đặt thẳng, không qua đường này) có thể không có phiếu nào đứng
    sau — trả `None`, đúng tinh thần "102 đơn cũ không có phiếu đề xuất"
    (`TestDeXuatMaTraCuuTrenDonHang`), không tự bịa một phiếu cho quá khứ.
    """
    if da_ton_tai:
        # Lọc CẢ `request_id` — `sales_order` một mình không phải khoá định
        # danh của lần bấm này, chỉ là hệ quả của nó. `request_id` mới thật
        # sự là thứ BR-O12 dùng để nhận ra "đây là cú bấm lại", nên đây mới
        # là điều kiện CHÍNH XÁC, không phải suy đoán qua kết quả phụ.
        #
        # Tra theo chứng từ thật đứng sau: phiếu của một yêu cầu báo giá mang
        # `bao_gia`, không mang `sales_order` (spec 2026-10-12 §5).
        khoa_tra = {"bao_gia": bao_gia_ten} if bao_gia_ten else {"sales_order": sales_order}
        return frappe.db.get_value(
            "Portal De Xuat Mua", {**khoa_tra, "request_id": request_id}, "name"
        )

    # Đọc lại dòng hàng THẬT từ chính Sales Order vừa tạo — canonical hoá
    # item_code + gộp dòng trùng đã được `dat_hang.tao_sales_order` làm rồi
    # (BR-R… chuẩn hoá case/khoảng trắng), không viết lại lần hai ở đây.
    # Bỏ dòng giữ chỗ kỹ thuật `ITEM_GIU_CHO` — nó không phải một mặt hàng
    # khoa "đề xuất", chỉ để ERPNext lưu được đơn toàn dòng đặt ngoài.
    bang_dong, cha = (
        ("Quotation Item", bao_gia_ten) if bao_gia_ten else ("Sales Order Item", sales_order)
    )
    dong = [
        {
            "item_code": r.item_code,
            "so_luong_de_xuat": r.qty,
            "so_luong_duyet": r.qty,
        }
        for r in frappe.get_all(
            bang_dong, filters={"parent": cha},
            fields=["item_code", "qty"],
        )
        if r.item_code != ITEM_GIU_CHO
    ]

    nguoi = frappe.session.user
    gio = frappe.utils.now_datetime()
    doc = frappe.get_doc({
        "doctype": "Portal De Xuat Mua",
        "customer": customer, "khoa_phong": khoa_phong,
        # Task 2 (gộp luồng đặt hàng) — `loai_don` đã xoá khỏi doctype.
        # `PortalDeXuatMua._suy_nguon_gia()` (validate(), chạy ngay trong
        # `.insert()` bên dưới) tự suy `nguon_gia` từng dòng từ `hdnt`,
        # không cần khai "loại đơn" ở đây nữa.
        "hdnt": contract if mode == "hdnt" else None,
        "ngay_can": delivery_date, "dia_chi_giao": address,
        "request_id": request_id, "sales_order": sales_order,
        "bao_gia": bao_gia_ten,
        "items": dong, "dat_ngoai": frappe.parse_json(dat_ngoai) if isinstance(
            dat_ngoai, str
        ) else (dat_ngoai or []),
        "ghi_chu": note,
        "ten_don_hang": ten_don_hang or "",
        "ly_do_yeu_cau": "Đặt hàng trực tiếp qua giỏ hàng quản lý (tự động duyệt).",
        "trang_thai": TRANG_THAI_DA_DUYET,
        "thoi_diem_gui": gio, "thoi_diem_duyet": gio,
        "nguoi_duyet": nguoi, "duyet_voi_tu_cach": "Quản lý chính",
        # `tu_duyet` KHÔNG khai tay ở đây — `PortalDeXuatMua._suy_tu_duyet()`
        # (validate(), Task 7 review M4) tự tính từ `nguoi_duyet == owner`
        # ngay khi `insert()` chạy (`owner` đã là `frappe.session.user` từ
        # trước validate()); giữ tay ở đây sẽ là hai nơi cùng viết một sự
        # thật, đúng thứ `.duyet()` (Task 3) đã tự nhắc mình tránh.
    })
    try:
        doc.ma_de_xuat = sinh_ma(customer, khoa_phong)
    except frappe.ValidationError:
        # QĐ điều phối viên 19/08 ("Blocker 2") — thiếu `Customer.
        # custom_ma_ngan` KHÔNG được chặn đơn trực tiếp của quản lý (khác
        # nhân viên GỬI DUYỆT, nơi guard cấp tài khoản đã bắt buộc Mã ngắn
        # từ trước khi có tài khoản `Nhân viên khoa`). Mã tra cứu là tiện
        # ích đối chiếu, không phải điều kiện đúng đắn của một đơn hàng —
        # không bao giờ để nó chặn một bệnh viện mua hàng. Để rỗng, không
        # throw.
        doc.ma_de_xuat = None
    doc.insert(ignore_permissions=True)

    if bao_gia_ten:
        frappe.db.set_value("Quotation", bao_gia_ten, {
            "custom_de_xuat": doc.name,
            "custom_ten_don_hang": doc.get("ten_don_hang") or "",
        })
    else:
        gia_tri_don = {
            "custom_de_xuat": doc.name,
            "custom_ma_tra_cuu": doc.ma_de_xuat,
        }
        if cot_ten_don_hang_ton_tai():
            # Nhánh QUẢN LÝ ĐẶT THẲNG — đường thứ hai từ CÙNG một giỏ hàng
            # (`portal_order_place`), song song với `de_xuat_duyet.duyet_va_tao_
            # don` của nhân viên khoa. Sửa một nhánh mà quên nhánh kia là đúng
            # một nửa người dùng gõ tên xong không thấy tên đâu.
            gia_tri_don["custom_ten_don_hang"] = doc.get("ten_don_hang") or ""
        frappe.db.set_value("Sales Order", sales_order, gia_tri_don)

    # Task 4 — ghi SAU `doc.insert()`: trước điểm đó `doc.name` còn rỗng
    # (đơn tự duyệt của quản lý — hàm này SINH RA phiếu, không đi qua
    # gui_duyet()/duyet() nên không có dòng nhật ký nào khác kể việc này).
    # `vai=VAI_HE_THONG` (brief) — không phải hành động của MỘT người,
    # `nguoi_thao_tac` bỏ trống đúng ngữ nghĩa `nhat_ky.ghi()` dành cho vai
    # đó, tương tự `duyet_va_tao_don`.
    from miyano_portal import nhat_ky
    nhat_ky.ghi(
        nhat_ky.SK_BAO_GIA_TAO if bao_gia_ten else nhat_ky.SK_DON_TAO,
        customer=customer, khoa_phong=khoa_phong, de_xuat=doc.name,
        sales_order=sales_order, vai=nhat_ky.VAI_HE_THONG,
    )
    return doc.name


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
        # VĐ-7 (hoàn phần chưa giao vào hạn mức Blanket Order) đã khép theo
        # spec 2026-10-09 §9: đơn từ cổng không còn tiêu hạn mức hợp đồng
        # nào, nên không có gì để hoàn.
        return "Hoàn thành (đóng sớm)"
    if so_status == "Cancelled":
        return "Đã huỷ"
    if float(per_delivered or 0) > 0:
        return "Đang giao"
    if so_status == "Draft":
        return "Chờ xác nhận"
    # To Deliver and Bill / To Bill / To Deliver, all with 0 delivered so far.
    return "Đang xử lý"


# `workflow_state` của Sales Order mà CỔNG phải đọc riêng, vì nó ĐÈ LÊN
# `so.status` gốc của ERPNext: `Từ chối` — state THẬT của máy trạng thái
# `Sales Order - Client Portal` (`setup/install_workflow.py`), Sales User bấm
# từ "Chờ Miyano xác nhận", `doc_status = 0`. Đặt tên MỘT LẦN ở đây, ngay
# trên hàm đọc nó, dùng chung cho `_so_status_vi_full`,
# `_TRANG_THAI_GHI_DE_WORKFLOW` và khối SQL của `_sql_giai_doan`.
WF_TU_CHOI = "Từ chối"


def _so_status_vi_full(so_status, per_delivered, workflow_state) -> str:
    """`_so_status_vi` chỉ đọc từ điển trạng thái GỐC của ERPNext
    (`so.status`), không biết gì về `workflow_state` của Client Portal. Một
    hàm DÙNG CHUNG cho danh sách đơn (`portal_order_history`) lẫn chi tiết
    đơn (`portal_order_track`), không phải hai lần viết tay điều kiện này.
    """
    # Review vòng 1 Task 11 (Important) — `Từ chối` là state THẬT của máy
    # trạng thái (Sales User bấm từ "Chờ Miyano xác nhận", `doc_status = 0`).
    # Thiếu nhánh này, một đơn Miyano ĐÃ TỪ CHỐI đọc ra "Chờ xác nhận" — y
    # hệt một đơn đang sống — và khoa chờ vô hạn một lô hàng không bao giờ
    # tới. Đo được trên site: `MD-HUYETHOC-260821-01`, khoa `KP-00002`, đúng
    # khoa của tài khoản nghiệm thu.
    #
    # Nhãn nêu rõ AI từ chối: "Từ chối" trần trùi trùng nghĩa với trạng thái
    # phiếu đề xuất (quản lý BỆNH VIỆN từ chối) — hai sự kiện khác hẳn nhau
    # về người ra quyết định và về việc khoa phải làm tiếp.
    if workflow_state == WF_TU_CHOI:
        return "Miyano đã từ chối"
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


# Brief 2026-08-16 (vá hồi quy phân trang) — trước bản này, chip lọc trạng
# thái ở Orders.vue lọc PHÍA CLIENT trên đúng MỘT trang đã tải: khách chọn
# "xem 10" rồi bấm "Chờ xác nhận" thấy TRỐNG dù đơn khớp nằm ở trang 2 —
# khách kết luận SAI là mình không có đơn nào đang chờ. `status_vi` (nhãn
# khách nhìn thấy) là GIÁ TRỊ SUY RA từ `status`/`per_delivered`/
# `workflow_state` qua `_so_status_vi_full`, không phải cột DB — hàm dưới
# đây dịch NGƯỢC mỗi nhãn trong `FILTERS` (Orders.vue) thành đúng bộ
# filters/or_filters SQL tương đương, để lọc được NGAY TRONG TRUY VẤN, dùng
# CHUNG cho cả `portal_order_history` (lọc + đếm `tong`) và
# `portal_dashboard_kpi` (đếm KPI) — viết tay điều kiện này hai lần là đúng
# kiểu lệch nhau đã từng bắt ở `_so_status_vi`/`_so_status_vi_full`.
# Đúng các state mà `_so_status_vi_full` ghi đè `so.status` — dựng TỪ chính
# các hằng đó, không chép lại chuỗi. Một state được thêm nhãn ở hàm kia mà
# quên thêm vào đây thì hai tầng nói hai điều khác nhau về CÙNG một đơn:
# danh sách hiện "Miyano đã từ chối" trong khi chip/KPI vẫn đếm nó là "Chờ
# xác nhận". Đó chính là cách `Từ chối` lọt lưới ở bản đầu Task 11.
#
# (Không có chip nào của `_dieu_kien_loc_trang_thai_don` LỌC RA đơn bị từ
# chối — cố ý: `portal_order_history` nay chỉ nuôi khối tóm tắt ở Dashboard
# và phép đếm KPI, không còn màn danh sách có chip nào. Chỗ tìm lại một yêu
# cầu đã chết là chip "Từ chối" của `portal_yeu_cau_cua_toi`.)
_TRANG_THAI_GHI_DE_WORKFLOW = [WF_TU_CHOI]


def _dieu_kien_loc_trang_thai_don(trang_thai: str) -> tuple:
    """Trả `(filters, or_filters)` khớp ĐÚNG nhánh của `_so_status_vi_full`
    ứng với nhãn `trang_thai` (một trong các chip của `Orders.vue`, KHÔNG
    kể "Tất cả"). Ném lỗi nếu nhãn lạ — không âm thầm trả về "không lọc gì"
    khi frontend gửi một chip mà backend chưa biết."""
    if trang_thai == "Đã huỷ":
        return [["status", "=", "Cancelled"]], None

    khong_ghi_de = [["workflow_state", "not in", _TRANG_THAI_GHI_DE_WORKFLOW]]
    if trang_thai == "Chờ xác nhận":
        return khong_ghi_de + [["status", "=", "Draft"], ["per_delivered", "<=", 0]], None
    if trang_thai == "Đang xử lý":
        return khong_ghi_de + [
            ["status", "not in", ["Completed", "Closed", "Cancelled", "Draft"]],
            ["per_delivered", "<=", 0],
        ], None
    if trang_thai == "Đang giao":
        return khong_ghi_de + [
            ["status", "not in", ["Completed", "Closed", "Cancelled"]],
            ["per_delivered", ">", 0],
        ], None
    if trang_thai == "Hoàn thành":
        return khong_ghi_de + [["status", "=", "Completed"]], None
    frappe.throw(f"Trạng thái lọc không hợp lệ: {trang_thai}")


def _pham_vi_filters() -> list:
    """`pham_vi_don()` (dict `{"custom_khoa_phong": ...}` hoặc `{}`) đổi
    sang khuôn `filters` kiểu LIST mà `frappe.get_list` trên `Sales Order`
    đang dùng ở file này (`_dieu_kien_loc_trang_thai_don` trả cùng khuôn) —
    một hàm chuyển khuôn DÙNG CHUNG, không phải mỗi endpoint tự viết
    `["custom_khoa_phong", "=", ...]` một kiểu riêng.

    Nuôi `portal_order_history`/`_dem_don_theo_trang_thai` (nên cả `portal_
    dashboard_kpi`) — HAI endpoint traffic cao nhất của cổng.

    SỬA (fix-wave 2026-08-18, V2 — Important): bản trước xây filter tham
    chiếu THẲNG `custom_khoa_phong` mà KHÔNG qua `_cot_khoa_phong_ton_tai()`
    — khác với `_ten_don_trong_pham_vi()`/`dam_bao_xem_duoc()` (đã có lưới
    từ Vòng sửa 3). Kết quả CUỐI CÙNG của `frappe.get_list` vẫn an toàn
    trên site test hôm nay nhờ tầng hook (`permissions.sales_query`) CŨNG
    chặn — nhưng đó là hai lớp AND lại che mất khoảng hở của nhau, không
    phải bằng chứng lớp này tự an toàn: filter do hàm này sinh ra bị AND
    thẳng vào WHERE cùng điều kiện hook, và MariaDB phải phân giải tên cột
    `custom_khoa_phong` lúc PARSE — không có short-circuit theo giá trị
    runtime của vế còn lại. Trên một site CHƯA chạy patch (cột thật sự
    không tồn tại), câu đó vẫn ném 1054 thô bất kể hook có trả `"1=0"` hay
    không. Thiếu cột thì FAIL-CLOSED (một filter không khớp bản ghi nào,
    cùng sentinel `__khong_don_nao__` mà `_loc_qua_don_cha` đã dùng), KHÔNG
    được để lỗi CSDL thô lọt ra."""
    pham_vi = pham_vi_don()
    if not pham_vi:
        return []
    if not _cot_khoa_phong_ton_tai():
        return [["name", "in", ["__khong_don_nao__"]]]
    return [["custom_khoa_phong", "=", v] for v in pham_vi.values()]


@frappe.whitelist()
def portal_order_history(limit=20, start=0, trang_thai=None) -> dict:
    """Brief 2026-08-15 (phân trang) — hình dạng trả về ĐỔI từ list sang
    `{"rows": [...], "tong": N}` (khuôn `portal_catalog_gop`), LUÔN
    LUÔN — endpoint này không nuôi dropdown nào (khác ba endpoint kiêm-
    hai-vai của api/kho.py), chỉ nguồn cho đúng màn Orders.vue + preview ở
    Dashboard.vue. Đã cập nhật MỌI caller (Dashboard.vue, test_e2e_flow.py,
    test_e6_mua_le.py, test_tracking.py) sang đọc `.rows`.

    `trang_thai` (brief 2026-08-16, vá hồi quy) — nhãn tiếng Việt của MỘT
    chip lọc (Orders.vue `FILTERS`), lọc PHÍA SERVER qua
    `_dieu_kien_loc_trang_thai_don` thay vì client tự lọc mảng đã tải.
    `None`/rỗng = không lọc, giữ NGUYÊN hành vi cũ cho mọi caller không
    truyền tham số này.

    Đếm `tong` qua `frappe.get_list` (không phải `frappe.db.count`/
    `frappe.get_all`) — Sales Order được scoping theo khách hàng qua
    `permission_query_conditions` (hooks.py), `get_all`/`db.count` BỎ QUA
    tầng đó và sẽ đếm lẫn đơn của khách khác. `frappe.db.count` cũng KHÔNG
    nhận `or_filters` (cần cho nhánh "Đã huỷ" ở trên) — `get_list` nhận cả
    hai, và vẫn tôn trọng scoping.
    """
    filters, or_filters = [], None
    if trang_thai:
        filters, or_filters = _dieu_kien_loc_trang_thai_don(trang_thai)
    # Bước 8 — Nhân viên khoa chỉ thấy đơn của khoa mình; Quản lý
    # (`pham_vi_don() == {}`) không bị lọc thêm gì ở đây.
    filters = filters + _pham_vi_filters()

    tong = frappe.get_list(
        "Sales Order", filters=filters, or_filters=or_filters,
        fields=["count(name) as tong"],
    )[0].tong
    rows = frappe.get_list(
        "Sales Order",
        filters=filters, or_filters=or_filters,
        # `workflow_state` — nuôi `_so_status_vi_full` bên dưới.
        #
        # Task 7 — `custom_loai_don` ĐÃ BỎ khỏi danh sách này. Nó từng được
        # trả ra dưới tên `loai_don` cho một badge "Mua lẻ / Theo HĐNT" trên
        # màn danh sách; badge đó không còn tồn tại và KHÔNG view nào đọc
        # khoá đó từ endpoint này (`OrderDetail.vue` là nơi duy nhất đọc
        # `loai_don`, và nó được `portal_order_track` nuôi). Giữ lại thì
        # phải giữ đúng nghĩa MỚI của giá trị ở một chỗ thứ hai không ai
        # dùng — thêm một bản soi gương để trôi lệch, không đổi lại được gì.
        # Bỏ CẢ cột khỏi `fields`, không chỉ bỏ dòng đổi tên: để cột lại mà
        # bỏ dòng đổi tên là rò thẳng tiền tố nội bộ `custom_` ra response.
        fields=["name", "transaction_date", "grand_total", "status", "per_delivered",
                "workflow_state", "custom_yeu_cau_goc",
                "custom_ma_tra_cuu"],
        # tiebreak `name` — `transaction_date`/`creation` không đủ duy
        # nhất giữa hai trang (brief 2026-08-15).
        order_by="transaction_date desc, creation desc, name desc",
        limit_page_length=int(limit), limit_start=int(start),
    )
    for r in rows:
        r["status_vi"] = _so_status_vi_full(r.pop("status"), r.get("per_delivered"), r.get("workflow_state"))
        r["yeu_cau_goc"] = r.pop("custom_yeu_cau_goc") or ""
        # Task 6, QĐ-A4 — mã của khách (`DXA-HUYETHOC-260819-01`), CẠNH
        # `name` (SAL-ORD-*, mã hệ thống), không THAY nó: khách đọc mã của
        # họ, Miyano đối chiếu bằng SAL-ORD-*. Đơn CŨ chưa từng đi qua một
        # phiếu đề xuất để trống — hợp lệ, không phải lỗi.
        r["ma_tra_cuu"] = r.pop("custom_ma_tra_cuu") or ""
    return {"rows": rows, "tong": tong}


# ---- Task 11 (QĐ-G11) — MỘT danh sách, MỘT dòng đời ---------------------
#
# Trước bản này một yêu cầu của khoa nằm ở "Đề xuất mua" khi còn là phiếu
# rồi NHẢY sang "Đơn hàng của tôi" sau khi quản lý duyệt. Để tìm lại yêu
# cầu của chính mình, nhân viên phải biết trước nó đang ở giai đoạn NỘI BỘ
# nào — tức phải học sơ đồ kiến trúc của hệ thống.
#
# `giai_doan` là dòng đời DUY NHẤT mà người dùng nhìn thấy. Nó KHÔNG thay
# hai từ điển trạng thái đang có (`Portal De Xuat Mua.trang_thai` và
# `_so_status_vi_full`) — nó là một lớp THÔ HƠN phủ lên cả hai, đủ để trả
# lời đúng câu người dùng hỏi ("yêu cầu của tôi tới đâu rồi?"). Nhãn chi
# tiết của đơn vẫn đi kèm ở `trang_thai_don` để màn danh sách không nuốt
# mất tín hiệu "đang chờ CHÍNH BẠN đồng ý".
#
# Ba `WF_*` mà câu SQL bên dưới dùng khai ở TRÊN `_so_status_vi_full` — một
# nguồn duy nhất cho cả hàm suy nhãn chi tiết, danh sách trạng thái ghi đè,
# và khối CASE này. Ba bản sao chuỗi là đúng cách `Từ chối` lọt lưới lần
# đầu: nó được đặc biệt hoá ở cấp phiếu mà quên ở cấp đơn.
# Ruling P54 (chủ đầu tư, 26/08/2026) — TÁCH KHOÁ KHỎI NHÃN.
#
# Tới trước bản này, bảy hằng số dưới đây là CHÍNH CHỮ TIẾNG VIỆT in trên
# chip. Cùng một chuỗi vì thế gánh BA vai: chữ hiển thị, khoá lọc
# `giai_doan` của `portal_yeu_cau_cua_toi`, và giá trị đi trong URL
# (`?chip=` — `YeuCauList.vue` ghi vào, `DeXuatDetail.vue` mang trả lại).
# Hệ quả: sửa một chữ vì lý do BIÊN TẬP làm chết mọi liên kết đã gửi cho
# bệnh viện. Đó là đúng lớp lỗi "một thứ gánh hai vai" mà cả nhánh này đang
# sửa, chỉ là lần này nó nằm ở một chuỗi chứ không ở một cột.
#
# Nay: hằng số là KHOÁ NỘI BỘ, ASCII, không dấu, và KHÔNG BAO GIỜ ĐỔI THEO
# LỜI HIỂN THỊ NỮA. Nhãn tiếng Việt ("Nháp", "Chờ quý vị đồng ý", …) sống ở
# ĐÚNG MỘT nơi: `frontend/src/format.js::NHAN_GIAI_DOAN`.
#
# CỐ Ý KHÔNG đặt thêm một bảng nhãn ở đây rồi trả kèm trong response. Chip
# phải vẽ được TRƯỚC khi có dòng nào tải về, nên giao diện buộc phải giữ
# bảng ánh xạ của nó; thêm một bản thứ hai ở máy chủ là dựng lại đúng cái
# ngã ba mà `_so_status_vi`/`_so_status_vi_full` đã phải gộp lại một lần
# rồi, và mà docstring `_sql_giai_doan()` ngay dưới tự dặn phải tránh.
GIAI_DOAN_NHAP = "nhap"
GIAI_DOAN_CHO_DUYET = "cho_duyet"
GIAI_DOAN_DA_DUYET = "da_duyet"
GIAI_DOAN_DA_GIAO = "da_giao"
GIAI_DOAN_TU_CHOI = "tu_choi"
GIAI_DOAN_DA_HUY = "da_huy"

# Bốn giai đoạn của QĐ-G11 + HAI ngõ cụt. Giai đoạn "chờ khách đồng ý" của
# đơn đã bỏ (patch v1_44): vòng báo giá nay nằm trên Quotation, ở tab báo giá. Hai ngõ cụt KHÔNG phải phần thừa:
# chúng là trạng thái THẬT mà chính người dùng đưa yêu cầu của mình vào
# (bấm Huỷ, hoặc bị quản lý từ chối), và người vừa làm việc đó là người đi
# tìm lại nó ngay sau đó — đúng bài học "Việc (d)" của `DeXuatList.vue`.
GIAI_DOAN_HOP_LE = (
    GIAI_DOAN_NHAP, GIAI_DOAN_CHO_DUYET, GIAI_DOAN_DA_DUYET, GIAI_DOAN_DA_GIAO,
    GIAI_DOAN_TU_CHOI, GIAI_DOAN_DA_HUY,
)

# BÍ DANH — bộ nhãn CŨ đã từng vừa là chữ hiển thị vừa là khoá, tức chính
# những chuỗi đã đi ra ngoài trong `?chip=` và trong mọi lời gọi API viết
# trước 26/08/2026. Một liên kết hợp lệ ngày hôm qua không được ném lỗi,
# cũng không được rơi lặng lẽ về "Tất cả".
#
# ĐÓNG BĂNG. Không thêm nhãn MỚI vào đây — thêm là buộc lại nhãn vào định
# danh, đúng thứ P54 vừa gỡ ra. Bảng này chỉ được PHÉP co lại (khi đã chắc
# không còn liên kết cũ nào ngoài đời), không được phép nở ra.
BI_DANH_GIAI_DOAN_CU = {
    "Nháp": GIAI_DOAN_NHAP,
    "Chờ duyệt": GIAI_DOAN_CHO_DUYET,
    "Đã duyệt": GIAI_DOAN_DA_DUYET,
    # Giai đoạn đã bỏ: link cũ rơi về "Đã duyệt" — đơn cũ của vòng báo giá
    # đã chuyển về chờ Miyano xác nhận (patch v1_44).
    "Chờ báo giá": GIAI_DOAN_DA_DUYET,
    "cho_khach_dong_y": GIAI_DOAN_DA_DUYET,
    "Đã giao": GIAI_DOAN_DA_GIAO,
    "Từ chối": GIAI_DOAN_TU_CHOI,
    "Đã huỷ": GIAI_DOAN_DA_HUY,
}


def _khoa_giai_doan(giai_doan: str) -> str:
    """Chuẩn hoá tham số `giai_doan` của client về KHOÁ nội bộ.

    Nhận khoá mới, HOẶC một nhãn cũ trong `BI_DANH_GIAI_DOAN_CU`. Mọi thứ
    khác vẫn NÉM y như trước — bí danh là một lối vào có DANH SÁCH, không
    phải một cái cống.

    KHÔNG viết thành `return BI_DANH_GIAI_DOAN_CU.get(gd, gd)`: dạng đó cho
    MỌI chuỗi lạ đi thẳng qua, biến phép lọc thành im lặng trả rỗng thay vì
    báo lỗi — đúng thứ `test_giai_doan_la_thi_bao_loi_chu_khong_am_tham_bo_
    loc` canh từ Task 11.
    """
    if giai_doan in GIAI_DOAN_HOP_LE:
        return giai_doan
    khoa = BI_DANH_GIAI_DOAN_CU.get(giai_doan)
    if khoa:
        return khoa
    frappe.throw(
        f"Giai đoạn không hợp lệ: {giai_doan}", frappe.ValidationError
    )


def _sql_giai_doan(tt: str, so: str) -> str:
    """Biểu thức SQL suy `giai_doan`. `tt` là cột trạng thái của PHIẾU
    (hoặc `null` cho nhánh đơn-không-qua-đề-xuất), `so` là alias bảng
    `tabSales Order`.

    ĐỊNH NGHĨA MỘT LẦN, dùng cho CẢ lọc, CẢ đếm `tong`, CẢ hiển thị — nếu
    lọc ở SQL còn nhãn suy ở Python thì hai vế sẽ trôi khỏi nhau, đúng lỗi
    `_so_status_vi`/`_so_status_vi_full` đã phải gộp lại một lần rồi.

    Thứ tự nhánh là CÓ CHỦ Ý: trạng thái PHIẾU thắng trước. Một phiếu đang
    "Chờ duyệt sửa" đã có đơn đứng sau, nhưng thứ nó đang CHỜ là quản lý,
    không phải Miyano — hiện "Đã duyệt" ở đó là nói sai ai đang giữ việc.

    HAI ngõ cụt được xét ở CẢ HAI cấp, không riêng cấp phiếu (review vòng 1,
    Important): `Từ chối` là state THẬT của Sales Order (`setup/
    install_workflow.py` — Sales User bấm từ "Chờ Miyano xác nhận"), và
    trước bản vá nó rơi qua hết mọi nhánh vào `else` → một đơn Miyano đã
    huỷ đọc ra "Đã duyệt", khoa chờ vô hạn. Một ngõ cụt không tìm lại được
    thì hai giai đoạn ngõ cụt của QĐ-G11 trở thành trang trí.

    Ruling P42 — "Đã giao" đòi `per_delivered >= 100`, KHÔNG phải `> 0`.
    Giao 25% mà báo "Đã giao" là sai với khoa đang chờ nốt 75%, và nó cãi
    nhau với nhãn phụ "Đang giao" đứng ngay cạnh trên CÙNG một dòng. Không
    thêm giai đoạn thứ sáu (QĐ-G11 chốt năm) — nhãn phụ và thanh tiến độ
    đã nói đủ phần còn lại; đổi lại, đơn giao gần đủ nằm ở "Đã duyệt" lâu
    hơn, chấp nhận được.

    Ruling P54 — khối CASE này sinh KHOÁ chứ không sinh nhãn tiếng Việt, nên
    nó cũng thôi phải nhét chữ có dấu vào chuỗi SQL.
    `null` trên `{tt}` (nhánh đơn) làm mọi phép so sánh trạng thái phiếu ra
    NULL — falsy trong SQL — nên nhánh đó rơi thẳng xuống các luật đơn hàng
    mà không cần một biểu thức riêng.
    """
    return f"""case
        when {tt} = '{TRANG_THAI_NHAP}' then '{GIAI_DOAN_NHAP}'
        when {tt} in ('{TRANG_THAI_CHO_DUYET}', '{TRANG_THAI_CHO_DUYET_SUA}')
            then '{GIAI_DOAN_CHO_DUYET}'
        when {tt} = '{TRANG_THAI_TU_CHOI}' then '{GIAI_DOAN_TU_CHOI}'
        when {tt} = '{TRANG_THAI_DA_HUY}' then '{GIAI_DOAN_DA_HUY}'
        when {so}.name is null then '{GIAI_DOAN_DA_DUYET}'
        when {so}.docstatus = 2 or {so}.status = 'Cancelled' then '{GIAI_DOAN_DA_HUY}'
        when {so}.workflow_state = '{WF_TU_CHOI}' then '{GIAI_DOAN_TU_CHOI}'
        when {so}.status in ('Completed', 'Closed') or {so}.per_delivered >= 100
            then '{GIAI_DOAN_DA_GIAO}'
        else '{GIAI_DOAN_DA_DUYET}'
    end"""


# ---------------------------------------------------------------------------
# Yêu cầu báo giá (spec 2026-10-12 §6). Hai tab của màn danh sách dùng CHUNG
# các mảnh SQL dưới đây: tab này nhận đúng những phiếu tab kia bỏ ra, nên một
# luật viết hai lần là hai tab hoặc cùng hiện, hoặc cùng giấu một phiếu.
# ---------------------------------------------------------------------------
NHOM_BAO_GIA = ("nhap", "dang_bao_gia", "cho_dong_y", "da_dong_y", "da_dong")

# Trạng thái mà khách được xem đơn giá. "Chờ Miyano báo giá" KHÔNG có ở đây,
# kể cả khi báo giá còn giữ giá gợi ý sau một lần khách sửa số lượng: giá
# Miyano chưa gửi lại không phải là báo giá.
_BAO_GIA_HIEN_GIA = (
    bao_gia.TT_CHO_KHACH, bao_gia.TT_DA_DONG_Y, bao_gia.TT_KHACH_TU_CHOI, bao_gia.TT_HET_HAN,
)


def _cot_bao_gia_ton_tai() -> bool:
    """Lưới an toàn lúc triển khai: mã mới chạy trên site chưa `bench migrate`
    thì chưa có cột `bao_gia` trên phiếu."""
    return frappe.db.has_column("Portal De Xuat Mua", "bao_gia")


def _sql_phieu_cho_bao_gia(p: str) -> str:
    """Phiếu THUẦN chờ báo giá: có dòng chờ báo giá hoặc dòng gõ tay, và không
    có dòng nào đã có giá. Phiếu nháp còn trộn (chưa gửi duyệt nên chưa tách)
    không thuộc nhóm này."""
    return f"""(
        (exists (select 1 from `tabPortal De Xuat Mua Item` i
                 where i.parent = {p}.name and i.nguon_gia = 'Chờ báo giá')
         or exists (select 1 from `tabSales Order Dat Ngoai Item` d
                    where d.parent = {p}.name and d.parenttype = 'Portal De Xuat Mua'))
        and not exists (select 1 from `tabPortal De Xuat Mua Item` i2
                        where i2.parent = {p}.name
                          and i2.nguon_gia in ('Bảng giá', 'Hợp đồng'))
    )"""


def _sql_thuoc_tab_bao_gia(p: str) -> str:
    """§6.1 — có `bao_gia`, hoặc chưa có cả đơn lẫn báo giá mà là phiếu chờ báo
    giá. Phiếu có `sales_order` mà không có `bao_gia` là đơn "Mua lẻ" của luồng
    cũ: ở lại tab Đơn hàng."""
    return (
        f"(coalesce({p}.bao_gia, '') != '' or (coalesce({p}.sales_order, '') = '' "
        f"and {_sql_phieu_cho_bao_gia(p)}))"
    )


def _sql_an_khoi_tab_don(p: str) -> str:
    """§6.4 — tab Đơn hàng chỉ bỏ phiếu chờ báo giá CHƯA có đơn. Phiếu đã có
    đơn (khách đã đồng ý) hiện ở cả hai tab: bên kia là báo giá, bên này là
    đơn sinh ra từ nó."""
    return (
        f"(coalesce({p}.sales_order, '') = '' and (coalesce({p}.bao_gia, '') != '' "
        f"or {_sql_phieu_cho_bao_gia(p)}))"
    )


def _sql_dem_dot(q: str, trang_thai: str) -> str:
    """Số đợt NHÁP của báo giá `q` đang ở `trang_thai` (spec 2026-10-15 §5.1).
    `'0'` khi site chưa có cột `custom_phieu_goc` (patch v1_45): 1054 lúc
    PARSE, không có short-circuit theo giá trị."""
    from miyano_portal import bao_gia_theo_dot

    if not bao_gia_theo_dot.san_sang():
        return "0"
    return f"""(select count(*) from `tabQuotation` dq
                where dq.custom_phieu_goc = {q}.name and dq.docstatus = 0
                  and dq.workflow_state = '{trang_thai}')"""


def _sql_dot_cho_khach(q: str) -> str:
    return _sql_dem_dot(q, bao_gia.TT_CHO_KHACH)


def _sql_nhom_bao_gia(q: str) -> str:
    # Phiếu gốc đã tách đợt: có đợt chờ khách thì nhóm "chờ đồng ý" thắng mọi
    # thứ; còn đợt Miyano đang báo lại (khách sửa số lượng / thu hồi để sửa)
    # thì "đang báo giá" dù phiếu gốc đã "Đã báo hết"; "Đã báo hết" / "Đã huỷ
    # phần còn lại" còn lại rơi vào `else` → 'da_dong'. Bản Python cùng luật:
    # `_nhom_phieu_goc`.
    return f"""case
        when {q}.name is null then 'nhap'
        when {_sql_dot_cho_khach(q)} > 0 then 'cho_dong_y'
        when {_sql_dem_dot(q, bao_gia.TT_CHO_MIYANO)} > 0 then 'dang_bao_gia'
        when {q}.workflow_state = '{bao_gia.TT_CHO_MIYANO}' then 'dang_bao_gia'
        when {q}.workflow_state = '{bao_gia.TT_CHO_KHACH}' then 'cho_dong_y'
        when {q}.workflow_state = '{bao_gia.TT_DA_DONG_Y}' then 'da_dong_y'
        else 'da_dong'
    end"""


@frappe.whitelist()
def portal_yeu_cau_cua_toi(limit=20, start=0, giai_doan=None, khoa_phong=None) -> dict:
    """QĐ-G11 — danh sách HỢP NHẤT phiếu đề xuất + đơn hàng, MỘT dòng cho
    mỗi yêu cầu, ở bất kỳ giai đoạn nào của dòng đời.

    Rào cản kỹ thuật của việc gộp đã tự mất từ Task 9: đơn hàng mang thẳng
    mã đề xuất, và phiếu giữ `sales_order` trỏ sang đơn — trên CẢ HAI đường
    sinh đơn (`de_xuat_duyet.duyet_va_tao_don` cho luồng duyệt, và
    `_dam_bao_phieu_tu_duyet` cho giỏ hàng quản lý). Gộp vì thế là một phép
    NOT EXISTS trên `sales_order`, không phải một phép khớp mã bằng tay.

    KHÔNG dùng `frappe.get_list`: role `Customer` có ZERO DocPerm trên
    `Portal De Xuat Mua`, nên `get_list` ném `PermissionError` cho MỌI
    Website User TRƯỚC KHI hook phạm vi kịp chạy (xem docstring
    `api/de_xuat.py`). Đường sống là hàm này, và nó phải TỰ hỏi đúng chốt
    phạm vi mà tầng hook hỏi — `get_portal_member()` cho trục khách hàng,
    `pham_vi_don()` cho trục khoa. Hệ quả: điều kiện `permission_query_
    conditions` (`permissions.sales_query`) KHÔNG tự áp lên SQL thô ở đây,
    nên nhánh đơn hàng phải mang bộ lọc khoa của chính nó — đó là lý do
    `dk_don` tồn tại thay vì tin vào tầng hook.

    Cắt trang TRONG SQL (`limit`/`offset` trên truy vấn đã gộp), và `tong`
    đếm SAU khi gộp + SAU khi lọc: đếm trước khi gộp thì phiếu-đã-thành-đơn
    bị tính hai lần, trang cuối rỗng, và khách thấy một con số không khớp
    số dòng đếm được. Lọc `giai_doan` cũng ở SQL, không ở client — lọc trên
    ĐÚNG MỘT trang đã tải chính là hồi quy đã phải vá cho `Orders.vue`
    (brief 2026-08-16).

    03/09/2026 — màn `/duyet` (hàng chờ riêng của quản lý) đã NGHỈ: việc
    duyệt vốn nằm ở màn CHI TIẾT phiếu, `/duyet` chỉ là một danh sách thứ
    hai của cùng bộ dữ liệu. Hàng chờ ấy nay là chính danh sách này lọc
    `giai_doan="cho_duyet"` — cùng bộ trạng thái, vì `_sql_giai_doan()` gom
    CẢ "Chờ duyệt" LẪN "Chờ duyệt sửa" vào khoá đó, đúng hai trạng thái mà
    `frontend/src/cho-duyet.js` đếm cho badge nav.

    `khoa_phong` sang từ màn đó cùng lúc (yêu cầu gốc chủ đầu tư ghi trong
    `DuyetList.vue`: "quản lý sẽ filter theo khoa … để biết khoa nào đang
    mua cái gì mà duyệt"). Nó CHỈ THU HẸP: bộ lọc phạm vi (`dk_phieu`/
    `dk_don`) đã kẹp trước, nên một nhân viên khoa gõ tay khoa của người
    khác nhận về RỖNG, không phải dữ liệu khoa đó. Lọc ở SQL cạnh
    `giai_doan`, không ở client — cùng lý do đã ghi ngay trên.
    """
    # Ruling P54 — nhận KHOÁ, và nhận cả nhãn CŨ qua bí danh (link `?chip=`
    # đã gửi cho bệnh viện, script bên ngoài viết trước 26/08/2026). Chuẩn
    # hoá NGAY ĐÂY, một lần, để phần dưới chỉ còn làm việc với khoá.
    if giai_doan:
        giai_doan = _khoa_giai_doan(giai_doan)

    tv = get_portal_member()
    tham_so = {"kh": tv.customer}
    khoa = pham_vi_don().get("custom_khoa_phong")

    dk_phieu = "p.customer = %(kh)s"
    dk_don = "so.customer = %(kh)s"
    if khoa:
        tham_so["khoa"] = khoa
        dk_phieu += " and p.khoa_phong = %(khoa)s"
        dk_don += " and so.custom_khoa_phong = %(khoa)s"

    # Lưới an toàn lúc triển khai, cùng nguồn kiểm tra với
    # `_pham_vi_filters()`/`permissions._khoa_query_condition`: trên một
    # site CHƯA chạy patch v1_23, cột `Sales Order.custom_khoa_phong` không
    # tồn tại và MariaDB ném 1054 ngay lúc PARSE — không có short-circuit
    # theo giá trị runtime. Thiếu cột thì nhánh ĐƠN HÀNG bị bỏ hẳn với nhân
    # viên khoa (fail-closed: thà câm còn hơn rò đơn của mọi khoa kèm tổng
    # tiền). Nhánh PHIẾU không phụ thuộc cột custom nào nên vẫn tới đúng
    # người — câm đúng chỗ, không câm cả màn.
    co_cot_khoa = _cot_khoa_phong_ton_tai()
    cot_khoa_don = "so.custom_khoa_phong" if co_cot_khoa else "null"
    # Cột TÊN của nhánh đơn — `null` khi site chưa chạy patch v1_34. Không
    # fail-closed như `cot_khoa_don`: thiếu tên chỉ là một ô trống, không
    # phải một lỗ quyền.
    cot_ten_don = (
        "coalesce(so.custom_ten_don_hang, '')"
        if cot_ten_don_hang_ton_tai() else "''"
    )
    # Mã lần đặt của hai phiếu tách — `''` khi site chưa chạy patch v1_41
    # (cùng lập trường với cột tên: một ô trống, không phải một lỗi 500).
    cot_lan_dat = (
        "coalesce(p.ma_lan_dat, '')" if cot_lan_dat_ton_tai() else "''"
    )
    co_nhanh_don = co_cot_khoa or not khoa
    # Spec 2026-10-12 §6.4 — phiếu chờ báo giá chưa có đơn thuộc tab kia.
    #
    # TRỪ chip "Chờ duyệt": đó là HÀNG VIỆC DUYỆT của quản lý, chéo loại. Huy
    # hiệu nav (`frontend/src/cho-duyet.js`) đếm MỌI phiếu "Chờ duyệt" / "Chờ
    # duyệt sửa" rồi dẫn tới `?chip=cho_duyet`; giấu phiếu chờ báo giá ở đây
    # thì quản lý bấm huy hiệu N mà danh sách ít hơn N, và phiếu cần duyệt
    # nằm lẫn với nháp / từ chối / huỷ ở tab kia. Phiếu đó vẫn hiện ở tab báo
    # giá. Mọi chip khác và "Tất cả" giữ nguyên luật loại.
    an_bao_gia = (
        f" and not {_sql_an_khoi_tab_don('p')}"
        if _cot_bao_gia_ton_tai() and giai_doan != GIAI_DOAN_CHO_DUYET else ""
    )

    nhanh_phieu = f"""
        select 'phieu' as nguon, p.name as de_xuat, p.sales_order as sales_order,
               -- `ma` là MÃ CỦA KHÁCH, KHÔNG rơi về `p.name`: tên nội bộ
               -- (`DXM-2026-000xx`, naming_series) là mã hệ thống, không
               -- phải thứ khoa đọc. Phiếu Nháp chưa có mã (mã cấp lúc Gửi
               -- duyệt) → rỗng, và tầng hiển thị nói thẳng "(chưa gửi
               -- duyệt)" — đúng cách `DeXuatList.vue` đã làm trước khi gộp.
               coalesce(nullif(p.ma_de_xuat, ''), '') as ma,
               -- TÊN ĐƠN HÀNG do nhân viên gõ ở giỏ (08/09/2026). Đọc từ
               -- PHIẾU ở nhánh này (`p`), từ `so.custom_ten_don_hang` ở
               -- nhánh đơn bên dưới — hai nhánh, hai nguồn, cùng một cột
               -- kết quả.
               coalesce(p.ten_don_hang, '') as ten_don_hang,
               p.khoa_phong as khoa_phong, p.creation as thoi_diem,
               p.trang_thai as trang_thai_phieu, p.owner as owner,
               so.status as so_status, so.per_delivered as per_delivered,
               so.workflow_state as workflow_state, so.grand_total as grand_total,
               p.name as khoa_sap_xep,
               {_sql_giai_doan("p.trang_thai", "so")} as giai_doan,
               -- Mã lần đặt chung của hai phiếu tách (spec 2026-10-09 §7);
               -- rỗng với phiếu không tách và với đơn không đứng sau phiếu.
               {cot_lan_dat} as ma_lan_dat
        from `tabPortal De Xuat Mua` p
        left join `tabSales Order` so on so.name = p.sales_order
        where {dk_phieu}{an_bao_gia}
    """
    # Đơn KHÔNG đứng sau phiếu nào — đơn cũ (có trước luồng duyệt) và đơn
    # của sáu tài khoản quản lý đang chạy thật. `not exists` trên
    # `sales_order` là ĐÚNG mối nối mã thật ghi, và nó cũng nuốt luôn ca
    # `custom_de_xuat` trỏ vào một phiếu đã bị xoá.
    nhanh_don = f"""
        select 'don', null, so.name, so.name,
               {cot_ten_don}, {cot_khoa_don}, so.creation, null, null,
               so.status, so.per_delivered, so.workflow_state, so.grand_total,
               so.name, {_sql_giai_doan("null", "so")}, ''
        from `tabSales Order` so
        where {dk_don}
          and not exists (
              select 1 from `tabPortal De Xuat Mua` p2
              where p2.customer = %(kh)s and p2.sales_order = so.name
          )
    """
    trong = nhanh_phieu + (f" union all {nhanh_don}" if co_nhanh_don else "")

    # Hai bộ lọc GIAO nhau, dựng cùng một chỗ: quản lý mở chip "Chờ duyệt"
    # rồi chọn khoa là ca dùng chính sau khi màn `/duyet` nghỉ. Áp ở lớp
    # NGOÀI (trên `t`) chứ không nhét vào `dk_phieu`/`dk_don`: nhánh đơn
    # lấy khoa từ một cột khác (`so.custom_khoa_phong`, có thể không tồn
    # tại trên site chưa chạy patch v1_23 — khi đó `cot_khoa_don` là
    # `null`), nên một điều kiện duy nhất trên cột đã hợp nhất `t.khoa_
    # phong` là nơi duy nhất luật này không phải viết hai lần.
    dieu_kien = []
    if giai_doan:
        tham_so["gd"] = giai_doan
        dieu_kien.append("t.giai_doan = %(gd)s")
    if khoa_phong:
        tham_so["kp"] = khoa_phong
        dieu_kien.append("t.khoa_phong = %(kp)s")
    dk_ngoai = (" where " + " and ".join(dieu_kien)) if dieu_kien else ""

    tong = frappe.db.sql(
        f"select count(*) from ({trong}) t{dk_ngoai}", tham_so
    )[0][0]
    rows = frappe.db.sql(
        f"""select * from ({trong}) t{dk_ngoai}
            order by t.thoi_diem desc, t.khoa_sap_xep desc
            limit %(limit)s offset %(start)s""",
        {**tham_so, "limit": int(limit), "start": int(start)},
        as_dict=True,
    )
    for r in rows:
        so_status = r.pop("so_status")
        workflow_state = r.pop("workflow_state")
        r["sales_order"] = r.get("sales_order") or ""
        r["de_xuat"] = r.get("de_xuat") or ""
        r["khoa_phong"] = r.get("khoa_phong") or ""
        r["trang_thai_phieu"] = r.get("trang_thai_phieu") or ""
        # `owner` nuôi đúng một việc ở màn danh sách: có hiện nút "Sửa" cho
        # một phiếu Nháp hay không (`de_xuat_luu_nhap` cho owner HOẶC quản
        # lý). Cùng điều kiện `DeXuatList.vue::coTheSuaNhap` đã dùng —
        # client đoán khác server thì khách gõ xong mới ăn "Phiếu này không
        # phải của bạn" và mất sạch công sửa.
        r["owner"] = r.get("owner") or ""
        # Nhãn CHI TIẾT của đơn — dùng lại ĐÚNG hàm mà `portal_order_
        # history`/`portal_order_track` dùng, không viết bản thứ ba.
        r["trang_thai_don"] = _so_status_vi_full(
            so_status, r.get("per_delivered"), workflow_state
        ) if r["sales_order"] else ""
        r["per_delivered"] = float(r.get("per_delivered") or 0)
        r["grand_total"] = float(r.get("grand_total") or 0)
    return {"rows": rows, "tong": int(tong)}


def _truy_van_tab_bao_gia() -> tuple[str, dict]:
    """SQL trong và tham số của tab báo giá, đã kẹp phạm vi khách + khoa."""
    tv = get_portal_member()
    tham_so = {"kh": tv.customer}
    dk = "p.customer = %(kh)s"
    khoa = pham_vi_don().get("custom_khoa_phong")
    if khoa:
        tham_so["khoa"] = khoa
        dk += " and p.khoa_phong = %(khoa)s"
    trong = f"""
        select p.name as de_xuat,
               -- Tên báo giá chỉ đi ra khi phép nối bên dưới NHẬN nó: phiếu
               -- trỏ sang một báo giá không qua được phép nối mà vẫn mang tên
               -- ra thì màn danh sách dẫn tới một trang chi tiết từ chối.
               coalesce(q.name, '') as bao_gia,
               coalesce(p.sales_order, '') as sales_order,
               coalesce(nullif(p.ma_de_xuat, ''), '') as ma,
               coalesce(p.ten_don_hang, '') as ten_don_hang,
               coalesce(p.khoa_phong, '') as khoa_phong, p.creation as thoi_diem,
               p.trang_thai as trang_thai_phieu, p.owner as owner,
               coalesce(q.workflow_state, '') as trang_thai_bao_gia,
               q.grand_total as grand_total, q.valid_till as han_hieu_luc,
               {_sql_nhom_bao_gia("q")} as nhom,
               -- Số báo giá đang chờ khách trên dòng này: chính phiếu (chưa
               -- tách đợt) hoặc các đợt của nó — huy hiệu đếm ĐỢT (§5.1).
               case when q.workflow_state = '{bao_gia.TT_CHO_KHACH}' then 1
                    else coalesce({_sql_dot_cho_khach("q")}, 0) end as so_cho_dong_y
        from `tabPortal De Xuat Mua` p
        -- Ba vế sau `q.name = p.bao_gia` là bản SQL của
        -- `_la_bao_gia_cong_cua()`: sửa một bên thì sửa bên kia.
        left join `tabQuotation` q
               on q.name = p.bao_gia and q.quotation_to = 'Customer'
              and q.party_name = %(kh)s and q.custom_nguon_don = '{bao_gia.NGUON_CONG}'
        where {dk} and {_sql_thuoc_tab_bao_gia("p")}
    """
    return trong, tham_so


def _kep_trang_bao_gia(limit, start) -> tuple[int, int]:
    """`limit` trong 1..200, `start` >= 0 — cùng lối `cint` rồi kẹp của
    `portal_thong_bao_list`. Giá trị âm hay không phải số từ client không
    được thành lỗi SQL."""
    limit = min(max(frappe.utils.cint(limit) or 20, 1), 200)
    start = max(frappe.utils.cint(start), 0)
    return limit, start


@frappe.whitelist()
def portal_bao_gia_danh_sach(nhom=None, khoa_phong=None, limit=20, start=0) -> dict:
    """Tab "Yêu cầu báo giá" (spec 2026-10-12 §6.2). SQL thô như
    `portal_yeu_cau_cua_toi`, vì vai Customer không có DocPerm trên phiếu lẫn
    Quotation; hàm tự kẹp phạm vi khách và khoa."""
    if nhom and nhom not in NHOM_BAO_GIA:
        frappe.throw(f"Nhóm không hợp lệ: {nhom}", frappe.ValidationError)
    if not _cot_bao_gia_ton_tai():
        return {"rows": [], "tong": 0}
    limit, start = _kep_trang_bao_gia(limit, start)
    trong, tham_so = _truy_van_tab_bao_gia()
    dieu_kien = []
    if nhom:
        tham_so["nhom"] = nhom
        dieu_kien.append("t.nhom = %(nhom)s")
    if khoa_phong:
        tham_so["kp"] = khoa_phong
        dieu_kien.append("t.khoa_phong = %(kp)s")
    dk_ngoai = (" where " + " and ".join(dieu_kien)) if dieu_kien else ""
    tong = frappe.db.sql(f"select count(*) from ({trong}) t{dk_ngoai}", tham_so)[0][0]
    rows = frappe.db.sql(
        f"""select * from ({trong}) t{dk_ngoai}
            order by t.thoi_diem desc, t.de_xuat desc
            limit %(limit)s offset %(start)s""",
        {**tham_so, "limit": limit, "start": start},
        as_dict=True,
    )
    for r in rows:
        duoc_xem_gia = r["trang_thai_bao_gia"] in _BAO_GIA_HIEN_GIA
        r["grand_total"] = float(r["grand_total"] or 0) if duoc_xem_gia else None
        r["han_hieu_luc"] = str(r["han_hieu_luc"]) if r.get("han_hieu_luc") else ""
        r["owner"] = r.get("owner") or ""
        r["so_cho_dong_y"] = int(r.get("so_cho_dong_y") or 0)
    return {"rows": rows, "tong": int(tong)}


@frappe.whitelist()
def portal_bao_gia_dem() -> dict:
    """Số báo giá đang chờ khách đồng ý — huy hiệu trên tab. Phiếu báo theo
    đợt đếm từng đợt đang chờ (spec 2026-10-15 §5.1)."""
    if not _cot_bao_gia_ton_tai():
        return {"cho_dong_y": 0}
    trong, tham_so = _truy_van_tab_bao_gia()
    n = frappe.db.sql(
        f"select coalesce(sum(t.so_cho_dong_y), 0) from ({trong}) t", tham_so
    )[0][0]
    return {"cho_dong_y": int(n)}


def _la_bao_gia_cong_cua(gt, customer) -> bool:
    """Báo giá này có phải của CỔNG và của đúng khách `customer` không.

    MỘT chỗ cho phép kiểm sở hữu (spec §8): `_bao_gia_cua_toi` và
    `_lien_ket_thong_bao` cùng hỏi hàm này. Bản SQL của nó nằm ở phép nối
    trong `_truy_van_tab_bao_gia`. Quotation dùng `party_name`, không có cột
    `customer`. `gt` là `Document` hoặc dict có ba trường dưới đây.
    """
    return bool(
        gt and customer
        and gt.get("quotation_to") == "Customer"
        and gt.get("party_name") == customer
        and gt.get("custom_nguon_don") == bao_gia.NGUON_CONG
    )


def _bao_gia_cua_toi(ten):
    """Chốt hai trục cho MỌI endpoint báo giá (spec §8). Trả `Document`.

    `ten` phải là CHUỖI: `frappe.get_doc`/`frappe.db.get_value` nhận cả dict
    bộ lọc, và thân JSON của request đưa dict tới nguyên vẹn — một bộ lọc kèm
    `grand_total` sẽ biến "tìm thấy / không tìm thấy" thành máy dò đúng cột mà
    endpoint đang giấu. Nạp MỘT lần theo đúng tên đó rồi kiểm trên chính bản
    đã nạp (như `_phieu_cua_toi`), không kiểm một truy vấn rồi nạp truy vấn
    khác.

    Báo giá không phải của cổng (nhân viên tự lập) không hiện, kể cả khi cùng
    khách. Mọi lý do từ chối trả CÙNG một thông điệp: không xác nhận cả sự
    tồn tại của báo giá thuộc khách khác. Hỏi `exists` trước khi nạp vì
    `get_doc` trên một tên không có để lại thông điệp "… not found" trong
    `message_log`, thứ đi ra client và phân biệt được hai ca.
    """
    tv = get_portal_member()
    bg = _nap_bao_gia_trong_pham_vi(ten, tv.customer)
    # Dòng `raise` DUY NHẤT của mọi ca từ chối. Frappe gửi traceback cho client
    # (`exc`, khi `allow_error_traceback` bật): mỗi lý do một dòng `raise` thì
    # số dòng lại phân biệt được "không tồn tại" với "của khách khác".
    if bg is None:
        raise frappe.PermissionError(LOI_KHONG_THAY)
    return bg


def _nap_bao_gia_trong_pham_vi(ten, customer):
    """`Document` nếu người gọi được thấy báo giá này, `None` cho MỌI lý do
    còn lại. Không ném lỗi phân biệt lý do — xem `_bao_gia_cua_toi`."""
    if not isinstance(ten, str) or not ten or not frappe.db.exists("Quotation", ten):
        return None
    try:
        bg = frappe.get_doc("Quotation", ten)
    except frappe.DoesNotExistError:
        frappe.clear_last_message()
        return None
    if not _la_bao_gia_cong_cua(bg, customer):
        return None
    try:
        khoa = pham_vi_don().get("custom_khoa_phong")
    except frappe.PermissionError:
        # Nhân viên khoa chưa được gán khoa: không có phạm vi nào để xét.
        return None
    if khoa and bg.get("custom_khoa_phong") != khoa:
        return None
    return bg


_NHOM_THEO_TRANG_THAI = {
    bao_gia.TT_CHO_MIYANO: "dang_bao_gia",
    bao_gia.TT_CHO_KHACH: "cho_dong_y",
    bao_gia.TT_DA_DONG_Y: "da_dong_y",
}


def _mo_ta_bao_gia(bg) -> dict:
    """Thứ khách được thấy của MỘT Quotation (cả phiếu hoặc một đợt)."""
    trang_thai = bg.get("workflow_state") or ""
    hien_gia = trang_thai in _BAO_GIA_HIEN_GIA
    het_han = bao_gia.qua_han(bg)
    cho_khach = trang_thai == bao_gia.TT_CHO_KHACH
    ma = ""
    if bg.get("custom_de_xuat"):
        ma = frappe.db.get_value("Portal De Xuat Mua", bg.custom_de_xuat, "ma_de_xuat") or ""
    return {
        "bao_gia": bg.name,
        "trang_thai": trang_thai,
        "nhom": _NHOM_THEO_TRANG_THAI.get(trang_thai, "da_dong"),
        "de_xuat": bg.get("custom_de_xuat") or "",
        "sales_order": bao_gia.don_cua_bao_gia(bg) or "",
        "ma": ma,
        "ten_don_hang": bg.get("custom_ten_don_hang") or "",
        "khoa_phong": bg.get("custom_khoa_phong") or "",
        "ngay_tao": str(bg.transaction_date),
        "han_hieu_luc": str(bg.valid_till) if bg.get("valid_till") else "",
        "het_han": het_han,
        "hien_gia": hien_gia,
        "tong_tien": float(bg.grand_total or 0) if hien_gia else None,
        "ly_do_tu_choi": bg.get("custom_ly_do_tu_choi") or "",
        "duoc_dong_y": cho_khach and not het_han,
        "duoc_sua_so_luong": cho_khach and not het_han and la_quan_ly(),
        "items": [
            {
                "name": d.name, "item_code": d.item_code, "item_name": d.item_name,
                "uom": d.uom, "qty": float(d.qty or 0),
                "rate": float(d.rate or 0) if hien_gia else None,
                "amount": float(d.amount or 0) if hien_gia else None,
            }
            for d in bg.items if d.item_code != ITEM_GIU_CHO
        ],
        "dat_ngoai": [
            {
                "ten_hang": d.ten_hang, "dvt": d.dvt, "so_luong": float(d.so_luong or 0),
                "da_xu_ly": int(d.da_xu_ly or 0), "item_khop": d.get("item_khop") or "",
            }
            for d in bg.get("custom_dat_ngoai") or []
        ],
    }


def _cac_dot(goc) -> list:
    """Các đợt của phiếu gốc, theo số đợt. Đợt chép khách/khoa/nguồn của phiếu
    gốc nên đã nằm trong phạm vi người gọi khi phiếu gốc nằm trong đó; vẫn lọc
    lại đúng ba trường đó (phòng thủ nhiều lớp: một đợt bị sửa tay sang khoa
    khác không được lộ qua trang của phiếu gốc)."""
    from miyano_portal import bao_gia_theo_dot

    if not bao_gia_theo_dot.san_sang():
        return []
    truong = ("party_name", "custom_khoa_phong", "custom_nguon_don")
    # So trong Python, chuẩn hoá rỗng: phiếu không khoa có `custom_khoa_phong`
    # là NULL, bộ lọc `= None` của `get_all` không khớp NULL.
    mau = tuple(goc.get(t) or "" for t in truong)
    return [
        frappe.get_doc("Quotation", d.name)
        for d in frappe.get_all(
            "Quotation", filters={"custom_phieu_goc": goc.name},
            fields=["name", *truong], order_by="custom_so_dot asc",
        )
        if tuple(d.get(t) or "" for t in truong) == mau
    ]


def _nhom_phieu_goc(goc, dot) -> str:
    """Bản Python của `_sql_nhom_bao_gia` cho phiếu đã tách đợt."""
    # Chỉ phản chiếu các trạng thái phiếu gốc CÓ ĐỢT đi tới được:
    # `kiem_chuyen_theo_dot` chặn CHO_KHACH / MIYANO_TU_CHOI trên phiếu như vậy.
    if any(d.docstatus == 0 and d.workflow_state == bao_gia.TT_CHO_KHACH for d in dot):
        return "cho_dong_y"
    if goc.get("workflow_state") == bao_gia.TT_CHO_MIYANO or any(
        d.docstatus == 0 and d.workflow_state == bao_gia.TT_CHO_MIYANO for d in dot
    ):
        return "dang_bao_gia"
    return "da_dong"


@frappe.whitelist()
def portal_bao_gia_chi_tiet(ten) -> dict:
    bg = _bao_gia_cua_toi(ten)
    # Email/thông báo trỏ tới tên ĐỢT: trang chi tiết luôn là của phiếu gốc.
    if bg.get("custom_phieu_goc"):
        bg = _bao_gia_cua_toi(bg.custom_phieu_goc)
    kq = _mo_ta_bao_gia(bg)
    dot = _cac_dot(bg)
    kq["dot"] = [
        {**_mo_ta_bao_gia(d), "so_dot": int(d.get("custom_so_dot") or 0),
         "da_tra_ve": bool(d.get("custom_da_tra_ve"))}
        for d in dot
    ]
    kq["con_lai"] = [
        {"name": d.name, "item_code": d.item_code, "item_name": d.item_name,
         "uom": d.uom, "qty": float(d.qty or 0)}
        for d in bg.items if d.item_code != ITEM_GIU_CHO
    ] if dot and bg.get("workflow_state") == bao_gia.TT_CHO_MIYANO else []
    kq["duoc_huy_con_lai"] = bool(dot) and bg.get("workflow_state") == bao_gia.TT_CHO_MIYANO
    # Phiếu gốc đã thôi báo (đã báo hết / huỷ phần còn lại): dòng gõ tay chưa
    # khớp mã không còn ai tìm nữa — không hiện "Miyano đang tìm mã".
    if dot and bg.get("workflow_state") != bao_gia.TT_CHO_MIYANO:
        kq["dat_ngoai"] = []
    kq["da_huy_con_lai"] = bg.get("workflow_state") == bao_gia.TT_HUY_CON_LAI
    # Chỉ khi đã huỷ thật: lý do nhân viên gõ mà chưa chuyển trạng thái là nội bộ.
    kq["ly_do_huy_con_lai"] = (
        (bg.get("custom_ly_do_huy_con_lai") or "") if kq["da_huy_con_lai"] else ""
    )
    if dot:
        kq["nhom"] = _nhom_phieu_goc(bg, dot)
    return kq


@frappe.whitelist()
def portal_bao_gia_dong_y(ten) -> dict:
    """Khách đồng ý báo giá → sinh đơn hàng (spec §4.4). Mọi tài khoản trong
    phạm vi bấm được."""
    bg = _bao_gia_cua_toi(ten)
    return bao_gia.dong_y(bg.name)


@frappe.whitelist()
def portal_bao_gia_tu_choi(ten, ly_do=None) -> dict:
    bg = _bao_gia_cua_toi(ten)
    return bao_gia.tu_choi(bg.name, ly_do)


@frappe.whitelist()
def portal_bao_gia_huy_con_lai(ten, ly_do=None) -> dict:
    """Spec 2026-10-15 §4.4 — huỷ các mặt hàng chưa báo của phiếu gốc. Mọi tài
    khoản trong phạm vi bấm được, như đồng ý; lý do tuỳ chọn."""
    from miyano_portal import bao_gia_theo_dot

    if ly_do is not None and not isinstance(ly_do, str):
        frappe.throw("Lý do không hợp lệ.", frappe.ValidationError)
    bg = _bao_gia_cua_toi(ten)
    return bao_gia_theo_dot.huy_con_lai_boi_khach(bg.name, ly_do)


@frappe.whitelist()
def portal_bao_gia_sua_so_luong(ten, dong) -> dict:
    """Chỉ quản lý. Nhân viên khoa không có đường "xin sửa" cho báo giá trong
    đợt này (kế hoạch 2026-10-13, mục quyết định để ngỏ)."""
    bg = _bao_gia_cua_toi(ten)
    if not la_quan_ly():
        raise frappe.PermissionError(
            "Chỉ quản lý của quý đơn vị sửa được số lượng trên báo giá."
        )
    kq = bao_gia.sua_so_luong(bg.name, dong)
    if bg.get("custom_de_xuat") and kq["ap_dung"]:
        _dong_bo_so_luong_duyet_ve_phieu(bg.custom_de_xuat, kq["ap_dung"])
    return {"trang_thai_moi": kq["trang_thai_moi"], "thay_doi": kq["thay_doi"]}


def _bao_gia_pdf_quotation(ten) -> None:
    from miyano_portal.setup.install_print_formats import NAME_YCBG

    bg = _bao_gia_cua_toi(ten)
    # Chỉ từ lúc báo giá ĐÃ GỬI cho khách: trước đó giá chưa phải báo giá.
    if bg.get("workflow_state") not in _BAO_GIA_HIEN_GIA:
        frappe.throw(
            "Báo giá này chưa được gửi. Vui lòng đợi Miyano báo giá.", frappe.ValidationError
        )
    if not frappe.db.exists("Print Format", NAME_YCBG):
        frappe.throw(
            "Mẫu in báo giá chưa sẵn sàng. Vui lòng liên hệ quản trị viên hệ thống.",
            frappe.ValidationError,
        )
    # Tài khoản cổng không có DocPerm trên Quotation, và hook
    # `bao_gia_khong_qua_trang_web` (Task 3) đóng luôn đường lui trang web mà
    # `frappe.get_print` rơi về. Quyền của khách đã được `_bao_gia_cua_toi`
    # kiểm ở trên; chỉ riêng việc dựng PDF chạy dưới quyền hệ thống.
    with quyen_he_thong():
        pdf = frappe.get_print("Quotation", bg.name, print_format=NAME_YCBG, as_pdf=True)
    frappe.local.response.filename = f"BaoGia-{bg.name}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"


def _dem_don_theo_trang_thai(trang_thai: str) -> int:
    filters, or_filters = _dieu_kien_loc_trang_thai_don(trang_thai)
    filters = filters + _pham_vi_filters()
    return frappe.get_list(
        "Sales Order", filters=filters, or_filters=or_filters,
        fields=["count(name) as n"],
    )[0].n


@frappe.whitelist()
def portal_dashboard_kpi() -> dict:
    """Brief 2026-08-16 (vá hồi quy phân trang) — Dashboard.vue trước đây
    suy 3 ô KPI (đơn chờ xác nhận/đang giao, hoá đơn chưa thanh toán) từ
    DANH SÁCH ĐÃ PHÂN TRANG (`portal_order_history`/`portal_invoices`, limit
    mặc định 10/20). Với `limit=10`, một khách có 15 đơn "Chờ xác nhận" thật
    chỉ thấy ô hiện một con số nhỏ hơn — SAI trên đúng màn đầu tiên khách
    nhìn thấy mỗi lần đăng nhập, hỏng niềm tin vào toàn bộ số liệu của cổng.

    Ba con số ở đây LUÔN đếm trên TOÀN BỘ dữ liệu của khách (không limit/
    start), độc lập với cỡ trang khách đang chọn ở Orders.vue/Invoices.vue.
    "Tổng công nợ" KHÔNG có ở đây — `portal_me().outstanding` đã là một truy
    vấn tổng hợp riêng từ trước, không suy từ danh sách phân trang, nên
    không phải hồi quy của đợt này.

    Đếm qua `frappe.get_list` (không phải `get_all`/`db.count`) — Sales
    Order/Sales Invoice được scoping theo khách hàng qua
    `permission_query_conditions` (hooks.py); `get_all`/`db.count` bỏ qua
    tầng đó và sẽ đếm lẫn dữ liệu khách khác.
    """
    return {
        "don_cho_xac_nhan": _dem_don_theo_trang_thai("Chờ xác nhận"),
        "don_dang_giao": _dem_don_theo_trang_thai("Đang giao"),
        "hoa_don_chua_thanh_toan": frappe.get_list(
            "Sales Invoice",
            filters=[["outstanding_amount", ">", 0]]
            + _loc_qua_don_cha("Sales Invoice Item", "sales_order"),
            fields=["count(distinct `tabSales Invoice`.name) as n"],
        )[0].n,
        # Spec 2026-10-12 §6.4 — thẻ "Báo giá chờ đồng ý" trỏ sang tab báo
        # giá nên chỉ đếm Quotation.
        "bao_gia_cho_dong_y": portal_bao_gia_dem()["cho_dong_y"],
    }


def _kiem_hang_tom_tat(r) -> dict | None:
    """Tóm tắt biên bản kiểm hàng cho một đợt giao, hoặc None nếu khách chưa
    lập. Client dùng để chọn giữa nút "Kiểm hàng" và một badge trạng thái."""
    if not r:
        return None
    return {
        "name": r.name,
        "trang_thai": r.trang_thai,
        "co_hang_hong": bool(r.co_hang_hong),
        "da_gui": int(r.docstatus) == 1,
    }


def _co_dong_cho_bao_gia(so) -> bool:
    """Đơn này còn dòng nào CHƯA CÓ GIÁ không?

    Nuôi huy hiệu "Có hàng chờ báo giá" trên màn chi tiết đơn (chủ đầu tư
    yêu cầu thêm lại 05/09/2026, sau khi nó rơi mất lúc gộp hai màn chi
    tiết).

    KHÁC `portal_mua_le.di_vong_bao_gia()` — và khác CỐ Ý, đừng gộp hai hàm:

      * `di_vong_bao_gia()` đọc DẤU `custom_loai_don`, tức ghi lại ĐƯỜNG đơn
        đã đi. Nó phải ổn định suốt vòng đời đơn, vì chốt giá khách đã đồng
        ý (`chot_bao_gia.kiem_gia_khop_gia_da_dong_y`) dựa vào nó.
      * Hàm NÀY đọc TÌNH TRẠNG GIÁ LÚC NÀY, và nó ĐƯỢC PHÉP lật — vì nó chỉ
        nuôi một cái nhãn, không nuôi chốt nào.

    Bản cũ trên `OrderDetail.vue` của `main` bật huy hiệu theo
    `loai_don === "Mua lẻ"`, nên vẫn hiện "Có hàng chờ báo giá" SAU KHI
    Miyano đã điền đủ giá — một cái nhãn nói sai về chính đơn nó gắn vào.
    Trớ trêu là commit đưa nó lên `main` tên là *"nhãn thôi nói dối 'Mua
    lẻ'"*: nó đổi chữ trên nhãn nhưng giữ nguyên vị ngữ, nên chỉ đổi lời nói
    dối chứ chưa hết dối.

    "Chưa có giá" = dòng hàng thật còn `rate == 0` — Miyano chưa điền giá.
    Đơn không còn bảng dòng gõ tay (patch v1_44), nên chỉ còn vế này.

    `ITEM_GIU_CHO` bị loại: đó là dòng giữ chỗ kỹ thuật của đơn cũ, luôn giá
    0 và không bao giờ là hàng thật — tính nó vào là huy hiệu sáng vĩnh viễn.
    """
    return any(
        i.get("item_code") != ITEM_GIU_CHO and not float(i.get("rate") or 0)
        for i in so.get("items") or []
    )


def _hoa_don_cua_don(order: str, customer: str) -> list:
    """Hoá đơn phát sinh từ CHÍNH đơn hàng này.

    Khoảng trống đã nêu trong đối chiếu 2026-08-16: cổng có mốc "Hoá đơn"
    bật/tắt và một trang Hoá đơn TOÀN CỤC, nhưng không có đường nào từ một
    đơn tới hoá đơn của nó — khách phải tự dò. Nối qua `Sales Invoice Item.
    sales_order`, đúng cách ERPNext ghi liên kết đó.

    `docstatus < 2` — hoá đơn đã huỷ không còn là hoá đơn của đơn này.
    KHÔNG đụng `portal_invoices` (hình dạng trả về của nó là hợp đồng API đã
    có người dùng).
    """
    ten = frappe.get_all(
        "Sales Invoice Item",
        filters={"sales_order": order, "docstatus": ["<", 2]},
        pluck="parent",
    )
    ten = list(dict.fromkeys(ten))
    if not ten:
        return []
    rows = frappe.get_all(
        "Sales Invoice",
        filters={"name": ["in", ten], "docstatus": ["<", 2]},
        fields=["name", "posting_date", "due_date", "status",
                "grand_total", "outstanding_amount"],
        order_by="posting_date asc",
    )
    # BA KHOÁ HĐĐT (chủ đầu tư chốt 05/09/2026) — trước bản này khối "Hoá
    # đơn của đơn này" trên màn chi tiết tải BẢN IN CỦA ERP
    # (`portal_document_download`), trong khi trang "Hoá đơn & công nợ" tải
    # BẢN THỂ HIỆN HOÁ ĐƠN ĐIỆN TỬ của Fast. Hai màn cùng một nút "PDF" giao
    # hai tờ giấy khác nhau cho cùng một hoá đơn, và tờ ở đây không phải
    # chứng từ thuế.
    #
    # KHÔNG viết lại logic HĐĐT ở đây: gọi đúng `einvoice.block_for()` mà
    # `portal_invoices` đang gọi. Một chốt "tải được hay chưa" thứ hai là hai
    # nơi lệch nhau, và nơi lệch sẽ hoặc giấu mất hoá đơn thật, hoặc hiện một
    # nút bấm vào là lỗi.
    #
    # Chỉ lấy BA khoá, không bê nguyên khối: hình dạng đầy đủ của `block_for`
    # là hợp đồng API của `portal_invoices` (bản chính + mọi bản điều chỉnh/
    # thay thế + cảnh báo pháp lý), và màn chi tiết đơn KHÔNG dựng lại giao
    # diện đó — nó chỉ cần biết "tải được chưa", "đang ở trạng thái gì" và
    # "số hoá đơn nào", rồi trỏ khách sang trang Hoá đơn để xem đủ.
    #
    # Bọc try/except cùng lý do (và cùng khuôn) với `dn_co_hoa_don_nhap` ở
    # `portal_order_track`: module HĐĐT là của team khác — nó hỏng thì mất
    # BA KHOÁ, không được mất cả trang chi tiết đơn hàng. Bọc NGOÀI vòng lặp
    # nên một lần hỏng ghi đúng MỘT log, không N log.
    khoi_hddt = {}
    try:
        for r in rows:
            khoi_hddt[r.name] = einvoice.block_for(r.name, customer)["chinh"]
    except Exception:
        frappe.log_error(title=f"HĐĐT: không đọc được khối hoá đơn cho đơn {order}")
        khoi_hddt = {}

    def _hddt(ten: str) -> dict:
        chinh = khoi_hddt.get(ten) or {}
        return {
            # `tai_duoc` là cờ boolean của chính adapter — KHÔNG BAO GIỜ đưa
            # đường dẫn file ra SPA (BR-E4, xem docstring `block_for`).
            "hddt_tai_duoc": bool(chinh.get("tai_duoc")),
            # Nhãn để hiện THAY CHO nút khi chưa tải được: "hide, don't
            # disable" — một nút chắc chắn báo lỗi lúc bấm dạy người dùng sợ
            # thanh công cụ. Rỗng khi module HĐĐT hỏng; giao diện tự lùi về
            # câu mặc định của nó.
            "hddt_nhan": chinh.get("nhan") or "",
            "hddt_so": chinh.get("so") or "",
        }

    return [
        {
            "name": r.name,
            "ngay": r.posting_date,
            "han_thanh_toan": r.due_date,
            "trang_thai": r.status,
            "tong_tien": float(r.grand_total or 0),
            "con_no": float(r.outstanding_amount or 0),
            **_hddt(r.name),
        }
        for r in rows
    ]


def _dat_ngoai_cho_khach(d) -> dict:
    """MỘT dòng "hàng chưa có mã" như cổng được thấy. Danh sách khoá tường
    minh: dòng đến từ báo giá nguồn của đơn, và không trường nào khác của
    chứng từ đó đi theo."""
    return {
        "name": d.name, "ten_hang": d.ten_hang, "dvt": d.dvt,
        "so_luong": float(d.so_luong or 0),
        "ghi_chu": d.ghi_chu or "", "da_xu_ly": bool(d.da_xu_ly),
        "item_khop": d.item_khop or "",
        "model_ma": d.model_ma or "", "hang_san_xuat": d.hang_san_xuat or "",
        "nuoc_san_xuat": d.nuoc_san_xuat or "", "quy_cach": d.quy_cach or "",
        "ncc_hien_tai": d.ncc_hien_tai or "",
        "gia_hien_tai": float(d.gia_hien_tai or 0),
        "anh": d.anh or "", "khong_co_anh": bool(d.khong_co_anh),
        "mo_ta_nhan_dang": d.mo_ta_nhan_dang or "",
    }


@frappe.whitelist()
def portal_order_track(order) -> dict:
    # Bước 8 — chặn theo KHOA trước tiên: `dam_bao_xem_duoc` tự no-op cho
    # Quản lý (pham_vi_don() == {}) và ném CÙNG một thông báo cho "đơn không
    # có thật" lẫn "đơn của khoa khác" (không có gì để `frappe.get_doc`
    # đụng vào rồi mới ném DoesNotExistError với văn xuôi khác).
    dam_bao_xem_duoc("Sales Order", order)
    so = frappe.get_doc("Sales Order", order)
    # frappe.get_doc does not auto-check permissions on load; check_permission()
    # is what actually invokes the has_permission hook (Task 5) that scopes
    # this to the caller's own customer — kiểm KHÁCH HÀNG, KHÔNG thay cho
    # kiểm khoa phòng ở trên.
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
    #
    # `docstatus = 1` và `is_return = 0` — hai vế BẮT BUỘC, và bản trước
    # thiếu CẢ HAI (lỗi đo được 18/08/2026, xem
    # `docs/superpowers/specs/2026-08-17-himedic-5-yeu-cau-design.md` §2b):
    #
    #   * `docstatus < 2` cho phiếu NHÁP đi qua → khách thấy một phiếu chưa
    #     ghi sổ như một đợt ĐÃ giao (đo thật: MAT-DN-2026-00022 còn nháp vẫn
    #     hiện thành "Đợt 2" trên màn Bạch Mai).
    #   * `make_return_doc` chép nguyên `against_sales_order` sang phiếu TRẢ
    #     HÀNG, và dòng hàng của nó mang `qty` ÂM → phiếu trả hiện thành một
    #     đợt giao với phần trăm âm (đo thật: "Đợt 4: -10.0%").
    #
    # Đây là CÙNG quy ước `portal_hen_giao._da_giao_sau()` đã dùng từ trước,
    # không phải một luật mới. Cờ `is_return` nằm trên chứng từ CHA nên phải
    # nối bảng — không có lối lọc nào bằng `frappe.get_all` trên riêng bảng
    # con, đúng lý do `_da_giao_sau` cũng viết SQL tay.
    total_qty = sum(float(i.qty or 0) for i in so.items) or 0
    dn_names = [
        r[0]
        for r in frappe.db.sql(
            """select dni.parent
               from `tabDelivery Note Item` dni
               inner join `tabDelivery Note` dn on dn.name = dni.parent
               where dni.against_sales_order = %s
                 and dn.docstatus = 1
                 and ifnull(dn.is_return, 0) = 0
               group by dni.parent
               order by min(dni.creation) asc""",
            (so.name,),
        )
    ]

    # E7b — cờ "đợt giao này đã có hoá đơn nháp", MỘT truy vấn cho cả danh
    # sách (không hỏi từng phiếu trong vòng lặp bên dưới). Chỉ là CỜ; nội
    # dung đầy đủ lấy qua `portal_einvoice_nhap` khi khách bấm xem — nhét sẵn
    # dòng hàng của mọi đợt giao vào đây sẽ phình response chi tiết đơn.
    #
    # Bọc lỗi CỐ Ý, cùng nguyên tắc với khối HĐĐT ở `portal_invoices` và
    # `delivery_hook._chay_an_toan`: module HĐĐT là của team khác — nó hỏng
    # thì mất CÁI CỜ, không được mất cả trang chi tiết đơn hàng. Bọc ở đây
    # (ngoài vòng lặp) nên một lần hỏng ghi đúng MỘT log, không N log.
    try:
        dn_co_nhap = einvoice.dn_co_hoa_don_nhap(dn_names, so.customer)
    except Exception:
        frappe.log_error(title=f"HĐĐT: không kiểm được hoá đơn nháp cho đơn {so.name}")
        dn_co_nhap = set()

    # US-E3.4 — trạng thái phiếu nhập chỉ hiện khi khách CÓ kho (không dùng
    # get_portal_kho(): hàm đó ném PermissionError khi khách chưa mở kho, mà
    # phần lớn khách hàng portal KHÔNG có kho — đây không phải một tình huống
    # ngoại lệ cho endpoint này). `active: 1` khớp đúng định nghĩa "có kho"
    # mà get_portal_kho()/delivery_hook._kho_cua_khach() đã dùng ở mọi nơi
    # khác trong app — một kho đã tắt được coi như "không có kho" ở đây,
    # nhất quán với việc hook cũng ngừng tự sinh phiếu cho kho đó.
    kho = frappe.db.get_value("Customer Warehouse", {"customer": so.customer, "active": 1}, "name")
    # Biên bản kiểm hàng — MỘT truy vấn cho cả danh sách (không hỏi từng
    # phiếu trong vòng lặp bên dưới), cùng khuôn `dn_co_nhap`. KHÔNG phụ
    # thuộc `kho`: biên bản chạy cho mọi khách, kể cả khách chưa mở kho.
    bien_ban_by_dn = {}
    if dn_names:
        for r in frappe.get_all(
            "Portal Delivery Inspection",
            filters={"delivery_note": ["in", dn_names], "docstatus": ["<", 2]},
            fields=["name", "delivery_note", "docstatus", "trang_thai", "co_hang_hong"],
        ):
            bien_ban_by_dn[r.delivery_note] = r

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
            ["name", "status", "lr_no", "transporter_name", *COT_THOI_GIAN_GIAO],
            as_dict=True,
        )
        if not dn:
            continue
        # Thời điểm giao THẬT do Miyano nhập trên phiếu; phiếu cũ chưa có thì
        # lùi về ngày giờ ghi sổ (xem `portal_thoi_gian_giao`). `posting_date`
        # vẫn trả riêng bên dưới — đó là ngày ghi sổ, một sự thật khác.
        thoi_gian_giao = thoi_gian_giao_cua_dn(dn)
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
            "thoi_gian_giao": thoi_gian_giao,
            "status": dn.get("status"),
            "percent": pct,
            "carrier": dn.get("transporter_name") or "",
            "awb": dn.get("lr_no") or "",
            "co_hoa_don_nhap": dn_name in dn_co_nhap,
            "kiem_hang": _kiem_hang_tom_tat(bien_ban_by_dn.get(dn_name)),
        }
        if receipt:
            row["so_dot"] = so_dot
            row["phieu_nhap"] = phieu_nhap
        deliveries.append(row)

        dot = {
            "so_dot": so_dot,
            "delivery_note": dn["name"],
            "ngay": dn.get("posting_date"),
            "thoi_gian_giao": thoi_gian_giao,
            "phan_tram": pct,
            "van_chuyen": dn.get("transporter_name") or "",
            "awb": dn.get("lr_no") or "",
            "co_hoa_don_nhap": dn_name in dn_co_nhap,
            "kiem_hang": _kiem_hang_tom_tat(bien_ban_by_dn.get(dn_name)),
        }
        if phieu_nhap:
            dot["phieu_nhap"] = phieu_nhap
        dot_giao.append(dot)

    # `_so_status_vi_full` — dùng CHUNG với `portal_order_history`, không
    # viết tay điều kiện này hai lần.
    status_vi = _so_status_vi_full(so.status, so.per_delivered, so.get("workflow_state"))

    # Review Task 7a — `giai_doan` phải là ĐÚNG `_sql_giai_doan()`, KHÔNG
    # một bản suy lại ở client (`ChiTietYeuCau.vue` từng có một bản như vậy,
    # thiếu các nhánh 'Miyano đã từ chối', 'Closed' — các
    # nhãn SAI trạng thái trên cùng một tài liệu đứng cạnh danh sách đọc
    # đúng). MỘT định nghĩa, dùng lại chính biểu thức lọc/đếm/hiển thị của
    # danh sách — `tt` truyền `null` vì hàm này KHÔNG có phiếu đứng trước để
    # hỏi (đường vào là chính Sales Order, xem `_sql_giai_doan()` docstring
    # về nhánh "đơn-không-qua-đề-xuất").
    giai_doan = frappe.db.sql(
        f"select {_sql_giai_doan('null', 'so')} from `tabSales Order` so where so.name = %s",
        so.name,
    )[0][0]

    return {
        "order": so.name,
        "status_vi": status_vi,
        "giai_doan": giai_doan,
        # Ruling P49 — `docstatus` để màn chi tiết TẮT nhãn "Có hàng chờ báo
        # giá" khi đơn đã được xác nhận. Trên một đơn đã giao xong, nhãn đó
        # không phải một phân loại sai — nó là một lời nói SAI VỀ HIỆN TẠI:
        # vòng báo giá diễn ra lúc đơn còn nháp (`docstatus == 0`), nên
        # `docstatus == 1` là đúng lằn ranh. `custom_loai_don` KHÔNG được tự
        # tắt theo (nó là DẤU ghi lại đường đơn đã đi, xem `di_vong_bao_gia`)
        # — cái tắt là NHÃN, không phải dấu.
        "docstatus": so.docstatus,
        "order_date": so.transaction_date,
        "po_khach": so.get("custom_so_po_khach") or "",
        "hdnt": so.get("custom_hdnt") or "",
        # US-E2.2 — khách phải đọc được lý do ngay trên chi tiết đơn, không
        # phải đi tìm lại email.
        "ly_do_tu_choi": so.get("custom_ly_do_tu_choi") or "",
        # Task 6, QĐ-A4 — cùng khoá `ma_tra_cuu` với `portal_order_history`,
        # xem chú thích ở đó. Đơn cũ không có phiếu đề xuất đứng sau: rỗng.
        "ma_tra_cuu": so.get("custom_ma_tra_cuu") or "",
        # Nhánh vào màn chi tiết bằng đường ĐƠN (~102 đơn cũ, và mọi link
        # trong thông báo giao hàng/hoá đơn) không nạp được nửa phiếu khi
        # phiếu không tồn tại — tên phải đọc được từ chính đơn.
        "ten_don_hang": so.get("custom_ten_don_hang") or "",
        # HSD tối thiểu khách ĐÃ YÊU CẦU (tháng, 0 = không yêu cầu). CHỈ số
        # này: kết quả đánh giá/ngoại lệ (`custom_ket_qua_hsd`,
        # `custom_hsd_ton_tot_nhat`, `custom_ngoai_le_*`) là nội bộ Miyano.
        "hsd_toi_thieu_thang": frappe.utils.cint(so.get("custom_hsd_toi_thieu_thang")),
        # 03/09/2026 (màn chi tiết GỘP) — phiếu đề xuất đứng sau đơn này.
        # Vào màn bằng đường `/yeu-cau/don/<name>` (link trong mọi thông báo
        # đã gửi đi, xem `_lien_ket_thong_bao`) thì đây là đường DUY NHẤT tìm
        # ngược ra phiếu: `Sales Order.name` và `Portal De Xuat Mua.name`
        # là hai naming khác nhau, không suy ra nhau được.
        #
        # `""` (không phải thiếu khoá) cho ~102 đơn cũ có TRƯỚC luồng duyệt:
        # màn gộp đọc khoá này để quyết định có nạp nửa phiếu hay không, và
        # một khoá vắng mặt buộc client phải đoán.
        "de_xuat": so.get("custom_de_xuat") or "",
        # Ruling P42 — giai đoạn "Đã giao" đòi `>= 100`, KHÔNG phải `> 0`.
        # Payload đã có `milestones[delivering].done` nhưng cờ đó là `> 0`
        # (giao một thùng cũng bật), nên nó KHÔNG thay được con số này. Màn
        # gộp đọc `per_delivered` để suy giai đoạn — cùng luật với
        # `_sql_giai_doan()` mà danh sách đang dùng, không phải một luật
        # thứ hai viết riêng cho màn chi tiết.
        "per_delivered": float(so.per_delivered or 0),
        # review (Phần C báo thiếu)
        "loai_don": so.get("custom_loai_don") or "Theo HĐNT",
        "workflow_state": so.get("workflow_state") or "",
        "yeu_cau_goc": so.get("custom_yeu_cau_goc") or "",
        "milestones": milestones,
        # §3.4 — LỌC dòng giữ chỗ khỏi phía khách. Khách không gõ ra nó,
        # không đặt nó, và nó không phải hàng: để nó lọt ra cổng là phơi một
        # chi tiết kỹ thuật nội bộ ra đúng chỗ nguyên tắc nền cấm.
        "items": [
            # `name` — để client tham chiếu dòng nếu cần.
            {"name": i.name, "item_code": i.item_code,
             "item_name": i.item_name or frappe.db.get_value("Item", i.item_code, "item_name"),
             "qty": i.qty, "delivered_qty": i.delivered_qty,
             "rate": float(i.rate or 0), "uom": i.uom, "amount": float(i.amount or 0),
             # Dấu "Bảng giá" / "Báo giá" của dòng (spec 2026-10-09 §4.2) —
             # `None` với dòng cũ chưa có dấu. Bảng mặt hàng in "Chờ báo
             # giá" cho dòng "Báo giá" chưa có giá thay vì "0 ₫".
             "nguon_gia": i.get("custom_nguon_gia") or None,
             "hsd_toi_thieu_thang": frappe.utils.cint(i.get("custom_hsd_toi_thieu_thang")),
             # Thời gian giao hàng (09/10/2026) — `None` khi đơn CHƯA được
             # Miyano xác nhận: trước mốc đó `delivery_date` là "ngày cần"
             # do chính khách gõ lúc đặt, in nó ra dưới chữ "Dự kiến giao"
             # là để Miyano cam kết một ngày mình chưa hề xem.
             "ngay_giao_du_kien": i.delivery_date if so.docstatus == 1 else None}
            for i in so.items
            if i.item_code != ITEM_GIU_CHO
        ],
        # Hàng khách mô tả bằng tên (chưa có mã). Đơn không mang dòng gõ tay
        # (patch v1_44; `custom_dat_ngoai` của Quotation là `no_copy`): mặt
        # hàng vốn là dòng khách gõ tay chỉ còn dấu vết trên báo giá nguồn.
        # Trả các dòng ĐÃ KHỚP của báo giá đó — không thì bảng mặt hàng không
        # nói được mã nào ứng với thứ khách đã mô tả. Đọc SAU hai chốt quyền
        # ở đầu hàm; `bao_gia_cua_don` đòi báo giá cùng khách với đơn.
        #
        # CHÍN TRƯỜNG CR-03 đi theo (`_dat_ngoai_cho_khach`). `anh` giữ
        # nguyên dạng chuỗi JSON như đã lưu — client tự tách. KHÔNG trả đường
        # dẫn tệp nào khác: ảnh riêng tư chỉ đi qua `portal_dat_ngoai_xem_anh`,
        # kiểm sở hữu từng lần xem.
        "dat_ngoai": [
            _dat_ngoai_cho_khach(d) for d in bao_gia.dong_go_tay_da_khop_cua_don(so)
        ],
        "deliveries": deliveries,
        # `30_API_Spec` §1.2 — cùng dữ liệu với `deliveries`, đúng tên field
        # đặc tả yêu cầu (xem ghi chú ngay phía trên vòng lặp).
        "dot_giao": dot_giao,
        # CR-04 — căn cứ tồn kho cho từng dòng hàng, để quản lý duyệt bằng
        # con số chứ không bằng kinh nghiệm. Phép tính sống ở `kho/
        # can_cu_duyet.py` (đó là việc của kho, và file này đã quá dài); ở
        # đây chỉ gắn kết quả vào đúng dòng.
        #
        # Item KHÔNG có mặt trong dict = không tra được (khách chưa mở kho,
        # vật tư chưa nối `item_code`, hàng không có trong danh mục kho).
        # Client hiện GẠCH NGANG, không hiện 0 — "tồn 0" nghĩa là hết hàng,
        # "không biết" là chuyện khác hẳn.
        "can_cu_kho": can_cu_duyet.can_cu_cho_don(so),
        # Huy hiệu "Có hàng chờ báo giá" — SERVER trả lời, client chỉ đọc.
        # Ruling #19: một bản sao logic ở client đã từng lệch khỏi server và
        # làm đơn BỊ TỪ CHỐI hiện badge xanh "Đã duyệt". Không dựng bản sao
        # thứ hai của phép suy này ở tầng giao diện.
        "co_dong_cho_bao_gia": _co_dong_cho_bao_gia(so),
        "hoa_don": _hoa_don_cua_don(so.name, so.customer),
        # Miyano hẹn lại lịch giao (2026-08-16, vai nhân viên). `None` khi
        # chưa có lời hẹn nào — client ẩn hẳn khối, không hiện một khung rỗng.
        "hen_giao": hen_giao_cua_don(so),
    }


def _ten_don_trong_pham_vi() -> list | None:
    """`None` = không giới hạn theo khoa (Quản lý). Ngược lại: danh sách tên
    `Sales Order` thuộc ĐÚNG khoa của người gọi (có thể rỗng).

    VÒNG SỬA 3 (V2, review độc lập, Important) — `frappe.get_all` bên dưới
    tham chiếu THẲNG `custom_khoa_phong`, cùng lưới an toàn với
    `dam_bao_xem_duoc` (`portal_context.py`, dùng CHUNG `_cot_khoa_phong_
    ton_tai()`, không viết lại phép kiểm cột thứ hai): Quản lý (`pham_vi`
    rỗng) không bao giờ chạm cột này — chỉ Nhân viên khoa mới cần. Thiếu
    cột thì trả `[]` (KHÔNG phải `None`) — `_loc_qua_don_cha` bên dưới coi
    `None` là "không giới hạn" (Quản lý) và một danh sách rỗng là "giới hạn
    nhưng không khớp gì" (sentinel `__khong_don_nao__`); trả nhầm `None` ở
    đây sẽ MỞ TOANG danh sách cho đúng người lẽ ra phải bị chặn."""
    pham_vi = pham_vi_don()
    if not pham_vi:
        return None
    if not _cot_khoa_phong_ton_tai():
        return []
    return frappe.get_all(
        "Sales Order", filters={"custom_khoa_phong": pham_vi["custom_khoa_phong"]},
        pluck="name",
    )


def _loc_qua_don_cha(child_doctype: str, link_field: str) -> list:
    """Filter kiểu LIST cho `frappe.get_list` trên một doctype DẪN XUẤT
    (Delivery Note/Sales Invoice) — lọc QUA ĐƠN CHA bằng cách nối bảng dòng
    (`child_doctype`), KHÔNG có field khoa phòng riêng trên chính doctype đó
    (một nguồn sự thật, xem docstring `dam_bao_xem_duoc`). `[]` (không lọc
    gì thêm) cho Quản lý; một sentinel không khớp bản ghi nào khi khoa CHƯA
    có đơn nào (danh sách `_ten_don_trong_pham_vi()` rỗng — `["in", []]`
    không đáng tin cậy trên mọi bản Frappe nên tự đóng bằng một giá trị
    không bao giờ khớp thay vì phó mặc).

    SỬA (review vòng sửa 2, C4) — mô tả trước đây ở đây SAI, và sai đúng chỗ
    nguy hiểm nhất (vị trí ranh giới an ninh thật). Bản Vòng sửa 1 bảo bộ
    lọc NÀY khoan dung hơn `_dieu_kien_khoa_qua_don_cha` (permissions.py,
    C2 — chỉ đòi "CÓ ÍT NHẤT MỘT dòng khớp khoa", không đòi "KHÔNG dòng nào
    khác khoa"), nên một Delivery Note/Sales Invoice trộn hai khoa "có thể
    XUẤT HIỆN trên danh sách rồi 403 khi mở". Điều đó ĐÚNG cho riêng hàm
    NÀY, nhưng SAI cho kết quả THẬT khách nhận được: `portal_deliveries`/
    `portal_invoices` (hai nơi DUY NHẤT gọi hàm này) gọi `frappe.get_list`
    KHÔNG `ignore_permissions=True` — nên `permission_query_conditions`
    (`delivery_query`/`invoice_query`, đã có vế khoa CHẶT từ C2) tự động
    ANDED vào CHÍNH truy vấn đó bởi framework, không phải một bước lọc
    riêng sau này. Kết quả cuối là GIAO của bộ lọc lỏng ở đây và bộ lọc
    chặt của hook — tức CHẶT (hook thắng). Danh sách khách thấy đã ĐÚNG
    NGAY từ đầu, không có khoảng hở "hiện ra rồi 403" trong thực tế.

    Bộ lọc lỏng ở ĐÂY vẫn hữu ích (thu hẹp SQL sớm, đỡ join thừa khi hook
    còn phải chạy lại chính phép join tương tự) nhưng KHÔNG PHẢI ranh giới
    an ninh — ranh giới an ninh THẬT là hook (`permissions.py`), luôn luôn.
    Ràng buộc ngầm PHẢI giữ: hai hàm gọi filter này TUYỆT ĐỐI không được
    thêm `ignore_permissions=True` — làm vậy sẽ tắt hẳn hook và biến bộ lọc
    lỏng ở đây thành tuyến phòng thủ DUY NHẤT, đúng lúc đó mô tả "khoan
    dung hơn, có thể lộ tên chứng từ" ở trên mới thành sự thật. `test_
    portal_deliveries_khop_chinh_xac_voi_frappe_get_list_qua_hook`/`test_
    portal_invoices_...` (`tests/test_cach_ly_khoa_phong.py`, C6) ghim
    đúng bất biến "kết quả endpoint == kết quả frappe.get_list thô qua
    hook" — đỏ ngay nếu ai đó phá ràng buộc này."""
    so_names = _ten_don_trong_pham_vi()
    if so_names is None:
        return []
    return [[child_doctype, link_field, "in", so_names or ["__khong_don_nao__"]]]


@frappe.whitelist()
def portal_deliveries(limit=20, start=0) -> list:
    filters = _loc_qua_don_cha("Delivery Note Item", "against_sales_order")
    return frappe.get_list(
        "Delivery Note",
        filters=filters,
        # `distinct` — một phiếu giao có THỂ có nhiều dòng cùng trỏ về một
        # đơn (nhiều mặt hàng); không có nó, phép nối bảng dòng ở trên nhân
        # bản CHÍNH phiếu giao đó trên danh sách, hỏng cả số lượng lẫn phân
        # trang một cách im lặng.
        distinct=True,
        fields=["name", "posting_date", "status"],
        order_by="posting_date desc",
        limit_page_length=int(limit), limit_start=int(start),
    )


@frappe.whitelist()
def portal_invoices(limit=20, start=0, ten=None) -> dict:
    """Brief 2026-08-15 (phân trang) — hình dạng trả về ĐỔI từ list sang
    `{"rows": [...], "tong": N, "qua_han_thanh_toan": ..., "sap_den_han_
    so_luong": ...}`, LUÔN LUÔN (endpoint này không nuôi dropdown nào). Đã
    cập nhật MỌI caller (Dashboard.vue, Invoices.vue, test_portal_read.py,
    test_e7_hddt.py) sang đọc `.rows`.

    `qua_han_thanh_toan`/`sap_den_han_so_luong` (bản trước Invoices.vue tự
    tính từ TOÀN BỘ `invoices.value` client-side) giờ tính Ở SERVER trên
    TOÀN BỘ hoá đơn còn nợ của khách — không phải chỉ trang đang xem, nếu
    không hai con số này sẽ đổi theo trang khách đang lật, một hồi quy im
    lặng đúng kiểu brief cảnh báo. Cùng công thức `daysUntil()`
    (frontend/src/format.js): quá hạn = hạn TT đã qua hôm nay; sắp đến hạn
    = còn 0-7 ngày VÀ còn nợ.

    `ten` (chủ đầu tư chốt 05/09/2026) — LỌC danh sách về ĐÚNG MỘT hoá đơn.
    Thêm vào để số hoá đơn trên màn chi tiết đơn bấm được: không có nó, liên
    kết chỉ mở đúng dòng khi hoá đơn tình cờ nằm ở TRANG ĐANG XEM, còn một
    hoá đơn cũ của bệnh viện nhiều năm giao dịch thì bấm vào không thấy gì —
    một liên kết chạy lúc được lúc không còn tệ hơn không có liên kết.

    THÊM VÀO, không đổi hợp đồng: bỏ trống thì hành vi giữ nguyên từng dấu
    phẩy, và hình dạng trả về không đổi ở cả hai nhánh.

    `ten` KHÔNG phải chốt an ninh và không được coi là chốt: nó chỉ CỘNG
    THÊM vào `pham_vi_hd` — bộ lọc phạm vi (khách hàng + khoa phòng) vẫn
    chạy nguyên vẹn, nên gõ tên hoá đơn của bệnh viện khác vẫn trả rỗng.

    Hai con số KPI (`qua_han_thanh_toan`/`sap_den_han_so_luong`) CỐ Ý KHÔNG
    lọc theo `ten`: chúng nói về TỔNG CÔNG NỢ của đơn vị, không phải về dòng
    đang xem. Lọc chúng theo một hoá đơn là biến thẻ "công nợ quá hạn" thành
    một con số khác hẳn tuỳ khách vừa bấm vào đâu — đúng dạng hồi quy im
    lặng mà đoạn trên đang cảnh báo. `tong` thì CÓ lọc, vì nó là tổng số
    dòng của chính danh sách này (phân trang đọc nó).
    """
    loc_ten = [["name", "=", ten]] if ten else []
    # Bước 8 — CẢ BA truy vấn dưới đây phải cùng một bộ lọc khoa phòng: đây
    # là đúng bẫy "hồi quy im lặng" mà docstring hàm này đang cảnh báo (phân
    # trang) áp cho một trục khác — lọc mỗi `rows` mà bỏ sót `tong`/
    # `qua_han_thanh_toan`/`sap_den_han_so_luong` thì nhân viên khoa vẫn đọc
    # được TỔNG CÔNG NỢ TOÀN BỆNH VIỆN ngay trên khối KPI, dữ liệu vẫn rò dù
    # danh sách chi tiết đã lọc đúng.
    pham_vi_hd = _loc_qua_don_cha("Sales Invoice Item", "sales_order")

    tong = frappe.get_list(
        "Sales Invoice", filters=loc_ten + pham_vi_hd,
        # `count(distinct name)`, KHÔNG `distinct=True` + `count(name)`: một
        # hoá đơn khớp NHIỀU dòng của cùng một đơn (nhiều mặt hàng) sẽ bị
        # phép nối bảng dòng ở `_loc_qua_don_cha` đếm lặp nếu chỉ đếm `name`.
        fields=["count(distinct `tabSales Invoice`.name) as tong"],
    )[0].tong

    hom_nay = frappe.utils.nowdate()
    qua_han_thanh_toan = 0.0
    sap_den_han_so_luong = 0
    for r in frappe.get_list(
        "Sales Invoice", filters=[["outstanding_amount", ">", 0]] + pham_vi_hd,
        distinct=True,
        fields=["due_date", "outstanding_amount"],
    ):
        if not r.due_date:
            continue
        so_ngay = frappe.utils.date_diff(r.due_date, hom_nay)
        if so_ngay < 0:
            qua_han_thanh_toan += float(r.outstanding_amount or 0)
        elif so_ngay <= 7:
            sap_den_han_so_luong += 1

    rows = frappe.get_list(
        "Sales Invoice",
        filters=loc_ten + pham_vi_hd,
        distinct=True,
        # `customer` chỉ dùng NỘI BỘ để đối chiếu sở hữu bản ghi HĐĐT
        # (`einvoice.block_for` — F-08/E7), bị `pop` trước khi trả về, KHÔNG
        # phải một field mới lộ ra response.
        fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount",
                "status", "customer"],
        # tiebreak `name`.
        order_by="posting_date desc, name desc",
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
        #
        # Bọc lỗi CỐ Ý (cùng nguyên tắc `delivery_hook._chay_an_toan`: "giao
        # hàng của Miyano không được phụ thuộc kho khách" — ở đây là "danh
        # sách hoá đơn + công nợ không được phụ thuộc module HĐĐT của team
        # khác"). Module đó đổi tên field/cấu trúc không được phép biến MẤT
        # cả danh sách hoá đơn (NL-12.1: công nợ vẫn hiển thị bình thường dù
        # HĐĐT có chuyện gì). KHÔNG bọc kiểu này ở `portal_einvoice_download`
        # — đó là hành động khách chủ động bấm, lỗi phải lộ ra chứ không được
        # nuốt thành "im lặng không tải được gì".
        customer = r.pop("customer")
        try:
            r["einvoice"] = einvoice.block_for(r["name"], customer)
        except Exception:
            frappe.log_error(title=f"HĐĐT: không dựng được khối cho {r['name']}")
            r["einvoice"] = einvoice.khoi_mac_dinh()
    return {
        "rows": rows, "tong": tong,
        "qua_han_thanh_toan": qua_han_thanh_toan,
        "sap_den_han_so_luong": sap_den_han_so_luong,
    }


def _ho_so_cua_hoa_don(invoice) -> tuple:
    """Kiểm sở hữu Sales Invoice qua phiên, rồi trả `(si, ho_so)` — `ho_so`
    là TOÀN BỘ `Fast EInvoice Document` khớp hoá đơn này, đã lọc đúng
    `customer` (review round 1, C-1: một Sales Invoice có thể khớp NHIỀU bản
    ghi — bản gốc + bản điều chỉnh/thay thế + bản lập lại sau huỷ nội bộ —
    không được chỉ lấy MỘT). Dùng chung cho cả hai endpoint bên dưới, tránh
    hai nơi tự viết lại khối kiểm quyền."""
    dam_bao_xem_duoc("Sales Invoice", invoice)
    customer = get_portal_customer()
    si = frappe.get_doc("Sales Invoice", invoice)
    # `frappe.get_doc` KHÔNG tự kiểm quyền — `check_permission` là nơi hook
    # `has_permission` (miyano_portal.permissions.generic_has_permission)
    # thực sự chạy.
    si.check_permission("read")
    if si.customer != customer:
        raise frappe.PermissionError("Hoá đơn không thuộc đơn vị của bạn.")
    ho_so = [f for f in einvoice.resolve_all(invoice) if f.customer == si.customer]
    return si, ho_so


def _dn_cua_khach(delivery_note):
    """Kiểm sở hữu MỘT phiếu giao qua phiên — khuôn giống `_ho_so_cua_hoa_don`
    (Sales Invoice). `frappe.get_doc` KHÔNG tự kiểm quyền: `check_permission`
    mới là nơi hook `has_permission` (`permissions.generic_has_permission`)
    thật sự chạy, và chốt `dn.customer` là lớp thứ hai không phụ thuộc cấu
    hình DocPerm/User Permission."""
    dam_bao_xem_duoc("Delivery Note", delivery_note)
    customer = get_portal_customer()
    dn = frappe.get_doc("Delivery Note", delivery_note)
    dn.check_permission("read")
    if dn.customer != customer:
        raise frappe.PermissionError("Phiếu giao không thuộc đơn vị của bạn.")
    return dn


def _phuc_vu_file(fei_row, field, ten_file, method):
    """Đọc một file đính kèm chứng từ HĐĐT rồi đẩy vào response.

    Dùng CHUNG cho cả bản chính thức (`official_pdf`) lẫn bản nháp
    (`draft_pdf`): hai đường gọi có chốt TRẠNG THÁI ngược nhau, nhưng phần
    "kiểm file thật sự đọc được rồi phục vụ" thì giống hệt — viết hai lần là
    hai chỗ có thể quên `make_access_log` hoặc quên lọc `attached_to_*`.

    Người gọi PHẢI tự kiểm sở hữu và trạng thái TRƯỚC khi gọi hàm này; hàm
    này không biết gì về khách của phiên.
    """
    duong_dan = fei_row.get(field)
    if not duong_dan:
        frappe.throw(
            "File đang được tạo, vui lòng thử lại sau ít phút.", frappe.ValidationError
        )

    # File có thể đã bị xoá/hỏng dù field vẫn còn giá trị cũ (NL-12.4) — kiểm
    # file THẬT SỰ đọc được, không chỉ tin field. Lọc thêm `attached_to_*`
    # (không chỉ `file_url`): Frappe gộp file trùng nội dung theo content
    # hash, nên nhiều `File` khác nhau (đính vào chứng từ HĐĐT khác nhau) có
    # thể trỏ CHUNG một `file_url` — chỉ lọc theo url sẽ tìm thấy record của
    # chứng từ KHÁC dù bản ghi của CHÍNH chứng từ này đã bị xoá (đã bắt gặp
    # thật khi hai chứng từ HĐĐT test có PDF trùng byte).
    file_doc = frappe.db.get_value(
        "File",
        {
            "file_url": duong_dan,
            "attached_to_doctype": einvoice.FEI,
            "attached_to_name": fei_row.name,
        },
        "name",
    )
    if not file_doc:
        frappe.throw(
            "File bị thiếu hoặc hỏng trên hệ thống. Vui lòng liên hệ kế toán Miyano.",
            frappe.ValidationError,
        )
    content = frappe.get_doc("File", file_doc).get_content()

    from frappe.core.doctype.access_log.access_log import make_access_log

    make_access_log(
        doctype=einvoice.FEI, document=fei_row.name, file_type="pdf", method=method,
    )
    frappe.local.response.filename = ten_file
    frappe.local.response.filecontent = content
    frappe.local.response.type = "pdf"


# --------------------------------------------------------------------------
# CR-03 — ảnh cho dòng "hàng chưa có trong hệ thống"
# --------------------------------------------------------------------------

# BR-Y5, dùng lại nguyên văn giới hạn tài liệu BA đã đặt cho đính kèm.
CR03_TOI_DA_ANH = 5
CR03_TOI_DA_BYTE = 10 * 1024 * 1024
CR03_LOAI_ANH = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")
CR03_DUOI_ANH = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")


def _cr03_danh_sach_anh(gia_tri) -> list:
    """Đọc field `anh` (chuỗi JSON) thành list. Hỏng thì trả rỗng.

    KHÔNG để lỗi parse ném ra ngoài: field này do hệ thống ghi, nhưng một
    bản ghi cũ/nhập tay hỏng không được phép làm chết cả màn đặt hàng.
    """
    if not gia_tri:
        return []
    try:
        ds = frappe.parse_json(gia_tri)
    except Exception:
        return []
    return [x for x in ds if isinstance(x, str) and x] if isinstance(ds, list) else []


@frappe.whitelist()
def portal_dat_ngoai_tai_anh(de_xuat, dong_idx) -> dict:
    """CR-03 — khách tải một ảnh cho MỘT dòng "hàng chưa có trong hệ thống".

    Ảnh đính vào chính `Portal De Xuat Mua`, KHÔNG đính vào dòng con: mỗi lần
    khách sửa giỏ, `de_xuat_luu_nhap` thay TOÀN BỘ bảng `dat_ngoai`
    (`doc.set("dat_ngoai", …)`), nên một tệp đính theo tên dòng con thành mồ
    côi ngay lần lưu kế tiếp. Dòng con chỉ giữ danh sách `file_url`.

    Chốt quyền qua `_phieu_cua_toi()` — ĐÚNG chốt mà mọi endpoint phiếu khác
    dùng (kiểm cả trục khách hàng lẫn trục khoa phòng). Không tự chế bộ lọc.

    Chỉ cho tải khi phiếu còn **Nháp**: sau khi gửi duyệt, nội dung phiếu là
    thứ quản lý đang đọc để quyết định — thêm ảnh vào lúc đó là đổi hồ sơ
    dưới chân người đang duyệt.
    """
    doc = _phieu_cua_toi(de_xuat)
    if doc.trang_thai != "Nháp":
        frappe.throw(
            "Chỉ thêm ảnh được khi phiếu còn ở trạng thái Nháp.",
            frappe.ValidationError,
        )

    try:
        i = int(dong_idx)
    except (TypeError, ValueError):
        raise frappe.PermissionError("Dòng không hợp lệ.")
    dong = doc.get("dat_ngoai") or []
    if not (0 <= i < len(dong)):
        raise frappe.PermissionError("Dòng không hợp lệ.")
    r = dong[i]

    tep = (frappe.request.files or {}).get("file") if frappe.request else None
    if tep is None:
        frappe.throw("Không nhận được tệp ảnh.", frappe.ValidationError)

    noi_dung = tep.stream.read()
    if len(noi_dung) > CR03_TOI_DA_BYTE:
        frappe.throw(
            f"Ảnh nặng quá {CR03_TOI_DA_BYTE // (1024 * 1024)}MB. Chụp lại ở "
            "độ phân giải thấp hơn giúp Miyano.",
            frappe.ValidationError,
        )

    ten_goc = tep.filename or "anh.jpg"
    # Kiểm CẢ mime CLIENT KHAI lẫn đuôi tệp, và cả hai đều phải qua. Mime do
    # trình duyệt gửi nên không tin được một mình; đuôi tệp cũng vậy. Đây
    # KHÔNG phải chốt an ninh chống tệp độc — nó chỉ chặn khách vô tình tải
    # nhầm một PDF hay .docx rồi tưởng đã có ảnh.
    duoi_ok = any(ten_goc.lower().endswith(d) for d in CR03_DUOI_ANH)
    mime_ok = (tep.mimetype or "") in CR03_LOAI_ANH
    if not (duoi_ok and mime_ok):
        frappe.throw(
            "Chỉ nhận ảnh (JPG, PNG, WEBP, HEIC). Nếu đang có bản PDF, hãy "
            "chụp màn hình rồi tải ảnh lên.",
            frappe.ValidationError,
        )

    hien_co = _cr03_danh_sach_anh(r.anh)
    if len(hien_co) >= CR03_TOI_DA_ANH:
        frappe.throw(
            f"Mỗi mặt hàng tối đa {CR03_TOI_DA_ANH} ảnh. Xoá bớt một ảnh cũ "
            "rồi thử lại.",
            frappe.ValidationError,
        )

    from frappe.utils.file_manager import save_file

    f = save_file(
        f"CR03_{doc.name}_{i}_{frappe.generate_hash(length=6)}_{ten_goc}",
        noi_dung,
        "Portal De Xuat Mua",
        doc.name,
        is_private=1,
    )
    hien_co.append(f.file_url)
    r.anh = frappe.as_json(hien_co)
    doc.save(ignore_permissions=True)
    return {"file_url": f.file_url, "anh": hien_co}


@frappe.whitelist()
def portal_dat_ngoai_xoa_anh(de_xuat, dong_idx, file_url) -> dict:
    """Gỡ một ảnh khỏi dòng. Chỉ gỡ khỏi DANH SÁCH của dòng, KHÔNG xoá
    `File`: cùng một tệp có thể đang được dòng khác dùng (khách tải lại đúng
    ảnh đó), và xoá tệp thật là mất dữ liệu để đổi lấy vài KB."""
    doc = _phieu_cua_toi(de_xuat)
    if doc.trang_thai != "Nháp":
        frappe.throw(
            "Chỉ sửa ảnh được khi phiếu còn ở trạng thái Nháp.", frappe.ValidationError
        )
    try:
        i = int(dong_idx)
    except (TypeError, ValueError):
        raise frappe.PermissionError("Dòng không hợp lệ.")
    dong = doc.get("dat_ngoai") or []
    if not (0 <= i < len(dong)):
        raise frappe.PermissionError("Dòng không hợp lệ.")
    r = dong[i]
    con_lai = [u for u in _cr03_danh_sach_anh(r.anh) if u != file_url]
    r.anh = frappe.as_json(con_lai)
    doc.save(ignore_permissions=True)
    return {"anh": con_lai}


@frappe.whitelist()
def portal_dat_ngoai_xem_anh(de_xuat, file_url) -> None:
    """Phục vụ một ảnh riêng tư của phiếu.

    VÌ SAO CẦN ENDPOINT NÀY thay vì để trình duyệt gọi thẳng
    `/private/files/…`: role `Customer` có ZERO DocPerm trên
    `Portal De Xuat Mua`, nên đường tệp mặc định của Frappe kiểm quyền theo
    document đính kèm sẽ **403 với chính người vừa tải ảnh lên**. Đường sống
    của cổng là endpoint whitelist, đúng như mọi chỗ khác.

    Kiểm TỪNG LẦN xem (không tin danh sách đã trả lúc dựng màn): phiếu thuộc
    người gọi, VÀ `file_url` thật sự đính vào ĐÚNG phiếu đó. Thiếu vế thứ
    hai thì một `file_url` đoán được của bệnh viện khác vẫn đi qua — Frappe
    gộp tệp trùng nội dung theo hash nên `file_url` KHÔNG phải một khoá bí
    mật (cùng bài học đã ghi ở `_phuc_vu_file`).
    """
    doc = _phieu_cua_toi(de_xuat, cho_quan_ly=True)
    ten_file = frappe.db.get_value(
        "File",
        {
            "file_url": file_url,
            "attached_to_doctype": "Portal De Xuat Mua",
            "attached_to_name": doc.name,
        },
        "name",
    )
    if not ten_file:
        raise frappe.PermissionError("Ảnh không thuộc phiếu này.")

    tep = frappe.get_doc("File", ten_file)
    frappe.local.response.filename = tep.file_name
    frappe.local.response.filecontent = tep.get_content()
    frappe.local.response.type = "download"


@frappe.whitelist()
def portal_einvoice_download(invoice, loai="pdf", fei=None) -> None:
    """US-E7.2/BR-E4 — tải file HĐĐT của một hoá đơn. `loai`:

    - `"pdf"`  — bản thể hiện hoá đơn ĐÃ PHÁT HÀNH (`official_pdf`), chốt
      trạng thái `einvoice.co_the_tai()` (06 trở đi).
    - `"nhap"` — bản in thử Fast dựng khi chứng từ còn ở 01–04 (`draft_pdf`),
      chốt trạng thái `einvoice.la_ban_nhap()` — NGƯỢC LẠI với trên.

    KHÔNG có XML: module HĐĐT không lưu XML ở đâu cả (không field nào chứa
    'xml' trên `Fast EInvoice Document`, đã kiểm JSON) — không có gì để giao.

    `fei` TUỲ CHỌN — một hoá đơn có thể khớp NHIỀU chứng từ HĐĐT (gốc + điều
    chỉnh/thay thế/lập lại), khách chọn đúng bản muốn tải từ danh sách
    `khac`/`chinh` mà `portal_invoices` đã trả. Tham số này KHÔNG BAO GIỜ
    được dùng thẳng để lấy tài liệu — chỉ dùng để LỌC trong tập
    `resolve_all(invoice)` đã tự suy từ phiên và đã lọc đúng khách; một tên
    không có trong tập đó (hoá đơn của khách khác, tên bịa) bị từ chối ngay,
    không round-trip `frappe.get_doc(FEI, ...)` với tên client gửi.

    Kiểm TỪNG LẦN tải (BR-E4, NL-12.5): hoá đơn thuộc customer của phiên +
    Fast EInvoice Document khớp thuộc ĐÚNG hoá đơn đó + trạng thái cho phép
    tải + file thật sự đọc được — không chỉ tin cờ `tai_duoc` đã tính lúc
    liệt kê (dữ liệu có thể đã đổi giữa hai lần gọi, và đây là chứng từ
    thuế). Không có URL file công khai: `/printview` hay dán link sang máy
    khác không đăng nhập đều 403 ở `check_permission`/`get_portal_customer`.
    """
    if loai not in ("pdf", "nhap"):
        frappe.throw(
            "Cổng chỉ cung cấp bản PDF thể hiện và bản nháp. Cần bản gốc XML "
            "có giá trị pháp lý, vui lòng liên hệ kế toán Miyano.",
            frappe.ValidationError,
        )

    _si, ho_so = _ho_so_cua_hoa_don(invoice)
    if not ho_so:
        frappe.throw("Chưa có hoá đơn điện tử cho chứng từ này.", frappe.ValidationError)

    if fei:
        muc = next((f for f in ho_so if f.name == fei), None)
        if not muc:
            raise frappe.PermissionError("Chứng từ HĐĐT không thuộc hoá đơn này.")
    else:
        muc = einvoice.chon_ban_ghi_chinh(ho_so)

    # Hai nhánh TÁCH BẠCH, cố ý không gộp điều kiện: chốt trạng thái của
    # chúng NGƯỢC nhau (`co_the_tai` mở từ 06, `la_ban_nhap` mở 01–04). Gộp
    # lại là sớm muộn cũng giao một bản in thử cho khách như thể nó là chứng
    # từ thuế, hoặc chặn nhầm hoá đơn thật.
    if loai == "nhap":
        if not einvoice.la_ban_nhap(muc):
            frappe.throw(
                "Chứng từ này không còn ở dạng nháp. Dùng nút tải hoá đơn điện tử.",
                frappe.ValidationError,
            )
        _phuc_vu_file(
            muc, "draft_pdf", f"Nhap_{muc.name}.pdf", "portal_einvoice_download_nhap"
        )
        return

    if not einvoice.co_the_tai(muc):
        frappe.throw(
            "Hoá đơn điện tử này chưa có file để tải. Bấm [Yêu cầu hỗ trợ] "
            "nếu cần Miyano hỗ trợ.",
            frappe.ValidationError,
        )
    _phuc_vu_file(
        muc,
        "official_pdf",
        f"{muc.fast_invoice_no or muc.name}.pdf",
        "portal_einvoice_download",
    )


@frappe.whitelist()
def portal_einvoice_nhap(delivery_note):
    """Khối "Hoá đơn nháp" của một phiếu giao — dòng hàng + tổng tiền của
    chứng từ HĐĐT kế toán vừa lập, kèm câu cảnh báo pháp lý đi CÙNG dữ liệu
    (`einvoice.CANH_BAO_NHAP`). `None` khi chưa lập.

    Neo theo Delivery Note chứ không theo Sales Invoice: bản ghi HĐĐT do
    `builder.create_from_delivery_note` sinh ra chỉ có `delivery_note`, và
    phiếu giao có thể chưa được lập hoá đơn bán hàng tại thời điểm đó."""
    dn = _dn_cua_khach(delivery_note)
    return einvoice.nhap_cho_delivery_note(dn.name, dn.customer)


@frappe.whitelist()
def portal_einvoice_nhap_pdf(delivery_note) -> None:
    """Tải bản in thử PDF theo PHIẾU GIAO — dùng ở màn chi tiết đơn hàng,
    nơi phiếu giao có thể chưa có Sales Invoice nào để bám vào.

    Cùng ràng buộc với `portal_einvoice_download`: kiểm sở hữu từng lần,
    không nhận tên chứng từ từ client, ghi `Access Log`."""
    dn = _dn_cua_khach(delivery_note)
    ban = einvoice.ban_nhap_tho(dn.name, dn.customer)
    if not ban:
        frappe.throw(
            "Phiếu giao này chưa có hoá đơn nháp. Nếu hoá đơn đã phát hành, "
            "xem ở mục Hoá đơn & công nợ.",
            frappe.ValidationError,
        )
    _phuc_vu_file(ban, "draft_pdf", f"Nhap_{dn.name}.pdf", "portal_einvoice_nhap_pdf")


@frappe.whitelist()
def portal_einvoice_ho_tro(invoice, fei=None) -> dict:
    """NL-12.4 — nút [Yêu cầu hỗ trợ] trên khối HĐĐT, tự đính mã hoá đơn.
    `fei` tuỳ chọn (cùng nguyên tắc "chỉ lọc trong tập đã resolve" của
    `portal_einvoice_download`) — khi khách bấm nút trên MỘT bản ghi cụ thể
    trong danh sách `khac`, thông báo đính đúng mã đó."""
    si, ho_so = _ho_so_cua_hoa_don(invoice)
    customer = si.customer
    fei_name = None
    if fei:
        muc = next((f for f in ho_so if f.name == fei), None)
        fei_name = muc.name if muc else None
    elif ho_so:
        fei_name = einvoice.chon_ban_ghi_chinh(ho_so).name
    bao_yeu_cau_ho_tro_hddt(customer, invoice, fei_name)
    return {"ok": True}


@frappe.whitelist()
def portal_request_cancel(order, reason) -> dict:
    dam_bao_xem_duoc("Sales Order", order)
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


def chan_neu_khong_phai_nhan_vien_miyano() -> None:
    """Caller-role guard: only staff (not portal customers) may provision accounts.

    Tách thành hàm riêng (Task 15) để đường nhập nhân sự hàng loạt từ Desk
    (`api/nhan_su.py`) chốt vai trò bằng ĐÚNG MỘT phép so với `portal_provision`
    — hai bản sao của cùng một danh sách role là kiểu lệch mà dự án này đã trả
    giá nhiều lần.
    """
    if not (set(frappe.get_roles()) & {"System Manager", "Sales Manager", "Sales User"}):
        frappe.throw("Không có quyền", frappe.PermissionError)


@frappe.whitelist()
def portal_provision(
    customer, email, send_invite=False, first_name=None, vai_tro=None, khoa_phong=None,
    dien_thoai=None,
) -> dict:
    """Cấp tài khoản cổng cho một email của một khách hàng.

    Task 15 (QĐ-G21) thêm BA tham số tuỳ chọn cho đường nhập nhân sự từ tệp
    Excel — bỏ trống cả ba thì hành vi GIỮ NGUYÊN từng dấu phẩy như trước
    (xem `test_provision.py`, không đổi một dòng nào):

      * `first_name` — tên NGƯỜI. Bỏ trống thì vẫn rơi về `customer` như cũ;
        đó chính là chỗ khiến tên hiển thị của mọi tài khoản cổng là tên bệnh
        viện (gốc của lỗi truy vết đã phải vá ở tầng hiển thị, `97fd6e2`).
      * `vai_tro` + `khoa_phong` — TỜ KHAI THẮNG. Khi người gọi nói rõ vai trò,
        luật ngầm "tài khoản đầu tiên của một bệnh viện là Quản lý" ở dưới
        KHÔNG chạy: hai cơ chế cùng quyết một việc là lỗi lặp lại của dự án
        này. Tài khoản cấp theo tờ khai luôn `active=1` — dùng được ngay,
        không rơi vào trạng thái chờ-gán-khoa.

    Task 10 thêm tham số THỨ TƯ, giữ đúng lời hứa ở trên — bỏ trống thì hành
    vi GIỮ NGUYÊN từng dấu phẩy như trước, `test_provision.py` không được đỏ
    một bài nào:

      * `dien_thoai` — số điện thoại nguồn cho dòng thời gian "Ai đã làm gì"
        (`User.mobile_no`). Tài khoản MỚI thì đặt thẳng lúc tạo. Tài khoản
        ĐÃ CÓ (nhánh `elif` dưới) chỉ được ĐIỀN VÀO CHỖ TRỐNG khi
        `mobile_no` đang rỗng — KHÔNG BAO GIỜ đè lên số đã có, đó là dữ liệu
        người khác đã nhập. Trường hợp lệch số (đã có số KHÁC) không xử ở
        đây: nó là quyết định cần người xem xét, không phải hành vi tự động
        — người gọi (`api/nhan_su.py::_phan_tich`) phải chặn/gắn cờ TRƯỚC khi
        gọi tới đây, không phải hàm này tự âm thầm bỏ qua.
    """
    chan_neu_khong_phai_nhan_vien_miyano()

    if not frappe.db.exists("Customer", customer):
        frappe.throw("Không tìm thấy khách hàng.")
    # VÒNG SỬA 3 (F5, review độc lập, Important): chặn SỚM, TRƯỚC mọi side
    # effect (User/Contact/User Permission). Bản trước không kiểm điều này
    # — nếu `email` đã có `Portal Member` thuộc một khách hàng KHÁC,
    # hàm vẫn âm thầm tạo Contact + Dynamic Link + User Permission cho
    # `customer` mới rồi trả về như cấp thành công, trong khi danh tính
    # cổng (Portal Member) của user đó vẫn trỏ về khách hàng CŨ — tài khoản
    # sẽ không bao giờ nhìn thấy `customer` mới, và người cấp không thấy gì
    # bất thường để biết mà sửa.
    khach_hien_co = frappe.db.get_value("Portal Member", {"user": email}, "customer")
    if khach_hien_co and khach_hien_co != customer:
        frappe.throw(
            f'Tài khoản "{email}" đã thuộc khách hàng "{khach_hien_co}", không thể '
            f'cấp thêm cho "{customer}". Một tài khoản chỉ thuộc một khách hàng.',
            frappe.ValidationError,
        )
    if not frappe.db.exists("User", email):
        u = frappe.get_doc({
            "doctype": "User", "email": email, "first_name": first_name or customer,
            "user_type": "Website User", "send_welcome_email": int(send_invite),
        })
        if dien_thoai:
            u.mobile_no = dien_thoai
        u.append("roles", {"role": "Customer"})
        u.insert(ignore_permissions=True)
    elif dien_thoai and not frappe.db.get_value("User", email, "mobile_no"):
        # Task 10, QĐ-4 — tài khoản ĐÃ CÓ (User có sẵn nhưng đang qua nhánh
        # tạo mới của `Portal Member`, ví dụ vừa được tạo cho một bệnh viện
        # khác rồi mới nhập cho bệnh viện này) chỉ được ĐIỀN VÀO CHỖ TRỐNG.
        # `mobile_no` đang có giá trị thì bỏ qua hẳn nhánh này — không đè.
        frappe.db.set_value("User", email, "mobile_no", dien_thoai, update_modified=False)
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
    # Từ 18/08/2026 `portal_context.get_allowed_customers()` chỉ đọc `Portal
    # Member`, không còn đọc `Contact`/`Dynamic Link` nữa — thiếu bước này,
    # tài khoản vừa cấp sẽ VÔ HÌNH với toàn bộ tầng phân quyền cổng ngay khi
    # hàm này trả về (Task 5, phát hiện qua test_provision.py đỏ). Đi qua
    # `doc.insert()` để `PortalMember.validate()` chạy, KHÔNG dùng
    # `frappe.db.set_value()`/`doc.db_set()` — xem giới hạn đã biết của
    # `_chan_hai_quan_ly` trong portal_member.py.
    #
    # VÒNG SỬA 2 (F5, phán quyết coordinator): chủ đầu tư mô tả luồng thật
    # là "nhân viên có tài khoản và ĐƯỢC GÁN KHOA BỞI QUẢN LÝ, nhưng tài
    # khoản sẽ được tạo ở phía Miyano" — tài khoản có TRƯỚC khoa phòng.
    # Tài khoản ĐẦU TIÊN của một bệnh viện luôn là Quản lý, kích hoạt ngay
    # (không có quản lý nào khác để chọi `_chan_hai_quan_ly`). Tài khoản
    # SAU ĐÓ — bệnh viện đã có quản lý đang hoạt động — không thể tự nó là
    # quản lý thứ hai, nên tạo dạng Nhân viên khoa CHƯA gán khoa (`active=0`
    # — chỗ giữ chỗ hợp lệ nhờ `_chan_vai_tro_va_khoa_phong`/
    # `_chan_thieu_ma_ngan` vừa nới ở vòng sửa này) và CHỜ quản lý gán khoa
    # + bật lại. Đây KHÔNG còn cùng hình với ca "hai tài khoản" của patch
    # backfill (`v1_23/backfill_portal_member.py`, vẫn tạo Quản lý+active=0
    # vì backfill không có nghiệp vụ "quản lý gán khoa sau" đứng sau nó) —
    # hai đường cố ý khác hình nhau, không phải một sai lệch cần hợp nhất.
    if frappe.db.exists("Portal Member", {"user": email}):
        cho_gan_khoa = frappe.db.get_value("Portal Member", {"user": email}, "active") == 0
    elif vai_tro:
        # TỜ KHAI THẮNG (Task 15, QĐ-G21) — vai trò và khoa phòng do người
        # nhập khai trên bảng Excel, không suy từ luật ngầm bên dưới. Vẫn đi
        # qua `doc.insert()` (không `db.set_value`): toàn bộ phép cách ly
        # "khoa này có thuộc đúng bệnh viện không" nằm trong
        # `PortalMember.validate()` — xem giới hạn đã biết của
        # `_chan_hai_quan_ly` trong portal_member.py.
        frappe.get_doc({
            "doctype": "Portal Member", "user": email, "customer": customer,
            "vai_tro": vai_tro, "khoa_phong": khoa_phong or None, "active": 1,
        }).insert(ignore_permissions=True)
        cho_gan_khoa = False
    else:
        da_co_quan_ly = frappe.db.exists(
            "Portal Member", {"customer": customer, "vai_tro": "Quản lý", "active": 1}
        )
        if da_co_quan_ly:
            frappe.get_doc({
                "doctype": "Portal Member", "user": email, "customer": customer,
                "vai_tro": "Nhân viên khoa", "active": 0,
            }).insert(ignore_permissions=True)
            cho_gan_khoa = True
        else:
            frappe.get_doc({
                "doctype": "Portal Member", "user": email, "customer": customer,
                "vai_tro": "Quản lý", "active": 1,
            }).insert(ignore_permissions=True)
            cho_gan_khoa = False
    # `cho_gan_khoa`: True nghĩa là tài khoản vừa cấp CHƯA dùng được — quản
    # lý bệnh viện phải vào gán khoa phòng rồi bật `active` mới xong. Trả
    # cờ này ra để người gọi (giao diện cấp tài khoản phía Miyano) biết còn
    # một bước nữa, không để tài khoản "cấp xong nhưng chết lặng lẽ".
    return {"user": email, "cho_gan_khoa": cho_gan_khoa}


@frappe.whitelist()
def portal_document_download(doctype, name) -> None:
    if doctype not in ("Sales Order", "Delivery Note", "Sales Invoice"):
        frappe.throw("Loại chứng từ không hợp lệ.")
    # Vệ guard trên CHỈ CHO QUA đúng 3 doctype `dam_bao_xem_duoc` đã có nhánh
    # — `NotImplementedError` của hàm đó (doctype lạ) không bao giờ tới được
    # đây để lộ ra khách như một lỗi 500.
    dam_bao_xem_duoc(doctype, name)
    doc = frappe.get_doc(doctype, name)
    # frappe.get_doc does NOT auto-enforce has_permission in this build, so the
    # isolation check must be done explicitly before any data leaves the server.
    doc.check_permission("read")
    # Phiếu giao đã có BẢN SCAN ĐÃ KÝ thì khách nhận đúng bản đó, không phải
    # bản in lại chưa chữ ký. Đó là thứ khách cần khi đối chiếu công nợ hay
    # khi thanh tra hỏi "ai đã nhận hàng ngày đó": một bản in mới sinh chứng
    # minh được nội dung, không chứng minh được việc bàn giao đã xảy ra.
    # (Yêu cầu nguyên văn của chủ đầu tư và ngày nêu: xem docstring
    # `patches/v1_28/them_o_dinh_bien_ban_da_ky.py` — chép ở MỘT chỗ.)
    canh_bao = None
    if doctype == "Delivery Note":
        da_phat, canh_bao = _tra_ban_scan_da_ky(doc)
        if da_phat:
            return
    from frappe.utils.pdf import get_pdf
    from frappe.www.printview import get_html_and_style
    # Each doctype renders through its installed bilingual Miyano print
    # format (see setup/install_print_formats.py).
    PRINT_FORMATS = {
        "Sales Order": "Miyano - Xác nhận đơn hàng",
        # Nút "⬇ Phiếu giao đợt" phát ĐÚNG tờ phiếu mà hai bên ký, tức mẫu
        # 02-VT "Phiếu xuất kho kiêm biên bản bàn giao", KHÔNG phải
        # "Miyano - Phiếu giao hàng" (mẫu thương mại, một tờ giấy KHÁC).
        # Sự việc kiểm chứng được bằng SQL: site có nhiều mẫu in cho
        # `Delivery Note`, và mẫu có ô ký của HAI BÊN là mẫu 02-VT.
        #
        # Vì sao đây là lỗi chứ không phải chuyện thẩm mỹ: khách ký vào tờ A
        # tại kho, rồi lên cổng tải về tờ B với bố cục khác, thiếu cột Số lô/
        # Hạn dùng và thiếu đoạn cam kết bàn giao. Lúc đối chiếu công nợ hay
        # lúc thanh tra hỏi, hai tờ giấy cùng nói về một lần giao mà không
        # khớp nhau về hình thức là thứ không giải thích được — và không có
        # tín hiệu nào báo, vì bản thân mỗi tờ đều "đúng".
        #
        # Một chứng từ, hai trạng thái: CHƯA có bản scan → in bản 02-VT chưa
        # ký; ĐÃ đính bản scan → `_tra_ban_scan_da_ky` ở trên trả thẳng bản
        # có chữ ký. Mẫu "Miyano - Phiếu giao hàng" KHÔNG gỡ khỏi site —
        # nhân viên vẫn chọn được trên Desk khi cần một bản thương mại.
        "Delivery Note": "Miyano - Phiếu xuất kho (02-VT)",
        "Sales Invoice": "Miyano - Hoá đơn",
    }
    print_format = PRINT_FORMATS.get(doctype)
    html = get_html_and_style(
        doc=doc.as_json(), print_format=print_format, no_letterhead=0
    )["html"]
    if canh_bao:
        html = _dan_canh_bao(html, canh_bao)
    frappe.local.response.filename = f"{name}.pdf"
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "pdf"


# Đuôi file được phép phát ra cho khách. Đuôi lấy từ TÊN FILE, mà tên file là
# văn bản tự do do người đính đặt — không phải một khai báo kiểu dữ liệu.
#
# CỐ Ý không đoán kiểu file bằng magic byte: đó là thêm một lớp suy đoán nữa
# để phục vụ một cái tên đặt sai, trong khi đường lui (in bản chưa ký) đã có
# sẵn, đã được kiểm, và cho khách một chứng từ đọc được ngay.
# Ruling P45 (chủ đầu tư chốt) — nút phiếu giao MỞ XEM ngay trong tab, không
# tải về. Chia làm hai nhóm vì "mở xem" chỉ đúng với thứ trình duyệt dựng
# được; `.tif` mở inline ra một TAB TRẮNG. Nhóm thứ hai là ĐƯỜNG THOÁT bắt
# buộc: giữ nguyên đường tải về, khách cầm được file thay vì nhìn trang trống.
_DUOI_MO_XEM = ("pdf", "jpg", "jpeg", "png", "gif", "bmp", "webp")
_DUOI_TAI_VE = ("tif", "tiff")
# `heic` CỐ Ý không nằm trong danh sách: máy Windows của bệnh viện phần lớn
# không mở được, nên phát ra một tệp HEIC là hỏng im lặng ở đầu bên kia. Ảnh
# HEIC phải được lưu lại thành JPG/PDF trước khi đính.
_DUOI_SCAN_CHO_PHEP = _DUOI_MO_XEM + _DUOI_TAI_VE

# Dán lên ĐẦU bản in khi phiếu ĐÃ CÓ bản scan đã ký mà cổng không phát được.
# Không có dòng này, khách nhận một tờ chưa ký trông hoàn toàn hợp lý trong
# khi bản đã ký vẫn tồn tại — đúng lớp "thay thế im lặng" mà cả việc này sinh
# ra để dẹp. Cảnh báo phải nằm trên CHÍNH tờ giấy khách mở ra; một dòng Error
# Log chỉ Miyano thấy.
_CANH_BAO_CHUA_KY = (
    "BẢN IN LẠI — CHƯA CÓ CHỮ KÝ. Phiếu giao này ĐÃ CÓ bản scan biên bản hai "
    "bên ký, nhưng cổng chưa phát được (lỗi tệp phía Miyano, đã có cảnh báo "
    "tự động). Vui lòng liên hệ Miyano 0988.806.848 để nhận bản đã ký."
)


def _dan_canh_bao(html: str, canh_bao: str) -> str:
    """Dán một khối cảnh báo lên đầu bản in.

    `escape_html` chứ không nối chuỗi thẳng: nội dung cảnh báo hôm nay là hằng
    số, nhưng hàm này là chỗ duy nhất chèn văn bản vào một trang sắp thành PDF
    — để ngỏ là mở sẵn một đường XSS lưu trữ cho lần sửa sau.
    """
    return (
        '<div style="border:2px solid #b00020; color:#b00020; padding:8px 10px;'
        ' margin:0 0 12px; font-weight:bold; font-size:13px; text-align:center">'
        f"⚠ {frappe.utils.escape_html(canh_bao)}</div>" + html
    )


def _tra_ban_scan_da_ky(doc) -> tuple[bool, str | None]:
    """Phiếu giao có bản scan biên bản đã ký → ĐẨY CHÍNH FILE ĐÓ ra response.

    Trả `(đã_phát, cảnh_báo)`:
      * `(True, None)`  — đã đẩy file, người gọi dừng;
      * `(False, None)` — phiếu không có bản scan nào, in bản chưa ký như cũ;
      * `(False, "...")` — phiếu CÓ bản scan nhưng không phát được. Vẫn in bản
        chưa ký (khách cầm được chứng từ đọc được ngay), NHƯNG kèm cảnh báo
        trên chính tờ giấy đó. Lui về trong im lặng ở nhánh này là đưa khách
        một tờ khác với tờ họ đã ký mà không nói gì.

    Ba chốt, mỗi chốt bịt một cách hỏng đã lường trước:

    1. **Không tin `file_url` một mình.** `custom_bien_ban_da_ky` là một ô
       `Attach`, giá trị của nó chỉ là một CHUỖI đường dẫn — sửa được từ Desk,
       và trỏ được tới bất kỳ file nào trên site (kể cả file riêng của khách
       khác). Nên phải tra `tabFile` bằng CẢ `attached_to_doctype` +
       `attached_to_name` khớp đúng phiếu giao này. Không khớp → coi như không
       có, in bản chưa ký; KHÔNG ném lỗi ra mặt khách vì đó là lỗi cấu hình
       phía Miyano, không phải việc của họ.

    2. **KHÔNG cứng `type = "pdf"`.** Bản scan thực tế phần lớn là ảnh chụp
       (JPG/PNG) chứ không phải PDF. Trả một JPG dưới đuôi `.pdf` thì máy
       khách mở ra rác — hỏng im lặng, và người báo lỗi sẽ là bệnh viện.
       Đuôi file lấy từ chính tên file đã lưu, NHƯNG chỉ trong danh sách cho
       phép (`_DUOI_SCAN_CHO_PHEP`).

    3. **Đọc nội dung qua `File.get_content()`**, không ghép đường dẫn tay:
       file riêng tư nằm ở `sites/<site>/private/files`, file công khai ở
       `public/files` — hàm của Frappe biết chỗ, phép ghép chuỗi thì không.
    """
    url = (doc.get("custom_bien_ban_da_ky") or "").strip()
    if not url:
        return False, None
    ten_file = frappe.db.get_value(
        "File",
        {
            "file_url": url,
            "attached_to_doctype": "Delivery Note",
            "attached_to_name": doc.name,
        },
        "name",
    )
    if not ten_file:
        # File không thuộc phiếu này (ô `Attach` bị sửa tay, dán nhầm đường dẫn
        # của phiếu khác). KHÔNG cảnh báo trên bản in: với phiếu NÀY thì không
        # có bản scan hợp lệ nào cả, và một cảnh báo "đã có bản ký" ở đây là
        # nói sai với khách.
        return False, None
    f = frappe.get_doc("File", ten_file)
    tach = (f.file_name or url).rsplit(".", 1)
    duoi = tach[1].lower() if len(tach) == 2 else ""
    if duoi not in _DUOI_SCAN_CHO_PHEP:
        # Tên file là văn bản tự do: một bản scan đặt tên "bien ban 25.08.2026"
        # cho ra file `.2026`, không máy nào mở được. Lui về bản in như ca file
        # mất trên đĩa — khách vẫn có chứng từ đọc được, còn Miyano đổi lại tên.
        frappe.log_error(
            "portal_document_download",
            f"Bản scan biên bản của {doc.name} có tên file không mang đuôi hợp "
            f"lệ: «{f.file_name or url}». Cổng phát bản in CHƯA KÝ cho tới khi "
            f"file được đổi tên (đuôi hợp lệ: {', '.join(_DUOI_SCAN_CHO_PHEP)}).",
        )
        return False, _CANH_BAO_CHUA_KY
    try:
        noi_dung = f.get_content()
    except Exception:
        # File đã bị xoá khỏi đĩa nhưng bản ghi còn (dọn dẹp dở dang, restore
        # thiếu thư mục files). Lui về bản in — khách vẫn có chứng từ đọc
        # được, thay vì một lỗi 500 không nói được gì.
        #
        # `frappe.log_error(title, message)` — TIÊU ĐỀ trước. Gọi ngược thì
        # `Error Log.method` (Data, 140 ký tự) nhận cả câu tiếng Việt còn
        # phần `error` chỉ còn mỗi tên hàm: dòng log tra không ra, đọc không
        # hiểu.
        frappe.log_error(
            "portal_document_download",
            f"Không đọc được bản scan biên bản của {doc.name}: {url}",
        )
        return False, _CANH_BAO_CHUA_KY
    frappe.local.response.filename = f"{doc.name}-bien-ban-da-ky.{duoi}"
    frappe.local.response.filecontent = noi_dung
    frappe.local.response.type = "download"
    # Ruling P45. `as_raw()` của Frappe lấy Content-Disposition từ
    # `display_content_as`, mặc định "attachment". Đặt TƯỜNG MINH cả hai nhánh
    # (không chỉ nhánh inline): `frappe.local.response` sống qua nhiều lời gọi
    # trong cùng một tiến trình, để sót thì giá trị của lần trước chảy sang.
    frappe.local.response.display_content_as = (
        "inline" if duoi in _DUOI_MO_XEM else "attachment"
    )
    return True, None


@frappe.whitelist()
def portal_bao_gia_pdf(order=None, quotation=None) -> None:
    """§3.6 — tải PDF của MỘT báo giá (Quotation) của cổng.

    Cùng khuôn `kho_phieu_pdf`/`portal_einvoice_download` (Quyết định nền số
    8): trả file qua response, KHÔNG sinh URL công khai — người dùng cổng
    không dùng được `/printview`.

    `order` ở lại trong chữ ký cho liên kết cũ: đơn hàng không còn báo giá
    dạng PDF (patch v1_44 bỏ vòng báo giá trên đơn và mẫu in "Miyano - Báo
    giá"), nên gọi theo đơn nhận một lời từ chối rõ ràng.
    """
    if quotation:
        return _bao_gia_pdf_quotation(quotation)
    frappe.throw(
        "Đơn hàng không có báo giá dạng PDF. Báo giá nằm ở mục Báo giá.",
        frappe.ValidationError,
    )


@frappe.whitelist()
def portal_reorder(order: str) -> dict:
    """UC-14 / US-E1.5 — điền lại giỏ theo một đơn cũ, theo GIÁ HIỆN HÀNH
    trong Price List của khách (spec 2026-10-09 §4.4).

    Mặt hàng chưa có giá KHÔNG bị loại: nó vào giỏ ở tầng chờ báo giá
    (`tang = "cho_bao_gia"`, `gia_hien_hanh = None`), đúng như khi khách tự
    chọn nó từ danh mục. Không còn tra hợp đồng khung hay hạn mức, nên số
    lượng giữ nguyên như đơn cũ.

    Dòng không còn đặt được (mặt hàng đã ngừng kinh doanh) vào `bi_loai` kèm
    mã lý do để giao diện dịch sang thông điệp. Im lặng bỏ bớt dòng là cách
    chắc chắn khiến khách đặt thiếu hàng mà không biết. Dòng giữ chỗ kỹ thuật
    `ITEM_GIU_CHO` thì bỏ qua hẳn — nó chưa bao giờ là thứ khách đặt.
    """
    dam_bao_xem_duoc("Sales Order", order)
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # `frappe.get_doc` KHÔNG chạy hook `has_permission` ở build này — phải
    # kiểm tường minh trước khi đọc bất cứ thứ gì của tài liệu.
    so.check_permission("read")
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng không thuộc đơn vị của bạn.")

    # Giá hỏi `bang_gia_khach` — ĐÚNG nguồn mà `dat_hang._xay_don` dùng lúc
    # dựng đơn, nên giỏ đặt lại và đơn sắp lập không thể nói hai giá khác
    # nhau cho cùng một mã. KHÔNG đọc `rate` hay `custom_hdnt` của đơn cũ:
    # đó là giá của ngày lập đơn cũ, không phải giá hôm nay. Một truy vấn
    # cho cả đơn.
    gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(
        customer, [d.item_code for d in so.items]
    )
    gio_hang, bi_loai = [], []
    for dong in so.items:
        if dong.item_code == ITEM_GIU_CHO:
            continue
        # Cùng chốt (và cùng mã lý do) với `dat_hang._xay_don`: đưa một mặt
        # hàng ngừng kinh doanh vào giỏ là để khách bị từ chối ở bước gửi.
        if frappe.db.get_value("Item", dong.item_code, "disabled"):
            bi_loai.append({
                "item_code": dong.item_code, "ly_do": "mat_hang_ngung_kinh_doanh",
            })
            continue
        gia = gia_theo_ma.get(dong.item_code)
        # Kèm tên và ĐVT: giỏ hàng dựng thẳng từ payload này, thiếu chúng thì
        # khách nhìn thấy mã hàng trần và không có đơn vị tính.
        gio_hang.append({
            "item_code": dong.item_code,
            "item_name": dong.item_name
            or frappe.db.get_value("Item", dong.item_code, "item_name"),
            "uom": dong.uom or "",
            "qty": float(dong.qty),
            "tang": "bang_gia" if gia is not None else "cho_bao_gia",
            "gia_hien_hanh": gia,
        })

    return {"gio_hang": gio_hang, "bi_loai": bi_loai}


def _dong_bo_so_luong_duyet_ve_phieu(ten_phieu: str, doi_items_ap_dung: dict[str, float]) -> None:
    """Task 9, Step 4b — ghi ngược `so_luong_duyet` lên phiếu đề xuất sau khi
    khách sửa số lượng báo giá (`portal_bao_gia_sua_so_luong`) thành công.

    Chỉ chạm dòng THẬT SỰ đổi (`doi_items_ap_dung`) — không đụng field nào khác, kể cả khi `save()`
    dưới đây đi qua `_chan_sua_so_luong_de_xuat()`: guard đó chỉ khoá
    `so_luong_de_xuat`/`item_code`/xoá dòng, không khoá `so_luong_duyet`."""
    phieu = frappe.get_doc("Portal De Xuat Mua", ten_phieu)
    doi = False
    for row in phieu.items:
        if row.item_code in doi_items_ap_dung:
            row.so_luong_duyet = doi_items_ap_dung[row.item_code]
            doi = True
    if doi:
        phieu.save(ignore_permissions=True)


# ---------------------------------------------------------------- trang Thông báo
# Brief 2026-08-15 (trang thông báo) Phần 3 — dùng thẳng `Notification Log`
# có sẵn của Frappe (KHÔNG dựng doctype mới). Hai endpoint dưới đây KHÔNG
# nhận `user`/`customer` từ client — mọi thứ suy từ `frappe.session.user`.


def _lien_ket_thong_bao(document_type, document_name, customer) -> str | None:
    """Suy đường dẫn trong SPA cho một Notification Log, kiểm sở hữu CHÍNH
    chứng từ đang trỏ tới trước khi trả.

    `for_user` của Notification Log đã lọc đúng người nhận (người gọi truyền
    `customer` suy từ CHÍNH phiên đó), nhưng KHÔNG phải bằng chứng người đó
    có quyền đọc document đang trỏ tới — một bản ghi định tuyến sai (dữ liệu
    cũ, lỗi ở nơi khác) vẫn có thể mang `for_user` đúng mà `document_name`
    lại là chứng từ CỦA KHÁCH KHÁC. Đối chiếu lại `customer` của CHÍNH
    document trước khi trả link là lớp kiểm thứ hai, không phụ thuộc việc
    `for_user` đã lọc đúng hay chưa.

    Trả `None` khi không suy được / không map được loại chứng từ / không sở
    hữu — trang Thông báo vẫn hiện dòng chữ, chỉ ẩn nút đi tới chứng từ.
    """
    if not document_type or not document_name or not customer:
        return None
    try:
        if document_type == "Sales Order":
            if frappe.db.get_value("Sales Order", document_name, "customer") != customer:
                return None
            # Task 11 — đường CHÍNH TẮC của màn chi tiết đơn nay nằm dưới
            # `/yeu-cau`. `/orders/<name>` vẫn chuyển hướng đúng (router.js,
            # QĐ-G11) nên thông báo CŨ không gãy — nhưng thông báo MỚI phải
            # mang đường mới, không phải một đường sống nhờ lớp tương thích.
            return f"/yeu-cau/don/{document_name}"

        if document_type == "Portal De Xuat Mua":
            if frappe.db.get_value("Portal De Xuat Mua", document_name, "customer") != customer:
                return None
            # 03/09/2026 — trước bản này doctype này KHÔNG có nhánh nào ở
            # đây, nên mọi thông báo §5.8 về phiếu (gửi duyệt / duyệt / từ
            # chối / xin sửa) hiện ra KHÔNG có nút đi tới chứng từ: quản lý
            # đọc "Khoa vừa gửi đề xuất mua X chờ bạn duyệt" rồi phải tự mở
            # danh sách và tìm lại X bằng mắt.
            #
            # Vá được ĐÚNG LÚC NÀY vì chi tiết một yêu cầu vừa có MỘT màn
            # chính tắc — trước đó, trỏ vào đường phiếu là bỏ nửa đơn, trỏ
            # vào đường đơn thì phiếu Chờ duyệt chưa có đơn nào để trỏ.
            return f"/yeu-cau/phieu/{document_name}"

        if document_type == "Quotation":
            gt = frappe.db.get_value(
                "Quotation", document_name,
                ["quotation_to", "party_name", "custom_nguon_don"], as_dict=True,
            )
            if not _la_bao_gia_cong_cua(gt, customer):
                return None
            return f"/yeu-cau-bao-gia/{document_name}"

        if document_type == "Sales Invoice":
            if frappe.db.get_value("Sales Invoice", document_name, "customer") != customer:
                return None
            # Cổng chưa có trang chi tiết một Sales Invoice riêng — "Hoá đơn &
            # công nợ" liệt kê tất cả, cùng khuôn brief (`v.v.` — minh hoạ,
            # không phải danh sách đóng).
            return "/invoices"

        if document_type == "Delivery Note":
            if frappe.db.get_value("Delivery Note", document_name, "customer") != customer:
                return None
            # Cổng không có trang chi tiết Delivery Note riêng — phiếu giao
            # hiện trong khối "Tiến trình giao hàng" của CHÍNH đơn hàng.
            so = frappe.db.get_value(
                "Delivery Note Item",
                {"parent": document_name, "against_sales_order": ["is", "set"]},
                "against_sales_order",
            )
            return f"/yeu-cau/don/{so}" if so else None

        if document_type == "Portal Delivery Inspection":
            r = frappe.db.get_value(
                "Portal Delivery Inspection", document_name,
                ["customer", "delivery_note"], as_dict=True,
            )
            # `not r` gộp cả "biên bản không còn tồn tại" lẫn "của khách
            # khác" — cùng khuôn nhánh Customer Stock Receipt bên dưới.
            if not r or r.customer != customer:
                return None
            return f"/kiem-hang/{r.delivery_note}"

        if document_type == "Customer Stock Receipt":
            kho = frappe.db.get_value("Customer Stock Receipt", document_name, "kho")
            # `not kho` gộp CẢ HAI: chứng từ không tồn tại (ví dụ phiếu nháp
            # đã bị `delivery_hook._huy_theo_delivery_note` xoá hẳn khi DN bị
            # huỷ — Notification Log trỏ tới một `document_name` không còn
            # nữa) VÀ chứng từ tồn tại nhưng không thuộc kho của khách này.
            kho_customer = frappe.db.get_value("Customer Warehouse", kho, "customer") if kho else None
            if not kho or kho_customer != customer:
                return None
            return f"/kho/nhap/{document_name}"
    except Exception:
        return None
    return None


def _customer_phien_hien_tai() -> str | None:
    """`get_portal_customer()` nhưng KHÔNG ném lỗi — trang Thông báo vẫn
    phải chạy được (chỉ mất khả năng suy link) cho một tài khoản lỗi cấu
    hình (chưa gắn Customer nào), thay vì 500 cả trang."""
    try:
        return get_portal_customer()
    except frappe.PermissionError:
        return None


def _pham_vi_phien_hien_tai() -> dict | None:
    """`pham_vi_don()` nhưng KHÔNG ném lỗi. Trả về MỘT TRONG BA, và người
    gọi PHẢI phân biệt cả ba (không được gộp bằng `if not pham_vi`):

    - `{}` — Quản lý, KHÔNG giới hạn theo khoa.
    - `{"custom_khoa_phong": ...}` — Nhân viên khoa, giới hạn đúng khoa đó.
    - `None` — KHÔNG xác định được phạm vi. Gồm cả tài khoản lỗi cấu hình
      (chưa gắn `Portal Member` nào) LẪN — quan trọng hơn — một Nhân viên
      khoa `active=1` CHƯA gán khoa, đúng ca `pham_vi_don()` cố ý fail-closed
      (`portal_context.py`, docstring "VÒNG SỬA 3").

    VÒNG SỬA 1 (review độc lập, I2 — Important): bản trước bắt
    `PermissionError` rồi trả `{}` — LẬT NGƯỢC fail-closed thành fail-open
    ĐÚNG Ở CA `pham_vi_don()` tồn tại để chặn. `None` khác `{}`: `bool(None)`
    và `bool({})` đều `False` trong Python — `if not pham_vi:` gộp nhầm hai
    ca này làm một chính là lỗi cũ, `_thong_bao_trong_pham_vi` bên dưới PHẢI
    kiểm `is None` tường minh."""
    try:
        return pham_vi_don()
    except frappe.PermissionError:
        return None


# `_lien_ket_thong_bao`/`dam_bao_xem_duoc` biết quy đúng bốn doctype này về
# đơn cha (Quotation mang thẳng `custom_khoa_phong`, spec 2026-10-12 §8).
# `Customer Stock Receipt`/`Portal Delivery Inspection` KHÔNG có mặt ở đây —
# CỐ Ý: kho là tài sản của CẢ bệnh viện, không thuộc riêng khoa
# nào (`Customer Warehouse` không gắn khoa phòng, xem thiết kế "kho khách
# hàng"), nên một thông báo "đã nhập hàng" là thông tin cấp bệnh viện, cùng
# hạng với `portal_catalog_gop` — lọc nó theo khoa sẽ là lỗi, không phải một chỗ
# quên áp phạm vi.
_THONG_BAO_DOCTYPE_LOC_KHOA = ("Sales Order", "Delivery Note", "Sales Invoice", "Quotation")


def _thong_bao_trong_pham_vi(document_type, document_name, pham_vi: dict | None) -> bool:
    """`False` = ẨN CẢ DÒNG thông báo, không chỉ null hoá `link`.

    `_lien_ket_thong_bao` chỉ null `link` khi không sở hữu chứng từ đích —
    đủ để chặn NAVIGATE nhưng `subject` (vd. "Portal - Đơn mới: SAL-ORD-...")
    vẫn mang thẳng tên chứng từ ra ngoài. Với cách ly THEO KHOA, riêng
    `subject` đã là rò rỉ (một nhân viên khoa B đọc được "khoa A vừa có đơn
    SAL-ORD-2026-00099" dù không bấm vào xem được) — nên hàm này ẩn hẳn dòng
    thay vì chỉ tắt nút đi tới.

    `pham_vi is None` — VÒNG SỬA 1 (I2) — PHẢI kiểm TRƯỚC `not pham_vi`:
    `None` (không xác định được phạm vi, xem `_pham_vi_phien_hien_tai`) và
    `{}` (Quản lý, không giới hạn) đều `falsy` như nhau trong Python nhưng
    mang Ý NGHĨA NGƯỢC NHAU — gộp chúng bằng `if not pham_vi: return True`
    (bản trước) chính là lỗi lật fail-closed thành fail-open.

    Biết fan-out lúc TẠO thông báo (`portal_thong_bao_khach._portal_users_
    cua_khach`) hiện gửi cho MỌI thành viên đang active của khách hàng, chưa
    lọc theo khoa (docstring hàm đó tự ghi nhận, để dành việc đó cho phần mở
    rộng khác).

    SỬA (fix-wave 2026-08-18, V1 — CRITICAL): bản trước khẳng định "lọc Ở
    ĐÂY (đường đọc) vẫn đạt đúng mục tiêu cách ly" — SAI, và sai đúng loại
    "docstring hứa một tính chất an toàn mà mã không có" mà chính đề án này
    đã xếp Critical (xem C4 — `_loc_qua_don_cha`). Hàm này chỉ chặn ĐÚNG
    MỘT đường đọc: `portal_thong_bao_list`/`portal_thong_bao_doc`. `Notification
    Log` có DocPerm `read/report/export` cho role `All` (core), không phải
    bảng con nên `rest_guard`/`search_guard` không chặn — `frappe.get_list`/
    `frappe.client.get_value` gọi thẳng vẫn đi qua, BỎ QUA hàm này hoàn
    toàn. Ranh giới an ninh THẬT cho `Notification Log`, kể cả với nhân
    viên khoa gọi ngoài hai endpoint này, là hook `permission_query_
    conditions` (`permissions.notification_khoa_query`, đăng ký trong
    `hooks.py`) — hàm NÀY chỉ là một lớp ẨN THÊM (ẩn cả dòng thay vì chỉ
    null `link`) cho riêng hai màn Thông báo, không phải nguồn sự thật duy
    nhất."""
    if document_type not in _THONG_BAO_DOCTYPE_LOC_KHOA or not document_name:
        return True
    if pham_vi is None:
        # Fail-closed — không xác định được phạm vi thì KHÔNG được coi là
        # "Quản lý, thấy hết".
        return False
    if not pham_vi:
        return True
    try:
        # `pham_vi=pham_vi` — dùng LẠI giá trị đã tính MỘT LẦN cho cả trang
        # (không hỏi `pham_vi_don()` lại mỗi dòng thông báo).
        dam_bao_xem_duoc(document_type, document_name, pham_vi=pham_vi)
        return True
    except frappe.PermissionError:
        return False


@frappe.whitelist()
def portal_thong_bao_list(start=0, limit=20) -> dict:
    """Danh sách thông báo của CHÍNH khách đang đăng nhập + số chưa đọc cho
    badge nav. Lọc `for_user = frappe.session.user` — KHÔNG nhận user/
    customer từ client."""
    user = frappe.session.user
    start = frappe.utils.cint(start)
    limit = min(frappe.utils.cint(limit) or 20, 100)

    rows = frappe.get_all(
        "Notification Log",
        filters={"for_user": user},
        fields=[
            "name", "subject", "email_content", "document_type",
            "document_name", "read", "creation",
        ],
        order_by="creation desc",
        limit_start=start,
        limit_page_length=limit,
    )
    chua_doc = frappe.db.count("Notification Log", {"for_user": user, "read": 0})

    customer = _customer_phien_hien_tai()
    pham_vi = _pham_vi_phien_hien_tai()
    items = [
        {
            "name": r.name,
            "subject": r.subject,
            "noi_dung": r.email_content,
            "doc_type": r.document_type,
            "doc_name": r.document_name,
            "da_doc": bool(r.read),
            "ngay": r.creation,
            "link": _lien_ket_thong_bao(r.document_type, r.document_name, customer),
        }
        for r in rows
        if _thong_bao_trong_pham_vi(r.document_type, r.document_name, pham_vi)
    ]
    # `chua_doc` (badge nav) CỐ Ý chưa lọc theo khoa — đây là một CON SỐ,
    # không phải nội dung chứng từ; thu hẹp nó đòi kiểm dam_bao_xem_duoc trên
    # MỌI thông báo chưa đọc của user (không chỉ trang đang xem), một chi phí
    # không tương xứng với rủi ro (một con số badge, không phải tên/mã chứng
    # từ). Ghi nhận là giới hạn đã biết, không phải bị bỏ sót.
    return {"items": items, "chua_doc": chua_doc}


@frappe.whitelist()
def portal_thong_bao_doc(name) -> dict:
    """Bấm MỘT thông báo: kiểm sở hữu (chỉ đọc được thông báo CỦA CHÍNH
    mình — lọc `for_user` NGAY TRONG truy vấn, không load rồi kiểm sau),
    suy link (tự kiểm sở hữu chứng từ đích — xem `_lien_ket_thong_bao`), rồi
    đánh dấu đã đọc. KHÔNG nhận user từ client."""
    user = frappe.session.user
    log = frappe.db.get_value(
        "Notification Log",
        {"name": name, "for_user": user},
        ["name", "subject", "email_content", "document_type", "document_name", "read"],
        as_dict=True,
    )
    if not log:
        # Không tồn tại HOẶC thuộc `for_user` khác — cùng một câu trả lời để
        # không lộ ra sự khác biệt giữa hai trường hợp đó.
        raise frappe.PermissionError("Không tìm thấy thông báo.")

    pham_vi = _pham_vi_phien_hien_tai()
    if not _thong_bao_trong_pham_vi(log.document_type, log.document_name, pham_vi):
        # CÙNG thông điệp với "không tồn tại"/"thuộc user khác" ở trên —
        # nguyên tắc constraint #1: không phân biệt lý do để khỏi lộ sự tồn
        # tại của chứng từ đích.
        raise frappe.PermissionError("Không tìm thấy thông báo.")

    customer = _customer_phien_hien_tai()
    link = _lien_ket_thong_bao(log.document_type, log.document_name, customer)

    if not log.read:
        frappe.db.set_value("Notification Log", name, "read", 1, update_modified=False)

    return {
        "name": log.name,
        "subject": log.subject,
        "noi_dung": log.email_content,
        "doc_type": log.document_type,
        "doc_name": log.document_name,
        "link": link,
    }


# ------------------------------------------------------------ kiểm hàng (E9)
# Thiết kế: docs/superpowers/specs/2026-08-16-kiem-hang-tra-hang-hong-design.md
#
# Ba endpoint dưới đây KHÔNG nhận `customer` từ client — suy từ phiên, rồi đối
# chiếu với `customer` của CHÍNH Delivery Note đang được kiểm. `Portal Delivery
# Inspection` không có DocPerm nào cho role `Customer` (Quyết định #7), nên mọi
# thao tác đi qua đây với `ignore_permissions` sau khi đã tự kiểm sở hữu.


def _dn_kiem_hang_cua_khach(delivery_note: str, customer: str) -> frappe._dict:
    """Nạp phiếu giao và chứng minh nó thuộc khách đang đăng nhập.

    Kiểm CẢ `docstatus == 1`: một phiếu giao còn nháp thì hàng chưa rời kho
    Miyano, không có gì để kiểm; một phiếu đã huỷ thì đợt giao đó không tồn
    tại nữa. Cho lập biên bản trên hai loại đó sẽ sinh ra chứng từ khiếu nại
    về một lần giao hàng chưa/không hề xảy ra.
    """
    dam_bao_xem_duoc("Delivery Note", delivery_note)
    dn = frappe.db.get_value(
        "Delivery Note", delivery_note,
        ["name", "customer", "docstatus", *COT_THOI_GIAN_GIAO], as_dict=True,
    )
    if not dn or dn.customer != customer:
        # Gộp "không tồn tại" và "của khách khác" vào một câu trả lời — không
        # để người gọi dò được sự tồn tại của chứng từ khách khác.
        raise frappe.PermissionError("Phiếu giao này không thuộc đơn vị của bạn.")
    if dn.docstatus != 1:
        frappe.throw(
            "Phiếu giao này chưa được ghi sổ hoặc đã huỷ.", frappe.ValidationError
        )
    return dn


def _ngay_giao_cua_dn(dn):
    """Ngày giao hiện trên màn kiểm hàng — CÙNG nguồn với khối "Giao hàng"
    của màn đơn (`thoi_gian_giao_cua_dn`), để hai màn nói về một đợt giao
    không ra hai ngày."""
    thoi_gian = thoi_gian_giao_cua_dn(dn)
    return thoi_gian.date() if thoi_gian else None


@frappe.whitelist()
def portal_kiem_hang_get(delivery_note) -> dict:
    """Mở màn kiểm hàng: trả biên bản đã có, hoặc một biên bản TRỐNG dựng sẵn
    từ dòng hàng của phiếu giao (chưa lưu gì)."""
    customer = get_portal_customer()
    dn = _dn_kiem_hang_cua_khach(delivery_note, customer)

    # `dong_goc` — dòng dựng lại từ CHÍNH phiếu giao, luôn đi kèm. Sau một
    # lần bị từ chối, client cần một bộ dòng trắng để khách gõ lại mà không
    # phải gọi thêm một vòng API nữa.
    dong_goc = [{**d, "sl_thieu": 0.0} for d in dong_tu_delivery_note(delivery_note)]

    bien_ban = bien_ban_cua_dn(delivery_note)
    if bien_ban:
        return {"delivery_note": delivery_note, "ngay_giao": _ngay_giao_cua_dn(dn),
                "bien_ban": bien_ban, "dong_goc": dong_goc, "moi": False}
    return {
        "delivery_note": delivery_note,
        "ngay_giao": _ngay_giao_cua_dn(dn),
        "moi": True,
        "dong_goc": dong_goc,
        "bien_ban": {
            "name": None,
            "delivery_note": delivery_note,
            "trang_thai": "Nháp",
            "da_gui": False,
            "co_the_gui_lai": False,
            "co_hang_hong": False,
            "ly_do_tu_choi": None,
            "phieu_tra_hang": None,
            "ghi_chu": "",
            "items": list(dong_goc),
        },
    }


def _ap_dong_tu_client(doc, dong, delivery_note: str) -> None:
    """Ghi số liệu khách gửi lên vào `doc.items`.

    Dòng và mốc `sl_giao` LUÔN dựng lại từ chính Delivery Note, KHÔNG lấy từ
    payload: `sl_giao` là mốc đối chiếu: nhận nó từ client tức là để khách tự
    khai mình được giao bao nhiêu, và mọi ràng buộc "không nhận thừa" trong
    controller sẽ so với một con số do chính bên bị ràng buộc cung cấp. Client
    chỉ được đóng góp ba giá trị: `sl_nhan`, `sl_tra`, `ly_do`.
    """
    gui = {}
    for d in (dong or []):
        ma = (d.get("item_code") or "").strip()
        if ma:
            gui[ma] = d

    doc.items = []
    for goc in dong_tu_delivery_note(delivery_note):
        d = gui.get(goc["item_code"], {})
        doc.append("items", {
            "item_code": goc["item_code"],
            "item_name": goc["item_name"],
            "uom": goc["uom"],
            "sl_giao": goc["sl_giao"],
            "sl_nhan": frappe.utils.flt(d.get("sl_nhan", goc["sl_giao"])),
            "sl_tra": frappe.utils.flt(d.get("sl_tra", 0)),
            "ly_do": (d.get("ly_do") or "").strip()[:140],
        })


def _bien_ban_sua_duoc(delivery_note: str):
    """Bản nháp còn sửa được của phiếu giao này, hoặc None."""
    ten = frappe.db.get_value(
        "Portal Delivery Inspection",
        {"delivery_note": delivery_note, "docstatus": 0}, "name",
    )
    return frappe.get_doc("Portal Delivery Inspection", ten) if ten else None


def _chan_da_gui(delivery_note: str) -> None:
    """Đã gửi thì không sửa nữa — TRỪ bản bị Miyano từ chối.

    Bản từ chối vẫn là `docstatus=1`; không loại nó ra ở đây thì khách bị từ
    chối xong hết đường đi (spec §4.3 hứa ngược lại) — họ đọc "Liên hệ Miyano
    nếu cần chỉnh sửa" trên một màn khoá cứng.
    """
    da_gui = frappe.db.get_value(
        "Portal Delivery Inspection",
        # Hằng số, KHÔNG chuỗi viết tay: controller lọc cùng trạng thái này
        # bằng `TT_TU_CHOI`, hai bản chuỗi rời nhau là một chỗ trôi âm thầm
        # ngay lần đầu ai đó đổi tên trạng thái.
        {"delivery_note": delivery_note, "docstatus": 1,
         "trang_thai": ["!=", TT_TU_CHOI]},
        "name",
    )
    if da_gui:
        frappe.throw(
            f"Phiếu giao này đã có biên bản {da_gui} đã gửi. Liên hệ Miyano "
            "nếu cần chỉnh sửa.",
            frappe.ValidationError,
        )


@frappe.whitelist()
def portal_kiem_hang_luu(delivery_note, dong, ghi_chu=None) -> dict:
    """Lưu nháp — khách kiểm dở, đóng máy, mở lại vẫn còn."""
    customer = get_portal_customer()
    _dn_kiem_hang_cua_khach(delivery_note, customer)
    _chan_da_gui(delivery_note)
    if isinstance(dong, str):
        dong = frappe.parse_json(dong)

    doc = _bien_ban_sua_duoc(delivery_note)
    if not doc:
        doc = frappe.new_doc("Portal Delivery Inspection")
        doc.customer = customer
        doc.delivery_note = delivery_note
        doc.sales_order = frappe.db.get_value(
            "Delivery Note Item",
            {"parent": delivery_note, "against_sales_order": ["is", "set"]},
            "against_sales_order",
        )
    doc.ngay_kiem = frappe.utils.nowdate()
    doc.nguoi_kiem = frappe.session.user
    doc.trang_thai = "Nháp"
    doc.ghi_chu = (ghi_chu or "").strip()[:500]
    _ap_dong_tu_client(doc, dong, delivery_note)
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def portal_kiem_hang_gui(delivery_note, dong, ghi_chu=None) -> dict:
    """Gửi biên bản cho Miyano (submit).

    Lưu rồi submit trong CÙNG một lời gọi — không tin vào một bản nháp đã lưu
    từ trước: khách có thể mở hai tab, và bản nháp trên server có thể cũ hơn
    những gì họ đang nhìn thấy lúc bấm Gửi.
    """
    ket_qua = portal_kiem_hang_luu(delivery_note, dong, ghi_chu)
    doc = frappe.get_doc("Portal Delivery Inspection", ket_qua["name"])
    # Role `Customer` KHÔNG có DocPerm nào trên doctype này (Quyết định #7) —
    # cổng là chính endpoint này, đã tự kiểm sở hữu phiếu giao ở
    # `_dn_kiem_hang_cua_khach`. Không có cờ này thì `submit()` ném PermissionError cho
    # đúng người được phép gửi.
    doc.flags.ignore_permissions = True
    doc.submit()
    return {
        "name": doc.name,
        "trang_thai": doc.trang_thai,
        "co_hang_hong": bool(doc.co_hang_hong),
    }


# ------------------------------------------------- nhật ký thao tác (Task 5)
# Thiết kế: docs/superpowers/specs/2026-09-03-nhat-ky-thao-tac-va-timeline-design.md


@frappe.whitelist()
def portal_nhat_ky_yeu_cau(de_xuat=None, order=None) -> list[dict]:
    """Đọc sổ nhật ký (`miyano_portal.nhat_ky`) của MỘT yêu cầu, cho khối
    "Truy vết yêu cầu" và dòng thời gian dọc (spec §9/§10).

    KHÔNG tự chế bộ lọc — gọi lại đúng hai chốt phần còn lại của cổng đang
    gọi: `_phieu_cua_toi(de_xuat, cho_quan_ly=True)` cho phiếu (kiểm CẢ trục
    khách hàng LẪN trục khoa, và `cho_quan_ly=True` vì đồng nghiệp cùng khoa
    — không riêng quản lý — cũng phải đọc được nhật ký), `dam_bao_xem_duoc()`
    cộng `so.check_permission("read")` cho đơn — đúng khuôn `portal_order_
    track` đã dùng: `dam_bao_xem_duoc` chỉ kiểm trục KHOA (tự no-op cho Quản
    lý), trục KHÁCH HÀNG vẫn phải dựa vào `check_permission("read")` (đi qua
    hook `sales_has_permission`, xem docstring `dam_bao_xem_duoc`).

    Lấy dòng theo CẢ HAI khoá (`de_xuat` lẫn `sales_order`) của chứng từ ĐÃ
    QUA CỬA — một yêu cầu có cả phiếu lẫn đơn thì nhật ký nằm rải ở cả hai
    (phiếu mang các sự kiện `khoa_*`/`quan_ly_*`, đơn mang `miyano_*`/
    `khach_*`/`giao_hang`/`hoa_don`), và bỏ sót một khoá là bỏ sót nửa câu
    chuyện. Không kiểm quyền THÊM một lần cho khoá còn lại — LẬP LUẬN (không
    phải điều đã tự đo ở đây): đơn suy từ phiếu qua `custom_de_xuat` (hoặc
    ngược lại) được TẠO RA từ đúng `customer`/`khoa_phong` của phiếu đó
    (`de_xuat_duyet.duyet_va_tao_don`/`_dam_bao_phieu_tu_duyet`), nên tự nó
    không phải một chứng từ THỨ HAI cần soát riêng — miễn là không có đường
    nào khác (vd sửa tay trên Desk) tách `custom_de_xuat` khỏi phiếu gốc của
    nó sau khi tạo; điều đó nằm ngoài phạm vi kiểm chứng của task này.
    """
    # Việc #6a (vòng sửa sau review toàn nhánh) — CẢ HAI nhánh dưới đây
    # chạm cột `Sales Order.custom_de_xuat` (patch v1_24) mà TRƯỚC bản vá
    # này không hỏi qua `_cot_de_xuat_ton_tai()` — đúng "bẫy patch hoàn
    # thành giả" mà docstring hàm đó cảnh (nguồn kiểm tra DUY NHẤT, không
    # tự hỏi cột rời ở nơi khác). Trên site chưa chạy patch v1_24, nhánh
    # `de_xuat` ném lỗi SQL 1054 THÔ (WHERE trên cột không tồn tại) thay vì
    # fail-closed, và nhánh `order` (tuy `so.get()` an toàn về mặt kỹ thuật
    # — Document.get() trả None cho field không có trong bản ghi đã nạp)
    # sẽ ÂM THẦM coi mọi đơn là "không có phiếu đứng trước", khác NHẤT
    # QUÁN với nhánh kia đang fail-closed.
    if de_xuat:
        doc = _phieu_cua_toi(de_xuat, cho_quan_ly=True)
        ten_de_xuat = doc.name
        ten_don = None
        if _cot_de_xuat_ton_tai():
            ten_don = frappe.db.get_value(
                "Sales Order", {"custom_de_xuat": ten_de_xuat}, "name"
            )
    elif order:
        dam_bao_xem_duoc("Sales Order", order)
        so = frappe.get_doc("Sales Order", order)
        so.check_permission("read")
        ten_don = so.name
        ten_de_xuat = so.get("custom_de_xuat") if _cot_de_xuat_ton_tai() else None
        doc = frappe.get_doc("Portal De Xuat Mua", ten_de_xuat) if ten_de_xuat else None
    else:
        frappe.throw("Cần truyền de_xuat hoặc order.", frappe.ValidationError)

    from miyano_portal import nhat_ky

    dieu_kien = []
    if ten_de_xuat:
        dieu_kien.append(["de_xuat", "=", ten_de_xuat])
    if ten_don:
        dieu_kien.append(["sales_order", "=", ten_don])
    hang = frappe.get_all(
        nhat_ky.DOCTYPE,
        or_filters=dieu_kien,
        fields=["su_kien", "thoi_diem", "vai", "nguoi_thao_tac", "ghi_chu"],
        order_by="thoi_diem asc",
    )

    def _dong(su_kien, thoi_diem, vai, nguoi, ghi_chu, suy_ra):
        # `vai == miyano` KHÔNG BAO GIỜ trả email — ranh giới §8, xem
        # docstring `lien_he_nguoi_dung`. Mọi vai khác giữ hành vi cũ (tên +
        # email khi hai giá trị khác nhau).
        return {
            "su_kien": su_kien,
            "thoi_diem": thoi_diem,
            "vai": vai,
            **lien_he_nguoi_dung(nguoi, cho_hien_tai_khoan=vai != nhat_ky.VAI_MIYANO),
            "ghi_chu": ghi_chu,
            "suy_ra": suy_ra,
        }

    ket_qua = [
        _dong(r.su_kien, r.thoi_diem, r.vai, r.nguoi_thao_tac, r.ghi_chu, False)
        for r in hang
    ]

    # Bước 5 (§9.6) — suy hai dòng cho chứng từ TẠO TRƯỚC khi bật nhật ký.
    # `nguoi_yeu_cau`/`nguoi_duyet`/`thoi_diem_gui`/`thoi_diem_duyet` là BỐN
    # trường đã ghi tường minh trên CHÍNH phiếu, có người và có mốc giờ — chỉ
    # nằm trên chứng từ thay vì trong sổ, KHÔNG phải một suy diễn kiểu
    # `Version` mà spec §4 đã bác. CHỈ chèn khi KHÔNG có dòng thật cùng loại
    # — chèn cả hai vô điều kiện sẽ hiện đôi cho MỌI yêu cầu mới (xem
    # `test_yeu_cau_MOI_khong_bi_hien_doi`).
    if doc is not None:
        su_kien_that = {r.su_kien for r in hang}
        if nhat_ky.SK_KHOA_GUI_DUYET not in su_kien_that and doc.thoi_diem_gui:
            # `nguoi_yeu_cau or owner` — CÙNG phép suy `de_xuat_chi_tiet`
            # (`api/de_xuat.py`) đã dùng: không đường mã nào trong app ghi
            # `nguoi_yeu_cau` cho phiếu lập qua giao diện thật, nên `owner`
            # mới là người đề nghị thật. Chép lại đúng biểu thức đó ở đây,
            # không tự dựng một phép suy thứ hai rồi trôi lệch.
            #
            # `ghi_chu` = LÝ DO YÊU CẦU (06/09/2026). Trước bản này hai dòng
            # suy ra truyền `None`, và điều đó chấp nhận được chừng nào khối
            # "Yêu cầu & duyệt" còn đứng cạnh để hiện lý do. Khối đó nay đã
            # bỏ (dòng thời gian đảm đương hết), nên nếu vẫn để `None` thì
            # ĐƠN CŨ mất hẳn lý do yêu cầu — không chỗ nào khác trên màn
            # còn hiện nó.
            ket_qua.append(_dong(
                nhat_ky.SK_KHOA_GUI_DUYET, doc.thoi_diem_gui, nhat_ky.VAI_KHOA,
                doc.nguoi_yeu_cau or doc.owner,
                (doc.get("ly_do_yeu_cau") or "").strip() or None, True,
            ))
        if nhat_ky.SK_QUAN_LY_DUYET not in su_kien_that and doc.thoi_diem_duyet:
            # `ghi_chu` = TƯ CÁCH DUYỆT, cùng lý do trên. Khuôn chữ giữ
            # ĐÚNG như dòng thật (`PortalDeXuatMua.duyet`) ghi ra, để hai
            # loại dòng đọc giống nhau — người xem không phải học hai cách
            # diễn đạt cho cùng một sự việc.
            tu_cach = (doc.get("duyet_voi_tu_cach") or "").strip()
            ket_qua.append(_dong(
                nhat_ky.SK_QUAN_LY_DUYET, doc.thoi_diem_duyet, nhat_ky.VAI_QUAN_LY,
                doc.nguoi_duyet, f"Tư cách: {tu_cach}" if tu_cach else None, True,
            ))
        ket_qua.sort(key=lambda d: d["thoi_diem"])

    return ket_qua
