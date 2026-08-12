# Sổ theo dõi khắc phục BA v2 — sửa cái gì, sửa thành gì

> **File này là nguồn sự thật duy nhất về trạng thái khắc phục.** Trước khi sửa bất kỳ
> mã `NG-xx` / `UX-xx` / `API-xx` nào, **đọc file này trước** để biết chỗ đó đã bị ai
> động vào chưa và động thành gì. Sau khi sửa xong, **ghi vào đây trong cùng commit**.
>
> Lý do tồn tại: 47 luồng ngoại lệ chạm vào cùng một nhúm hàm (`portal_order_place`,
> `portal_catalog`, `remaining_qty`, `delivery_hook`). Hai người sửa hai mã số khác nhau
> rất dễ đè lên nhau. Bảng dưới đây cho biết **hàm nào đã đổi hình dạng** trước khi
> ai đó mở nó ra lần nữa.

**Tài liệu nguồn:** [`BA-v2-ngoai-le-va-UX-miyano_portal.md`](BA-v2-ngoai-le-va-UX-miyano_portal.md)
**Lộ trình:** [`superpowers/plans/2026-08-12-BA-v2-lo-trinh-khac-phuc.md`](superpowers/plans/2026-08-12-BA-v2-lo-trinh-khac-phuc.md)

---

## 0. Cách ghi

Mỗi mục đã sửa ghi **năm dòng**, không hơn:

```
### NG-xx · <tên ngắn> — <ngày> · commit <sha ngắn>
**Trước:** <hành vi cũ, một câu>
**Sau:** <hành vi mới, một câu>
**Đụng vào:** <file:dòng hoặc file:hàm — liệt kê hết, kể cả file JSON và patch>
**Phá vỡ:** <ai/cái gì phải đổi theo — API, frontend, dữ liệu. Ghi "không" nếu không>
**Test:** <đường dẫn module test chứng minh>
```

Nếu một task đụng vào một hàm mà **task khác cũng sẽ đụng**, ghi thêm dòng:
`**Cảnh báo chồng lấn:** <mã số khác> cũng sẽ sửa hàm này — <điều cần biết>`

---

## 1. Trạng thái hiện tại

| | |
|---|---|
| Nhánh | `develop` |
| Điểm gốc (chưa sửa gì) | `0ba68b4` — *docs(portal): bộ tài liệu BA và sơ đồ quy trình cho cổng khách hàng* |
| Đợt đang chạy | **Đợt 1 — Chặn máu (P0)**, chưa bắt đầu |
| Cập nhật lần cuối | 2026-08-12 |

### Bảng tiến độ

Trạng thái: ⬜ chưa làm · 🟨 đang làm · ✅ xong · ⏸️ hoãn

| Đợt | Mã | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | NG-37 rò rỉ sổ hoá đơn | ⬜ | Phạm vi rộng hơn BA v2: phải bọc **cả** `search_widget`, không chỉ `search_link` |
| 1 | NG-12 precision tiền | ⬜ | 10 trường / **6** doctype (BA v2 ghi 8 — xem đính chính ở lộ trình §2) |
| 1 | NG-10 giá không lọc ngày | ⬜ | |
| 1 | NG-11 giá lấy tuỳ ý | ⬜ | Phải làm cùng NG-10, cùng một hàm |
| 1 | NG-09 VAT | ⬜ | QĐ-02 = **A** (có VAT, mẫu thuế theo khách hàng) |
| 1 | NG-08 báo giá chốt | ⬜ | Phụ thuộc NG-09, NG-10, NG-11 |
| 1 | NG-02 hợp đồng nháp | ⬜ | |
| 1 | NG-03 hợp đồng chưa hiệu lực | ⬜ | |
| 1 | NG-04 hợp đồng hết hạn giữa chừng | ⬜ | |
| 1 | NG-05 mặt hàng bị gỡ khỏi hợp đồng | ⬜ | |
| 1 | NG-01 hạn mức đơn nháp | ⬜ | QĐ-01 = **A** (giữ chỗ mềm, 3 ngày làm việc) |
| 1 | NG-31 huỷ phiếu giao không đảo được | ⬜ | Ba lớp: ToDo · cờ trên phiếu · báo cáo đối soát (API-08) |
| 1 | Giao diện: giỏ hàng + danh mục | ⬜ | Task 11 — bỏ phép tính VAT phía trình duyệt |
| 1 | UX-08 (khung + 3 mã) | ⬜ | Task 12 — bảng đầy đủ `MYN-E101…E107` để đợt 2 |
| 2–5 | *(xem lộ trình)* | ⬜ | |

