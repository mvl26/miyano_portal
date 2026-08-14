"""Adapter — khối HĐĐT hiển thị trên cổng khách hàng (E7, chỉ đọc).

`Fast EInvoice Document` (110 trường, `apps/erpnext/erpnext/einvoice/`) là
doctype của MODULE KHÁC (team Dev). File này là NƠI DUY NHẤT ánh xạ tên
trường thật của module đó sang dữ liệu cổng hiển thị — đổi mapping chỉ sửa ở
đây, không rải tên trường khắp `api/portal.py`/frontend (PRD E7 DoD).

Bản đồ dữ liệu ĐÃ KIỂM lại bằng cách đọc trực tiếp
`erpnext/einvoice/doctype/fast_einvoice_document/fast_einvoice_document.json`
và `erpnext/einvoice/*.py` — KHÔNG theo mù bảng "tên tạm" trong PRD/BA (các
trường `einvoice_*` trên `Sales Invoice` mà BA giả định KHÔNG TỒN TẠI). Các
phát hiện quan trọng nhất, lệch với brief gốc — chi tiết đầy đủ + hệ quả cho
team HĐĐT ở `docs/HDDT-ban-giao-team-module.md`:

1. **Liên kết chính KHÔNG phải `sales_invoice`.** `builder.py::
   create_from_delivery_note` — luồng tạo bản ghi HĐĐT GỐC — chỉ gán
   `fei.delivery_note`, không bao giờ gán `fei.sales_invoice`. `resolve_all()`
   dưới đây bắc cầu qua `Sales Invoice Item.delivery_note` -> `FEI.
   delivery_note`, đúng docstring `erpnext/einvoice/lookup.py`.
2. **MỘT Sales Invoice có thể khớp NHIỀU `Fast EInvoice Document`, không chỉ
   một** (review round 1, C-1). `lineage.py::_COPIED_FIELDS` copy CẢ
   `delivery_note` LẪN `sales_invoice` từ bản gốc sang bản điều chỉnh/thay
   thế — nghĩa là cả nhà (gốc + con) LUÔN cùng xuất hiện trong tập khớp của
   MỘT Sales Invoice. `cancel.py::_unlock_delivery_note` cũng xoá số hoá đơn
   trên Delivery Note để cho phép lập một `Fast EInvoice Document` MỚI cho
   CÙNG phiếu giao sau khi huỷ nội bộ — một bản ghi cũ (đã huỷ) và một bản ghi
   mới có thể cùng khớp một Sales Invoice mà KHÔNG có field nào nối chúng.
   Trả đúng MỘT bản ghi (bản cũ, trước review round 1) khiến hoá đơn gốc vẫn
   còn giá trị pháp lý bị NGỠ là không tải được ngay khi kế toán bắt đầu lập
   bản điều chỉnh — resolve_all()/block_for() dưới đây trả TOÀN BỘ tập khớp.
3. **`amended_from_fei`** là nửa CÒN LẠI của liên kết hai chiều NL-12.2/12.3
   mà bảng map gốc trong brief bỏ sót (brief chỉ liệt `original_document`,
   là nửa NGƯỢC). `lineage.mark_original_superseded()` set field này trên
   bản ghi GỐC, trỏ TỚI bản ghi điều chỉnh/thay thế, ngay khi bản ghi con
   phát hành xong.
4. **Không có sự kiện nào để móc email "phát hành thành công" (US-E7.3).**
   Mọi lần đổi `status` sang "Đã phát hành" đều qua
   `frappe.db.set_value(..., update_modified=False)` (`issue.py::
   _store_issue_result`) — ghi thẳng DB, KHÔNG chạy qua vòng đời Document,
   nên `doc_events["Fast EInvoice Document"]["on_update"]` không bao giờ
   được gọi cho sự kiện này dù đăng ký trong `hooks.py` của app này (đã kiểm
   thực nghiệm). NẰM NGOÀI phạm vi brief E7 ("Việc phải làm" chỉ có 3 mục) —
   descope + yêu cầu chính thức cho team HĐĐT ở tài liệu bàn giao, KHÔNG tự
   viết job poll vá lỗ ở đây. Vì lý do tương tự, patch backfill
   US-E7.3/TC-E7-06 KHÔNG cần viết: khối HĐĐT được TRA CỨU TRỰC TIẾP mỗi lần
   đọc (không sao chép dữ liệu sang field nào trên `Sales Invoice`), nên hoá
   đơn cũ tự động "sáng" ngay khi có `Fast EInvoice Document` khớp.

Trạng thái 12 ("Đã hủy nội bộ") — `cancel.py::cancel_internally` chỉ hủy được
hóa đơn đang ở `09 - CQT từ chối`, và không có field nào nối bản ghi bị hủy
với hóa đơn mới lập cho CÙNG phiếu giao (nếu có) — CỐ Ý không suy đoán liên
kết ĐÍCH DANH đó (không gán `hoa_don_goc`/`hoa_don_moi` giữa hai bản ghi
không có field nối), vì đó là BỊA lineage không có thật trong dữ liệu. Cả hai
bản ghi vẫn cùng có mặt trong `khac`/`chinh` của `block_for()` (cùng khớp một
`delivery_note`) nên khách vẫn THẤY cả hai — chỉ là không có một mũi tên
"thay bằng" nối chúng.

An toàn dữ liệu (quyết định nền tảng #7/#8 của app): role `Customer` **không**
có DocPerm nào trên `Fast EInvoice Document` (đã kiểm thực nghiệm —
`frappe.has_permission("Fast EInvoice Document", "read", user=<khách>)` trả
`False`) — cổng không được thêm DocPerm mới. Module này KHÔNG BAO GIỜ gọi
`frappe.get_doc(FEI, ...)` với tên nhận từ client; mọi truy cập của
`api/portal.py` bắt đầu từ `Sales Invoice` (nơi khách CÓ quyền qua
`check_permission`), rồi mới dò sang `Fast EInvoice Document` và tự đối
chiếu `fei.customer == si.customer` trước khi tin bất kỳ dữ liệu nào — một
FEI bị kế toán gõ nhầm `sales_invoice` sang hoá đơn của khách khác sẽ bị vô
hiệu ở đây, không lộ ra cổng. Endpoint tải (`portal_einvoice_download`) nhận
tham số `fei` TUỲ CHỌN từ client để chọn ĐÚNG bản ghi trong một tập nhiều bản
ghi, nhưng KHÔNG BAO GIỜ dùng thẳng tên đó để `frappe.get_doc()` — tên đó chỉ
được dùng để LỌC trong tập `resolve_all(invoice)` đã tự suy ra và đã lọc
đúng khách của phiên; một tên lạ không có trong tập đó bị từ chối ngay.
"""

