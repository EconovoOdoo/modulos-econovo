# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class BaseAutomation(models.Model):
    _inherit = 'base.automation'

    kiosk_managed_model = fields.Char(
        string="Kiosk Managed Model",
        index=True,
        help="Technical field. When set, this Automated Action was created "
             "and is fully managed by the Kiosk Mode framework to notify "
             "real-time kiosk screens watching this model - do not edit or "
             "delete it manually, disable the 'Real Time' refresh mode on "
             "the relevant kiosk action(s) instead.",
    )
