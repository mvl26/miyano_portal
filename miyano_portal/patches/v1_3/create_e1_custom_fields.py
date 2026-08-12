from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Custom field của Epic E1.

    `create_custom_fields` idempotent sẵn: gọi lại chỉ cập nhật thuộc tính,
    không sinh bản ghi thứ hai.

    **`custom_boi_so_dat` KHÔNG có trong `20_DataDict.md` §4.** PRD E1 chỉ
    viết "bội số đặt của item Miyano lấy từ Item" mà không nêu tên trường,
    và CSDL không có cột nào tương tự. Tên được chốt ở đây theo đúng khuôn
    `custom_*` của bốn custom field `Sales Order` đang có. Đổi tên sau khi
    patch đã chạy là đổi schema đã cài — quyết định bây giờ, đừng để sau.
    """
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_boi_so_dat",
                    "label": "Bội số đặt",
                    "fieldtype": "Int",
                    "insert_after": "stock_uom",
                    "description": (
                        "Số lượng đặt trên cổng phải là bội số của số này. "
                        "Để trống hoặc 0 = không ràng buộc."
                    ),
                }
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_request_id",
                    "label": "Mã yêu cầu (chống trùng đơn)",
                    "fieldtype": "Data",
                    # `unique` là chốt chặn THẬT của BR-O12: CSDL làm trọng
                    # tài, không phải một phép kiểm trước-khi-ghi. Kiểm rồi
                    # ghi vẫn để lọt hai đơn khi hai tiến trình cùng đọc thấy
                    # "chưa có" (TC-E1-02).
                    "unique": 1,
                    "read_only": 1,
                    # Không copy sang bản amend/duplicate: mã yêu cầu thuộc về
                    # đúng một lần bấm của khách, nhân bản nó sẽ đụng unique.
                    "no_copy": 1,
                    "insert_after": "custom_nguon_don",
                    "description": (
                        "Sinh bởi cổng khi mở màn xác nhận. Gửi lại cùng mã "
                        "trả về đúng đơn đã tạo thay vì tạo đơn thứ hai."
                    ),
                }
            ],
        },
        ignore_validate=True,
    )