import frappe

FEI = "Fast EInvoice Document"

# 14 mã trạng thái thật (erpnext/einvoice/constants.py) -> nhóm hiển thị cho
# khách + nhãn tiếng Việt + class badge. KHÔNG BAO GIỜ phơi mã số thô
# ("06 - Đã phát hành") ra JSON trả về cổng — chỉ nhóm + nhãn đã dịch.
_STATUS_META = {
    # 01–04 là BẢN NHÁP có thật — khách xem được nội dung và tải được bản in
    # thử khi Fast đã dựng (`draft_pdf`). Gọi chúng là "Đang phát hành HĐĐT"
    # như bản trước là nói sai: chưa ai bấm phát hành cả, và giấu mất thứ
    # khách đang có quyền xem.
    "01 - Nháp": ("nhap", "Hoá đơn nháp", "b-gray"),
    "02 - Đã xem nháp": ("nhap", "Hoá đơn nháp", "b-gray"),
    "03 - Chờ khách duyệt": ("nhap", "Hoá đơn nháp", "b-gray"),
    "04 - Khách đã duyệt": ("nhap", "Hoá đơn nháp", "b-gray"),
    # 05 mới thật sự là "đã bấm phát hành, đang chờ Fast": nội dung đã chốt,
    # không còn là bản để khách góp ý.
    "05 - Đang phát hành": ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray"),
    "06 - Đã phát hành": ("da_phat_hanh", "Đã phát hành", "b-green"),
    "07 - Đã gửi khách": ("da_phat_hanh", "Đã phát hành", "b-green"),
    "08 - CQT chấp nhận": ("da_phat_hanh", "Đã phát hành", "b-green"),
    # Từ 09 trở đi: đã có số thật (ISSUED_STATUSES) nhưng không còn là "bình
    # thường" — mỗi trạng thái một nhãn RIÊNG, không gộp chung "Đã phát hành"
    # (đó là nói dối khách về giá trị hoá đơn đang cầm, cùng lỗi với chú
    # thích XML đã bỏ).
    "09 - CQT từ chối": ("cqt_tu_choi", "CQT từ chối", "b-orange"),
    "10 - Đã điều chỉnh": ("da_dieu_chinh", "Bị điều chỉnh", "b-orange"),
    "11 - Đã thay thế": ("da_thay_the", "Đã thay thế", "b-red"),
    "12 - Đã hủy nội bộ": ("da_huy", "Đã hủy nội bộ", "b-red"),
    "98 - Cần đối soát": ("loi", "Cần đối soát", "b-red"),
    "99 - Lỗi": ("loi", "Lỗi hệ thống", "b-red"),
}
_MAC_DINH = ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray")

