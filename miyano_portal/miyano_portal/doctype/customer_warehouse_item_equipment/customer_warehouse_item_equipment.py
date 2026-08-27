from miyano_portal.kho.voucher_item import VoucherItemBase


class CustomerWarehouseItemEquipment(VoucherItemBase):
	"""Dòng "máy sử dụng được vật tư này" của `Customer Warehouse Item`.

	Toàn bộ logic `has_permission()` — và lời giải thích đầy đủ về phạm vi
	THẬT SỰ của nó (chặn được gì, KHÔNG chặn được gì, vì sao hook
	has_permission cho doctype istable là decoy) — nằm ở
	`miyano_portal.kho.voucher_item.VoucherItemBase`. Dùng CHUNG với
	`Customer Stock Receipt Item`/`Customer Stock Issue Item` (FINDING N4:
	không viết một bản has_permission thứ ba giống hệt hai bản kia), dù bản
	thân doctype này không phải một "chứng từ" — nó áp được vì
	`voucher_item_readable()` chỉ cần PARENT (`Customer Warehouse Item`) có
	field `kho`, và parent của nó có.
	"""
