"""Đồng bộ đơn giá hợp đồng nguyên tắc sang Price List của khách.

**Hiện trạng (09/10/2026 — spec `docs/superpowers/specs/2026-10-09-gia-theo-
price-list-design.md`).** Chủ đầu tư chốt: cổng định giá theo MỘT nguồn —
Price List của khách (`bang_gia_khach.gia_bang_gia_nhieu`). Danh mục gộp,
phiếu đề xuất và dựng đơn không còn hỏi hợp đồng. Hợp đồng chỉ còn MỘT đường
tới giá: `dong_bo()` chép `Blanket Order Item.rate` vào Price List đó — lúc
trình ký (`tu_hdnt`, hook `Blanket Order.on_submit`) và trong các patch vá dữ
liệu (`v1_13`, `v1_26`, `v1_41`).

Vì sao vẫn cần đồng bộ: sales nhập giá MỘT lần trên hợp đồng rồi coi là xong;
không ai biết phải nhập lần hai vào bảng giá. Thiếu bước chép này thì hàng đã
ký giá vẫn hiện "chờ báo giá" trên cổng. Lỗi gốc (14/08/2026, `erptest.local`):
ba hợp đồng khai đủ `rate`, cả site có 0 dòng `Item Price`.

Ranh giới cố ý của `dong_bo()`:

- **Chỉ `Selling`.** Hợp đồng mua hàng của Miyano không dính bảng giá bán.
- **Hợp đồng đã hết hạn không ghi gì** — nó không có quyền đặt giá cho hôm nay.
- **`rate <= 0` là CHƯA khai giá, không phải "bán 0 đồng"** — bỏ qua, không
  dựng dòng giá 0 (bộ đọc bỏ qua dòng đó, còn sales nhìn bảng lại tưởng đã có).
- **Giá hợp đồng ĐÈ giá cũ** của chính mã đó trong bảng của khách.
- **Bảng đích luôn là bảng của RIÊNG khách** (§5.3, thay Ruling P32 và quy tắc
  "không tự chế bảng giá" của bản 14/08): khách chưa có bảng thì tạo, đang dùng
  chung thì tách (`bang_gia_khach.dam_bao_bang_gia_rieng`) rồi mới ghi. Trước
  09/10 hai ca đó bị TỪ CHỐI kèm `ly_do`.
- **Ghi qua bộ ghi chung** `bang_gia_khach.ghi_gia_vao_bang`, để dòng được sửa
  đúng là dòng bộ đọc trả về.
- **Nhiều hợp đồng cùng khai một mã**: `dong_bo_khach()` phân định bằng
  `nguon_gia_theo_ma_cho_khach()` (Ruling P30) — hết hạn sớm nhất thắng.

**Còn sót, chờ gỡ.** `gia_dong_hop_dong()` và `con_hieu_luc()` là phép tra
"hợp đồng trước, bảng giá sau" của QĐ-G12 (21/08/2026). Luồng đặt hàng mới
không gọi chúng; chúng còn sống chỉ vì các endpoint cũ chưa gỡ vẫn gọi:
`portal_contracts`, `portal_catalog`, `portal_catalog_ban_le`, `portal_reorder`
(`api/portal.py`) và `portal_mua_le._gop_hoac_them_dong_hang`. Gỡ các endpoint
đó thì xoá luôn hai hàm này.
"""

import frappe
from frappe import _
from frappe.utils import flt, format_date, getdate


THU_TU_PHAN_DINH = "to_date asc, name asc"


def con_hieu_luc(blanket_order: str) -> bool:
    """HĐNT đã trình ký VÀ hôm nay nằm trong khoảng hiệu lực.

    Ruling P31 (review vòng 1) — chốt này nằm ở ĐÂY, trong hàm dùng chung,
    KHÔNG ở từng nơi gọi: sáu nơi gọi là sáu chỗ có thể quên, và hai nơi đã
    quên thật (`portal_catalog` chỉ kiểm quyền sở hữu; `portal_reorder` tin
    thẳng `Sales Order.custom_hdnt` của đơn cũ). Hậu quả không phải lỗi kỹ
    thuật mà là một con số SAI hiện ra cho khách: giỏ "đặt lại đơn cũ" báo
    giá của một hợp đồng đã chết, rồi lúc xác nhận đơn lại mang giá khác.

    Cùng định nghĩa "còn hiệu lực" với `nguon_gia_theo_ma_cho_khach()`
    (BR-R7, Ruling P18): `docstatus == 1` — bản NHÁP là sales còn đang soạn,
    không được định giá cho ai. `from_date`/`to_date` để trống coi như không
    ràng buộc phía đó."""
    hd = frappe.db.get_value(
        "Blanket Order", blanket_order,
        ["docstatus", "from_date", "to_date"], as_dict=True,
    )
    if not hd or hd.docstatus != 1:
        return False
    hom_nay = getdate()
    if hd.from_date and getdate(hd.from_date) > hom_nay:
        return False
    if hd.to_date and getdate(hd.to_date) < hom_nay:
        return False
    return True


