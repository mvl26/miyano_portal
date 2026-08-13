"""Report desk "Tỷ trọng nguồn cung" (share-of-wallet) — US-E5.5 (UC-51).

Toàn bộ số học sống ở
`miyano_portal.kho.desk_reports.ty_trong_nguon_cung_rows()` — giá trị + SL
nhập theo nguồn (Miyano vs từng NCC khác) trong một kỳ, từ phiếu nhập ĐÃ GHI
SỔ, LOẠI TRỪ đảo (tính ở mức sổ kho, không phải mức chứng từ — xem docstring
hàm đó).

Quyền hạn: `ref_doctype=Customer Stock Receipt`, `roles=System Manager/
Sales Manager/Sales User` (xem setup/install_kho_desk_reports.py). Role
`Customer` KHÔNG có DocPerm nào trên doctype này — report liệt kê nguồn
nhập hàng (kể cả mua ngoài NCC khác) của MỌI khách hàng, VĐ-10: chỉ triển
khai cho khách đã ký điều khoản chia sẻ dữ liệu, quản lý bằng quy trình mở
kho, không chặn bằng code.
"""

import frappe

from miyano_portal.kho import desk_reports

COLUMNS = [
	{"label": "Khách hàng", "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
	{"label": "Nguồn", "fieldname": "nguon", "fieldtype": "Data", "width": 160},
	{"label": "SL nhập", "fieldname": "sl_nhap", "fieldtype": "Float", "precision": 2, "width": 110},
	{"label": "Giá trị nhập", "fieldname": "gia_tri_nhap", "fieldtype": "Currency", "width": 150},
	{"label": "Tỷ trọng (%)", "fieldname": "ty_trong_pct", "fieldtype": "Percent", "width": 110},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = desk_reports.ty_trong_nguon_cung_rows(
		customer=filters.get("customer") or None,
		tu_ngay=filters.get("tu_ngay") or None,
		den_ngay=filters.get("den_ngay") or None,
	)
	return COLUMNS, data
