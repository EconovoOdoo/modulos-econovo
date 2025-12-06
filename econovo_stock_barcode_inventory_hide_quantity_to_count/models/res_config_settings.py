# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    show_quantity_to_count = fields.Boolean(
        string="Show Quantity to Count",
        related="company_id.show_quantity_to_count",
        readonly=False,
        help="When enabled, the expected quantity (quantity on hand) is displayed "
             "during inventory adjustments in the Barcode app. "
             "Disable this option to force operators to perform a true blind count "
             "without seeing the system's expected quantities."
    )