# NL-12.1: nhóm "chưa có gì để xem" — không nút tải, không phải lỗi. Cũng là
# nhóm mặc định khi CHƯA có chứng từ HĐĐT nào (`khoi_mac_dinh`).
_CHUA_PHAT_HANH = {"dang_phat_hanh"}
# NL-12.4: nhóm "lỗi" — nút tải disable + nút Yêu cầu hỗ trợ, BẤT KỂ file có
# hay không (98/99 nghĩa là bản ghi tự nó có vấn đề, không phải "đang chờ").
_NHOM_LOI = {"loi"}
# E7b: bản nháp — CÓ nội dung để xem, có thể có PDF nháp do Fast dựng, nhưng
# tuyệt đối không phải hoá đơn chính thức. Tách riêng vì hai nhóm trên đều
# nghĩa là "không có gì cho khách", còn nhóm này thì ngược lại.
_NHOM_NHAP = {"nhap"}

# Câu cảnh báo đi CÙNG dữ liệu, không để riêng bên frontend: chính docstring
# `actions.send_draft_to_customer` của module HĐĐT chốt rằng gửi bản nháp mà
# không nói rõ là để khách hiểu nhầm đã có hoá đơn. Một lần sửa giao diện làm
# rơi mất câu này là một lần khách tưởng mình đang cầm chứng từ thuế.
CANH_BAO_NHAP = (
    "Bản nháp — chưa có số hoá đơn, chưa ký số, chưa gửi Cơ quan Thuế, "
    "KHÔNG có giá trị pháp lý. Số liệu có thể thay đổi trước khi phát hành."
)

# Thứ tự ưu tiên khi CHỌN bản ghi "chính" (badge thu gọn) trong một tập nhiều
# `Fast EInvoice Document` cùng khớp một Sales Invoice (review round 1, C-1).
# Số CÀNG NHỎ càng ưu tiên. "Còn hiệu lực, tải được hoặc chỉ chờ file" đứng
# TRƯỚC "đang có bản điều chỉnh/thay thế mới soạn dở" — nếu không, kế toán
# vừa bấm "Lập hoá đơn điều chỉnh" (sinh bản con "01 - Nháp") sẽ NGAY LẬP TỨC
# làm bản GỐC vẫn còn nguyên giá trị (chưa hề bị `mark_original_superseded`
# đổi trạng thái) biến mất khỏi badge chính — đúng lỗi C-1 đã sửa.
_UU_TIEN_CHINH = {
    "da_phat_hanh": 0, "cqt_tu_choi": 0,
    # `nhap` cùng hạng 1 với `dang_phat_hanh`: một bản điều chỉnh vừa được
    # soạn (01) KHÔNG được che bản gốc còn nguyên giá trị pháp lý — đúng lỗi
    # C-1 đã sửa ở review vòng 1.
    "dang_phat_hanh": 1, "loi": 1, "nhap": 1,
    "da_dieu_chinh": 2, "da_thay_the": 2, "da_huy": 2,
}

