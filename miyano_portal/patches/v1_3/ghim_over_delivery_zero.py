import frappe


def execute():
    """Ghim over-delivery allowance = 0 (QĐ-2, BR-O10).

    Trường nằm ở `Stock Settings` — **KHÔNG** phải `Selling Settings` như
    PRD E3 ghi (đã kiểm `tabSingles` trên `erptest.local`). `Item` có một
    trường cùng tên, ghi đè theo từng mặt hàng.

    Tại thời điểm viết patch, giá trị trên site đã là 0 và không `Item` nào
    ghi đè — tức hành vi mong muốn đang đúng, nhưng chỉ vì mặc định của
    framework. Patch này biến "tình cờ đúng" thành "đúng theo thiết kế": sau
    khi cài app lên một site mới, hoặc sau khi ai đó đổi tay rồi migrate lại,
    giá trị vẫn về 0.

    Chỉ ghi khi đang khác 0 — chạy lại nhiều lần không sinh thay đổi thừa và
    không đụng `modified` của Single khi không cần.
    """
    hien_tai = frappe.db.get_single_value(
        "Stock Settings", "over_delivery_receipt_allowance"
    )
    if (hien_tai or 0) != 0:
        frappe.db.set_single_value(
            "Stock Settings", "over_delivery_receipt_allowance", 0
        )

    # Ngoại lệ theo từng mặt hàng làm rỗng nghĩa của cấu hình chung: một Item
    # khai allowance > 0 vẫn giao vượt được dù Stock Settings đã khoá.
    #
    # CỐ Ý không tự xoá — chỉ ghi log để người vận hành quyết định. Một ngoại
    # lệ có thể do nghiệp vụ thật (hàng cân, hàng đong, đóng gói theo thùng
    # lẻ) chứ không phải cấu hình nhầm, và một patch âm thầm sửa dữ liệu
    # nghiệp vụ của người khác là thứ không ai muốn phát hiện sau ba tháng.
    ngoai_le = frappe.get_all(
        "Item",
        filters={"over_delivery_receipt_allowance": [">", 0]},
        fields=["name", "over_delivery_receipt_allowance"],
    )
    if ngoai_le:
        frappe.log_error(
            title="QĐ-2: mặt hàng mở ngoại lệ giao vượt",
            message=frappe.as_json(ngoai_le),
        )
