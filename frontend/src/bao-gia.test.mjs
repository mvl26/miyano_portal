// Nhóm, nhãn và hành động của tab "Yêu cầu báo giá" (spec 2026-10-12 §6).
// Chạy bằng `node --test src/*.test.mjs` (`yarn test`).

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  NHOM_BAO_GIA, nhanNhomBaoGia, nhomBaoGiaBadge, khoaNhomBaoGia,
  dichDongBaoGia, hanhDongBaoGia, dongDaSua, dichSauDatHang,
  thongBaoSauDuyet, loiSoLuong, nhanDongBaoGia, badgeDongBaoGia, nhanDot,
} from './bao-gia.js'

test('năm nhóm, đúng thứ tự vòng đời', () => {
  assert.deepEqual(NHOM_BAO_GIA, ['nhap', 'dang_bao_gia', 'cho_dong_y', 'da_dong_y', 'da_dong'])
})

test('nhãn nói rõ việc đang ở phía ai, không dùng lại "Chờ báo giá"', () => {
  assert.equal(nhanNhomBaoGia('dang_bao_gia'), 'Miyano đang báo giá')
  assert.equal(nhanNhomBaoGia('cho_dong_y'), 'Chờ anh/chị đồng ý')
  for (const k of NHOM_BAO_GIA) assert.notEqual(nhanNhomBaoGia(k), 'Chờ báo giá')
})

test('nhóm lạ không làm vỡ nhãn và huy hiệu', () => {
  assert.equal(nhanNhomBaoGia('la'), 'la')
  assert.equal(nhomBaoGiaBadge('la'), 'b-gray')
  assert.equal(nhomBaoGiaBadge('cho_dong_y'), 'b-orange')
})

test('?nhom= chỉ nhận khoá hợp lệ', () => {
  assert.equal(khoaNhomBaoGia('cho_dong_y'), 'cho_dong_y')
  assert.equal(khoaNhomBaoGia('cho_duyet'), '')
  assert.equal(khoaNhomBaoGia(undefined), '')
})

test('dòng đã có báo giá mở màn báo giá; chưa có thì mở phiếu', () => {
  assert.deepEqual(dichDongBaoGia({ bao_gia: 'SAL-QTN-1', de_xuat: 'DXM-1' }),
    { name: 'bao-gia-detail', params: { ten: 'SAL-QTN-1' } })
  assert.deepEqual(dichDongBaoGia({ bao_gia: '', de_xuat: 'DXM-1' }),
    { name: 'de-xuat-detail', params: { ten: 'DXM-1' }, query: { tu: 'bao-gia' } })
})

test('hành động theo cờ của server', () => {
  assert.deepEqual(hanhDongBaoGia({ duoc_dong_y: true, duoc_sua_so_luong: true }),
    ['dong_y', 'tu_choi', 'sua_so_luong'])
  assert.deepEqual(hanhDongBaoGia({ duoc_dong_y: true, duoc_sua_so_luong: false }),
    ['dong_y', 'tu_choi'])
  assert.deepEqual(hanhDongBaoGia({ duoc_dong_y: false }), [])
  assert.deepEqual(hanhDongBaoGia(null), [])
})

test('chỉ gửi dòng có số lượng thật sự đổi và hợp lệ', () => {
  const items = [{ name: 'a', qty: 10 }, { name: 'b', qty: 20 }, { name: 'c', qty: 5 }]
  assert.deepEqual(dongDaSua(items, { a: 10, b: 40, c: '' }), [{ name: 'b', qty: 40 }])
  assert.deepEqual(dongDaSua(items, {}), [])
})

