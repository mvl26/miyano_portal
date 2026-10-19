// HSD tối thiểu theo yêu cầu khách (spec 2026-10-19 §4.6) — `yarn test`.

import test from 'node:test'
import assert from 'node:assert/strict'
import { chuanHoaThang, thangHieuLuc, nhanHsd } from './hsd.js'

test('chuanHoaThang', () => {
  assert.deepEqual(chuanHoaThang(''), { ok: true, gia_tri: null })
  assert.deepEqual(chuanHoaThang(null), { ok: true, gia_tri: null })
  assert.deepEqual(chuanHoaThang(undefined), { ok: true, gia_tri: null })
  assert.deepEqual(chuanHoaThang('3'), { ok: true, gia_tri: 3 })
  assert.deepEqual(chuanHoaThang(0), { ok: true, gia_tri: 0 })
  assert.deepEqual(chuanHoaThang(60), { ok: true, gia_tri: 60 })
  for (const x of [-1, 61, 2.5, 'abc', '2.5', NaN]) {
    const kq = chuanHoaThang(x)
    assert.equal(kq.ok, false, String(x))
    assert.equal(kq.loi, 'HSD tối thiểu phải là số tháng từ 0 đến 60.')
  }
})

test('thangHieuLuc', () => {
  assert.equal(thangHieuLuc({ hsd_toi_thieu_thang: null }, 3), 3)
  assert.equal(thangHieuLuc({ hsd_toi_thieu_thang: 0 }, 3), 0)
  assert.equal(thangHieuLuc({ hsd_toi_thieu_thang: 6 }, 3), 6)
  assert.equal(thangHieuLuc({}, null), null)
})

test('nhanHsd: chỉ hiện khi có yêu cầu dương', () => {
  assert.equal(nhanHsd(6), 'HSD tối thiểu: 6 tháng')
  for (const x of [0, null, undefined, '']) assert.equal(nhanHsd(x), '')
})
