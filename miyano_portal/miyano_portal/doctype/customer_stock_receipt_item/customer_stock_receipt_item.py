from miyano_portal.kho.voucher_item import VoucherItemBase


class CustomerStockReceiptItem(VoucherItemBase):
	"""Dòng vật tư của `Customer Stock Receipt`.

	Toàn bộ logic ghi đè `has_permission()` — và lời giải thích đầy đủ về phạm
	vi THẬT SỰ của nó (chặn được gì, KHÔNG chặn được gì, vì sao hook
	has_permission cho doctype istable là decoy, và lỗ printview FINDING 8 đã
	được đóng ở tầng cấu hình quyền ra sao) — nằm ở
	`miyano_portal.kho.voucher_item.VoucherItemBase`. Hai bảng dòng chứng từ
	kho dùng CHUNG một bản, không phải hai bản chép tay giống nhau từng byte
	như trước (FINDING N4).
	"""
