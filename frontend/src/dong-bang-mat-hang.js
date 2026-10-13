// Dòng của bảng mặt hàng ở màn chi tiết (`components/chi-tiet/BangMatHang.vue`).
// Tách khỏi component để `node --test` canh được
// (`dong-bang-mat-hang.test.mjs`), cùng khuôn `gia-dong-don.js`.
//
// BẤT BIẾN: mọi `item_code` có trên đơn đều có mặt trong bảng.
//
// Bảng lấy dòng từ PHIẾU khi có phiếu (phiếu giữ cả dòng quản lý hạ về 0), rồi
// nối dòng khách gõ tay đã khớp mã qua `don.dat_ngoai`. Cả hai nguồn đó đều có
// thể thiếu một dòng mà đơn CÓ: đơn "Theo báo giá" sinh từ một báo giá mà
// Miyano đã khớp mã dòng gõ tay hoặc thêm dòng trên Desk — mặt hàng đó không
// nằm trên phiếu. Bỏ sót nó là để khách vừa đồng ý 2,43 triệu mở đơn ra thấy
// một mặt hàng 960 nghìn (lỗi P-1, trình duyệt thật 13/10/2026).

function soHoacNull(v) {
  return v === null || v === undefined ? null : Number(v)
}

// `dong`: các dòng bảng đã dựng. `don`: payload `portal_order_track` (hoặc
// null khi phiếu chưa có đơn). Trả MẢNG MỚI = `dong` + một dòng cho mỗi mã có
// trên `don.items` mà `dong` chưa có. Dòng sẵn có giữ nguyên đối tượng.
export function boSungDongChiCoTrenDon(dong, don) {
  const kq = [...(dong || [])]
  const theoMa = new Map(kq.map((r) => [r.item_code, r]))
  const moi = new Set()
  for (const it of don?.items || []) {
    const ma = it.item_code
    if (moi.has(ma)) {
      // Đơn có hai dòng cùng mã (nhân viên thêm tay trên Desk): bảng khoá theo
      // mã nên gộp vào MỘT dòng, cộng số lượng / thành tiền / đã giao.
      const r = theoMa.get(ma)
      r.so_luong_tren_don += Number(it.qty) || 0
      r.thanh_tien_tren_don += Number(it.amount) || 0
      r.da_giao_tren_don += Number(it.delivered_qty) || 0
      // Các dòng gộp KHÁC đơn giá: không có một đơn giá nào đúng với SL ×
      // giá = thành tiền. `null` → bảng in "—"; thành tiền vẫn là tổng thật.
      if (soHoacNull(it.rate) !== r.don_gia_tren_don) r.don_gia_tren_don = null
      continue
    }
    if (theoMa.has(ma)) continue
    const r = {
      item_code: ma,
      item_name: it.item_name || '',
      dvt: it.uom || '',
      // `null`, không phải 0: dòng này không có trên phiếu nên KHÔNG có số đề
      // xuất / số duyệt nào — bảng in "—", cùng luật với dòng khớp mã.
      so_luong_de_xuat: null,
      so_luong_duyet: null,
      so_luong_xin_sua: null,
      so_luong_tren_don: Number(it.qty) || 0,
      don_gia_tren_don: soHoacNull(it.rate),
      thanh_tien_tren_don: Number(it.amount) || 0,
      nguon_gia_tren_don: it.nguon_gia || null,
      da_giao_tren_don: Number(it.delivered_qty) || 0,
      ngay_giao_du_kien: it.ngay_giao_du_kien || null,
      ghi_chu_quan_ly: '',
      // Cùng chốt với dòng khớp mã: không có dòng phiếu để quản lý sửa.
      chi_tu_yeu_cau: true,
      // Riêng dòng này: có trên đơn mà không đến từ phiếu lẫn yêu cầu gõ tay.
      chi_tren_don: true,
    }
    kq.push(r)
    theoMa.set(ma, r)
    moi.add(ma)
  }
  return kq
}
