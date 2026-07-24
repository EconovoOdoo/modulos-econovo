# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    production_plan_id = fields.Many2one(
        related='raw_material_production_id.plan_id',
        string='Production Plan',
        store=True,
    )
