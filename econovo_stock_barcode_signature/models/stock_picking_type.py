# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    barcode_require_signature = fields.Boolean(
        string="Require Signature",
        help="Ask for a signature from the Barcode app before transfers of "
             "this operation type can be considered complete. For a Batch "
             "Transfer, a single signature is requested and stored on every "
             "underlying transfer.",
    )

    def _get_barcode_config(self):
        """Expose barcode_require_signature to the Barcode app JS client."""
        config = super()._get_barcode_config()
        config['barcode_require_signature'] = self.barcode_require_signature
        return config
