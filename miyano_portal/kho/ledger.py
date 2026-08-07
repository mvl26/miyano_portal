"""Engine ghi sổ kho khách hàng.

`Customer Stock Ledger Entry` là nguồn sự thật duy nhất: chỉ ghi thêm, không
sửa, không xoá. `Customer Stock Lot Balance` là cache dẫn xuất, tái dựng lại
được bất cứ lúc nào bằng rebuild_lot_balance().

Cố ý KHÔNG dùng Stock Ledger Entry / Bin của ERPNext: kho khách không thuộc
Company nào, và cả hai company của Miyano đều bật perpetual inventory nên mọi
bút toán kho ở đó đều chảy vào sổ kế toán của Miyano.
"""

import frappe

LOT_KHONG_CO = "KHONG-LO"

# Số lượng nhỏ hơn ngưỡng này coi như bằng 0, tránh rác do sai số dấu phẩy động
# tích luỹ qua nhiều lần cộng trừ.
EPS = 0.0005


def _lot_balance_name(kho: str, vat_tu: str, so_lo: str) -> str | None:
	return frappe.db.get_value(
		"Customer Stock Lot Balance",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo},
		"name",
	)


def _current_qty(kho: str, vat_tu: str, so_lo: str) -> float:
	name = _lot_balance_name(kho, vat_tu, so_lo)
	if not name:
		return 0.0
	return float(frappe.db.get_value("Customer Stock Lot Balance", name, "so_luong") or 0)


def _ensure_non_negative(kho, vat_tu, so_lo, cu_qty, delta):
	"""Chặn một bút toán đẩy tồn của lô xuống âm.

	Tồn âm không chỉ vô nghĩa vật lý: nó còn âm thầm phá đơn giá bình quân gia
	quyền của lần nhập tiếp theo (cu_qty âm kéo don_gia lệch), và vì
	get_lot_balances() lọc so_luong > EPS nên một lô đang âm biến mất khỏi mọi
	báo cáo thay vì báo lỗi. Gọi ở hai điểm: post_lines() gọi trước khi insert
	dòng sổ (để không bao giờ ghi một dòng làm tồn âm vào sổ append-only,
	không xoá được), và _apply_to_balance() gọi lại làm lưới an toàn thứ hai
	cho rebuild_lot_balance() — nơi replay thẳng từ sổ, không đi qua
	post_lines().
	"""
	moi_qty = cu_qty + float(delta)
	if moi_qty < -EPS:
		frappe.throw(
			f"Không đủ tồn để xuất lô {so_lo} (vật tư {vat_tu}, kho {kho}): "
			f"tồn hiện có {cu_qty}, yêu cầu xuất {abs(float(delta))}.",
			frappe.ValidationError,
		)