**Thứ tự thi công đợt 1.** Task 1 và 2 độc lập, làm song song và ship riêng được. Từ
Task 3 là một chuỗi phụ thuộc trên cùng vài hàm — đảo thứ tự sẽ phải sửa lại thứ vừa viết:

```
T1 NG-37 ─┐ độc lập          T10 NG-31 ─ độc lập
T2 NG-12 ─┘                  T11 giao diện · T12 bản đồ lỗi

T3 NG-10/11 → T4 NG-09 → T5 NG-08(API-03) → T6 NG-08(API-04)
   → T7 NG-02…05 → T8 NG-01 (đọc) → T9 NG-01 (nhả chỗ)
```

---

## 2. Quyết định đã chốt — KHÔNG mở lại nếu chưa bàn

| Mã | Chốt ngày | Phương án | Ràng buộc kéo theo |
|---|---|---|---|
| **QĐ-01** | 2026-08-12 | **A** — giữ chỗ mềm, hết hạn **3 ngày làm việc** | Không sửa `blanket_order.py` của ERPNext. Hạn mức "thật" tính ở tầng cổng. |
| **QĐ-02** | 2026-08-12 | **A** — có VAT, `Sales Taxes and Charges Template` theo Customer | Dữ liệu 0/7 hoá đơn không thuế trên `erptest.local` là **dữ liệu thử**, không phải chủ ý nghiệp vụ. Cổng đang báo tổng tiền **thấp hơn** số phải trả. |
| **QĐ-03** | 2026-08-12 | **B** — lô chưa khai HSD nhóm riêng cuối báo cáo | Không loại khỏi báo cáo. Không bắt buộc nhập HSD khi ghi sổ. |
| **QĐ-04** | 2026-08-12 | **A** — giữ một tầng duyệt | Vẫn còn bước Miyano xác nhận → khoảng đơn nháp vẫn tồn tại → QĐ-01 A là cần thiết. Loại QĐ-01 B khỏi bàn. |

---

## 3. Các điểm chồng lấn đã biết — đọc trước khi mở file

Bốn chỗ này bị nhiều mã số cùng chạm. Ghi ra để người sau không sửa lại thứ vừa đổi hình dạng.

| Vị trí | Các mã cùng chạm | Thứ tự bắt buộc |
|---|---|---|
| `api/portal.py::portal_catalog` | NG-02, NG-03, NG-05, NG-09, NG-10, NG-11, NG-01, API-01 | NG-10/11 (hàm đọc giá) → NG-09 (thuế) → NG-02/03/05 (lọc) → NG-01 (cột giữ chỗ) → API-01 (đổi hình dạng trả về) |
| `api/portal.py::portal_order_place` | NG-01, NG-04, NG-08, NG-09, NG-10, NG-11, API-04 | NG-10/11 → NG-09 → NG-08/API-04 (nhận mã chốt) → NG-04 (kiểm ngày) → NG-01 (kiểm hạn mức thật) |
| `portal_context.py::remaining_qty` | NG-01, NG-05, NG-06 | NG-05 (tách "hết hạn mức" khỏi "không có trong hợp đồng") → NG-01 (trừ phần giữ chỗ) → NG-06 (quy đổi đơn vị, đợt 2) |
| `kho/delivery_hook.py::_chay_an_toan` | NG-31, NG-32 | NG-31 (báo động ba lớp). NG-32 **đang đúng** — ghi vào đây để không ai "sửa" chỗ đang đúng. |

**Ranh giới triển khai của đợt 1.** Task 3→11 là **một** đơn vị lên site: Task 6 làm
`quote` thành bắt buộc trên `portal_order_place`, Task 11 mới dạy giao diện gửi nó.
Giữa hai commit ấy **không khách nào đặt hàng được**. Chỉ `bench migrate` + restart trên
site thật khi cả chín task xong và bundle đã build. Task 1 · 2 · 10 · 12 lên riêng được.

**Ba chỗ tuyệt đối không đụng** (BA v2 đã kết luận là đang đúng):

- `kho/delivery_hook.py:245-255` `_phieu_dang_song()` khoá theo từng phiếu giao — **đúng**, đừng gộp.
- `kho/delivery_hook.py:225-230` xoá phiếu nháp mồ côi — **đúng** (NG-32), chỉ còn thiếu thông báo.
- `Customer Stock Ledger Entry` / `Customer Stock Lot Balance` **cố ý không** bật `track_changes` — đừng bật (BA v2 §NG-21).

---

## 4. Nhật ký thay đổi

*(Chưa có mục nào. Mục đầu tiên sẽ được ghi khi Task 1 của đợt 1 hoàn thành.)*
