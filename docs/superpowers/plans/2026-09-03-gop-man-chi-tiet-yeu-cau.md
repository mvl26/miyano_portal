# Gộp màn chi tiết phiếu + chi tiết đơn — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một yêu cầu mua = một màn chi tiết duy nhất, đọc theo dòng thời gian (xin gì → duyệt bao nhiêu → giá → giao tới đâu), thay cho hai màn `DeXuatDetail.vue` và `OrderDetail.vue` hôm nay.

**Architecture:** Giữ NGUYÊN hai đường `/yeu-cau/phieu/:ten` và `/yeu-cau/don/:name`, nhưng cả hai trỏ vào CÙNG một component `ChiTietYeuCau.vue`. Component nhận một đầu mối (phiếu hoặc đơn), nạp song song nửa còn lại nếu có, rồi dựng các KHỐI — khối nào không có dữ liệu thì không hiện. Bảng mặt hàng gộp làm MỘT, cột mọc theo giai đoạn; phép nối phiếu↔đơn làm ở SERVER (`de_xuat_chi_tiet`) chứ không ở client, vì repo này không có hạ tầng test JS.

**Tech Stack:** Vue 3 (`<script setup>`, không store ngoài), vue-router 4, Vite 6; backend Frappe/ERPNext (Python 3.11), test bằng `bench run-tests`.

**Spec:** Không có file spec riêng — thiết kế được chủ đầu tư duyệt trong hội thoại 03/09/2026 và được chép nguyên vào mục "Thiết kế đã chốt" ngay dưới đây. Bối cảnh kiến trúc: `docs/BAN-DO-CHUC-NANG.md` §2.3 (QĐ-G11 và khung đảo lại 03/09/2026).

---

## Global Constraints

Mọi task đều phải tuân, không nhắc lại trong từng task:

- **Không 404 một đường đang chạy.** Luật QĐ-G7/QĐ-G11 (`frontend/src/router.js`). Kế hoạch này KHÔNG đổi đường nào — đó là lý do chọn "hai đường, một component".
- **Thông báo tự động đã gửi đi trỏ tới `/yeu-cau/don/<name>`** (`api/portal.py::_link_chung_tu`, chốt bởi `tests/test_thong_bao_endpoint.py`). Đường này phải tiếp tục mở đúng màn.
- **Hide, don't disable.** Nút không đủ điều kiện thì BIẾN MẤT, không hiện xám (`frontend/src/de-xuat-actions.js`, đầu file).
- **Hành động là dữ liệu.** Nút mới phải khai trong registry, không rải `v-if` trong template.
- **Registry chỉ quyết định HIỆN GÌ, không phải chốt an ninh.** Server đã enforce; `when()` không bao giờ được là thứ duy nhất ngăn một chuyển trạng thái sai.
- **Không có test JS.** `frontend/package.json` chỉ có `build`. Mọi bất biến frontend được canh bằng test Python đọc file bằng regex — tiền lệ: `tests/test_de_xuat_action_registry.py`, `tests/test_yeu_cau_list.py::TestDuongCuVaSoCua`.
- **Python:** `api/de_xuat.py` + doctype dùng **tab**; `api/portal.py` dùng **4 dấu cách**. Theo đúng file đang sửa.
- **Chạy suite:** `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal` (~5,5 phút, 1758 test tính đến 03/09/2026).
- **Build frontend:** `cd frontend && yarn build` — bundle sinh ra ở `miyano_portal/public/frontend/`, **phải commit kèm** (đó là thứ site phục vụ).
- **Ngôn ngữ:** chữ hiển thị và chú thích bằng tiếng Việt, theo văn phong sẵn có (nêu LÝ DO, không mô tả lại code).
- **"CHÉP NGUYÊN từ `<file>` dòng A–B" là lệnh DI CHUYỂN nguyên văn**, không phải chỗ trống để tự viết lại. Những khối đó là markup đang chạy thật, đã qua nhiều vòng review, và kế hoạch cố ý KHÔNG in lại chúng — in lại là tạo bản sao thứ hai sẽ trôi khỏi bản gốc ngay trong lúc thi công. Đổi tên biến theo hướng dẫn, **không sửa class, không sửa chữ hiển thị, không "tiện tay" dọn**. Muốn sửa gì trong đó thì đó là một task khác.

---

## Thiết kế đã chốt

### Vì sao gộp

Task 11 (QĐ-G11) gộp *danh sách* vì "một yêu cầu phải xuất hiện đúng một lần, người dùng không phải học giai đoạn nội bộ mới tìm lại được đồ mình xin". Ở tầng **chi tiết** nghịch lý đó còn nguyên: bấm một dòng → màn phiếu → phải bấm tiếp link "Đơn hàng" → màn thứ hai. Khoa xin 100, duyệt 40, giao 25 — ba con số của MỘT việc, nằm ở HAI trang.

Từ Task 7, **mọi đơn đặt qua cổng đều có một phiếu đứng sau** (`api/portal.py::_dam_bao_phieu_tu_duyet` tạo phiếu "Đã duyệt" cho cả đường quản lý đặt thẳng). Quan hệ phiếu↔đơn là **1:1**; ngoại lệ duy nhất là ~102 đơn cũ có trước luồng duyệt. Hai màn tách đôi vì **lịch sử thi công**, không vì nghiệp vụ.

Lợi ích đo được nhất, không phải thẩm mỹ: ở giai đoạn "Chờ quý vị đồng ý", hai đường sửa số lượng đang nằm ở hai màn khác nhau và **chia theo vai trò** —
- quản lý: `portal_order_sua_so_luong` ("Gửi lại để báo giá", trong `OrderDetail.vue`, gated bởi `duoc_sua_da_duyet`);
- nhân viên khoa: `de_xuat_xin_sua` ("Xin sửa số lượng", trong `DeXuatDetail.vue`, gated bởi `!me.la_quan_ly`).

Hôm nay người dùng thấy đường nào là tuỳ họ tình cờ mở màn nào. Gộp xong: một màn, một thanh hành động, registry tự chọn đúng nút cho đúng vai.

### Đường dẫn — hai cửa, một phòng

**KHÔNG tạo route mới, KHÔNG chuyển hướng.** Lý do: `Portal De Xuat Mua.name` (`DXM-2026-000xx`) và `Sales Order.name` là HAI docname khác nhau, nên "một route nhận cả hai id" phải tự đoán loại chứng từ từ chuỗi id — một phép đoán không có gì bảo đảm. Giữ hai đường thì:

| Đường | Tham số | Đầu mối |
|---|---|---|
| `/yeu-cau/phieu/:ten` | docname phiếu | phiếu; nạp đơn qua `doc.sales_order` |
| `/yeu-cau/don/:name` | docname đơn | đơn; nạp phiếu qua `data.de_xuat` (**thêm ở Task 1**) |

Cả hai `component: ChiTietYeuCau`. Bookmark, link trong thông báo đã gửi, và `test_thong_bao_endpoint.py` không phải đụng tới dòng nào.

### Bố cục

Full width, đọc từ trên xuống theo dòng thời gian. Khối không có dữ liệu thì **không hiện** (không phải hiện rỗng):

```
← Quay lại  (giữ ?chip= và ?khoa= như hiện nay)

┌ 1. ĐẦU TRANG ─────────────────────────────────────────────┐
│ MD-HUYETHOC-260825-04              [badge GIAI ĐOẠN]      │
│ Khoa Huyết học · Đặt ngày 25/08/2026 · 12.450.000 ₫       │
│ (Số dự trù · HĐNT nếu có)                                 │
│ Lý do từ chối (đỏ) — nếu có, của phiếu HOẶC của đơn       │
└───────────────────────────────────────────────────────────┘

┌ 2. VIỆC ĐANG CHỜ BẠN ── chỉ khi có ít nhất một hành động ─┐
│ banner hạn báo giá (nếu đang chờ đồng ý)                  │
│ dòng nhắc quy ước (nếu quản lý đang duyệt)                │
│ [Duyệt] [Từ chối] [Đồng ý đặt hàng] [Xin sửa số lượng] …  │
└───────────────────────────────────────────────────────────┘

┌ 3. TIẾN TRÌNH ── chỉ khi ĐÃ có đơn ───────────────────────┐
│ Đặt hàng → Xác nhận → Soạn hàng → Giao hàng → Hoá đơn     │
└───────────────────────────────────────────────────────────┘

▸ 4. YÊU CẦU & DUYỆT  ── <details>, chỉ khi CÓ phiếu ───────
     Người yêu cầu · Thời điểm gửi · Lý do yêu cầu
     Người duyệt · Thời điểm duyệt · Tư cách duyệt

┌ grid2 ────────────────────────┬───────────────────────────┐
│ 5. MẶT HÀNG                   │ 6. GIAO HÀNG (chỉ khi có  │
│    một bảng, cột theo giai    │    đơn)                   │
│    đoạn                       │    HOÁ ĐƠN CỦA ĐƠN NÀY    │
│    Đặt ngoài (nếu có)         │    TÀI LIỆU & ĐẶT LẠI     │
└───────────────────────────────┴───────────────────────────┘
```

**Ba trường hợp, cùng một màn:**

| Giai đoạn | Khối hiện |
|---|---|
| Nháp / Chờ duyệt / Từ chối / Đã huỷ (chưa có đơn) | 1, 2, 4 (mở sẵn), 5 |
| Đã duyệt / Chờ quý vị đồng ý / Đã giao | 1, 2, 3, 4, 5, 6 |
| Đơn cũ không có phiếu (~102 đơn) | 1, 2, 3, 5, 6 — khối 4 vắng |

Nghĩa là: không có màn nào trống, cũng không có màn nào thừa. Ở hai đầu, màn gộp co lại đúng bằng một trong hai màn hôm nay.

**Luật thu gọn khối 4** (chủ đầu tư chốt): `<details open>` khi `giai_doan !== 'da_giao'`. Đơn đã giao xong thì câu hỏi của người dùng là "hàng đâu, hoá đơn đâu" — con số duyệt là chuyện đã xong; nhưng nó là dữ liệu đối chiếu khi có tranh cãi nên **thu gọn, không giấu**. Một dòng điều kiện, đổi luật sau này chỉ sửa đúng dòng đó.

### Bảng mặt hàng gộp

Một bảng. Nguồn dòng:
- **Có phiếu** → dòng của PHIẾU. Phiếu là tập cha: nó giữ cả dòng quản lý đã hạ về 0 (gạch ngang, nhãn "Không duyệt" — bằng chứng "khoa đã xin gì") lẫn dòng "Quản lý thêm".
- **Không có phiếu** → dòng của ĐƠN.

Cột mọc theo giai đoạn:

| Cột | Hiện khi |
|---|---|
| Mặt hàng, ĐVT | luôn |
| SL đề xuất | có phiếu |
| SL đặt (số THẬT trên đơn) | có đơn |
| SL duyệt | có phiếu VÀ `trang_thai !== 'Nháp'` |
| SL xin sửa | `trang_thai === 'Chờ duyệt sửa'` |
| Ghi chú quản lý | có phiếu |
| Đơn giá, Thành tiền | có đơn |
| Đã giao | có đơn VÀ đơn đã giao ít nhất một đợt |

