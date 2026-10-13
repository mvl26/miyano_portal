// Luật giỏ hàng theo Price List (spec 2026-10-09 §3.2, §4.1, §7) — chạy bằng
// `node --test src/*.test.mjs` (`yarn test`), cùng khuôn `api.dich-loi.test.mjs`.

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  coGia, dongKhopMa, laTangBangGia, tangTuNguonGia, thanhTienDong, tomTatGio,
} from './gio-hang.js'

const A = { item_code: 'A', tang: 'bang_gia', don_gia: 1200, so_luong_de_xuat: 10 }
const B = { item_code: 'B', tang: 'cho_bao_gia', don_gia: null, so_luong_de_xuat: 3 }
// Dòng tầng bảng giá của phiếu Nháp mở lại: chưa có con số.
const C = { item_code: 'C', tang: 'bang_gia', don_gia: 0, so_luong_de_xuat: 2 }

test('coGia: chỉ dòng tầng bảng giá có đơn giá DƯƠNG', () => {
  assert.equal(coGia(A), true)
  assert.equal(coGia(B), false)
  assert.equal(coGia(C), false, 'giá 0 là "chưa có giá", không phải "0 đồng"')
  assert.equal(coGia({ tang: 'bang_gia', don_gia: null }), false)
  assert.equal(coGia({ tang: 'bang_gia' }), false)
  assert.equal(coGia({ tang: 'cho_bao_gia', don_gia: 5000 }), false, 'tầng quyết định, không phải giá')
  assert.equal(coGia({ tang: 'hop_dong', don_gia: 5000 }), false, 'tầng cũ không còn được trả về')
})

test('laTangBangGia đọc `tang`, kể cả khi chưa có con số', () => {
  assert.equal(laTangBangGia(C), true)
  assert.equal(laTangBangGia(B), false)
  assert.equal(laTangBangGia(null), false)
})

test('thanhTienDong: giá × số lượng trong giỏ, `null` khi không có giá', () => {
  assert.equal(thanhTienDong(A), 12000)
  assert.equal(thanhTienDong({ ...A, so_luong_de_xuat: '2.5' }), 3000, 'ô nhập giữ chuỗi thô')
  assert.equal(thanhTienDong({ ...A, so_luong_de_xuat: '' }), 0)
  assert.equal(thanhTienDong(B), null)
  assert.equal(thanhTienDong(C), null)
})

test('tangTuNguonGia: dòng phiếu đã lưu', () => {
  assert.equal(tangTuNguonGia('Bảng giá', 0), 'bang_gia')
  assert.equal(tangTuNguonGia('Chờ báo giá', 0), 'cho_bao_gia')
  assert.equal(tangTuNguonGia('', 0), 'cho_bao_gia')
  assert.equal(tangTuNguonGia(undefined, undefined), 'cho_bao_gia')
  assert.equal(tangTuNguonGia('Hợp đồng', 88000), 'bang_gia', 'dòng cũ đã đóng dấu giá')
  assert.equal(tangTuNguonGia('Hợp đồng', 0), 'cho_bao_gia')
})

test('tomTatGio: giỏ trộn sẽ tách, đếm đúng hai nhóm', () => {
  const t = tomTatGio([A, B, C], 2)
  assert.equal(t.soDatNgay, 2)
  assert.equal(t.soChoBaoGia, 3, '1 dòng có mã chờ báo giá + 2 dòng gõ tay')
  assert.equal(t.seTach, true)
})

test('tomTatGio: dòng gõ tay một mình cũng làm giỏ có giá phải tách', () => {
  const t = tomTatGio([A], 1)
  assert.equal(t.seTach, true)
  assert.equal(t.soDatNgay, 1)
  assert.equal(t.soChoBaoGia, 1)
})

test('tomTatGio: giỏ một loại không tách', () => {
  assert.equal(tomTatGio([A, C], 0).seTach, false)
  assert.equal(tomTatGio([B], 3).seTach, false)
  assert.equal(tomTatGio([], 0).seTach, false)
  assert.equal(tomTatGio(null, 0).seTach, false)
})

test('tomTatGio: phiếu đã từng gửi duyệt không tách nữa (chỉ tách lần gửi đầu)', () => {
  const t = tomTatGio([A, B], 0, true)
  assert.equal(t.seTach, false)
  assert.equal(t.soDatNgay, 1)
  assert.equal(t.soChoBaoGia, 1)
})

test('tomTatGio: tạm tính chỉ cộng dòng có con số và nói rõ dòng chưa rõ giá', () => {
  const t = tomTatGio([A, B, C, { ...A, item_code: 'D', don_gia: 500, so_luong_de_xuat: 4 }], 1)
  assert.equal(t.tongTamTinh, 12000 + 2000)
  assert.equal(t.soCoGia, 2)
  assert.equal(t.soChuaRoGia, 1, 'dòng C thuộc tầng bảng giá nhưng chưa có con số')
})

test('dongKhopMa: chỉ nhận dòng trùng mã chính xác', () => {
  const rows = [{ item_code: 'VT00051', tang: 'cho_bao_gia' }, { item_code: 'VT0005', tang: 'bang_gia' }]
  assert.equal(dongKhopMa(rows, 'VT0005').tang, 'bang_gia')
  assert.equal(dongKhopMa(rows, 'VT000'), null)
  assert.equal(dongKhopMa(undefined, 'VT0005'), null)
})
