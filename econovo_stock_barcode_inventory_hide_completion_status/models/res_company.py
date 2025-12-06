# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    show_completion_status = fields.Boolean(
        string="Show Completion Status",
        default=True,
        help="When enabled, inventory lines show visual feedback (green/red) "
             "indicating if the counted quantity matches the expected quantity. "
             "Disable this for blind counting where operators should not see "
             "if their count is correct.",
    )