# Field cần cho khối hiển thị + đối chiếu sở hữu + chọn bản ghi chính.
# `fast_pattern` (Mẫu số) — thiếu ở bản trước (review I-1): PRD yêu cầu hiện
# "Số + MẪU SỐ–ký hiệu" và trang tra cứu CQT đòi cả hai trường tách biệt.
# CỐ Ý KHÔNG gồm `fast_key_search` (khoá tích hợp nội bộ dùng để gọi Fast,
# không phải mã tra cứu cho khách — đó là `tax_verification_code`) và không
# gồm giá trị file nào khác ngoài việc TỰ nó (xem ghi chú `official_pdf`
# trong `_muc_cho`).
_FIELDS = (
    "name", "creation", "status", "invoice_type", "fast_invoice_no", "fast_serial",
    "fast_pattern", "fast_signed_date", "issued_time", "tax_verification_code",
    "official_pdf", "original_document", "amended_from_fei",
    "cancel_reason", "customer", "sales_invoice", "delivery_note",
    # E7b — khối hiển thị cần biết CÓ bản in thử hay không để bật nút xem.
    # Chỉ dùng để tính cờ boolean; đường dẫn không bao giờ ra khỏi module này.
    "draft_pdf",
)


def _meta(status):
    return _STATUS_META.get(status, _MAC_DINH)


def resolve_all(sales_invoice_name):
    """Mọi `Fast EInvoice Document` khớp một `Sales Invoice` — GỘP CẢ HAI
    tầng (liên kết trực tiếp `sales_invoice` VÀ bắc cầu qua
    `Sales Invoice Item.delivery_note`), không dừng lại ở bản ghi đầu tiên
    tìm thấy (xem điểm 2 ở docstring module — lý do KHÔNG được dừng sớm).

    Trả list `frappe._dict` đủ `_FIELDS`, sắp theo `creation` TĂNG DẦN (cũ
    nhất trước), dedupe theo `name`. List rỗng nghĩa là kế toán chưa bắt đầu
    quy trình HĐĐT cho hoá đơn này — với khách, hiển thị y hệt "Đang phát
    hành HĐĐT" như trạng thái 01-05 (xem `block_for`).

    KHÔNG kiểm quyền ở đây — hàm này chỉ tra cứu. Người gọi (`block_for` /
    `portal_einvoice_download`) chịu trách nhiệm đối chiếu `customer` trước
    khi dùng bất kỳ trường nào trả về.
    """
    truc_tiep = frappe.get_all(
        FEI, filters={"sales_invoice": sales_invoice_name},
        fields=_FIELDS, order_by="creation asc",
    )

    dn_names = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": sales_invoice_name, "delivery_note": ["!=", ""]},
        pluck="delivery_note",
    )
    dn_names = list(dict.fromkeys(dn_names))
    qua_dn = (
        frappe.get_all(
            FEI, filters={"delivery_note": ["in", dn_names]},
            fields=_FIELDS, order_by="creation asc",
        )
        if dn_names else []
    )

    theo_ten = {}
    for row in [*truc_tiep, *qua_dn]:
        theo_ten[row.name] = row
    ket_qua = list(theo_ten.values())
    ket_qua.sort(key=lambda r: r.creation)
    return ket_qua


def _tom_tat(fei_row):
    group, label, badge = _meta(fei_row.status)
    return {
        "fei": fei_row.name,
        "so": fei_row.fast_invoice_no or "",
        "ky_hieu": fei_row.fast_serial or "",
        "trang_thai": group,
        "nhan": label,
        "badge": badge,
    }


def _tim_trong(fei_name, ho_so):
    """Tìm một bản ghi theo tên TRONG tập đã có sẵn (không round-trip DB
    thêm) — dùng cho lineage giữa các bản ghi CÙNG một Sales Invoice, vốn
    luôn cùng có mặt trong `ho_so` vì con copy cả `delivery_note` lẫn
    `sales_invoice` từ cha (điểm 2, docstring module)."""
    for f in ho_so:
        if f.name == fei_name:
            return f
    return None


def _lineage_ref(fei_name, customer, ho_so=()):
    """Thông tin rút gọn của một bản ghi liên quan (gốc hoặc bản thay thế),
    dùng cho link hai chiều NL-12.2/12.3. Ưu tiên tìm trong `ho_so` đã có
    (cùng nhà, không round-trip); rơi về tra DB riêng cho trường hợp hiếm
    liên kết trỏ ra NGOÀI tập đã resolve. Trả `None` nếu không tìm thấy HOẶC
    khách của bản ghi liên quan không khớp — không lộ dữ liệu hoá đơn của
    khách khác qua một liên kết lineage sai."""
    if not fei_name:
        return None
    trong_nha = _tim_trong(fei_name, ho_so)
    if trong_nha:
        return _tom_tat(trong_nha) if trong_nha.customer == customer else None

    row = frappe.db.get_value(
        FEI, fei_name,
        ["fast_invoice_no", "fast_serial", "status", "customer"],
        as_dict=True,
    )
    if not row or row.customer != customer:
        return None
    row.name = fei_name
    return _tom_tat(row)


