# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    production_plan_id = fields.Many2one(
        'mrp.plan', compute='_compute_production_plan_id',
        help="Production Plan of the Manufacturing Order this line supplies "
             "components for (found by following the move's destination "
             "chain, since a supply transfer's own move isn't linked to the "
             "MO directly).")

    @api.depends('move_id.raw_material_production_id.plan_id',
                 'move_id.move_dest_ids.raw_material_production_id.plan_id')
    def _compute_production_plan_id(self):
        for line in self:
            line.production_plan_id = line.move_id._get_supply_production().plan_id

    def _get_fields_stock_barcode(self):
        """Add production_plan_id so a Batch Transfer line can show it."""
        return super()._get_fields_stock_barcode() + ['production_plan_id']

