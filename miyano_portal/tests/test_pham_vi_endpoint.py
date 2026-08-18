"""Mọi endpoint whitelist phải KHAI BÁO lập trường về phạm vi khoa phòng.

Đây không phải test một hành vi — nó là một cái chốt. Cổng có 27 endpoint ở
`api/portal.py` và 38 ở `api/kho.py`; nếu mỗi cái tự viết điều kiện lọc thì
việc MỘT cái quên lọc là chắc chắn xảy ra. App đã dính đúng kiểu đó hai lần
trong tuần 17–18/08 (phiếu trả hàng lọt vào danh sách đợt giao; phiếu giao
nháp lọt ra cổng khách).

Thêm endpoint mới mà không thêm tên nó vào một trong hai/ba tập bên dưới
(theo module) thì test này ĐỎ. Đó là toàn bộ mục đích của nó.

VÒNG SỬA 1 (review độc lập, I3) — bản trước CHỈ soi `api/portal.py`. Ba
module khác cũng có `@frappe.whitelist()` mà một tài khoản cổng gọi tới
được (trực tiếp hoặc qua đường Frappe generic) nằm ngoài tầm nhìn cũ:
`search_guard.py` (7 hàm — CHÍNH đường `frappe.client.get_list`/`get_value`
mà C2 vừa vá), `portal_kiem_hang.py` (4 hàm — vai NHÂN VIÊN, chốt role),
`portal_hen_giao.py` (1 hàm — cùng khuôn). Mở rộng phép liệt kê sang cả ba.
"""

import inspect

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import portal_hen_giao, portal_kiem_hang, search_guard
from miyano_portal.api import kho as kho_api
from miyano_portal.api import portal as portal_api

# Endpoint ĐÃ đi qua `pham_vi_don()` hoặc `dam_bao_xem_duoc()`.
DA_AP_PHAM_VI: set[str] = {
	"portal_order_history", "portal_order_track", "portal_dashboard_kpi",
	"portal_deliveries", "portal_invoices", "portal_reorder",
	"portal_order_accept", "portal_order_sua_so_luong", "portal_order_huy",
	"portal_request_cancel", "portal_bao_gia_pdf", "portal_document_download",
	"portal_kiem_hang_get", "portal_kiem_hang_luu", "portal_kiem_hang_gui",
	"portal_einvoice_download", "portal_einvoice_nhap",
	"portal_einvoice_nhap_pdf", "portal_einvoice_ho_tro",
	"portal_thong_bao_list", "portal_thong_bao_doc",
}

# Endpoint CỐ Ý không lọc theo khoa — mỗi cái kèm lý do bằng chữ. Sửa tập
# này là một quyết định phân quyền, không phải một thao tác dọn dẹp.
MIEN_PHAM_VI: dict[str, str] = {
	"portal_me": (
		"outstanding là công nợ GL cấp KHÁCH HÀNG/công ty (Vòng sửa 1, I1: "
		"lý do cũ 'không có dữ liệu đơn hàng' SAI — _get_outstanding() trả "
		"tổng công nợ GL của CẢ bệnh viện). Không truy được về khoa qua GL "
		"Entry (thanh toán/bút toán không mang custom_khoa_phong), và nhất "
		"quán với các field khác CÙNG endpoint (customer_name/tax_id/"
		"addresses) — đều cấp bệnh viện. KHÁC hoa_don_chua_thanh_toan trên "
		"portal_dashboard_kpi: đó là ĐẾM HOÁ ĐƠN cụ thể, quy được về khoa "
		"qua Sales Invoice Item.sales_order, đứng cạnh hai con số khác đã "
		"lọc khoa trên cùng màn — để nó unscoped sẽ phá ngữ cảnh 'đây là "
		"số liệu khoa tôi' của khối KPI đó."
	),
	"portal_contracts": "hợp đồng khung ký ở cấp bệnh viện, không thuộc khoa nào",
	"portal_catalog": "danh mục hàng theo hợp đồng — cấp bệnh viện",
	"portal_catalog_ban_le": "danh mục hàng bán lẻ — cấp bệnh viện",
	"portal_order_place": (
		"đường GHI; phạm vi do dat_hang.tao_sales_order chốt, suy khoa TỪ "
		"PHIÊN qua get_portal_member() ngay tại portal_order_place — Vòng "
		"sửa 1 (C1): trước đây hàm này KHÔNG hề truyền khoa_phong xuống, "
		"nên MỌI đơn đặt qua cổng có custom_khoa_phong = NULL."
	),
	"portal_provision": "chỉ nhân viên Miyano gọi, không phải endpoint của khách",
}

