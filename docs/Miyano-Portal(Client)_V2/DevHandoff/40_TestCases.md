# 40_TestCases — Kịch bản kiểm thử v2 (bổ sung bộ 73 TC của V1)

Quy ước: viết dạng Given/When/Then rút gọn; **Loại**: C=Chính (happy) · B=Biên · Â=Âm (phải chặn).
Bộ 73 TC V1 (`KichBan_DuLieu_Test_ClientPortal_Miyano_v1.0.xlsx`) vẫn chạy đủ — dưới đây chỉ là phần v2.
Dev dùng bảng này để yêu cầu Claude Code sinh test tự động (`bench run-tests --app miyano_portal`).

## Dữ liệu nền dùng chung (dựng bằng `setup/demo_kho_flow.py` mở rộng)

```
KH-A (BV Test A, có kho KKH-A active, được bật mua lẻ) · KH-B (PK Test B, có kho, KHÔNG bật mua lẻ)
HĐNT-A: VT0001 hạn mức 500 (đã đặt 100) · VT0002 hạn mức 200 (đã đặt 195) · VT0009 hạn mức 0 (KGH)
Settings: ngưỡng duyệt 50.000.000 · SLA đơn 8h · SLA yêu cầu 48h · hiệu lực báo giá 7 ngày
· ADU 90 ngày · dữ liệu tối thiểu 30 ngày · chậm luân chuyển 90 ngày · Price List bán lẻ "Bán lẻ 2026"
Kho KKH-A: VT-A (map VT0001, min 10/ROP 25/max 60, lead 3, bội số 10) · lô L1 nhận 2 đợt (100 + 50)
```

## TC-E1 — Đặt hàng & hạn mức

| Mã | Kịch bản (GWT rút gọn) | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E1-01 | Gọi `portal_order_place` 2 lần cùng `request_id` | Lần 2 trả đúng SO lần 1, `da_ton_tai=true`; DB chỉ 1 SO | Â |
| TC-E1-02 | 2 request song song cùng `request_id` (thread) | Chỉ 1 SO tạo; không lỗi 500 | B |
| TC-E1-03 | VT0003 bội số 10, đặt 15 qua API (bỏ qua client) | 417 `sai_boi_so`, gợi ý 20 | Â |
| TC-E1-04 | Ngày giao = hôm qua qua API | 417 `ngay_giao_khong_hop_le` | Â |
| TC-E1-05 | **VT0009 hạn mức 0**: đặt 1.000 | Thành công; dòng SO không có `against_blanket_order`; có `custom_hdnt` | C |
| TC-E1-06 | VT0009 trên danh mục | Badge "Không giới hạn", không bar, SL không khoá max | C |
| TC-E1-07 | VT0002 đặt 10 (còn 5) | 417 gom lỗi, `con_lai=5`; giỏ giữ nguyên | Â |
| TC-E1-08 | % hạn mức HĐNT trên Dashboard khi có VT0009 (KGH) | Mẫu số không gồm VT0009 | B |
| TC-E1-09 | Item thiếu giá: đặt | 417 `thieu_gia` + Notification "Thiếu giá" cho sales, ngày thứ 2 không gửi lại | Â |
| TC-E1-10 | `portal_reorder` đơn cũ có 1 dòng hết hạn mức | Giỏ điền dòng hợp lệ giá hiện hành; `bi_loai` nêu dòng kia | C |

## TC-E2 — Duyệt đơn

| Mã | Kịch bản | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E2-01 | Sales User xác nhận đơn 49tr / 50tr | 49tr OK; 50tr bị chặn NL-2.5 | B |
| TC-E2-02 | Sales Manager xác nhận đơn 50tr | OK, docstatus 1 | C |
| TC-E2-03 | Ngưỡng để trống, Sales User xác nhận 100tr | OK (một tầng như cũ) | C |
| TC-E2-04 | Từ chối không nhập lý do | Chặn; có lý do → email khách chứa đúng lý do | Â |
| TC-E2-05 | Đơn treo 9h làm việc | Notification leo thang Manager đúng 1 lần/ngày | C |
| TC-E2-06 | `portal_order_accept` đơn của khách khác | 403, không đổi trạng thái | Â |

## TC-E3 — Giao nhiều đợt & đối soát

| Mã | Kịch bản | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E3-01 | SO 10, DN1=6 submit, DN2=5 | DN2 bị ERPNext chặn (allowance 0); DN2=4 OK | Â |
| TC-E3-02 | 3 DN lần lượt trên 1 SO | 3 phiếu nhập nháp, `so_dot` = 1,2,3; mỗi dòng `sl_giao` đúng DN | C |
| TC-E3-03 | Sửa thực nhận 48/50 không lý do → ghi sổ | Chặn; có lý do → ghi sổ OK, `co_chenh_lech=1`, sổ ghi 48, Notification sales | Â/C |
| TC-E3-04 | Sửa thực nhận 52 > `sl_giao` 50 | Chặn NL-3.10 | Â |
| TC-E3-05 | Huỷ DN khi phiếu nháp / đã ghi sổ | Nháp bị gỡ / phiếu đảo sinh, tồn về đúng (test [Hiện có] phải giữ xanh) | C |
| TC-E3-06 | `portal_order_track` đơn có 2 đợt | `dot_giao[]` đủ 2 phần tử, trạng thái phiếu nhập đúng | C |
| TC-E3-07 | DN có dòng không batch | Phiếu ghi `KHONG-LO`, `thieu_lo_han=1`, không chặn giao | B |
| TC-E3-08 | Lỗi giả lập trong phần mở rộng hook | DN vẫn submit OK (không ném lỗi ra ngoài) | Â |

