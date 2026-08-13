"""Adapter — khối HĐĐT hiển thị trên cổng khách hàng (E7, chỉ đọc).

`Fast EInvoice Document` (110 trường, `apps/erpnext/erpnext/einvoice/`) là
doctype của MODULE KHÁC (team Dev). File này là NƠI DUY NHẤT ánh xạ tên
trường thật của module đó sang dữ liệu cổng hiển thị — đổi mapping chỉ sửa ở
đây, không rải tên trường khắp `api/portal.py`/frontend (PRD E7 DoD).

Bản đồ dữ liệu ĐÃ KIỂM lại bằng cách đọc trực tiếp
`erpnext/einvoice/doctype/fast_einvoice_document/fast_einvoice_document.json`
và `erpnext/einvoice/*.py` — KHÔNG theo mù bảng "tên tạm" trong PRD/BA (các
trường `einvoice_*` trên `Sales Invoice` mà BA giả định KHÔNG TỒN TẠI). Ba
phát hiện quan trọng nhất, lệch với brief gốc:

1. **Liên kết chính KHÔNG phải `sales_invoice`.** `builder.py::
   create_from_delivery_note` — luồng tạo bản ghi HĐĐT DUY NHẤT của module —
   chỉ gán `fei.delivery_note`, không bao giờ gán `fei.sales_invoice`. Field
   `sales_invoice` có tồn tại nhưng KHÔNG bắt buộc (`reqd` không có trong
   JSON, trong khi `delivery_note` có) và không ai tự động điền — theo đúng
   docstring của `erpnext/einvoice/lookup.py`: "kế toán tự điền" là trường
   hợp PHỤ, đường CHÍNH là bắc cầu qua `Sales Invoice Item.delivery_note` ->
   `FEI.delivery_note`. `_resolve()` dưới đây implement lại đúng thứ tự ưu
   tiên đó (tầng 1 rồi mới tầng 2), nhưng KHÔNG lọc theo
   `lookup.DECLARABLE_STATUSES` như `lookup.invoice_numbers_for()` — cổng cần
   thấy cả trạng thái chưa phát hành / lỗi, không chỉ trạng thái đã kê khai
   thuế được.
2. **`amended_from_fei`** là nửa CÒN LẠI của liên kết hai chiều NL-12.2/12.3
   mà bảng map gốc trong brief bỏ sót (brief chỉ liệt `original_document`,
   là nửa NGƯỢC). `lineage.mark_original_superseded()` set field này trên
   bản ghi GỐC, trỏ TỚI bản ghi điều chỉnh/thay thế, ngay khi bản ghi con
   phát hành xong.
3. **Không có sự kiện nào để móc email "phát hành thành công" (US-E7.3).**
   Mọi lần đổi `status` sang "Đã phát hành" đều qua
   `frappe.db.set_value(..., update_modified=False)` (`issue.py::
   _store_issue_result`) — ghi thẳng DB, KHÔNG chạy qua vòng đời Document,
   nên `doc_events["Fast EInvoice Document"]["on_update"]` không bao giờ
   được gọi cho sự kiện này dù đăng ký trong `hooks.py` của app này (đã kiểm
   thực nghiệm: xem `on_change` cũng không chạy vì cùng lý do). Tự viết một
   scheduler job poll trạng thái là khả thi nhưng NẰM NGOÀI phạm vi brief
   này ("Việc phải làm" chỉ có 3 mục, không có mục này) — BÁO team HĐĐT thay
   vì tự vá. Vì lý do tương tự, patch backfill US-E7.3/TC-E7-06 KHÔNG cần
   viết: khối HĐĐT được TRA CỨU TRỰC TIẾP mỗi lần đọc (không sao chép dữ liệu
   sang field nào trên `Sales Invoice`), nên hoá đơn cũ tự động "sáng" ngay
   khi có `Fast EInvoice Document` khớp — không có gì để backfill.

Trạng thái 12 ("Đã hủy nội bộ") — `cancel.py::cancel_internally` chỉ hủy được
hóa đơn đang ở `09 - CQT từ chối`, và không có field nào nối bản ghi bị hủy
với hóa đơn mới lập cho CÙNG phiếu giao (nếu có) — CỐ Ý không suy đoán liên
kết đó qua `delivery_note` trùng, vì đó là BỊA lineage không có thật trong dữ
liệu. Báo đây là khoảng trống cho team HĐĐT, không tự vá bằng phỏng đoán.

An toàn dữ liệu (quyết định nền tảng #7/#8 của app): role `Customer` **không**
có DocPerm nào trên `Fast EInvoice Document` (đã kiểm thực nghiệm —
`frappe.has_permission("Fast EInvoice Document", "read", user=<khách>)` trả
`False`) — cổng không được thêm DocPerm mới. Module này KHÔNG BAO GIỜ gọi
`frappe.get_doc(FEI, ...)` với tên nhận từ client; mọi truy cập của
`api/portal.py` bắt đầu từ `Sales Invoice` (nơi khách CÓ quyền qua
`check_permission`), rồi mới dò sang `Fast EInvoice Document` và tự đối
chiếu `fei.customer == si.customer` trước khi tin bất kỳ dữ liệu nào — một
FEI bị kế toán gõ nhầm `sales_invoice` sang hoá đơn của khách khác sẽ bị vô
hiệu ở đây, không lộ ra cổng.
"""