def gia_dong_hop_dong(item_code: str, blanket_order=None, price_list=None):
    """QĐ-G12 — đơn giá của MỘT DÒNG, tra theo đúng thứ tự đã chốt.

    HÀM DÙNG CHUNG DUY NHẤT cho mọi nơi cần giá của một dòng hợp đồng: dựng
    đơn (`dat_hang._xay_don`), đóng dấu giá lúc gửi duyệt
    (`PortalDeXuatMua._dong_dau_gia`) và so giá lúc duyệt
    (`de_xuat_duyet._kiem_gia_doi`). Mỗi nơi một phép tra riêng là từng ấy chỗ
    có thể lệch, và dự án này đã trả giá đúng cho lỗi đó ở `nguon_gia`/
    `blanket_order` (Ruling P28: kiểm hạn mức và dựng đơn mỗi bên tự suy hợp
    đồng, hai bên bất đồng ở hai trạng thái tới được).

    Thứ tự, dừng ở giá trị DƯƠNG đầu tiên:

      1. `Blanket Order Item.rate` của ĐÚNG hợp đồng dòng đó đã suy ra
         (`blanket_order`) — hợp đồng đã ký là nguồn sự thật;
      2. `Item Price` trong bảng giá của khách (`price_list`);
      3. Không có → trả `None`, người gọi báo thiếu giá.

    `rate <= 0` ở bước 1 là CHƯA KHAI GIÁ (không phải "bán 0 đồng") — cùng
    quy ước `dong_bo()` đã dùng ở dưới — nên rơi xuống bước 2.

    Bước 1 là chỗ DUY NHẤT lọc "phải dương". Bước 2 trả THẲNG giá trị đọc
    được, kể cả `0`, đúng như phép tra cũ (`dat_hang._gia_hien_hanh`, đã xoá)
    — mọi người gọi đều dùng `if not rate`, nên `0` và `None` cho cùng một
    kết cục ở cổng đặt hàng.

    `price_list` được phép `None` và phép kiểm nằm TRONG hàm này, không ở
    các nơi gọi: bước 1 KHÔNG cần bảng giá nào cả. Để phép kiểm ở ngoài
    (`... if price_list else None`, đúng dạng cả bốn nơi gọi đang viết trước
    Task 12) thì một khách chưa được gán `default_price_list` vẫn bị chặn
    "chưa có giá trong hợp đồng" dù hợp đồng khai giá đầy đủ — tức QĐ-G12
    chết ngay ở ca dễ gặp nhất.

    Ruling P31 (review vòng 1) — bước 1 chỉ chạy khi hợp đồng CÒN HIỆU LỰC
    (`con_hieu_luc()`). Hết hạn/chưa tới ngày/còn nháp thì bỏ qua bước 1 và
    rơi xuống bảng giá, không phải ném lỗi: người gọi vẫn có quyền hỏi giá
    của một dòng gắn với hợp đồng cũ, chỉ là hợp đồng đó không còn quyền trả
    lời.

    Nợ cũ, cố ý giữ nguyên: bước 2 chưa lọc `valid_from`/`valid_upto`, nhiều
    bản ghi thì lấy tuỳ ý.
    """
    if blanket_order and con_hieu_luc(blanket_order):
        rate = flt(frappe.db.get_value(
            "Blanket Order Item",
            {"parent": blanket_order, "item_code": item_code},
            "rate",
            # M-2 (review vòng 1) — TẤT ĐỊNH. Một hợp đồng liệt kê trùng
            # `item_code` hai dòng thì `get_value` với filter dict lấy TUỲ Ý
            # một dòng; trước Task 12 điều đó chỉ ảnh hưởng phép chọn hạn
            # mức, giờ nó chọn GIÁ. Dòng đứng TRƯỚC trên chứng từ thắng —
            # quy tắc đọc được bằng mắt trên chính tờ hợp đồng.
            order_by="idx asc, name asc",
        ))
        if rate > 0:
            return rate
    if not price_list:
        return None
    return frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": 1},
        "price_list_rate",
    )


