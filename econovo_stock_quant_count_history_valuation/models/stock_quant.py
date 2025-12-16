# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class StockQuant(models.Model):
    """Extension of stock.quant to show valuation preview."""

    _inherit = 'stock.quant'

    # === Currency Fields ===
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        compute='_compute_valuation_preview',
        store=True,
    )
    currency_usd_id = fields.Many2one(
        comodel_name='res.currency',
        string='USD',
        compute='_compute_valuation_preview',
        store=True,
    )

    # === Unit Cost Fields ===
    preview_unit_cost = fields.Monetary(
        string='Unit Cost',
        currency_field='currency_id',
        compute='_compute_valuation_preview',
        store=True,
        help='Current product cost in company currency',
    )
    preview_unit_cost_usd = fields.Monetary(
        string='Unit Cost (USD)',
        currency_field='currency_usd_id',
        compute='_compute_valuation_preview',
        store=True,
        help='Current product cost in USD',
    )

    # === Difference Value Preview ===
    preview_difference_value = fields.Monetary(
        string='Diff. Value',
        currency_field='currency_id',
        compute='_compute_valuation_preview',
        store=True,
        help='Value of the difference if adjustment is applied',
    )
    preview_difference_value_usd = fields.Monetary(
        string='Diff. Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_valuation_preview',
        store=True,
        help='Value of the difference in USD if adjustment is applied',
    )

    # === Helper to check if there's a difference ===
    has_inventory_difference = fields.Boolean(
        string='Has Difference',
        compute='_compute_valuation_preview',
        store=True,
    )
    
    # === Helper to check if it's a loss ===
    is_inventory_loss = fields.Boolean(
        string='Is Loss',
        compute='_compute_valuation_preview',
        store=True,
        help='True if the difference is negative (loss)',
    )
    
    # === Helper to check if product has cost ===
    has_product_cost = fields.Boolean(
        string='Has Cost',
        compute='_compute_valuation_preview',
        store=True,
        help='True if the product has a defined cost',
    )

    @api.depends(
        'product_id',
        'product_id.standard_price',
        'company_id',
        'quantity',
        'inventory_quantity',
        'inventory_quantity_set',
        'inventory_diff_quantity',
    )
    def _compute_valuation_preview(self):
        """Compute valuation preview fields."""
        usd = self.env.ref('base.USD', raise_if_not_found=False)

        for quant in self:
            company = quant.company_id or self.env.company
            company_currency = company.currency_id
            product = quant.product_id

            quant.currency_id = company_currency
            quant.currency_usd_id = usd

            # Get unit cost
            unit_cost = product.standard_price if product else 0.0
            quant.preview_unit_cost = unit_cost
            quant.has_product_cost = unit_cost > 0

            # Get USD cost
            unit_cost_usd = quant._get_usd_cost(product, company)
            quant.preview_unit_cost_usd = unit_cost_usd

            # Calculate difference value
            if quant.inventory_quantity_set:
                diff_qty = quant.inventory_diff_quantity or 0.0
                quant.has_inventory_difference = diff_qty != 0
                quant.is_inventory_loss = diff_qty < 0
                quant.preview_difference_value = diff_qty * unit_cost
                quant.preview_difference_value_usd = diff_qty * unit_cost_usd
            else:
                quant.has_inventory_difference = False
                quant.is_inventory_loss = False
                quant.preview_difference_value = 0.0
                quant.preview_difference_value_usd = 0.0

    def _get_usd_cost(self, product, company):
        """Get product cost in USD.

        Uses gg_cost_dolarization field if available, otherwise converts.
        """
        if not product:
            return 0.0

        # Check if gg_cost_dolarization is installed
        if hasattr(product, 'standard_price_usd') and product.standard_price_usd:
            return product.standard_price_usd

        # Fallback: convert using exchange rate
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd:
            return 0.0

        company_currency = company.currency_id
        if company_currency == usd:
            return product.standard_price

        # Get rate
        rate = self._get_usd_rate(company)
        if rate:
            return product.standard_price / rate
        return 0.0

    def _get_usd_rate(self, company):
        """Get current USD exchange rate for company."""
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd:
            return 1.0

        company_currency = company.currency_id
        if company_currency == usd:
            return 1.0

        # Search for current rate
        CurrencyRate = self.env['res.currency.rate']
        today = fields.Date.today()

        rate_record = CurrencyRate.search([
            ('currency_id', '=', usd.id),
            ('name', '<=', today),
            ('company_id', 'in', [company.id, False]),
        ], order='name desc', limit=1)

        if rate_record and rate_record.rate:
            return 1.0 / rate_record.rate

        return 1.0
