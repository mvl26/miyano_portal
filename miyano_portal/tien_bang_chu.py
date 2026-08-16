"""Đọc số tiền thành chữ TIẾNG VIỆT cho chứng từ kế toán.

`frappe.utils.money_in_words` đọc theo ngôn ngữ hệ thống — site này để tiếng
Anh nên Phiếu xuất kho mẫu 02-VT in ra *"VND Nine Hundred And Fifty Thousand
only."* ở dòng "Tổng số tiền (viết bằng chữ)". Trên một chứng từ kế toán Việt
Nam đó là lỗi, không phải chuyện thẩm mỹ.

Không đổi ngôn ngữ hệ thống để chữa: đổi `language` của site sẽ dịch toàn bộ
Desk sang tiếng Việt — một thay đổi rộng hơn nhiều so với việc cần sửa, và nó
đụng vào mọi người dùng đang quen giao diện hiện tại.

Đăng ký làm Jinja method trong `hooks.py` để mọi mẫu in dùng chung MỘT bản
đọc số. Ba mẫu tự chép mỗi mẫu một kiểu đọc là ba chỗ sẽ lệch nhau.
"""

CHU_SO = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
DON_VI = ("", " nghìn", " triệu", " tỷ", " nghìn tỷ", " triệu tỷ")


def _doc_ba_so(so: int, day_du: bool) -> str:
	"""Đọc một nhóm 3 chữ số.

	`day_du` — nhóm này có nhóm lớn hơn đứng trước hay không. Nó quyết định
	"một trăm linh năm" (đầy đủ) khác "linh năm" (nhóm đầu tiên): 105 đọc là
	"một trăm linh năm", còn 1.105 đọc là "một nghìn một trăm linh năm" chứ
	không phải "một nghìn trăm linh năm".
	"""
	tram, chuc, donvi = so // 100, (so // 10) % 10, so % 10
	phan = []

	if tram > 0 or day_du:
		phan.append(f"{CHU_SO[tram]} trăm")

	if chuc == 0:
		# "linh" chỉ xuất hiện khi CÒN chữ số hàng đơn vị và có hàng trăm
		# đứng trước — 100 đọc "một trăm", không phải "một trăm linh không".
		if donvi > 0 and (tram > 0 or day_du):
			phan.append(f"linh {CHU_SO[donvi]}")
		elif donvi > 0:
			phan.append(CHU_SO[donvi])
	elif chuc == 1:
		phan.append("mười")
		if donvi == 1:
			phan.append("một")
		elif donvi == 5:
			phan.append("lăm")
		elif donvi > 0:
			phan.append(CHU_SO[donvi])
	else:
		phan.append(f"{CHU_SO[chuc]} mươi")
		if donvi == 1:
			# "hai mươi mốt", không phải "hai mươi một".
			phan.append("mốt")
		elif donvi == 4:
			phan.append("tư")
		elif donvi == 5:
			# "hai mươi lăm", không phải "hai mươi năm".
			phan.append("lăm")
		elif donvi > 0:
			phan.append(CHU_SO[donvi])

	return " ".join(phan)


def doc_so(so: int) -> str:
	"""Đọc một số nguyên không âm thành chữ tiếng Việt."""
	so = int(so)
	if so == 0:
		return "không"

	nhom = []
	while so > 0:
		nhom.append(so % 1000)
		so //= 1000

	phan = []
	for i in range(len(nhom) - 1, -1, -1):
		if nhom[i] == 0:
			# BỎ HẲN nhóm rỗng. Cách đọc "không trăm" của nhóm bị bỏ đã nằm
			# sẵn trong nhóm KẾ TIẾP nhờ `day_du=True` — 1.000.005 ra "một
			# triệu không trăm linh năm", đúng cách đọc chứng từ. Bản trước
			# chèn "không trăm" cho TỪNG nhóm rỗng nên thành "một triệu không
			# trăm nghìn không trăm linh năm".
			continue
		day_du = i < len(nhom) - 1
		phan.append(_doc_ba_so(nhom[i], day_du) + DON_VI[i])

	return " ".join(x for x in phan if x).strip()


def tien_bang_chu(so, don_vi: str = "đồng") -> str:
	"""Số tiền thành chữ, viết hoa chữ đầu, kết thúc bằng đơn vị và dấu chấm.

	VND không có phần lẻ trong thực tế chứng từ — làm tròn về số nguyên thay
	vì đọc "phẩy năm mươi xu", thứ không tồn tại trên phiếu kho.
	"""
	try:
		nguyen = int(round(float(so or 0)))
	except (TypeError, ValueError):
		return ""
	if nguyen < 0:
		return "Âm " + doc_so(-nguyen) + f" {don_vi}."
	chu = doc_so(nguyen)
	return chu[0].upper() + chu[1:] + f" {don_vi}."
