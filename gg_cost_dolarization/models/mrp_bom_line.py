from odoo import models, fields, api
from datetime import datetime

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    standard_price_usd = fields.Float(
        related="product_id.standard_price_usd",
        string="Costo Estándar en USD",
        help="Costo estándar del producto en dólares estadounidenses (USD).",
    )

    total_cost_usd = fields.Float(
        string="Costo Total en USD",
        compute='_compute_total_cost_usd',
        store=True
    )


    def _compute_total_cost_usd(self):
        for line in self:
            line.total_cost_usd = line.product_qty * line.standard_price_usd

    @api.onchange('standard_price_usd')
    def _onchange_standard_price(self):
        for line in self:
            line._compute_total_cost_usd()
