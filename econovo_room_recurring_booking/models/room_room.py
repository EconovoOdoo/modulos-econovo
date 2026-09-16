# -*- coding: utf-8 -*-
from odoo import api, fields, models


class RoomRoom(models.Model):
    _inherit = 'room.room'

    busy_until = fields.Datetime(
        string="Busy Until",
        compute='_compute_busy_until',
        help="End of the booking currently occupying the room, if any. Unlike "
             "Next Booking Start, this ignores later bookings separated by a "
             "free gap (e.g. a weekly recurring meeting), so it always reflects "
             "when the current occupation actually ends.",
    )

    @api.depends('room_booking_ids.start_datetime', 'room_booking_ids.stop_datetime')
    def _compute_busy_until(self):
        now = fields.Datetime.now()
        current_stop_by_room = dict(self.env['room.booking']._read_group(
            [('start_datetime', '<=', now), ('stop_datetime', '>=', now), ('room_id', 'in', self.ids)],
            ['room_id'],
            ['stop_datetime:max'],
        ))
        for room in self:
            room.busy_until = current_stop_by_room.get(room)
