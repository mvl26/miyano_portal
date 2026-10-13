// Bảng mặt hàng của màn chi tiết không được đánh rơi dòng nào của đơn (lỗi P-1,
// trình duyệt thật 13/10/2026) — chạy bằng `node --test src/*.test.mjs`.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { boSungDongChiCoTrenDon } from './dong-bang-mat-hang.js'

// Đúng ca đã lộ: phiếu gốc có 1 mã; đơn "Theo báo giá" có 2 dòng, dòng sau vốn
// là hàng khách gõ tay được Miyano khớp mã trên báo giá.
const DONG_PHIEU = [{
  item_code: 'MYN-ALC-90-500', item_name: 'Cồn 90', dvt: 'Chai',
  so_luong_de_xuat: 20, so_luong_duyet: 30,
  so_luong_tren_don: 30, don_gia_tren_don: 32000, thanh_tien_tren_don: 960000,
}]
const DON = {
  items: [
    { item_code: 'MYN-ALC-90-500', item_name: 'Cồn 90', uom: 'Chai', qty: 30, rate: 32000, amount: 960000, delivered_qty: 0, nguon_gia: 'Báo giá' },
    { item_code: 'MYN-GLOVE-NIT-L', item_name: 'Găng nitrile L', uom: 'Hộp', qty: 15, rate: 98000, amount: 1470000, delivered_qty: 5, nguon_gia: 'Báo giá', ngay_giao_du_kien: '2026-10-20' },
  ],
}

const ma = (ds) => ds.map((r) => r.item_code)

test('mọi item_code có trên đơn đều có mặt trong bảng', () => {
  const kq = boSungDongChiCoTrenDon(DONG_PHIEU, DON)
  for (const it of DON.items) assert.ok(ma(kq).includes(it.item_code), it.item_code)
  assert.deepEqual(ma(kq), ['MYN-ALC-90-500', 'MYN-GLOVE-NIT-L'])
})

test('dòng bổ sung mang đúng số lượng, đơn giá, thành tiền của đơn', () => {
  const r = boSungDongChiCoTrenDon(DONG_PHIEU, DON)[1]
  assert.equal(r.item_name, 'Găng nitrile L')
  assert.equal(r.dvt, 'Hộp')
  assert.equal(r.so_luong_tren_don, 15)
  assert.equal(r.don_gia_tren_don, 98000)
  assert.equal(r.thanh_tien_tren_don, 1470000)
  assert.equal(r.da_giao_tren_don, 5)
  assert.equal(r.nguon_gia_tren_don, 'Báo giá')
  assert.equal(r.ngay_giao_du_kien, '2026-10-20')
})

test('dòng bổ sung không có số của phiếu và không sửa được lúc duyệt', () => {
  const r = boSungDongChiCoTrenDon(DONG_PHIEU, DON)[1]
  assert.equal(r.so_luong_de_xuat, null)
  assert.equal(r.so_luong_duyet, null)
  assert.equal(r.so_luong_xin_sua, null)
  assert.equal(r.chi_tu_yeu_cau, true)
  assert.equal(r.chi_tren_don, true)
  assert.equal(r.yeu_cau_khop, undefined)
})

test('dòng đã có trong bảng giữ nguyên, không nhân đôi', () => {
  const kq = boSungDongChiCoTrenDon(DONG_PHIEU, DON)
  assert.equal(kq[0], DONG_PHIEU[0])
  // Dòng gõ tay đã khớp mã mà `BangMatHang` tự dựng từ `don.dat_ngoai`.
  const daCo = [...DONG_PHIEU, { item_code: 'MYN-GLOVE-NIT-L', yeu_cau_khop: [{}], chi_tu_yeu_cau: true }]
  const kq2 = boSungDongChiCoTrenDon(daCo, DON)
  assert.equal(kq2.length, 2)
  assert.equal(kq2[1], daCo[1])
})

test('không có đơn, hoặc đơn không thừa dòng nào: trả nguyên danh sách', () => {
  assert.deepEqual(boSungDongChiCoTrenDon(DONG_PHIEU, null), DONG_PHIEU)
  assert.deepEqual(boSungDongChiCoTrenDon(DONG_PHIEU, {}), DONG_PHIEU)
  assert.deepEqual(boSungDongChiCoTrenDon(DONG_PHIEU, { items: [DON.items[0]] }), DONG_PHIEU)
  assert.deepEqual(boSungDongChiCoTrenDon([], DON).length, 2)
})

test('đơn có hai dòng cùng mã: một dòng bảng, cộng số lượng và thành tiền', () => {
  const don = { items: [
    { item_code: 'X', item_name: 'X', uom: 'Cái', qty: 2, rate: 100, amount: 200, delivered_qty: 1 },
    { item_code: 'X', item_name: 'X', uom: 'Cái', qty: 3, rate: 100, amount: 300, delivered_qty: 0 },
  ] }
  const kq = boSungDongChiCoTrenDon([], don)
  assert.equal(kq.length, 1)
  assert.equal(kq[0].so_luong_tren_don, 5)
  assert.equal(kq[0].thanh_tien_tren_don, 500)
  assert.equal(kq[0].da_giao_tren_don, 1)
})

test('BangMatHang.vue đi qua hàm này ở cuối `dong`, không tự dựng danh sách riêng', () => {
  const vue = readFileSync(
    new URL('./components/chi-tiet/BangMatHang.vue', import.meta.url), 'utf8'
  )
  assert.match(vue, /import \{ boSungDongChiCoTrenDon \} from '\.\.\/\.\.\/dong-bang-mat-hang'/)
  assert.match(vue, /return boSungDongChiCoTrenDon\(co_ban, props\.don\)/)
  assert.doesNotMatch(vue, /\n  return co_ban\n/)
})