def khoi_mac_dinh():
    """Khối `{"chinh": ..., "khac": []}` khi CHƯA có `Fast EInvoice Document`
    nào khớp, VÀ khi `portal_invoices` phải tự bọc lỗi quanh `block_for`
    (xem ghi chú ở đó): một trường đổi tên/module HĐĐT đổi cấu trúc không
    được phép biến MẤT cả danh sách hoá đơn + công nợ của khách — đúng ràng
    buộc NL-12.1 (công nợ vẫn hiển thị bình thường bất kể trạng thái HĐĐT)."""
    group, label, badge = _MAC_DINH
    return {
        "chinh": {
            "fei": None, "trang_thai": group, "nhan": label, "badge": badge,
            "tai_duoc": False, "nhap_tai_duoc": False, "ho_tro": False,
        },
        "khac": [],
    }


def _muc_cho(fei, ho_so, customer):
    """Dựng khối hiển thị cho MỘT bản ghi (dùng cho cả `chinh` lẫn `khac`)."""
    group, label, badge = _meta(fei.status)
    ho_tro = group in _NHOM_LOI
    co_file = bool(fei.official_pdf)
    tai_duoc = co_the_tai(fei) and co_file

    # Nút xem BẢN NHÁP — tách hẳn khỏi `tai_duoc` (PDF chính thức). Hai nút
    # phục vụ hai file khác nhau với hai chốt trạng thái NGƯỢC nhau; gộp một
    # cờ là sớm muộn cũng giao một bản in thử cho khách như thể nó là chứng
    # từ thuế.
    nhap_tai_duoc = group in _NHOM_NHAP and bool(fei.draft_pdf)

    # NL-12.4 — "File XML/PDF thiếu hoặc hỏng": trạng thái ĐÃ phát hành
    # (issue.py::_queue_pdf_download chạy NỀN, có độ trễ ký số HSM) nhưng
    # file vẫn chưa đính — khác hẳn "đang phát hành" (05, còn ở Desk) và
    # khác "lỗi" (98/99, bản ghi tự nó hỏng): đây là chờ file, cần nhãn riêng
    # + vẫn cho khách yêu cầu hỗ trợ nếu chờ lâu.
    #
    # Dùng `co_the_tai()` chứ không liệt tay hai nhóm: kể từ E7b, một bản
    # NHÁP chưa có PDF là chuyện BÌNH THƯỜNG (trạng thái 01 — kế toán chưa
    # bấm "Xem bản nháp"), không phải sự cố cần khách bấm Yêu cầu hỗ trợ.
    if co_the_tai(fei) and not co_file:
        label = f"{label} — file đang xử lý"
        ho_tro = True

    muc = {
        "fei": fei.name,
        "trang_thai": group,
        "nhan": label,
        "badge": badge,
        "so": fei.fast_invoice_no or "",
        "ky_hieu": fei.fast_serial or "",
        "mau_so": fei.fast_pattern or "",
        "ngay_phat_hanh": fei.fast_signed_date,
        "ma_tra_cuu": fei.tax_verification_code or "",
        "tai_duoc": tai_duoc,
        "nhap_tai_duoc": nhap_tai_duoc,
        "ho_tro": ho_tro,
    }
    # NL-12.2 — badge rõ ràng cho hoá đơn huỷ: lý do huỷ đã nằm sẵn trong
    # `cancel_reason` (review M-1), không lý do gì giữ lại mà không hiện.
    if group == "da_huy" and fei.cancel_reason:
        muc["ly_do_huy"] = fei.cancel_reason

    goc = _lineage_ref(fei.original_document, customer, ho_so)
    if goc:
        muc["hoa_don_goc"] = goc
    moi = _lineage_ref(fei.amended_from_fei, customer, ho_so)
    if moi:
        muc["hoa_don_moi"] = moi
        # Bản mẫu (id `einv-row`) đặt số hoá đơn thay thế NGAY TRONG BADGE
        # thu gọn: "Đã huỷ — thay bằng 00299", không phải một nhãn tĩnh —
        # khớp lại đúng chữ đó cho hai nhóm có `hoa_don_moi` (10/11), thay vì
        # buộc khách bấm xổ dòng mới biết số hoá đơn nào đã thay thế nó.
        if group == "da_thay_the":
            muc["nhan"] = f"Đã huỷ — thay bằng {moi['so'] or moi['fei']}"
        elif group == "da_dieu_chinh":
            muc["nhan"] = f"Bị điều chỉnh — xem {moi['so'] or moi['fei']}"
    return muc


