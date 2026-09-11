# -*- coding: utf-8 -*-
from odoo import fields, models


class RoomBooking(models.Model):
    _inherit = 'room.booking'

    recurrence_id = fields.Many2one(
        'room.booking.recurrence',
        string="Recurrence",
        ondelete='cascade',
        readonly=True,
        index=True,
        help="Recurrence that generated this booking automatically, if any.",
    )
