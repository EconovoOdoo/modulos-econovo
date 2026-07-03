# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
import logging
import pytz
from datetime import datetime, timedelta
from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    """Inherit the module to add late check-in tracking with tolerance"""
    _inherit = 'hr.attendance'

    late_check_in = fields.Integer(
        string="Actual Late Time (Minutes)",
        compute="_compute_late_check_in",
        help="This shows the actual duration of the employee's tardiness (without tolerance).",
        store=True)

    tolerance_late_time = fields.Integer(
        string="Counted Late Time (Minutes)",
        compute="_compute_tolerance_late_time",
        help="Late time after applying tolerance settings. 0 means within tolerance limit.",
        store=True)

    is_within_tolerance = fields.Boolean(
        string="Within Tolerance",
        compute="_compute_tolerance_late_time",
        help="True if the employee is within the late tolerance limit.",
        store=True)

    late_check_in_id = fields.Many2one(
        'late.check.in',
        string="Late Check-in Record",
        help="Related late check-in record if created")

    # ZK Machine Integration
    zk_punch_ids = fields.One2many(
        'zk.machine.attendance', 'hr_attendance_id',
        string='Device Punches',
        help='Raw punch records from biometric device that contributed to this attendance')

    zk_punch_count = fields.Integer(
        string='Punch Count',
        compute='_compute_zk_punch_count',
        store=True,
        help='Number of device punches linked to this attendance')

    attendance_source = fields.Selection([
        ('biometric', 'Biometric Device'),
        ('mobile_app', 'Mobile App'),
        ('web', 'Web Browser'),
        ('manual', 'Manual Entry'),
        ('system', 'System Generated')
    ], string='Attendance Source', compute='_compute_attendance_source', store=True,
       help='Source of this attendance record')

    # ── Source tracking fields (written by OdooHub / other mobile APIs) ───────
    # These are defined here so they exist even when odoo_messenger_api is not
    # installed.  Independent module — no cross-dependency.
    in_browser = fields.Char(
        string='Check-in Source',
        help='Browser or app name used for check-in (e.g. "Odoo Messenger App")')
    out_browser = fields.Char(
        string='Check-out Source',
        help='Browser or app name used for check-out (e.g. "Odoo Messenger App")')
    in_mode = fields.Char(
        string='Check-in Mode',
        help='Mode used for check-in (e.g. "manual")')
    out_mode = fields.Char(
        string='Check-out Mode',
        help='Mode used for check-out (e.g. "manual")')

    # ── Display helpers ───────────────────────────────────────────────────────
    attendance_source_icon = fields.Html(
        string='Source', compute='_compute_attendance_source_icon', store=False,
        help='Colored badge showing attendance source')

    checkin_distance = fields.Float(
        string='Check-in Distance (m)', compute='_compute_checkin_distance',
        store=True, digits=(10, 1),
        help='Distance in meters between check-in GPS and nearest ZK device')

    # ── GPS / Location fields (for Attendance Map) ──────────────────────────
    in_latitude = fields.Float(
        string='Check-in Latitude', digits=(10, 7),
        help='GPS latitude when employee checked in')
    in_longitude = fields.Float(
        string='Check-in Longitude', digits=(10, 7),
        help='GPS longitude when employee checked in')
    out_latitude = fields.Float(
        string='Check-out Latitude', digits=(10, 7),
        help='GPS latitude when employee checked out')
    out_longitude = fields.Float(
        string='Check-out Longitude', digits=(10, 7),
        help='GPS longitude when employee checked out')
    has_checkin_location = fields.Boolean(
        string='Has Check-in Location', compute='_compute_has_location', store=True)
    has_checkout_location = fields.Boolean(
        string='Has Check-out Location', compute='_compute_has_location', store=True)

    @api.depends('in_latitude', 'in_longitude', 'out_latitude', 'out_longitude')
    def _compute_has_location(self):
        for rec in self:
            rec.has_checkin_location = bool(rec.in_latitude and rec.in_longitude)
            rec.has_checkout_location = bool(rec.out_latitude and rec.out_longitude)

    # ── Safety-net field ──────────────────────────────────────────────────────
    # Prevents JS crash from stale column_invisible="(bool(not auto_punch_out))"
    # references left in the database by uninstalled / third-party modules.
    # Always False, no behaviour change.
    auto_punch_out = fields.Boolean(
        string='Auto Punch Out',
        compute='_compute_auto_punch_out',
        store=False,
        help='Safety-net field: always False. Prevents JS crash from stale '
             'view references left by uninstalled modules.')

    @api.depends()
    def _compute_auto_punch_out(self):
        for rec in self:
            rec.auto_punch_out = False

    @api.depends('zk_punch_ids')
    def _compute_zk_punch_count(self):
        """Count the number of ZK punches linked to this attendance"""
        for rec in self:
            rec.zk_punch_count = len(rec.zk_punch_ids)

    @api.depends('zk_punch_ids', 'in_browser')
    def _compute_attendance_source(self):
        """Determine the source of attendance record.

        Detection priority:
        1. Biometric device — has linked zk.machine.attendance punches
        2. Mobile App — in_browser contains 'Messenger' / 'OdooHub' / 'Mobile'
        3. Web Browser — in_browser is set but not a mobile app
        4. Manual Entry — fallback
        """
        for rec in self:
            if rec.zk_punch_ids:
                rec.attendance_source = 'biometric'
            elif rec.in_browser and any(
                kw in (rec.in_browser or '')
                for kw in ('Messenger', 'OdooHub', 'Mobile', 'mobile', 'Flutter')
            ):
                rec.attendance_source = 'mobile_app'
            elif rec.in_browser:
                rec.attendance_source = 'web'
            else:
                rec.attendance_source = 'manual'

    def _compute_attendance_source_icon(self):
        """Render a colored badge showing where the punch came from."""
        for rec in self:
            src = rec.attendance_source
            if src == 'biometric':
                rec.attendance_source_icon = (
                    '<span style="background:#7c7cff;color:#fff;border-radius:8px;'
                    'padding:2px 8px;font-size:11px;">🔐 ZK Device</span>'
                )
            elif src == 'mobile_app':
                rec.attendance_source_icon = (
                    '<span style="background:#28a745;color:#fff;border-radius:8px;'
                    'padding:2px 8px;font-size:11px;">📱 Mobile App</span>'
                )
            elif src == 'web':
                rec.attendance_source_icon = (
                    '<span style="background:#ffc107;color:#333;border-radius:8px;'
                    'padding:2px 8px;font-size:11px;">🌐 Web</span>'
                )
            elif src == 'system':
                rec.attendance_source_icon = (
                    '<span style="background:#6c757d;color:#fff;border-radius:8px;'
                    'padding:2px 8px;font-size:11px;">⚙️ System</span>'
                )
            else:
                rec.attendance_source_icon = (
                    '<span style="background:#6c757d;color:#fff;border-radius:8px;'
                    'padding:2px 8px;font-size:11px;">✏️ Manual</span>'
                )

    @api.depends('in_latitude', 'in_longitude')
    def _compute_checkin_distance(self):
        """Calculate distance between check-in GPS and nearest ZK device."""
        import math
        for rec in self:
            if not (rec.in_latitude and rec.in_longitude):
                rec.checkin_distance = 0
                continue
            devices = self.env['biometric.device.details'].sudo().search([
                ('latitude', '!=', 0), ('longitude', '!=', 0),
            ])
            if not devices:
                rec.checkin_distance = 0
                continue
            min_dist = float('inf')
            for dev in devices:
                lat1, lon1 = math.radians(rec.in_latitude), math.radians(rec.in_longitude)
                lat2, lon2 = math.radians(dev.latitude), math.radians(dev.longitude)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
                c = 2 * math.asin(math.sqrt(a))
                dist = 6371000 * c  # meters
                if dist < min_dist:
                    min_dist = dist
            rec.checkin_distance = round(min_dist, 1)

    @api.depends('check_in', 'employee_id.resource_calendar_id.attendance_ids')
    def _compute_late_check_in(self):
        """Calculate actual late check-in minutes without applying tolerance.

        Only the FIRST check-in of the day is ever counted as late.
        Subsequent check-ins (after a check-out and re-entry) always get
        late_check_in = 0 so they never generate a late penalty.
        """
        # Pre-compute first check-in per (employee, local_date) for the whole
        # batch — one query per unique employee+day, not one per record.
        _user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        first_map = self._first_checkin_map()

        for rec in self:
            rec.late_check_in = 0
            if not rec.check_in or not rec.employee_id:
                continue

            # Skip late calculation for non-first punches
            local_date = pytz.utc.localize(rec.check_in).astimezone(_user_tz).date()
            first_ci = first_map.get((rec.employee_id.id, local_date))
            if first_ci and abs((rec.check_in - first_ci).total_seconds()) > 60:
                continue

            # Get resource calendar from employee or contract
            calendar = None
            # Try to get calendar from current contract
            try:
                if hasattr(rec.employee_id, '_get_contracts'):
                    contracts = rec.employee_id._get_contracts(rec.check_in.date())
                    if contracts and rec.employee_id.id in contracts:
                        contract_versions = contracts[rec.employee_id.id]
                        if contract_versions and hasattr(contract_versions, 'resource_calendar_id'):
                            calendar = contract_versions.resource_calendar_id
            except Exception as e:
                _logger.debug("Could not get contract calendar for %s: %s", rec.employee_id.name, e)
            
            if not calendar:
                calendar = rec.employee_id.resource_calendar_id
            if not calendar:
                calendar = rec.employee_id.company_id.resource_calendar_id

            if not calendar:
                continue

            # Convert check_in using the calendar's timezone (same tz as hour_from).
            # calendar.tz takes priority because hour_from is stored in calendar.tz.
            # This matches the priority order used by Odoo 19's _get_tz().
            cal_tz_name = (calendar.tz
                           or rec.employee_id.tz
                           or rec.employee_id.company_id.resource_calendar_id.tz
                           or 'UTC')
            tz_obj = pytz.timezone(cal_tz_name) if cal_tz_name in pytz.all_timezones else pytz.utc
            dt_local = pytz.utc.localize(rec.check_in).astimezone(tz_obj)
            local_weekday = str(dt_local.weekday())

            # Find the earliest start time among all schedule lines for this weekday.
            # Avoids day_period=='morning' filter which silently skips full-day lines.
            day_schedules = [s for s in calendar.attendance_ids
                             if s.dayofweek == local_weekday]
            if not day_schedules:
                continue
            schedule = min(day_schedules, key=lambda s: s.hour_from)

            str_time = dt_local.strftime("%H:%M")
            check_in_date = datetime.strptime(str_time, "%H:%M").time()
            start_date = datetime.strptime(
                '{0:02.0f}:{1:02.0f}'.format(*divmod(
                    schedule.hour_from * 60, 60)), "%H:%M").time()

            check_in_td = timedelta(hours=check_in_date.hour, minutes=check_in_date.minute)
            start_date_td = timedelta(hours=start_date.hour, minutes=start_date.minute)

            if check_in_td > start_date_td:
                final = check_in_td - start_date_td
                rec.late_check_in = int(final.total_seconds() / 60)

    @api.depends('late_check_in')
    def _compute_tolerance_late_time(self):
        """Calculate late time after applying tolerance settings."""
        for rec in self:
            # Get tolerance parameter from system configuration
            minutes_after = int(self.env['ir.config_parameter'].sudo().get_param(
                'dotbd_hr_zk_attendance_suite.late_check_in_after', default=0))

            if rec.late_check_in > minutes_after:
                rec.tolerance_late_time = rec.late_check_in - minutes_after
                rec.is_within_tolerance = False
            else:
                rec.tolerance_late_time = 0
                rec.is_within_tolerance = True

    @api.model
    def create_late_check_in_records(self):
        """Function creates records in late.check.in model for employees who were late
        This is called by cron job or manually"""
        max_limit = int(self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.maximum_minutes', default=240))

        enable_penalties = self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.enable_late_penalties', default='True') in ('True', 'true', '1', True)

        if not enable_penalties:
            return

        # Get existing late check-in records
        existing_late_records = self.env['late.check.in'].sudo().search([])
        existing_attendance_ids = set(existing_late_records.mapped('attendance_id.id'))

        # Get all attendance records without late check-in record
        attendance_records = self.sudo().search([
            ('check_in', '!=', False),
            ('late_check_in', '>', 0),
        ])

        # Pre-compute the first check-in of each day per employee so that only
        # the first punch can ever be penalised.  Subsequent re-entries (after
        # lunch, floor changes, etc.) are skipped even if their late_check_in > 0.
        _user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        first_map = attendance_records._first_checkin_map()

        for rec in attendance_records:
            # Skip if within tolerance
            if rec.is_within_tolerance:
                continue

            # Skip if exceeds maximum limit (considered absent instead of late)
            if max_limit > 0 and rec.late_check_in > max_limit:
                continue

            # Skip if this is not the first check-in of the day
            local_date = pytz.utc.localize(rec.check_in).astimezone(_user_tz).date()
            first_ci = first_map.get((rec.employee_id.id, local_date))
            if first_ci and abs((rec.check_in - first_ci).total_seconds()) > 60:
                continue

            record_data = {
                'employee_id': rec.employee_id.id,
                'late_minutes': rec.tolerance_late_time,
                'actual_late_minutes': rec.late_check_in,
                'date': rec.check_in.date(),
                'attendance_id': rec.id,
            }

            if rec.id not in existing_attendance_ids:
                # Create new late check-in record
                late_record = self.env['late.check.in'].sudo().create(record_data)
                rec.late_check_in_id = late_record.id
            else:
                # Update existing record
                existing_record = existing_late_records.filtered(
                    lambda x: x.attendance_id.id == rec.id
                )
                if existing_record:
                    existing_record.write(record_data)

    @api.model
    def late_check_in_records(self):
        """Alias method for backward compatibility with employee_late_check_in module
        Calls create_late_check_in_records() method"""
        return self.create_late_check_in_records()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_late_check_in()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'check_in' in vals or 'employee_id' in vals:
            self._sync_late_check_in()
        return result

    def _first_checkin_map(self):
        """Return {(employee_id, local_date): earliest_check_in_utc} for self.

        Used by _sync_late_check_in and create_late_check_in_records to
        determine which attendance record is the first punch of the day so
        that only the first punch is ever counted as late.
        """
        _user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        emp_dates = set()
        for rec in self:
            if rec.check_in and rec.employee_id:
                local_date = pytz.utc.localize(rec.check_in).astimezone(_user_tz).date()
                emp_dates.add((rec.employee_id.id, local_date))

        result = {}
        for emp_id, local_date in emp_dates:
            day_start = _user_tz.localize(
                datetime.combine(local_date, datetime.min.time())
            ).astimezone(pytz.utc).replace(tzinfo=None)
            day_end = _user_tz.localize(
                datetime.combine(local_date, datetime.max.time().replace(microsecond=0))
            ).astimezone(pytz.utc).replace(tzinfo=None)
            first = self.env['hr.attendance'].sudo().search([
                ('employee_id', '=', emp_id),
                ('check_in', '>=', day_start),
                ('check_in', '<=', day_end),
            ], order='check_in asc', limit=1)
            if first:
                result[(emp_id, local_date)] = first.check_in
        return result

    def _sync_late_check_in(self):
        """Create or update late.check.in records for attendance records in self.

        Called immediately on create/write so the dashboard reflects late
        status in real time — the daily cron remains a safety net only.
        Only the FIRST check-in of the day counts as late; subsequent
        check-ins (re-entries after lunch etc.) are never penalised.
        """
        enable_penalties = self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.enable_late_penalties', default='True'
        ) in ('True', 'true', '1', True)
        if not enable_penalties:
            return

        max_limit = int(self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.maximum_minutes', default=240))

        _user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        first_map = self._first_checkin_map()

        existing = self.env['late.check.in'].sudo().search([
            ('attendance_id', 'in', self.ids)
        ])
        existing_by_att = {r.attendance_id.id: r for r in existing}

        to_unlink = self.env['late.check.in'].sudo()
        for rec in self:
            if not rec.check_in or not rec.employee_id:
                continue

            # Only the first punch of the day can be late
            local_date = pytz.utc.localize(rec.check_in).astimezone(_user_tz).date()
            first_ci = first_map.get((rec.employee_id.id, local_date))
            if first_ci and abs((rec.check_in - first_ci).total_seconds()) > 60:
                # Subsequent check-in — remove any stale late record and skip
                if rec.id in existing_by_att:
                    to_unlink |= existing_by_att[rec.id]
                continue

            if rec.is_within_tolerance or (max_limit > 0 and rec.late_check_in > max_limit):
                if rec.id in existing_by_att:
                    to_unlink |= existing_by_att[rec.id]
                continue

            record_data = {
                'employee_id': rec.employee_id.id,
                'late_minutes': rec.tolerance_late_time,
                'actual_late_minutes': rec.late_check_in,
                'date': fields.Date.to_date(rec.check_in),
                'attendance_id': rec.id,
            }
            if rec.id in existing_by_att:
                existing_by_att[rec.id].write(record_data)
            else:
                late = self.env['late.check.in'].sudo().create(record_data)
                rec.late_check_in_id = late.id

        if to_unlink:
            to_unlink.unlink()

    def unlink(self):
        """Override the unlink method to delete corresponding records in late.check.in model"""
        late_records_to_delete = self.env['late.check.in'].sudo().search([
            ('attendance_id', 'in', self.ids)
        ])
        late_records_to_delete.unlink()
        return super().unlink()

    def action_auto_close_at_shift_end(self):
        """Manager-triggered bulk auto-close: sets check_out on each selected
        open record using the shift-aware helper.

        Usable from the 'Open Attendance (No Check-Out)' list view via the
        action menu. Silently skips records that already have a check_out.
        """
        helper = self.env['biometric.device.details']
        closed = 0
        skipped = 0
        for rec in self:
            if rec.check_out:
                skipped += 1
                continue
            try:
                helper._close_open_record_at_shift_end(rec, rec.employee_id)
                closed += 1
            except Exception as e:
                _logger.warning(
                    "Manual auto-close failed for attendance %s: %s", rec.id, e)
                skipped += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Auto-Close at Shift End',
                'message': f'Closed {closed} record(s). Skipped {skipped}.',
                'type': 'success' if closed else 'warning',
                'sticky': False,
            },
        }
