"""Endpoint cổng cho `Portal De Xuat Mua` (spec §5).

MỌI hàm ở đây suy `customer` và `khoa_phong` từ PHIÊN ĐĂNG NHẬP qua
`get_portal_member()`, KHÔNG nhận từ client — cùng luật C1 đã áp cho
`portal_order_place`. Một tham số `khoa_phong` nhận từ client sẽ cho nhân
viên khoa A lập phiếu mang tên khoa B.

Module này PHẢI có tên trong `tests/test_pham_vi_endpoint.py` — module mới
không tự động bị test đếm ngược soi tới.

BỐI CẢNH KIẾN TRÚC (Task 5, 19/08/2026) — role `Customer` có ZERO DocPerm
trên `Portal De Xuat Mua` (đã kiểm `tabDocPerm` thực nghiệm, xem
`test_de_xuat_cach_ly.py`), giống ba doctype cổng khác đang chạy thật. Hệ
quả: `frappe.get_list`/`doc.check_permission()` ném `PermissionError` cho
MỌI Website User TRƯỚC KHI hook `has_permission`/`permission_query_
conditions` (Task 4, `permissions.de_xuat_query_condition`/`de_xuat_co_
quyen`) kịp chạy. Hook đó vì thế là LỚP PHÒNG THỦ THỨ HAI, chết có điều
kiện — ĐƯỜNG SỐNG của cổng là các hàm whitelist DƯỚI ĐÂY, và chúng phải tự
hỏi ĐÚNG chốt phạm vi mà tầng hook hỏi (`pham_vi_don()`), không tự chế bộ
lọc riêng.
"""

import frappe

from miyano_portal.portal_context import (
	get_portal_member,
	la_quan_ly,
	lien_he_nguoi_dung,
	pham_vi_don,
	ten_nguoi_dung,
)

DOCTYPE = "Portal De Xuat Mua"


def _phieu_cua_toi(ten: str, *, cho_quan_ly=False):
	"""Lấy phiếu sau khi đã kiểm quyền. Trả `Document`.

	SỬA SAU TASK 4 — `doc.check_permission("read")` KHÔNG dùng được ở đây.
	Role `Customer` có ZERO DocPerm trên doctype này (đã kiểm `tabDocPerm`
	19/08: cả `Portal Item Request`, `Portal Delivery Inspection`,
	`Customer Department`, `Portal De Xuat Mua` đều vậy — quy ước của app,
	không phải thiếu sót). `check_permission` ném `PermissionError` cho MỌI
	Website User TRƯỚC KHI hook `has_permission` có cơ hội chạy.

	Nên đường sống của cổng là ĐÂY, và nó phải hỏi ĐÚNG chốt phạm vi mà
	tầng hook hỏi — `pham_vi_don()` — chứ không tự chế bộ lọc riêng.

	`cho_quan_ly=True` KHÔNG có nghĩa "chỉ quản lý gọi được" — nó nghĩa là
	BỎ vòng kiểm chủ sở hữu, chỉ còn vòng kiểm phạm vi (khách hàng + khoa
	phòng). Dùng cho `de_xuat_chi_tiet`: bất kỳ ai TRONG PHẠM VI (đúng
	khách hàng, đúng khoa — kể cả quản lý, vốn có `pham_vi_don()` rỗng nên
	luôn trong phạm vi) đều xem được chi tiết một phiếu, không riêng người
	tạo ra nó — đúng ý nghĩa "đồng nghiệp cùng khoa xem được phiếu của
	nhau", không phải một đặc quyền chỉ dành cho quản lý.
	"""
	doc = frappe.get_doc(DOCTYPE, ten)
	tv = get_portal_member()
	if doc.customer != tv.customer:
		# Không xác nhận cả sự tồn tại của phiếu thuộc khách khác.
		raise frappe.PermissionError("Phiếu này không thuộc đơn vị của bạn.")
	pv = pham_vi_don()
	khoa_gioi_han = pv.get("custom_khoa_phong")
	if khoa_gioi_han and doc.khoa_phong != khoa_gioi_han:
		raise frappe.PermissionError("Phiếu này không thuộc khoa phòng của bạn.")
	if not cho_quan_ly and doc.owner != frappe.session.user and not la_quan_ly():
		raise frappe.PermissionError("Phiếu này không phải của bạn.")
	return doc