def _apply_to_balance(kho, vat_tu, so_lo, han_su_dung, delta, don_gia):
	"""Cộng `delta` vào tồn của một lô và cập nhật đơn giá bình quân gia quyền.

	TÍNH LẠI BÌNH QUÂN CHO CẢ delta ÂM — ĐỪNG "ĐƠN GIẢN HOÁ" LẠI.

	Cám dỗ hiển nhiên là chỉ tính lại khi delta > 0, vì với phiếu XUẤT thường
	thì phép tính lại đúng là một no-op: dòng xuất luôn mang chính đơn giá bình
	quân hiện hành của lô (`_lay_gia_va_han_tu_lo` đọc thẳng từ lô), nên
	(Q·P − q·P)/(Q − q) = P. Bỏ nhánh âm đi mà không có gì đỏ lên.

	Nhưng KHÔNG phải mọi dòng âm đều là phiếu xuất. Phiếu đảo của một phiếu
	NHẬP cũng ghi một dòng âm, và nó mang đơn giá GỐC lúc nhập chứ không phải
	bình quân hiện hành — đó là điều bắt buộc, nếu không việc huỷ phiếu sẽ tự
	sinh hoặc tự huỷ tiền (xem `_lay_gia_va_han_tu_lo`). Nếu không tính lại
	bình quân ở nhánh âm, sổ trừ đi `delta × giá_gốc` còn cache chỉ trừ
	`delta × bình_quân_hiện_hành`, và hai bên lệch VĨNH VIỄN: sổ là append-only
	nên không sửa được, còn `rebuild_lot_balance()` replay đúng hàm này nên lặp
	lại y nguyên phép tính sai. Đo được: nhập 100@50k, xuất 30, nhập 100@70k,
	huỷ phiếu xuất, huỷ phiếu nhập 50k → sổ 7.000.000, cache 6.000.000.

	Công thức chung giữ đúng bất biến giá trị theo cấu trúc, vì
	    tồn_mới × giá_mới = tồn_cũ × giá_cũ + delta × đơn_giá_dòng,
	tức là đúng số mà dòng sổ vừa cộng vào tổng `gia_tri` của sổ. Xem
	`TestKhoBatBienGiaTri` và thiết kế mục 3.

	Ý nghĩa kinh tế của nhánh âm: sau khi huỷ phiếu nhập 100 @ 50.000 khỏi một
	lô đang có 200 đơn vị bình quân 60.000, 100 đơn vị còn lại mang
	(12.000.000 − 5.000.000) / 100 = 70.000 — đúng thực tế, phần còn lại chính
	là lô đã nhập giá 70.000.
	"""
	name = _lot_balance_name(kho, vat_tu, so_lo)
	if name:
		bal = frappe.get_doc("Customer Stock Lot Balance", name)
	else:
		bal = frappe.new_doc("Customer Stock Lot Balance")
		bal.kho = kho
		bal.vat_tu = vat_tu
		bal.so_lo = so_lo
		bal.so_luong = 0
		bal.don_gia = 0

	cu_qty = float(bal.so_luong or 0)
	# Giữ nguyên lưới an toàn: tồn kết quả dưới -EPS bị chặn TRƯỚC khi bất kỳ
	# thứ gì được ghi, kể cả đơn giá.
	_ensure_non_negative(kho, vat_tu, so_lo, cu_qty, delta)
	moi_qty = cu_qty + float(delta)

	if abs(moi_qty) > EPS:
		bal.don_gia = (
			cu_qty * float(bal.don_gia or 0) + float(delta) * float(don_gia)
		) / moi_qty
	elif cu_qty <= EPS:
		# Lô mới toanh (hoặc đang rỗng) nhận một dòng ~0: không có bình quân cũ
		# nào để giữ, lấy luôn đơn giá của dòng.
		bal.don_gia = float(don_gia)
	# Còn lại: tồn kết quả về 0. Không chia được, nên GIỮ NGUYÊN đơn giá cũ
	# thay vì chia cho 0 hay đặt về 0. Hệ quả đã biết và chấp nhận: `gia_tri`
	# được lưu dưới dạng so_luong × don_gia nên nó buộc phải bằng 0, trong khi
	# tổng của sổ có thể còn dư một phần chênh nếu dòng cuối mang đơn giá khác
	# bình quân (chỉ xảy ra với phiếu đảo của phiếu nhập). Xem
	# test_lo_ve_khong_khong_giu_duoc_gia_tri_du.

	bal.so_luong = 0.0 if abs(moi_qty) < EPS else moi_qty
	# Hạn dùng ghi lần đầu; lần nhập sau của cùng lô không được ghi đè bằng
	# giá trị rỗng, nhưng được phép bổ sung nếu trước đó chưa có.
	if han_su_dung and not bal.han_su_dung:
		bal.han_su_dung = han_su_dung
	bal.gia_tri = float(bal.so_luong) * float(bal.don_gia or 0)
	bal.flags.ignore_permissions = True
	bal.save(ignore_permissions=True)


