# -*- coding: utf-8 -*-

from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    production_plan_id = fields.Many2one(
        'mrp.plan', related='move_id.group_id.mrp_production_ids.plan_id',
        help="Production Plan of the Manufacturing Order sharing this "
             "line's procurement group.")

    def _get_fields_stock_barcode(self):
        """Add production_plan_id so a Batch Transfer line can show it."""
        return super()._get_fields_stock_barcode() + ['production_plan_id']