def _chon_chinh(muc_list):
    """Chọn bản ghi "chính" cho badge thu gọn — xem `_UU_TIEN_CHINH`.
    `muc_list` phải theo đúng thứ tự `creation` tăng dần (như `resolve_all`
    trả về): trong cùng một hạng ưu tiên, bản ghi MỚI NHẤT thắng."""
    return min(
        enumerate(muc_list),
        key=lambda cap: (_UU_TIEN_CHINH.get(cap[1]["trang_thai"], 1), -cap[0]),
    )[1]


def block_for(sales_invoice_name, sales_invoice_customer):
    """Khối HĐĐT cho MỘT hoá đơn — trả `{"chinh": {...}, "khac": [...]}`
    JSON-hoá được thẳng cho SPA. `chinh` là bản ghi hiện hành để hiện badge
    thu gọn; `khac` là MỌI bản ghi còn lại (gốc đã bị điều chỉnh/thay thế,
    bản đã huỷ nội bộ, ...) — không được rơi mất một bản nào (NL-12.2 "không
    giấu hoá đơn cũ", review round 1 C-1).

    `sales_invoice_customer` PHẢI là `customer` THẬT của chính hoá đơn này
    (không phải "khách hàng của phiên nói chung") — đối chiếu với
    `fei.customer` bảo vệ khỏi một lỗi dữ liệu ở module HĐĐT (kế toán gõ
    nhầm `sales_invoice` sang hoá đơn của khách khác) biến thành rò dữ liệu
    ở cổng, kể cả khi `Sales Invoice` đọc được đã tự nó đúng chủ.

    KHÔNG BAO GIỜ đưa `official_pdf` (đường dẫn file) vào dict trả về —
    đó là URL file, phá đúng ràng buộc "không có URL file công khai" (BR-E4)
    nếu lọt ra SPA. Chỉ đưa cờ boolean `tai_duoc`; file thật đi qua
    `portal_einvoice_download`, kiểm sở hữu lại từ đầu mỗi lần tải.
    """
    ho_so = [f for f in resolve_all(sales_invoice_name) if f.customer == sales_invoice_customer]
    if not ho_so:
        return khoi_mac_dinh()

    muc_list = [_muc_cho(f, ho_so, sales_invoice_customer) for f in ho_so]
    chinh = _chon_chinh(muc_list)
    khac = [m for m in muc_list if m is not chinh]
    # `canh_bao` ở cấp KHỐI, không nhân bản vào từng mục: giao diện chỉ hiện
    # nó một lần cho mỗi hoá đơn, và để ở đây thì frontend không phải gõ lại
    # câu cảnh báo pháp lý (xem `CANH_BAO_NHAP`).
    return {"chinh": chinh, "khac": khac, "canh_bao": CANH_BAO_NHAP}


def co_the_tai(fei_row):
    """`True` nếu bản ghi được phép tải **PDF CHÍNH THỨC** (`official_pdf`) —
    dùng lại đúng quy tắc của `block_for` ở `portal_einvoice_download` (không
    viết lại logic lần hai, tránh hai nơi lệch nhau).

    Loại CẢ `_NHOM_NHAP`, và đó là dòng quan trọng nhất trong hàm này. Kể từ
    E7b, 01–04 không còn nằm trong `_CHUA_PHAT_HANH` nữa; một bản nháp lại
    hoàn toàn có thể ĐÃ có file đính kèm. Quên loại nhóm nháp ở đây là mở
    đường giao một bản in thử cho khách như thể nó là chứng từ thuế. Bản nháp
    đi đường riêng: cờ `nhap_tai_duoc` + `portal_einvoice_download(loai="nhap")`.
    """
    group, _label, _badge = _meta(fei_row.status)
    return (
        group not in _CHUA_PHAT_HANH
        and group not in _NHOM_LOI
        and group not in _NHOM_NHAP
    )


