"""Tự lập chứng từ HĐĐT khi submit Sales Invoice — E7b.

Nơi DUY NHẤT của app này gọi vào module HĐĐT của team khác
(`apps/erpnext/erpnext/einvoice/`). Đổi chữ ký
`builder.create_from_sales_invoice` / `create_from_delivery_note` hay
`actions.preview_draft` là vỡ đúng file này, không rải ra chỗ khác — xem
`docs/HDDT-ban-giao-team-module.md`.

**Hai bản module HĐĐT** (erpnext 0f08cd32, 14/10/2026): bản 3.0 lập hoá đơn
điện tử từ CHÍNH Sales Invoice (`create_from_sales_invoice`, một hoá đơn bán
một chứng từ) và đóng hẳn đường phát hành theo phiếu giao
(`create_from_delivery_note` chỉ còn `frappe.throw`). Bản 2.0 thì ngược lại.
Site chạy bản nào thì đi đường đó — nhận biết bằng việc builder CÓ
`create_from_sales_invoice` hay không, để app này chạy được trên cả hai trong
lúc các site lần lượt lên bản 3.0.

**Tự động tới đâu, và vì sao dừng ở đó** (quyết định Q1 của spec): job chạy
hai nút đầu của quy trình — tạo chứng từ, rồi lấy bản in thử PDF từ Fast — và
**dừng ở `02 - Đã xem nháp`**. KHÔNG gọi `send_draft_to_customer`. Kế toán
phải được liếc bản nháp trước khi nó vào hộp thư khách; khách thì vẫn xem
được ngay trên cổng nên không ai phải chờ email. Nút "Gửi bản nháp cho khách"
ở Desk mở đúng từ trạng thái 02 (`form_state.py::BUTTONS`, đã kiểm) nên kế
toán bấm tiếp được ngay — nếu nút đó phụ thuộc thêm một cờ mà chỉ thao tác
tay mới đặt thì cả quyết định này sụp, nên đừng sửa chỗ dừng mà không kiểm
lại điều kiện của nút.
"""

import frappe
from frappe import _

SI = "Sales Invoice"


def tu_sales_invoice(doc, method=None):
    """Hook `Sales Invoice.on_submit` — CHỈ đẩy việc vào hàng đợi.

    Không bao giờ ném lỗi ra ngoài (quyết định nền tảng #4, cùng nguyên tắc
    `kho/delivery_hook._chay_an_toan`): lập HĐĐT là hiệu ứng phụ, không có
    quyền chặn việc xuất hoá đơn bán hàng.

    Cũng KHÔNG gọi Fast tại đây: một lời gọi Fast có thể mất tới 120 giây
    (`fast_client.REQUEST_TIMEOUT_SECONDS`), đặt trong `on_submit` là bắt kế
    toán ngồi chờ và biến một sự cố mạng thành lỗi không submit được hoá đơn.

    Bỏ qua hoá đơn trả hàng: builder (cả hai bản) từ chối thẳng
    phiếu trả hàng ("phiếu trả hàng không lập hóa đơn trực tiếp — dùng hóa
    đơn điều chỉnh giảm từ hóa đơn gốc"), nên không lọc sớm thì mỗi lần lập
    giấy báo có là một Comment lỗi vô nghĩa trên chứng từ.
    """
    if doc.get("is_return"):
        return
    try:
        frappe.enqueue(
            "miyano_portal.hddt_tu_dong.lap_hddt_cho_hoa_don",
            queue="long",
            timeout=600,
            sales_invoice=doc.name,
        )
    except Exception:
        frappe.log_error(title=f"HĐĐT: không đẩy được job lập hoá đơn cho {doc.name}")


