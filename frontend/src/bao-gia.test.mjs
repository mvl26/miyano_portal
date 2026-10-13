// Nhóm, nhãn và hành động của tab "Yêu cầu báo giá" (spec 2026-10-12 §6).
// Chạy bằng `node --test src/*.test.mjs` (`yarn test`).

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  NHOM_BAO_GIA, nhanNhomBaoGia, nhomBaoGiaBadge, khoaNhomBaoGia,
  dichDongBaoGia, hanhDongBaoGia, dongDaSua, dichSauDatHang,
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
    { name: 'de-xuat-detail', params: { ten: 'DXM-1' } })
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
