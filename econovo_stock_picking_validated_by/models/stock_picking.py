# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    validation_user_id = fields.Many2one(
        'res.users', string='Validated By',
        copy=False, readonly=True,
        help="User whose session validated this transfer, stamped "
             "automatically the moment it is set to done.")

    def _action_done(self):
        res = super()._action_done()
        self.write({'validation_user_id': self.env.user.id})
        return res
