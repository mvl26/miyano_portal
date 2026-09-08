"""Thêm `Sales Order.custom_ten_don_hang` — TÊN ĐƠN HÀNG do nhân viên gõ.

Chủ đầu tư 08/09/2026: *"khi trong giỏ hàng em thêm 1 trường là tên đơn hàng
để nhân viên điền vào khi đặt hàng, và tên này cũng được hiển thị tại list
đơn hàng"*.

VÌ SAO CHÉP LÊN ĐƠN chứ không chỉ để trên phiếu: tên do khách gõ ở giỏ hàng
sống trên `Portal De Xuat Mua.ten_don_hang`, nhưng danh sách yêu cầu ở cổng
là UNION hai nhánh (`portal_yeu_cau_cua_toi`) — nhánh thứ hai đọc THẲNG từ
`Sales Order` cho những đơn không đứng sau phiếu nào. Không có cột này thì
đúng nhánh đó không bao giờ hiện được tên. Và chủ đầu tư gọi nó là *tên ĐƠN
HÀNG*, không phải tên phiếu: nó phải đọc được ở phía Miyano trên chính đơn,
nơi người xử lý đứng.

Chép GIÁ TRỊ, không đọc chéo qua `custom_de_xuat` mỗi lần — cùng lý do
`custom_ma_tra_cuu` (patch v1_24) đã chép `ma_de_xuat`: role `Customer` có
zero DocPerm trên `Portal De Xuat Mua` (§5.1), mở một đường đọc chéo doctype
chỉ để lấy một chuỗi là mở rộng bề mặt quyền cho một việc hiển thị.

KHÔNG `read_only`: khác `custom_ma_tra_cuu` (mã hệ thống cấp). Đây là tên do
NGƯỜI đặt, và nhân viên Miyano phải sửa được khi khách gõ nhầm — đơn cũ /
đơn đặt thẳng không qua đề xuất cũng cần đặt tên được.

Đơn CŨ để trống — hợp lệ, không phải lỗi: không ai từng gõ tên cho chúng.
Cố ý KHÔNG backfill từ phiếu: một cái tên bịa ra cho 102 đơn cũ nói dối
rằng có người đã đặt tên chúng.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Sales Order", {
		"fieldname": "custom_ten_don_hang",
		"label": "Tên đơn hàng",
		"fieldtype": "Data",
		"insert_after": "custom_ma_tra_cuu",
	})