import frappe

FEI = "Fast EInvoice Document"

# 14 mã trạng thái thật (erpnext/einvoice/constants.py) -> nhóm hiển thị cho
# khách + nhãn tiếng Việt + class badge. KHÔNG BAO GIỜ phơi mã số thô
# ("06 - Đã phát hành") ra JSON trả về cổng — chỉ nhóm + nhãn đã dịch.
_STATUS_META = {
    "01 - Nháp": ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray"),
    "02 - Đã xem nháp": ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray"),
    "03 - Chờ khách duyệt": ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray"),
    "04 - Khách đã duyệt": ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray"),
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

# NL-12.1: nhóm "chưa phát hành" — không nút tải, không phải lỗi.
_CHUA_PHAT_HANH = {"dang_phat_hanh"}
# NL-12.4: nhóm "lỗi" — nút tải disable + nút Yêu cầu hỗ trợ, BẤT KỂ file có
# hay không (98/99 nghĩa là bản ghi tự nó có vấn đề, không phải "đang chờ").
_NHOM_LOI = {"loi"}

# Field cần cho khối hiển thị + đối chiếu sở hữu. CỐ Ý KHÔNG gồm
# `fast_key_search` (khoá tích hợp nội bộ dùng để gọi Fast, không phải mã tra
# cứu cho khách — đó là `tax_verification_code`) và không gồm giá trị file
# nào khác ngoài việc TỰ nó (xem ghi chú `official_pdf` trong `block_for`).
_FIELDS = (
    "name", "status", "invoice_type", "fast_invoice_no", "fast_serial",
    "fast_signed_date", "issued_time", "tax_verification_code",
    "official_pdf", "original_document", "amended_from_fei",
    "cancel_reason", "customer", "sales_invoice", "delivery_note",
)


def _meta(status):
    return _STATUS_META.get(status, _MAC_DINH)


def resolve(sales_invoice_name):
    """Tìm bản ghi `Fast EInvoice Document` khớp một `Sales Invoice`.

    Trả `frappe._dict` đủ `_FIELDS`, hoặc `None` nếu chưa có bản ghi nào (kế
    toán chưa bắt đầu quy trình HĐĐT cho hoá đơn này — với khách, trạng thái
    đó hiển thị y hệt "Đang phát hành HĐĐT" như trạng thái 01-05, xem
    `block_for`).

    KHÔNG kiểm quyền ở đây — hàm này chỉ tra cứu. Người gọi (`block_for` /
    `portal_einvoice_download`) chịu trách nhiệm đối chiếu `customer` trước
    khi dùng bất kỳ trường nào trả về.
    """
    truc_tiep = frappe.get_all(
        FEI, filters={"sales_invoice": sales_invoice_name},
        fields=_FIELDS, order_by="creation desc", limit=1,
    )
    if truc_tiep:
        return truc_tiep[0]

    dn_names = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": sales_invoice_name, "delivery_note": ["!=", ""]},
        pluck="delivery_note",
    )
    dn_names = list(dict.fromkeys(dn_names))
    if not dn_names:
        return None

    qua_dn = frappe.get_all(
        FEI, filters={"delivery_note": ["in", dn_names]},
        fields=_FIELDS, order_by="creation desc", limit=1,
    )
    return qua_dn[0] if qua_dn else None


