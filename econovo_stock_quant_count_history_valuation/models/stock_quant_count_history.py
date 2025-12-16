# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class StockQuantCountHistory(models.Model):
    """Extension of count history to include valuation."""

    _inherit = 'stock.quant.count.history'

    # === Relationship to Valuation ===
    valuation_id = fields.One2many(
        comodel_name='stock.quant.count.history.valuation',
        inverse_name='history_id',
        string='Valuation Details',
    )

    # === Delegated Fields for Easy Access ===
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        compute='_compute_valuation_fields',
        store=True,
    )
    currency_usd_id = fields.Many2one(
        comodel_name='res.currency',
        string='USD',
        compute='_compute_valuation_fields',
        store=True,
    )
    final_difference_value = fields.Monetary(
        string='Difference Value',
        currency_field='currency_id',
        compute='_compute_valuation_fields',
        store=True,
    )
    final_difference_value_usd = fields.Monetary(
        string='Difference Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_valuation_fields',
        store=True,
    )
    is_loss = fields.Boolean(
        string='Is Loss',
        compute='_compute_valuation_fields',
        store=True,
    )
    value_source = fields.Selection(
        selection=[
            ('snapshot', 'Estimated (Snapshot)'),
            ('svl', 'Actual (from Valuation Layer)'),
            ('none', 'No Difference'),
        ],
        string='Value Source',
        compute='_compute_valuation_fields',
        store=True,
    )

    @api.depends(
        'valuation_id',
        'valuation_id.currency_id',
        'valuation_id.currency_usd_id',
        'valuation_id.final_difference_value',
        'valuation_id.final_difference_value_usd',
        'valuation_id.is_loss',
        'valuation_id.value_source',
    )
    def _compute_valuation_fields(self):
        """Compute delegated valuation fields."""
        for record in self:
            valuation = record.valuation_id[:1] if record.valuation_id else False
            if valuation:
                record.currency_id = valuation.currency_id
                record.currency_usd_id = valuation.currency_usd_id
                record.final_difference_value = valuation.final_difference_value
                record.final_difference_value_usd = valuation.final_difference_value_usd
                record.is_loss = valuation.is_loss
                record.value_source = valuation.value_source
            else:
                record.currency_id = record.company_id.currency_id
                record.currency_usd_id = self.env.ref(
                    'base.USD', raise_if_not_found=False
                )
                record.final_difference_value = 0.0
                record.final_difference_value_usd = 0.0
                record.is_loss = False
                record.value_source = 'none'

    # === Override Create to Auto-create Valuation ===

    @api.model_create_multi
    def create(self, vals_list):
        """Create count history records and their valuations."""
        records = super().create(vals_list)
        records._create_valuation()
        return records

    def _create_valuation(self):
        """Create valuation records for count histories."""
        ValuationModel = self.env['stock.quant.count.history.valuation']

        for record in self:
            # Skip if valuation already exists
            if record.valuation_id:
                continue

            # Get product cost
            product = record.product_id
            if not product:
                continue

            # Get cost method
            cost_method = 'standard'
            if hasattr(product, 'cost_method') and product.cost_method:
                cost_method = product.cost_method
            elif hasattr(product, 'categ_id') and product.categ_id:
                cost_method = product.categ_id.property_cost_method or 'standard'

            # Create valuation record first to use its methods
            valuation = ValuationModel.create({
                'history_id': record.id,
            })

            # Get exchange rate
            count_date = record.count_datetime.date() if record.count_datetime else fields.Date.today()
            exchange_rate = valuation._get_usd_rate(count_date)

            # Get product cost
            unit_cost = product.standard_price or 0.0

            # Get USD cost
            unit_cost_usd = valuation._get_product_cost_usd(product, count_date)

            # Update valuation with cost data
            valuation.write({
                'snapshot_unit_cost': unit_cost,
                'snapshot_unit_cost_usd': unit_cost_usd,
                'snapshot_cost_method': cost_method,
                'exchange_rate': exchange_rate,
            })

            # Try to find and link SVL if count was applied
            if record.state == 'applied':
                valuation._find_and_link_svl()
