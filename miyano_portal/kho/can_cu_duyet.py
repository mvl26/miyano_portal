"""CR-04 — căn cứ tồn kho đặt ngay cạnh dòng hàng khi quản lý duyệt đơn.

Quản lý duyệt phải trả lời đúng một câu: *"số lượng nhân viên đề nghị có hợp
lý không?"*. Trước CR này họ không có căn cứ nào ngoài kinh nghiệm.

ĐẶT Ở `kho/` CHỨ KHÔNG Ở `api/portal.py`: đây là phép tính của kho (tồn, sổ
kho, mức dùng), và `portal.py` đã quá dài. `portal_order_track` chỉ gọi vào
đây và gắn kết quả vào từng dòng hàng.

BA RÀNG BUỘC, cả ba đều là ràng buộc chứ không phải sở thích:

1. **KHÔNG dùng `get_portal_kho()`.** Hàm đó NÉM `PermissionError` khi khách
   chưa mở kho — và 1/6 khách hiện tại đúng như vậy. Gọi nó ở đây là làm
   chết màn chi tiết đơn của riêng nhóm bệnh viện đó, một lỗi chỉ lộ ra với
   đúng những người ít có tiếng nói nhất. Hỏi thẳng `Customer Warehouse`,
   đúng tiền lệ `portal_order_track` đã dùng cho `kho`.

2. **Không tra được thì trả `None`, KHÔNG trả 0.** "Tồn 0" nghĩa là HẾT
   HÀNG. "Không biết" là chuyện khác hẳn. Quản lý đọc nhầm hai thứ đó sẽ
   duyệt một đơn vì tưởng kho trống, trong khi hệ thống chỉ đơn giản không
   tra được — đúng thứ CR-04 sinh ra để dẹp, quay lại dưới dạng tinh vi hơn.

3. **Hỏng thì mất con số, không mất cả trang.** Cùng nguyên tắc
   `delivery_hook._chay_an_toan` và `dn_co_hoa_don_nhap`.

KHÔNG viết lại phép cộng lô: `reports.ton_hien_tai_rows()` là nơi duy nhất
gộp tồn theo lô, đã dùng chung bởi cổng lẫn desk.
"""

import frappe

from miyano_portal.kho import reports

# Ngưỡng màu chấm và cờ ⚠, ĐẶT MỘT CHỖ có tên để đổi được mà không phải đi
# tìm số rải rác. Đơn vị: ngày còn dùng được.
NGUONG_DO = 7
NGUONG_VANG = 14
NGUONG_DAT_KHI_CHUA_CAN = 30

# Kỳ trượt tính mức dùng bình quân — 12 tuần, đúng bản vẽ chủ đầu tư.
SO_NGAY_ADU = 84


def muc_ton_tru(con_dung_duoc) -> str | None:
    """Màu chấm suy từ SỐ NGÀY CÒN DÙNG ĐƯỢC, không từ `ton_toi_thieu`.

    Bản vẽ gốc chấm màu theo `tồn ≤ Min`, nhưng 0/22 vật tư kho đã khai Min
    (đo 05/09/2026) — một ngưỡng không ai điền thì màu không bao giờ sáng.
    Số ngày còn dùng được tự tính từ sổ kho, không cần ai nhập liệu.

    `None` -> KHÔNG chấm màu. Trả "do" cho ca không biết là nói với quản lý
    "sắp hết" trong khi thật ra không ai biết gì — sai nguy hiểm hơn im lặng.
    """
    if con_dung_duoc is None:
        return None
    if con_dung_duoc <= NGUONG_DO:
        return "do"
    if con_dung_duoc <= NGUONG_VANG:
        return "vang"
    return "xanh"


def co_canh_bao(con_dung_duoc, nv_dat) -> bool:
    """⚠ "đặt khi chưa cần" — còn dùng được lâu mà nhân viên vẫn đặt.

    Bản vẽ gốc định nghĩa ⚠ là *"NV đặt lệch đáng kể so với đề xuất"*, mà
    "đề xuất" cần `ton_toi_da` — không có. Nhưng CHÍNH DỮ LIỆU trong bản vẽ
    đã khớp cách tính này: hai dòng ⚠ là hai dòng còn dùng lâu nhất (40 và
    100 ngày), hai dòng ✓ là hai dòng sắp hết (5 và 9 ngày).

    KHÔNG gắn cờ khi hàng sắp hết: đặt lúc sắp hết là việc ĐÚNG, gắn cờ vào
    đó là dạy quản lý bỏ qua cờ.
    """
    if con_dung_duoc is None or not nv_dat:
        return False
    return con_dung_duoc >= NGUONG_DAT_KHI_CHUA_CAN