**Phép nối phiếu↔đơn làm ở SERVER.** `de_xuat_chi_tiet` đã trả `so_luong_tren_don` mỗi dòng (Ruling P51) bằng đúng một truy vấn `Sales Order Item`; Task 2 mở rộng truy vấn đó để trả thêm đơn giá / thành tiền / đã giao. Không viết hàm nối trong JS: repo không có test JS, còn phía Python thì `tests/` canh được.

Dòng `dat_ngoai` (hàng khách gõ tay chưa có mã) giữ **bảng con riêng** ngay dưới, như hôm nay — chúng là loại dòng khác ("Miyano đang tìm nguồn"), gộp vào bảng chính là nói sai về chúng.

### Thanh hành động gộp

Hai registry, một thanh:
- `de-xuat-actions.js` — **giữ nguyên**, đang được `tests/test_de_xuat_action_registry.py` canh từng tên endpoint.
- `don-actions.js` — **mới** (Task 3), cùng hình dạng, cho hành động của Sales Order.

Component nối hai mảng rồi render. Mỗi mục mang `nhom: 'phieu' | 'don'` để biết gọi `api.callDeXuat` hay `api.call`.

---

## Cấu trúc file

**Tạo mới**

| File | Trách nhiệm |
|---|---|
| `frontend/src/don-actions.js` | Registry hành động của Sales Order (`when(don, me)`), JS thuần, không import Vue |
| `frontend/src/views/ChiTietYeuCau.vue` | Màn gộp: nạp dữ liệu, đầu trang, thanh hành động, lắp các khối |
| `frontend/src/components/chi-tiet/KhoiTienTrinh.vue` | Mốc tiến trình (chuyển từ `OrderDetail.vue`) |
| `frontend/src/components/chi-tiet/KhoiGiaoHang.vue` | Đợt giao + kiểm hàng + hoá đơn nháp (chuyển từ `OrderDetail.vue`) |
| `frontend/src/components/chi-tiet/KhoiHoaDonTaiLieu.vue` | Hoá đơn của đơn + PDF + Đặt lại + Huỷ/Sửa (chuyển từ `OrderDetail.vue`) |
| `frontend/src/components/chi-tiet/KhoiBaoGia.vue` | Banner hạn báo giá + ô sửa số lượng gửi lại (chuyển từ `OrderDetail.vue`) |
| `frontend/src/components/chi-tiet/KhoiTruyVet.vue` | Người yêu cầu / thời điểm / người duyệt, bọc `<details>` |
| `frontend/src/components/chi-tiet/BangMatHang.vue` | Bảng mặt hàng gộp, cột theo giai đoạn |
| `miyano_portal/tests/test_chi_tiet_gop.py` | Test cho hai bổ sung backend + lưới regex cho màn gộp |

**Sửa**

| File | Việc |
|---|---|
| `miyano_portal/api/portal.py` | `portal_order_track` trả thêm `de_xuat` |
| `miyano_portal/api/de_xuat.py` | `de_xuat_chi_tiet` trả thêm giá/đã giao mỗi dòng |
| `frontend/src/router.js` | Hai route trỏ vào `ChiTietYeuCau` |
| `frontend/src/views/YeuCauList.vue` | Một dòng, một đích — bỏ nút "Đơn hàng" trùng |
| `frontend/src/App.vue` | Không đổi (đã ôm cả hai route từ 03/09 sáng) |
| `miyano_portal/tests/test_de_xuat_action_registry.py` | Quét thêm `don-actions.js`, đối chiếu `api/portal.py` |
| `miyano_portal/tests/test_yeu_cau_list.py` | Cập nhật `test_khong_con_man_danh_sach_cu` |
| `docs/BAN-DO-CHUC-NANG.md`, `docs/HDSD-*.md` | Cập nhật mô tả màn |

**Xoá**

- `frontend/src/views/OrderDetail.vue` (Task 7)
- `frontend/src/views/DeXuatDetail.vue` (Task 7)

---

## Task 1: `portal_order_track` trả tên phiếu đứng sau đơn và `per_delivered`

**Files:**
- Modify: `miyano_portal/api/portal.py` (khối `return {` của `portal_order_track`, quanh dòng 1204–1230 — mốc ổn định: dòng `"ma_tra_cuu": so.get("custom_ma_tra_cuu") or "",`)
- Test: `miyano_portal/tests/test_chi_tiet_gop.py` (tạo mới)

**Interfaces:**
- Consumes: không có (task đầu)
- Produces:
  - `portal_order_track(order)["de_xuat"]` — `str` (docname `Portal De Xuat Mua`) hoặc `""` khi đơn không có phiếu đứng sau. Task 7 dùng khoá này để nạp nửa phiếu khi vào bằng đường `/yeu-cau/don/:name`.
  - `portal_order_track(order)["per_delivered"]` — `float`, phần trăm đã giao. Task 7 dùng để suy giai đoạn `da_giao`, và đó là điều kiện THU GỌN khối "Yêu cầu & duyệt".

  **Vì sao cần khoá thứ hai:** payload hôm nay có `milestones[key="delivering"].done`, nhưng cờ đó là `per_delivered > 0` (giao được một thùng cũng bật). Ruling P42 định nghĩa giai đoạn "Đã giao" là `>= 100` — "giao 25% mà báo Đã giao là sai với khoa đang chờ nốt 75%". Suy giai đoạn từ cờ milestone sẽ thu gọn khối truy vết ngay khi vừa giao đợt đầu.

- [ ] **Step 1: Viết test đỏ**

Tạo `miyano_portal/tests/test_chi_tiet_gop.py`:

```python
"""Màn chi tiết GỘP (03/09/2026) — hai nửa của MỘT yêu cầu trên một màn.

Trước bản này, chi tiết một yêu cầu nằm ở HAI màn: `DeXuatDetail.vue`
(`/yeu-cau/phieu/:ten`) và `OrderDetail.vue` (`/yeu-cau/don/:name`). Khoa
xin 100, quản lý duyệt 40, Miyano giao 25 — ba con số của MỘT việc, ở hai
trang, nối với nhau bằng một cái link.

Hai bổ sung backend ở đây là thứ làm màn gộp CHẠY ĐƯỢC:
  * `portal_order_track` trả `de_xuat` — vào bằng đường ĐƠN thì phải tìm
    ngược ra phiếu, mà `Sales Order.name` KHÔNG suy ra `Portal De Xuat
    Mua.name` (hai naming khác nhau);
  * `de_xuat_chi_tiet` trả giá/đã giao THEO DÒNG — bảng mặt hàng gộp làm
    một, và phép nối phiếu↔đơn phải làm ở SERVER: `frontend/` không có hạ
    tầng test nào (package.json chỉ có `build`), nên một hàm nối viết bằng
    JS là một hàm không ai canh.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat, portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _don_phieu_cu():
	"""Dọn Sales Order test TRƯỚC khi dọn phiếu, và hạ phiếu cũ về Nháp
	TRƯỚC KHI `dung_fixture()` force-delete (`on_trash` chặn xoá phiếu đã
	gửi duyệt). Cùng khuôn `test_yeu_cau_list.py::_don_phieu_cu`."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"]},
		fields=["name", "docstatus"],
	):
		if r.docstatus == 1:
			frappe.get_doc("Sales Order", r.name).cancel()
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


class TestChiTietGopBackend(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item
		self.quan_ly = self._thanh_vien("dxgop.ql@demo.miyano", "Quản lý", None)
		self.nhan_vien = self._thanh_vien(
			"dxgop.nv@demo.miyano", "Nhân viên khoa", self.khoa_a
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email, vai_tro, khoa_phong):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		gia_tri = {
			"customer": self.kh_a, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		contact = frappe.db.get_value("Contact", {"user": email})
		if contact and not frappe.db.exists("Dynamic Link", {
			"parent": contact, "parenttype": "Contact",
			"link_doctype": "Customer", "link_name": self.kh_a,
		}):
			c = frappe.get_doc("Contact", contact)
			c.append("links", {"link_doctype": "Customer", "link_name": self.kh_a})
			c.save(ignore_permissions=True)
		return email

	def _phieu_da_duyet(self, so_luong=10):
		"""Phiếu đi qua ĐƯỜNG DUYỆT THẬT (`de_xuat_duyet.duyet_va_tao_don`),
		KHÔNG gán tay `phieu.sales_order` — gán tay là ghim một trạng thái
		rồi đo lại chính nó, đúng kiểu fixture-che-cổng dự án đã dính bảy
		lần (xem docstring `test_yeu_cau_list.py`)."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "Hết găng tay cỡ M",
			"items": [{"item_code": self.item, "so_luong_de_xuat": so_luong}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		doc.gui_duyet()
		from miyano_portal import de_xuat_duyet
		de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		doc.reload()
		return doc

	def test_order_track_tra_ten_phieu_dung_sau_don(self):
		"""Vào màn bằng đường ĐƠN thì phải tìm ngược ra phiếu — `Sales
		Order.name` không suy ra được `Portal De Xuat Mua.name`."""
		phieu = self._phieu_da_duyet()
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(kq["de_xuat"], phieu.name)

	def test_order_track_tra_phan_tram_da_giao(self):
		"""Giai đoạn "Đã giao" đòi `per_delivered >= 100` (Ruling P42) —
		`milestones[delivering].done` KHÔNG thay được: cờ đó là `> 0`, giao
		một thùng cũng bật. Màn gộp dùng giai đoạn này để quyết định thu gọn
		khối "Yêu cầu & duyệt", nên suy sai là thu gọn quá sớm."""
		phieu = self._phieu_da_duyet()
		frappe.db.set_value(
			"Sales Order", phieu.sales_order, "per_delivered", 40,
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(float(kq["per_delivered"]), 40.0)

	def test_order_track_don_khong_co_phieu_tra_chuoi_rong(self):
		"""~102 đơn cũ có TRƯỚC luồng duyệt không có phiếu nào đứng sau.
		Trả `""` (không phải thiếu khoá): màn gộp đọc khoá này để quyết
		định có nạp nửa phiếu hay không, và một khoá vắng mặt buộc client
		phải đoán."""
		so = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
			"items": [{
				"item_code": self.item, "qty": 1, "rate": 1000,
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
			}],
		}).insert(ignore_permissions=True)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=so.name)
		self.assertEqual(kq["de_xuat"], "")
```