def _lineage_ref(fei_name, customer):
    """Thông tin rút gọn của một bản ghi liên quan (gốc hoặc bản thay thế),
    dùng cho link hai chiều NL-12.2/12.3. Trả `None` nếu không tìm thấy HOẶC
    khách của bản ghi liên quan không khớp — không lộ dữ liệu hoá đơn của
    khách khác qua một liên kết lineage sai."""
    if not fei_name:
        return None
    row = frappe.db.get_value(
        FEI, fei_name,
        ["fast_invoice_no", "fast_serial", "status", "customer"],
        as_dict=True,
    )
    if not row or row.customer != customer:
        return None
    group, label, badge = _meta(row.status)
    return {
        "fei": fei_name,
        "so": row.fast_invoice_no or "",
        "ky_hieu": row.fast_serial or "",
        "trang_thai": group,
        "nhan": label,
        "badge": badge,
    }


def block_for(sales_invoice_name, sales_invoice_customer):
    """Khối HĐĐT cho MỘT hoá đơn — trả dict JSON-hoá được thẳng cho SPA.

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
    fei = resolve(sales_invoice_name)
    if not fei or fei.customer != sales_invoice_customer:
        group, label, badge = _MAC_DINH
        return {
            "fei": None, "trang_thai": group, "nhan": label, "badge": badge,
            "tai_duoc": False, "ho_tro": False,
        }

    group, label, badge = _meta(fei.status)
    ho_tro = group in _NHOM_LOI
    co_file = bool(fei.official_pdf)
    tai_duoc = group not in _CHUA_PHAT_HANH and group not in _NHOM_LOI and co_file

    # NL-12.4 — "File XML/PDF thiếu hoặc hỏng": trạng thái ĐÃ phát hành
    # (issue.py::_queue_pdf_download chạy NỀN, có độ trễ ký số HSM) nhưng
    # file vẫn chưa đính — khác hẳn "đang phát hành" (01-05, còn ở Desk) và
    # khác "lỗi" (98/99, bản ghi tự nó hỏng): đây là chờ file, cần nhãn riêng
    # + vẫn cho khách yêu cầu hỗ trợ nếu chờ lâu.
    if group not in _CHUA_PHAT_HANH and group not in _NHOM_LOI and not co_file:
        label = f"{label} — file đang xử lý"
        ho_tro = True

    block = {
        "fei": fei.name,
        "trang_thai": group,
        "nhan": label,
        "badge": badge,
        "so": fei.fast_invoice_no or "",
        "ky_hieu": fei.fast_serial or "",
        "ngay_phat_hanh": fei.fast_signed_date,
        "ma_tra_cuu": fei.tax_verification_code or "",
        "tai_duoc": tai_duoc,
        "ho_tro": ho_tro,
    }
    goc = _lineage_ref(fei.original_document, sales_invoice_customer)
    if goc:
        block["hoa_don_goc"] = goc
    moi = _lineage_ref(fei.amended_from_fei, sales_invoice_customer)
    if moi:
        block["hoa_don_moi"] = moi
    return block


def sua_duoc_tai(fei_row):
    """`True` nếu nhóm hiển thị của bản ghi cho phép tải — dùng lại đúng quy
    tắc của `block_for` ở `portal_einvoice_download` (không viết lại logic
    lần hai, tránh hai nơi lệch nhau)."""
    group, _label, _badge = _meta(fei_row.status)
    return group not in _CHUA_PHAT_HANH and group not in _NHOM_LOI
