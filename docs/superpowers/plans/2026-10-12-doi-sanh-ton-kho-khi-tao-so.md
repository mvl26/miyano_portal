# Đối sánh tồn kho trên Sales Order — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trên form Sales Order ở Desk, nhân viên Miyano thấy bảng đối sánh tồn kho từng dòng hàng và tạo được một Material Request nháp cho đúng phần thiếu.

**Architecture:** Một module mới `miyano_portal/doi_sanh_ton.py` gồm ba lớp: hàm thuần (nhận số, trả số), hàm đọc CSDL (`Bin`, `Batch`, `Sales Order Item`, `Material Request Item`), và hai endpoint whitelist có chốt vai nội bộ. `public/js/sales_order.js` gọi endpoint đọc để dựng một khối trên dashboard của form và thêm nút tạo MR. Không thêm doctype, custom field hay hook.

**Tech Stack:** Frappe 15.113 / ERPNext 15.83 (Python 3.12), MariaDB, JavaScript Desk (không build). Test: `FrappeTestCase` chạy qua `bench run-tests`.

**Spec:** `docs/superpowers/specs/2026-10-12-doi-sanh-ton-kho-khi-tao-so-design.md` — đọc trước khi làm bất kỳ task nào.

## Global Constraints

- Nhánh: `feat/doi-sanh-ton-kho-so`, tách từ `main`, nằm ở worktree `/home/hoangvietyeuem/worktrees/miyano_portal-doi-sanh-ton` (gọi là **WT**). Mọi sửa file và mọi lệnh `git` của kế hoạch này chạy trong WT.
- Thư mục app của bench, `/home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal` (gọi là **APP**), đang ở nhánh `feat/thoi-gian-giao-hang-va-gia-bang-gia` và có một phiên khác đang commit việc "giá theo Price List". TUYỆT ĐỐI không `git switch` / `checkout` / `stash` / `add` / `commit` trong APP, không sửa file có sẵn nào trong APP.
- Bench chỉ nạp code từ APP. Để test chạy được code của WT, tạo MỘT LẦN hai symlink trong APP và giấu chúng khỏi `git status` của APP (Task 1, Step 0). Không tạo symlink cho `sales_order.js`.
- Test chạy trên nền code của APP (nhánh Price List đang dở) cộng hai file của kế hoạch này. Lỗi phát sinh ở bước tạo Sales Order trong fixture mà không liên quan `doi_sanh_ton` thì dừng lại báo, không tự sửa code của việc khác.
- Chạy test: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`.
- `erptest.local` cũng là site chủ dự án đang mở qua `192.168.61.129`. Test chỉ tạo dữ liệu mang tiền tố `_TEST DST-`; không xoá dữ liệu nào khác.
- File mới dùng **tab** để thụt lề. `public/js/sales_order.js` dùng tab.
- Tên hàm, hằng số, thông báo: tiếng Việt, tên không dấu. Commit message không dấu, tiền tố `feat(desk):` / `test(desk):` / `docs:`; kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Không bật Stock Reservation, không đổi Stock Settings (spec Q1).
- Material Request tạo ra luôn ở `docstatus = 0`; không gọi `submit()` ở bất kỳ đâu (spec Q2).
- Không thêm hook `validate` / `before_submit` nào lên Sales Order (spec §8).
- Tài khoản cổng (`permissions._is_restricted_user`, tức `user_type = "Website User"`) bị từ chối ở cả hai endpoint TRƯỚC khi xét vai.
- Vai nội bộ, nguyên văn: `System Manager`, `Sales Manager`, `Sales User`, `Stock Manager`, `Stock User`, `Purchase Manager`, `Purchase User`.
- Mọi số lượng trong bảng và trong MR theo **đơn vị tồn kho**, làm tròn 3 chữ số thập phân.
- "Không tra được" trả `None` (giao diện hiện `—`), không bao giờ trả `0`.

## Review Focus

1. **Bấm "Tạo MR" hai lần liên tiếp (bấm đúp, hai người cùng mở đơn).** Mong đợi: chỉ một MR; lần hai báo "không còn phần thiếu". Test ở Task 4.
2. **Tồn kho đổi giữa lúc bảng hiện và lúc bấm tạo MR.** Mong đợi: MR theo số thiếu tính lại ở máy chủ lúc bấm. Test ở Task 4.
3. **Mặt hàng chưa từng nhập kho (không có dòng `Bin`).** Mong đợi: tồn hiện tại `0` thật và báo thiếu toàn bộ, không phải `—`. Test ở Task 2.
4. **Lô không khai hạn dùng trên mặt hàng quản lý theo lô.** Mong đợi: vẫn tính là dùng được. Test ở Task 2.
5. **Phép tính bảng ném lỗi (dữ liệu bẩn, truy vấn hỏng).** Mong đợi: endpoint trả `{"loi": ...}`, form Sales Order vẫn mở được; nhưng lỗi QUYỀN vẫn phải ném ra. Test ở Task 3.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| Create `miyano_portal/doi_sanh_ton.py` | Hàm thuần tính bảng; hàm đọc tồn / giữ hàng / MR; `bang_cho_don`; hai endpoint `doi_sanh_ton`, `tao_mr_phan_thieu`. |
| Create `miyano_portal/tests/test_doi_sanh_ton.py` | Toàn bộ kiểm thử của kế hoạch này. |
| Modify `miyano_portal/public/js/sales_order.js` | Khối "Đối sánh tồn kho" trên dashboard của form; nút "Tạo MR cho phần thiếu". |

Hình dạng một dòng của bảng (dùng xuyên suốt Task 2–5):

```python
{
	"so_detail": str | None,   # tên dòng Sales Order Item; None với dòng đặt ngoài
	"idx": int,
	"item_code": str | None,
	"item_name": str,
	"kho": str | None,
	"dvt": str | None,         # đơn vị tồn kho
	"ly_do": str | None,       # khác None = không tra được, các cột tồn là None
	"sl_yeu_cau": float | None,
	"ton_hien_tai": float | None,
	"ton_kha_dung": float | None,
	"sl_thieu": float | None,
	"mr_da_phu": float | None,
	"can_mua": float | None,
	"de_xuat": str | None,     # "du" | "can_mua" | "mr_mot_phan" | "da_co_mr"
	"mr": list[str],           # tên các Material Request đang phủ dòng này
	"don_nhap_khac": dict | None,  # {"sl": float, "so_don": int}
}
```

---

### Task 1: Hàm thuần

**Files:**
- Create: `miyano_portal/doi_sanh_ton.py`
- Create: `miyano_portal/tests/test_doi_sanh_ton.py`

**Interfaces:**
- Produces:
  - `ROLE_NOI_BO: tuple[str, ...]`
  - `LY_DO_DAT_NGOAI`, `LY_DO_KHONG_TON`, `LY_DO_KHONG_KHO`, `LY_DO_GIAO_THANG`, `LY_DO_BO: str`
  - `DX_DU = "du"`, `DX_CAN_MUA = "can_mua"`, `DX_MOT_PHAN = "mr_mot_phan"`, `DX_DA_CO_MR = "da_co_mr"`
  - `sl_con_giao(stock_qty, qty, delivered_qty) -> float`
  - `ton_kha_dung(ton_hien_tai, ton_het_han, giu_don_khac) -> float` (`ton_het_han` là tổng tồn của các lô ĐÃ hết hạn; `0` với mặt hàng không theo lô)
  - `chia_ton(yeu_cau: list[tuple[tuple, float]], kha_dung: dict[tuple, float]) -> list[tuple[float, float]]` — mỗi phần tử là `(tồn có thể sử dụng dòng này thấy, số thiếu)`
  - `de_xuat(sl_thieu, mr_da_phu) -> dict` với khoá `ma`, `mr_da_phu`, `can_mua`
  - `ly_do_khong_tra(row, thong_tin_item, la_bo: bool) -> str | None`

- [ ] **Step 0: Nối hai file của WT vào APP**

```bash
WT=/home/hoangvietyeuem/worktrees/miyano_portal-doi-sanh-ton
APP=/home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
touch $WT/miyano_portal/doi_sanh_ton.py $WT/miyano_portal/tests/test_doi_sanh_ton.py
ln -s $WT/miyano_portal/doi_sanh_ton.py $APP/miyano_portal/doi_sanh_ton.py
ln -s $WT/miyano_portal/tests/test_doi_sanh_ton.py $APP/miyano_portal/tests/test_doi_sanh_ton.py
printf '%s\n' miyano_portal/doi_sanh_ton.py miyano_portal/tests/test_doi_sanh_ton.py >> "$(git -C $APP rev-parse --git-common-dir)/info/exclude"
git -C $APP status --short | grep doi_sanh_ton || echo "APP sach"
```
Expected: `APP sach` (hai symlink không hiện trong `git status` của APP).

`info/exclude` nằm ở thư mục git dùng chung nên cũng che hai đường dẫn này trong WT: ở Task 1 Step 5 phải `git add -f` cho hai file đó. Từ commit đầu tiên trở đi chúng đã được theo dõi nên `git add` thường là đủ.

- [ ] **Step 1: Viết test (chưa có module nên sẽ fail)**

Ghi vào `miyano_portal/tests/test_doi_sanh_ton.py` (trong WT; file rỗng đã có từ Step 0):

```python
"""Đối sánh tồn kho trên Sales Order và Material Request cho phần thiếu.

Spec: docs/superpowers/specs/2026-10-12-doi-sanh-ton-kho-khi-tao-so-design.md

BA ĐIỀU ĐỊNH HÌNH BỘ TEST NÀY:

1. **Đây là tồn của MIYANO (`Bin`), không phải tồn của bệnh viện** (CR-04,
   `kho/can_cu_duyet.py`). Hai nguồn, hai người đọc.

2. **Không tra được thì trả `None`, KHÔNG trả 0.** "Tồn 0" nghĩa là hết hàng.

3. **Tài khoản cổng khách hàng ĐỌC ĐƯỢC đơn của chính họ**, nên chốt quyền
   phải là danh sách vai nội bộ — kiểm "đọc được Sales Order" là để lọt đúng
   người cần chặn.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import doi_sanh_ton as dst


class TestSlConGiao(FrappeTestCase):
	def test_chua_giao_gi_thi_bang_stock_qty(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=20, qty=2, delivered_qty=0), 20)

	def test_giao_mot_phan_chi_con_phan_chua_giao(self):
		"""2 Thùng = 20 Hộp, đã giao 0,5 Thùng -> còn 15 Hộp."""
		self.assertEqual(dst.sl_con_giao(stock_qty=20, qty=2, delivered_qty=0.5), 15)

	def test_giao_thua_khong_ra_so_am(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=10, qty=10, delivered_qty=12), 0)

	def test_qty_bang_0_khong_chia(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=0, qty=0, delivered_qty=0), 0)


class TestTonKhaDung(FrappeTestCase):
	def test_khong_co_lo_het_han_thi_chi_tru_phan_da_giu(self):
		self.assertEqual(dst.ton_kha_dung(100, 0, 30), 70)

	def test_tru_lo_het_han_roi_tru_phan_da_giu(self):
		"""Tồn 100, trong đó 40 đã hết hạn; đơn khác giữ 10."""
		self.assertEqual(dst.ton_kha_dung(100, 40, 10), 50)

	def test_moi_lo_deu_het_han_thi_ve_0(self):
		self.assertEqual(dst.ton_kha_dung(100, 100, 0), 0)

	def test_don_khac_giu_nhieu_hon_ton_thi_ve_0_khong_am(self):
		self.assertEqual(dst.ton_kha_dung(4, 0, 10), 0)


class TestChiaTon(FrappeTestCase):
	def test_hai_dong_cung_mat_hang_chia_nhau_mot_luong_ton(self):
		"""Tồn 10, hai dòng mỗi dòng 6: dòng sau chỉ thấy 4 còn lại.

		Không có bài này thì hai dòng cùng báo "đủ" trên cùng 10 cái.
		"""
		k = ("A", "Kho 1")
		kq = dst.chia_ton([(k, 6), (k, 6)], {k: 10})
		self.assertEqual(kq, [(10, 0), (4, 2)])

	def test_khac_kho_thi_khong_chia_nhau(self):
		k1, k2 = ("A", "Kho 1"), ("A", "Kho 2")
		kq = dst.chia_ton([(k1, 6), (k2, 6)], {k1: 10, k2: 1})
		self.assertEqual(kq, [(10, 0), (1, 5)])

	def test_khong_sua_dict_dau_vao(self):
		k = ("A", "Kho 1")
		nguon = {k: 10}
		dst.chia_ton([(k, 6)], nguon)
		self.assertEqual(nguon, {k: 10})


class TestDeXuat(FrappeTestCase):
	def test_du_hang(self):
		self.assertEqual(
			dst.de_xuat(0, 0), {"ma": dst.DX_DU, "mr_da_phu": 0, "can_mua": 0}
		)

	def test_thieu_chua_co_mr(self):
		self.assertEqual(
			dst.de_xuat(6, 0), {"ma": dst.DX_CAN_MUA, "mr_da_phu": 0, "can_mua": 6}
		)

	def test_mr_phu_mot_phan(self):
		self.assertEqual(
			dst.de_xuat(6, 4), {"ma": dst.DX_MOT_PHAN, "mr_da_phu": 4, "can_mua": 2}
		)

	def test_mr_phu_het(self):
		self.assertEqual(
			dst.de_xuat(6, 6), {"ma": dst.DX_DA_CO_MR, "mr_da_phu": 6, "can_mua": 0}
		)

	def test_mr_nhieu_hon_thieu_thi_chi_tinh_bang_phan_thieu(self):
		"""MR 10 nhưng nay chỉ còn thiếu 6: không hiện "đã có MR 10" cho 6 cái."""
		self.assertEqual(
			dst.de_xuat(6, 10), {"ma": dst.DX_DA_CO_MR, "mr_da_phu": 6, "can_mua": 0}
		)

	def test_du_hang_ma_van_con_mr_thi_van_la_du(self):
		self.assertEqual(dst.de_xuat(0, 5)["ma"], dst.DX_DU)


class TestLyDoKhongTra(FrappeTestCase):
	"""Bốn ca của spec §5.5 (ca đặt ngoài nằm ở `bang_cho_don`)."""

	TON = frappe._dict(is_stock_item=1, has_batch_no=0)

	def _dong(self, **kw):
		d = frappe._dict(item_code="A", warehouse="Kho 1", delivered_by_supplier=0)
		d.update(kw)
		return d

	def test_dong_binh_thuong_tra_duoc(self):
		self.assertIsNone(dst.ly_do_khong_tra(self._dong(), self.TON, False))

	def test_hang_khong_quan_ly_ton(self):
		khong_ton = frappe._dict(is_stock_item=0, has_batch_no=0)
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), khong_ton, False), dst.LY_DO_KHONG_TON
		)

	def test_item_khong_con_ton_tai(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), None, False), dst.LY_DO_KHONG_TON
		)

	def test_bo_san_pham(self):
		"""Mã gộp của Product Bundle luôn là hàng KHÔNG quản lý tồn — lý do
		phải là "bộ sản phẩm", không bị ca "không quản lý tồn" che mất."""
		khong_ton = frappe._dict(is_stock_item=0, has_batch_no=0)
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), khong_ton, True), dst.LY_DO_BO
		)

	def test_giao_thang(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(delivered_by_supplier=1), self.TON, False),
			dst.LY_DO_GIAO_THANG,
		)

	def test_khong_co_kho(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(warehouse=None), self.TON, False),
			dst.LY_DO_KHONG_KHO,
		)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: FAIL — `AttributeError: module 'miyano_portal.doi_sanh_ton' has no attribute 'sl_con_giao'`

- [ ] **Step 3: Viết phần hàm thuần**

Ghi vào `miyano_portal/doi_sanh_ton.py` (trong WT; file rỗng đã có từ Step 0):

```python
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: `Ran 23 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
cd /home/hoangvietyeuem/worktrees/miyano_portal-doi-sanh-ton
git add -f miyano_portal/doi_sanh_ton.py miyano_portal/tests/test_doi_sanh_ton.py
git commit -m "feat(desk): doi sanh ton kho tren Sales Order - cac ham tinh thuan

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Đọc CSDL và dựng bảng cho một đơn

**Files:**
- Modify: `miyano_portal/doi_sanh_ton.py` (thêm vào cuối file)
- Modify: `miyano_portal/tests/test_doi_sanh_ton.py` (thêm vào cuối file)

**Interfaces:**
- Consumes: mọi hàm thuần và hằng số của Task 1.
- Produces:
  - `_ton_het_han(item_code: str, warehouse: str) -> float`
  - `_giu_cho_don_khac(item_code: str, warehouse: str, tru_don: str) -> float`
  - `_mr_theo_dong(so_details: list[str]) -> dict[str, dict]` — `{so_detail: {"sl": float, "mr": list[str]}}`
  - `bang_cho_don(so) -> dict` — `{"dong": list[dict], "tong": {"so_dong": int, "so_thieu": int}, "co_the_tao_mr": bool}`; mỗi phần tử của `dong` có đúng các khoá ở mục File Structure.

- [ ] **Step 1: Thêm test tích hợp**

Thêm vào ĐẦU `miyano_portal/tests/test_doi_sanh_ton.py`, ngay dưới dòng `import frappe`:

```python
import unittest.mock
```

Rồi ngay dưới dòng `from miyano_portal import doi_sanh_ton as dst`:

```python
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry
from erpnext.stock.stock_balance import get_reserved_qty

from miyano_portal.setup.seed_kho_demo import seed_kho_demo

COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"
KHACH = "Bệnh viện Bạch Mai"


class _CoSo(FrappeTestCase):
	"""Dựng dữ liệu chung. Mỗi test tự tạo MẶT HÀNG MỚI (`_TEST DST-…`):
	`erptest.local` có sẵn tồn và đơn cũ, dùng lại mặt hàng demo thì số tồn
	và số "đã giữ cho đơn khác" không còn là số test tự đặt ra."""

	def setUp(self):
		frappe.set_user("Administrator")
		seed_kho_demo()

	def tearDown(self):
		frappe.set_user("Administrator")

	def _item(self, theo_lo=False, quan_ly_ton=True, uoms=None):
		ma = "_TEST DST-" + frappe.generate_hash(length=8)
		frappe.get_doc({
			"doctype": "Item", "item_code": ma,
			"item_name": "Vật tư test đối sánh tồn",
			"item_group": frappe.get_all(
				"Item Group", filters={"is_group": 0}, pluck="name"
			)[0],
			"stock_uom": "Hộp", "is_stock_item": int(quan_ly_ton),
			"has_batch_no": int(theo_lo), "create_new_batch": 0,
			"uoms": uoms or [],
		}).insert(ignore_permissions=True)
		return ma

	def _nap(self, item, qty, lo=None):
		make_stock_entry(
			item_code=item, qty=qty, to_warehouse=KHO_MYN, rate=1000,
			batch_no=lo, company=COMPANY, purpose="Material Receipt",
		)

	def _lo(self, item, han):
		ten = "_TEST DST-LO-" + frappe.generate_hash(length=8)
		frappe.get_doc({
			"doctype": "Batch", "batch_id": ten, "item": item, "expiry_date": han,
		}).insert(ignore_permissions=True)
		return ten

	def _don(self, dong, submit=True):
		"""`dong`: `[(item_code, qty), ...]` hoặc dict dòng đầy đủ."""
		ngay = frappe.utils.add_days(frappe.utils.today(), 2)
		so = frappe.new_doc("Sales Order")
		so.customer = KHACH
		so.company = COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = ngay
		for d in dong:
			if not isinstance(d, dict):
				d = {"item_code": d[0], "qty": d[1]}
			so.append("items", {
				"rate": 1000, "warehouse": KHO_MYN, "delivery_date": ngay, **d,
			})
		so.insert(ignore_permissions=True)
		if submit:
			so.submit()
		return so

	def _bang(self, so):
		return dst.bang_cho_don(frappe.get_doc("Sales Order", so.name))

	def _dong_dau(self, so):
		return self._bang(so)["dong"][0]
```

Thêm vào CUỐI file:

```python
class TestBangChoDon(_CoSo):
	def test_du_hang(self):
		item = self._item()
		self._nap(item, 10)
		d = self._dong_dau(self._don([(item, 4)], submit=False))
		self.assertEqual(d["sl_yeu_cau"], 4)
		self.assertEqual(d["ton_hien_tai"], 10)
		self.assertEqual(d["ton_kha_dung"], 10)
		self.assertEqual(d["sl_thieu"], 0)
		self.assertEqual(d["de_xuat"], dst.DX_DU)
		self.assertEqual(d["dvt"], "Hộp")
		self.assertIsNone(d["ly_do"])

	def test_thieu_mot_phan(self):
		item = self._item()
		self._nap(item, 4)
		d = self._dong_dau(self._don([(item, 10)], submit=False))
		self.assertEqual(d["sl_thieu"], 6)
		self.assertEqual(d["can_mua"], 6)
		self.assertEqual(d["de_xuat"], dst.DX_CAN_MUA)

	def test_mat_hang_chua_tung_nhap_kho_la_TON_0_khong_phai_gach_ngang(self):
		"""Không có dòng `Bin` nào = thật sự không có hàng, tra được hẳn hoi."""
		item = self._item()
		d = self._dong_dau(self._don([(item, 3)], submit=False))
		self.assertIsNone(d["ly_do"])
		self.assertEqual(d["ton_hien_tai"], 0)
		self.assertEqual(d["sl_thieu"], 3)

	def test_don_dang_xem_da_submit_KHONG_tu_tru_chinh_minh(self):
		"""`Bin.reserved_qty` gồm cả đơn đang xem. Trừ nhầm thì đơn tự tranh
		hàng với chính nó và luôn báo thiếu."""
		item = self._item()
		self._nap(item, 10)
		d = self._dong_dau(self._don([(item, 10)]))
		self.assertEqual(d["ton_kha_dung"], 10)
		self.assertEqual(d["sl_thieu"], 0)

	def test_don_khac_da_submit_lam_giam_ton_kha_dung(self):
		item = self._item()
		self._nap(item, 10)
		self._don([(item, 7)])
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_hien_tai"], 10)
		self.assertEqual(d["ton_kha_dung"], 3)
		self.assertEqual(d["sl_thieu"], 2)

	def test_don_nhap_khac_KHONG_tru_nhung_co_ghi_chu(self):
		item = self._item()
		self._nap(item, 10)
		self._don([(item, 7)], submit=False)
		self._don([(item, 1)], submit=False)
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_kha_dung"], 10)
		self.assertEqual(d["don_nhap_khac"], {"sl": 8, "so_don": 2})

	def test_khong_co_don_nhap_khac_thi_ghi_chu_la_None(self):
		item = self._item()
		self._nap(item, 10)
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertIsNone(d["don_nhap_khac"])

	def test_giu_cho_don_khac_khop_dung_ham_goc_cua_ERPNext(self):
		"""Ghim bản sao truy vấn vào `stock_balance.get_reserved_qty`: không
		loại đơn nào thì hai hàm phải ra cùng một số."""
		item = self._item()
		self._nap(item, 20)
		self._don([(item, 7)])
		self._don([(item, 2)])
		self.assertEqual(
			dst._giu_cho_don_khac(item, KHO_MYN, tru_don=""),
			get_reserved_qty(item, KHO_MYN),
		)
		self.assertEqual(dst._giu_cho_don_khac(item, KHO_MYN, tru_don=""), 9)

	def test_hai_dong_cung_mat_hang_chia_nhau_ton(self):
		item = self._item()
		self._nap(item, 10)
		dong = self._bang(self._don([(item, 6), (item, 6)], submit=False))["dong"]
		self.assertEqual([d["ton_kha_dung"] for d in dong], [10, 4])
		self.assertEqual([d["sl_thieu"] for d in dong], [0, 2])

	def test_don_vi_ban_khac_don_vi_ton_kho(self):
		"""2 Thùng × 10 = 20 Hộp; tồn 15 Hộp -> thiếu 5 Hộp."""
		item = self._item(uoms=[{"uom": "Thùng", "conversion_factor": 10}])
		self._nap(item, 15)
		so = self._don(
			[{"item_code": item, "qty": 2, "uom": "Thùng", "conversion_factor": 10}],
			submit=False,
		)
		d = self._dong_dau(so)
		self.assertEqual(d["sl_yeu_cau"], 20)
		self.assertEqual(d["sl_thieu"], 5)
		self.assertEqual(d["dvt"], "Hộp")

	def test_don_da_giao_mot_phan_chi_tinh_phan_con_lai(self):
		item = self._item()
		self._nap(item, 10)
		so = self._don([(item, 10)])
		dn = make_delivery_note(so.name)
		dn.posting_date = frappe.utils.today()
		dn.set_posting_time = 1
		for r in dn.items:
			r.qty = 4
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		dn.submit()
		d = self._dong_dau(so)
		self.assertEqual(d["sl_yeu_cau"], 6)
		self.assertEqual(d["ton_hien_tai"], 6)
		self.assertEqual(d["sl_thieu"], 0)

	def test_hang_khong_quan_ly_ton_hien_gach_ngang(self):
		item = self._item(quan_ly_ton=False)
		d = self._dong_dau(self._don([(item, 3)], submit=False))
		self.assertEqual(d["ly_do"], dst.LY_DO_KHONG_TON)
		for cot in ("ton_hien_tai", "ton_kha_dung", "sl_thieu", "can_mua", "de_xuat"):
			self.assertIsNone(d[cot], cot)

	def test_dong_dat_ngoai_chua_khop_ma_hien_gach_ngang(self):
		item = self._item()
		self._nap(item, 10)
		so = self._don([(item, 1)], submit=False)
		so.append("custom_dat_ngoai", {
			"ten_hang": "Kim sinh thiết ngoài danh mục", "so_luong": 3, "dvt": "Cái",
		})
		bang = dst.bang_cho_don(so)
		dn = bang["dong"][-1]
		self.assertEqual(dn["ly_do"], dst.LY_DO_DAT_NGOAI)
		self.assertEqual(dn["item_name"], "Kim sinh thiết ngoài danh mục")
		self.assertEqual(dn["sl_yeu_cau"], 3)
		self.assertIsNone(dn["ton_hien_tai"])
		self.assertIsNone(dn["so_detail"])
		# Dòng không tra được không vào số tổng kết.
		self.assertEqual(bang["tong"], {"so_dong": 1, "so_thieu": 0})

	def test_tong_ket_dem_dung_dong_thieu(self):
		a, b = self._item(), self._item()
		self._nap(a, 10)
		bang = self._bang(self._don([(a, 4), (b, 2)], submit=False))
		self.assertEqual(bang["tong"], {"so_dong": 2, "so_thieu": 1})

	def test_don_nhap_co_thieu_van_KHONG_tao_duoc_mr(self):
		item = self._item()
		bang = self._bang(self._don([(item, 2)], submit=False))
		self.assertFalse(bang["co_the_tao_mr"])

	def test_don_da_submit_co_thieu_thi_tao_duoc_mr(self):
		item = self._item()
		bang = self._bang(self._don([(item, 2)]))
		self.assertTrue(bang["co_the_tao_mr"])


class TestLoHetHan(_CoSo):
	def _hom_qua(self):
		return frappe.utils.add_days(frappe.utils.today(), -1)

	def test_lo_het_han_bi_loai_khoi_ton_kha_dung(self):
		item = self._item(theo_lo=True)
		con_han = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		sap_het = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		self._nap(item, 6, lo=con_han)
		self._nap(item, 4, lo=sap_het)
		# Nhập khi lô còn hạn rồi mới đẩy hạn về quá khứ: ERPNext không cho
		# nhập kho vào một lô đã hết hạn sẵn.
		frappe.db.set_value("Batch", sap_het, "expiry_date", self._hom_qua())

		d = self._dong_dau(self._don([(item, 8)], submit=False))
		self.assertEqual(d["ton_hien_tai"], 10)
		self.assertEqual(d["ton_kha_dung"], 6)
		self.assertEqual(d["sl_thieu"], 2)

	def test_lo_khong_khai_han_van_dung_duoc(self):
		item = self._item(theo_lo=True)
		khong_han = self._lo(item, None)
		self._nap(item, 5, lo=khong_han)
		d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_kha_dung"], 5)
		self.assertEqual(d["sl_thieu"], 0)

	def test_moi_lo_deu_het_han_thi_ton_kha_dung_0(self):
		item = self._item(theo_lo=True)
		lo = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		self._nap(item, 5, lo=lo)
		frappe.db.set_value("Batch", lo, "expiry_date", self._hom_qua())
		d = self._dong_dau(self._don([(item, 2)], submit=False))
		self.assertEqual(d["ton_hien_tai"], 5)
		self.assertEqual(d["ton_kha_dung"], 0)
		self.assertEqual(d["sl_thieu"], 2)

	def test_ton_khong_co_so_lo_di_kem_VAN_tinh_la_dung_duoc(self):
		"""Mặt hàng theo lô mà tồn `Bin` không có sổ lô (dữ liệu nhập thiếu
		lô — có thật trên site thử). Không biết lô nào hết hạn thì không trừ
		gì: báo "tồn 0" ở đây là bịa ra một ca hết hàng."""
		item = self._item(theo_lo=True)
		lo = self._lo(item, frappe.utils.add_days(frappe.utils.today(), 90))
		self._nap(item, 5, lo=lo)
		with unittest.mock.patch(
			"erpnext.stock.doctype.batch.batch.get_batch_qty", return_value=[]
		):
			d = self._dong_dau(self._don([(item, 5)], submit=False))
		self.assertEqual(d["ton_kha_dung"], 5)
		self.assertEqual(d["sl_thieu"], 0)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: FAIL — `AttributeError: module 'miyano_portal.doi_sanh_ton' has no attribute 'bang_cho_don'` (23 test của Task 1 vẫn pass).

- [ ] **Step 3: Viết phần đọc CSDL và `bang_cho_don`**

Thêm vào CUỐI `miyano_portal/doi_sanh_ton.py`:

```python
# ------------------------------------------------------------- đọc CSDL
def _ton_hien_tai(item_code: str, warehouse: str) -> float:
	"""`Bin.actual_qty`. Không có dòng `Bin` = chưa từng có hàng = 0 THẬT."""
	return flt(
		frappe.db.get_value(
			"Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"
		),
		DO_CHINH_XAC,
	)


def _ton_het_han(item_code: str, warehouse: str) -> float:
	"""Tổng tồn của các lô ĐÃ hết hạn tại một kho.

	= (mọi lô, `for_stock_levels=True`) − (lô còn hạn và lô không khai hạn).
	Hỏi đúng hàm ERPNext dùng khi tự chọn lô để xuất, để "hết hạn" ở đây và
	"không xuất được" ở phiếu giao là cùng một định nghĩa.

	Tính phần HẾT HẠN rồi trừ, KHÔNG lấy thẳng "tổng lô còn hạn" làm tồn dùng
	được: đo trên site thử 12/10/2026 có mặt hàng theo lô mà tồn `Bin` không
	có sổ lô đi kèm (1/60). Lấy tổng lô còn hạn thì mặt hàng đó ra 0 và báo
	thiếu sai; cách này chỉ trừ thứ biết chắc là hết hạn.
	"""
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	def tong(**kw):
		lo = get_batch_qty(item_code=item_code, warehouse=warehouse, **kw) or []
		return sum(flt(b.get("qty")) for b in lo)

	return flt(max(tong(for_stock_levels=True) - tong(), 0), DO_CHINH_XAC)


def _giu_cho_don_khac(item_code: str, warehouse: str, tru_don: str) -> float:
	"""Phần còn phải giao của các Sales Order KHÁC đã Submit.

	Là BẢN SAO truy vấn của `erpnext.stock.stock_balance.get_reserved_qty`
	(nguồn của `Bin.reserved_qty`), thêm đúng một điều kiện `parent != tru_don`
	ở mỗi nhánh. Không lấy `Bin.reserved_qty` rồi tự trừ phần của đơn đang
	xem: phép trừ viết tay phải khớp từng nhánh (hàng trả lại, Product Bundle)
	mới không lệch. Bài test `…khop_dung_ham_goc…` ghim hai truy vấn vào nhau.
	"""
	khong_giu_khi_tra = cint(
		frappe.db.get_single_value(
			"Selling Settings", "dont_reserve_sales_order_qty_on_sales_return"
		)
	)
	kq = frappe.db.sql(
		f"""
		select
			sum(dnpi_qty * ((so_item_qty - so_item_delivered_qty
				- if({khong_giu_khi_tra}, so_item_returned_qty, 0)) / so_item_qty))
		from
			(
				(select
					dnpi.qty as dnpi_qty,
					(
						select qty from `tabSales Order Item`
						where name = dnpi.parent_detail_docname
						and (delivered_by_supplier is null or delivered_by_supplier = 0)
					) as so_item_qty,
					(
						select delivered_qty from `tabSales Order Item`
						where name = dnpi.parent_detail_docname
						and delivered_by_supplier = 0
					) as so_item_delivered_qty,
					(
						select returned_qty from `tabSales Order Item`
						where name = dnpi.parent_detail_docname
						and delivered_by_supplier = 0
					) as so_item_returned_qty,
					dnpi.parent, dnpi.name
				from `tabPacked Item` dnpi
				where dnpi.item_code = %(item)s and dnpi.warehouse = %(kho)s
					and dnpi.parenttype = 'Sales Order'
					and dnpi.item_code != dnpi.parent_item
					and dnpi.parent != %(tru)s
					and exists (select 1 from `tabSales Order` so
						where so.name = dnpi.parent and so.docstatus = 1
						and so.status not in ('On Hold', 'Closed')))
			union
				(select
					so_item.stock_qty as dnpi_qty,
					so_item.qty as so_item_qty,
					so_item.delivered_qty as so_item_delivered_qty,
					so_item.returned_qty as so_item_returned_qty,
					so_item.parent, so_item.name
				from `tabSales Order Item` so_item
				where so_item.item_code = %(item)s and so_item.warehouse = %(kho)s
					and (so_item.delivered_by_supplier is null
						or so_item.delivered_by_supplier = 0)
					and so_item.parent != %(tru)s
					and exists (select 1 from `tabSales Order` so
						where so.name = so_item.parent and so.docstatus = 1
						and so.status not in ('On Hold', 'Closed')))
			) tab
		where so_item_qty >= so_item_delivered_qty
		""",
		{"item": item_code, "kho": warehouse, "tru": tru_don or ""},
	)
	return flt(kq[0][0] if kq else 0, DO_CHINH_XAC)


def _don_nhap_khac(item_code: str, warehouse: str, tru_don: str):
	"""Các đơn NHÁP khác cùng mặt hàng, cùng kho — chỉ để ghi chú (spec §5.3)."""
	sl, so_don = frappe.db.sql(
		"""
		select coalesce(sum(i.stock_qty), 0), count(distinct i.parent)
		from `tabSales Order Item` i
		join `tabSales Order` s on s.name = i.parent
		where s.docstatus = 0 and i.item_code = %(item)s
			and i.warehouse = %(kho)s and i.parent != %(tru)s
		""",
		{"item": item_code, "kho": warehouse, "tru": tru_don or ""},
	)[0]
	if not so_don:
		return None
	return {"sl": flt(sl, DO_CHINH_XAC), "so_don": cint(so_don)}


def _mr_theo_dong(so_details: list) -> dict:
	"""Phần Material Request CHƯA NHẬN VỀ KHO, gom theo dòng đơn.

	`stock_qty − received_qty`, không phải `stock_qty`: hàng đã nhận thì đã
	nằm trong tồn hiện tại, đếm cả số MR gốc là đếm hai lần. Tính cả MR nháp
	lẫn MR đã Submit; bỏ MR đã huỷ và MR Stopped.
	"""
	so_details = [n for n in so_details if n]
	if not so_details:
		return {}
	rows = frappe.db.sql(
		"""
		select mri.sales_order_item, mri.parent,
			greatest(mri.stock_qty - mri.received_qty, 0) as con
		from `tabMaterial Request Item` mri
		join `tabMaterial Request` mr on mr.name = mri.parent
		where mri.sales_order_item in %(ds)s
			and mr.material_request_type = 'Purchase'
			and mr.docstatus in (0, 1)
			and mr.status not in ('Stopped', 'Cancelled')
		order by mr.creation
		""",
		{"ds": tuple(so_details)},
		as_dict=True,
	)
	kq = {}
	for r in rows:
		if flt(r.con) <= 0:
			continue
		d = kq.setdefault(r.sales_order_item, {"sl": 0.0, "mr": []})
		d["sl"] = flt(d["sl"] + flt(r.con), DO_CHINH_XAC)
		if r.parent not in d["mr"]:
			d["mr"].append(r.parent)
	return kq


# ------------------------------------------------------------ dựng bảng
def _dong_trong(**kw) -> dict:
	d = {
		"so_detail": None, "idx": 0, "item_code": None, "item_name": "",
		"kho": None, "dvt": None, "ly_do": None, "sl_yeu_cau": None,
		"ton_hien_tai": None, "ton_kha_dung": None, "sl_thieu": None,
		"mr_da_phu": None, "can_mua": None, "de_xuat": None, "mr": [],
		"don_nhap_khac": None,
	}
	d.update(kw)
	return d


def bang_cho_don(so) -> dict:
	"""Bảng đối sánh tồn kho cho một Sales Order (spec §5).

	`so` là document Sales Order (đã lưu hay đang dựng trong bộ nhớ đều được).
	Chỉ ĐỌC; không ghi gì vào đơn hay vào CSDL.
	"""
	dong_don = list(so.get("items") or [])
	ma_hang = sorted({r.item_code for r in dong_don if r.item_code})
	thong_tin = {}
	bo = set()
	if ma_hang:
		thong_tin = {
			i.name: i
			for i in frappe.get_all(
				"Item",
				filters={"name": ["in", ma_hang]},
				fields=["name", "is_stock_item", "has_batch_no"],
			)
		}
		bo = set(
			frappe.get_all(
				"Product Bundle",
				filters={"name": ["in", ma_hang], "disabled": 0},
				pluck="name",
			)
		)
	mr = _mr_theo_dong([r.name for r in dong_don])

	nguon = {}
	bang = []
	for r in dong_don:
		item = thong_tin.get(r.item_code)
		d = _dong_trong(
			so_detail=r.name, idx=r.idx, item_code=r.item_code,
			item_name=r.item_name or r.item_code or "", kho=r.warehouse,
			dvt=r.stock_uom,
			ly_do=ly_do_khong_tra(r, item, r.item_code in bo),
		)
		bang.append(d)
		if d["ly_do"]:
			continue
		khoa = (r.item_code, r.warehouse)
		if khoa not in nguon:
			ton = _ton_hien_tai(r.item_code, r.warehouse)
			het_han = (
				_ton_het_han(r.item_code, r.warehouse)
				if cint(item.has_batch_no) else 0
			)
			nguon[khoa] = {
				"ton_hien_tai": ton,
				"kha_dung": ton_kha_dung(
					ton, het_han,
					_giu_cho_don_khac(r.item_code, r.warehouse, so.name),
				),
				"don_nhap_khac": _don_nhap_khac(r.item_code, r.warehouse, so.name),
			}
		d["sl_yeu_cau"] = sl_con_giao(r.stock_qty, r.qty, r.delivered_qty)
		d["ton_hien_tai"] = nguon[khoa]["ton_hien_tai"]
		d["don_nhap_khac"] = nguon[khoa]["don_nhap_khac"]

	tra_duoc = [d for d in bang if not d["ly_do"]]
	chia = chia_ton(
		[((d["item_code"], d["kho"]), d["sl_yeu_cau"]) for d in tra_duoc],
		{k: v["kha_dung"] for k, v in nguon.items()},
	)
	for d, (thay, thieu) in zip(tra_duoc, chia):
		phu = mr.get(d["so_detail"]) or {}
		dx = de_xuat(thieu, phu.get("sl"))
		d.update(
			ton_kha_dung=thay, sl_thieu=thieu, de_xuat=dx["ma"],
			mr_da_phu=dx["mr_da_phu"], can_mua=dx["can_mua"],
			mr=list(phu.get("mr") or []),
		)

	# Dòng đặt ngoài CHƯA khớp mã: không có `item_code` nên không có gì để
	# tra. Dòng đã khớp thì đã thành một dòng `items` ở trên.
	for dn in so.get("custom_dat_ngoai") or []:
		if dn.get("item_khop"):
			continue
		bang.append(_dong_trong(
			idx=dn.idx, item_name=dn.get("ten_hang") or "", dvt=dn.get("dvt"),
			sl_yeu_cau=flt(dn.get("so_luong"), DO_CHINH_XAC),
			ly_do=LY_DO_DAT_NGOAI,
		))

	con_mua = any(flt(d["can_mua"]) > 0 for d in tra_duoc)
	return {
		"dong": bang,
		"tong": {
			"so_dong": len(tra_duoc),
			"so_thieu": sum(1 for d in tra_duoc if flt(d["sl_thieu"]) > 0),
		},
		# ERPNext chỉ cho sinh Material Request từ Sales Order đã Submit.
		"co_the_tao_mr": bool(
			cint(so.docstatus) == 1
			and so.get("status") not in ("On Hold", "Closed")
			and con_mua
		),
	}
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: `Ran 43 tests` … `OK`

Nếu `test_lo_het_han_bi_loai_khoi_ton_kha_dung` fail với `ton_kha_dung == 10`: hai lời gọi `get_batch_qty` trong `_ton_het_han` đang trả cùng một tổng. In `get_batch_qty(item_code=…, warehouse=…, for_stock_levels=True)` và bản không có `for_stock_levels` cho mặt hàng test để xem lô hết hạn có mặt ở bản thứ nhất và vắng ở bản thứ hai không.

- [ ] **Step 5: Commit**

```bash
cd /home/hoangvietyeuem/worktrees/miyano_portal-doi-sanh-ton
git add miyano_portal/doi_sanh_ton.py miyano_portal/tests/test_doi_sanh_ton.py
git commit -m "feat(desk): doi sanh ton kho - dung bang cho mot Sales Order

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Endpoint đọc bảng, chốt vai nội bộ

**Files:**
- Modify: `miyano_portal/doi_sanh_ton.py` (thêm vào cuối file)
- Modify: `miyano_portal/tests/test_doi_sanh_ton.py` (thêm vào cuối file)

**Interfaces:**
- Consumes: `bang_cho_don(so) -> dict`, `ROLE_NOI_BO` (Task 1–2).
- Produces:
  - `_don_duoc_doc(order: str)` — trả document Sales Order, ném `frappe.PermissionError` nếu là tài khoản cổng, thiếu vai nội bộ, hoặc thiếu quyền đọc đơn.
  - `doi_sanh_ton(order: str) -> dict` (whitelist) — kết quả `bang_cho_don` với `co_the_tao_mr` đã tính cả quyền tạo MR; hoặc `{"loi": str}` khi phép tính hỏng.

- [ ] **Step 1: Thêm test**

Thêm ngay dưới hằng `KHACH = …`:

```python
# `seed_demo()` tạo tài khoản cổng này cho đúng Customer KHACH (vai "Customer").
BM_USER = "bvbm@demo.miyano"
SALES_USER = "sales_user@demo.miyano"
```

Thêm vào CUỐI file:

```python
class TestEndpointDoc(_CoSo):
	def setUp(self):
		super().setUp()
		if not frappe.db.exists("User", SALES_USER):
			frappe.get_doc({
				"doctype": "User", "email": SALES_USER, "first_name": "Sales DST",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		frappe.get_doc("User", SALES_USER).add_roles("Sales User")
		self.item = self._item()
		self._nap(self.item, 4)
		self.so = self._don([(self.item, 10)])
		self.addCleanup(
			frappe.db.delete, "Error Log", {"method": ["like", "Đối sánh tồn kho:%"]}
		)

	def test_nhan_vien_ban_hang_doc_duoc(self):
		frappe.set_user(SALES_USER)
		bang = dst.doi_sanh_ton(self.so.name)
		self.assertEqual(bang["dong"][0]["sl_thieu"], 6)

	def test_tai_khoan_cong_khach_hang_bi_tu_choi_voi_DON_CUA_CHINH_HO(self):
		"""Khách đọc được Sales Order này (đơn của bệnh viện họ) — và đúng vì
		thế mà chốt phải là vai, không phải quyền đọc đơn."""
		frappe.set_user(BM_USER)
		self.assertTrue(
			frappe.has_permission("Sales Order", "read", doc=self.so.name)
		)
		with self.assertRaises(frappe.PermissionError):
			dst.doi_sanh_ton(self.so.name)

	def test_tai_khoan_cong_LO_DUOC_GAN_vai_noi_bo_van_bi_tu_choi(self):
		"""Chốt "không phải tài khoản cổng" đứng TRƯỚC chốt vai. Giả lập bằng
		cách vá `get_roles`: gán vai Desk thật cho user sẽ khiến Frappe đổi
		`user_type` của họ, không còn là ca cần canh."""
		frappe.set_user(BM_USER)
		with unittest.mock.patch.object(
			frappe, "get_roles", return_value=["Customer", "Sales User", "All"]
		):
			with self.assertRaises(frappe.PermissionError):
				dst.doi_sanh_ton(self.so.name)

	def test_nhan_vien_khong_co_quyen_tao_mr_thi_khong_thay_nut(self):
		frappe.set_user(SALES_USER)
		self.assertFalse(frappe.has_permission("Material Request", "create"))
		self.assertFalse(dst.doi_sanh_ton(self.so.name)["co_the_tao_mr"])

	def test_quan_tri_thay_nut(self):
		self.assertTrue(dst.doi_sanh_ton(self.so.name)["co_the_tao_mr"])

	def test_phep_tinh_hong_KHONG_lam_chet_form(self):
		with unittest.mock.patch.object(
			dst, "bang_cho_don", side_effect=RuntimeError("truy vấn hỏng")
		):
			kq = dst.doi_sanh_ton(self.so.name)
		self.assertEqual(list(kq), ["loi"])
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"method": "Đối sánh tồn kho: không tính được bảng"}
			)
		)

	def test_loi_QUYEN_thi_van_phai_nem_ra(self):
		"""Nuốt lỗi là để form không chết, KHÔNG phải để che lỗi quyền."""
		frappe.set_user(BM_USER)
		with unittest.mock.patch.object(
			dst, "bang_cho_don", side_effect=RuntimeError("không được tới đây")
		):
			with self.assertRaises(frappe.PermissionError):
				dst.doi_sanh_ton(self.so.name)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: FAIL — `AttributeError: module 'miyano_portal.doi_sanh_ton' has no attribute 'doi_sanh_ton'`

- [ ] **Step 3: Viết endpoint**

Thêm vào CUỐI `miyano_portal/doi_sanh_ton.py`:

```python
# ------------------------------------------------------------- endpoint
def _don_duoc_doc(order: str):
	"""Sales Order mà người gọi được xem bảng tồn, hoặc ném PermissionError.

	Ba chốt, theo thứ tự: không phải tài khoản cổng, có vai nội bộ, đọc được
	đơn. Hai chốt đầu là chốt thật — tài khoản cổng khách hàng qua được chốt
	thứ ba với đơn của chính họ. Chốt đầu dùng đúng định nghĩa "tài khoản
	cổng" của cả app (`permissions._is_restricted_user`), để một tài khoản
	khách lỡ được gán thêm vai nội bộ vẫn không thấy tồn của Miyano.
	"""
	from miyano_portal.permissions import _is_restricted_user

	if _is_restricted_user(frappe.session.user):
		raise frappe.PermissionError("Bạn không có quyền xem đối sánh tồn kho.")
	if not set(ROLE_NOI_BO) & set(frappe.get_roles()):
		raise frappe.PermissionError("Bạn không có quyền xem đối sánh tồn kho.")
	so = frappe.get_doc("Sales Order", order)
	so.check_permission("read")
	return so


@frappe.whitelist()
def doi_sanh_ton(order: str) -> dict:
	"""Bảng đối sánh tồn kho của một Sales Order, cho form trên Desk.

	Phép tính hỏng thì trả `{"loi": …}` thay vì ném: bảng là thông tin phụ,
	nó hỏng không được kéo theo cả form Sales Order. Lỗi QUYỀN thì vẫn ném —
	`_don_duoc_doc` nằm NGOÀI khối try.
	"""
	so = _don_duoc_doc(order)
	try:
		bang = bang_cho_don(so)
	except Exception:
		frappe.log_error(
			title="Đối sánh tồn kho: không tính được bảng",
			message=frappe.get_traceback(with_context=True),
		)
		return {"loi": "Không tính được bảng đối sánh tồn kho. Lỗi đã được ghi lại."}
	bang["co_the_tao_mr"] = bool(
		bang["co_the_tao_mr"] and frappe.has_permission("Material Request", "create")
	)
	return bang
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: `Ran 50 tests` … `OK`

- [ ] **Step 5: Commit**

```bash
cd /home/hoangvietyeuem/worktrees/miyano_portal-doi-sanh-ton
git add miyano_portal/doi_sanh_ton.py miyano_portal/tests/test_doi_sanh_ton.py
git commit -m "feat(desk): doi sanh ton kho - endpoint doc bang, chot vai noi bo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Tạo Material Request nháp cho phần thiếu

**Files:**
- Modify: `miyano_portal/doi_sanh_ton.py` (thêm vào cuối file)
- Modify: `miyano_portal/tests/test_doi_sanh_ton.py` (thêm vào cuối file)

**Interfaces:**
- Consumes: `_don_duoc_doc(order)`, `bang_cho_don(so)` (Task 2–3).
- Produces: `tao_mr_phan_thieu(order: str) -> dict` (whitelist) — `{"name": str, "so_dong": int}`.

- [ ] **Step 1: Thêm test**

Thêm vào CUỐI file test:

```python
class TestTaoMr(_CoSo):
	def _mr_cua(self, so):
		return frappe.get_all(
			"Material Request Item",
			filters={"sales_order": so.name},
			fields=["parent", "item_code", "qty", "stock_qty", "uom", "stock_uom",
				"warehouse", "sales_order_item", "schedule_date", "docstatus"],
			order_by="idx",
		)

	def test_chi_gom_dong_thieu_dung_so_thieu_va_la_NHAP(self):
		du, thieu = self._item(), self._item()
		self._nap(du, 10)
		self._nap(thieu, 4)
		so = self._don([(du, 5), (thieu, 10)])

		kq = dst.tao_mr_phan_thieu(so.name)

		self.assertEqual(kq["so_dong"], 1)
		mr = frappe.get_doc("Material Request", kq["name"])
		self.assertEqual(mr.docstatus, 0)
		self.assertEqual(mr.material_request_type, "Purchase")
		self.assertEqual(mr.company, COMPANY)
		self.assertEqual(len(mr.items), 1)
		r = mr.items[0]
		self.assertEqual(r.item_code, thieu)
		self.assertEqual(r.qty, 6)
		self.assertEqual(r.stock_qty, 6)
		self.assertEqual(r.uom, "Hộp")
		self.assertEqual(r.warehouse, KHO_MYN)
		self.assertEqual(r.sales_order, so.name)
		self.assertEqual(r.sales_order_item, so.items[1].name)
		self.assertEqual(
			frappe.utils.getdate(r.schedule_date),
			frappe.utils.getdate(so.items[1].delivery_date),
		)

	def test_ngay_giao_da_qua_thi_ngay_can_hang_la_hom_nay(self):
		item = self._item()
		so = self._don([(item, 3)])
		frappe.db.set_value(
			"Sales Order Item", so.items[0].name, "delivery_date",
			frappe.utils.add_days(frappe.utils.today(), -5),
		)
		kq = dst.tao_mr_phan_thieu(so.name)
		mr = frappe.get_doc("Material Request", kq["name"])
		self.assertEqual(
			frappe.utils.getdate(mr.items[0].schedule_date),
			frappe.utils.getdate(frappe.utils.today()),
		)

	def test_bam_lan_hai_khong_sinh_mr_trung(self):
		item = self._item()
		so = self._don([(item, 3)])
		dst.tao_mr_phan_thieu(so.name)
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(len(self._mr_cua(so)), 1)
		d = self._dong_dau(so)
		self.assertEqual(d["de_xuat"], dst.DX_DA_CO_MR)
		self.assertEqual(d["mr_da_phu"], 3)
		self.assertEqual(len(d["mr"]), 1)

	def test_mr_da_huy_thi_khong_con_tinh_la_phu(self):
		item = self._item()
		so = self._don([(item, 3)])
		mr = frappe.get_doc("Material Request", dst.tao_mr_phan_thieu(so.name)["name"])
		mr.submit()
		mr.cancel()
		self.assertEqual(self._dong_dau(so)["de_xuat"], dst.DX_CAN_MUA)
		self.assertEqual(dst.tao_mr_phan_thieu(so.name)["so_dong"], 1)

	def test_mr_da_nhan_ve_kho_thi_phan_da_nhan_khong_con_la_phu(self):
		"""Cần 10, tồn 0, MR 10. Hàng về đủ rồi 6 cái bị xuất cho đơn khác:
		thiếu 6 và MR không còn phủ gì. Đếm `stock_qty` thay vì
		`stock_qty − received_qty` thì bảng nói "đã có MR" và nút biến mất."""
		item = self._item()
		so = self._don([(item, 10)])
		ten_mr = dst.tao_mr_phan_thieu(so.name)["name"]
		dong_mr = frappe.get_doc("Material Request", ten_mr).items[0].name
		frappe.db.set_value("Material Request Item", dong_mr, "received_qty", 10)
		self._nap(item, 4)  # 10 về, 6 đã đi nơi khác -> còn 4 trên kệ

		d = self._dong_dau(so)
		self.assertEqual(d["sl_thieu"], 6)
		self.assertEqual(d["mr_da_phu"], 0)
		self.assertEqual(d["de_xuat"], dst.DX_CAN_MUA)

	def test_mr_theo_so_thieu_LUC_BAM_khong_theo_luc_bang_hien(self):
		item = self._item()
		so = self._don([(item, 10)])
		self.assertEqual(self._dong_dau(so)["can_mua"], 10)
		self._nap(item, 7)  # hàng về giữa lúc xem và lúc bấm
		kq = dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(
			frappe.get_doc("Material Request", kq["name"]).items[0].qty, 3
		)

	def test_mr_phu_mot_phan_thi_lan_sau_chi_tao_phan_con_lai(self):
		item = self._item()
		self._nap(item, 4)
		so = self._don([(item, 10)])
		dst.tao_mr_phan_thieu(so.name)  # MR 6
		# Đơn khác vừa Submit lấy mất 3 trong 4 cái trên kệ.
		self._don([(item, 3)])
		d = self._dong_dau(so)
		self.assertEqual(d["sl_thieu"], 9)
		self.assertEqual(d["de_xuat"], dst.DX_MOT_PHAN)
		self.assertEqual(d["can_mua"], 3)
		kq = dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(
			frappe.get_doc("Material Request", kq["name"]).items[0].qty, 3
		)

	def test_don_nhap_khong_tao_duoc_mr(self):
		item = self._item()
		so = self._don([(item, 3)], submit=False)
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)
		self.assertEqual(self._mr_cua(so), [])

	def test_don_da_huy_khong_tao_duoc_mr(self):
		item = self._item()
		so = self._don([(item, 3)])
		so.cancel()
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)

	def test_don_du_hang_khong_tao_duoc_mr(self):
		item = self._item()
		self._nap(item, 10)
		so = self._don([(item, 3)])
		with self.assertRaises(frappe.ValidationError):
			dst.tao_mr_phan_thieu(so.name)

	def test_tai_khoan_cong_khach_hang_bi_tu_choi(self):
		item = self._item()
		so = self._don([(item, 3)])
		frappe.set_user(BM_USER)
		with self.assertRaises(frappe.PermissionError):
			dst.tao_mr_phan_thieu(so.name)
		frappe.set_user("Administrator")
		self.assertEqual(self._mr_cua(so), [])

	def test_nhan_vien_khong_co_quyen_tao_mr_bi_tu_choi(self):
		item = self._item()
		so = self._don([(item, 3)])
		if not frappe.db.exists("User", SALES_USER):
			frappe.get_doc({
				"doctype": "User", "email": SALES_USER, "first_name": "Sales DST",
				"send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		frappe.get_doc("User", SALES_USER).add_roles("Sales User")
		frappe.set_user(SALES_USER)
		with self.assertRaises(frappe.PermissionError):
			dst.tao_mr_phan_thieu(so.name)
		frappe.set_user("Administrator")
		self.assertEqual(self._mr_cua(so), [])
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: FAIL — `AttributeError: module 'miyano_portal.doi_sanh_ton' has no attribute 'tao_mr_phan_thieu'`

- [ ] **Step 3: Viết `tao_mr_phan_thieu`**

Thêm vào CUỐI `miyano_portal/doi_sanh_ton.py`:

```python
@frappe.whitelist()
def tao_mr_phan_thieu(order: str) -> dict:
	"""Tạo MỘT Material Request NHÁP cho phần thiếu của đơn (spec §6).

	Không gọi `sales_order.make_material_request` của ERPNext: hàm đó lấy toàn
	bộ số lượng đơn (không trừ tồn) và chỉ đếm MR đã Submit khi chống trùng.

	Không bao giờ Submit — bộ phận mua kiểm tra rồi tự Submit.
	"""
	so = _don_duoc_doc(order)
	if not frappe.has_permission("Material Request", "create"):
		raise frappe.PermissionError(
			"Bạn không có quyền tạo yêu cầu mua hàng (Material Request)."
		)
	if cint(so.docstatus) != 1:
		frappe.throw(
			"Chỉ tạo được yêu cầu mua hàng cho đơn đã xác nhận.",
			frappe.ValidationError,
		)
	if so.status in ("On Hold", "Closed"):
		frappe.throw(
			"Đơn đang tạm giữ hoặc đã đóng — không tạo yêu cầu mua hàng.",
			frappe.ValidationError,
		)

	# Khoá dòng đơn rồi MỚI tính lại: hai lần bấm sát nhau xếp hàng ở đây, lần
	# sau thấy MR nháp của lần trước và dừng. Số thiếu tính lại tại máy chủ,
	# không nhận từ trình duyệt — tồn có thể đã đổi từ lúc bảng hiện.
	frappe.db.get_value("Sales Order", so.name, "name", for_update=True)
	thieu = [d for d in bang_cho_don(so)["dong"] if flt(d["can_mua"]) > 0]
	if not thieu:
		frappe.throw(
			"Đơn không còn phần thiếu nào cần mua thêm.", frappe.ValidationError
		)

	hom_nay = getdate(today())
	ngay_giao = {r.name: r.delivery_date for r in so.items}

	mr = frappe.new_doc("Material Request")
	mr.material_request_type = "Purchase"
	mr.company = so.company
	mr.transaction_date = hom_nay
	for d in thieu:
		ngay = getdate(ngay_giao.get(d["so_detail"]) or so.delivery_date or hom_nay)
		mr.append("items", {
			"item_code": d["item_code"],
			"item_name": d["item_name"],
			"qty": d["can_mua"],
			"uom": d["dvt"],
			"stock_uom": d["dvt"],
			"conversion_factor": 1,
			"stock_qty": d["can_mua"],
			"warehouse": d["kho"],
			"schedule_date": max(ngay, hom_nay),
			"sales_order": so.name,
			"sales_order_item": d["so_detail"],
		})
	mr.schedule_date = min(getdate(r.schedule_date) for r in mr.items)
	mr.insert()
	return {"name": mr.name, "so_dong": len(mr.items)}
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: `Ran 62 tests` … `OK`

Nếu `test_bam_lan_hai…` fail vì `mr_da_phu == 0` sau lần tạo đầu: dòng MR nháp đang có `stock_qty = 0`. Kiểm `stock_qty` được truyền trong `mr.append` và đọc lại bằng `frappe.db.get_value("Material Request Item", {"parent": <mr>}, "stock_qty")`.

- [ ] **Step 5: Commit**

```bash
cd /home/hoangvietyeuem/worktrees/miyano_portal-doi-sanh-ton
git add miyano_portal/doi_sanh_ton.py miyano_portal/tests/test_doi_sanh_ton.py
git commit -m "feat(desk): tao Material Request nhap cho phan thieu cua Sales Order

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Khối bảng và nút trên form Sales Order

**Files:**
- Modify: `miyano_portal/public/js/sales_order.js`
- Modify: `miyano_portal/tests/test_doi_sanh_ton.py` (thêm vào cuối file)

**Interfaces:**
- Consumes:
  - `miyano_portal.doi_sanh_ton.doi_sanh_ton(order)` → `{dong, tong, co_the_tao_mr}` hoặc `{loi}`
  - `miyano_portal.doi_sanh_ton.tao_mr_phan_thieu(order)` → `{name, so_dong}`
  - Mã đề xuất: `"du"`, `"can_mua"`, `"mr_mot_phan"`, `"da_co_mr"`
- Produces: không có gì cho task khác.

- [ ] **Step 1: Thêm test canh file JS và canh cổng khách**

Thêm vào đầu file test, cạnh các `import` khác:

```python
from pathlib import Path
```

Thêm vào CUỐI file test:

```python
class TestGiaoDienDesk(FrappeTestCase):
	"""Desk JS không có bộ chạy test trong repo này — canh bằng nội dung
	file, cùng cách `test_cr06_desk_hang_moi.py` đang làm."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Đi từ file THẬT của module, không từ `frappe.get_app_path`: khi
		# module được nối vào app bằng symlink (đang phát triển ở worktree),
		# `resolve()` dẫn về đúng cây mã chứa bản `sales_order.js` đi cùng nó.
		goc = Path(dst.__file__).resolve().parent
		cls.js = (goc / "public" / "js" / "sales_order.js").read_text(encoding="utf-8")
		cls.goc_repo = goc.parent

	def test_form_goi_dung_hai_endpoint(self):
		self.assertIn("miyano_portal.doi_sanh_ton.doi_sanh_ton", self.js)
		self.assertIn("miyano_portal.doi_sanh_ton.tao_mr_phan_thieu", self.js)

	def test_danh_sach_vai_o_js_khop_voi_python(self):
		"""Hai danh sách lệch nhau thì hoặc nhân viên không thấy bảng, hoặc
		người không có vai mở đơn là dính hộp báo lỗi quyền."""
		for vai in dst.ROLE_NOI_BO:
			self.assertIn(f'"{vai}"', self.js, vai)

	def test_js_xu_du_bon_ma_de_xuat(self):
		for ma in (dst.DX_DU, dst.DX_CAN_MUA, dst.DX_MOT_PHAN, dst.DX_DA_CO_MR):
			self.assertIn(f"{ma}:", self.js, ma)

	def test_cong_khach_hang_KHONG_goi_doi_sanh_ton(self):
		"""Spec Q4: tồn của Miyano không được lộ sang cổng khách hàng."""
		src = self.goc_repo / "frontend" / "src"
		for f in list(src.rglob("*.vue")) + list(src.rglob("*.js")):
			self.assertNotIn(
				"doi_sanh_ton", f.read_text(encoding="utf-8"), str(f)
			)
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: 3 FAIL trong `TestGiaoDienDesk` (`test_form_goi_dung_hai_endpoint`, `test_danh_sach_vai_o_js_khop_voi_python`, `test_js_xu_du_bon_ma_de_xuat`); `test_cong_khach_hang_KHONG_goi_doi_sanh_ton` pass.