def post_lines(voucher, lines: list[dict]) -> list[str]:
	"""Ghi các dòng của một phiếu vào sổ và cập nhật tồn theo lô.

	`so_luong` trong mỗi dòng đã mang dấu: dương là nhập, âm là xuất.
	Bỏ qua dòng đã ghi rồi (khoá theo `chung_tu_row`) nên gọi lại an toàn.
	"""
	created = []
	for line in lines:
		row_id = line["chung_tu_row"]
		if frappe.db.exists(
			"Customer Stock Ledger Entry",
			{
				"chung_tu_type": voucher.doctype,
				"chung_tu": voucher.name,
				"chung_tu_row": row_id,
			},
		):
			continue

		so_luong = float(line["so_luong"])
		don_gia = float(line.get("don_gia") or 0)

		# Chặn TRƯỚC khi insert dòng sổ: sổ là append-only, không xoá được, nên
		# nếu chặn muộn hơn (trong _apply_to_balance, sau insert) một dòng làm
		# tồn âm sẽ đã nằm vĩnh viễn trong sổ trước khi lỗi được ném ra.
		_ensure_non_negative(
			voucher.kho, line["vat_tu"], line["so_lo"],
			_current_qty(voucher.kho, line["vat_tu"], line["so_lo"]), so_luong,
		)

		entry = frappe.new_doc("Customer Stock Ledger Entry")
		entry.kho = voucher.kho
		entry.ngay = voucher.ngay
		entry.vat_tu = line["vat_tu"]
		entry.so_lo = line["so_lo"]
		entry.han_su_dung = line.get("han_su_dung")
		entry.so_luong = so_luong
		entry.don_gia = don_gia
		entry.gia_tri = so_luong * don_gia
		entry.chung_tu_type = voucher.doctype
		entry.chung_tu = voucher.name
		entry.chung_tu_row = row_id
		entry.flags.ignore_permissions = True
		entry.insert(ignore_permissions=True)
		created.append(entry.name)

		_apply_to_balance(
			voucher.kho, line["vat_tu"], line["so_lo"],
			line.get("han_su_dung"), so_luong, don_gia,
		)
	return created


def get_lot_balance(kho: str, vat_tu: str, so_lo: str) -> dict | None:
	return frappe.db.get_value(
		"Customer Stock Lot Balance",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo},
		["name", "so_luong", "don_gia", "han_su_dung"],
		as_dict=True,
	)


def get_lot_balances(kho: str, vat_tu: str) -> list[dict]:
	"""Các lô còn tồn của một vật tư, sắp theo FEFO.

	Hạn gần nhất xuất trước; lô không có hạn dùng xếp cuối vì không thể so sánh
	với lô có hạn — để chúng lên đầu sẽ khiến hàng sắp hết hạn nằm lại kho.
	"""
	rows = frappe.get_all(
		"Customer Stock Lot Balance",
		filters={"kho": kho, "vat_tu": vat_tu, "so_luong": [">", EPS]},
		fields=["name", "so_lo", "han_su_dung", "so_luong", "don_gia"],
	)
	return sorted(
		rows,
		key=lambda r: (r["han_su_dung"] is None, r["han_su_dung"] or "", r["so_lo"]),
	)


def mark_reversed(chung_tu_type: str, chung_tu: str) -> None:
	frappe.db.set_value(
		"Customer Stock Ledger Entry",
		{"chung_tu_type": chung_tu_type, "chung_tu": chung_tu},
		"da_dao",
		1,
		update_modified=False,
	)


def rebuild_lot_balance(kho: str | None = None) -> int:
	"""Dựng lại toàn bộ tồn theo lô từ sổ.

	Lưới an toàn khi nghi ngờ cache lệch sổ. Chạy được từ dòng lệnh:
	    bench --site <site> execute miyano_portal.kho.ledger.rebuild_lot_balance
	"""
	filters = {"kho": kho} if kho else {}
	frappe.db.delete("Customer Stock Lot Balance", filters)

	entries = frappe.get_all(
		"Customer Stock Ledger Entry",
		filters=filters,
		fields=["kho", "vat_tu", "so_lo", "han_su_dung", "so_luong", "don_gia"],
		# creation không đủ để làm tiebreaker duy nhất: dữ liệu di trú (xem
		# miyano_portal/migration/export_supplycore.py) có thể giữ nguyên
		# timestamp gốc và trùng creation giữa các dòng, hoặc hai insert rơi
		# cùng micro giây. _apply_to_balance không giao hoán trên don_gia nên
		# thứ tự replay phải xác định — dãy SKK-.######### tăng dần đơn điệu
		# nên dùng name làm tiebreaker.
		order_by="creation asc, name asc",
	)
	for e in entries:
		_apply_to_balance(
			e["kho"], e["vat_tu"], e["so_lo"], e["han_su_dung"],
			float(e["so_luong"]), float(e["don_gia"] or 0),
		)
	return frappe.db.count("Customer Stock Lot Balance", filters)


