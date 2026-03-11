# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import fields, models


class MrpWorkcenter(models.Model):
    """Add a direct-USD hourly cost field to work centers.

    ``costs_hour_usd`` mirrors the role that ``product.standard_price_usd``
    (from ``gg_cost_dolarization``) plays for components: it stores an
    independently maintained USD catalogue rate for the work center that is
    used instead of multiplying the ARS rate by the company exchange rate.

    Auto-update behaviour
    ---------------------
    Whenever ``costs_hour`` (ARS) is written, ``costs_hour_usd`` is
    automatically set to ``costs_hour × rate`` where ``rate`` is the most
    recent ``res.currency.rate`` record for USD *at or before today*.
    This mirrors the identical auto-update logic in
    ``gg_cost_dolarization/models/product_template.py``.

    The field remains writable, so an operator can override the computed USD
    rate when the true labour cost in USD was negotiated independently of the
    company exchange rate (edge case E10).
    """

    _inherit = 'mrp.workcenter'

    costs_hour_usd = fields.Float(
        string="Cost per hour (USD)",
        help=(
            "Hourly processing cost in USD (direct price).\n\n"
            "Auto-updated from the company exchange rate whenever "
            "'Cost per Hour' (ARS) is saved.  Can be manually overridden "
            "when the USD labour rate was negotiated independently of the "
            "exchange rate.\n\n"
            "Used by the BOM Cost Summary to populate the 'BoM Cost USD "
            "(direct)' column for operations, independently of the company "
            "exchange rate."
        ),
        store=True,
        default=0.0,
    )
    employee_costs_hour_usd = fields.Float(
        string="Employee cost per hour (USD)",
        help=(
            "Employee hourly cost in USD (direct price).\n\n"
            "Mirrors employee_costs_hour (ARS, defined by mrp_workorder).\n\n"
            "Auto-updated from the company exchange rate whenever "
            "'Employee Cost per Hour' (ARS) is saved.  Can be manually "
            "overridden.\n\n"
            "Combined with costs_hour_usd (× employee_ratio) when computing "
            "bom_cost_usd_direct for operations in the BOM Cost Summary."
        ),
        store=True,
        default=0.0,
    )

    def _get_usd_rate(self):
        """Return the most recent USD exchange rate at or before today.

        Searches rates for the current company first; if none found, falls
        back to rates with no company set (shared rates), and finally to any
        company (handles single-company setups with rates on company 1).
        """
        dolar_currency = self.env.ref('base.USD', raise_if_not_found=False)
        if not dolar_currency:
            return 0.0
        now = datetime.now()
        base_domain = [
            ('name', '<=', now),
            ('currency_id', '=', dolar_currency.id),
        ]
        # Try current company first, then shared (no company), then any
        for extra in [
            [('company_id', '=', self.env.company.id)],
            [('company_id', '=', False)],
            [],
        ]:
            rate_rec = self.env['res.currency.rate'].search(
                base_domain + extra,
                order='name desc',
                limit=1,
            )
            if rate_rec:
                return rate_rec.rate
        return 0.0

    def write(self, vals):
        """Auto-update *_usd fields when their ARS counterparts change."""
        needs_rate = 'costs_hour' in vals or 'employee_costs_hour' in vals
        if needs_rate:
            rate = self._get_usd_rate()
            if 'costs_hour' in vals:
                vals['costs_hour_usd'] = (vals.get('costs_hour') or 0.0) * rate
            if 'employee_costs_hour' in vals:
                vals['employee_costs_hour_usd'] = (
                    (vals.get('employee_costs_hour') or 0.0) * rate
                )
        return super().write(vals)
