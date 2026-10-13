// Quy tắc hiển thị tên mặt hàng (chủ đầu tư 13/10/2026) — `yarn test`.

import test from 'node:test'
import assert from 'node:assert/strict'
import { ghepTenThuongGoi, maCanNap, tenMatHang, TIEU_DE_COT, KHONG_CO } from './ten-hang.js'

test('thứ tự cột cố định: Mã → Tên mặt hàng → Tên thường gọi', () => {
  assert.deepEqual(Object.values(TIEU_DE_COT), ['Mã', 'Tên mặt hàng', 'Tên thường gọi'])
})

test('ghepTenThuongGoi: nhiều tên cách nhau bằng dấu phẩy, giữ thứ tự', () => {
  assert.equal(ghepTenThuongGoi(['Ống đỏ', 'Ống EDTA']), 'Ống đỏ, Ống EDTA')
})

test('ghepTenThuongGoi: chưa có tên thì "—", không để ô trống', () => {
  assert.equal(ghepTenThuongGoi([]), KHONG_CO)
  assert.equal(ghepTenThuongGoi(undefined), KHONG_CO)
  assert.equal(ghepTenThuongGoi(['', '  ', null]), KHONG_CO)
})

test('ghepTenThuongGoi: bỏ tên lặp và khoảng trắng thừa', () => {
  assert.equal(ghepTenThuongGoi([' Ống đỏ ', 'Ống đỏ']), 'Ống đỏ')
})

test('ghepTenThuongGoi: không cắt tên dài', () => {
  const dai = 'x'.repeat(400)
  assert.equal(ghepTenThuongGoi([dai]), dai)
})

test('maCanNap: chỉ mã chưa có trong kho, không lặp, bỏ mã rỗng', () => {
  assert.deepEqual(maCanNap(['A', 'B', 'A', '', null, 'C'], { B: {} }), ['A', 'C'])
  assert.deepEqual(maCanNap(undefined, {}), [])
})

test('tenMatHang: tên trên chứng từ thắng tên hiện tại của Item', () => {
  assert.equal(tenMatHang('Tên lúc lập đơn', 'Tên mới'), 'Tên lúc lập đơn')
})

test('tenMatHang: dòng không mang tên thì lấy tên của Item, không bỏ trống', () => {
  assert.equal(tenMatHang('', 'Băng keo cá nhân'), 'Băng keo cá nhân')
  assert.equal(tenMatHang(undefined, undefined), KHONG_CO)
})