test('sau khi đặt: giỏ trộn về danh sách, giỏ chỉ có hàng chờ báo giá sang yêu cầu báo giá', () => {
  const don = { sales_order: 'SO-1', bao_gia: null }
  const baoGia = { sales_order: null, bao_gia: 'SAL-QTN-1' }
  assert.deepEqual(dichSauDatHang({ sales_order: 'SO-1', bao_gia: 'SAL-QTN-1', don: [don, baoGia] }),
    { loai: 'tron', to: { name: 'yeu-cau' } })
  assert.deepEqual(dichSauDatHang({ sales_order: null, bao_gia: 'SAL-QTN-1', don: [baoGia] }),
    { loai: 'bao_gia', to: { name: 'bao-gia-detail', params: { ten: 'SAL-QTN-1' } } })
  // Tên báo giá chỉ nằm trong `don[]` cũng phải ra đúng đích.
  assert.deepEqual(dichSauDatHang({ sales_order: null, don: [baoGia] }),
    { loai: 'bao_gia', to: { name: 'bao-gia-detail', params: { ten: 'SAL-QTN-1' } } })
  assert.deepEqual(dichSauDatHang({ sales_order: 'SO-1', bao_gia: null, don: [don] }),
    { loai: 'don', to: null })
})

test('không có mã đơn thì không bao giờ rơi vào màn xác nhận đơn', () => {
  assert.notEqual(dichSauDatHang({ sales_order: null, don: [] }).loai, 'don')
  assert.notEqual(dichSauDatHang(null).loai, 'don')
  assert.deepEqual(dichSauDatHang({}).to, { name: 'yeu-cau' })
})

test('duyệt một phiếu: nói đúng chứng từ vừa sinh ra', () => {
  assert.equal(thongBaoSauDuyet({ sales_order: 'SO-1', bao_gia: null, phieu_cung_lan_dat: null }),
    'Đã duyệt phiếu — đơn hàng đã được tạo.')
  assert.equal(thongBaoSauDuyet({ sales_order: null, bao_gia: 'SAL-QTN-1', phieu_cung_lan_dat: null }),
    'Đã duyệt phiếu — yêu cầu báo giá đã gửi cho Miyano.')
  // Không biết sinh ra gì thì không khẳng định gì.
  assert.equal(thongBaoSauDuyet({}), 'Đã duyệt phiếu.')
  assert.equal(thongBaoSauDuyet(null), 'Đã duyệt phiếu.')
})

test('duyệt cả hai phiếu: đếm đúng số đơn và số yêu cầu báo giá', () => {
  const don = { sales_order: 'SO-2', bao_gia: null }
  const baoGia = { sales_order: null, bao_gia: 'SAL-QTN-2' }
  assert.equal(thongBaoSauDuyet({ sales_order: 'SO-1', bao_gia: null, phieu_cung_lan_dat: don }),
    'Đã duyệt cả hai phiếu — 2 đơn hàng đã được tạo.')
  assert.equal(thongBaoSauDuyet({ sales_order: 'SO-1', bao_gia: null, phieu_cung_lan_dat: baoGia }),
    'Đã duyệt cả hai phiếu — 1 đơn hàng đã được tạo và 1 yêu cầu báo giá đã gửi cho Miyano.')
  assert.equal(thongBaoSauDuyet({ sales_order: null, bao_gia: 'SAL-QTN-1', phieu_cung_lan_dat: don }),
    'Đã duyệt cả hai phiếu — 1 đơn hàng đã được tạo và 1 yêu cầu báo giá đã gửi cho Miyano.')
  assert.equal(thongBaoSauDuyet({ sales_order: null, bao_gia: 'SAL-QTN-1', phieu_cung_lan_dat: baoGia }),
    'Đã duyệt cả hai phiếu — 2 yêu cầu báo giá đã gửi cho Miyano.')
  assert.equal(thongBaoSauDuyet({ phieu_cung_lan_dat: {} }), 'Đã duyệt cả hai phiếu.')
})