def con_dung_duoc(ton, dang_ve, adu):
    """`(Tồn + Đang về) ÷ ADU`, đơn vị ngày.

    ADU bằng 0 hoặc chưa biết -> `None`, KHÔNG chia. Một số vô cực không nói
    được gì với người đọc, và chia cho 0 thì nổ.
    """
    if ton is None or not adu:
        return None
    return (float(ton) + float(dang_ve or 0)) / float(adu)


def _kho_cua_khach(customer: str) -> str | None:
    """Kho đang hoạt động của khách, hoặc `None`.

    KHÔNG `get_portal_kho()` — xem ràng buộc 1 ở docstring module.
    """
    return frappe.db.get_value(
        "Customer Warehouse", {"customer": customer, "active": 1}, "name"
    )


def _adu_theo_vat_tu(kho: str, ten_vat_tu: list) -> dict:
    """Mức dùng bình quân mỗi ngày, kỳ trượt `SO_NGAY_ADU`.

    CHỈ đếm dòng XUẤT (`so_luong < 0`). Dòng nhập không phải mức dùng, và
    cộng cả hai vào rồi chia là ra một con số không mang nghĩa gì.

    Vật tư không có dòng xuất nào trong kỳ KHÔNG có mặt trong dict trả về —
    khác hẳn với "ADU = 0". Người gọi phân biệt hai ca đó.
    """
    if not ten_vat_tu:
        return {}
    tu_ngay = frappe.utils.add_days(frappe.utils.nowdate(), -SO_NGAY_ADU)
    dong = frappe.get_all(
        "Customer Stock Ledger Entry",
        filters={"kho": kho, "vat_tu": ["in", ten_vat_tu],
                 "so_luong": ["<", 0], "ngay": [">=", tu_ngay]},
        fields=["vat_tu", "sum(so_luong) as tong"],
        group_by="vat_tu",
    )
    return {
        d.vat_tu: abs(float(d.tong or 0)) / SO_NGAY_ADU
        for d in dong
        if d.tong
    }


def _dang_ve_theo_item(customer: str, tru_don: str, item_codes: list) -> dict:
    """*Đã đặt nhưng chưa NHẬP KHO* (chủ đầu tư chốt nguyên văn).

        Đang về = Σ (đã đặt trên các đơn CÒN HIỆU LỰC)
                − Σ (đã nhập kho TỪ CHÍNH các đơn đó)

    CỐ Ý rộng hơn `qty − delivered_qty` mà bản vẽ ghi. Chênh lệch nằm ở
    khoảng **đã giao nhưng chưa vào sổ kho**: phiếu nhập tự sinh hỏng (bị
    `_chay_an_toan` nuốt, chỉ để lại một dòng Error Log), phiếu giao lùi ngày
    trước `ngay_bat_dau` của kho, hoặc kiểm hàng trả lại một phần. Trong mọi
    ca đó hàng CHƯA nằm trên kệ bệnh viện — đúng nghĩa "đang về".

    `tru_don` — đơn ĐANG DUYỆT không tính vào. Nếu tính, con số này cộng
    trùng với cột "NV đặt" ngay cạnh, và quản lý đọc ra "hàng sắp về rồi"
    cho chính lô họ đang cân nhắc.
    """
    if not item_codes:
        return {}

    dat = frappe.get_all(
        "Sales Order Item",
        filters={
            "item_code": ["in", item_codes],
            "docstatus": 1,
            "parent": ["!=", tru_don or ""],
        },
        fields=["parent", "item_code", "qty"],
    )
    if not dat:
        return {}

    ten_don = list({d.parent for d in dat})
    con_hieu_luc = {
        r.name
        for r in frappe.get_all(
            "Sales Order",
            filters={"name": ["in", ten_don], "customer": customer,
                     "docstatus": 1, "status": ["not in", ("Closed", "Completed")]},
            fields=["name"],
        )
    }
    if not con_hieu_luc:
        return {}

    tong = {}
    for d in dat:
        if d.parent in con_hieu_luc:
            tong[d.item_code] = tong.get(d.item_code, 0.0) + float(d.qty or 0)

    # Trừ phần ĐÃ NHẬP KHO từ chính các đơn đó. `Customer Stock Receipt` mang
    # `sales_order`, nên quy được về đơn — đó là điều làm cho định nghĩa
    # "chưa nhập kho" tính được, thay vì phải suy gián tiếp qua phiếu giao.
    da_nhap = frappe.get_all(
        "Customer Stock Receipt",
        filters={"sales_order": ["in", list(con_hieu_luc)], "docstatus": 1},
        fields=["name"],
    )
    if da_nhap:
        for d in frappe.get_all(
            "Customer Stock Receipt Item",
            filters={"parent": ["in", [x.name for x in da_nhap]]},
            fields=["vat_tu", "so_luong"],
        ):
            ma = frappe.db.get_value("Customer Warehouse Item", d.vat_tu, "item_code")
            if ma in tong:
                tong[ma] -= float(d.so_luong or 0)

    # Âm nghĩa là đã nhập nhiều hơn đã đặt (nhập bù, nhập nhầm đơn) — không
    # có "đang về" âm; kẹp về 0 chứ không trả một số âm khó hiểu ra màn hình.
    return {k: max(0.0, v) for k, v in tong.items()}


