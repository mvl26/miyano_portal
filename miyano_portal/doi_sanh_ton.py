"""Đối sánh tồn kho của MIYANO trên Sales Order, và Material Request cho
phần thiếu.

Spec: docs/superpowers/specs/2026-10-12-doi-sanh-ton-kho-khi-tao-so-design.md

KHÔNG nhầm với CR-04 (`kho/can_cu_duyet.py`): CR-04 là tồn tại kho của BỆNH
VIỆN, cho quản lý bệnh viện duyệt số lượng đặt. Ở đây là tồn tại kho của
Miyano (`Bin`, `Batch`), cho nhân viên Miyano xác nhận đơn.

Ba lớp, từ trong ra ngoài:

1. Hàm thuần — nhận số, trả số. Mọi quy tắc tính nằm ở đây.
2. Hàm đọc CSDL — mỗi hàm một nguồn.
3. Hai endpoint — chốt vai nội bộ rồi mới gọi hai lớp trên.
"""

import frappe
from frappe.utils import cint, flt, getdate, today

# Tài khoản cổng khách hàng ĐỌC ĐƯỢC đơn của chính họ
# (`permissions.sales_has_permission`), nên "có quyền đọc Sales Order" không
# chặn được họ. Chốt bằng danh sách vai đặt tên rõ, theo tiền lệ
# `portal_hen_giao.ROLE_HEN_GIAO`.
ROLE_NOI_BO = (
	"System Manager",
	"Sales Manager",
	"Sales User",
	"Stock Manager",
	"Stock User",
	"Purchase Manager",
	"Purchase User",
)

# Số lượng tồn kho của ERPNext mặc định 3 chữ số thập phân.
DO_CHINH_XAC = 3

LY_DO_DAT_NGOAI = "Hàng chưa có mã — chưa khớp được mặt hàng"
LY_DO_KHONG_TON = "Mặt hàng không quản lý tồn kho"
LY_DO_KHONG_KHO = "Dòng đơn chưa có kho"
LY_DO_GIAO_THANG = "Nhà cung cấp giao thẳng — không qua kho Miyano"
LY_DO_BO = "Bộ sản phẩm — tồn nằm ở các mặt hàng thành phần"

DX_DU = "du"
DX_CAN_MUA = "can_mua"
DX_MOT_PHAN = "mr_mot_phan"
DX_DA_CO_MR = "da_co_mr"


# ---------------------------------------------------------------- hàm thuần
def sl_con_giao(stock_qty, qty, delivered_qty) -> float:
	"""Phần CÒN PHẢI GIAO của một dòng đơn, theo đơn vị tồn kho.

	`stock_qty` là cả dòng theo đơn vị tồn kho; `qty` và `delivered_qty` theo
	đơn vị bán. Đơn đã giao một phần mà vẫn đòi đủ `stock_qty` thì luôn báo
	thiếu sai — hàng đã giao đã rời kho rồi.
	"""
	qty = flt(qty)
	if qty <= 0:
		return 0.0
	con = max(qty - flt(delivered_qty), 0)
	return flt(flt(stock_qty) * con / qty, DO_CHINH_XAC)


def ton_kha_dung(ton_hien_tai, ton_het_han, giu_don_khac) -> float:
	"""Tồn có thể sử dụng = tồn hiện tại − lô hết hạn − đã giữ cho đơn khác.

	`ton_het_han` là tổng tồn của các lô ĐÃ hết hạn — chỉ trừ thứ BIẾT CHẮC
	là hết hạn. Mặt hàng không theo lô thì truyền 0.
	"""
	dung_duoc = flt(ton_hien_tai) - max(flt(ton_het_han), 0)
	return flt(max(dung_duoc - flt(giu_don_khac), 0), DO_CHINH_XAC)


def chia_ton(yeu_cau, kha_dung) -> list:
	"""Chia tồn có thể sử dụng cho các dòng theo thứ tự dòng.

	`yeu_cau`: `[(khoa, so_luong), ...]`, `khoa = (item_code, kho)`.
	`kha_dung`: `{khoa: so_luong}`.
	Trả `[(ton_dong_nay_thay, so_thieu), ...]` cùng thứ tự.

	Hai dòng cùng mặt hàng, cùng kho dùng CHUNG một lượng tồn: dòng trước lấy
	trước, dòng sau chỉ thấy phần còn lại.
	"""
	con = {k: max(flt(v), 0) for k, v in kha_dung.items()}
	ket_qua = []
	for khoa, sl in yeu_cau:
		thay = flt(con.get(khoa), DO_CHINH_XAC)
		cap = min(flt(sl), thay)
		con[khoa] = thay - cap
		ket_qua.append((thay, flt(flt(sl) - cap, DO_CHINH_XAC)))
	return ket_qua


def de_xuat(sl_thieu, mr_da_phu) -> dict:
	"""Cột "Đề xuất" của một dòng (spec §5.4).

	`mr_da_phu` là phần MR CHƯA NHẬN VỀ KHO. Chỉ tính tới mức bằng số thiếu:
	MR 10 cho một dòng nay chỉ còn thiếu 6 thì phủ 6, không phải 10.
	"""
	thieu = max(flt(sl_thieu), 0)
	phu = min(max(flt(mr_da_phu), 0), thieu)
	can_mua = flt(thieu - phu, DO_CHINH_XAC)
	if thieu <= 0:
		ma = DX_DU
	elif phu <= 0:
		ma = DX_CAN_MUA
	elif can_mua > 0:
		ma = DX_MOT_PHAN
	else:
		ma = DX_DA_CO_MR
	return {"ma": ma, "mr_da_phu": flt(phu, DO_CHINH_XAC), "can_mua": can_mua}


def ly_do_khong_tra(row, thong_tin_item, la_bo: bool):
	"""Vì sao KHÔNG tra được tồn cho dòng này, hoặc `None` nếu tra được.

	Dòng có lý do thì các cột tồn hiện `—`, không hiện 0: "tồn 0" nghĩa là
	hết hàng, "không biết" là chuyện khác.
	"""
	# Bộ sản phẩm xét TRƯỚC: ERPNext buộc mã gộp của Product Bundle là mặt
	# hàng KHÔNG quản lý tồn, nên xét sau thì lý do này không bao giờ hiện.
	if la_bo:
		return LY_DO_BO
	if not thong_tin_item or not cint(thong_tin_item.get("is_stock_item")):
		return LY_DO_KHONG_TON
	if cint(row.get("delivered_by_supplier")):
		return LY_DO_GIAO_THANG
	if not row.get("warehouse"):
		return LY_DO_KHONG_KHO
	return None
