# Kết quả kiểm thử hệ thống — đối chiếu ma trận nghiệm thu

Ngày: 2026-08-14 · Nhánh `feature/e7-hddt` · Site `erptest.local`
Đối chiếu với `docs/Miyano-Portal(Client)_V2/DevHandoff/40_TestCases.md`

## Tóm tắt

| Chỉ số | Kết quả |
|---|---|
| Test tự động | **808/808 xanh** |
| `bench migrate` hai lần liên tiếp | **sạch, exit 0** |
| Test case nghiệm thu | **67** (tài liệu, không phải 61) |
| — Phủ thật | **42** (63%) |
| — Phủ yếu | **24** (36%) |
| — Không phủ | **1** (TC-E7-06) |

"Phủ thật" = có test, test **đỏ được** khi tính năng hỏng, và đi qua **đúng đường người dùng thật đi**.
"Phủ yếu" = có test nhưng gọi hàm nội bộ thay vì endpoint, hoặc khẳng định quá lỏng, hoặc fixture dựng hình dạng dữ liệu hệ thống thật không sinh ra.

Theo epic: E1 5/5/0 · E2 4/2/0 · E3 7/1/0 · E4 7/3/0 · E5 3/3/0 · E6 8/4/0 · E7 1/4/1 · E8 7/2/0.

## Phát hiện quan trọng nhất

### 1. Một chốt chặn KHÔNG được test bảo vệ (đã chứng minh)

Hạ `LY_DO_TOI_THIEU_KHACH` từ **10 xuống 1** — tức gỡ bỏ quy tắc "lý do từ chối báo giá phải ≥10 ký tự" — thì **cả hai module test liên quan vẫn xanh** (`test_e2_workflow_va_accept` 11 test, `test_e6_mua_le` 26 test).

Nguyên nhân: ca "chặn" không gửi lý do **nào cả** (chạm nhánh `not ly_do`, không chạm nhánh độ dài); ca "đậu" dùng 28 ký tự thay vì 15 như TC yêu cầu. Và **lý do khách nhập không được khẳng định là có lưu ở đâu** — nó chỉ nằm trong `add_comment`, không assertion nào chạm.

Đây là chứng từ đàm phán giá. Mất lý do là mất căn cứ.

### 2. Bộ dữ liệu nền mà tài liệu mô tả KHÔNG TỒN TẠI

Tài liệu mô tả một bộ dữ liệu chung (KH-A/KH-B, HĐNT-A với VT0001 hạn mức 500 đã đặt 100, VT0002 200/195, VT0009 hạn mức 0, kho KKH-A với VT-A min 10/ROP 25/max 60, lô L1 nhận 2 đợt) dựng bằng `setup/demo_kho_flow.py`.

Thực tế:
- `demo_kho_flow.py` **không test nào chạm tới** (700+ dòng, là script UAT chính thức trong CLAUDE.md, đang mục nát trong im lặng).
- Nó dựng khách hoàn toàn khác ("Minh Đức"), trong khi test dùng "Bạch Mai"/"PXN ABC".
- `VT0009` **không tồn tại** trong mã sản phẩm. Các con số 500/200/0 và 100/195 do **từng test tự ghi đè**.
- Min/ROP/max/lead/bội số và lô L1 hai đợt đều do test tự dựng.

**Hệ quả:** không ai nghiệm thu được toàn hệ trên một bộ dữ liệu thống nhất. Mỗi bộ số chuẩn của PRD được kiểm trên một hình dạng dữ liệu do chính test đó dựng riêng. Không thể chạy một lệnh rồi mở giao diện lên soi bằng mắt xem 67 kịch bản có ra đúng số không.

Ví dụ cụ thể: TC-E1-07 nói "VT0002 đặt 10 (còn 5)". Số 5 là kết quả phép trừ của hai con số mà chính `setUp` vừa ghi (`qty=200, ordered_qty=195`) — assertion đang kiểm phép trừ của dữ liệu nó tự đặt.

### 3. Ba test case của E7 không thể thực hiện theo tài liệu

- TC-E7-02 "tải **xml** + pdf" và TC-E7-05 "file **xml** thiếu" — module Fast **không lưu XML ở đâu**, và endpoint **chủ động từ chối** `loai="xml"`. Test hiện khoá hành vi **ngược lại** với TC.
- TC-E7-06 "chạy patch backfill 2 lần" — **không có patch nào để chạy**; đã descope có ghi lại, nhưng PRD vẫn đòi.

Nghiệm thu theo tài liệu hiện tại sẽ **fail ba TC "đúng thiết kế"**. Cần chữ ký nghiệm thu, không cần thêm test.

### 4. Hoá đơn điện tử nằm NGOÀI lưới an toàn cách ly

