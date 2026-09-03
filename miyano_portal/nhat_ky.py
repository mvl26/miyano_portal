"""Đường DUY NHẤT ghi vào sổ nhật ký thao tác.

Một hàm, không phải mỗi nơi tự dựng một `frappe.get_doc(...)`: luật
"không bao giờ ném lỗi" và luật "người thao tác là phiên đang gọi" phải
đúng ở MỌI chỗ ghi, mà một luật lặp ở mười hai nơi thì sớm muộn cũng lệch
một nơi — và nơi lệch sẽ là nơi không ai để ý.

Khoá sự kiện là KHOÁ, không phải nhãn (Ruling P54). Nhãn tiếng Việt sống ở
`frontend/src/format.js`. Sổ này là bản ghi VĨNH VIỄN — một khoá đã ghi
xuống thì không sửa được nữa, nên nó tuyệt đối không được mang theo một
quyết định biên tập.
"""

import frappe
from frappe.utils import now_datetime

DOCTYPE = "Portal Nhat Ky Yeu Cau"

VAI_KHOA = "khoa"
VAI_QUAN_LY = "quan_ly"
VAI_MIYANO = "miyano"
VAI_HE_THONG = "he_thong"

SK_KHOA_GUI_DUYET = "khoa_gui_duyet"
SK_KHOA_THU_HOI = "khoa_thu_hoi"
SK_QUAN_LY_DUYET = "quan_ly_duyet"
SK_QUAN_LY_TU_CHOI = "quan_ly_tu_choi"
SK_QUAN_LY_HUY_PHIEU = "quan_ly_huy_phieu"
SK_KHOA_XIN_SUA = "khoa_xin_sua"
SK_QUAN_LY_DUYET_SUA = "quan_ly_duyet_sua"
SK_QUAN_LY_TU_CHOI_SUA = "quan_ly_tu_choi_sua"
SK_DON_TAO = "don_tao"
SK_MIYANO_XAC_NHAN = "miyano_xac_nhan"
SK_MIYANO_BAO_GIA = "miyano_bao_gia"
SK_MIYANO_TU_CHOI = "miyano_tu_choi"
SK_KHACH_DONG_Y = "khach_dong_y"
SK_KHACH_KHONG_DONG_Y = "khach_khong_dong_y"
SK_KHACH_GUI_LAI_BAO_GIA = "khach_gui_lai_bao_gia"
SK_KHACH_HUY_DON = "khach_huy_don"
SK_GIAO_HANG = "giao_hang"
SK_HOA_DON = "hoa_don"


def ghi(su_kien, *, customer, vai, khoa_phong=None, de_xuat=None,
        sales_order=None, nguoi_thao_tac=None, ghi_chu=None,
        thoi_diem=None) -> str | None:
	"""Ghi một dòng. Trả `name`, hoặc `None` khi ghi hỏng.

	KHÔNG BAO GIỜ ném lỗi — hàm này chạy ngay sau những chuyển trạng thái
	ĐÃ THÀNH CÔNG (`gui_duyet()`, `duyet()`, hook giao hàng…). Một trục
	trặc ở khâu ghi mà cuốn theo cả transaction sẽ làm mất đúng thứ vừa
	làm được. Cùng ràng buộc tuyệt đối mà `portal_thong_bao_khach.bao_*`
	đang chịu — và cùng cách xử: nuốt lỗi nhưng để lại dấu ở Error Log,
	vì một `except: pass` trần là cách chắc chắn để mất sự kiện mà không
	ai biết.

	KHÔNG `frappe.db.commit()`: dòng nhật ký phải sống chết cùng giao dịch
	của chuyển trạng thái. Nếu chuyển trạng thái bị rollback thì dòng này
	biến mất theo — sổ không được kể một việc chưa từng xảy ra.
	"""
	try:
		if nguoi_thao_tac is None and vai != VAI_HE_THONG:
			nguoi_thao_tac = frappe.session.user
		doc = frappe.get_doc({
			"doctype": DOCTYPE,
			"customer": customer,
			"khoa_phong": khoa_phong,
			"de_xuat": de_xuat,
			"sales_order": sales_order,
			"thoi_diem": thoi_diem or now_datetime(),
			"su_kien": su_kien,
			"nguoi_thao_tac": nguoi_thao_tac,
			"vai": vai,
			"ghi_chu": ghi_chu,
		}).insert(ignore_permissions=True)
		return doc.name
	except Exception:
		try:
			frappe.log_error(
				title=f"Nhật ký thao tác: không ghi được sự kiện {su_kien}",
				message=frappe.get_traceback(with_context=True),
			)
		except Exception:
			pass
		return None
