# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CurrencyRateSchedule(models.Model):
    _name = 'currency.rate.schedule'
    _description = 'Currency Rate Update Schedule'
    _order = 'dayofweek, hour'

    source_id = fields.Many2one(
        'currency.rate.source',
        string='Rate Source',
        required=True,
        ondelete='cascade',
        index=True
    )
    dayofweek = fields.Selection(
        [
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        string='Day of Week',
        required=True,
        default='0',
        index=True
    )
    hour = fields.Selection(
        selection='_get_hour_selection',
        string='Hour',
        required=True,
        default='9:00'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.model
    def _get_hour_selection(self):
        """Generate hour selection options with 30-minute intervals (00:00 to 23:30)."""
        options = []
        for h in range(24):
            options.append((f'{h}:00', f'{h:02d}:00'))
            options.append((f'{h}:30', f'{h:02d}:30'))
        return options

    def name_get(self):
        """Display as 'Monday 09:00'."""
        result = []
        day_names = dict(self._fields['dayofweek'].selection)
        for record in self:
            day = day_names.get(record.dayofweek, record.dayofweek)
            # hour is now in format '9:00' or '9:30'
            hour_display = record.hour if record.hour else '00:00'
            if ':' not in hour_display:
                hour_display = f'{int(hour_display):02d}:00'
            result.append((record.id, f'{day} {hour_display}'))
        return result

    _sql_constraints = [
        ('unique_schedule', 'UNIQUE(source_id, dayofweek, hour)',
         'This day/hour combination already exists for this source!')
    ]