- [ ] **Step 2: Chạy test, xác nhận nó ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
```

Kỳ vọng: FAIL — `KeyError: 'de_xuat'` ở hai bài, `KeyError: 'per_delivered'` ở bài thứ ba.

- [ ] **Step 3: Thêm hai khoá vào payload**

Trong `miyano_portal/api/portal.py`, hàm `portal_order_track`, ngay dưới dòng `"ma_tra_cuu": so.get("custom_ma_tra_cuu") or "",` thêm:

```python
        # 03/09/2026 (màn chi tiết GỘP) — phiếu đề xuất đứng sau đơn này.
        # Vào màn bằng đường `/yeu-cau/don/<name>` (link trong mọi thông báo
        # đã gửi đi, xem `_link_chung_tu`) thì đây là đường DUY NHẤT tìm
        # ngược ra phiếu: `Sales Order.name` và `Portal De Xuat Mua.name`
        # là hai naming khác nhau, không suy ra nhau được.
        #
        # `""` (không phải thiếu khoá) cho ~102 đơn cũ có TRƯỚC luồng duyệt:
        # màn gộp đọc khoá này để quyết định có nạp nửa phiếu hay không, và
        # một khoá vắng mặt buộc client phải đoán.
        "de_xuat": so.get("custom_de_xuat") or "",
        # Ruling P42 — giai đoạn "Đã giao" đòi `>= 100`, KHÔNG phải `> 0`.
        # Payload đã có `milestones[delivering].done` nhưng cờ đó là `> 0`
        # (giao một thùng cũng bật), nên nó KHÔNG thay được con số này. Màn
        # gộp đọc `per_delivered` để suy giai đoạn — cùng luật với
        # `_sql_giai_doan()` mà danh sách đang dùng, không phải một luật
        # thứ hai viết riêng cho màn chi tiết.
        "per_delivered": float(so.per_delivered or 0),
```

- [ ] **Step 4: Chạy lại, xác nhận XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
```

Kỳ vọng: `Ran 3 tests ... OK`.

- [ ] **Step 5: Khai phạm vi cho endpoint (không có endpoint mới, nhưng chạy lưới đếm ngược)**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_pham_vi_endpoint
```

Kỳ vọng: OK (task này không thêm endpoint, chỉ thêm khoá — lưới vẫn phải xanh).

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/api/portal.py miyano_portal/tests/test_chi_tiet_gop.py
git commit -m "feat(portal): portal_order_track tra ten phieu va per_delivered

Man chi tiet gop vao bang duong /yeu-cau/don/<name> can tim nguoc ra
phieu; hai naming khac nhau nen khong suy ra nhau duoc. per_delivered de
suy giai doan da_giao dung luat Ruling P42 (>= 100, khong phai > 0).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: `de_xuat_chi_tiet` trả giá và số đã giao theo từng dòng

**Files:**
- Modify: `miyano_portal/api/de_xuat.py:218-245` (khối dựng `qty_tren_don`, mốc ổn định: chú thích `# Ruling P51 — SỐ ĐANG CÓ TRÊN ĐƠN`)
- Test: `miyano_portal/tests/test_chi_tiet_gop.py`

**Interfaces:**
- Consumes: `TestChiTietGopBackend._phieu_da_duyet()` từ Task 1
- Produces: mỗi phần tử `de_xuat_chi_tiet(ten)["items"][i]` có thêm ba khoá — `don_gia_tren_don: float | None`, `thanh_tien_tren_don: float | None`, `da_giao_tren_don: float | None`. `None` = dòng không có mặt trên đơn (hoặc phiếu chưa có đơn). Task 7 (`BangMatHang.vue`) đọc đúng ba tên này.

- [ ] **Step 1: Viết test đỏ**

Thêm vào `miyano_portal/tests/test_chi_tiet_gop.py`, trong lớp `TestChiTietGopBackend`:

```python
	def test_chi_tiet_tra_gia_va_da_giao_theo_dong(self):
		"""Bảng mặt hàng của màn gộp là MỘT bảng: SL xin / SL duyệt (của
		phiếu) đứng cạnh Đơn giá / Đã giao (của đơn). Phép nối làm ở ĐÂY,
		không ở JS — `frontend/` không có test nào, và đây cũng là truy vấn
		`Sales Order Item` mà hàm này ĐÃ chạy sẵn cho `so_luong_tren_don`
		(Ruling P51), nên không tốn thêm một vòng hỏi CSDL nào."""
		phieu = self._phieu_da_duyet(so_luong=10)
		frappe.db.set_value(
			"Sales Order Item",
			{"parent": phieu.sales_order, "item_code": self.item},
			{"rate": 1500, "amount": 15000},
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=phieu.name)
		dong = next(d for d in kq["items"] if d["item_code"] == self.item)
		self.assertEqual(float(dong["don_gia_tren_don"]), 1500.0)
		self.assertEqual(float(dong["thanh_tien_tren_don"]), 15000.0)
		self.assertEqual(float(dong["da_giao_tren_don"]), 0.0)

	def test_chi_tiet_phieu_chua_co_don_tra_None_khong_phai_0(self):
		"""`0` và "chưa có đơn" là HAI ca khác nhau, đừng gộp — cùng lý do
		`so_luong_tren_don` đã trả `None` (Ruling P51). Một bảng in `0 ₫`
		cho phiếu Chờ duyệt là nói với khoa rằng hàng của họ giá 0."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "x",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		doc.gui_duyet()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=doc.name)
		dong = kq["items"][0]
		self.assertIsNone(dong["don_gia_tren_don"])
		self.assertIsNone(dong["thanh_tien_tren_don"])
		self.assertIsNone(dong["da_giao_tren_don"])
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
```

Kỳ vọng: FAIL — `KeyError: 'don_gia_tren_don'`.

- [ ] **Step 3: Mở rộng truy vấn sẵn có**

Trong `miyano_portal/api/de_xuat.py`, thay khối dựng `qty_tren_don` (hiện tại lấy `fields=["item_code", "qty"]`) bằng:

```python
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
	return kq
```

Xoá khối `qty_tren_don = {}` cũ và vòng `for row in dong:` cũ — khối trên thay cả hai. **Giữ nguyên** chú thích Ruling P51 dài phía trên (nó giải thích vì sao `so_luong_tren_don` tồn tại và không được thay `so_luong_duyet`).

- [ ] **Step 4: Chạy lại module + hai module đọc `so_luong_tren_don`**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_de_xuat_sua_sau_duyet
```

Kỳ vọng: cả hai OK. Module thứ hai là lưới thật cho `so_luong_tren_don` — nó phải xanh nguyên vẹn, vì task này chỉ THÊM khoá.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/api/de_xuat.py miyano_portal/tests/test_chi_tiet_gop.py
git commit -m "feat(portal): de_xuat_chi_tiet tra don gia va so da giao theo dong

Bang mat hang cua man gop la MOT bang; phep noi phieu<->don lam o server
vi frontend khong co ha tang test. Dung dung truy van Sales Order Item
ham nay da chay san cho so_luong_tren_don.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Registry hành động của ĐƠN

**Files:**
- Create: `frontend/src/don-actions.js`
- Modify: `miyano_portal/tests/test_de_xuat_action_registry.py`

**Interfaces:**
- Consumes: không có
- Produces: `ACTIONS_DON` (mảng), `hanhDongDonChoPhep(don, me)` → mảng mục `{ method, label, variant, nhom: 'don', when, args? }`. Task 7 nối kết quả này với `hanhDongChoPhep(phieu, me)` của `de-xuat-actions.js`.

- [ ] **Step 1: Viết registry**

Tạo `frontend/src/don-actions.js`:

```js
// Registry hành động cho ĐƠN HÀNG (Sales Order) trên màn chi tiết gộp.
//
// Anh em sinh đôi của `de-xuat-actions.js`, cùng hình dạng và cùng luật:
// hành động là DỮ LIỆU, hide-don't-disable, và ĐÂY KHÔNG PHẢI CHỐT AN NINH
// (server đã enforce; registry chỉ quyết định HIỆN GÌ).
//
// Vì sao FILE RIÊNG chứ không thêm vào `de-xuat-actions.js`: hai bộ gọi hai
// module endpoint khác nhau (`api.call` → `api/portal.py` ở đây, `api.
// callDeXuat` → `api/de_xuat.py` ở kia), và `tests/test_de_xuat_action_
// registry.py` đối chiếu tên endpoint với ĐÚNG một module cho mỗi file. Trộn
// hai họ tên vào một mảng làm lưới đó mất khả năng nói "tên này không tồn
// tại" — nó không biết phải hỏi module nào.
//
// `nhom: 'don'` để người gọi biết dùng `api.call`. Mục của
// `de-xuat-actions.js` không mang khoá này (mặc định là phiếu) — cố ý không
// đi sửa tám mục đã có và tám dòng test đang canh chúng.
//
// File CỐ Ý là JS thuần, không import Vue.

export const ACTIONS_DON = [
  // E6/F-07 — "Chờ bạn đồng ý" là một trạng thái của CHÍNH Sales Order
  // (`workflow_state`), lộ ra qua `portal_order_track().chap_nhan`. Server
  // tự tính `can_dong_y` (đã trừ báo giá hết hạn) — client KHÔNG suy lại.
  { method: 'portal_order_accept', label: '✔ Đồng ý đặt hàng', variant: 'success',
    nhom: 'don', args: [{ key: 'action', const: 'dong_y' }],
    when: (d) => !!d.chap_nhan?.can_dong_y },

  { method: 'portal_order_accept', label: '✕ Không đồng ý…', variant: 'secondary',
    nhom: 'don', khoa: 'khong_dong_y',
    args: [
      { key: 'action', const: 'khong_dong_y' },
      { key: 'ly_do', label: 'Lý do không đồng ý báo giá', type: 'textarea', required: true },
    ],
    when: (d) => !!d.chap_nhan?.can_dong_y },

  // Việc 2/brief 2026-08-15 — huỷ THẬT (đơn đóng ngay), khác
  // `portal_request_cancel` bên dưới. Server đòi lý do >= 10 ký tự
  // (`LY_DO_TOI_THIEU_KHACH`) — nói ra ở đây để hộp thoại đòi đúng bằng đó.
  { method: 'portal_order_huy', label: '🗑 Huỷ đơn…', variant: 'danger',
    nhom: 'don',
    args: [{ key: 'ly_do', label: 'Lý do huỷ đơn (≥ 10 ký tự)', type: 'textarea', required: true, minLen: 10 }],
    when: (d) => !!d.chap_nhan?.can_dong_y },

  // Task 6 (QĐ-G2b) + Task 7 (Ruling P49) — CHỐT, không phải nhãn. Soi
  // gương hai điều kiện của `portal.portal_order_sua_so_luong`: loại đơn đi
  // vòng báo giá, và guard vai trò `dam_bao_duoc_sua_don_da_duyet` mà server
  // TỰ TRẢ LỜI qua `duoc_sua_da_duyet` — KHÔNG suy lại từ dữ kiện client.
  //
  // `!== false` chứ không `=== true`, CÓ CHỦ Ý: khoá vắng mặt chỉ có thể do
  // backend cũ hơn bundle, và `=== true` khi đó giấu chức năng khỏi CẢ quản
  // lý. Server không bao giờ mất quyền nói không.
  { method: 'portal_order_sua_so_luong', label: '✎ Gửi lại để báo giá', variant: 'secondary',
    nhom: 'don', dacBiet: 'sua_so_luong',
    when: (d) => !!d.chap_nhan?.can_dong_y
      && d.loai_don === 'Mua lẻ'
      && d.duoc_sua_da_duyet !== false },

  // Đơn ĐÃ XÁC NHẬN — chỉ GHI một yêu cầu chờ nhân viên Miyano xử lý, không
  // đóng đơn. Ẩn khi đang "Chờ bạn đồng ý": ở đó đã có đường "Không đồng ý"
  // riêng, hai bộ hành động cùng hiện sẽ tranh nhau.
  { method: 'portal_request_cancel', label: 'Huỷ / Sửa đơn', variant: 'secondary',
    nhom: 'don',
    args: [{ key: 'reason', label: 'Lý do yêu cầu huỷ / sửa đơn', type: 'textarea', required: true }],
    when: (d) => d.status_vi === 'Chờ xác nhận' && !d.chap_nhan?.can_dong_y },
]

