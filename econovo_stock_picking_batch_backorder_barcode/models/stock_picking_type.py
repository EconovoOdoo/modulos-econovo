# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def _get_barcode_config(self):
        config = super()._get_barcode_config()
        config['create_backorder_batch'] = self.create_backorder_batch
        return config