test('số lượng sửa phải lớn hơn 0 — báo đúng dòng và nói phải làm gì', () => {
  const items = [
    { name: 'a', item_code: 'VT-A', qty: 10 },
    { name: 'b', item_code: 'VT-B', qty: 20 },
  ]
  const cau = (ma) => `${ma}: số lượng phải lớn hơn 0. Không cần mặt hàng nào nữa thì từ chối báo giá.`
  assert.equal(loiSoLuong(items, { a: 10, b: 0 }), cau('VT-B'))
  assert.equal(loiSoLuong(items, { a: -3, b: 20 }), cau('VT-A'))
  assert.equal(loiSoLuong(items, { a: '', b: 20 }), cau('VT-A'))
  assert.equal(loiSoLuong(items, { a: 'abc', b: 20 }), cau('VT-A'))
  assert.equal(loiSoLuong(items, { a: null, b: 20 }), cau('VT-A'))
  // Một dòng 0 cạnh một dòng sửa hợp lệ vẫn bị chặn, không lặng lẽ bỏ qua.
  assert.equal(loiSoLuong(items, { a: 0, b: 40 }), cau('VT-A'))
})

test('số lượng hợp lệ thì không có lỗi', () => {
  const items = [{ name: 'a', item_code: 'VT-A', qty: 10 }, { name: 'b', item_code: 'VT-B', qty: 20 }]
  assert.equal(loiSoLuong(items, { a: 10, b: 40 }), '')
  assert.equal(loiSoLuong(items, { a: 0.5, b: '7' }), '')
  assert.equal(loiSoLuong([], {}), '')
})

test('dòng nhóm nháp nói đúng trạng thái phiếu, không gom chung một nhãn', () => {
  for (const tt of ['Nháp', 'Chờ duyệt', 'Chờ duyệt sửa', 'Từ chối', 'Đã huỷ']) {
    assert.equal(nhanDongBaoGia({ nhom: 'nhap', trang_thai_phieu: tt }), tt)
  }
  assert.equal(badgeDongBaoGia({ nhom: 'nhap', trang_thai_phieu: 'Nháp' }), 'b-gray')
  assert.equal(badgeDongBaoGia({ nhom: 'nhap', trang_thai_phieu: 'Chờ duyệt' }), 'b-blue')
  assert.equal(badgeDongBaoGia({ nhom: 'nhap', trang_thai_phieu: 'Từ chối' }), 'b-red')
  assert.equal(badgeDongBaoGia({ nhom: 'nhap', trang_thai_phieu: 'Đã huỷ' }), 'b-red')
})

test('dòng nhóm nháp thiếu trạng thái phiếu rơi về nhãn nhóm', () => {
  assert.equal(nhanDongBaoGia({ nhom: 'nhap', trang_thai_phieu: '' }), 'Nháp / chờ duyệt nội bộ')
  assert.equal(badgeDongBaoGia({ nhom: 'nhap' }), 'b-gray')
})

test('dòng đã có báo giá giữ nhãn và huy hiệu của nhóm', () => {
  const dong = { nhom: 'cho_dong_y', trang_thai_phieu: 'Đã duyệt' }
  assert.equal(nhanDongBaoGia(dong), 'Chờ anh/chị đồng ý')
  assert.equal(badgeDongBaoGia(dong), 'b-orange')
  assert.equal(nhanDongBaoGia({ nhom: 'da_dong', trang_thai_phieu: 'Đã duyệt' }), 'Đã đóng')
})

test('nhãn đợt: số đợt + trạng thái, đợt đã trả về nói rõ', () => {
  assert.equal(nhanDot({ so_dot: 2, nhom: 'cho_dong_y' }), 'Đợt 2 · Chờ anh/chị đồng ý')
  assert.equal(nhanDot({ so_dot: 1, nhom: 'da_dong', da_tra_ve: true }), 'Đợt 1 · đã trả về phiếu')
  assert.equal(nhanDot({ so_dot: 3, nhom: 'da_dong_y' }), 'Đợt 3 · Đã đồng ý')
})