// Lọc theo doc + người dùng. Bọc `when()` trong try/catch vì đúng lý do
// `de-xuat-actions.js` đã ghi: một field thiếu phải làm nút BIẾN MẤT, không
// làm sập cả thanh công cụ — nhưng phải để lại dấu vết ở console, không nuốt
// im lặng.
export function hanhDongDonChoPhep(don, me) {
  if (!don || !me) return []
  return ACTIONS_DON.filter((a) => {
    try {
      return a.when(don, me)
    } catch (e) {
      console.warn(`[don-actions] when() của "${a.label}" ném lỗi — ẩn nút này:`, e)
      return false
    }
  })
}
```

- [ ] **Step 2: Viết lưới canh tên endpoint (đỏ trước)**

**Ruling preflight #3:** ba bài dưới đây viết **thêm vào lớp `TestDeXuatActionRegistry` sẵn có** (không dựng lớp mới). Lớp đó đã có `_endpoint_that_portal()` ở dòng 169 và `_METHOD_RE` ở module — dựng lớp `TestRegistryDon` riêng buộc phải CHÉP LẠI helper đó, đúng thứ rubric review coi là lỗi; còn nâng helper lên module-level là churn lên một lưới đang chạy tốt.

Thêm vào `miyano_portal/tests/test_de_xuat_action_registry.py`, trong lớp `TestDeXuatActionRegistry`, sau `test_luoi_api_call_bat_duoc_ten_bia`:

```python
# 03/09/2026 (màn chi tiết GỘP) — registry THỨ HAI, cho hành động của Sales
# Order. Lưới cũ đối chiếu `de-xuat-actions.js` với `api/de_xuat.py`; file
# mới phải đối chiếu với `api/portal.py`. Không mở rộng lưới cũ để nó quét
# cả hai: khi đó nó mất khả năng nói "tên này không tồn tại" — một tên sai
# trong file này sẽ được coi là hợp lệ chỉ vì file kia có một tên trùng.
	# -- 03/09/2026, màn chi tiết GỘP: registry THỨ HAI -----------------------

	def _methods_registry_don(self) -> set[str]:
		return set(_METHOD_RE.findall(REGISTRY_DON.read_text(encoding="utf-8")))

	def test_file_registry_don_ton_tai(self):
		self.assertTrue(REGISTRY_DON.exists(), f"Không thấy {REGISTRY_DON}")

	def test_registry_don_khong_rong(self):
		"""Vế dương — thiếu nó thì một registry rỗng cũng qua bài."""
		self.assertGreaterEqual(len(self._methods_registry_don()), 4)

	def test_moi_method_cua_registry_don_la_endpoint_that_cua_portal(self):
		"""Đối chiếu với `api/portal.py`, KHÔNG phải `api/de_xuat.py`. Đó
		là lý do đây là file registry thứ hai chứ không phải thêm mục vào
		file cũ: trộn hai họ tên vào một mảng làm lưới mất khả năng nói
		'tên này không tồn tại' — nó không biết phải hỏi module nào."""
		thua = self._methods_registry_don() - self._endpoint_that_portal()
		self.assertEqual(
			thua, set(),
			f"don-actions.js khai method KHÔNG tồn tại (whitelist) ở "
			f"api/portal.py: {thua}. Đây là nút sẽ 404 lúc người dùng bấm.",
		)

	def test_moi_muc_registry_don_deu_mang_nhom_don(self):
		"""Màn gộp nối HAI registry rồi mới render; `nhom: 'don'` là thứ
		DUY NHẤT cho nó biết gọi `api.call` thay vì `api.callDeXuat`. Một
		mục quên khoá này sẽ được gọi sai module và 404 lúc bấm."""
		noi_dung = REGISTRY_DON.read_text(encoding="utf-8")
		so_muc = len(_METHOD_RE.findall(noi_dung))
		so_nhom = noi_dung.count("nhom: 'don'")
		self.assertEqual(
			so_nhom, so_muc,
			f"{so_muc} mục nhưng chỉ {so_nhom} mục khai `nhom: 'don'`.",
		)
```

và thêm hằng `REGISTRY_DON = FRONTEND_SRC / "don-actions.js"` ở module-level, cạnh `REGISTRY` đã có.

- [ ] **Step 3: Chạy lưới, xác nhận XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_de_xuat_action_registry
```

Kỳ vọng: OK. (Registry viết ở Step 1 nên lưới xanh ngay — bài này canh HỒI QUY, không phải TDD đỏ-trước; nếu nó đỏ thì có một tên endpoint gõ sai, sửa `don-actions.js`.)

- [ ] **Step 4: Chứng minh lưới THẬT SỰ bắt được tên sai**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal && \
  sed -i "s/method: 'portal_order_huy'/method: 'portal_order_huyyy'/" frontend/src/don-actions.js && \
  cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_de_xuat_action_registry 2>&1 | tail -5
```

Kỳ vọng: FAIL kèm `{'portal_order_huyyy'}`. Rồi hoàn nguyên:

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal && \
  sed -i "s/method: 'portal_order_huyyy'/method: 'portal_order_huy'/" frontend/src/don-actions.js && \
  cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_de_xuat_action_registry 2>&1 | tail -3
```

Kỳ vọng: OK.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/don-actions.js miyano_portal/tests/test_de_xuat_action_registry.py
git commit -m "feat(portal): registry hanh dong cua don hang

Anh em sinh doi cua de-xuat-actions.js, doi chieu voi api/portal.py.
Man chi tiet gop noi hai registry thanh mot thanh cong cu.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: Tách bốn khối của `OrderDetail.vue` thành component

Task này **không đổi hành vi gì** — nó là lưới an toàn cho Task 7. Sau task này `OrderDetail.vue` vẫn chạy y hệt, chỉ mỏng đi.

**Files:**
- Create: `frontend/src/components/chi-tiet/KhoiTienTrinh.vue`, `KhoiGiaoHang.vue`, `KhoiHoaDonTaiLieu.vue`, `KhoiBaoGia.vue`
- Modify: `frontend/src/views/OrderDetail.vue`

**Interfaces:**
- Consumes: không có
- Produces (props của từng component — Task 7 truyền đúng những tên này):
  - `KhoiTienTrinh`: `milestones: Array` → không emit gì
  - `KhoiBaoGia`: `don: Object`, `dangGui: Boolean` → emit `sua-so-luong(dong)` với `dong = { items: [{item_code, qty}], dat_ngoai: [{name, qty}] }`
  - `KhoiGiaoHang`: `don: Object` → không emit (tự gọi `portal_einvoice_nhap` khi bấm xem, giữ nguyên như hiện nay)
  - `KhoiHoaDonTaiLieu`: `don: Object`, `dangDatLai: Boolean` → emit `dat-lai()`

- [ ] **Step 1: Tách `KhoiTienTrinh.vue`**

Cắt khối template từ mốc `<!-- Tiến trình -->` (dòng 515) tới hết `</div>` đóng card (dòng 533), cùng `currentIdx`/`stepClass` trong `<script setup>`, sang file mới:

```vue
<script setup>
// Mốc tiến trình của đơn. Tách khỏi `OrderDetail.vue` 03/09/2026 để màn
// chi tiết GỘP dùng lại nguyên vẹn — không chép lần hai.
import { computed } from 'vue'
import { useIsMobile } from '../../useMobile'

const props = defineProps({ milestones: { type: Array, default: () => [] } })
const isMobile = useIsMobile()

// Bước hiện tại = mốc đầu tiên chưa hoàn thành (để tô cam như mockup).
const currentIdx = computed(() => props.milestones.findIndex((m) => !m.done))
function stepClass(m, idx) {
  if (m.done) return 'done'
  if (idx === currentIdx.value) return 'cur'
  return ''
}
</script>

<template>
  <div class="card mb10" style="margin-bottom: 14px">
    <div class="h3">Tiến trình</div>
    <!-- CHÉP NGUYÊN khối template cũ ở OrderDetail.vue dòng 517–532:
         nhánh desktop (`.tl`) và nhánh mobile (`.vlb`), đổi `data.milestones`
         thành `milestones`. Không sửa class, không sửa chữ. -->
  </div>
</template>
```

Thay chỗ cũ trong `OrderDetail.vue` bằng `<KhoiTienTrinh :milestones="data.milestones" />` và thêm import.

- [ ] **Step 2: Build và soi mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
```

Kỳ vọng: build xanh. Mở `/portal/yeu-cau`, bấm vào một đơn ĐÃ GIAO → khối "Tiến trình" hiện y như trước (5 mốc, mốc đang chạy tô cam), cả trên desktop lẫn khi thu hẹp cửa sổ < 900px.

- [ ] **Step 3: Tách `KhoiBaoGia.vue`**

Cắt khối từ mốc `<!-- E6/F-07 [MỚI — QĐ-6] — banner "Chờ bạn đồng ý" -->` (dòng 443–513), NHƯNG **để lại** ba nút hành động (Đồng ý / Không đồng ý / Huỷ đơn) — chúng chuyển sang registry ở Task 3 và sẽ được thanh hành động của Task 7 render. Component này giữ:
- banner hạn hiệu lực + câu giải thích;
- link tải báo giá PDF;
- khối ô nhập sửa số lượng (`soLuongMoiItems` / `soLuongMoiDatNgoai` / `initSoLuongMoi` / `moGuiLai` chuyển vào đây), phát ra sự kiện `sua-so-luong` thay vì tự gọi API.

Trong `OrderDetail.vue`, thay bằng:

```vue
<KhoiBaoGia
  v-if="data.chap_nhan && data.chap_nhan.can_dong_y"
  :don="data"
  :dang-gui="dangSuaSoLuong"
  @sua-so-luong="guiLaiBaoGia"
/>
```

và sửa `guiLaiBaoGia(dong)` nhận payload từ sự kiện thay vì đọc ref cục bộ.

- [ ] **Step 4: Build và soi mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
```

Kỳ vọng: build xanh. Mở một đơn đang "Chờ bạn đồng ý" (dựng bằng `bench --site erptest.local execute miyano_portal.setup.demo_kho_flow.chay_tat_ca` nếu site chưa có) → banner hạn báo giá hiện, sửa số lượng một dòng rồi bấm "Gửi lại để báo giá" → modal xác nhận → toast "Đã gửi số lượng mới…". **Nếu không dựng được ca này trên site, GHI RÕ trong báo cáo task là chưa soi mắt được, đừng bỏ qua im lặng.**

- [ ] **Step 5: Tách `KhoiGiaoHang.vue`**

