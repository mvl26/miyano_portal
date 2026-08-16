"""Ba field trên `Sales Order` cho việc Miyano hẹn lại lịch giao.

Nhu cầu chủ đầu tư 2026-08-16 (vai nhân viên): "khi chưa có hàng tôi muốn
thông báo lại cho khách hàng về hàng thiếu và sẽ vận chuyển sau hoặc đổi ngày
giao hàng". Trước bản này chỉ có một ô ghi chú tự do trên biên bản kiểm hàng —
không hiện được lên cổng, không thành cam kết, và không dùng được cho trường
hợp Miyano biết thiếu hàng TRƯỚC khi giao.

`allow_on_submit=1`: đơn đã xác nhận rồi mới phát sinh việc hẹn lại — đó là
toàn bộ tình huống. `read_only=1`: chỉ đặt qua
`miyano_portal.portal_hen_giao.hen_giao_lai`, hàm đó mới là chỗ ghi lịch sử
và bắn thông báo cho khách. Sửa tay trên form sẽ đổi con số mà khách không
bao giờ được biết.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_sec_hen_giao",
                    "label": "Hẹn lịch giao",
                    "fieldtype": "Section Break",
                    "insert_after": "custom_dat_ngoai",
                    "collapsible": 1,
                    "depends_on": "eval:doc.custom_ngay_hen_giao",
                },
                {
                    "fieldname": "custom_loai_hen_giao",
                    "label": "Loại hẹn giao",
                    "fieldtype": "Select",
                    "options": "\nSẽ giao bù\nĐã đổi ngày giao",
                    "insert_after": "custom_sec_hen_giao",
                    "allow_on_submit": 1,
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_ngay_hen_giao",
                    "label": "Ngày hẹn giao",
                    "fieldtype": "Date",
                    "insert_after": "custom_loai_hen_giao",
                    "allow_on_submit": 1,
                    "read_only": 1,
                },
                {
                    "fieldname": "custom_ly_do_hen_giao",
                    "label": "Lý do / nội dung báo khách",
                    "fieldtype": "Small Text",
                    "insert_after": "custom_ngay_hen_giao",
                    "allow_on_submit": 1,
                    "read_only": 1,
                },
            ],
        },
        ignore_validate=True,
    )
