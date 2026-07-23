# -*- coding: utf-8 -*-
from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _get_lock_date_protected_fields(self):
        """Exclude 'analytic_distribution' from the reconciliation-protected
        fields, so it stays editable on already-reconciled journal items.

        Analytic distribution is a pure management-reporting dimension: it
        never affects amounts, accounts, dates, partners or tax reports, so
        there is no accounting-integrity reason to protect it the same way
        as the genuinely fiscal/reconciliation-sensitive fields. Every other
        protected field (and the fiscal year / tax lock dates) is left
        completely untouched.
        """
        protected_fields = super()._get_lock_date_protected_fields()
        protected_fields['reconciliation'] = [
            fname for fname in protected_fields['reconciliation']
            if fname != 'analytic_distribution'
        ]
        return protected_fields
