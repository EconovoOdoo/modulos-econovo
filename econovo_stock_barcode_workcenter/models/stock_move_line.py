# -*- coding: utf-8 -*-

from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    production_plan_id = fields.Many2one(related='move_id.production_plan_id')

    def _get_fields_stock_barcode(self):
        """Add production_plan_id so a Batch Transfer line can show it."""
        return super()._get_fields_stock_barcode() + ['production_plan_id']
