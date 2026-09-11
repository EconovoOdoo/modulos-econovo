# -*- coding: utf-8 -*-
from datetime import datetime, time

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

RULE_TYPE_TO_STEP = {
    'day': 'days',
    'week': 'weeks',
    'month': 'months',
}

# Changing these after bookings were already generated would desync the
# pattern from what was actually created; block it instead of silently
# leaving already-generated occurrences inconsistent.
_PATTERN_FIELDS = {'room_id', 'start_datetime', 'stop_datetime', 'interval', 'rule_type'}
_REGENERATE_TRIGGER_FIELDS = {'end_type', 'count', 'end_date', 'horizon_weeks'}


class RoomBookingRecurrence(models.Model):
    _name = 'room.booking.recurrence'
    _inherit = ['mail.thread']
    _description = 'Room Booking Recurrence'
    _order = 'start_datetime desc, id'

    name = fields.Char(required=True, tracking=True)
    room_id = fields.Many2one('room.room', string="Room", required=True, ondelete='cascade', tracking=True)
    office_id = fields.Many2one(related='room_id.office_id', string="Office", store=True, readonly=True)
    company_id = fields.Many2one(related='room_id.company_id', string="Company", store=True, readonly=True)
    organizer_id = fields.Many2one('res.users', string="Organizer", default=lambda self: self.env.user.id, tracking=True)

    start_datetime = fields.Datetime(
        string="First Occurrence Start", required=True, tracking=True,
        help="Start of the first occurrence. Its weekday and time of day define the recurring schedule.",
    )
    stop_datetime = fields.Datetime(
        string="First Occurrence End", required=True, tracking=True,
        help="End of the first occurrence; its duration is repeated for every occurrence.",
    )

    interval = fields.Integer(string="Repeat Every", default=1, required=True)
    rule_type = fields.Selection([
        ('day', 'Days'),
        ('week', 'Weeks'),
        ('month', 'Months'),
    ], string="Frequency", default='week', required=True, tracking=True)

    end_type = fields.Selection([
        ('forever', 'Forever'),
        ('count', 'Number of Repetitions'),
        ('end_date', 'End Date'),
    ], string="Ends", default='forever', required=True, tracking=True)
    count = fields.Integer(string="Repetitions", default=1)
    end_date = fields.Date(string="End Date")
    horizon_weeks = fields.Integer(
        string="Generation Horizon (weeks)", default=8,
        help="Only used for recurrences that never end: how many weeks ahead bookings are kept "
             "generated. A scheduled action extends this horizon automatically.",
    )

    booking_ids = fields.One2many('room.booking', 'recurrence_id', string="Bookings")
    booking_count = fields.Integer(compute='_compute_booking_count')
    active = fields.Boolean(default=True)

    @api.depends('booking_ids')
    def _compute_booking_count(self):
        for recurrence in self:
            recurrence.booking_count = len(recurrence.booking_ids)

    @api.constrains('start_datetime', 'stop_datetime')
    def _check_date_boundaries(self):
        for recurrence in self:
            if recurrence.start_datetime >= recurrence.stop_datetime:
                raise ValidationError(_(
                    "The first occurrence of %(name)s must start before it ends.",
                    name=recurrence.name,
                ))

    @api.constrains('interval')
    def _check_interval(self):
        for recurrence in self:
            if recurrence.interval <= 0:
                raise ValidationError(_(
                    "The repeat interval of %(name)s must be greater than zero.",
                    name=recurrence.name,
                ))

    @api.constrains('end_type', 'count', 'end_date')
    def _check_end_condition(self):
        for recurrence in self:
            if recurrence.end_type == 'count' and recurrence.count <= 0:
                raise ValidationError(_(
                    "The number of repetitions of %(name)s must be greater than zero.",
                    name=recurrence.name,
                ))
            if recurrence.end_type == 'end_date':
                if not recurrence.end_date:
                    raise ValidationError(_("%(name)s needs an end date.", name=recurrence.name))
                if recurrence.end_date < recurrence.start_datetime.date():
                    raise ValidationError(_(
                        "The end date of %(name)s must be on or after its first occurrence.",
                        name=recurrence.name,
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        recurrences = super().create(vals_list)
        recurrences._generate_bookings()
        return recurrences

    def write(self, vals):
        if _PATTERN_FIELDS & vals.keys():
            for recurrence in self:
                if recurrence.booking_ids:
                    raise UserError(_(
                        "You cannot change the schedule of %(name)s because it already generated "
                        "bookings. Stop it and create a new recurrence instead.",
                        name=recurrence.name,
                    ))
        res = super().write(vals)
        if _REGENERATE_TRIGGER_FIELDS & vals.keys():
            self._generate_bookings()
        return res

    def action_view_bookings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('room.room_booking_action')
        action['domain'] = [('recurrence_id', '=', self.id)]
        return action

    def action_stop(self):
        # Only drop occurrences that have not started yet; keep history intact.
        for recurrence in self:
            future_bookings = recurrence.booking_ids.filtered(lambda b: b.start_datetime > fields.Datetime.now())
            future_bookings.unlink()
        self.active = False

    def _iter_occurrence_starts(self):
        self.ensure_one()
        step = RULE_TYPE_TO_STEP[self.rule_type]
        if self.end_type == 'end_date':
            horizon = datetime.combine(self.end_date, time.max)
        elif self.end_type == 'forever':
            horizon = fields.Datetime.now() + relativedelta(weeks=self.horizon_weeks)
        else:
            horizon = None
        index = 0
        while True:
            if self.end_type == 'count' and index >= self.count:
                return
            start = self.start_datetime + relativedelta(**{step: self.interval * index})
            if horizon is not None and start > horizon:
                return
            yield start
            index += 1

    def _generate_bookings(self):
        Booking = self.env['room.booking']
        for recurrence in self:
            existing_starts = set(recurrence.booking_ids.mapped('start_datetime'))
            duration = recurrence.stop_datetime - recurrence.start_datetime
            for start in recurrence._iter_occurrence_starts():
                if start in existing_starts:
                    continue
                try:
                    with self.env.cr.savepoint():
                        Booking.create({
                            'name': recurrence.name,
                            'room_id': recurrence.room_id.id,
                            'organizer_id': recurrence.organizer_id.id,
                            'start_datetime': start,
                            'stop_datetime': start + duration,
                            'recurrence_id': recurrence.id,
                        })
                except ValidationError:
                    recurrence.message_post(body=_(
                        "Skipped the occurrence on %(date)s: the room is already booked during "
                        "that time slot.",
                        date=start,
                    ))
        return True

    @api.model
    def _cron_generate_bookings(self):
        self.search([('active', '=', True)])._generate_bookings()