Cắt từ mốc `<!-- Giao hàng -->` (dòng 636) tới ngay TRƯỚC `<!-- Khoảng trống 2026-08-16` (dòng 730). Mang theo: `dotLabel`, `pdfUrl`, `kiemHangBadge`, `KIEM_HANG_BADGE`, `toggleNhap`, `nhapMo`, `nhapData`, `nhapDangTai`, `urlPdfNhap`, và import `HoaDonNhap.vue`.

- [ ] **Step 6: Tách `KhoiHoaDonTaiLieu.vue`**

Cắt từ `<!-- Khoảng trống 2026-08-16` (dòng 730) tới hết `</div>` đóng card giao hàng. Mang theo `pdfUrl` (chép, không import chéo — bảy dòng, cùng lý do `KIEM_HANG_BADGE` đang được giữ hai bản). Nút "Đặt lại đơn này" phát `dat-lai`; nút "Huỷ / Sửa đơn" **bỏ khỏi đây** (đã vào registry Task 3).

- [ ] **Step 7: Build, chạy suite, soi mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal
```

Kỳ vọng: build xanh, suite 1758 test xanh. Soi mắt: mở một đơn đã giao → khối Giao hàng (đợt giao, kiểm hàng, hoá đơn nháp), khối Hoá đơn của đơn này, nút PDF và Đặt lại — tất cả y như trước.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/chi-tiet frontend/src/views/OrderDetail.vue miyano_portal/public/frontend
git commit -m "refactor(portal): tach bon khoi cua OrderDetail thanh component

Khong doi hanh vi. Chuan bi cho man chi tiet gop dung lai nguyen ven,
thay vi chep lan hai.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: Tách `KhoiTruyVet.vue` (có thu gọn)

**Files:**
- Create: `frontend/src/components/chi-tiet/KhoiTruyVet.vue`
- Modify: `frontend/src/views/DeXuatDetail.vue`

**Interfaces:**
- Consumes: không có
- Produces: `KhoiTruyVet` props `phieu: Object`, `moSan: Boolean` (mặc định `true`). Task 7 truyền `:mo-san="giaiDoan !== 'da_giao'"`.

- [ ] **Step 1: Viết component**

```vue
<script setup>
// Khối truy vết của phiếu đề xuất: ai xin, xin lúc nào, vì sao, ai duyệt.
// Tách khỏi `DeXuatDetail.vue` 03/09/2026 cho màn chi tiết GỘP.
//
// Bọc `<details>` vì trên màn gộp khối này KHÔNG phải lúc nào cũng là câu
// hỏi đang sống. Đơn đã giao xong thì thứ người ta mở trang để đọc là "hàng
// đâu, hoá đơn đâu"; con số duyệt là chuyện đã xong. Nhưng nó là dữ liệu
// ĐỐI CHIẾU khi có tranh cãi ("khoa xin 100, ai hạ xuống 40?"), nên THU
// GỌN, không giấu — một cú bấm là ra, và chữ trên nhãn nói sẵn nó chứa gì.
import { computed } from 'vue'
import { fmtDateTime } from '../../format'

const props = defineProps({
  phieu: { type: Object, required: true },
  moSan: { type: Boolean, default: true },
})

// Chủ đầu tư chốt 25/08 — hiện CẢ tên hiển thị LẪN tên tài khoản. Lý do đo
// được trên site: tài khoản cổng của bệnh viện đặt `User.full_name` bằng
// chính tên bệnh viện/khoa, nên chỉ hiện tên là khối truy vết mất sạch giá
// trị nhận dạng NGƯỜI. Chỉ ghép khi hai thứ KHÁC nhau (tài khoản đã xoá thì
// server lui về chính email, ghép nữa sẽ thành "a@b.com (a@b.com)").
const nguoiYeuCau = computed(() => {
  const d = props.phieu
  const taiKhoan = d.nguoi_yeu_cau || d.owner || ''
  const ten = d.nguoi_yeu_cau_ten || taiKhoan
  return { ten, taiKhoan: ten === taiKhoan ? '' : taiKhoan }
})
</script>

<template>
  <details class="card mb10" :open="moSan" style="margin-bottom: 14px">
    <summary style="cursor: pointer; font-weight: 600">
      Yêu cầu &amp; duyệt
      <span class="tag" style="font-weight: 400">
        — ai xin, xin lúc nào, ai duyệt
      </span>
    </summary>
    <!-- CHÉP NGUYÊN nội dung khối truy vết cũ ở DeXuatDetail.vue
         (đoạn "Người yêu cầu / Thời điểm gửi / Lý do yêu cầu / Người duyệt"),
         đổi `doc.` thành `phieu.`. Không sửa chữ, không sửa thứ tự dòng. -->
  </details>
</template>
```

- [ ] **Step 2: Dùng lại trong `DeXuatDetail.vue`**

Thay khối cũ bằng `<KhoiTruyVet :phieu="doc" />` (mở sẵn — màn cũ chưa biết giai đoạn, và nó sắp bị xoá ở Task 7).

- [ ] **Step 3: Build và soi mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
```

Kỳ vọng: build xanh; mở một phiếu Chờ duyệt → khối "Yêu cầu & duyệt" mở sẵn, nội dung y như trước, bấm vào nhãn thì thu lại được.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/chi-tiet/KhoiTruyVet.vue frontend/src/views/DeXuatDetail.vue miyano_portal/public/frontend
git commit -m "refactor(portal): tach khoi truy vet, boc details de thu gon duoc

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: `BangMatHang.vue` — một bảng, cột theo giai đoạn

**Files:**
- Create: `frontend/src/components/chi-tiet/BangMatHang.vue`

**Interfaces:**
- Consumes: `de_xuat_chi_tiet(...).items[]` (Task 2 đã thêm `don_gia_tren_don` / `thanh_tien_tren_don` / `da_giao_tren_don`), `portal_order_track(...).items[]`, `.dat_ngoai[]`
- Produces: props `phieu: Object | null`, `don: Object | null`, `quanLyDangDuyet: Boolean`, `slDuyetSua: Object`, `ghiChuSua: Object` (hai object dùng `v-model` một chiều — component ghi thẳng vào, cha đọc để dựng payload `dieu_chinh`, giữ nguyên cơ chế `DeXuatDetail.vue` đang chạy).

- [ ] **Step 1: Viết component**

```vue
<script setup>
// Bảng mặt hàng của màn chi tiết GỘP. MỘT bảng cho cả hai nửa của một yêu
// cầu — trước 03/09/2026 đây là hai bảng ở hai màn, và "khoa xin 100 /
// duyệt 40 / giao 25" là ba con số người dùng phải tự ghép bằng mắt qua
// hai lần điều hướng.
//
// NGUỒN DÒNG là PHIẾU khi có phiếu, không phải đơn. Phiếu là tập cha: nó
// giữ cả dòng quản lý đã hạ về 0 (bằng chứng "khoa đã xin gì" — §5.3 cấm
// xoá dòng, chỉ cho hạ về 0) lẫn dòng "Quản lý thêm". Lấy dòng từ đơn sẽ
// làm mất đúng những dòng đó, tức mất câu trả lời cho câu hỏi hệ thống này
// tồn tại để trả lời.
//
// Giá và số đã giao đi CÙNG dòng phiếu, do server nối
// (`de_xuat_chi_tiet`) — không nối ở đây: `frontend/` không có test nào,
// còn phía Python thì `tests/test_chi_tiet_gop.py` canh được.
import { computed } from 'vue'
import { fmtVND } from '../../format'

const props = defineProps({
  phieu: { type: Object, default: null },
  don: { type: Object, default: null },
  quanLyDangDuyet: { type: Boolean, default: false },
  slDuyetSua: { type: Object, default: () => ({}) },
  ghiChuSua: { type: Object, default: () => ({}) },
})

// Đơn cũ không có phiếu (~102 đơn trước luồng duyệt) — dòng lấy từ đơn, và
// hai cột của phiếu tự vắng mặt theo `coPhieu` bên dưới.
const dong = computed(() => {
  if (props.phieu) return props.phieu.items || []
  return (props.don?.items || []).map((it) => ({
    item_code: it.item_code,
    item_name: it.item_name,
    dvt: it.uom,
    so_luong_tren_don: it.qty,   // Ruling preflight #2 — nuôi cột "SL đặt"
    don_gia_tren_don: it.rate,
    thanh_tien_tren_don: it.amount,
    da_giao_tren_don: it.delivered_qty,
  }))
})

const coPhieu = computed(() => !!props.phieu)
const coDon = computed(() => !!props.don)
// "Đã đóng dấu duyệt" — `so_luong_duyet` chỉ mang nghĩa SAU khi phiếu rời
// Nháp (`_dong_dau_so_luong_duyet` chạy trong `gui_duyet`). Hiện cột đó
// trên một phiếu Nháp là in ra một bản sao vô nghĩa của cột đề xuất.
const coCotDuyet = computed(() => coPhieu.value && props.phieu.trang_thai !== 'Nháp')
const coCotXinSua = computed(() => props.phieu?.trang_thai === 'Chờ duyệt sửa')
// Cột "Đã giao" chỉ hiện khi CÓ đợt giao — một cột toàn số 0 trên đơn vừa
// duyệt là một cột chiếm chỗ mà không nói gì.
const coCotDaGiao = computed(
  () => coDon.value && (props.don.deliveries || []).length > 0
)

// M1 (Task 4) — "hạ về 0" chỉ có nghĩa SAU khi quản lý đã thật sự cầm phiếu
// lên xử lý. Ở "Nháp"/"Chờ duyệt", `so_luong_duyet` mới là bản sao mặc định
// của `so_luong_de_xuat`, coi nó là "Không duyệt" sẽ gắn badge sai cho MỌI
// dòng của MỌI phiếu chưa ai đụng tới.
const daDieuChinh = computed(
  () => ['Đã duyệt', 'Chờ duyệt sửa'].includes(props.phieu?.trang_thai)
)
function khongDuyet(row) {
  return daDieuChinh.value && Number(row.so_luong_duyet) === 0
}
</script>

<template>
  <div class="card" style="padding: 0; overflow-x: auto">
    <table>
      <thead>
        <tr>
          <th>Mặt hàng</th>
          <th>ĐVT</th>
          <th v-if="coPhieu" class="right">SL đề xuất</th>
          <th v-if="coCotDuyet" class="right">SL duyệt</th>
          <th v-if="coCotXinSua" class="right">SL xin sửa</th>
          <!-- Ruling preflight #2 — SỐ THẬT TRÊN ĐƠN, không phải `so_luong_
               duyet`. Hai con số này lệch nhau khi Miyano khớp một dòng gõ
               tay vào đơn (Ruling P51: `_gop_hoac_them_dong_hang` cộng
               thẳng vào `Sales Order Item.qty` mà không đụng cột duyệt).
               Với đơn cũ KHÔNG có phiếu, đây là cột số lượng DUY NHẤT —
               thiếu nó thì bảng in giá của một thứ không ai biết đặt bao
               nhiêu. -->
          <th v-if="coDon" class="right">SL đặt</th>
          <th v-if="coDon" class="right">Đơn giá</th>
          <th v-if="coDon" class="right">Thành tiền</th>
          <th v-if="coCotDaGiao" class="right">Đã giao</th>
          <th v-if="coPhieu">Ghi chú quản lý</th>
        </tr>
      </thead>
      <tbody>
        <!-- CHÉP các ô từ bảng cũ của DeXuatDetail.vue (gạch ngang + nhãn
             "Không duyệt" theo `khongDuyet(row)`, ô nhập SL duyệt và ô ghi
             chú khi `quanLyDangDuyet`) và thêm ba ô mới: đơn giá, thành
             tiền, đã giao — dùng `fmtVND` cho hai ô tiền.
             Ô tiền của dòng KHÔNG có trên đơn in "—", KHÔNG in "0 ₫". -->
      </tbody>
    </table>

    <!-- Dòng đặt ngoài: hàng khách gõ tay chưa có mã, sống trên ĐƠN chứ
         không trên phiếu. Bảng con RIÊNG, không gộp vào bảng trên — chúng
         là một loại dòng khác ("Miyano đang tìm nguồn"), nhét chung sẽ nói
         sai về chúng. Tách tiếp theo `da_xu_ly` như OrderDetail.vue đã
         làm (review I-4): dòng đã khớp mã KHÔNG được đọc như đang chờ. -->
  </div>
</template>
```

