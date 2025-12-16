# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockQuantCountHistoryValuation(models.Model):
    """Valuation details for inventory count history."""

    _name = 'stock.quant.count.history.valuation'
    _description = 'Count History Valuation'
    _order = 'id desc'

    # === Relationship ===
    history_id = fields.Many2one(
        comodel_name='stock.quant.count.history',
        string='Count History',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        related='history_id.company_id',
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        related='history_id.product_id',
        store=True,
        readonly=True,
    )

    # === Currency Configuration ===
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Company Currency',
        compute='_compute_currencies',
        store=True,
    )
    currency_usd_id = fields.Many2one(
        comodel_name='res.currency',
        string='USD Currency',
        compute='_compute_currencies',
        store=True,
    )
    exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(16, 6),
        help='Exchange rate at the moment of count (Company Currency / USD)',
    )

    # === Snapshot Values (at count moment) ===
    snapshot_unit_cost = fields.Monetary(
        string='Unit Cost',
        currency_field='currency_id',
        help='Product cost at the moment of count',
    )
    snapshot_unit_cost_usd = fields.Monetary(
        string='Unit Cost (USD)',
        currency_field='currency_usd_id',
    )
    snapshot_cost_method = fields.Selection(
        selection=[
            ('standard', 'Standard Price'),
            ('fifo', 'FIFO'),
            ('average', 'Average Cost'),
            ('last', 'Last Purchase Price'),
        ],
        string='Cost Method',
        help='Product cost method at the moment of count',
    )

    # === Calculated Snapshot Values ===
    snapshot_on_hand_value = fields.Monetary(
        string='On Hand Value',
        currency_field='currency_id',
        compute='_compute_snapshot_values',
        store=True,
        help='Value of on-hand quantity at count moment',
    )
    snapshot_on_hand_value_usd = fields.Monetary(
        string='On Hand Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_snapshot_values',
        store=True,
    )
    snapshot_counted_value = fields.Monetary(
        string='Counted Value',
        currency_field='currency_id',
        compute='_compute_snapshot_values',
        store=True,
        help='Value of counted quantity at count moment',
    )
    snapshot_counted_value_usd = fields.Monetary(
        string='Counted Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_snapshot_values',
        store=True,
    )
    snapshot_difference_value = fields.Monetary(
        string='Snapshot Difference Value',
        currency_field='currency_id',
        compute='_compute_snapshot_values',
        store=True,
        help='Estimated value difference based on snapshot cost',
    )
    snapshot_difference_value_usd = fields.Monetary(
        string='Snapshot Difference Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_snapshot_values',
        store=True,
    )

    # === SVL Integration (for Applied counts) ===
    valuation_layer_ids = fields.Many2many(
        comodel_name='stock.valuation.layer',
        relation='count_history_valuation_svl_rel',
        column1='valuation_id',
        column2='svl_id',
        string='Valuation Layers',
        readonly=True,
        help='Valuation layers created when count was applied',
    )
    has_svl = fields.Boolean(
        string='Has Valuation Layers',
        compute='_compute_svl_values',
        store=True,
    )
    svl_total_value = fields.Monetary(
        string='SVL Total Value',
        currency_field='currency_id',
        compute='_compute_svl_values',
        store=True,
        help='Actual value from Stock Valuation Layers',
    )
    svl_total_value_usd = fields.Monetary(
        string='SVL Total Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_svl_values',
        store=True,
    )

    # === Final Values (SVL if available, else Snapshot) ===
    value_source = fields.Selection(
        selection=[
            ('snapshot', 'Estimated (Snapshot)'),
            ('svl', 'Actual (from Valuation Layer)'),
            ('none', 'No Difference'),
        ],
        string='Value Source',
        compute='_compute_final_values',
        store=True,
        help='Source of the final valuation',
    )
    final_difference_value = fields.Monetary(
        string='Difference Value',
        currency_field='currency_id',
        compute='_compute_final_values',
        store=True,
        help='Final difference value (from SVL if available, else snapshot)',
    )
    final_difference_value_usd = fields.Monetary(
        string='Difference Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_final_values',
        store=True,
    )
    is_loss = fields.Boolean(
        string='Is Loss',
        compute='_compute_final_values',
        store=True,
        help='True if this count resulted in a loss',
    )

    # === Compute Methods ===

    @api.depends('company_id')
    def _compute_currencies(self):
        """Compute company currency and USD currency."""
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for record in self:
            record.currency_id = record.company_id.currency_id
            record.currency_usd_id = usd

    @api.depends(
        'snapshot_unit_cost',
        'snapshot_unit_cost_usd',
        'history_id.quantity_on_hand',
        'history_id.quantity_counted',
        'history_id.difference',
    )
    def _compute_snapshot_values(self):
        """Compute snapshot-based values."""
        for record in self:
            history = record.history_id
            cost = record.snapshot_unit_cost or 0.0
            cost_usd = record.snapshot_unit_cost_usd or 0.0

            record.snapshot_on_hand_value = history.quantity_on_hand * cost
            record.snapshot_on_hand_value_usd = history.quantity_on_hand * cost_usd
            record.snapshot_counted_value = history.quantity_counted * cost
            record.snapshot_counted_value_usd = history.quantity_counted * cost_usd
            record.snapshot_difference_value = history.difference * cost
            record.snapshot_difference_value_usd = history.difference * cost_usd

    @api.depends('valuation_layer_ids', 'valuation_layer_ids.value')
    def _compute_svl_values(self):
        """Compute SVL-based values."""
        for record in self:
            svl_records = record.valuation_layer_ids
            record.has_svl = bool(svl_records)
            if svl_records:
                record.svl_total_value = sum(svl_records.mapped('value'))
                # USD value: use gg_cost_dolarization field if available
                if hasattr(svl_records, 'total_cost_usd'):
                    record.svl_total_value_usd = sum(
                        svl_records.mapped('total_cost_usd')
                    )
                else:
                    # Fallback: convert using exchange rate
                    rate = record.exchange_rate or 1.0
                    if rate:
                        record.svl_total_value_usd = record.svl_total_value / rate
                    else:
                        record.svl_total_value_usd = 0.0
            else:
                record.svl_total_value = 0.0
                record.svl_total_value_usd = 0.0

    @api.depends(
        'has_svl',
        'svl_total_value',
        'svl_total_value_usd',
        'snapshot_difference_value',
        'snapshot_difference_value_usd',
        'history_id.difference',
    )
    def _compute_final_values(self):
        """Compute final values using SVL if available, else snapshot."""
        for record in self:
            diff = record.history_id.difference

            if diff == 0:
                record.value_source = 'none'
                record.final_difference_value = 0.0
                record.final_difference_value_usd = 0.0
                record.is_loss = False
            elif record.has_svl:
                record.value_source = 'svl'
                record.final_difference_value = record.svl_total_value
                record.final_difference_value_usd = record.svl_total_value_usd
                record.is_loss = record.svl_total_value < 0
            else:
                record.value_source = 'snapshot'
                record.final_difference_value = record.snapshot_difference_value
                record.final_difference_value_usd = record.snapshot_difference_value_usd
                record.is_loss = record.snapshot_difference_value < 0

    # === Business Methods ===

    def _get_usd_rate(self, date):
        """Get USD exchange rate for a given date.

        Returns the rate as Company Currency / USD.
        Falls back to the most recent rate if no rate exists for the date.
        """
        self.ensure_one()
        company_currency = self.company_id.currency_id
        usd = self.env.ref('base.USD', raise_if_not_found=False)

        if not usd:
            return 1.0

        if company_currency == usd:
            return 1.0

        # Search for rate on or before the date
        CurrencyRate = self.env['res.currency.rate']
        rate_record = CurrencyRate.search([
            ('currency_id', '=', usd.id),
            ('name', '<=', date),
            ('company_id', 'in', [self.company_id.id, False]),
        ], order='name desc', limit=1)

        if rate_record:
            # Odoo stores rates as 1 / exchange_rate
            # We need Company Currency / USD
            return 1.0 / rate_record.rate if rate_record.rate else 1.0

        # No rate found, try to get any rate
        rate_record = CurrencyRate.search([
            ('currency_id', '=', usd.id),
            ('company_id', 'in', [self.company_id.id, False]),
        ], order='name desc', limit=1)

        if rate_record:
            return 1.0 / rate_record.rate if rate_record.rate else 1.0

        # No rate at all, return 1.0 as fallback
        return 1.0

    def _get_product_cost_usd(self, product, date):
        """Get product cost in USD.

        Uses gg_cost_dolarization field if available, otherwise converts.
        """
        # Check if gg_cost_dolarization is installed
        if hasattr(product, 'standard_price_usd') and product.standard_price_usd:
            return product.standard_price_usd

        # Fallback: convert using exchange rate
        rate = self._get_usd_rate(date)
        if rate:
            return product.standard_price / rate
        return 0.0

    def action_refresh_svl(self):
        """Manually refresh SVL links."""
        for record in self:
            record._find_and_link_svl()
        return True

    def _find_and_link_svl(self):
        """Find and link related Stock Valuation Layers."""
        self.ensure_one()
        history = self.history_id

        # Only search for SVL if count was applied and had a difference
        if history.state != 'applied' or history.difference == 0:
            return

        # First, check if SVL has count_history_id field (our extension)
        SVL = self.env['stock.valuation.layer']
        if hasattr(SVL, 'count_history_id'):
            svl_records = SVL.search([
                ('count_history_id', '=', history.id),
            ])
            if svl_records:
                self.valuation_layer_ids = [(6, 0, svl_records.ids)]
                return

        # Fallback: Find by correlation
        # Time window: 30 seconds before/after count datetime
        time_from = history.count_datetime - timedelta(seconds=30)
        time_to = history.count_datetime + timedelta(seconds=30)

        domain = [
            ('product_id', '=', history.product_id.id),
            ('company_id', '=', history.company_id.id),
            ('create_date', '>=', time_from),
            ('create_date', '<=', time_to),
            ('quantity', '=', history.difference),
        ]

        svl_records = SVL.search(domain)
        if svl_records:
            self.valuation_layer_ids = [(6, 0, svl_records.ids)]
