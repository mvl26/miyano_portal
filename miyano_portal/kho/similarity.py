"""So khớp gần đúng tên, không dấu — dùng chung cho NL-7.3 (NCC) và NL-4.5
(vật tư), theo đúng US-E4.5: ngưỡng 85%, so sánh sau khi bỏ dấu tiếng Việt.

Một nơi DUY NHẤT cài thuật toán "gần giống": nếu ngưỡng hay cách chuẩn hoá đổi,
chỉ sửa ở đây, không rải rác giữa kho/ncc.py và kho/vat_tu.py.
"""

import difflib
import unicodedata

NGUONG_GAN_GIONG = 0.85


def khong_dau(value) -> str:
    """Chuẩn hoá: trim, hạ chữ thường, bỏ dấu tiếng Việt (kể cả đ/Đ, vốn
    KHÔNG decompose qua NFD như các dấu thanh/dấu phụ khác — phải thay tay)."""
    s = (value or "").strip()
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", s).lower()


def ty_le_giong(a, b) -> float:
    return difflib.SequenceMatcher(None, khong_dau(a), khong_dau(b)).ratio()


def la_trung_tuyet_doi(a, b) -> bool:
    return khong_dau(a) == khong_dau(b)


def la_gan_giong(a, b, nguong: float = NGUONG_GAN_GIONG) -> bool:
    return ty_le_giong(a, b) >= nguong


def phan_loai(a, b, nguong: float = NGUONG_GAN_GIONG) -> str | None:
    """Trả "trung" (trùng tuyệt đối, không dấu), "gan_giong" (>= ngưỡng,
    nhưng không phải trùng tuyệt đối), hoặc None (không liên quan)."""
    if la_trung_tuyet_doi(a, b):
        return "trung"
    if la_gan_giong(a, b, nguong):
        return "gan_giong"
    return None
