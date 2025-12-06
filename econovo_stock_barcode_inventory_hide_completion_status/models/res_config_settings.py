# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    show_completion_status = fields.Boolean(
        related="company_id.show_completion_status",
        readonly=False,
        string="Show Completion Status",
    )
