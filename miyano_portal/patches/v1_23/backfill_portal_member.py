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
(dù vòng sửa 2 đã nới `_chan_vai_tro_va_khoa_phong` để một `Nhân viên khoa`
`active=0` chưa gán khoa cũng hợp lệ — xem `portal_provision` trong
`api/portal.py`, đường đó CỐ Ý dùng hình đó vì nó biết chắc "đây là nhân
viên khoa chờ gán", còn backfill thì không biết gì về vai trò thật của tài
khoản thừa; vòng sửa 3 cũng đã revert việc nới `_chan_thieu_ma_ngan` — Mã
ngắn là dữ liệu của Miyano, không phải lý do để backfill né tránh).
`Quản lý`+`active=0` chỉ còn là hình NHẤT QUÁN VỚI DỮ LIỆU CŨ của backfill,
không còn là hình DUY NHẤT hợp lệ trên toàn hệ thống — hai đường cố ý khác
hình nhau, không phải một sai lệch cần hợp nhất. `_chan_hai_quan_ly` chỉ
xét bản ghi `active=1` nên không đụng tới quản lý đang hoạt động. Kèm Error
Log liệt kê các tài khoản đó để vận hành gán khoa phòng/mã ngắn rồi tự tay
quyết vai trò và bật lại.

QUAN TRỌNG: toàn bộ backfill đi qua `doc.insert()`, TUYỆT ĐỐI không dùng
`frappe.db.set_value()`/`doc.db_set()` — xem GIỚI HẠN ĐÃ BIẾT trong
docstring `_chan_hai_quan_ly` (portal_member.py): hai đường đó đi vòng qua
`validate()` hoàn toàn, không có ràng buộc DB nào đứng chặn. Code phía
server là đúng loại hay bị cám dỗ dùng `db_set` cho nhanh — patch này thì
không.

VÒNG SỬA 3 (F5, review độc lập, Important — SỬA TRONG CHÍNH FILE PATCH
CŨ, không viết patch mới): patch này mới cháy lượt chạy DUY NHẤT trên
`erptest.local` (6/6 tài khoản đã kiểm đúng, không đổi hình dữ liệu ở đó)
và CHƯA từng chạy trên site prod `miyano` — sửa ngay trong file này vẫn
tới được prod ở lần `migrate` kế tiếp, không cần một `v1_23` patch khác
chạy nối theo. Ba lỗ đã vá:

1. KHÔNG lọc `User.user_type` trước bản sửa này: một `Contact` của NHÂN
   VIÊN MIYANO (không phải khách hàng) mà có `user` và một `Dynamic Link`
   trỏ sang `Customer` (ví dụ nhân viên sales từng được gắn liên hệ với
   khách) vẫn bị patch coi là một "tài khoản cổng" của khách hàng đó. Nếu
   `Contact` đó cũ hơn `Contact` thật của khách, nó CHIẾM mất suất quản lý
   duy nhất — tài khoản bệnh viện thật bị đẩy xuống `active=0`, tức khách
   hàng thật không đăng nhập dùng được sau `migrate`. Vá: chỉ xét
   `User.user_type == "Website User"`.

2. `la_quan_ly_dau_tien = i == 0` chỉ nhìn vào THỨ TỰ TRONG DANH SÁCH
   VỪA GOM, không nhìn vào DB — nếu bệnh viện đó đã có sẵn một `Portal
   Member` `Quản lý`/`active=1` (ví dụ do `portal_provision()`/
   `seed_demo()` tạo trước khi patch này chạy), patch vẫn cố chèn thêm một
   quản lý `active=1` thứ hai ở `i==0`, và `_chan_hai_quan_ly` NÉM LỖI
   GIỮA `bench migrate`, bỏ dở toàn bộ migration (kể cả các patch khác xếp
   sau). Vá: kiểm `frappe.db.exists("Portal Member", {"customer": cust,
   "vai_tro": "Quản lý", "active": 1})` trước khi quyết định, không chỉ
   dựa vào `i`.