# search_guard.py — Vòng sửa 1 (I3). Bảy hàm này là vỏ mỏng quanh
# `frappe.client.*`/`frappe.desk.search.*`, KHÔNG tự gọi `pham_vi_don()`/
# `dam_bao_xem_duoc()` — chúng thừa hưởng phạm vi khoa qua HAI cơ chế khác
# nhau tuỳ trục:
#   * Trục DOCTYPE CON (`frappe.is_table(doctype)` đúng): NG-37/NG-37b chặn
#     Website User HOÀN TOÀN trước khi chạm doctype cha — không có khái
#     niệm khoa phòng ở doctype con, không cần lọc thêm.
#   * Trục DOCTYPE CHA (Sales Order/Delivery Note/Sales Invoice — role
#     Customer có DocPerm read trực tiếp): rơi thẳng xuống
#     `frappe.client.get_list`/`get`/`get_value` thật, TỰ ĐỘNG đi qua
#     `permission_query_conditions`/`has_permission` mà C2 (Vòng sửa 1) vừa
#     thêm vế khoa — ĐÂY chính là kênh C2 nêu tên
#     ("frappe.client.get_value", "search_guard.client_get_list").
# Test `test_client_get_list_qua_search_guard_khong_lo_don_khoa_khac` +
# `test_client_get_value_qua_search_guard_khong_doc_duoc_don_khoa_khac`
# trong `test_cach_ly_khoa_phong.py` khẳng định trực tiếp hai hàm này.
SEARCH_GUARD_AP_QUA_HOOK: dict[str, str] = {
	"search_link": "vỏ mỏng quanh search_widget (cùng hàm dưới)",
	"search_widget": "chặn ignore_user_permissions=1 (NG-37); phần còn lại đi qua permission_query_conditions đã có khoa",
	"client_get_list": "gọi frappe.client.get_list thật cho doctype cha — permission_query_conditions (sales_query/delivery_query/invoice_query) đã có vế khoa, xem C2",
	"client_get": "cùng cơ chế client_get_list, qua frappe.client.get + has_permission (sales_has_permission/generic_has_permission đã có vế khoa)",
	"client_get_value": "gọi frappe.client.get_value -> get_list nội bộ, cùng permission_query_conditions",
	"client_validate_link": "chỉ chặn trục doctype con (frappe.is_table); doctype cha đi qua exists()+has_permission, đã có vế khoa",
	"client_has_permission": "gọi thẳng frappe.client.has_permission -> frappe.has_permission -> sales_has_permission/generic_has_permission, đã có vế khoa",
}

# portal_kiem_hang.py / portal_hen_giao.py — Vòng sửa 1 (I3). Năm hàm này
# đều mở đầu bằng một chốt VAI TRÒ (`_kiem_role_duyet()`/`_kiem_role()`,
# yêu cầu Sales Manager/System Manager/Sales User) — một Website User
# (khách cổng) không bao giờ có các role đó, nên không bao giờ qua nổi
# dòng đầu hàm để đọc được dữ liệu của BẤT KỲ khoa nào, kể cả khoa của
# chính khách hàng mình. Cùng hạng miễn trừ với `portal_provision`.
STAFF_ONLY_MIEN_PHAM_VI: dict[str, str] = {
	"kiem_hang_duyet_tra": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"kiem_hang_tu_choi": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"kiem_hang_da_xu_ly": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"kiem_hang_hen_giao": "chỉ Sales Manager/System Manager gọi (_kiem_role_duyet), không phải endpoint của khách",
	"hen_giao_lai": "chỉ System Manager/Sales Manager/Sales User gọi (_kiem_role), không phải endpoint của khách",
}