- [ ] **Step 2: Build (chưa ai dùng — chỉ kiểm cú pháp)**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
```

Kỳ vọng: build xanh (Vite bỏ qua component chưa import, nhưng lỗi cú pháp vẫn nổ khi Task 7 import — chạy lại ở đó).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/chi-tiet/BangMatHang.vue
git commit -m "feat(portal): bang mat hang gop, cot moc theo giai doan

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Màn gộp `ChiTietYeuCau.vue` và chuyển hai route sang nó

Task lớn nhất. Sau task này hai view cũ biến mất.

**Files:**
- Create: `frontend/src/views/ChiTietYeuCau.vue`
- Modify: `frontend/src/router.js`
- Delete: `frontend/src/views/OrderDetail.vue`, `frontend/src/views/DeXuatDetail.vue`
- Test: `miyano_portal/tests/test_chi_tiet_gop.py` (thêm lớp lưới regex)

> **Ruling preflight #1** — `tests/test_yeu_cau_list.py` đã GỠ khỏi danh sách này: chỉ Task 10 Step 1 thật sự sửa nó, và một file nằm trong hai task là hai người cùng sửa một chỗ.

**Interfaces:**
- Consumes: mọi thứ của Task 1–6
- Produces: route `order-detail` và `de-xuat-detail` cùng trỏ `ChiTietYeuCau`; không tên route nào mất đi (App.vue `isActive` và mọi `router.push` hiện có vẫn đúng).

- [ ] **Step 1: Viết lưới regex ĐỎ TRƯỚC**

Thêm vào `miyano_portal/tests/test_chi_tiet_gop.py`:

```python
class TestManGopTrenRouter(FrappeTestCase):
	"""Đọc `router.js`/thư mục `views` bằng regex — cùng lý do và cùng tiền
	lệ `test_yeu_cau_list.py::TestDuongCuVaSoCua`: frontend không có hạ tầng
	test, và "hai đường trỏ về một màn" không có bước build nào bắt được."""

	FRONTEND_SRC = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"

	def _router(self) -> str:
		return (self.FRONTEND_SRC / "router.js").read_text(encoding="utf-8")

	def test_hai_duong_cu_van_con_va_deu_tro_vao_man_gop(self):
		"""Hai đường này nằm trong bookmark của khách VÀ trong link của MỌI
		thông báo tự động đã gửi đi (`api/portal.py::_link_chung_tu`, chốt
		bởi `test_thong_bao_endpoint.py`). Kế hoạch gộp CỐ Ý không đổi
		đường — đổi là kéo theo một lớp tương thích mà không ai được lợi."""
		noi_dung = self._router()
		for path in ("/yeu-cau/don/:name", "/yeu-cau/phieu/:ten"):
			moc = re.search(
				r"\{[^{}]*path:\s*'" + re.escape(path) + r"'[^{}]*\}", noi_dung
			)
			self.assertIsNotNone(moc, f"router.js không còn khai báo {path}")
			self.assertIn(
				"ChiTietYeuCau", moc.group(0),
				f"{path} không trỏ vào màn gộp — hai cửa lại dẫn về hai phòng.",
			)

	def test_hai_man_cu_da_nghi(self):
		"""Còn file là còn đường một route lạc quay lại nửa màn cũ."""
		for ten in ("OrderDetail.vue", "DeXuatDetail.vue"):
			self.assertFalse(
				(self.FRONTEND_SRC / "views" / ten).exists(),
				f"{ten} phải nghỉ (gộp vào ChiTietYeuCau.vue)",
			)

	def test_man_gop_noi_CA_HAI_registry_hanh_dong(self):
		"""Thanh hành động là điểm được nhiều nhất của việc gộp: nhân viên
		khoa và quản lý có hai đường sửa số lượng khác nhau, trước đây nằm ở
		hai màn. Nối thiếu một registry là trả lại đúng cái hố đó."""
		man = (self.FRONTEND_SRC / "views" / "ChiTietYeuCau.vue").read_text(encoding="utf-8")
		self.assertIn("de-xuat-actions", man)
		self.assertIn("don-actions", man)
```

Thêm `import re` và `from pathlib import Path` vào đầu file test.

- [ ] **Step 2: Chạy, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
```

Kỳ vọng: FAIL cả ba bài mới (`ChiTietYeuCau` chưa tồn tại).

- [ ] **Step 3: Viết `ChiTietYeuCau.vue` — phần script**

```vue
<script setup>
// Chi tiết MỘT yêu cầu mua — cả hai nửa của nó, trên một màn.
//
// Thay `DeXuatDetail.vue` + `OrderDetail.vue` (03/09/2026, chủ đầu tư
// chốt). Trước bản này, bấm một dòng ở danh sách cho ra màn PHIẾU, rồi phải
// bấm tiếp một link để sang màn ĐƠN — "khoa xin 100 / duyệt 40 / giao 25"
// là ba con số của MỘT việc nằm ở HAI trang. Đó đúng là nghịch lý QĐ-G11 đã
// dỡ ở tầng danh sách và bỏ quên ở tầng chi tiết.
//
// HAI ĐƯỜNG, MỘT MÀN — cố ý không tạo route mới, không chuyển hướng:
// `Portal De Xuat Mua.name` và `Sales Order.name` là hai naming khác nhau,
// nên "một route nhận cả hai id" phải ĐOÁN loại chứng từ từ chuỗi id. Giữ
// hai đường thì mọi bookmark và mọi link trong thông báo ĐÃ GỬI ĐI
// (`/yeu-cau/don/<name>`, xem `api/portal.py::_link_chung_tu`) không phải
// đụng một dòng nào.
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, giaiDoanBadge, nhanGiaiDoan } from '../format'
import { store } from '../store'
import { showToast } from '../toast'
import { hanhDongChoPhep } from '../de-xuat-actions'
import { hanhDongDonChoPhep } from '../don-actions'
import { capNhatChoDuyetCount } from '../cho-duyet'
import ReasonModal from '../components/ReasonModal.vue'
import KhoiTruyVet from '../components/chi-tiet/KhoiTruyVet.vue'
import KhoiTienTrinh from '../components/chi-tiet/KhoiTienTrinh.vue'
import KhoiBaoGia from '../components/chi-tiet/KhoiBaoGia.vue'
import KhoiGiaoHang from '../components/chi-tiet/KhoiGiaoHang.vue'
import KhoiHoaDonTaiLieu from '../components/chi-tiet/KhoiHoaDonTaiLieu.vue'
import BangMatHang from '../components/chi-tiet/BangMatHang.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const phieu = ref(null)
const don = ref(null)

// Đầu mối = đường đã vào. `:ten` → phiếu, `:name` → đơn. Không đoán theo
// hình dạng chuỗi id.
const tenPhieuVao = computed(() => route.params.ten || '')
const tenDonVao = computed(() => route.params.name || '')

// Nạp cả hai nửa. Nửa THỨ HAI là best-effort: một yêu cầu vẫn phải đọc
// được khi nửa kia lỗi (hoặc không tồn tại) — thà thiếu một khối còn hơn
// trắng cả màn. Nhưng KHÔNG rơi im lặng: ghi console, cùng luật `App.vue`.
async function load() {
  loading.value = true
  error.value = ''
  phieu.value = null
  don.value = null
  try {
    if (tenPhieuVao.value) {
      phieu.value = await api.callDeXuat('de_xuat_chi_tiet', { ten: tenPhieuVao.value })
      if (phieu.value.sales_order) await napDon(phieu.value.sales_order)
    } else {
      don.value = await api.call('portal_order_track', { order: tenDonVao.value })
      if (don.value.de_xuat) await napPhieu(don.value.de_xuat)
    }
  } catch (e) {
    error.value = e.message || 'Không tải được chi tiết yêu cầu.'
  } finally {
    loading.value = false
  }
}
async function napDon(ten) {
  try {
    don.value = await api.call('portal_order_track', { order: ten })
  } catch (e) {
    console.warn('Không nạp được nửa ĐƠN của yêu cầu này:', e)
  }
}
async function napPhieu(ten) {
  try {
    phieu.value = await api.callDeXuat('de_xuat_chi_tiet', { ten })
  } catch (e) {
    // Ca tới được: nhân viên khoa A mở link đơn của khoa B qua một thông
    // báo định tuyến sai — `_phieu_cua_toi()` chặn đúng. Mất khối truy vết,
    // không mất cả màn.
    console.warn('Không nạp được nửa PHIẾU của yêu cầu này:', e)
  }
}

// Giai đoạn — MỘT badge, đúng bộ khoá của `_sql_giai_doan()` (api/portal.py)
// mà danh sách đang dùng. Suy ở client theo ĐÚNG thứ tự nhánh của server:
// trạng thái PHIẾU thắng trước (một phiếu "Chờ duyệt sửa" đã có đơn đứng
// sau, nhưng thứ nó đang CHỜ là quản lý, không phải Miyano).
const giaiDoan = computed(() => {
  const tt = phieu.value?.trang_thai
  if (tt === 'Nháp') return 'nhap'
  if (tt === 'Chờ duyệt' || tt === 'Chờ duyệt sửa') return 'cho_duyet'
  if (tt === 'Từ chối') return 'tu_choi'
  if (tt === 'Đã huỷ') return 'da_huy'
  const d = don.value
  if (!d) return 'da_duyet'
  if (d.docstatus === 2 || d.status_vi === 'Đã huỷ') return 'da_huy'
  if (d.status_vi === 'Từ chối') return 'tu_choi'
  // `>= 100`, KHÔNG phải `> 0` — Ruling P42. `per_delivered` do Task 1
  // thêm vào payload chính vì phép so này (cờ milestone `delivering` là
  // `> 0`, dùng nó sẽ thu gọn khối truy vết ngay khi vừa giao đợt đầu).
  if (Number(d.per_delivered || 0) >= 100) return 'da_giao'
  if (d.chap_nhan?.can_dong_y) return 'cho_khach_dong_y'
  return 'da_duyet'
})

// Thanh hành động GỘP. Đây là điểm được nhiều nhất của việc gộp: ở giai
// đoạn "Chờ quý vị đồng ý" có HAI đường sửa số lượng, chia theo VAI TRÒ —
// quản lý đi `portal_order_sua_so_luong`, nhân viên khoa đi
// `de_xuat_xin_sua` (phải qua duyệt lại). Trước bản này người dùng thấy
// đường nào là tuỳ họ tình cờ mở màn nào.
const hanhDong = computed(() => [
  ...hanhDongChoPhep(phieu.value, store.me),
  ...hanhDongDonChoPhep(don.value, store.me),
])

const quanLyDangDuyet = computed(
  () => phieu.value?.trang_thai === 'Chờ duyệt' && !!store.me?.la_quan_ly
)

// Nút "Quay lại" mang theo bộ lọc đang mở của danh sách (C3). Giữ nguyên cơ
// chế `?chip=` / `?khoa=` — người dùng vào thẳng bằng URL (link thông báo,
// tab ghim) không có bước lịch sử nào để `router.back()` lùi.
const quayLaiTo = computed(() => ({
  name: 'yeu-cau',
  query: {
    ...(route.query.chip ? { chip: String(route.query.chip) } : {}),
    ...(route.query.khoa ? { khoa: String(route.query.khoa) } : {}),
  },
}))

onMounted(async () => {
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      console.warn('Không nạp được hồ sơ phiên — thanh hành động sẽ rỗng:', e)
    }
  }
  await load()
})
</script>
```

