# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    show_quantity_to_count = fields.Boolean(
        string="Show Quantity to Count",
        default=True,
        help="When enabled, the expected quantity (quantity on hand) is displayed "
             "during inventory adjustments in the Barcode app. "
             "Disable this option to force operators to perform a true blind count "
             "without seeing the system's expected quantities."
    )