@frappe.whitelist()
def de_xuat_tao_nhap(hdnt=None, **_bo_qua) -> dict:
	"""`**_bo_qua` là CỐ Ý: client cũ/độc hại gửi thêm `customer` hay
	`khoa_phong` thì chúng rơi vào đây và bị vứt, không đi vào doc.

	Task 2 (gộp luồng đặt hàng) — tham số `loai_don` đã bỏ: không frontend
	nào gọi hàm này kèm `loai_don` (chỉ test cũ có, đã sửa cùng task),
	`Portal De Xuat Mua Item.nguon_gia` giờ tự suy TỪNG DÒNG ở `validate()`
	(`PortalDeXuatMua._suy_nguon_gia()`), không còn cần khai loại đơn lúc
	tạo nháp nữa."""
	tv = get_portal_member()
	doc = frappe.get_doc({
		"doctype": DOCTYPE,
		"customer": tv.customer,
		"khoa_phong": tv.khoa_phong,
		"hdnt": hdnt,
		"trang_thai": "Nháp",
	}).insert(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_luu_nhap(ten, items=None, dat_ngoai=None, ngay_can=None,
                     dia_chi_giao=None, ghi_chu=None, ly_do_yeu_cau=None) -> dict:
	doc = _phieu_cua_toi(ten)
	if doc.trang_thai != "Nháp":
		frappe.throw("Chỉ sửa được phiếu đang ở trạng thái Nháp.",
		             frappe.ValidationError)
	if items is not None:
		doc.set("items", frappe.parse_json(items) if isinstance(items, str) else items)
	if dat_ngoai is not None:
		doc.set("dat_ngoai",
		        frappe.parse_json(dat_ngoai) if isinstance(dat_ngoai, str) else dat_ngoai)
	for f, v in (("ngay_can", ngay_can), ("dia_chi_giao", dia_chi_giao),
	             ("ghi_chu", ghi_chu), ("ly_do_yeu_cau", ly_do_yeu_cau)):
		if v is not None:
			doc.set(f, v)
	doc.save(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_xoa_nhap(ten) -> dict:
	"""§5.4b — XOÁ THẬT, chỉ phiếu CHƯA TỪNG gửi duyệt. `on_trash` của
	doctype là chốt cuối; kiểm ở đây chỉ để báo lỗi dễ hiểu hơn. Owner HOẶC
	quản lý (`_phieu_cua_toi()` mặc định `cho_quan_ly=False` đã cho cả hai
	đi qua).

	Review toàn nhánh (03/09/2026) — hỏi `ma_de_xuat`, KHÔNG hỏi trạng
	thái: `thu_hoi()` đưa phiếu ĐÃ gửi duyệt về lại Nháp, nên "đang ở Nháp"
	thôi không còn nghĩa là "chưa ai thấy phiếu này". Lý do đầy đủ (và cái
	mất khi xoá nhầm: `Version`, `Notification Log`, một số trong dãy mã)
	nằm ở `PortalDeXuatMua.on_trash()`. Hai tầng phải hỏi CÙNG một câu —
	tầng này lệch một chữ là người dùng nhận thông điệp của tầng kia, viết
	cho một hoàn cảnh khác."""
	doc = _phieu_cua_toi(ten)
	if doc.ma_de_xuat:
		frappe.throw(
			f'Phiếu {doc.ma_de_xuat} đã từng gửi duyệt nên không xoá được, kể '
			"cả sau khi thu hồi về Nháp. Dùng Huỷ phiếu để giữ lại dấu vết.",
			frappe.ValidationError,
		)
	frappe.delete_doc(DOCTYPE, doc.name, ignore_permissions=True)
	return {"ok": True}


@frappe.whitelist()
def de_xuat_gui_duyet(ten) -> dict:
	"""Chỉ CHỦ PHIẾU (owner) được gửi duyệt — khác `de_xuat_xoa_nhap`/
	`de_xuat_luu_nhap` (owner HOẶC quản lý). Quản lý là người DUYỆT phiếu
	(`doc.duyet()`, Task 6/9), không phải người tự GỬI hộ phiếu của nhân
	viên khác — `_phieu_cua_toi()` một mình sẽ cho quản lý đi qua (nó cũng
	chấp nhận quản lý ở vòng kiểm chủ sở hữu chung), nên endpoint này phải
	tự thêm một chốt owner-only riêng SAU vòng kiểm phạm vi của
	`_phieu_cua_toi()`. Một quản lý tự tạo phiếu cho chính mình vẫn gửi
	được bình thường qua đúng nhánh owner này (họ CHÍNH LÀ owner) — không
	mất khả năng tự duyệt phiếu của mình (`tu_duyet`, xem `PortalDeXuatMua.
	duyet()`)."""
	doc = _phieu_cua_toi(ten)
	if doc.owner != frappe.session.user:
		raise frappe.PermissionError("Chỉ chủ phiếu (người tạo) mới gửi duyệt được.")
	doc.gui_duyet()
	return {"name": doc.name, "ma_de_xuat": doc.ma_de_xuat}


@frappe.whitelist()
def de_xuat_thu_hoi(ten) -> dict:
	"""Chủ đầu tư 03/09/2026 — "NV sửa được đơn ở trạng thái Chờ duyệt".
	Đường đi: thu hồi về Nháp → sửa ở màn Đặt hàng (`de_xuat_luu_nhap`) →
	`de_xuat_gui_duyet` lại. Lý do KHÔNG nới guard khoá cột đề xuất nằm ở
	`PortalDeXuatMua.thu_hoi()` và `test_de_xuat_thu_hoi.py`.

	CHỈ CHỦ PHIẾU — chốt owner-only viết riêng SAU `_phieu_cua_toi()`, đúng
	khuôn `de_xuat_gui_duyet` và vì đúng lý do đó: `_phieu_cua_toi()` một
	mình cho cả quản lý LẪN đồng nghiệp cùng khoa đi qua.

	Quản lý KHÔNG thu hồi hộ được: rút một phiếu khỏi hàng chờ mà không để
	lại lời nào chính là từ chối không ghi lý do — `de_xuat_tu_choi` đã có
	cho việc đó và nó bắt buộc lý do. Quản lý cũng không mất khả năng nào:
	họ sửa số lượng THẲNG lúc duyệt qua `dieu_chinh` (§5.3). Một quản lý tự
	lập phiếu cho mình vẫn thu hồi được — họ CHÍNH LÀ chủ phiếu."""
	doc = _phieu_cua_toi(ten)
	if doc.owner != frappe.session.user:
		raise frappe.PermissionError(
			"Chỉ chủ phiếu (người tạo) mới thu hồi được. Quản lý muốn trả "
			"phiếu về cho khoa thì dùng Từ chối, kèm lý do."
		)
	doc.thu_hoi()
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_danh_sach(trang_thai=None, limit=50) -> list[dict]:
	"""SỬA SAU TASK 4 — KHÔNG dùng `frappe.get_list` tràn được.

	Role `Customer` có ZERO DocPerm trên doctype này, nên `get_list` ném
	`PermissionError` TRƯỚC khi `permission_query_conditions` kịp chạy.
	Hook của Task 4 là LỚP PHÒNG THỦ THỨ HAI — nó sẽ có hiệu lực nếu
	DocPerm bị cấp lại, và nó chặn `GET /api/resource/...`; nhưng hôm nay
	đường đó đã trả 403 cho mọi Website User, tức KÍN HƠN chứ không hở.

	Đường sống là đây. Phải áp CẢ HAI bộ lọc, và lấy đúng chốt mà tầng hook
	đúng hỏi — `get_portal_member()` cho khách, `pham_vi_don()` cho khoa.
	Tự chế bộ lọc riêng ở đây là đi ngược nguồn sự thật thứ hai."""
	tv = get_portal_member()
	loc = {"customer": tv.customer}
	pv = pham_vi_don()
	if pv.get("custom_khoa_phong"):
		loc["khoa_phong"] = pv["custom_khoa_phong"]
	if trang_thai:
		loc["trang_thai"] = trang_thai
	return frappe.get_all(
		DOCTYPE, filters=loc,
		fields=["name", "ma_de_xuat", "khoa_phong", "trang_thai",
		        "thoi_diem_gui", "owner"],
		order_by="modified desc", limit_page_length=int(limit),
	)


@frappe.whitelist()
def de_xuat_chi_tiet(ten) -> dict:
	"""M1 (review tổng 19/08) — dọn sentinel TRƯỚC KHI trả ra ngoài.

	`so_luong_xin_sua` mặc định `-1` (`SO_LUONG_XIN_SUA_TRONG`) là quy ước
	NỘI BỘ nghĩa "dòng này chưa có yêu cầu xin sửa". `doc.as_dict()` thô
	đẩy thẳng `-1` ra API, và mọi tầng hiển thị phải tự biết luật đó — hoặc
	hiện "SL xin sửa: -1" cho người dùng. Đổi về `None` ở ĐÚNG biên giới
	của app là chỗ rẻ nhất và duy nhất không phải lặp lại.

	CHỈ đổi giá trị ÂM: `0` là một yêu cầu THẬT ("xin bỏ dòng này", quy ước
	của `portal_order_sua_so_luong`) và phải sống sót nguyên vẹn."""
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	kq = doc.as_dict()
	# Chủ đầu tư chốt 21/08 — khối "Truy vết yêu cầu" phải ghi TÊN NGƯỜI.
	# Suy từ `nguoi_yeu_cau` nếu có, nếu không thì `owner`: phiếu lập qua
	# giao diện thật KHÔNG điền `nguoi_yeu_cau` (không đường mã nào ghi
	# field đó cho doctype này), nên `owner` mới là người đề nghị thật —
	# đúng thứ tự mà `DeXuatDetail.vue` vẫn đang hiển thị. Giải một lần ở
	# BIÊN GIỚI API, cùng chỗ và cùng lý do với việc dọn sentinel dưới đây.
	kq["nguoi_yeu_cau_ten"] = ten_nguoi_dung(
		kq.get("nguoi_yeu_cau") or kq.get("owner")
	)
	# Task 6 (nhật ký thao tác, spec §8) — SỐ ĐIỆN THOẠI đi CÙNG chỗ, CÙNG lý
	# do với tên: một hàm duy nhất (`lien_he_nguoi_dung`, đã dựng ở Task 5
	# cho endpoint đọc sổ) tra `User.mobile_no`/`phone`, không một bản tra
	# thứ hai viết riêng cho khối truy vết. `cho_hien_tai_khoan=True` (mặc
	# định) — người yêu cầu LUÔN là người của CHÍNH bệnh viện đang xem màn
	# này, không phải nhân sự Miyano, nên ranh giới §8 (giấu email Miyano)
	# không áp ở đây.
	kq["nguoi_yeu_cau_dien_thoai"] = lien_he_nguoi_dung(
		kq.get("nguoi_yeu_cau") or kq.get("owner")
	)["dien_thoai"]
	# Vá Minor #6 (review 03/09) — `nguoi_duyet` đang hiện THẲNG email trên
	# `KhoiTruyVet.vue`. Thêm `nguoi_duyet_ten`/`nguoi_duyet_dien_thoai` bên
	# cạnh, KHÔNG đổi giá trị field gốc `nguoi_duyet` (vẫn email nguyên vẹn —
	# đúng luật đã ghi ở `nguoi_yeu_cau_ten` phía trên). `lien_he_nguoi_dung`
	# tự trả rỗng khi `nguoi_duyet` chưa có (phiếu chưa ai duyệt) — không cần
	# tự bọc `if`.
	lh_duyet = lien_he_nguoi_dung(kq.get("nguoi_duyet"))
	kq["nguoi_duyet_ten"] = lh_duyet["ten"]
	kq["nguoi_duyet_dien_thoai"] = lh_duyet["dien_thoai"]
	dong = kq.get("items") or []
	# Task 10 — `boi_so` (quy cách đóng gói) đi CÙNG dòng phiếu, không chỉ
	# cùng kết quả tìm kiếm của `portal_catalog_gop`. Màn Đặt hàng chặn bội
	# số ngay tại ô số lượng; một phiếu Nháp MỞ LẠI để sửa tiếp không đi qua
	# ô tìm kiếm nữa, nên nếu không mang bội số theo đường này thì đúng lỗi
	# "7 hộp của lốc 10" lại nổ vào mặt QUẢN LÝ lúc duyệt — cho một con số
	# quản lý không hề chọn. `None` (KHÔNG phải `0`/`1`) = không ràng buộc,
	# cùng quy ước `portal_catalog_gop`/`kiem_boi_so()`.
	#
	# MỘT truy vấn cho cả phiếu, không hỏi từng dòng.
	boi_so_theo_ma = {
		r.name: int(r.custom_boi_so_dat or 0) or None
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", [d.get("item_code") for d in dong if d.get("item_code")] or [""]]},
			fields=["name", "custom_boi_so_dat"],
		)
	}
	# Ruling P51 — SỐ ĐANG CÓ TRÊN ĐƠN, cạnh `so_luong_duyet`, không thay
	# nó. Ô "xin sửa số lượng" điền sẵn từ `so_luong_duyet` sẽ cho khoa nhìn
	# một con số CŨ: đường khớp mã dòng gõ tay (`portal_mua_le._gop_hoac_
	# them_dong_hang`, hook `validate` của Sales Order — QĐ-G13) cộng thẳng
	# vào `Sales Order Item.qty` mà không bao giờ đụng `so_luong_duyet`. Khoa
	# đọc 15 trên màn đơn, thấy ô điền sẵn 10, gõ 15 — và đó đúng là cách
	# ngõ cụt "Chờ duyệt sửa" bắt đầu (xem docstring `_loc_thay_doi_that`).
	#
	# Chốt "+" của phiếu nay so với CHÍNH con số này, nên trả nó ra là để
	# màn hình hỏi cùng một câu với server, không phải để thêm một cột nữa.
	# `None` = phiếu chưa có đơn, hoặc dòng không có mặt trên đơn (quản lý
	# đã hạ về 0 lúc duyệt) — hai ca khác nhau với `0`, đừng gộp.
	#
	# MỘT truy vấn cho cả phiếu, cùng khuôn `boi_so` ngay trên.
	#
	# 03/09/2026 (màn chi tiết GỘP) — CÙNG truy vấn này, thêm ba cột. Bảng
	# mặt hàng của màn gộp là MỘT bảng: SL xin / SL duyệt (của phiếu) đứng
	# cạnh Đơn giá / Đã giao (của đơn). Phép nối phải làm Ở ĐÂY chứ không ở
	# JS — `frontend/` không có hạ tầng test nào (package.json chỉ có
	# `build`), nên một hàm nối viết bằng JS là một hàm không ai canh.
	#
	# `None` cho dòng KHÔNG có trên đơn — giữ nguyên quy ước của
	# `so_luong_tren_don` ngay dưới: `0` và "chưa có đơn" là hai ca khác
	# nhau, và một bảng in `0 ₫` cho phiếu Chờ duyệt là nói với khoa rằng
	# hàng của họ giá 0.
	dong_tren_don = {}
	if kq.get("sales_order"):
		dong_tren_don = {
			r.item_code: r
			for r in frappe.get_all(
				"Sales Order Item",
				filters={"parent": kq["sales_order"]},
				fields=["item_code", "qty", "rate", "amount", "delivered_qty"],
			)
		}
	for row in dong:
		if (row.get("so_luong_xin_sua") or 0) < 0:
			row["so_luong_xin_sua"] = None
		row["boi_so"] = boi_so_theo_ma.get(row.get("item_code"))
		tren_don = dong_tren_don.get(row.get("item_code"))
		row["so_luong_tren_don"] = float(tren_don.qty or 0) if tren_don else None
		row["don_gia_tren_don"] = float(tren_don.rate or 0) if tren_don else None
		row["thanh_tien_tren_don"] = float(tren_don.amount or 0) if tren_don else None
		row["da_giao_tren_don"] = float(tren_don.delivered_qty or 0) if tren_don else None

	# Review Task 7a — `giai_doan` phải là ĐÚNG `_sql_giai_doan()` của danh
	# sách (`api/portal.py`), KHÔNG một bản suy lại ở client. Bản suy ở
	# `ChiTietYeuCau.vue` (trước bản vá này) thiếu ba nhánh — đơn Miyano đã
	# từ chối, đơn đóng sớm (`status = 'Closed'`), báo giá hết hạn — cả ba
	# đọc ra "Đã duyệt" sai sự thật, lệch với chính danh sách đứng cạnh nó.
	# Nhập hàm PRIVATE (`_sql_giai_doan`, có gạch dưới) từ `api/portal.py`
	# CÓ CHỦ Ý, không đổi tên công khai: hàm chỉ có ĐÚNG một khách ngoài
	# module là đây, và `api/portal.py` đã có tiền lệ nhập chéo tương tự
	# (`de_xuat_xin_sua` nhập cả module `portal` để gọi
	# `portal_order_sua_so_luong`) — đổi tên công khai cho một khách duy
	# nhất chỉ thêm diện tích đổi mà không thêm rào chắn nào.
	from miyano_portal.api.portal import _sql_giai_doan

	kq["giai_doan"] = frappe.db.sql(
		f"""select {_sql_giai_doan("p.trang_thai", "so")}
			from `tabPortal De Xuat Mua` p
			left join `tabSales Order` so on so.name = p.sales_order
			where p.name = %s""",
		doc.name,
	)[0][0]
	return kq


def _ap_dieu_chinh(doc, dieu_chinh):
	"""Quản lý chỉ chạm `so_luong_duyet` và `ghi_chu_quan_ly`. Bỏ một mặt
	hàng = HẠ VỀ 0, không xoá dòng (§5.3). Thêm mặt hàng → dòng mới có
	`so_luong_de_xuat = 0`, `nguon_dong = "Quản lý thêm"`.

	CHỈ đọc BA khoá: `item_code` (để KHỚP dòng ĐÃ CÓ, hoặc làm mã của dòng
	mới), `so_luong_duyet` và `ghi_chu_quan_ly` — mọi field khác trong
	payload bị bỏ qua, cùng khuôn `portal_order_sua_so_luong`. (M3, review
	tổng 19/08 — bản trước viết "CHỈ đọc `item_code` và `so_luong_duyet` —
	mọi field khác bị bỏ qua" ngay dưới một câu đã kể đúng cả ba, trong khi
	code đọc `ghi_chu_quan_ly` thật: hai câu mâu thuẫn trong CÙNG một
	docstring, và câu sai là câu mà người đọc dùng để quyết định.)
	"""
	dc = frappe.parse_json(dieu_chinh) if isinstance(dieu_chinh, str) else dieu_chinh
	theo_ma = {d.item_code: d for d in doc.items}
	for row in dc.get("items", []):
		ma = row.get("item_code")
		if ma in theo_ma:
			theo_ma[ma].so_luong_duyet = float(row.get("so_luong_duyet") or 0)
			if row.get("ghi_chu_quan_ly") is not None:
				theo_ma[ma].ghi_chu_quan_ly = row["ghi_chu_quan_ly"]
		else:
			# M3 (review tổng) — CHÉP CẢ `ghi_chu_quan_ly`. Bản trước bỏ nó
			# ở đúng nhánh này, không kèm lý do nào: quản lý gõ lý do cho
			# mặt hàng HỌ VỪA THÊM (chính là dòng cần giải thích nhất — khoa
			# không hề xin nó) thì lý do đó biến mất lặng lẽ.
			doc.append("items", {
				"item_code": ma, "so_luong_de_xuat": 0,
				"so_luong_duyet": float(row.get("so_luong_duyet") or 0),
				"ghi_chu_quan_ly": row.get("ghi_chu_quan_ly"),
				"nguon_dong": "Quản lý thêm",
			})
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def de_xuat_duyet_phieu(ten, dieu_chinh=None) -> dict:
	"""Chốt quyền DUY NHẤT của đường duyệt. Kế hoạch C (uỷ quyền) sửa ĐÚNG
	dòng `la_quan_ly()` này, không đụng `de_xuat_duyet.duyet_va_tao_don`."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới duyệt được đề xuất.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	if dieu_chinh:
		_ap_dieu_chinh(doc, dieu_chinh)
	from miyano_portal import de_xuat_duyet
	return de_xuat_duyet.duyet_va_tao_don(doc.name, frappe.session.user)


@frappe.whitelist()
def de_xuat_tu_choi(ten, ly_do) -> dict:
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới từ chối được đề xuất.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.tu_choi(ly_do)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_xin_sua(ten, dong) -> dict:
	"""Task 9 (§12 Q4) — nhân viên khoa xin sửa số lượng một đơn ĐÃ được
	quản lý duyệt. `_phieu_cua_toi(..., cho_quan_ly=True)`: KHÔNG chỉ chủ
	phiếu — bất kỳ đồng nghiệp nào CÙNG KHOA (trong phạm vi khách hàng +
	khoa của `pham_vi_don()`) đều xin sửa được, không riêng owner. Đơn Sales
	Order KHÔNG bị chạm ở đây — `PortalDeXuatMua.xin_sua()` chỉ ghi lên
	phiếu, đúng thiết kế §12 Q4 (nhân viên vẫn sửa được, nhưng phải quay lại
	quản lý duyệt lần nữa TRƯỚC KHI đơn thật sự đổi).

	`dong` — JSON (hoặc dict) `{"items": [{"item_code": str, "qty": float}]}`,
	cùng hình dạng `dong` của `portal.portal_order_sua_so_luong`."""
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	if isinstance(dong, str):
		dong = frappe.parse_json(dong)
	items = (dong or {}).get("items") or []
	doc.xin_sua(items)
	# M4 (review tổng 19/08) — thông báo RIÊNG cho việc xin sửa. Bản trước
	# gọi lại `bao_de_xuat_gui_duyet`, nên quản lý nhận "Khoa vừa gửi đề
	# xuất mua X chờ bạn duyệt" cho một phiếu ĐÃ DUYỆT TỪ TRƯỚC — sai việc.
	# Người nhận vẫn là "chỉ Quản lý", giống bước gửi duyệt; chỉ tiền tố và
	# nội dung là riêng (xem docstring `bao_de_xuat_xin_sua`).
	from miyano_portal.portal_thong_bao_khach import bao_de_xuat_xin_sua
	bao_de_xuat_xin_sua(doc)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_duyet_sua(ten) -> dict:
	"""Chỉ quản lý — ĐỒNG Ý yêu cầu xin sửa: gọi lõi `portal.portal_order_
	sua_so_luong` DƯỚI QUYỀN QUẢN LÝ đang gọi (guard `dam_bao_duoc_sua_don_
	da_duyet` cho qua vì `la_quan_ly()` đúng) để sửa THẬT Sales Order, rồi
	mới gọi `doc.duyet_sua()` dọn phần còn lại trên phiếu. Thứ tự này CỐ Ý:
	nếu sửa đơn thất bại (hết hiệu lực báo giá, đơn không còn ở đúng
	trạng thái...), phiếu KHÔNG được chuyển "Đã duyệt" sớm hơn thật.

	I2 (review Task 9) — lọc `d.so_luong_xin_sua >= 0`, KHÔNG lọc truthy:
	`0` là một yêu cầu THẬT ("xin bỏ dòng này", đúng quy ước của
	`portal_order_sua_so_luong`), không phải "chưa có gì để duyệt". Lọc
	truthy (bản đầu của Task 9) làm rớt LẶNG LẼ đúng yêu cầu nguy hiểm nhất."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới duyệt yêu cầu xin sửa được.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	dong = {
		"items": [
			{"item_code": d.item_code, "qty": float(d.so_luong_xin_sua)}
			for d in doc.items if d.so_luong_xin_sua >= 0
		]
	}
	from miyano_portal.api import portal
	portal.portal_order_sua_so_luong(doc.sales_order, dong)
	doc.reload()
	doc.duyet_sua()
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_tu_choi_sua(ten, ly_do) -> dict:
	"""Chỉ quản lý — TỪ CHỐI yêu cầu xin sửa: đơn giữ NGUYÊN, không gọi lõi
	`portal_order_sua_so_luong` chút nào — chỉ dọn phiếu."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới từ chối yêu cầu xin sửa được.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.tu_choi_sua(ly_do)
	return {"name": doc.name}


@frappe.whitelist()
def de_xuat_huy(ten) -> dict:
	"""§5.4b — từ Chờ duyệt trở đi CHỈ quản lý huỷ được. Nhân viên không
	huỷ phiếu đã gửi: một phiếu đang nằm trong danh sách chờ của quản lý mà
	biến mất giữa chừng là thứ khó chịu nhất cho người duyệt."""
	if not la_quan_ly():
		raise frappe.PermissionError("Chỉ quản lý mới huỷ được phiếu đã gửi.")
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	doc.huy()
	return {"name": doc.name}