# he_so_dau mirrors _he_so_dau()/on_submit() of the two voucher controllers —
# duplicated here (not imported) because pulling in the controller classes
# would create an import cycle (controllers import `ledger`, not the reverse).
_HE_SO_DAU = {
	"Customer Stock Receipt": lambda loai: -1.0 if loai == "Phiếu đảo" else 1.0,
	"Customer Stock Issue": lambda loai: 1.0 if loai == "Phiếu đảo" else -1.0,
}
_LOAI_FIELD = {"Customer Stock Receipt": "loai_nhap", "Customer Stock Issue": "loai_xuat"}


def replay_vouchers_into_ledger(doctype: str | None = None, kho: str | None = None) -> list[str]:
	"""Ghi lại Sổ Kho Khách (`Customer Stock Ledger Entry`) từ CHÍNH CÁC PHIẾU
	đã tồn tại (`Customer Stock Receipt`/`Customer Stock Issue`), dùng khi sổ
	bị mất/trống nhưng chứng từ nguồn vẫn còn nguyên vẹn.

	Bổ sung cho `rebuild_lot_balance()`, không thay thế: hàm đó dựng lại TỒN
	THEO LÔ từ SỔ; hàm này dựng lại chính SỔ từ CHỨNG TỪ GỐC — cần khi sự cố
	xoá mất cả sổ (không chỉ cache tồn). `post_lines()` đã idempotent theo
	`chung_tu_row`, nên gọi hàm này trên một site đã có đủ sổ là vô hại,
	không ghi thêm dòng nào.

	Phải replay theo ĐÚNG THỨ TỰ TẠO CHỨNG TỪ (autoname `name` tăng đơn điệu
	theo (kho, năm) — xem `voucher.next_voucher_name`): một phiếu ĐẢO luôn
	được tạo SAU phiếu gốc, nên nếu xử lý theo thứ tự `name` tăng dần thì
	dòng dương của phiếu gốc luôn được ghi trước dòng âm bù trừ của nó —
	đảo thứ tự sẽ khiến `_ensure_non_negative()` chặn dòng đảo vì tồn tạm
	thời âm.

	Chứng từ ĐÃ HUỶ (`docstatus=2`) vẫn phải được replay: sổ vẫn phải chứa
	dòng gốc của nó (chỉ đánh dấu `da_dao=1`), đúng bất biến "sổ append-only,
	huỷ không xoá dòng nào" — hàm này tự đánh dấu lại sau khi ghi.

	Chạy được từ dòng lệnh:
	    bench --site <site> execute miyano_portal.kho.ledger.replay_vouchers_into_ledger
	"""
	created: list[str] = []
	for dt in (doctype,) if doctype else ("Customer Stock Receipt", "Customer Stock Issue"):
		loai_field = _LOAI_FIELD[dt]
		he_so_fn = _HE_SO_DAU[dt]
		filters = {"kho": kho} if kho else {}
		names = frappe.get_all(dt, filters=filters, fields=["name"], order_by="name asc", pluck="name")
		for name in names:
			doc = frappe.get_doc(dt, name)
			he_so = he_so_fn(doc.get(loai_field))
			lines = [{
				"vat_tu": r.vat_tu,
				"so_lo": r.so_lo,
				"han_su_dung": r.han_su_dung,
				"so_luong": he_so * float(r.so_luong),
				"don_gia": float(r.don_gia or 0),
				"chung_tu_row": r.name,
			} for r in doc.items]
			created += post_lines(doc, lines)
			if doc.docstatus == 2:
				mark_reversed(dt, doc.name)
	return created