## TC-E4 — Kho: NCC, đợt, nhật ký

| Mã | Kịch bản | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E4-01 | Tạo NCC trùng tuyệt đối / gần giống trong kho | Trùng → chặn; gần giống → `goi_y_trung` trả về | Â/B |
| TC-E4-02 | KH-B gọi `kho_ncc_list` xem NCC của KH-A | Chỉ thấy NCC kho mình (cách ly) | Â |
| TC-E4-03 | Phiếu Mua ngoài không chọn NCC | Chặn `thieu_ncc` | Â |
| TC-E4-04 | Phiếu Mua ngoài bỏ trống chứng từ → ghi sổ | OK + `thieu_chung_tu=1`; lọc theo cờ ra đúng phiếu | C |
| TC-E4-05 | Import tồn đầu kỳ lần 2 | Chặn `ton_dau_da_nhap` từ bước upload | Â |
| TC-E4-06 | Xuất sử dụng lô quá hạn, không tick xác nhận | Chặn; tick → OK; loại "Xuất huỷ - hết hạn" không hỏi | Â/C |
| TC-E4-07 | **Nhật ký**: 12 dòng có 2 dòng đảo | Tồn-sau-giao-dịch dòng cuối = `kho_ton`; dòng đảo `da_dao=true` | C |
| TC-E4-08 | **NXT theo đợt — bộ số chuẩn PRD E4**: L1 nhận 100+50, xuất 120 | PNK-001: còn 0, 100%; PNK-005: còn 30, 40%, tuổi 51n, cờ chậm (ngưỡng 30) | C |
| TC-E4-09 | Cảnh báo hạn: lô không hạn dùng | Vào nhóm "Không có hạn dùng", không tính sắp hết hạn | B |
| TC-E4-10 | Tạo vật tư tên giống ≥85% | Cảnh báo mềm, vẫn tạo được | B |

## TC-E5 — Dự trù JIT (bộ số chuẩn PRD E5)

| Mã | Kịch bản | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E5-01 | 90 ngày xuất sử dụng 450 + xuất huỷ 30 + 1 phiếu đảo | ADU = **5,0** (chỉ tính Xuất sử dụng, trừ đảo) | C |
| TC-E5-02 | `kho_min_max_goi_y` với lead 3, min 10 | ROP = **25**; max để khách chốt | C |
| TC-E5-03 | Tồn 22, ROP 25, max 60, bội số 10 | Trạng thái "Sắp thiếu"; ngày phủ **4,4**; SL gợi ý **40** | C |
| TC-E5-04 | Vật tư 20 ngày dữ liệu, chưa khai min | Không cảnh báo; gợi ý trả `du_lieu=false` | B |
| TC-E5-05 | Giỏ bổ sung: vật tư thuộc HĐNT / ngoài HĐNT | Thuộc → giỏ điền 40; ngoài → chỉ có nút tạo yêu cầu (E6) | C |
| TC-E5-06 | Report share-of-wallet kỳ có nhập Miyano 70tr + NCC-X 30tr | Tỷ trọng 70/30 đúng, loại trừ phiếu đảo | C |

## TC-E6 — Mua lẻ & yêu cầu hàng hoá

| Mã | Kịch bản | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E6-01 | KH-B (không bật) gọi `portal_catalog_ban_le` | 403 `khong_duoc_mua_le` | Â |
| TC-E6-02 | KH-A đặt lẻ item có giá lẻ | SO `custom_loai_don="Mua lẻ"`, không trừ hạn mức, vào "Chờ xác nhận" | C |
| TC-E6-03 | Đặt lẻ item ĐANG thuộc HĐNT hiệu lực | 417 `thuoc_hdnt_hieu_luc` (BR-R7) | Â |
| TC-E6-04 | Payload trộn dòng HĐNT + lẻ 1 đơn | Server từ chối | Â |
| TC-E6-05 | Tạo yêu cầu thiếu `dvt` / đính kèm 6 file / file 11MB | Chặn từng trường hợp đúng thông điệp | Â |
| TC-E6-06 | Tạo yêu cầu tên gần giống yêu cầu đang mở | `canh_bao_trung` có mã cũ, vẫn tạo được | B |
| TC-E6-07 | Yêu cầu quá 48h ở "Mới" | Leo thang Manager 1 lần/ngày | C |
| TC-E6-08 | "Không đáp ứng được" thiếu lý do | Chặn; có lý do → email khách kèm lý do | Â |
| TC-E6-09 | SO báo giá "Chờ khách đồng ý": KH-A đồng ý | → "Chờ Miyano xác nhận"; Comment log user+time; yêu cầu → "Đã chuyển thành đơn" | C |
| TC-E6-10 | Không đồng ý với lý do 5 ký tự / 15 ký tự | 5 → chặn; 15 → về "Chờ xác nhận", lý do lưu | Â/C |
| TC-E6-11 | Báo giá quá 7 ngày | Job đóng đơn + email 2 phía; yêu cầu → "Hết hạn"; `portal_order_accept` → `qua_han_hieu_luc` | B |
| TC-E6-12 | KH-B xem yêu cầu của KH-A (đoán URL/name) | 403/không thấy | Â |