def _endpoints(module) -> set[str]:
	# `frappe.whitelist()` trong bản Frappe của site này KHÔNG gắn thuộc
	# tính `.whitelisted` lên hàm (khác một số bản Frappe khác) — nó chỉ
	# ghi hàm gốc vào danh sách toàn cục `frappe.whitelisted`. Soát bằng
	# `fn in frappe.whitelisted` thay vì `getattr(fn, "whitelisted", ...)`
	# để đo đúng cơ chế THẬT của bản đang chạy, không phải cơ chế giả định.
	return {
		ten for ten, fn in inspect.getmembers(module, inspect.isfunction)
		if fn in frappe.whitelisted and fn.__module__ == module.__name__
	}


class TestMoiEndpointKhaiBaoPhamVi(FrappeTestCase):
	def test_moi_endpoint_portal_deu_da_khai_bao(self):
		thuc_te = _endpoints(portal_api)
		da_khai = DA_AP_PHAM_VI | set(MIEN_PHAM_VI)
		chua_khai = thuc_te - da_khai
		self.assertFalse(
			chua_khai,
			"Endpoint chưa khai báo lập trường về phạm vi khoa phòng: "
			f"{sorted(chua_khai)}. Thêm vào DA_AP_PHAM_VI (đã lọc) hoặc "
			"MIEN_PHAM_VI (kèm lý do) trong test này.",
		)

	def test_khong_khai_bao_thua(self):
		"""Tên trong hai tập mà không còn là endpoint nữa → tập đã mục."""
		thuc_te = _endpoints(portal_api)
		thua = (DA_AP_PHAM_VI | set(MIEN_PHAM_VI)) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")

	def test_module_kho_chua_ap_pham_vi_la_no_biet_dieu_do(self):
		"""Bước 8 của đề án mới cách ly module kho. Cho tới lúc đó, test này
		giữ CON SỐ để việc thêm endpoint kho mới không lặng lẽ trôi qua."""
		self.assertEqual(
			len(_endpoints(kho_api)), 38,
			"Số endpoint api/kho.py đã đổi. Bước 8 phân loại 38 cái này thành "
			"13 phải lọc / 8 phải thu hẹp / 17 chặn theo vai trò — xem spec "
			"§7.1c. Cập nhật cả hai chỗ cùng lúc.",
		)

	def test_moi_endpoint_search_guard_deu_da_khai_bao(self):
		thuc_te = _endpoints(search_guard)
		chua_khai = thuc_te - set(SEARCH_GUARD_AP_QUA_HOOK)
		self.assertFalse(
			chua_khai,
			f"Endpoint search_guard.py chưa khai báo: {sorted(chua_khai)}. "
			"Thêm vào SEARCH_GUARD_AP_QUA_HOOK kèm cơ chế bảo vệ thật.",
		)

	def test_khong_khai_bao_thua_search_guard(self):
		thuc_te = _endpoints(search_guard)
		thua = set(SEARCH_GUARD_AP_QUA_HOOK) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")

	def test_moi_endpoint_kiem_hang_va_hen_giao_deu_da_khai_bao(self):
		thuc_te = _endpoints(portal_kiem_hang) | _endpoints(portal_hen_giao)
		chua_khai = thuc_te - set(STAFF_ONLY_MIEN_PHAM_VI)
		self.assertFalse(
			chua_khai,
			f"Endpoint chưa khai báo: {sorted(chua_khai)}. Thêm vào "
			"STAFF_ONLY_MIEN_PHAM_VI (nếu role-gated) hoặc xử lý phạm vi "
			"khoa nếu khách cổng gọi được.",
		)

	def test_khong_khai_bao_thua_kiem_hang_va_hen_giao(self):
		thuc_te = _endpoints(portal_kiem_hang) | _endpoints(portal_hen_giao)
		thua = set(STAFF_ONLY_MIEN_PHAM_VI) - thuc_te
		self.assertFalse(thua, f"Khai báo cho endpoint không còn tồn tại: {sorted(thua)}")
