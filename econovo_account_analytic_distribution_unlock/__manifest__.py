# -*- coding: utf-8 -*-
{
    'name': 'Account Analytic Distribution Editable on Reconciled Entries',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Allow editing the Analytic Distribution of a journal item even after it has been reconciled.',
    'description': """
Odoo protects a set of "reconciliation-sensitive" fields on
``account.move.line`` (``account_id``, ``date``, ``balance``,
``amount_currency``, ``currency_id``, ``partner_id`` as of this Odoo.sh
build) from being edited once the line is reconciled — see
``account.move.line._get_lock_date_protected_fields()`` /
``_check_reconciliation()``. On this instance, ``analytic_distribution`` has
also ended up in that protected set, so changing an entry's analytic tag on
an already-reconciled bill/invoice raises:

    "You cannot do this modification on a reconciled journal entry.
     You can just change some non legal fields or you must unreconcile first."

This is stricter than necessary: the analytic distribution is a pure
management-reporting dimension. It never affects amounts, accounts, dates,
partners, or tax reports, so it has no bearing on accounting integrity,
reconciliation matching, or fiscal reporting. There is no legitimate reason
to block it alongside the genuinely sensitive fields.

This module overrides ``_get_lock_date_protected_fields()`` to remove
``analytic_distribution`` from the ``reconciliation`` set only. Every other
protection is left completely untouched: the fiscal year lock date, the tax
lock date, and the reconciliation protection on every other field (amount,
account, date, partner, currency) all keep working exactly as before.

This does NOT touch reconciliation state in any way (it never breaks or
recreates a reconciliation) — it purely widens which fields remain editable
on an already-reconciled line.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'account',
    ],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