def can_cu_cho_don(so) -> dict:
    """Căn cứ tồn kho cho từng `item_code` của một đơn.

    Trả `{item_code: {ton, dang_ve, adu, con_dung_duoc, muc, vat_tu}}`.
    `vat_tu` để màn hình gọi thẳng `kho_the_kho` xổ sổ kho tại dòng — endpoint
    đó đã tự kiểm vật tư thuộc kho người gọi, không cần đường đọc thứ hai.

    Item không tra được (khách chưa mở kho, vật tư chưa nối `item_code`, hàng
    không có trong danh mục kho) KHÔNG có mặt trong dict — màn hình hiện gạch
    ngang. Xem ràng buộc 2 ở docstring module.
    """
    try:
        kho = _kho_cua_khach(so.customer)
        if not kho:
            return {}

        item_codes = [
            i.get("item_code") for i in (so.get("items") or []) if i.get("item_code")
        ]
        if not item_codes:
            return {}

        vat_tu_rows = frappe.get_all(
            "Customer Warehouse Item",
            filters={"kho": kho, "item_code": ["in", item_codes], "active": 1},
            fields=["name", "item_code"],
        )
        if not vat_tu_rows:
            return {}
        theo_item = {r.item_code: r.name for r in vat_tu_rows}
        ten_vat_tu = [r.name for r in vat_tu_rows]

        ton = {
            r["vat_tu"]: float(r.get("so_luong") or 0)
            for r in reports.ton_hien_tai_rows(kho)
            if r.get("vat_tu") in set(ten_vat_tu)
        }
        adu = _adu_theo_vat_tu(kho, ten_vat_tu)
        # ĐƠN CẦN LOẠI TRỪ — hàm này được gọi từ HAI nơi với HAI loại doc:
        #
        #   * `portal_order_track` truyền một `Sales Order`. Doctype đó không
        #     có field `sales_order`, nên rơi về `so.name` = chính nó. Đúng.
        #   * `de_xuat_chi_tiet` truyền một `Portal De Xuat Mua`. `so.name` ở
        #     đây là MÃ PHIẾU, không bao giờ khớp tên một Sales Order — nên
        #     đơn do chính phiếu đó sinh ra KHÔNG bị loại và số lượng của nó
        #     CỘNG TRÙNG vào "Đang về". Quản lý mở một phiếu đã duyệt sẽ thấy
        #     "đang về" gấp đôi thực tế và kết luận ngược hẳn: "hàng đang về
        #     nhiều rồi, lần sau bớt đặt".
        #
        # Hỏi `sales_order` TRƯỚC rồi mới rơi về `name` — một biểu thức phục
        # vụ đúng cả hai người gọi, thay vì bắt mỗi nơi tự nhớ truyền gì.
        dang_ve = _dang_ve_theo_item(
            so.customer, so.get("sales_order") or so.name, list(theo_item)
        )

        ket_qua = {}
        for ma, vt in theo_item.items():
            # Vật tư CÓ trong danh mục kho nhưng không còn lô nào -> tồn 0 là
            # sự thật ("hết hàng"), khác hẳn "không tra được".
            t = ton.get(vt, 0.0)
            dv = dang_ve.get(ma, 0.0)
            a = adu.get(vt)
            cdd = con_dung_duoc(t, dv, a)
            ket_qua[ma] = {
                "vat_tu": vt,
                "ton": t,
                "dang_ve": dv,
                "adu": a,
                "con_dung_duoc": cdd,
                "muc": muc_ton_tru(cdd),
            }
        return ket_qua
    except Exception:
        # Module kho hỏng thì MẤT CÁC CON SỐ, không mất cả màn duyệt.
        frappe.log_error(
            title=f"CR-04: không dựng được căn cứ tồn kho cho đơn {so.get('name')}"
        )
        return {}
