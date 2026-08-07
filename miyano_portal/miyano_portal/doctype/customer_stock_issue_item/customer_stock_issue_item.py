from miyano_portal.kho.voucher_item import VoucherItemBase


class CustomerStockIssueItem(VoucherItemBase):
	"""Dòng vật tư của `Customer Stock Issue`.

	Cùng lớp cơ sở với `CustomerStockReceiptItem` — cùng lý do, cùng cơ chế,
	chỉ khác doctype cha. Xem `miyano_portal.kho.voucher_item.VoucherItemBase`
	để có toàn bộ giải thích (FINDING N4: trước đây hai file này chứa hai bản
	`has_permission()` giống nhau từng byte).
	"""