def dong_bo(bo, thang_cuoc=None) -> dict:
    """Dựng/cập nhật `Item Price` từ một HĐNT. `bo` là tên hoặc document.

    Trả `{"tao": int, "cap_nhat": int, "bo_qua": [{item_code, ly_do}],
    "ly_do": str | None}` — `ly_do` chỉ có giá trị khi KHÔNG đồng bộ được gì
    cho cả chứng từ (hợp đồng mua hàng, hoặc đã hết hiệu lực). `cap_nhat`
    đếm dòng đang có giá dương bị đổi; mọi lần ghi khác tính vào `tao`. Hàm
    này ném lỗi bình thường; người gọi từ hook chịu trách nhiệm bọc (xem
    `tu_hdnt`).

    `thang_cuoc` — `{item_code: hợp đồng thắng cuộc}` do người gọi tính sẵn
    bằng ĐÚNG luật của cổng (Ruling P30, xem `dong_bo_khach`). Mã nào có
    người thắng KHÁC hợp đồng này thì hợp đồng này KHÔNG được ghi giá cho
    nó. `None` = không phân định (đường gọi một hợp đồng lẻ: test, patch cũ
    v1_13) — giữ nguyên hành vi cũ."""
    doc = bo if hasattr(bo, "doctype") else frappe.get_doc("Blanket Order", bo)
    ket_qua = {"tao": 0, "cap_nhat": 0, "bo_qua": [], "ly_do": None}

    if doc.blanket_order_type != "Selling":
        ket_qua["ly_do"] = _("Hợp đồng mua hàng — không liên quan bảng giá bán.")
        return ket_qua

    # Hợp đồng ĐÃ HẾT HẠN không có quyền đặt giá cho hôm nay. Bỏ chốt này là
    # một lỗi thật đã bị test E6 bắt: `dong_bo` suy bảng giá từ KHÁCH
    # (`default_price_list`) chứ không từ hợp đồng, nên một HĐNT cũ vừa được
    # submit lại (sửa đổi, ký bổ sung) sẽ ghi đè giá của hợp đồng ĐANG hiệu
    # lực. Không chặn theo `from_date`: hợp đồng ký trước ngày hiệu lực vẫn
    # nên dựng sẵn giá — `portal_contracts` đã tự chặn đặt hàng cho tới
    # `from_date`, nên giá "có sớm" vô hại, còn giá "hết hạn" thì có hại.
    # `getdate()` cả hai vế: ở luồng hook `on_submit`, `doc.to_date` còn là
    # CHUỖI (chưa qua vòng nạp lại của `frappe.get_doc`), so thẳng với một
    # `date` sẽ ném TypeError — và hook thì nuốt lỗi, nên sai lầm này biến
    # thành "im lặng không đồng bộ gì cả".
    if doc.to_date and getdate(doc.to_date) < getdate():
        ket_qua["ly_do"] = _(
            "Hợp đồng đã hết hiệu lực ngày {0} — không cập nhật bảng giá."
        ).format(format_date(doc.to_date))
        return ket_qua

    # Spec 2026-10-09 §5.3 (thay Ruling P32) — không còn TỪ CHỐI khi khách
    # chưa có bảng hoặc đang dùng chung bảng: tách/tạo bảng riêng rồi ghi.
    # Gọi SAU hai chốt ở trên: hợp đồng mua hàng hay đã hết hạn thì không có
    # gì để ghi, không được vì nó mà dựng bảng.
    from miyano_portal import bang_gia_khach
    bang_gia = bang_gia_khach.dam_bao_bang_gia_rieng(doc.customer)
    # Một truy vấn cho cả hợp đồng: giá BỘ ĐỌC đang trả cho khách này. "Đã
    # khớp" phải hỏi bộ đọc chứ không soi một dòng `Item Price` bất kỳ — dòng
    # đúng giá mà đã hết hạn, khác đơn vị hay bị dòng riêng của khách che thì
    # cổng vẫn không thấy giá hợp đồng.
    dang_co = bang_gia_khach.gia_bang_gia_nhieu(
        doc.customer, [d.item_code for d in doc.items]
    )

    tien_te = frappe.db.get_value("Price List", bang_gia, "currency") or "VND"

    for dong in doc.items:
        # Ruling P30 — mã này thuộc về hợp đồng khác theo LUẬT CỦA CỔNG.
        nguoi_thang = (thang_cuoc or {}).get(dong.item_code)
        if nguoi_thang and nguoi_thang != doc.name:
            continue
        rate = flt(dong.rate)
        if rate <= 0:
            ket_qua["bo_qua"].append({
                "item_code": dong.item_code,
                "ly_do": _("chưa khai đơn giá trên hợp đồng"),
            })
            continue

        if dang_co.get(dong.item_code) == rate:
            continue
        # `Blanket Order Item` KHÔNG có trường `uom` — giá trên hợp đồng luôn
        # hiểu theo ĐVT tồn kho của mặt hàng, đúng đơn vị bộ ghi chung dùng.
        gia_cu = bang_gia_khach.ghi_gia_vao_bang(
            bang_gia, doc.customer, dong.item_code, rate, tien_te
        )
        # Cùng mã khai hai dòng trên một hợp đồng: dòng sau thấy giá dòng trước.
        dang_co[dong.item_code] = rate
        ket_qua["cap_nhat" if gia_cu else "tao"] += 1

    return ket_qua


