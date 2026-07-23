# Account Analytic Distribution Editable on Reconciled Entries

Allows editing the Analytic Distribution of an `account.move.line` even
after the journal entry has been reconciled.

## The problem

`account.move.line._get_lock_date_protected_fields()` returns a set of
fields protected against edits once a line is reconciled
(`_check_reconciliation()`). On this Odoo.sh build, `analytic_distribution`
ended up included in that `reconciliation` set, so changing the analytic tag
of an already-reconciled bill/invoice raises:

> "You cannot do this modification on a reconciled journal entry. You can
> just change some non legal fields or you must unreconcile first."

This is stricter than necessary: the analytic distribution is a pure
management-reporting dimension. It has no effect on amounts, accounts,
dates, partners, currencies or tax reports, so there is no
accounting-integrity reason to protect it the same way as the genuinely
sensitive fields.

## The fix

This module overrides `_get_lock_date_protected_fields()` to remove
`analytic_distribution` from the `reconciliation` set only. Every other
protection is left exactly as it was:

- The fiscal year lock date and tax lock date checks are untouched.
- Every other reconciliation-protected field (`account_id`, `date`,
  `balance`, `amount_currency`, `currency_id`, `partner_id`) is still fully
  protected.

This module never breaks, recreates or otherwise touches reconciliation
state — it only widens which fields remain editable on an already-reconciled
line.

## Uninstalling

Uninstalling this module restores the original (stricter) behavior with no
side effects, since it makes no data model changes.