def chon_ban_ghi_chinh(ho_so):
    """Chọn bản ghi THÔ (không phải khối hiển thị `_muc_cho`) "chính" trong
    một tập — dùng ở endpoint tải khi client không chỉ định rõ `fei` nào.
    Cùng quy tắc ưu tiên `_UU_TIEN_CHINH` với `_chon_chinh` (khối hiển thị),
    tách hàm riêng vì endpoint tải cần field thô (`official_pdf`, ...) mà
    khối hiển thị cố tình không giữ (BR-E4 — không lộ đường dẫn file)."""
    return min(
        enumerate(ho_so),
        key=lambda cap: (_UU_TIEN_CHINH.get(_meta(cap[1].status)[0], 1), -cap[0]),
    )[1]


# =========================================================================
# KHỐI HOÁ ĐƠN NHÁP — neo theo DELIVERY NOTE, không phải Sales Invoice.
#
# Đây là đường đọc THỨ HAI của cùng một dữ liệu. Nó KHÔNG thay `block_for`
# (trang Hoá đơn & công nợ vẫn dùng đường kia, và Task 1 đã dạy đường kia
# gọi đúng tên nhóm `nhap`) — nó tồn tại vì một lý do khác hẳn:
#
# `builder.create_from_delivery_note` — luồng THẬT sinh bản ghi HĐĐT — chỉ
# gán `fei.delivery_note`, KHÔNG gán `fei.sales_invoice`. Nếu Miyano lập
# Sales Invoice sau (gộp cuối kỳ) thì ngay tại thời điểm chứng từ HĐĐT vừa
# được lập, chưa có Sales Invoice nào để `block_for` bám vào — khách sẽ
# không thấy gì trên màn chi tiết đơn hàng.
#
# Hai đường phải luôn nói CÙNG một điều về cùng một chứng từ; chốt bằng
# `TestHaiDuongDocKhopNhau`.
# =========================================================================

# Suy TỪ `_STATUS_META` chứ không khai tay lần thứ hai: một tập trạng thái
# khai ở hai nơi là hai nơi lệch nhau được. Xem
# `test_nhap_statuses_suy_tu_status_meta`.
_NHAP_STATUSES = tuple(ma for ma, (nhom, _l, _b) in _STATUS_META.items() if nhom in _NHOM_NHAP)

_FIELDS_NHAP = (
    "name", "creation", "modified", "status", "invoice_type", "invoice_date",
    "amount", "tax_amount", "total_amount", "discount_amount", "amount_in_words",
    "draft_pdf", "customer", "delivery_note",
)

_FIELDS_DONG = (
    "idx", "item_code", "item_name", "uom", "qty", "price", "amount",
    "discount_amount", "tax_rate", "tax_amount", "note",
)


def ban_nhap_tho(delivery_note, dn_customer, fields=_FIELDS_NHAP):
    """Bản ghi HĐĐT còn ở vòng nháp của MỘT phiếu giao — hàng THÔ (còn
    `draft_pdf`), dành cho endpoint tải file. `None` nếu không có.

    Trả bản MỚI NHẤT khi khớp nhiều: `builder._assert_no_live_invoice` chỉ
    cho một bản ghi "sống" trên mỗi phiếu giao, nhưng `lineage._COPIED_FIELDS`
    copy `delivery_note` sang bản điều chỉnh/thay thế — nên một phiếu giao ĐÃ
    phát hành hoá đơn vẫn có thể có thêm một bản NHÁP mới (hoá đơn điều chỉnh
    đang soạn). Bản đang soạn dở là bản khách cần xem, nên mới nhất thắng.

    KHÔNG kiểm quyền (như `resolve_all`) nhưng LUÔN tự đối chiếu
    `fei.customer` — một bản ghi bị kế toán gõ nhầm khách không lọt ra cổng
    dù phiếu giao đọc được đã đúng chủ. KHÔNG gọi `check_enabled()`: tích hợp
    Fast có thể bị tắt, tắt không được làm chết cả trang chi tiết đơn.
    """
    rows = frappe.get_all(
        FEI,
        filters={"delivery_note": delivery_note, "status": ["in", list(_NHAP_STATUSES)]},
        fields=list(fields),
        order_by="creation asc",
    )
    rows = [r for r in rows if r.customer == dn_customer]
    return rows[-1] if rows else None