def dong_bo_khach(customer, doc=None) -> dict:
    """Đồng bộ MỌI HĐNT bán của một khách, không chỉ hợp đồng vừa ký.

    Vì sao phải quét cả khách: `Customer.default_price_list` là MỘT field,
    nhưng một khách có thể có NHIỀU hợp đồng còn hiệu lực cùng lúc
    (`portal_contracts` chỉ lọc theo khoảng ngày, và `portal_order_place`
    nhận `contract` làm tham số nên khách chọn hợp đồng nào cũng đặt được).
    Trình import (`migration/import_erpnext.py`) trước 09/10/2026 lại đặt
    mỗi hợp đồng một bảng giá riêng rồi trỏ `default_price_list` sang bảng
    giá MỚI NHẤT (dữ liệu cũ trên site vẫn mang hình dạng đó) — nếu chỉ đồng
    bộ hợp đồng vừa ký thì hợp đồng cũ hơn bị bỏ lại ở bảng giá không còn ai
    đọc, và lỗi "chưa có giá" quay lại đúng cho hợp đồng đó. Đã dựng lại
    được bằng test trước khi sửa.

    **Ruling P30 (review vòng 1) — ĐỔI LUẬT PHÂN ĐỊNH.** Bản trước duyệt
    `creation asc` rồi để mỗi lần ghi đè lên cùng một dòng `Item Price`, tức
    luật ẩn "hợp đồng KÝ SAU thắng". Cổng thì phân định NGƯỢC LẠI — "hết hạn
    sớm nhất thắng, trùng `to_date` thì `name` nhỏ hơn"
    (`nguon_gia_theo_ma_cho_khach`, Ruling P14). Trước Task 12 điều đó vô
    hại vì CẢ HAI bên đều đọc `Item Price`, nên chúng khớp nhau theo cấu
    trúc dù luật khác nhau. Sau Task 12 cổng đọc thẳng hợp đồng, và hai luật
    ngược nhau trên cùng một dữ liệu thành một sai lệch CÓ HỆ THỐNG: khách
    có hợp đồng A (88.000, hết 31/12) và bản gia hạn C ký sau (95.000, hết
    30/06 năm sau) thì cổng báo giá 88.000, `Item Price` giữ 95.000, và nhân
    viên Miyano chỉ cần sửa số lượng trên đơn trong Desk là `transaction.js`
    nạp `price_list_rate` đè `rate` — bệnh viện được báo một giá, bị xuất
    hoá đơn một giá khác, không sự kiện nào ghi lại.

    Từ đây `Item Price` theo ĐÚNG luật của cổng: người thắng tính MỘT LẦN ở
    đây bằng chính `nguon_gia_theo_ma_cho_khach()`, rồi truyền xuống
    `dong_bo(..., thang_cuoc=...)` để hợp đồng THUA không ghi giá cho mã đó.
    Dựa vào thứ tự ghi đè là một luật ẩn, và luật ẩn thì không ai sửa được
    khi nó sai. Muốn "bản gia hạn ký sau đè giá cũ" thì đổi luật ở MỘT chỗ
    (`THU_TU_PHAN_DINH`) và cả hai bên cùng đổi — đó chính là điểm.

    `creation asc` vẫn giữ, nhưng giờ chỉ còn là thứ tự TẤT ĐỊNH cho các mã
    KHÔNG có người thắng (mã không nằm trong hợp đồng còn hiệu lực nào —
    hợp đồng chưa tới ngày hiệu lực vẫn được dựng sẵn giá, xem `dong_bo`).
    Những mã đó không bao giờ đi qua bước 2 của cổng: dòng ngoài mọi hợp
    đồng còn hiệu lực là dòng "chờ báo giá", `rate = 0`, không tra bảng giá.

    Hợp đồng hết hiệu lực bị `dong_bo` tự loại; CỐ Ý không lọc lần thứ hai ở
    truy vấn này (hai nơi cùng định nghĩa "còn hiệu lực" là hai nơi lệch nhau
    được). `ly_do` trả về là của CHÍNH hợp đồng vừa ký — đó là thứ người bấm
    submit cần đọc, không phải lý do của một hợp đồng cũ nào khác."""
    # Ruling P30 (review vòng 1) — LUẬT PHÂN ĐỊNH của CỔNG, không phải luật
    # ẩn "ai ghi sau thì thắng" của vòng lặp bên dưới. Import tại chỗ để
    # `gia_hdnt` không phụ thuộc module doctype ở tầng import.
    from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
        nguon_gia_theo_ma_cho_khach,
    )

    thang_cuoc = nguon_gia_theo_ma_cho_khach(customer)
    tong = {"tao": 0, "cap_nhat": 0, "bo_qua": [], "ly_do": None}
    ten_hien_tai = doc.name if doc is not None else None

    ds = frappe.get_all(
        "Blanket Order",
        filters={"customer": customer, "blanket_order_type": "Selling", "docstatus": 1},
        pluck="name",
        order_by="creation asc",
    )
    if ten_hien_tai and ten_hien_tai not in ds:
        ds.append(ten_hien_tai)

    for ten in ds:
        # Hợp đồng vừa ký dùng THẲNG document đang có trong bộ nhớ: ở
        # `on_submit` bản ghi đã xuống DB, nhưng đọc lại là một round-trip
        # thừa và là một chỗ có thể đọc trúng dữ liệu chưa kịp ghi.
        kq = dong_bo(doc if ten == ten_hien_tai else ten, thang_cuoc=thang_cuoc)
        tong["tao"] += kq["tao"]
        tong["cap_nhat"] += kq["cap_nhat"]
        if ten == ten_hien_tai:
            tong["ly_do"] = kq["ly_do"]
            tong["bo_qua"] = kq["bo_qua"]
    return tong