## TC-E7 — Hoá đơn điện tử

| Mã | Kịch bản | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E7-01 | SI "Chưa phát hành" | Khối hiển thị "Đang phát hành HĐĐT", không nút tải | C |
| TC-E7-02 | ~~SI "Đã phát hành": tải xml + pdf~~ **KHÔNG ÁP DỤNG** | ~~Stream đúng file; log lượt tải ghi user+giờ~~ — module Fast **không lưu XML ở đâu** (không field/method Fast nào trả XML); endpoint chủ động từ chối `loai="xml"`. Chỉ còn PDF. Xem `docs/HDDT-ban-giao-team-module.md` §1. | C |
| TC-E7-03 | KH-B tải hoá đơn KH-A / request không đăng nhập | 403 cả hai | Â |
| TC-E7-04 | SI bị huỷ có SI thay thế | Badge + link 2 chiều trên cả hai dòng | C |
| TC-E7-05 | ~~File xml thiếu trên server~~ **KHÔNG ÁP DỤNG** | ~~417 thân thiện; notification kế toán~~ — không có file XML nào để "thiếu": module Fast không lưu XML, endpoint từ chối `loai="xml"` ngay từ đầu (hành vi NGƯỢC với kịch bản này theo đúng thiết kế). Xem `docs/HDDT-ban-giao-team-module.md` §1. | Â |
| TC-E7-06 | ~~Chạy patch backfill 2 lần~~ **KHÔNG ÁP DỤNG** | ~~Idempotent, không nhân bản dữ liệu~~ — không có patch backfill nào để chạy: khối HĐĐT trên cổng **tra cứu trực tiếp** `Fast EInvoice Document` mỗi lần đọc (`einvoice.py`), không copy/backfill dữ liệu sang bảng nào khác, nên không có gì để "chạy 2 lần" hay nhân bản. Đã descope, ghi lại tại `docs/HDDT-ban-giao-team-module.md`; `16_PRD_E7_HDDT.md:56` vẫn đòi patch — chênh lệch tài liệu, không phải thiếu triển khai. | B |

## TC-E8 — Cấp phát khoa phòng / cá nhân (QĐ-9)

| Mã | Kịch bản | Kỳ vọng | Loại |
|---|---|---|---|
| TC-E8-01 | Tạo khoa trùng tuyệt đối / gần giống trong kho | Trùng → chặn; gần giống → `goi_y_trung` | Â/B |
| TC-E8-02 | KH-B gọi `kho_khoa_phong_list` | Chỉ thấy khoa kho mình (cách ly) | Â |
| TC-E8-03 | Kho bật `bat_buoc_khoa_phong`; phiếu Xuất sử dụng tạo SAU đó thiếu khoa → ghi sổ | Chặn NL-4.11; phiếu nháp tạo TRƯỚC khi bật → ghi sổ OK | Â/B |
| TC-E8-04 | Loại "Xuất huỷ - hết hạn" thiếu khoa, kho đang bật cờ | Không chặn (chỉ áp Xuất sử dụng) | B |
| TC-E8-05 | Khoa bị tắt còn trên phiếu nháp → ghi sổ | Cảnh báo chọn lại khoa hoạt động (NL-4.12) | Â |
| TC-E8-06 | `kho_nguoi_nhan_goi_y("Khoa Hồi sức","t")` với lịch sử "BS. Tuấn"/"ĐD. Lan" | Trả ["BS. Tuấn"]; khoa khác không lẫn gợi ý | C |
| TC-E8-07 | **Báo cáo cấp phát — bộ số chuẩn PRD E8** (538.000 / 552.000 / 230.000 chưa gắn khoa) | Nhóm đúng; %: 40,8 / 41,8 / 17,4; "Chưa gắn khoa" tách riêng; phiếu đảo không tính | C |
| TC-E8-08 | Khoa đã dùng trên phiếu → xoá | Không xoá được, chỉ tắt (BR-CP1) | Â |
| TC-E8-09 | In phiếu xuất có khoa + người nhận | Print format TT107 hiển thị đúng hai trường | C |

## Hồi quy bắt buộc mỗi lần merge

339 test [Hiện có] xanh · TC-SEC-01/02/03 của V1 (cách ly, không lộ tồn/lô/giá vốn, không vào Desk)
chạy lại trên MỌI màn hình mới (NCC, nhật ký, dự trù, yêu cầu, HĐĐT) · `bench migrate` chạy 2 lần liên
tiếp không lỗi.
