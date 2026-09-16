# -*- coding: utf-8 -*-
{
    'name': 'Room Recurring Booking',
    'summary': 'Keep a meeting room permanently reserved on a fixed weekly/daily/monthly schedule',
    'description': """
Room Recurring Booking
=======================

Adds a Recurrence concept on top of the Meeting Rooms app so a room can be
kept reserved on a fixed schedule (e.g. every Monday from 8:30 to 9:30 for a
weekly general meeting) without having to create every occurrence by hand.

Each recurrence generates individual room.booking records, one per
occurrence, so the app's own overlap check (room.booking._check_unique_slot)
still blocks any other booking -- from any company -- during that slot,
exactly like a manual booking would.

Recurrences without an end date keep a rolling horizon of upcoming
occurrences generated automatically via a scheduled action.

Also fixes the Rooms kanban card, which otherwise labels a room "Busy until"
the START of the NEXT booking even when that next booking is days away and
the room is actually free in between (a gap easily created by a weekly
recurrence). Adds room.room.busy_until (end of the CURRENTLY ongoing
booking, if any) and uses it instead of Next Booking Start while the room is
actually busy.
""",
    'category': 'Services/Room',
    'version': '17.0.1.0.2',
    'depends': ['room'],
    'data': [
        'security/ir.model.access.csv',
        'views/room_booking_recurrence_views.xml',
        'views/room_booking_views.xml',
        'views/room_room_views.xml',
        'views/room_menus.xml',
        'data/ir_cron_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
}
