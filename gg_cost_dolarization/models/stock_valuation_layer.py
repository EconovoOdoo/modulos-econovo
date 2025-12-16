from odoo import models, fields, api
from datetime import datetime

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    standard_price_usd = fields.Float(
        string="Costo Estándar en USD",
        help="Costo estándar del producto en dólares estadounidenses (USD).",
        compute="_compute_standard_price_usd",
        store=True
    )

    total_cost_usd = fields.Float(
        string="Costo Total en USD",
        compute='_compute_total_cost_usd',
        store=True
    )

    @api.depends('unit_cost', 'create_date')
    def _compute_standard_price_usd(self):
        dolar_currency = self.env.ref('base.USD')
        for line in self:
            dolar_quotation_with_date = self.env['res.currency.rate'].search(
                [('name', '<=', line.create_date),
                 ('currency_id', '=', dolar_currency.id)],
                order='name desc',
                limit=1
            )
            line.standard_price_usd = line.unit_cost * (dolar_quotation_with_date.rate or 0.0)

    @api.depends('quantity', 'value', 'create_date')
    def _compute_total_cost_usd(self):
        dolar_currency = self.env.ref('base.USD')
        for line in self:
            dolar_quotation_with_date = self.env['res.currency.rate'].search(
                [('name', '<=', line.create_date),
                 ('currency_id', '=', dolar_currency.id)],
                order='name desc',
                limit=1
            )
            line.total_cost_usd = line.value * (dolar_quotation_with_date.rate or 0.0)