3. Một bản ghi hỏng (dữ liệu bẩn không lường trước, ví dụ `Customer` đã bị
   xoá nhưng `Dynamic Link` còn trỏ tới) trước đây sẽ ném lỗi giữa vòng lặp
   và bỏ dở migration. Vá: bọc thân vòng lặp trong `try/except`, ghi Error
   Log cho TỪNG bản ghi lỗi kèm traceback rồi ĐI TIẾP — một bệnh viện dữ
   liệu bẩn không được phép chặn toàn bộ site migrate.
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

	# VÒNG SỬA 3, vá #1: chỉ tài khoản cổng (Website User) mới là ứng viên
	# Portal Member. Một Contact của nhân viên Miyano (System User) vô tình
	# có Dynamic Link sang Customer không được phép chiếm suất quản lý.
	website_users = set(
		frappe.get_all("User", filters={"user_type": "Website User"}, pluck="name")
	)
	contacts = [c for c in contacts if c.user in website_users]

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
	loi = []
	for cust, users in cap.items():
		# VÒNG SỬA 3, vá #2: hỏi DB xem bệnh viện này ĐÃ có quản lý đang
		# hoạt động chưa — không suy diễn thuần từ vị trí trong danh sách
		# (i == 0). Cập nhật cờ này ngay sau khi tự patch tạo một quản lý,
		# để không tự chèn hai quản lý active=1 trong cùng một lượt chạy.
		da_co_quan_ly = bool(frappe.db.exists(
			"Portal Member", {"customer": cust, "vai_tro": "Quản lý", "active": 1}
		))
		for user in users:
			if frappe.db.exists("Portal Member", {"user": user}):
				# User đã có Portal Member (chạy lại patch, hoặc tài khoản
				# mới hơn đã được portal_provision() cấp) — không đụng vào.
				continue
			la_quan_ly_moi = not da_co_quan_ly
			# VÒNG SỬA 3, vá #3: một bản ghi hỏng không được phép bỏ dở
			# migrate — ghi Error Log rồi đi tiếp, không throw ra ngoài.
			try:
				frappe.get_doc({
					"doctype": "Portal Member",
					"user": user,
					"customer": cust,
					"vai_tro": "Quản lý",
					"active": 1 if la_quan_ly_moi else 0,
				}).insert(ignore_permissions=True)
			except Exception:
				loi.append(f"{user} ({cust})")
				frappe.log_error(
					title="Portal Member backfill: một bản ghi lỗi, đã bỏ qua",
					message=frappe.get_traceback(),
				)
				continue
			if la_quan_ly_moi:
				da_co_quan_ly = True
			else:
				can_xu_tay.append(f"{user} ({cust})")

	if can_xu_tay:
		frappe.log_error(
			title="Portal Member: bệnh viện có nhiều tài khoản, cần gán vai trò tay",
			message=(
				"Các tài khoản sau đã tạo ở trạng thái Quản lý nhưng TẮT "
				"(active=0) vì bệnh viện của họ đã có quản lý đang hoạt động "
				"(tài khoản cũ nhất theo Contact.creation, hoặc quản lý đã có "
				"sẵn từ trước khi patch chạy). Backfill KHÔNG tạo dạng Nhân "
				"viên khoa vì không có cơ sở để đoán khoa phòng lẫn Mã ngắn "
				"khách hàng. Vận hành cần xem lại, quyết vai trò thật (Quản "
				"lý hay Nhân viên khoa + khoa phòng + Mã ngắn nếu cần), rồi "
				"bật lại: " + ", ".join(can_xu_tay)
			),
		)

	if loi:
		frappe.log_error(
			title="Portal Member backfill: có bản ghi bị bỏ qua vì lỗi",
			message=(
				"Các cặp (user, customer) sau KHÔNG tạo được Portal Member vì "
				"insert() ném lỗi (xem Error Log riêng từng bản ghi để biết chi "
				"tiết) — migrate vẫn tiếp tục, cần vận hành xử lý tay: "
				+ ", ".join(loi)
			),
		)
