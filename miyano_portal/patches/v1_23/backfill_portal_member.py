"""Sinh `Portal Member` cho mọi tài khoản cổng đang có.

Trước patch này danh tính cổng suy từ `Contact.user` + `Dynamic Link`; sau
Task 5, `portal_context` chỉ còn đọc `Portal Member` — không có nhánh dự
phòng đọc `Contact` (xem docstring `get_portal_member` trong
`portal_context.py`). Patch này là cầu nối MỘT LẦN giữa hai thời kỳ: mọi
tài khoản cổng đang hoạt động trước 18/08/2026 phải có một bản ghi
`Portal Member` tương ứng, nếu không `get_allowed_customers()` của họ đột
ngột trả rỗng ngay sau khi site này migrate.

Tất cả tài khoản backfill đều thành `Quản lý` KHÔNG gắn khoa phòng ->
`pham_vi_don()` trả `{}` -> phạm vi vẫn là toàn bộ đơn của bệnh viện, y hệt
hành vi trước khi có đề án này. Đây là ràng buộc tự đặt cho cả đề án: không
làm phiền khách đang dùng.

Một bệnh viện lỡ có hai tài khoản (chưa xảy ra trên site nào tính tới
18/08/2026 — đã đo, 6 user / 6 khách thật trên erptest.local) thì tài khoản
CŨ NHẤT (theo `Contact.creation` sớm nhất) làm quản lý; các tài khoản còn
lại được tạo dạng `Quản lý` nhưng `active=0` — script backfill không có cơ
sở để suy ra khoa phòng thật của họ nên KHÔNG chọn hình `Nhân viên khoa`
(dù vòng sửa 2 đã nới `_chan_vai_tro_va_khoa_phong`/`_chan_thieu_ma_ngan`
để một `Nhân viên khoa` `active=0` chưa gán khoa cũng hợp lệ — xem
`portal_provision` trong `api/portal.py`, đường đó CỐ Ý dùng hình đó vì nó
biết chắc "đây là nhân viên khoa chờ gán", còn backfill thì không biết gì
về vai trò thật của tài khoản thừa). `Quản lý`+`active=0` chỉ còn là hình
NHẤT QUÁN VỚI DỮ LIỆU CŨ của backfill, không còn là hình DUY NHẤT hợp lệ
trên toàn hệ thống — hai đường cố ý khác hình nhau, không phải một sai
lệch cần hợp nhất. `_chan_hai_quan_ly` chỉ xét bản ghi `active=1` nên
không đụng tới quản lý đang hoạt động. Kèm Error Log liệt kê các tài
khoản đó để vận hành gán khoa phòng/mã ngắn rồi tự tay quyết vai trò và
bật lại.

QUAN TRỌNG: toàn bộ backfill đi qua `doc.insert()`, TUYỆT ĐỐI không dùng
`frappe.db.set_value()`/`doc.db_set()` — xem GIỚI HẠN ĐÃ BIẾT trong
docstring `_chan_hai_quan_ly` (portal_member.py): hai đường đó đi vòng qua
`validate()` hoàn toàn, không có ràng buộc DB nào đứng chặn. Code phía
server là đúng loại hay bị cám dỗ dùng `db_set` cho nhanh — patch này thì
không.
"""

import frappe


def execute():
	# order_by="creation asc": Contact được tạo càng sớm càng đại diện cho
	# tài khoản cổng càng CŨ. Dựa vào thứ tự nạp để suy "ai cũ nhất" thay vì
	# sort lại danh sách user (sort theo email không liên quan gì tới tuổi
	# tài khoản) — xem "quyết định tự đưa ra" trong task-5-report.md.
	contacts = frappe.get_all(
		"Contact", filters={"user": ["is", "set"]}, fields=["name", "user"],
		order_by="creation asc",
	)

	# customer -> [user...], thứ tự CŨ NHẤT trước, khử trùng lặp user (một
	# user có thể có nhiều Contact cùng trỏ một Customer — ca thật trên site
	# là "BVĐK Minh Đức", 3 Contact / 1 user).
	cap: dict[str, list[str]] = {}
	for c in contacts:
		khach_list = frappe.get_all(
			"Dynamic Link",
			filters={"parenttype": "Contact", "parent": c.name, "link_doctype": "Customer"},
			pluck="link_name",
		)
		for cust in khach_list:
			users = cap.setdefault(cust, [])
			if c.user not in users:
				users.append(c.user)

	can_xu_tay = []
	for cust, users in cap.items():
		for i, user in enumerate(users):
			if frappe.db.exists("Portal Member", {"user": user}):
				# User đã có Portal Member (chạy lại patch, hoặc tài khoản
				# mới hơn đã được portal_provision() cấp) — không đụng vào.
				continue
			la_quan_ly_dau_tien = i == 0
			frappe.get_doc({
				"doctype": "Portal Member",
				"user": user,
				"customer": cust,
				"vai_tro": "Quản lý",
				"active": 1 if la_quan_ly_dau_tien else 0,
			}).insert(ignore_permissions=True)
			if not la_quan_ly_dau_tien:
				can_xu_tay.append(f"{user} ({cust})")

	if can_xu_tay:
		frappe.log_error(
			title="Portal Member: bệnh viện có nhiều tài khoản, cần gán vai trò tay",
			message=(
				"Các tài khoản sau đã tạo ở trạng thái Quản lý nhưng TẮT "
				"(active=0) vì bệnh viện của họ đã có quản lý đang hoạt động "
				"(tài khoản cũ nhất theo Contact.creation). Backfill KHÔNG "
				"tạo dạng Nhân viên khoa vì không có cơ sở để đoán khoa phòng "
				"lẫn Mã ngắn khách hàng. Vận hành cần xem lại, quyết vai trò "
				"thật (Quản lý hay Nhân viên khoa + khoa phòng + Mã ngắn nếu "
				"cần), rồi bật lại: " + ", ".join(can_xu_tay)
			),
		)
