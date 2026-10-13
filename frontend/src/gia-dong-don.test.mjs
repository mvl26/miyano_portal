// Dòng đơn chưa có giá hiện "Chờ báo giá", không "0 ₫" (final-fix S-7) — chạy
// bằng `node --test src/*.test.mjs` (`yarn test`).

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { NHAN_CHO_BAO_GIA, choBaoGiaTrenDon } from './gia-dong-don.js'

test('dòng "Báo giá" giá 0 trên đơn là dòng chờ báo giá', () => {
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: 0, nguon_gia_tren_don: 'Báo giá' }), true)
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: -1, nguon_gia_tren_don: 'Báo giá' }), true)
})

test('dòng đã có giá dương thì không, dù dấu gì', () => {
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: 7000, nguon_gia_tren_don: 'Báo giá' }), false)
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: 54000, nguon_gia_tren_don: 'Bảng giá' }), false)
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: 7000, yeu_cau_khop: [{}] }), false)
})

test('dòng không có trên đơn (giá null) in "—", không phải chờ báo giá', () => {
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: null, nguon_gia_tren_don: null }), false)
  assert.equal(choBaoGiaTrenDon({}), false)
  assert.equal(choBaoGiaTrenDon(null), false)
})

test('dòng cũ không dấu mà giá 0 giữ cách hiện cũ', () => {
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: 0, nguon_gia_tren_don: null }), false)
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: 0 }), false)
})

test('dòng gõ tay đã khớp mã chưa có giá vẫn là chờ báo giá', () => {
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: 0, yeu_cau_khop: [{}] }), true)
  assert.equal(choBaoGiaTrenDon({ don_gia_tren_don: null, yeu_cau_khop: [{}] }), true)
})

test('một cách gọi duy nhất', () => {
  assert.equal(NHAN_CHO_BAO_GIA, 'Chờ báo giá')
})

// Component phải DÙNG luật trên ở cả hai ô và mang dấu của dòng đơn vào dòng
// bảng — `frontend/` không render được .vue trong node, nên canh bằng nguồn.
const vue = readFileSync(
  new URL('./components/chi-tiet/BangMatHang.vue', import.meta.url), 'utf8',
)

test('BangMatHang: ô Đơn giá và Thành tiền hỏi choBaoGiaTrenDon', () => {
  assert.match(vue, /import \{[^}]*choBaoGiaTrenDon[^}]*\} from '..\/..\/gia-dong-don'/)
  assert.match(
    vue,
    /<template v-if="choBaoGiaTrenDon\(row\)">\s*<span class="tag">\{\{ NHAN_CHO_BAO_GIA \}\}<\/span>/,
    'ô Đơn giá in nhãn chờ báo giá',
  )
  assert.match(
    vue, /<template v-if="choBaoGiaTrenDon\(row\)">—<\/template>/,
    'ô Thành tiền in "—"',
  )
  assert.ok(!vue.includes('Chờ Miyano báo giá'), 'không còn cách gọi thứ hai')
})

test('BangMatHang: dòng bảng mang dấu của dòng đơn ở cả ba nguồn dòng', () => {
  assert.match(vue, /nguon_gia_tren_don: it\.nguon_gia/, 'dòng lấy từ đơn')
  assert.match(vue, /nguon_gia_tren_don: hang\?\.nguon_gia \|\| null/, 'dòng gõ tay đã khớp')
})