def dn_co_hoa_don_nhap(delivery_notes, dn_customer) -> set:
    """Tập con của `delivery_notes` đã có hoá đơn nháp — MỘT truy vấn cho cả
    danh sách, không phải một truy vấn mỗi phiếu giao.

    Chi tiết đơn hàng liệt kê mọi đợt giao của một đơn (`dot_giao[]` sinh ra
    chính vì giao nhiều đợt là chuyện thường ở đây), nên hỏi từng phiếu một
    là N round-trip cho một màn hình. Chỉ lấy CỜ, không kéo dòng hàng/tổng
    tiền — nội dung đi qua `nhap_cho_delivery_note` khi khách bấm xem."""
    delivery_notes = list(delivery_notes or [])
    if not delivery_notes:
        return set()
    rows = frappe.get_all(
        FEI,
        filters={"delivery_note": ["in", delivery_notes], "status": ["in", list(_NHAP_STATUSES)]},
        fields=["delivery_note", "customer"],
    )
    return {r.delivery_note for r in rows if r.customer == dn_customer}


def la_ban_nhap(fei_row):
    """`True` nếu bản ghi còn ở vòng nháp (01–04). Cặp đối xứng với
    `co_the_tai` — một hàm gác đường hoá đơn chính thức, một hàm gác đường
    bản nháp; cả hai cùng đọc `_meta` nên không bao giờ lệch định nghĩa
    nhóm."""
    group, _label, _badge = _meta(fei_row.status)
    return group in _NHOM_NHAP


def _dong_cua(fei_name):
    return frappe.get_all(
        "Fast EInvoice Line",
        filters={"parent": fei_name, "parenttype": FEI},
        fields=list(_FIELDS_DONG),
        order_by="idx asc",
    )


def nhap_cho_delivery_note(delivery_note, dn_customer):
    """Khối "Hoá đơn nháp" cho MỘT phiếu giao — JSON-hoá được thẳng cho SPA,
    hoặc `None` khi kế toán chưa lập chứng từ HĐĐT cho phiếu giao này.

    KHÔNG BAO GIỜ đưa `draft_pdf` (đường dẫn file) vào dict trả về — cùng
    ràng buộc "không có URL file công khai" (BR-E4 / quyết định nền tảng #8)
    đã áp cho `official_pdf` ở `block_for`. Chỉ cờ `nhap_tai_duoc`; file thật
    đi qua `portal_einvoice_nhap_pdf`, kiểm sở hữu lại từ đầu mỗi lần tải.

    Dòng hàng ở đây là DỰ PHÒNG cho giao diện: thứ khách cần thấy trước hết
    là chính file PDF do Fast dựng, bảng số liệu này chỉ để có cái mà xem khi
    Fast chưa dựng xong (trạng thái 01) hoặc gọi Fast lỗi.
    """
    fei = ban_nhap_tho(delivery_note, dn_customer)
    if not fei:
        return None

    return {
        "fei": fei.name,
        "nhan": "Hoá đơn nháp",
        "canh_bao": CANH_BAO_NHAP,
        # `invoice_type` phân biệt bản nháp của hoá đơn GỐC với bản điều
        # chỉnh/thay thế đang soạn cho cùng phiếu giao — hai thứ khác hẳn
        # nhau về ý nghĩa, gọi chung "hoá đơn nháp" là giấu mất một nửa.
        "loai": fei.invoice_type or "",
        "ngay": fei.invoice_date,
        "tien_hang": fei.amount,
        "tien_thue": fei.tax_amount,
        "chiet_khau": fei.discount_amount,
        "tong_tien": fei.total_amount,
        "bang_chu": fei.amount_in_words or "",
        "cap_nhat_luc": fei.modified,
        "nhap_tai_duoc": bool(fei.draft_pdf),
        "dong": [
            {
                "stt": d.idx,
                "ma": d.item_code or "",
                "ten": d.item_name or "",
                "dvt": d.uom or "",
                "so_luong": d.qty,
                "don_gia": d.price,
                "thanh_tien": d.amount,
                "chiet_khau": d.discount_amount,
                "thue_suat": d.tax_rate or "",
                "tien_thue": d.tax_amount,
                "ghi_chu": d.note or "",
            }
            for d in _dong_cua(fei.name)
        ],
    }