**Ghi chú thi công (không phải placeholder — đây là hướng dẫn CHÉP):** phần còn lại của `<script setup>` — `slDuyetSua`, `ghiChuSua`, `dungLaiDieuChinh`, `soDuyetMoi`, `dieuChinhItems`, `nhanDuyet`, `chayHanhDong`, `argModalAction`, `xinSuaOpen` + toàn bộ luồng "Xin sửa số lượng", `datLai` — **chép nguyên** từ `DeXuatDetail.vue` và `OrderDetail.vue`, đổi `doc.` → `phieu.`, `data.` → `don.`. Trong `chayHanhDong`, chọn module theo `action.nhom`:

```js
const goi = action.nhom === 'don'
  ? (args) => api.call(action.method, args)
  : (args) => api.callDeXuat(action.method, { ten: phieu.value.name, ...args })
```

và đối số của nhóm `don` luôn có `order: don.value.order`.

- [ ] **Step 4: Viết `ChiTietYeuCau.vue` — phần template**

Theo đúng thứ tự khối của mục "Bố cục" ở đầu tài liệu:

```vue
<template>
  <div>
    <div class="topbar">
      <router-link :to="quayLaiTo"><button class="btn-o">← Quay lại</button></router-link>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else>
      <!-- 1. Đầu trang — MỘT mã, MỘT badge giai đoạn. Hai badge chồng nhau
           (loại đơn + trạng thái) là thứ màn cũ làm và là thứ khiến người
           đọc phải tự ghép hai từ điển trạng thái. -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="sb">
          <b style="font-size: 16px">{{ ma }}</b>
          <span class="badge" :class="giaiDoanBadge(giaiDoan)">{{ nhanGiaiDoan(giaiDoan) }}</span>
        </div>
        <!-- khoa phòng · ngày · tổng tiền · số dự trù · HĐNT -->
        <!-- lý do từ chối (đỏ) — của PHIẾU hoặc của ĐƠN, cái nào có -->
      </div>

      <!-- 2. Việc đang chờ bạn — banner + TOÀN BỘ nút, một chỗ duy nhất -->
      <div v-if="hanhDong.length || coTheSuaNhap" class="card mb10" style="margin-bottom: 14px">
        <div class="h3">Việc đang chờ bạn</div>
        <KhoiBaoGia v-if="don?.chap_nhan?.can_dong_y" :don="don" :dang-gui="dangSuaSoLuong" @sua-so-luong="guiLaiBaoGia" />
        <p v-if="quanLyDangDuyet" class="tag" style="margin-bottom: 10px">
          Bạn có thể <b>sửa số lượng duyệt</b> ở bảng bên dưới trước khi bấm Duyệt. Để trống một ô
          nghĩa là <b>giữ nguyên</b> dòng đó; gõ <b>0</b> nghĩa là <b>bỏ mặt hàng</b> khỏi đơn.
        </p>
        <div class="flex" style="flex-wrap: wrap">
          <!-- nút "Sửa nháp" (điều hướng, không qua registry) + v-for hanhDong -->
        </div>
      </div>

      <KhoiTienTrinh v-if="don" :milestones="don.milestones" />

      <KhoiTruyVet v-if="phieu" :phieu="phieu" :mo-san="giaiDoan !== 'da_giao'" />

      <div class="grid2">
        <BangMatHang
          :phieu="phieu" :don="don"
          :quan-ly-dang-duyet="quanLyDangDuyet"
          :sl-duyet-sua="slDuyetSua" :ghi-chu-sua="ghiChuSua"
        />
        <div>
          <KhoiGiaoHang v-if="don" :don="don" />
          <KhoiHoaDonTaiLieu v-if="don" :don="don" :dang-dat-lai="dangDatLai" @dat-lai="datLai" />
        </div>
      </div>

      <div v-if="phieu?.ghi_chu" class="card mb10" style="margin-top: 14px">
        <div class="h3">Ghi chú</div>
        <p style="font-size: 13px; white-space: pre-wrap">{{ phieu.ghi_chu }}</p>
      </div>
    </template>

    <!-- Ba ReasonModal (lý do yêu cầu / hành động có args / xin sửa số
         lượng) — chép nguyên từ hai màn cũ. -->
  </div>
</template>
```

`ma` = `phieu?.ma_de_xuat || don?.order || phieu?.name`.

- [ ] **Step 5: Đổi router**

Trong `frontend/src/router.js`:

```js
import ChiTietYeuCau from './views/ChiTietYeuCau.vue'
```

(bỏ hai import `OrderDetail`, `DeXuatDetail`) và:

```js
  // 03/09/2026 — HAI đường, MỘT màn. Chi tiết một yêu cầu là MỘT trang; hai
  // đường chỉ là hai ĐẦU MỐI khác nhau (docname phiếu / docname đơn) vì hai
  // doctype đặt tên khác nhau. Cố ý KHÔNG gộp thành một đường: đường đơn
  // nằm trong link của MỌI thông báo tự động đã gửi đi (`_link_chung_tu`).
  { path: '/yeu-cau/don/:name', name: 'order-detail', component: ChiTietYeuCau, meta: { title: 'Chi tiết đơn hàng' } },
  { path: '/yeu-cau/phieu/:ten', name: 'de-xuat-detail', component: ChiTietYeuCau, meta: { title: 'Chi tiết đơn hàng' } },
```

- [ ] **Step 6: Xoá hai màn cũ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal && \
  git rm frontend/src/views/OrderDetail.vue frontend/src/views/DeXuatDetail.vue
```

- [ ] **Step 7: Build và chạy lưới**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
```

Kỳ vọng: build xanh, lưới xanh.

- [ ] **Step 8: Soi mắt SÁU ca — bắt buộc, ghi kết quả từng ca vào báo cáo**

| # | Ca | Kỳ vọng |
|---|---|---|
| 1 | Phiếu **Nháp** (`/yeu-cau/phieu/<ten>`) | Đầu trang + nút "Sửa nháp"/"Gửi duyệt"/"Xoá" + bảng chỉ có SL đề xuất. KHÔNG có Tiến trình, KHÔNG có Giao hàng |
| 2 | Phiếu **Chờ duyệt**, đăng nhập bằng quản lý | Nút Duyệt/Từ chối/Huỷ; cột SL duyệt là ô NHẬP; sửa một ô rồi bấm Duyệt → hộp xác nhận liệt kê điều chỉnh → đơn sinh ra |
| 3 | Phiếu **Chờ duyệt**, đăng nhập bằng chủ phiếu | Nút "Thu hồi để sửa"; bảng chỉ đọc |
| 4 | Đơn **Chờ quý vị đồng ý** (`/yeu-cau/don/<name>`) | Banner hạn báo giá + nút Đồng ý/Không đồng ý/Huỷ đơn; khối "Yêu cầu & duyệt" MỞ SẴN; bảng có đủ SL xin/SL duyệt/Đơn giá |
| 5 | Đơn **đã giao 100%** | Khối "Yêu cầu & duyệt" THU GỌN; Tiến trình đủ 5 mốc; Giao hàng + Hoá đơn hiện; cột "Đã giao" có số |
| 6 | Đơn **cũ không có phiếu** (`SAL-ORD-…`) | Không có khối "Yêu cầu & duyệt"; bảng không có cột SL đề xuất/SL duyệt; mọi thứ còn lại như màn đơn cũ |

Nếu site chưa có ca 6, dựng bằng:
```bash
bench --site erptest.local console
# frappe.get_doc({"doctype":"Sales Order", ...}).insert()  — không gắn custom_de_xuat
```

- [ ] **Step 9: Chạy toàn bộ suite**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal
```

Kỳ vọng: 1758+ test xanh. `test_thong_bao_endpoint.py` phải xanh **không sửa gì** — đó là bằng chứng đường `/yeu-cau/don/<name>` còn nguyên.

- [ ] **Step 10: Commit**

```bash
git add -A frontend/src miyano_portal/tests/test_chi_tiet_gop.py miyano_portal/public/frontend
git commit -m "feat(portal): mot man chi tiet cho ca phieu va don

Hai duong /yeu-cau/phieu/:ten va /yeu-cau/don/:name cung tro vao
ChiTietYeuCau.vue. Khoi nao khong co du lieu thi khong hien, nen man gop
co lai dung bang mot trong hai man cu o hai dau dong doi.

Thanh hanh dong noi ca hai registry: nhan vien khoa va quan ly khong con
phai mo dung man moi thay duong sua so luong cua minh.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: Một dòng, một đích ở danh sách

**Files:**
- Modify: `frontend/src/views/YeuCauList.vue`
- Test: `miyano_portal/tests/test_chi_tiet_gop.py`

**Interfaces:**
- Consumes: màn gộp của Task 7
- Produces: không có

- [ ] **Step 1: Viết lưới đỏ**

Thêm vào `TestManGopTrenRouter`:

```python
	def test_danh_sach_khong_con_hai_cua_cho_mot_dong(self):
		"""Nút "Đơn hàng" ở cột cuối từng là LỐI VÀO THỨ HAI, dẫn tới nửa
		kia của cùng một yêu cầu. Từ khi hai nửa nằm chung một màn, nó là
		cửa thứ hai vào đúng một phòng — và một dòng có hai đích là đúng
		thứ QĐ-G11 dỡ ở tầng danh sách."""
		man = (self.FRONTEND_SRC / "views" / "YeuCauList.vue").read_text(encoding="utf-8")
		self.assertNotIn(
			"Đơn hàng</button>", man,
			"YeuCauList.vue còn nút 'Đơn hàng' — hai cửa cho một dòng.",
		)
```