- [ ] **Step 3: Gọi khối bảng từ `refresh`**

Trong `miyano_portal/public/js/sales_order.js`, sửa `refresh`: thêm một dòng ngay sau `hien_thong_tin_hang_moi(frm);`

```javascript
		hien_thong_tin_hang_moi(frm);
		hien_doi_sanh_ton(frm);
```

- [ ] **Step 4: Thêm ba hàm vào cuối `sales_order.js`**

```javascript
// Đối sánh tồn kho của MIYANO (spec 2026-10-12).
//
// Danh sách vai phải KHỚP `doi_sanh_ton.ROLE_NOI_BO` ở máy chủ (có bài test
// canh). Lọc ở đây không phải là chốt quyền — chốt thật nằm ở máy chủ — mà
// để người không có vai mở đơn không bị hộp báo "không có quyền" bật lên.
const VAI_XEM_TON = [
	"System Manager", "Sales Manager", "Sales User",
	"Stock Manager", "Stock User", "Purchase Manager", "Purchase User",
];

const NHAN_DE_XUAT = {
	du: (d, so) => `<span style="color:var(--green-600)">Đủ hàng</span>`,
	can_mua: (d, so) => `<b style="color:var(--red-600)">Cần mua ${so(d.can_mua)}</b>`,
	mr_mot_phan: (d, so) =>
		`Đã có MR ${so(d.mr_da_phu)} · <b style="color:var(--red-600)">cần mua thêm ${so(d.can_mua)}</b>`,
	da_co_mr: (d, so) => `Đã có MR ${so(d.mr_da_phu)}`,
};

function hien_doi_sanh_ton(frm) {
	if (frm.is_new()) return;
	if (!VAI_XEM_TON.some((v) => frappe.user_roles.includes(v))) return;

	const ten = frm.doc.name;
	frappe.call({
		method: "miyano_portal.doi_sanh_ton.doi_sanh_ton",
		args: { order: ten },
	}).then((r) => {
		// Người dùng đã chuyển sang đơn khác trong lúc chờ: bỏ kết quả cũ.
		if (frm.doc.name !== ten || !r.message) return;
		ve_doi_sanh_ton(frm, r.message);
		if (r.message.co_the_tao_mr) {
			frm.add_custom_button(
				__("Tạo MR cho phần thiếu"), () => tao_mr_phan_thieu(frm), __("Miyano")
			);
		}
	});
}

function ve_doi_sanh_ton(frm, bang) {
	const esc = frappe.utils.escape_html;
	const so = (v) => (v === null || v === undefined
		? "—"
		: format_number(v, null, Number.isInteger(v) ? 0 : 3));

	// `refresh` có thể chạy hai lần sát nhau; mỗi lần là một lời gọi riêng.
	// Gỡ khối cũ trước khi vẽ, không thì form có hai bảng.
	frm.dashboard.parent.find(".mvl-doi-sanh-ton")
		.closest(".form-dashboard-section").remove();

	let than;
	if (bang.loi) {
		than = `<p class="text-muted">${esc(bang.loi)}</p>`;
	} else {
		const tong = bang.tong.so_thieu
			? `<b style="color:var(--red-600)">Thiếu ${bang.tong.so_thieu}/${bang.tong.so_dong} dòng</b>`
			: (bang.tong.so_dong
				? `<b style="color:var(--green-600)">Đủ hàng cả đơn</b>`
				: `<span class="text-muted">Không có dòng nào tra được tồn</span>`);

		const hang = bang.dong.map((d) => {
			const mr = (d.mr || []).map(
				(m) => `<a href="/app/material-request/${encodeURIComponent(m)}">${esc(m)}</a>`
			).join(", ");
			const de_xuat = d.ly_do
				? `<span class="text-muted">${esc(d.ly_do)}</span>`
				: NHAN_DE_XUAT[d.de_xuat](d, so) + (mr ? `<br>${mr}` : "");
			const nhap = d.don_nhap_khac
				? `<div class="text-muted" style="font-size:.75rem">Đơn nháp khác đang chờ: ${so(d.don_nhap_khac.sl)} ${esc(d.dvt || "")} (${d.don_nhap_khac.so_don} đơn)</div>`
				: "";
			return `<tr>
				<td>${esc(d.item_name || "")}
					${d.item_code ? `<div class="text-muted" style="font-size:.75rem">${esc(d.item_code)}${d.kho ? " · " + esc(d.kho) : ""}</div>` : ""}
				</td>
				<td>${esc(d.dvt || "")}</td>
				<td class="text-right">${so(d.sl_yeu_cau)}</td>
				<td class="text-right">${so(d.ton_hien_tai)}</td>
				<td class="text-right">${so(d.ton_kha_dung)}${nhap}</td>
				<td class="text-right">${d.sl_thieu ? `<b style="color:var(--red-600)">${so(d.sl_thieu)}</b>` : so(d.sl_thieu)}</td>
				<td>${de_xuat}</td>
			</tr>`;
		}).join("");

		than = `<p style="margin:0 0 .5rem">${tong}
				<span class="text-muted"> · tính theo bản đơn đã lưu, đơn vị tồn kho</span></p>
			<div style="overflow-x:auto">
			<table class="table table-bordered" style="margin:0;font-size:.85rem">
				<thead><tr>
					<th>Mặt hàng</th><th>ĐVT</th>
					<th class="text-right">SL yêu cầu</th>
					<th class="text-right">Tồn hiện tại</th>
					<th class="text-right">Tồn có thể sử dụng</th>
					<th class="text-right">SL thiếu</th>
					<th>Đề xuất</th>
				</tr></thead>
				<tbody>${hang}</tbody>
			</table></div>`;
	}

	frm.dashboard.add_section(
		`<div class="mvl-doi-sanh-ton" style="padding:.5rem 0">${than}</div>`,
		__("Đối sánh tồn kho")
	);
}

function tao_mr_phan_thieu(frm) {
	frappe.confirm(
		__("Tạo một yêu cầu mua hàng NHÁP cho các dòng đang thiếu? Số lượng được tính lại theo tồn kho lúc này."),
		() => {
			frappe.call({
				method: "miyano_portal.doi_sanh_ton.tao_mr_phan_thieu",
				args: { order: frm.doc.name },
				freeze: true,
				freeze_message: __("Đang tạo yêu cầu mua hàng…"),
			}).then((r) => {
				if (!r.message) return;
				frappe.show_alert({
					message: __("Đã tạo {0} (nháp) — {1} dòng", [r.message.name, r.message.so_dong]),
					indicator: "green",
				});
				frappe.set_route("Form", "Material Request", r.message.name);
			});
		}
	);
}
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_doi_sanh_ton`
Expected: `Ran 66 tests` … `OK`

