"""Backfill đơn giá HĐNT → `Item Price` cho các hợp đồng đã ký TỪ TRƯỚC.

Hook `Blanket Order.on_submit` (`gia_hdnt.tu_hdnt`) chỉ chạy cho hợp đồng ký
từ nay về sau. Hợp đồng đã submit trước đó không bao giờ kích hoạt nó, và đó
chính là hình dạng dữ liệu đã gây lỗi: trên `erptest.local` lúc phát hiện, ba
HĐNT đều đã submit và có `rate`, ba bảng giá HĐNT đều tồn tại, nhưng cả site
có **0 bản ghi `Item Price`** — khách không đặt được mặt hàng nào.

Idempotent theo đúng nghĩa của `gia_hdnt.dong_bo`: dòng đã khớp giá thì không
đụng tới, `bench migrate` chạy lại bao nhiêu lần cũng không sinh trùng.

Hợp đồng đã hết hiệu lực bị `gia_hdnt.dong_bo` tự bỏ qua (xem chốt `to_date`
ở đó) — quét cả danh sách ở đây vẫn đúng, và cố ý không tự lọc lần thứ hai:
hai nơi cùng định nghĩa "hợp đồng còn hiệu lực" là hai nơi có thể lệch nhau.
"""

import frappe

from miyano_portal import gia_hdnt


def execute():
	ten_list = frappe.get_all(
		"Blanket Order",
		filters={"blanket_order_type": "Selling", "docstatus": 1},
		pluck="name",
		order_by="creation asc",
	)

	tong_tao = tong_cap_nhat = 0
	for ten in ten_list:
		try:
			ket_qua = gia_hdnt.dong_bo(ten)
		except Exception:
			# Một hợp đồng hỏng (Item đã xoá, bảng giá bị vô hiệu...) không
			# được chặn `bench migrate` của cả site — ghi log rồi đi tiếp,
			# cùng nguyên tắc với hook.
			frappe.log_error(title=f"Backfill giá HĐNT: bỏ qua {ten}")
			continue
		tong_tao += ket_qua["tao"]
		tong_cap_nhat += ket_qua["cap_nhat"]
		if ket_qua["ly_do"]:
			print(f"  · {ten}: {ket_qua['ly_do']}")
		for bo_qua in ket_qua["bo_qua"]:
			print(f"  · {ten} / {bo_qua['item_code']}: {bo_qua['ly_do']}")

	print(
		f"Đồng bộ giá HĐNT: {len(ten_list)} hợp đồng — "
		f"tạo {tong_tao} Item Price, cập nhật {tong_cap_nhat}."
	)
