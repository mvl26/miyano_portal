app_name = "miyano_portal"
app_title = "Miyano Portal"
app_publisher = "SupplyCore Project"
app_description = "Miyano customer portal for ERPNext"
app_email = "info@miyano.com.vn"
app_license = "mit"

# Apps
# ------------------

required_apps = ["frappe/frappe", "erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "miyano_portal",
# 		"logo": "/assets/miyano_portal/logo.png",
# 		"title": "Miyano Portal",
# 		"route": "/miyano_portal",
# 		"has_permission": "miyano_portal.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/miyano_portal/css/miyano_portal.css"
# app_include_js = "/assets/miyano_portal/js/miyano_portal.js"

# include js, css files in header of web template
# web_include_css = "/assets/miyano_portal/css/miyano_portal.css"
# web_include_js = "/assets/miyano_portal/js/miyano_portal.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "miyano_portal/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}

# Desk — nút vai nhân viên. `Portal Delivery Inspection` trỏ về Delivery Note/
# Sales Order bằng field **Data** (không Link, xem docstring
# `_chan_trung_phieu_giao`), nên Frappe KHÔNG dựng mục "Connections" cho chúng:
# không có hai file dưới đây, nhân viên đứng ở đơn hoặc phiếu giao không có
# đường nào sang biên bản kiểm hàng của khách.
doctype_js = {
	"Sales Order": "public/js/sales_order.js",
	"Delivery Note": "public/js/delivery_note.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "miyano_portal/public/icons.svg"

# Website route rules
# --------------------
# SPA Vue phục vụ tại /portal (www/portal/index.html). Các route phía client
# như /portal/orders, /portal/dashboard phải trả về cùng shell để vue-router xử
# lý. Rule /portal/login đặt trước (werkzeug ưu tiên segment tĩnh hơn <path:>)
# để trang đăng nhập www/portal/login.html KHÔNG bị catch-all chiếm mất.
website_route_rules = [
	{"from_route": "/portal/login", "to_route": "portal/login"},
	{"from_route": "/portal/<path:app_path>", "to_route": "portal/index"},
]

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
#
# Thiết kế lại mua lẻ §4.6 — Notification "Portal - Báo giá sẵn sàng"
# (setup/install_notifications.py) phải nêu đúng "hạn hiệu lực báo giá".
# Đăng ký `han_hieu_luc_bao_gia` làm global cho MỌI template render qua
# `frappe.render_template` (kể cả message của doctype `Notification`, xem
# `frappe/email/doctype/notification/notification.py::get_context` — context
# đó lấy globals từ `get_jinja_hooks()`, đúng dict này) — TÁI DÙNG hàm DUY
# NHẤT đã tính hạn này cho `portal_order_accept`/`portal_order_track`/job
# daily `quet_bao_gia_het_han` thay vì hardcode "+N ngày" trong template:
# N đọc từ `Miyano Portal Settings.hieu_luc_bao_gia_ngay` (có thể đổi), hai
# nơi tính ra hai con số khác nhau là đúng lỗi đã trả giá ở review I-2(a).
# Spec 2026-08-15 §3.4 — `la_dong_giu_cho` (portal_mua_le.py) khai rõ trong
# docstring của chính nó là "dùng CHUNG bởi Python và Jinja, đăng ký ở đây".
# Đăng ký tại đây để câu đó ĐÚNG SỰ THẬT: một mẫu in tương lai lọc dòng giữ
# chỗ `HANG-DAT-NGOAI` (`{% if la_dong_giu_cho(i.item_code) %}`) đọc CÙNG một
# hằng số `ITEM_GIU_CHO` với Python, không chép chuỗi riêng — đổi hằng số thì
# cả hai nơi đổi theo, không có nơi nào lặng lẽ hết lọc.
jinja = {
	"methods": [
		"miyano_portal.portal_mua_le.han_hieu_luc_bao_gia",
		"miyano_portal.portal_mua_le.la_dong_giu_cho",
		# Đọc tiền thành chữ TIẾNG VIỆT cho chứng từ kế toán.
		# `frappe.utils.money_in_words` đọc theo ngôn ngữ hệ thống (site này
		# để tiếng Anh) nên in ra "Nine Hundred And Fifty Thousand" trên mẫu
		# 02-VT — lỗi thật, không phải chuyện thẩm mỹ.
		"miyano_portal.tien_bang_chu.tien_bang_chu",
		# Mẫu 02-VT bản TT 99/2025 có hai cột `Số lô`/`Hạn dùng`. Quy tắc đọc
		# lô (bundle TRƯỚC, `batch_no` sau) chỉ đúng ở MỘT nơi —
		# `kho/delivery_hook._lo_cua_dong` — và template gọi vào đó qua hàm
		# này. Viết `{{ i.batch_no }}` thẳng trong mẫu sẽ in ô TRỐNG cho đúng
		# những dòng tách nhiều lô, trên một biên bản bàn giao có chữ ký.
		"miyano_portal.kho.delivery_hook.lo_han_cho_in",
	],
}

# Installation
# ------------

# before_install = "miyano_portal.install.before_install"
# BẮT BUỘC bật: `install_app()` đánh dấu MỌI patch là đã chạy (frappe/installer.py:324)
# rồi mới gọi hook này, nên site mới không có workflow/custom field/notification
# nào nếu không chạy lại patch ở đây. Xem `miyano_portal/install.py`.
after_install = "miyano_portal.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "miyano_portal.uninstall.before_uninstall"
# after_uninstall = "miyano_portal.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "miyano_portal.utils.before_app_install"
# after_app_install = "miyano_portal.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "miyano_portal.utils.before_app_uninstall"
# after_app_uninstall = "miyano_portal.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "miyano_portal.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Sales Order": "miyano_portal.permissions.sales_query",
	"Delivery Note": "miyano_portal.permissions.delivery_query",
	"Sales Invoice": "miyano_portal.permissions.invoice_query",
	"Blanket Order": "miyano_portal.permissions.blanket_query",
	# E6 — Portal Item Request mang `customer` trực tiếp, cùng hình dạng bốn
	# doctype trên (KHÔNG phải hình dạng kho/permissions.py). Không có
	# DocPerm nào cho role Customer trên doctype này (xem JSON) nên đây, như
	# các dòng trên, là lớp phòng thủ thứ hai — cổng thật là api/portal.py.
	"Portal Item Request": "miyano_portal.permissions.yeu_cau_query",
	# Kiểm hàng — `customer` trực tiếp, cùng khuôn Portal Item Request. Không
	# có DocPerm nào cho role Customer (xem JSON): cổng thật là api/portal.py,
	# entry này là lớp phòng thủ thứ hai.
	"Portal Delivery Inspection": "miyano_portal.permissions.kiem_hang_query",
	"Portal Delivery Inspection Item": "miyano_portal.permissions.kiem_hang_item_query",
	# Đề xuất mua — `customer` trực tiếp, cùng khuôn Portal Item Request.
	# Vế trục khách hàng kéo lên từ Task 4 (ruling coordinator 19/08/2026,
	# xem docstring `permissions.de_xuat_query_condition`); Task 4 thêm vế
	# khoa phòng vào CHÍNH các hàm này, không đăng ký thêm entry mới.
	"Portal De Xuat Mua": "miyano_portal.permissions.de_xuat_query_condition",
	"Portal De Xuat Mua Item": "miyano_portal.permissions.de_xuat_item_query",
	# E7 — Fast EInvoice Document là doctype của module HĐĐT (team Dev, app
	# erpnext), CỐ Ý không có DocPerm nào cho `Customer` (xem JSON gốc). Entry
	# này là lớp phòng thủ thứ hai "chết có điều kiện", cùng khuôn tám
	# doctype kho bên dưới — đọc docstring `permissions.einvoice_query`.
	"Fast EInvoice Document": "miyano_portal.permissions.einvoice_query",
	# V1 (fix-wave 2026-08-18, review tổng toàn nhánh — CRITICAL) — KHÁC
	# HẲN các entry ở trên: `Notification Log` KHÔNG bị gỡ DocPerm (đây là
	# doctype của core, cấp `read/report/export` cho role `All`, mà MỌI
	# user — kể cả Website User — đều mang role đó). Entry này vì thế là
	# lớp phòng thủ THẬT SỰ đang sống, không phải "chết có điều kiện": mọi
	# Website User luôn qua được vòng kiểm role cơ bản, hook này LUÔN được
	# gọi. Đọc docstring `permissions.notification_khoa_query` cho lý do
	# đầy đủ (fan-out lúc tạo thông báo gửi cho MỌI thành viên active của
	# khách hàng, chưa lọc theo khoa — hook này bù lại đúng vế đó ở đường
	# đọc, AND thêm vào điều kiện `for_user` core đã có, không ghi đè).
	"Notification Log": "miyano_portal.permissions.notification_khoa_query",
	# ---------------------------------------------------------------------
	# Kho khách hàng — ĐỌC comment ở khối has_permission bên dưới trước khi
	# tin rằng các entry dưới đây là thứ đang bảo vệ dữ liệu kho. Kể từ vòng
	# 4, cơ chế bảo vệ CHÍNH là: role `Customer` KHÔNG còn bất kỳ DocPerm nào
	# trên tám doctype kho, nên Website User không bao giờ qua nổi vòng kiểm
	# role cơ bản và các hàm dưới đây KHÔNG BAO GIỜ được gọi tới cho họ.
	# Giữ lại làm lớp phòng thủ thứ hai: nếu ai đó cấp lại DocPerm cho
	# `Customer` (qua JSON doctype hoặc Role Permission Manager), các điều
	# kiện này lập tức có hiệu lực trở lại và giới hạn list view theo kho.
	# ---------------------------------------------------------------------
	"Customer Warehouse": "miyano_portal.kho.permissions.kho_query",
	"Customer Warehouse Item": "miyano_portal.kho.permissions.vat_tu_query",
	"Customer Stock Receipt": "miyano_portal.kho.permissions.receipt_query",
	"Customer Stock Issue": "miyano_portal.kho.permissions.issue_query",
	"Customer Stock Ledger Entry": "miyano_portal.kho.permissions.sle_query",
	"Customer Stock Lot Balance": "miyano_portal.kho.permissions.lot_query",
	# E4: NCC của kho — mang field `kho` riêng (không phải kho tự nó), nên
	# dùng cùng khuôn _kho_condition() như Customer Warehouse Item.
	"Customer Supplier": "miyano_portal.kho.permissions.ncc_query",
	# E8: Khoa phòng của kho — cùng hình dạng Customer Supplier.
	"Customer Department": "miyano_portal.kho.permissions.khoa_phong_query",
	# Grandchild item tables — không có field `kho` riêng, phải lọc qua parent.
	"Customer Stock Receipt Item": "miyano_portal.kho.permissions.receipt_item_query",
	"Customer Stock Issue Item": "miyano_portal.kho.permissions.issue_item_query",
}

has_permission = {
	"Sales Order": "miyano_portal.permissions.sales_has_permission",
	"Delivery Note": "miyano_portal.permissions.generic_has_permission",
	"Sales Invoice": "miyano_portal.permissions.generic_has_permission",
	"Blanket Order": "miyano_portal.permissions.generic_has_permission",
	# E6 — cùng khuôn Sales Order/Delivery Note/... ở trên (customer trực
	# tiếp), không phải khuôn kho_child_has_permission (customer qua `kho`).
	"Portal Item Request": "miyano_portal.permissions.generic_has_permission",
	# Kiểm hàng — cùng khuôn (customer trực tiếp).
	"Portal Delivery Inspection": "miyano_portal.permissions.generic_has_permission",
	# Đề xuất mua — cùng khuôn (customer trực tiếp). "Portal De Xuat Mua
	# Item" CỐ Ý không có entry ở đây: istable=1, has_child_permission()
	# route thẳng về PARENT trước khi has_permission của bảng con có cơ hội
	# chạy (cùng lý do đã ghi cho Portal Delivery Inspection Item/Customer
	# Stock *Item ở khối comment "CÁI GÌ ĐANG THẬT SỰ BẢO VỆ..." bên dưới) —
	# override has_permission trên controller (portal_de_xuat_mua_item.py)
	# là lớp phòng thủ cho đường gọi qua INSTANCE, không phải entry ở đây.
	"Portal De Xuat Mua": "miyano_portal.permissions.de_xuat_co_quyen",
	# E7 — cùng lớp phòng thủ thứ hai như entry query_conditions ở trên.
	"Fast EInvoice Document": "miyano_portal.permissions.generic_has_permission",
	"Customer Warehouse": "miyano_portal.kho.permissions.kho_has_permission",
	"Customer Warehouse Item": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Receipt": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Issue": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Ledger Entry": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Lot Balance": "miyano_portal.kho.permissions.kho_child_has_permission",
	# E4: cùng khuôn — Customer Supplier mang field `kho` riêng như Warehouse Item.
	"Customer Supplier": "miyano_portal.kho.permissions.kho_child_has_permission",
	# E8: cùng khuôn — Customer Department mang field `kho` riêng.
	"Customer Department": "miyano_portal.kho.permissions.kho_child_has_permission",
	# =====================================================================
	# CÁI GÌ ĐANG THẬT SỰ BẢO VỆ TÁM DOCTYPE KHO (vòng 4 — mô hình hiện tại)
	# =====================================================================
	# Role `Customer` KHÔNG có DocPerm nào trên sáu doctype cha (Customer
	# Warehouse / Warehouse Item / Stock Receipt / Stock Issue / Stock Ledger
	# Entry / Stock Lot Balance) — xem mảng "permissions" trong sáu file JSON
	# tương ứng, chỉ còn System Manager / Sales Manager / Sales User. Đó là
	# TOÀN BỘ cơ chế cách ly ở phía đọc trực tiếp doctype: không có grant nền,
	# mọi Website User bị chặn ngay ở vòng kiểm role, trên MỌI đường gọi —
	# /printview, download_pdf, frappe.client.has_permission,
	# frappe.client.get_list, REST v1/v2, desk. Hai bảng con istable=1 cũng
	# được đóng theo, vì has_child_permission() quy chiếu ngược về đúng role
	# check trên doctype CHA (đó chính là lý do vòng 1-3 không đóng nổi lỗ
	# /printview ở tầng class/hook: chừng nào cha còn read=1 cho `Customer`
	# thì con vẫn lọt).
	#
	# Cổng duy nhất được phép của portal là API whitelist
	# miyano_portal/api/kho.py: nó suy kho từ phiên đăng nhập qua
	# get_portal_kho() rồi lọc tường minh theo kho đó, tức an toàn NHỜ CẤU
	# TRÚC TRUY VẤN chứ không nhờ tầng phân quyền của framework. Đúng như
	# thiết kế đã duyệt: portal không bao giờ chạm thẳng vào các doctype này.
	#
	# Các entry has_permission còn lại ở trên, và toàn bộ khối
	# permission_query_conditions, giờ là LỚP PHÒNG THỦ THỨ HAI: với role
	# `Customer` hiện tại chúng không bao giờ được gọi tới (không có grant
	# nền thì framework chặn trước khi tới hook). Chúng chỉ có ý nghĩa nếu ai
	# đó cấp lại DocPerm cho `Customer`, hoặc cấp cho một role Website User
	# khác. Giữ lại vì rẻ và vì chúng biến một sai lầm cấu hình tương lai từ
	# "rò rỉ toàn bộ" thành "vẫn lọc theo kho".
	#
	# Customer Stock Receipt Item / Customer Stock Issue Item CỐ Ý không có
	# entry ở đây (dù CÓ entry trong permission_query_conditions ở trên).
	# Đây là loại "chết" KHÁC HẲN với đoạn trên, đừng gộp hai thứ làm một:
	# chúng là istable=1, và frappe.permissions.has_child_permission() rẽ
	# nhánh sang kiểm PARENT trước khi bất kỳ hook has_permission nào đăng ký
	# cho CHÍNH doctype con có cơ hội chạy — một entry ở đây KHÔNG BAO GIỜ
	# được gọi, bất kể cấu hình DocPerm thế nào, kể cả sau khi ai đó cấp lại
	# quyền cho `Customer` (đã xác minh thực nghiệm, xem task-6-report.md
	# phần "Deviation"). Tức là: các entry khác ở khối này "chết có điều
	# kiện" (sống lại nếu grant quay lại), hai entry này thì "chết cấu trúc"
	# (không bao giờ sống). ĐỪNG thêm lại chúng — một entry has_permission
	# "có vẻ đúng" nhưng chết là một decoy.
	#
	# has_permission() ghi đè trên class controller
	# (customer_stock_receipt_item.py / customer_stock_issue_item.py) cũng
	# thuộc lớp phòng thủ thứ hai, KHÔNG phải cơ chế chính: nó chỉ chặn được
	# lời gọi qua INSTANCE (doc.check_permission()/doc.has_permission()),
	# không chặn được lời gọi MODULE-LEVEL frappe.has_permission(doctype,
	# ptype, doc) mà /printview dùng. Lỗ /printview được đóng bởi việc gỡ
	# DocPerm ở trên, KHÔNG phải bởi override đó.
}

# DocType Class
# ---------------
# Override standard doctype classes

# Brief 2026-08-15 (trang thông báo) — BLOCKING FIX: vá lỗi lõi Frappe khiến
# `Notification Log` chết câm vĩnh viễn khi site không có Email Account gửi
# ra. Xem docstring `overrides/notification.py` cho phân tích đầy đủ. Áp
# dụng cho MỌI Notification trên site (bugfix lõi, không riêng 5 bản ghi
# "Portal - *").
override_doctype_class = {
	"Notification": "miyano_portal.overrides.notification.Notification",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# Kho khách hàng, thiết kế §4.3. Miyano giao hàng → sinh Phiếu Nhập Kho
	# NHÁP trong kho của khách mua.
	#
	# CỐ Ý dùng on_submit / on_cancel chứ không phải before_*, và điều này
	# KHÔNG mâu thuẫn với quy tắc "validation thuộc về before_*": hook này
	# không validate gì cả, nó chỉ sinh hiệu ứng phụ, và nó KHÔNG BAO GIỜ ném
	# lỗi ra ngoài (xem delivery_hook._chay_an_toan). Đặt nó ở before_submit
	# sẽ biến mọi trục trặc phía kho khách thành một lỗi chặn Miyano giao
	# hàng — đúng thứ ràng buộc cao nhất của tính năng này cấm.
	#
	# Hook của app chạy SAU method cùng tên của chính doctype
	# (frappe.model.document.Document.hook → compose(fn, *hooks)), nên tới lúc
	# hook này chạy thì Delivery Note đã ghi sổ kho ERPNext, đã ghi GL Entry,
	# và đã có bundle lô do ERPNext tự sinh từ `batch_no`.
	"Delivery Note": {
		"on_submit": [
			"miyano_portal.kho.delivery_hook.on_delivery_note_submit",
			# Kiểm hàng (2026-08-16): phiếu TRẢ HÀNG được ghi sổ → biên bản
			# kiểm hàng sinh ra nó chuyển sang "Đã thu hồi". Cùng ràng buộc
			# tuyệt đối như hook ngay trên: không bao giờ ném lỗi ra ngoài.
			"miyano_portal.portal_kiem_hang.dong_bo_trang_thai_thu_hoi",
		],
		"on_cancel": "miyano_portal.kho.delivery_hook.on_delivery_note_cancel",
		# brief 2026-08-15 (trang thông báo) Phần 2 — điểm giòn định tuyến:
		# PHÁT HIỆN (không sửa được, xem docstring hàm) khi contact_email của
		# chứng từ không khớp tài khoản cổng nào của khách, nghĩa là
		# Notification "Portal - Xuất giao" (send_system_notification=1) sẽ
		# không sinh Notification Log cho chứng từ này. `on_update` vì đây là
		# hook PHÁT HIỆN chạy song song với luồng bán hàng chính, không phải
		# validate — không bao giờ ném lỗi (xem docstring).
		"on_update": "miyano_portal.portal_thong_bao_khach.kiem_tra_dinh_tuyen_thong_bao_khach",
	},
	# E7b — ký hoá đơn bán hàng thì tự lập chứng từ HĐĐT từ phiếu giao của nó
	# và lấy luôn bản in thử PDF từ Fast, để khách mở cổng là thấy hoá đơn.
	#
	# CHỈ đẩy hàng đợi, không gọi Fast tại đây: một lời gọi Fast có thể mất
	# tới 120 giây. Và hook không bao giờ ném lỗi ra ngoài — lập HĐĐT không
	# có quyền chặn việc xuất hoá đơn bán hàng (cùng nguyên tắc Delivery Note
	# ở trên). Xem `miyano_portal/hddt_tu_dong.py`.
	#
	# Dòng đăng ký này CÓ TEST CANH GIỮ (`test_e7b_tu_dong.TestHookDuocDangKy`).
	# Lý do: nó đã từng biến mất một lần mà không test nào đỏ — toàn bộ test
	# của tính năng gọi thẳng hàm `tu_sales_invoice`/`lap_hddt_cho_hoa_don`,
	# nên "hàm chạy đúng" và "hàm có được gọi hay không" là hai chuyện khác
	# nhau. Xoá dòng này là tắt cả tính năng mà mọi test vẫn xanh.
	"Sales Invoice": {
		"on_submit": "miyano_portal.hddt_tu_dong.tu_sales_invoice",
		# Cùng lý do/chốt với "Delivery Note" ở trên — Notification "Portal -
		# Hoá đơn phát hành".
		"on_update": "miyano_portal.portal_thong_bao_khach.kiem_tra_dinh_tuyen_thong_bao_khach",
	},
	# Ký HĐNT (Selling) → dựng luôn Item Price trong bảng giá của khách.
	#
	# CẬP NHẬT Task 12 (QĐ-G12, 21/08/2026) — chú thích cũ ở đây nói rằng
	# cổng CHỈ chấp nhận đơn giá đến từ `Item Price` và rằng giữ nguyên phép
	# tra đó mới là đúng. CẢ HAI vế nay đã SAI: với một dòng hợp đồng, cổng
	# đọc `Blanket Order Item.rate` TRƯỚC (`gia_hdnt.gia_dong_hop_dong`),
	# bảng giá chỉ còn là bước lui. Lý do đổi: hook này chạy ĐÚNG MỘT LẦN
	# lúc trình ký, nên mọi hợp đồng ký trước khi nó ra đời và mọi hợp đồng
	# nạp bằng import không bao giờ được đồng bộ — và chỗ hổng đó im lặng,
	# biểu hiện ra thành "chưa có giá trong hợp đồng" cho một hợp đồng có
	# rate rành rành.
	#
	# Hook VẪN CẦN, chỉ đổi vai: nó không còn là điều kiện để khách đặt được
	# hàng, mà là thứ giữ `Item Price` khớp với hợp đồng cho phía ERPNext —
	# báo cáo, hoá đơn, và giá Desk tự điền khi nhân viên Miyano dựng chứng
	# từ bằng tay. Ruling P30: nó ghi theo ĐÚNG luật phân định của cổng.
	#
	# `on_submit` là đủ: `Blanket Order Item.rate` KHÔNG `allow_on_submit`
	# (đã kiểm JSON doctype), nên giá chỉ đổi được bằng cách sửa đổi hợp đồng
	# — thao tác đó lại submit một lần nữa và hook chạy lại.
	"Blanket Order": {
		"on_submit": "miyano_portal.gia_hdnt.tu_hdnt",
	},
	# Epic E2 — BR-O14 / NL-2.1: bắt buộc lý do khi chuyển Sales Order sang
	# "Từ chối". Áp cho MỌI Sales Order, không riêng đơn từ cổng.
	#
	# BR-O9 / NL-2.5: ngưỡng duyệt hai tầng. CỐ Ý đặt ở before_submit chứ
	# không ở condition của workflow transition — xem docstring
	# `kiem_nguong_duyet` trong portal_duyet_don.py.
	"Sales Order": {
		# Task 13 (QĐ-G13, chủ đầu tư chốt 21/08/2026) — khớp mã cho một
		# dòng "đặt ngoài" thì CHUYỂN nó thành dòng hàng thật trong `items`,
		# lấy giá hợp đồng bằng hàm dùng chung (QĐ-G14).
		#
		# Ở `before_validate` chứ KHÔNG `validate`, và đây là lý do: hook
		# của app chạy SAU method cùng tên của chính doctype
		# (`Document.hook` → `compose(fn, *hooks)`), nên một hook `validate`
		# chạy SAU `SalesOrder.validate()` — sau `set_missing_values`, sau
		# `calculate_taxes_and_totals`. Dòng hàng thêm vào lúc đó sẽ thiếu
		# `item_name`/`uom`, có `amount = 0` và KHÔNG được cộng vào
		# `grand_total`, tức tái hiện đúng nửa sau của triệu chứng
		# ("không vào tổng tiền") mà task này sinh ra để dẹp.
		#
		# Phần CẤM của kế hoạch (bẫy 4) vẫn giữ tuyệt đối: chốt KHÔNG nằm
		# trong `validate()` của doctype con — Frappe không bao giờ gọi hàm
		# đó khi document CHA lưu.
		"before_validate": [
			"miyano_portal.portal_mua_le.chuyen_dong_dat_ngoai_thanh_hang",
		],
		"validate": [
			"miyano_portal.portal_duyet_don.kiem_ly_do_tu_choi",
			# E6 phần B, review I-2(a) round 2 — ghi `custom_ngay_gui_khach_
			# duyet` mỗi khi đơn CHUYỂN VÀO "Chờ khách đồng ý". Ở `validate`
			# (không phải một endpoint cổng) vì đường đi CHÍNH của US-E6.5
			# là sales bấm nút workflow "Gửi khách duyệt" TỪ DESK.
			"miyano_portal.portal_mua_le.ghi_ngay_gui_khach_duyet",
			# Thiết kế lại mua lẻ §4.3 — đồng bộ `da_xu_ly` của bảng con
			# "đặt ngoài" theo `item_khop`. Ở `validate` cùng lý do dòng
			# trên: `Document.validate()` của bảng con KHÔNG được Frappe
			# gọi khi cha lưu, đây là nơi DUY NHẤT chốt này chạy được cho
			# mọi đường ghi (cổng lẫn Desk).
			"miyano_portal.portal_mua_le.dong_bo_da_xu_ly_dat_ngoai",
		],
		"before_submit": [
			"miyano_portal.portal_duyet_don.kiem_nguong_duyet",
			# Thiết kế lại mua lẻ §4.4 — CHỐT MỚI: không xác nhận đơn khi
			# còn dòng "đặt ngoài" chưa xử lý (chưa khớp `item_khop`).
			"miyano_portal.portal_mua_le.kiem_dat_ngoai_da_xu_ly",
			# Critical-3 (review Task 13, 22/08) — chốt ngay trên tin
			# `da_xu_ly`, mà `da_xu_ly` chỉ nói thật TẠI LÚC chuyển. Nhân
			# viên Desk xoá dòng `items` do phép chuyển sinh ra thì cờ vẫn
			# bật và đơn xác nhận được với mặt hàng khoa yêu cầu không có
			# dòng nào. Chốt này đối chiếu `dong_hang` với `items` THẬT.
			"miyano_portal.portal_mua_le.kiem_dong_chuyen_con_tren_don",
			# Việc thêm (controller, ngoài Task 9) — CHỐT MỚI, cạnh chốt trên:
			# chốt trên chỉ nhìn `custom_dat_ngoai`, không nhìn `items` — nên
			# không bắt được dòng giữ chỗ `ITEM_GIU_CHO` còn sót lại trong
			# `items` dù mọi dòng đặt ngoài đã khớp mã. Xem docstring hàm.
			"miyano_portal.portal_mua_le.kiem_khong_con_dong_giu_cho",
		],
		# Cùng lý do/chốt với "Delivery Note"/"Sales Invoice" ở trên —
		# Notification "Portal - Đơn xác nhận"/"Đơn bị từ chối"/"Báo giá sẵn
		# sàng" (brief 2026-08-15, trang thông báo, Phần 2).
		"on_update": ["miyano_portal.portal_thong_bao_khach.kiem_tra_dinh_tuyen_thong_bao_khach"],
	},
}

# Scheduled Tasks
# ---------------

# NL-2.6 / US-E2.3 — đơn treo quá SLA thì leo thang cho Sales Manager.
# Xem docstring `portal_sla.quet_don_treo` cho quy tắc chống spam (tối đa một
# lần nhắc mỗi đơn mỗi ngày, dù job này chạy mỗi giờ).
scheduler_events = {
	"hourly": [
		"miyano_portal.portal_sla.quet_don_treo",
		# E6/NL-11.2 — leo thang yêu cầu hàng hoá quá SLA còn "Mới".
		"miyano_portal.portal_sla.quet_yeu_cau_qua_han",
	],
	"daily": [
		# E6 phần B/NL-10.5 — báo giá "Chờ khách đồng ý" quá hạn hiệu lực:
		# tự đóng + email hai phía + yêu cầu gốc chuyển "Hết hạn".
		"miyano_portal.portal_bao_gia.quet_bao_gia_het_han",
		# US-E5.4 — vật tư dưới min/ROP: email tổng hợp theo tần suất cấu
		# hình trên từng kho (mặc định TẮT, bật riêng theo kho).
		"miyano_portal.portal_du_tru_job.quet_canh_bao_ton_daily",
	],
}

# Testing
# -------

# before_tests = "miyano_portal.install.before_tests"

# ------------------------------------------------------------------
# Overriding Methods — BA v2 §NG-37 + NG-37b (NG-37b ngoài BA v2 gốc, thêm
# 2026-08-12 sau khi review Task 1 chứng minh lỗ bằng probe thật — xem
# .superpowers/sdd/2026-08-12-dot-1-chan-mau-P0/task-1b-brief.md)
# ------------------------------------------------------------------
# NG-37: `search_link` và `search_widget` của Frappe nhận `ignore_user_permissions`
# TỪ CLIENT và chuyển thẳng xuống `get_list(ignore_permissions=...)`, bỏ qua
# permission_query_conditions. Phải bọc CẢ HAI: `search_link` chỉ gọi
# `search_widget`, nên bọc một mình nó vẫn hở đường gọi thẳng.
#
# NG-37b: `frappe.client.get_list`/`frappe.client.get` trên MỌI doctype con
# (`frappe.is_table(doctype)`, không riêng ba doctype PoC gốc — xem Critical
# C1 dưới đây) chỉ kiểm quyền cha ở MỨC DOCTYPE (`check_parent_permission`,
# không kèm `doc`), bỏ qua khách hàng của đơn — CÙNG HỌ với NG-37 nhưng là
# một endpoint khác hẳn.
#
# review round 1 (2026-08-12): bản vá đầu tiên chỉ liệt kê ba tên (Sales
# Order Item / Delivery Note Item / Sales Invoice Item) — allow-by-omission
# trên TRỤC DOCTYPE, fail OPEN với mọi doctype con khác (`Payment Schedule`,
# `Sales Taxes and Charges`, `Sales Invoice Payment`, `Sales Invoice
# Advance`, `Packed Item`, `Sales Team`, `Pricing Rule Detail`, ...). Đã sửa
# thành gate `frappe.is_table(doctype)` trong `client_get_list`/`client_get`
# — chặn MỌI doctype con cho Website User, không liệt kê tên.
#
# CẢNH BÁO PHẠM VI — dict `override_whitelisted_methods` dưới đây KHÔNG PHỦ
# route REST, đây là kiến thức dễ mất nhất trong cả đợt vá NG-37: người đọc
# sau thấy dict đã có `frappe.client.get`/`frappe.client.get_list` sẽ dễ
# tưởng mọi đường đọc doctype con đã bị bịt — KHÔNG PHẢI VẬY.
#   - Trục ROUTE (đã đóng — NG-37c, xem `miyano_portal/rest_guard.py` +
#     `before_request` bên dưới): hai entry NG-37b ở dict này chỉ đóng được
#     request định tuyến bằng CHUỖI TÊN qua
#     `frappe.override_whitelisted_method()` (`/api/method/...`,
#     `/api/v2/method/...`). `/api/resource/<doctype>` (v1),
#     `/api/v1/resource/<doctype>` (v1, submount khác cùng route),
#     `/api/v2/document/<doctype>` (v2), và mọi biến thể đọc MỘT bản ghi qua
#     REST (`/api/resource/<doctype>/<name>`, `/api/v2/document/<doctype>/
#     <name>`) gọi thẳng hàm gốc bằng THAM CHIẾU PYTHON (`frappe.call(frappe.
#     client.get_list, ...)`) hoặc đi qua `doc.check_permission()` ->
#     `has_child_permission()` trực tiếp — KHÔNG đi qua dict này, dù doctype
#     có phải bảng con hay không. `override_whitelisted_methods` không thể
#     đóng được trục này DÙ thêm bao nhiêu entry — đây là giới hạn theo
#     THIẾT KẾ của cơ chế, không phải thiếu cấu hình (xem docstring dài ở
#     `rest_guard.py`). Đã đóng bằng hook `before_request` riêng, chặn ở
#     tầng định tuyến HTTP, TRƯỚC khi request kịp rẽ vào một trong hai
#     đường lỗ trên.
#   - Trục HÀM (còn mở — đã probe HTTP thật 2026-08-12, xem
#     `task-1c-report.md` mục "Step 7"): `frappe.client.get_value`/
#     `validate_link`/`has_permission` không nằm trong dict này —
#     `get_value`/`validate_link` gọi `get_list` NỘI BỘ của `client.py`
#     (tham chiếu Python trực tiếp trong cùng file, không phải bản đã
#     override), `has_permission` dính một biến thể khác của cùng lỗi
#     `has_child_permission()`. Đã mở tracker NG-37d cho những gì probe xác
#     nhận còn thật sự mở — KHÔNG lặng lẽ mở rộng phạm vi NG-37c để vá luôn
#     ở đây; xem changelog.
#
# Xem miyano_portal/search_guard.py cho toàn bộ bốn hàm dưới đây,
# miyano_portal/rest_guard.py cho hook `before_request`.
# ------------------------------------------------------------------
override_whitelisted_methods = {
	"frappe.desk.search.search_link": "miyano_portal.search_guard.search_link",
	"frappe.desk.search.search_widget": "miyano_portal.search_guard.search_widget",
	"frappe.client.get_list": "miyano_portal.search_guard.client_get_list",
	"frappe.client.get": "miyano_portal.search_guard.client_get",
	# NG-37d — cùng lỗ check_parent_permission, khác đường vào. Ba hàm này
	# gọi lẫn nhau bằng tham chiếu NỘI BỘ module `frappe/client.py`
	# (`validate_link` → `get_value` → `get_list` cùng file), nên bọc
	# `frappe.client.get_list` ở trên KHÔNG cứu được chúng — mỗi tên hàm
	# định tuyến từ ngoài vào phải có một lớp bọc riêng.
	"frappe.client.get_value": "miyano_portal.search_guard.client_get_value",
	"frappe.client.validate_link": "miyano_portal.search_guard.client_validate_link",
	"frappe.client.has_permission": "miyano_portal.search_guard.client_has_permission",
}
# override_doctype_dashboards = {
# 	"Task": "miyano_portal.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# NG-37c (2026-08-12, ngoài BA v2 gốc — xem .superpowers/sdd/
# 2026-08-12-dot-1-chan-mau-P0/task-1c-brief.md): đóng trục ROUTE mà
# `override_whitelisted_methods` ở trên KHÔNG PHỦ ĐƯỢC theo thiết kế —
# `/api/resource/<doctype>` (v1), `/api/v1/resource/<doctype>` (v1, submount
# khác), `/api/v2/document/<doctype>` (v2) gọi thẳng
# `frappe.client.get_list`/dispatch tới `has_child_permission()` bằng THAM
# CHIẾU HÀM, không qua tra cứu chuỗi tên nào cả. `before_request` là cửa sổ
# duy nhất chặn được cả hai phiên bản API bằng một chỗ: `frappe/app.py::
# init_request()` gọi hook này SAU KHI session đã resume từ cookie
# (`frappe.session.user` đã là user thật) và TRƯỚC KHI request được dispatch
# tới route handler. Đọc docstring dài ở `miyano_portal/rest_guard.py`
# trước khi sửa gì ở đây.
before_request = [
	"miyano_portal.rest_guard.chan_rest_doctype_con",
]
# after_request = ["miyano_portal.utils.after_request"]

# Job Events
# ----------
# before_job = ["miyano_portal.utils.before_job"]
# after_job = ["miyano_portal.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"miyano_portal.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

