"""Giá theo Price List của khách (spec 2026-10-09 §6).

Phần CẤU TRÚC ở `them_truong()`. Phần DỮ LIỆU (bảng giá riêng, chép giá hợp
đồng, đóng dấu đơn đang dở) ở `chuyen_du_lieu()`.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def them_truong():
	# Hai doctype có thêm lựa chọn / trường mới trong .json: site cũ chỉ thấy
	# sau khi nạp lại, nên reload ở đây thay vì chờ `bench migrate`.
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua_item")
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua")
	create_custom_fields({
		"Sales Order Item": [
			{
				"fieldname": "custom_nguon_gia", "label": "Nguồn giá",
				"fieldtype": "Select", "options": "\nBảng giá\nBáo giá",
				"insert_after": "rate", "read_only": 1, "no_copy": 1,
				"in_list_view": 1, "columns": 1,
				"description": "Bảng giá: đơn giá lấy từ Price List của khách. Báo giá: Miyano điền, ghi vào Price List khi khách đồng ý.",
			},
			{
				"fieldname": "custom_gia_khach_dong_y", "label": "Giá khách đã đồng ý",
				"fieldtype": "Currency", "insert_after": "custom_nguon_gia",
				"read_only": 1, "no_copy": 1,
			},
		],
	}, ignore_validate=True)

	# `custom_loai_don` là Custom Field (không có Property Setter), nên lựa chọn
	# nằm ở `options` của chính nó. Giữ "Theo HĐNT" cho đơn cũ.
	ten = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "custom_loai_don"}, "name"
	)
	if ten:
		lua_chon = (frappe.db.get_value("Custom Field", ten, "options") or "").split("\n")
		if "Theo bảng giá" not in lua_chon:
			lua_chon.append("Theo bảng giá")
			frappe.db.set_value("Custom Field", ten, "options", "\n".join(lua_chon))
			frappe.clear_cache(doctype="Sales Order")
	else:
		# Không ném lỗi (phần dữ liệu của patch vẫn phải chạy), nhưng cũng
		# không bỏ qua trong im lặng: thiếu lựa chọn này thì đơn "Theo bảng
		# giá" đầu tiên hỏng ở phép kiểm Select của `custom_loai_don`.
		frappe.log_error(
			title="Patch v1_41: thiếu Custom Field custom_loai_don",
			message=(
				"Không tìm thấy Custom Field `custom_loai_don` trên Sales Order "
				"nên CHƯA thêm được lựa chọn \"Theo bảng giá\". Tạo lại field "
				"(patch v1_8 `create_e6_mua_le_custom_fields`) rồi chạy lại "
				"`miyano_portal.patches.v1_41.gia_theo_price_list.them_truong`."
			),
		)


def _tung_khach(khach, viec, ten_buoc):
	"""Chạy `viec(kh)` cho từng khách, mỗi khách trong một savepoint.

	Dữ liệu thật có khách hỏng (bảng giá bị xoá, Item lạ trên hợp đồng...).
	Một khách hỏng không được chặn cả patch, cũng không được để lại nửa chừng
	(đã tạo bảng mà chưa gán): lùi về savepoint, ghi Error Log kèm tên khách,
	đi tiếp. Trả `(kết quả theo khách, danh sách khách lỗi)`.
	"""
	ket_qua, loi = {}, []
	for kh in khach:
		diem = "v141" + frappe.generate_hash(length=10)
		frappe.db.savepoint(diem)
		try:
			ket_qua[kh] = viec(kh)
			frappe.db.release_savepoint(diem)
		except Exception:
			frappe.db.rollback(save_point=diem)
			frappe.log_error(
				title=f"Patch v1_41 ({ten_buoc}): {kh}"[:140],
				message=f"Khách hàng: {kh}\n\n{frappe.get_traceback()}",
			)
			loi.append(kh)
	return ket_qua, loi


def chuyen_du_lieu():
	"""Spec 2026-10-09 §6, bước 2–3 và đoạn "đơn đang dở". Chạy lại nhiều lần
	cho cùng kết quả: bảng đã riêng thì giữ, giá đã khớp thì không ghi, dòng đã
	có dấu thì không đụng."""
	from miyano_portal import bang_gia_khach, gia_hdnt
	from miyano_portal.chot_bao_gia import TT_CHO_XAC_NHAN
	from miyano_portal.portal_mua_le import (
		ITEM_GIU_CHO, LOAI_DON_BAO_GIA, TRANG_THAI_CHO_KHACH,
	)

	khach = frappe.get_all(
		"Customer", filters={"disabled": 0}, pluck="name", order_by="name asc"
	)

	# 1. Bảng giá riêng cho MỌI khách đang hoạt động — phải xong trước bước 2,
	#    vì bảng đích của `dong_bo` là bảng riêng của khách.
	def _bang_rieng(kh):
		truoc = frappe.db.get_value("Customer", kh, "default_price_list")
		sau = bang_gia_khach.dam_bao_bang_gia_rieng(kh)
		return None if sau == truoc else ("tach" if truoc else "tao")

	bang, loi_bang = _tung_khach(khach, _bang_rieng, "bảng giá riêng")

	# 2. Chép giá từ hợp đồng đã ký (`dong_bo` tự loại hợp đồng hết hạn). Nhiều
	#    khách chỉ có giá nhờ hợp đồng; bỏ bước này thì hàng của họ rơi về "chờ
	#    báo giá". MỌI khách có hợp đồng, kể cả khách đã vô hiệu hoá (§6 bước
	#    3): `dong_bo` tự bảo đảm bảng riêng cho khách của hợp đồng, nên giá của
	#    một khách đã vô hiệu hoá không rơi vào bảng của khách khác.
	co_hop_dong = sorted(
		kh for kh in set(frappe.get_all(
			"Blanket Order",
			filters={"blanket_order_type": "Selling", "docstatus": 1},
			pluck="customer",
		)) if kh and kh not in loi_bang
	)
	gia, loi_gia = _tung_khach(co_hop_dong, gia_hdnt.dong_bo_khach, "giá hợp đồng")

	# 3. Đơn báo giá đang dở: đóng dấu "Báo giá" để khi khách đồng ý thì giá
	#    vẫn được ghi (dòng cũ có dấu rỗng, `ghi_gia_da_dong_y` bỏ qua chúng).
	#    Không đụng `modified`: đây không phải một lần ai đó sửa đơn.
	dong = frappe.db.sql(
		"""select soi.name
		   from `tabSales Order Item` soi
		   inner join `tabSales Order` so on so.name = soi.parent
		   where so.docstatus = 0
		     and so.custom_nguon_don = 'Client Portal'
		     and so.custom_loai_don = %(loai)s
		     and so.workflow_state in %(trang_thai)s
		     and ifnull(soi.custom_nguon_gia, '') = ''
		     and ifnull(soi.blanket_order, '') = ''
		     and soi.item_code != %(giu_cho)s""",
		{
			"loai": LOAI_DON_BAO_GIA,
			"trang_thai": (TT_CHO_XAC_NHAN, TRANG_THAI_CHO_KHACH),
			"giu_cho": ITEM_GIU_CHO,
		},
		pluck=True,
	)
	if dong:
		frappe.db.sql(
			"update `tabSales Order Item` set custom_nguon_gia = %s where name in %s",
			(bang_gia_khach.NGUON_BAO_GIA, tuple(dong)),
		)

	viec = list(bang.values())
	loi = loi_bang + loi_gia
	co_ghi = [kh for kh, k in gia.items() if k["tao"] or k["cap_nhat"]]
	print(
		f"[miyano_portal] v1_41 giá theo Price List: {viec.count('tao')} bảng giá "
		f"tạo mới, {viec.count('tach')} bảng tách khỏi bảng dùng chung; "
		f"{len(gia)} khách có hợp đồng được rà, {len(co_ghi)} khách có giá được ghi "
		f"({sum(k['tao'] for k in gia.values())} dòng tạo, "
		f"{sum(k['cap_nhat'] for k in gia.values())} dòng cập nhật); "
		f"{len(dong)} dòng đơn báo giá đang dở được đóng dấu; "
		f"{len(loi)} khách lỗi"
		+ (f" (xem Error Log): {', '.join(loi)}." if loi else ".")
	)


def execute():
	them_truong()
	chuyen_du_lieu()
