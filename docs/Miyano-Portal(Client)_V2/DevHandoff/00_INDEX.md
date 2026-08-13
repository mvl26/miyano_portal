# 00_INDEX — Bộ bàn giao Dev · Miyano Client Portal v2.2 (2026-08-12)

Mục đích: Dev (dùng Claude Code) đọc là biết **cần làm gì, làm thế nào, sản phẩm ra sao**.
Đặt cả thư mục `DevHandoff/` + 2 file BA/FormSpec vào repo để Claude Code tự đọc.

## Thứ tự đọc

| # | File | Là gì | Khi nào đọc |
|---|---|---|---|
| 1 | `01_HuongDan_Dev_ClaudeCode.md` | **Đọc đầu tiên nếu mới dùng Claude Code**: cài đặt, vòng làm việc, prompt mẫu, quy tắc an toàn | Trước khi bắt đầu |
| 2 | `CLAUDE.md` | Ngữ cảnh dự án cho Claude Code: quy ước, 10 quyết định nền tảng, lệnh | **Luôn** — copy vào root repo |
| 3 | `00_INDEX.md` | File này | Khi nhận việc |
| 3 | `1x_PRD_E*.md` (7 file) | PRD từng epic: user story + AC (Given/When/Then), Mermaid flow, quy tắc, ngoại lệ, DoD | Trước khi code epic đó |
| 4 | `20_DataDict.md` | Từ điển dữ liệu theo DocType/fieldtype Frappe | Khi tạo/sửa doctype, trường |
| 5 | `30_API_Spec.md` | Đặc tả endpoint whitelist: tham số, JSON request/response mẫu, mã lỗi | Khi viết API |
| 6 | `40_TestCases.md` | Test case v2 dạng GWT + bộ số kỳ vọng | Khi viết test |
| 7 | `50_Prototype_ClientPortal_v2.html` | Prototype desktop 23 màn (F-01…F-23), mở bằng trình duyệt | Khi dựng UI |

Tài liệu nền (cùng bộ, ngoài thư mục này): `BA-miyano_portal_v2.md` (nguồn sự thật QT/UC/BR/NL/VĐ) ·
`FormSpec-miyano_portal_v2.md` (đặc tả từng trường) · `01_Workflow-miyano_portal_v2.html` (sơ đồ cho người).

## Bản đồ epic

| Epic | File | Phạm vi (QT / UC / BR chính) | Ưu tiên đề xuất |
|---|---|---|---|
| E1 — Đặt hàng & hạn mức | `10_PRD_E1_DatHang_HanMuc.md` | QT1 · UC-01…05, 14 · BR-O1…O8, O11…O13, **O15** | P1 (mở rộng phần Hiện có) |
| E2 — Duyệt đơn & máy trạng thái | `11_PRD_E2_DuyetDon.md` | QT2 · BR-O9, O14 · SLA NL-2.6 | P1 |
| E3 — Giao nhiều đợt & đối soát | `12_PRD_E3_GiaoNhieuDot_DoiSoat.md` | QT3 · UC-07, 47, 48 · BR-O10, K16, K17 | P1 |
| E4 — Kho khách: NCC, đợt hàng, nhật ký | `13_PRD_E4_KhoKhach_NCC_DotHang.md` | QT4/5/7/8 · UC-42, 43, 44 · BR-N, BR-D, K19…K21 | P2 |
| E5 — Dự trù JIT | `14_PRD_E5_DuTru_JIT.md` | QT9 · UC-45, 46, 49, 50, 51 · BR-P | P3 (cần ≥30 ngày dữ liệu) |
| E6 — Mua lẻ & yêu cầu hàng hoá | `15_PRD_E6_MuaLe_YeuCauHang.md` | QT10/11 · UC-15…17, 52, 53 · BR-R, BR-Y | P2 |
| E7 — Hoá đơn điện tử | `16_PRD_E7_HDDT.md` | QT12 · UC-18 · BR-E · **chờ VĐ-11** | P2 (sau họp data contract) |
| E8 — Cấp phát khoa phòng/cá nhân | `17_PRD_E8_CapPhat_KhoaPhong.md` | QT4 mở rộng · UC-54…56 · BR-CP · QĐ-9 | P2 (làm cùng đợt E4) |

Việc chung P0 (trước mọi epic): vá bảo mật **VĐ-1** (`search_link`) · doctype `Miyano Portal Settings` ·
cấu hình over-delivery = 0 (QĐ-2).

## Quy ước prompt cho Claude Code (gợi ý cho Dev)

```
Đọc CLAUDE.md, DevHandoff/12_PRD_E3_GiaoNhieuDot_DoiSoat.md, 20_DataDict.md (mục Customer Stock Receipt),
30_API_Spec.md (kho_phieu_nhap_save). Hiện thực US-E3.2 đúng AC, kèm test theo 40_TestCases.md nhóm TC-E3.
Không vi phạm 10 quyết định nền tảng trong CLAUDE.md.
```

## Trạng thái nhãn

Mọi tài liệu dùng chung nhãn: **[Hiện có]** = đã chạy trên nhánh `feature/vat-tu-danh-muc`, đối chiếu
mã nguồn; **[MỚI]** = phải xây trong v2. PRD chỉ đặc tả chi tiết phần [MỚI]; phần [Hiện có] nêu để biết
điểm nối, tránh code trùng.