- [ ] **Step 2: Chạy, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
```

- [ ] **Step 3: Bỏ nút và hàm `moDon`**

Trong `YeuCauList.vue`: xoá hai chỗ `<button v-if="r.sales_order" ... @click.stop="moDon(r)">Đơn hàng</button>` (bản desktop và bản mobile) và hàm `moDon`. Sửa chú thích của `moYeuCau` — bỏ câu "Nút 'Đơn hàng' riêng ở cột cuối…" và thay bằng:

```js
// 03/09/2026 — MỘT đích cho mọi dòng. Nút "Đơn hàng" riêng ở cột cuối đã
// bỏ cùng lúc hai màn chi tiết gộp làm một: nó từng là lối vào NỬA KIA của
// cùng một yêu cầu, nay là cửa thứ hai vào đúng một phòng.
```

- [ ] **Step 4: Build, chạy lưới, soi mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_chi_tiet_gop
```

Soi mắt: `/portal/yeu-cau` — mỗi dòng chỉ còn nút "Sửa" (với phiếu Nháp của mình); bấm bất kỳ dòng nào cũng ra màn gộp.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/YeuCauList.vue miyano_portal/tests/test_chi_tiet_gop.py miyano_portal/public/frontend
git commit -m "refactor(portal): mot dong mot dich o danh sach don hang

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Thông báo về phiếu cũng có nút đi tới chứng từ

Lỗ có sẵn, nay vá được vì đã có một màn chính tắc: quản lý nhận "Khoa vừa gửi đề xuất mua X chờ bạn duyệt" mà **không có link nào** — `_link_chung_tu` không xử lý `Portal De Xuat Mua`.

**Files:**
- Modify: `miyano_portal/api/portal.py::_link_chung_tu`
- Test: `miyano_portal/tests/test_thong_bao_endpoint.py`

**Interfaces:**
- Consumes: route `de-xuat-detail` của Task 7
- Produces: không có

- [ ] **Step 1: Viết test đỏ**

Thêm vào `miyano_portal/tests/test_thong_bao_endpoint.py`, cùng lớp với `test_link_...` sẵn có:

```python
    def test_link_thong_bao_phieu_de_xuat_tro_toi_man_chi_tiet(self):
        """Lỗ có TỪ Task 8 (§5.8): `bao_de_xuat_gui_duyet` gửi cho quản lý
        "Khoa vừa gửi đề xuất mua X chờ bạn duyệt" — và trang Thông báo ẩn
        nút đi tới chứng từ, vì `_link_chung_tu` không biết doctype này.
        Quản lý phải tự mở danh sách và tìm lại đúng phiếu bằng mắt.

        Vá được từ 03/09/2026 vì chi tiết một yêu cầu nay có MỘT màn chính
        tắc, không còn phải chọn giữa hai đường."""
        phieu = frappe.get_doc({
            "doctype": "Portal De Xuat Mua",
            "customer": CUSTOMER_BVBM, "khoa_phong": None,
            "items": [{"item_code": ITEM, "so_luong_de_xuat": 1}],
        }).insert(ignore_permissions=True)
        _tao_log(USER_BVBM, "Phiếu chờ duyệt", "Portal De Xuat Mua", phieu.name)
        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        row = next(i for i in res["items"] if i["subject"] == "Phiếu chờ duyệt")
        self.assertEqual(row["link"], f"/yeu-cau/phieu/{phieu.name}")

    def test_link_phieu_cua_khach_khac_bi_chan(self):
        """VẾ ÂM — cùng lớp kiểm thứ hai mà mọi nhánh khác của
        `_link_chung_tu` đều có: `for_user` đúng KHÔNG phải bằng chứng người
        đó đọc được chứng từ đang trỏ tới."""
        phieu = frappe.get_doc({
            "doctype": "Portal De Xuat Mua",
            "customer": "PXN ABC",
            "items": [{"item_code": ITEM, "so_luong_de_xuat": 1}],
        }).insert(ignore_permissions=True)
        _tao_log(USER_BVBM, "Phiếu khách khác", "Portal De Xuat Mua", phieu.name)
        frappe.set_user(USER_BVBM)
        res = portal_thong_bao_list()
        row = next(i for i in res["items"] if i["subject"] == "Phiếu khách khác")
        self.assertIsNone(row["link"])
```

(Dùng đúng hằng `CUSTOMER_BVBM` / `ITEM` / `_tao_log` / `USER_BVBM` mà file test đó đang có; nếu tên khác thì theo tên thật trong file.)

- [ ] **Step 2: Chạy, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_thong_bao_endpoint
```

Kỳ vọng: bài đầu FAIL (`None != '/yeu-cau/phieu/…'`), bài sau XANH sẵn (mặc định trả `None`) — giữ nó lại, nó là lưới chống hồi quy cho bản vá.

- [ ] **Step 3: Thêm nhánh**

Trong `_link_chung_tu`, ngay sau nhánh `Sales Order`:

```python
        if document_type == "Portal De Xuat Mua":
            if frappe.db.get_value("Portal De Xuat Mua", document_name, "customer") != customer:
                return None
            # 03/09/2026 — trước bản này doctype này KHÔNG có nhánh nào ở
            # đây, nên mọi thông báo §5.8 về phiếu (gửi duyệt / duyệt / từ
            # chối / xin sửa) hiện ra KHÔNG có nút đi tới chứng từ: quản lý
            # đọc "Khoa vừa gửi đề xuất mua X chờ bạn duyệt" rồi phải tự mở
            # danh sách và tìm lại X bằng mắt.
            #
            # Vá được ĐÚNG LÚC NÀY vì chi tiết một yêu cầu vừa có MỘT màn
            # chính tắc — trước đó, trỏ vào đường phiếu là bỏ nửa đơn, trỏ
            # vào đường đơn thì phiếu Chờ duyệt chưa có đơn nào để trỏ.
            return f"/yeu-cau/phieu/{document_name}"
```

- [ ] **Step 4: Chạy lại module**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests \
  --app miyano_portal --module miyano_portal.tests.test_thong_bao_endpoint
```

Kỳ vọng: OK.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/api/portal.py miyano_portal/tests/test_thong_bao_endpoint.py
git commit -m "fix(portal): thong bao ve phieu de xuat co nut di toi chung tu

Lo co tu Task 8: _link_chung_tu khong biet Portal De Xuat Mua nen quan ly
doc 'khoa vua gui de xuat X' ma khong co duong nao toi X.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Tài liệu và chốt cuối

**Files:**
- Modify: `docs/BAN-DO-CHUC-NANG.md`, `docs/HDSD-phan-quyen-khoa-phong.md`, `docs/HDSD-hai-vai-khach-hang-va-nhan-vien.md`
- Modify: `miyano_portal/tests/test_yeu_cau_list.py`

- [ ] **Step 1: Cập nhật `test_khong_con_man_danh_sach_cu`**

Bài này đang liệt kê ba màn đã nghỉ. `OrderDetail.vue`/`DeXuatDetail.vue` là màn CHI TIẾT, không phải danh sách — canh chúng ở `test_chi_tiet_gop.py::test_hai_man_cu_da_nghi` (Task 7), không nhét vào đây. Chỉ thêm một dòng chú thích trỏ sang:

```python
		# Hai màn CHI TIẾT cũ (`OrderDetail.vue`/`DeXuatDetail.vue`) cũng đã
		# nghỉ 03/09/2026, nhưng chúng được canh ở
		# `test_chi_tiet_gop.py::test_hai_man_cu_da_nghi` — bài này chỉ nói
		# về màn DANH SÁCH.
```

- [ ] **Step 2: `docs/BAN-DO-CHUC-NANG.md`**

Trong §2.3, dưới khung "Đảo lại — chủ đầu tư chốt 03/09/2026", thêm khung thứ hai:

```markdown
> **Gộp tiếp tầng CHI TIẾT — chủ đầu tư chốt 03/09/2026.** QĐ-G11 gộp *danh
> sách* nhưng để nguyên hai màn *chi tiết*: bấm một dòng ra màn phiếu, rồi
> phải bấm tiếp một link để sang màn đơn. "Khoa xin 100 / duyệt 40 / giao
> 25" là ba con số của MỘT việc, ở HAI trang. Nay là **một màn**
> (`ChiTietYeuCau.vue`), đọc theo dòng thời gian, khối nào không có dữ liệu
> thì không hiện — nên nó co lại đúng bằng một trong hai màn cũ ở hai đầu
> dòng đời. **Hai đường giữ nguyên** (`/yeu-cau/phieu/:ten`,
> `/yeu-cau/don/:name`) vì hai doctype đặt tên khác nhau và đường đơn nằm
> trong link của mọi thông báo đã gửi đi.
```

- [ ] **Step 3: `docs/HDSD-phan-quyen-khoa-phong.md`**

Bảng "Ba màn của luồng này" → **hai màn** (Đặt hàng, Danh sách đơn hàng) cộng một dòng "Chi tiết đơn hàng" mô tả các khối. Mục "Quản lý sửa số lượng rồi duyệt" giữ nguyên các bước, chỉ đổi câu mở: bảng SL duyệt nay nằm trên cùng màn với tiến trình và giao hàng.

- [ ] **Step 4: `docs/HDSD-hai-vai-khach-hang-va-nhan-vien.md`**

Thêm một đoạn ngắn ở A5 nói: bấm vào một đơn là thấy **tất cả** — ai xin, ai duyệt, giá, tiến trình giao, hoá đơn; khối "Yêu cầu & duyệt" tự thu gọn khi đơn đã giao xong, bấm vào nhãn để mở lại.

- [ ] **Step 5: Chạy toàn bộ suite + build lần cuối**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal
```

Kỳ vọng: build xanh, suite xanh.

- [ ] **Step 6: Commit**

```bash
git add docs miyano_portal/tests/test_yeu_cau_list.py miyano_portal/public/frontend
git commit -m "docs(portal): mot man chi tiet cho ca phieu va don

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Rủi ro đã biết

1. **Task 7 là task lớn nhất** (một màn ~500 dòng ghép từ hai màn ~1500 dòng). Task 4–6 tồn tại để thu nhỏ nó; nếu vẫn thấy quá lớn khi bắt tay, **dừng lại và tách đôi** (7a: khung + đầu trang + thanh hành động, dùng tạm bảng của phiếu; 7b: `BangMatHang` + hai khối đơn) — đừng cố làm một lượt.
2. **Không có test JS.** Mọi bất biến frontend chỉ được canh bằng regex và bằng SÁU ca soi mắt ở Task 7 Step 8. Ca nào không dựng được trên site thì **ghi ra**, đừng bỏ qua im lặng.
3. **`giaiDoan` suy ở client** (Task 7) là bản sao THỨ HAI của `_sql_giai_doan()`. Hai bản sẽ trôi khỏi nhau. Nếu muốn triệt để, một task sau này cho `portal_order_track` và `de_xuat_chi_tiet` trả thẳng `giai_doan` — nhưng đó là việc riêng, không nhét vào kế hoạch này.
4. **`dat_ngoai`** chỉ sống trên đơn. Bảng con giữ nguyên; đừng cố nhét vào bảng chính.
