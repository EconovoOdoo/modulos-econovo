# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    validation_user_id = fields.Many2one(
        related='picking_id.validation_user_id', store=True,
        string='Validated By')