def tu_hdnt(doc, method=None):
    """Hook `on_submit` của `Blanket Order`.

    KHÔNG được làm hỏng việc ký hợp đồng: đồng bộ bảng giá là hiệu ứng phụ,
    lỗi ở đây (bảng giá bị xoá, Item lạ, ...) không có quyền rollback một
    chứng từ nghiệp vụ đã đúng — cùng nguyên tắc `delivery_hook._chay_an_toan`.
    Nhưng cũng KHÔNG được im lặng: người vừa submit phải thấy ngay, vì hậu quả
    của việc bỏ sót là khách không đặt được hàng và không ai biết tại sao."""
    try:
        if doc.blanket_order_type != "Selling":
            return
        ket_qua = dong_bo_khach(doc.customer, doc)
    except Exception:
        frappe.log_error(title=f"HĐNT {doc.name}: không đồng bộ được đơn giá sang bảng giá")
        frappe.msgprint(
            _("Không dựng được bảng giá từ hợp đồng này. Kiểm tra Error Log — "
              "khách sẽ không đặt hàng được trên cổng cho tới khi xử lý."),
            indicator="red", alert=True,
        )
        return

    if ket_qua["ly_do"] and doc.blanket_order_type == "Selling":
        frappe.msgprint(ket_qua["ly_do"], indicator="orange", alert=True)
    if ket_qua["bo_qua"]:
        frappe.msgprint(
            _("Chưa khai đơn giá cho: {0}. Khách chưa đặt được các mặt hàng này.").format(
                ", ".join(b["item_code"] for b in ket_qua["bo_qua"])
            ),
            indicator="orange", alert=True,
        )
