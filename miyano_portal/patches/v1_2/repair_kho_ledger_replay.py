"""One-time repair patch — see .superpowers/sdd/2026-08-06-kho-khach-hang-phase-1/p6-desk-report.md,
section "Sự cố mất dữ liệu sổ kho".

While building the Phase 6 desk reports, a mutation-verification test saved a
`DocType` document to test a permission regression. Frappe's `DocType`
controller commits unconditionally on update (needed for schema-cache
consistency), and that commit flushed the *entire* pending test-session
transaction on this bench — including `frappe.db.delete(...)` calls against
`Customer Stock Ledger Entry` / `Customer Stock Lot Balance` that several
existing test files run in `setUp()` and expect to roll back at class
teardown. The result: the real ledger/lot-balance rows for this site's
pre-existing `Customer Stock Receipt` records were deleted for real.

`ledger.replay_vouchers_into_ledger()` is the reviewed, tested repair: it
replays every existing Receipt/Issue (submitted or cancelled) back into the
ledger, deriving everything from data still intact on those documents. It is
idempotent (dedup by `chung_tu_row`, same guard `post_lines()` always uses),
so running it on a site where the ledger is already correct is a no-op.
"""

from miyano_portal.kho.ledger import replay_vouchers_into_ledger


def execute():
    replay_vouchers_into_ledger()