- [ ] **Step 6: Kiểm tra trên trình duyệt — CẦN CHỦ DỰ ÁN ĐỒNG Ý TRƯỚC**

Trình duyệt chỉ thấy `sales_order.js` của APP, mà APP đang ở nhánh khác. Bước này chỉ làm được khi nhánh `feat/doi-sanh-ton-kho-so` đã được đưa vào APP (phiên Price List xong và chủ dự án cho chuyển nhánh hoặc gộp nhánh). Chưa tới lúc đó thì DỪNG ở đây, báo rõ "phần giao diện chưa kiểm trên trình duyệt", và làm tiếp Step 7–8. Không chép hay nối `sales_order.js` vào APP.

File `doctype_js` được Frappe nạp thẳng từ thư mục app, không cần `bench build`.

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local clear-cache`

Mở một Sales Order trên Desk bằng tài khoản nội bộ và kiểm đủ sáu điều:

1. Đơn nháp: khối "Đối sánh tồn kho" hiện, không có nút "Tạo MR cho phần thiếu".
2. Đơn đã Submit có dòng thiếu: nút hiện trong nhóm "Miyano"; bấm → xác nhận → mở ra một Material Request ở trạng thái Draft, đúng dòng và đúng số thiếu.
3. Quay lại đơn: cột Đề xuất của dòng đó là "Đã có MR n" kèm liên kết tới MR; nút không còn.
4. Bấm F5 và bấm nút "Tải lại" của form hai lần liên tiếp: chỉ có MỘT khối bảng.
5. Đơn có dòng đặt ngoài chưa khớp mã: dòng đó hiện `—` ở ba cột tồn và lý do ở cột Đề xuất.
6. Mở Console của trình duyệt: không có lỗi JavaScript.

`frm.dashboard.parent` (jQuery) là nơi `add_section` gắn khối vào, và mỗi khối được bọc bằng `.form-dashboard-section` (`frappe/public/js/frappe/form/section.js`). Nếu KHÔNG có bảng nào hiện và Console báo lỗi ở dòng `.find(".mvl-doi-sanh-ton")`: `frm.dashboard.parent` không phải jQuery ở bản này — bọc lại thành `$(frm.dashboard.parent)`. Nếu có HAI bảng: xem phần tử cha của `.mvl-doi-sanh-ton` trong DevTools và thay đúng tên class đó vào `.closest(...)`.

- [ ] **Step 7: Chạy lại các bộ test láng giềng**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_cr06_desk_hang_moi
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e3_doi_soat
```
Expected: `test_e3_doi_soat` `OK`. `test_cr06_desk_hang_moi` đọc `sales_order.js` của APP (bản chưa sửa) nên kết quả của nó ở đây chỉ xác nhận không làm hỏng gì trong APP; chạy lại nó sau khi nhánh vào APP.

- [ ] **Step 8: Commit**

```bash
cd /home/hoangvietyeuem/worktrees/miyano_portal-doi-sanh-ton
git add miyano_portal/public/js/sales_order.js miyano_portal/tests/test_doi_sanh_ton.py
git commit -m "feat(desk): bang doi sanh ton kho va nut tao MR tren form Sales Order

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