`test_kho_isolation.py` quét động `tabDocType WHERE module='Miyano Portal'` và ném lỗi khi gặp tên không phân loại được — cơ chế này đã cứu dự án nhiều lần. Nhưng `Fast EInvoice Document` thuộc module `Einvoice` của app `erpnext`, **không bị quét tới**.

Nếu module Fast thêm một doctype thứ hai mang dữ liệu khách, nó sẽ ship ra với **zero độ phủ cách ly** và toàn bộ 808 test vẫn xanh.

## Ưu tiên xử lý trước khi nghiệm thu

**P0 — sai chứng từ thuế / mất tiền**
1. TC-E7-06 + chênh lệch spec E7 — quyết định bằng **văn bản**.
2. TC-E7-04 — fixture tự ghi hai field mà `lineage.mark_original_superseded()` ghi, nhưng **không gọi hàm đó**. Upstream đổi là cổng hiển thị sai badge trên chứng từ thuế đã huỷ, test vẫn xanh.
3. TC-E6-10 — false green đã chứng minh (mục 1).
4. TC-E6-02 — "không trừ hạn mức" chỉ chứng minh là "dòng không gắn `blanket_order`". Cần assert `ordered_qty` trước/sau. Nếu đơn lẻ lỡ trừ hạn mức, khách mất quyền đặt theo hợp đồng.

**P1 — rò dữ liệu chéo khách**
5. Mở lưới quét động sang module `Einvoice`.
6. TC-E4-07/E4-08, TC-E5-06 — bộ số chuẩn chỉ chạy trên hàm nội bộ với `kho`/`customer` tiêm tay; test qua phiên chỉ `assertTrue(any(...))`. Lỗi suy diễn tenant sẽ không bị bắt.
7. Màn dự trù thiếu cặp đối chứng cách ly mà bốn màn kia đều có.

**P2 — độ tin cậy chốt chặn**
8. TC-E1-02 — nhánh endpoint bắt `UniqueValidationError` **chưa từng chạy**; không thread nào trong toàn bộ 808 test.
9. TC-E2-02 — chạy as `Administrator` (được cấp mọi role vô điều kiện), không phải tài khoản Sales Manager thật.
10. TC-E2-04 / TC-E6-08 — "email chứa đúng lý do" chỉ kiểm **cấu hình** `Notification`, không render thư, không đọc `Email Queue`.
11. Nhóm "set_user trang trí" (TC-E4-03, E4-06, E8-01, E8-06, E5-01): gọi `set_user` rồi dựng doc với `kho` hardcode + `ignore_permissions=True` — phiên không bao giờ được đọc.
12. Dựng bộ dữ liệu nền thật (mục 2), cho một test smoke chạy `demo_kho_flow.py` chống mục nát.

**P3 — tiện ích:** TC-E1-06 (mệnh đề giao diện — repo không có harness frontend), TC-E5-05, TC-E4-10 (thiếu ca biên 85%), TC-E7-02 (log chỉ đếm delta).

## Bằng chứng phá-code-thấy-đỏ

| Mutation | Kết quả | Kết luận |
|---|---|---|
| Gỡ `if nguong <= 0: return` (ngưỡng duyệt) | **ĐỎ** | TC-E2-03 phủ thật |
| Gỡ quy ước hạn mức 0 = không giới hạn | **ĐỎ** | TC-E1-05 phủ thật |
| `LY_DO_TOI_THIEU_KHACH` 10 → 1 | **XANH cả hai module** | **False green** — TC-E6-10 |
| Gỡ một lớp kiểm sở hữu HĐĐT | XANH | Lớp dư thừa, không phải lỗ hổng |
| Gỡ **cả hai** lớp | **ĐỎ** | TC-E7-03 phủ thật, phòng thủ hai lớp |

`git diff` = 0 byte sau mỗi lần khôi phục; `apps/erpnext` không bị đụng.

## Hồi quy an ninh trên màn mới

| Màn | Cách ly 2 khách | Không lộ tồn/lô/giá vốn | Không DocPerm |
|---|---|---|---|
| NCC | ✅ có positive control | ✅ | ✅ |
| Nhật ký | ✅ | ✅ | ✅ |
| Dự trù | ⚠️ thiếu cặp đối chứng | ✅ | n/a |
| Yêu cầu | ✅ mạnh nhất (5 endpoint, chống dò tên) | ✅ | ✅ |
| HĐĐT | ✅ đã chứng minh đỏ | ✅ | ✅ nhưng **ngoài lưới quét động** |

Ghi chú: `grep "TC-SEC"` trong repo = 0 hit. Ba TC an ninh V1 được phủ về **nội dung** nhưng không truy vết được về mã TC.
