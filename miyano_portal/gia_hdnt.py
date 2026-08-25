"""Giá hợp đồng: hàm tra dùng chung của cổng, và đồng bộ sang `Item Price`.

> **ĐỌC TRƯỚC.** Phần "Vì sao cần file này" bên dưới là lập luận của bản
> 14/08/2026 và **đã bị Task 12 (QĐ-G12, 21/08) đảo ở vế trung tâm**: cổng
> GIỜ ĐỌC `Blanket Order Item.rate` khi đặt hàng, qua
> `gia_dong_hop_dong()` ngay dưới đây. Giữ nguyên văn bản cũ (thay vì xoá)
> vì phần chẩn đoán của nó vẫn đúng và vẫn là lời giải thích tốt nhất cho
> việc `dong_bo()` tồn tại; chỉ có kết luận "nên tra qua Item Price" là hết
> hạn. Xem khối "Task 12" ở cuối docstring này để biết cái gì thay cái gì.

**Vì sao cần file này** *(bản 14/08 — vế "cổng không bao giờ đọc rate" đã
hết đúng, xem khối Task 12 ở cuối)*. Cổng không bao giờ đọc `Blanket Order
Item.rate` khi đặt hàng: ba đường đặt hàng (`portal_order_place` HĐNT/bán
lẻ, `portal_reorder`) đều tra `Item Price` trong `Customer.default_price_list`.

Đó là ĐÚNG, và lý do là: **cổng cần giá TRƯỚC khi có bất kỳ chứng từ nào.**
`portal_catalog` phải hiện giá, giỏ hàng phải cộng tổng, kiểm hạn mức phải
chạy — tất cả xảy ra khi chưa có Sales Order nào tồn tại. Trong khi đó
`blanket_order_rate` của ERPNext chỉ được điền tại ĐÚNG HAI thời điểm, cả hai
đều đã có chứng từ trong tay: `blanket_order.py::make_order()` (nút
"Create → Sales Order" trên HĐNT ở Desk, `target.rate = source.get("rate")`)
và sự kiện JS `transaction.js::blanket_order()` khi người dùng chọn HĐNT trên
một dòng của form. KHÔNG có đường server-side nào suy ra giá HĐNT cho một
chứng từ tự dựng — mà `_xay_don_hdnt` thì dựng Sales Order từ đầu.

(Ghi chú lịch sử: bản đầu của docstring này khẳng định thêm rằng đơn hàng
không có Item Price sẽ bị Desk nạp lại giá về 0 khi sửa số lượng. ĐÃ KIỂM
mã nguồn: SAI. `get_item_details.get_price_list_rate` trả về mà KHÔNG đặt
`price_list_rate` khi không tìm thấy Item Price, và `transaction.js::
_set_values_for_item_list` chỉ ghi đè `rate` khi khoá `price_list_rate` thật
sự có mặt — nên `rate` giữ nguyên. Không dùng lập luận đó để bảo vệ thiết kế
này nữa; lý do thật là đoạn ở trên.)

Chỗ hổng là ở QUY TRÌNH, không phải ở phép tra: sales nhập giá vào HĐNT rồi
tưởng thế là xong, không ai biết phải nhập lần thứ hai vào bảng giá. Khi đó
`portal_catalog` (có nhánh rơi về `row["rate"]`) vẫn HIỆN giá đẹp, còn lúc gửi
đơn thì bị chặn "… chưa có giá trong hợp đồng" — mâu thuẫn không thể tự giải
thích nếu chỉ nhìn HĐNT. Trên `erptest.local` lúc phát hiện: cả site có **0
bản ghi `Item Price`** dù ba bảng giá HĐNT đều tồn tại và ba HĐNT đều có rate.

Từ đây: nhập giá MỘT lần trên HĐNT, submit là hệ thống tự dựng bảng giá.

Ranh giới cố ý:

- **Chỉ `Selling`.** HĐNT mua hàng của Miyano không dính dáng bảng giá bán.
- **`rate = 0` là CHƯA khai giá, không phải "bán 0 đồng"** — bỏ qua. Đường đặt
  hàng dùng `if not rate` nên một Item Price giá 0 vẫn báo thiếu giá, trong khi
  sales nhìn bảng giá lại thấy "đã có dòng": che mất đúng việc cần làm.
- **Giá HĐNT ĐÈ giá cũ.** Hợp đồng đã ký là nguồn sự thật; giữ im lặng một giá
  cũ khác với hợp đồng là xuất hoá đơn sai.
- **Không tự chế bảng giá.** Khách chưa có `default_price_list` thì báo cho
  người submit chứ không đặt bừa một tên bảng giá (đặt sai thì mọi đơn sau đó
  chạy trên bảng giá không ai rà).

---

**Task 12 (21/08/2026) — QĐ-G12.** Lập luận ở trên VẪN ĐÚNG và không bị bỏ:
cổng vẫn cần giá TRƯỚC khi có chứng từ, `dong_bo` vẫn là cách để phía ERPNext
(báo cáo, hoá đơn, giá lúc Desk dựng chứng từ) thấy đúng giá hợp đồng. Cái
SAI không nằm ở phép tra mà ở chỗ nó là phép tra DUY NHẤT: `tu_hdnt` là hook
`on_submit`, chạy ĐÚNG MỘT LẦN lúc trình ký, nên mọi hợp đồng ký TRƯỚC khi
hook ra đời và mọi hợp đồng nạp bằng import chưa bao giờ được đồng bộ — và
chỗ hổng đó IM LẶNG. Chủ đầu tư gặp đúng nó ngày 21/08: `MFG-BLR-2026-00020`
khai đủ `rate` cho ba mã, `tabItem Price` không có dòng nào, cổng chặn đơn
bằng "MYN-SYR-10 chưa có giá trong hợp đồng".

Từ Task 12, cổng KHÔNG còn phụ thuộc việc đồng bộ đã kịp chạy hay chưa: với
một dòng HỢP ĐỒNG, nguồn giá là CHÍNH HỢP ĐỒNG ĐÓ (`gia_dong_hop_dong()`
dưới đây), bảng giá chỉ còn là bước lui. Hai việc khác nhau, cả hai đều giữ:
`gia_dong_hop_dong()` làm cổng ĐÚNG NGAY, `dong_bo()` làm dữ liệu NHẤT QUÁN.
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
    đơn (`dat_hang._xay_don`), danh mục gộp (`api/portal.portal_catalog_gop`),
    đóng dấu giá lúc gửi duyệt (`PortalDeXuatMua._dong_dau_gia`) và so giá
    lúc duyệt (`de_xuat_duyet._kiem_gia_doi`). Bốn phép tra riêng là bốn chỗ
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
    kết cục ở cổng đặt hàng; giữ nguyên giá trị trả về để `portal_catalog_gop`
    (hiển thị `don_gia`) không đổi hành vi ở nhánh không liên quan tới QĐ-G12.

    `price_list` được phép `None` và phép kiểm nằm TRONG hàm này, không ở
    bốn nơi gọi: bước 1 KHÔNG cần bảng giá nào cả. Để phép kiểm ở ngoài
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
    cho cả chứng từ (sai loại, khách chưa có bảng giá...). Hàm này ném lỗi
    bình thường; người gọi từ hook chịu trách nhiệm bọc (xem `tu_hdnt`).

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

    bang_gia = frappe.db.get_value("Customer", doc.customer, "default_price_list")
    if bang_gia:
        # Ruling P32 (review vòng 1) — bảng giá đích suy từ KHÁCH
        # (`default_price_list`), KHÔNG từ hợp đồng. Khi hai bệnh viện cùng
        # trỏ về một bảng giá (đúng hình dạng dữ liệu demo/site này:
        # `HĐNT-BVBM-2026` là mặc định của CẢ `Bệnh viện Bạch Mai` LẪN
        # `PXN ABC`), hợp đồng của bên này ghi giá cho bên kia. Hậu quả
        # không dừng ở một dòng thừa: một mã `rate = 0` (chưa khai giá) của
        # khách B rơi xuống bước 2 của `gia_dong_hop_dong()` và đọc trúng
        # giá ĐÃ ĐÀM PHÁN của khách A — bệnh viện này bị tính giá của bệnh
        # viện khác thay vì được chặn đúng bằng "chưa có giá trong hợp
        # đồng". Thà KHÔNG ghi và báo ồn ào, còn hơn ghi rồi không ai biết.
        # `disabled: 0` (sửa 25/08) — chốt này đếm khách hàng ĐANG HOẠT
        # ĐỘNG. Thiếu bộ lọc, một bệnh viện cũ đã bị vô hiệu hoá nhưng vẫn
        # trỏ `default_price_list` về bảng giá này sẽ khiến phép đếm mãi
        # mãi > 1, và bệnh viện CÒN LẠI bị chặn đồng bộ giá VĨNH VIỄN bằng
        # một câu bảo họ "tách bảng giá riêng cho từng khách" — trong khi
        # họ đã là khách duy nhất còn hoạt động dùng nó. Khách đã vô hiệu
        # hoá thì không đặt hàng được nữa, nên không có giá nào của họ để
        # mà trộn: đúng nghĩa nguy cơ mà P32 dựng lên để chặn.
        dung_chung = frappe.get_all(
            "Customer", filters={"default_price_list": bang_gia, "disabled": 0},
            pluck="name", order_by="name asc",
        )
        if len(dung_chung) > 1:
            ket_qua["ly_do"] = _(
                "Bảng giá {0} đang là Bảng giá mặc định của {1} khách hàng ({2}) "
                "nên KHÔNG ghi đơn giá hợp đồng vào đó — làm vậy là trộn giá đàm "
                "phán của các bệnh viện khác nhau. Tách bảng giá riêng cho từng "
                "khách rồi ký lại (hoặc chạy lại đồng bộ)."
            ).format(bang_gia, len(dung_chung), ", ".join(dung_chung))
            frappe.log_error(
                title=f"Bảng giá dùng chung: {bang_gia}",
                message=ket_qua["ly_do"],
            )
            return ket_qua
    if not bang_gia:
        ket_qua["ly_do"] = _(
            "Khách hàng {0} chưa được gán Bảng giá mặc định (default_price_list) "
            "nên chưa dựng được đơn giá. Khách sẽ không đặt hàng được trên cổng "
            "cho tới khi bổ sung."
        ).format(doc.customer)
        return ket_qua

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

        ten = frappe.db.get_value(
            "Item Price",
            {"item_code": dong.item_code, "price_list": bang_gia, "selling": 1},
            "name",
        )
        if ten:
            if flt(frappe.db.get_value("Item Price", ten, "price_list_rate")) == rate:
                continue
            # `db.set_value` chứ không `get_doc().save()`: Item Price có
            # validate trùng lặp theo (item, price_list, uom, ngày hiệu lực)
            # đủ nặng để một lần submit HĐNT nhiều dòng thành nhiều round-trip,
            # trong khi ở đây chỉ đổi đúng một con số trên bản ghi ĐÃ hợp lệ.
            frappe.db.set_value("Item Price", ten, "price_list_rate", rate)
            ket_qua["cap_nhat"] += 1
            continue

        frappe.get_doc({
            "doctype": "Item Price",
            "item_code": dong.item_code,
            "price_list": bang_gia,
            # `Blanket Order Item` KHÔNG có trường `uom` (đã kiểm JSON: chỉ
            # item_code/item_name/qty/rate/ordered_qty/party_item_code) — giá
            # trên hợp đồng luôn hiểu theo ĐVT tồn kho của mặt hàng. Ghi
            # tường minh chứ không để trống: Item Price khác ĐVT là một mức
            # giá KHÁC, để trống thì ERPNext tự suy và có thể suy khác với
            # dòng đơn hàng.
            "uom": frappe.db.get_value("Item", dong.item_code, "stock_uom"),
            "selling": 1,
            "buying": 0,
            "price_list_rate": rate,
            "currency": tien_te,
        }).insert(ignore_permissions=True)
        ket_qua["tao"] += 1

    return ket_qua


def dong_bo_khach(customer, doc=None) -> dict:
    """Đồng bộ MỌI HĐNT bán của một khách, không chỉ hợp đồng vừa ký.

    Vì sao phải quét cả khách: `Customer.default_price_list` là MỘT field,
    nhưng một khách có thể có NHIỀU hợp đồng còn hiệu lực cùng lúc
    (`portal_contracts` chỉ lọc theo khoảng ngày, và `portal_order_place`
    nhận `contract` làm tham số nên khách chọn hợp đồng nào cũng đặt được).
    Trình import (`migration/import_erpnext.py`) lại đặt mỗi hợp đồng một
    bảng giá riêng rồi trỏ `default_price_list` sang bảng giá MỚI NHẤT — nếu
    chỉ đồng bộ hợp đồng vừa ký thì hợp đồng cũ hơn bị bỏ lại ở bảng giá
    không còn ai đọc, và lỗi "chưa có giá" quay lại đúng cho hợp đồng đó.
    Đã dựng lại được bằng test trước khi sửa.

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