def lap_hddt_cho_hoa_don(sales_invoice, client=None) -> dict:
    """Lập chứng từ HĐĐT + lấy bản in thử PDF cho hoá đơn bán.

    Bản 3.0: MỘT chứng từ cho cả hoá đơn bán. Bản 2.0: một chứng từ cho TỪNG
    phiếu giao của hoá đơn (xem docstring module).

    Trả `{"tao": [tên chứng từ], "bo_qua": [{nguon, ly_do}],
    "ly_do": str | None}`. `nguon` là tên hoá đơn bán (bản 3.0) hoặc phiếu
    giao (bản 2.0). `ly_do` chỉ có giá trị khi dừng cho CẢ hoá đơn (không có
    phiếu giao nào ở bản 2.0, hoặc tích hợp Fast đang tắt).

    `client` để test tiêm `FastClient` giả — đường sản xuất luôn để `None`.
    """
    from erpnext.einvoice import builder
    from erpnext.einvoice.fast_settings import check_enabled

    ket_qua = {"tao": [], "bo_qua": [], "ly_do": None}

    # Chứng từ có thể không còn tồn tại vào lúc worker chạy: job được đẩy ở
    # `on_submit` nhưng chạy sau đó vài giây tới vài phút, và trong khoảng đó
    # hoá đơn có thể đã bị xoá. Không chốt ở đây thì `_ghi_comment` ném
    # `DoesNotExistError` — đo thật trên bench: mỗi lượt chạy test suite để
    # lại 75 Error Log rác đúng vì lý do này (test rollback giao dịch, worker
    # nhặt job sau đó và không còn thấy Sales Invoice nào).
    if not frappe.db.exists(SI, sales_invoice):
        return ket_qua

    ban_3 = la_ban_3()
    if ban_3:
        nguon = [sales_invoice]
    else:
        nguon = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": sales_invoice, "delivery_note": ["!=", ""]},
            pluck="delivery_note",
        )
        nguon = list(dict.fromkeys(nguon))
        if not nguon:
            ket_qua["ly_do"] = _("Hoá đơn không qua phiếu giao nào — không lập HĐĐT tự động.")
            _ghi_comment(sales_invoice, ket_qua)
            return ket_qua

    # Kiểm công tắc MỘT lần cho cả hoá đơn: tắt là tắt cho mọi chứng từ. Và
    # đây là CẤU HÌNH chứ không phải sự cố, nên không `log_error` — ghi log
    # lỗi cho một site cố tình chưa bật Fast là tạo nhiễu, không tạo tín hiệu.
    try:
        check_enabled()
    except Exception as e:
        ket_qua["ly_do"] = str(e)
        _ghi_comment(sales_invoice, ket_qua)
        return ket_qua

    tao = builder.create_from_sales_invoice if ban_3 else builder.create_from_delivery_note
    for ten in nguon:
        # Bọc lỗi TỪNG CHỨNG TỪ NGUỒN: một phiếu vướng luật kiểm (thiếu MST,
        # quá 300 dòng, tổng tiền lệch...) không được kéo theo các phiếu còn
        # lại của cùng hoá đơn.
        try:
            fei = tao(ten)
        except Exception as e:
            ket_qua["bo_qua"].append({"nguon": ten, "ly_do": str(e)})
            continue

        try:
            from erpnext.einvoice.actions import preview_draft

            preview_draft(fei, client=client)
            ket_qua["tao"].append(fei)
        except Exception as e:
            # Chứng từ ĐÃ tạo được, chỉ chưa có PDF — để nguyên ở `01 - Nháp`
            # cho kế toán sửa dữ liệu rồi bấm lại nút "Xem bản nháp" ở Desk.
            # Vẫn tính vào `tao` vì bản ghi có thật; lý do hỏng ghi ở `bo_qua`.
            ket_qua["tao"].append(fei)
            ket_qua["bo_qua"].append({
                "nguon": ten,
                "ly_do": _("đã tạo {0} nhưng chưa dựng được PDF nháp: {1}").format(fei, e),
            })
            frappe.log_error(title=f"HĐĐT {fei}: không dựng được bản nháp PDF")

    _ghi_comment(sales_invoice, ket_qua)
    return ket_qua


def la_ban_3() -> bool:
    """Module HĐĐT của site là bản 3.0 (lập từ Sales Invoice)."""
    from erpnext.einvoice import builder

    return hasattr(builder, "create_from_sales_invoice")


def _ghi_comment(sales_invoice, ket_qua):
    """Một Comment tổng kết trên chính Sales Invoice.

    Đây là nơi DUY NHẤT kế toán biết job đã chạy hay chưa, phiếu nào ra chứng
    từ nào, phiếu nào bị bỏ và vì sao. Chủ dự án đã chốt: giữ Comment, không
    bắn Notification cho role Kế toán HĐĐT."""
    dong = []
    if ket_qua["ly_do"]:
        dong.append(ket_qua["ly_do"])
    if ket_qua["tao"]:
        dong.append(_("Đã lập chứng từ HĐĐT: {0}").format(", ".join(ket_qua["tao"])))
    for b in ket_qua["bo_qua"]:
        dong.append(_("{0}: {1}").format(b["nguon"], b["ly_do"]))
    if not dong:
        return
    frappe.get_doc(SI, sales_invoice).add_comment("Comment", "<br>".join(dong))
