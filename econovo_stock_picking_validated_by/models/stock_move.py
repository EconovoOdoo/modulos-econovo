# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    validation_user_id = fields.Many2one(
        'res.users', string='Validated By',
        copy=False, readonly=True,
        help="User whose session set this move to done, stamped "
             "automatically the moment it happens. Covers transfer "
             "validation as well as moves completed without a picking "
             "(e.g. inventory adjustments).")

    def _action_done(self, cancel_backorder=False):
        moves_todo = super()._action_done(cancel_backorder=cancel_backorder)
        moves_todo.write({'validation_user_id': self.env.user.id})
        return moves_todo
