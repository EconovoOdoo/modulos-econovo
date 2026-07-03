# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models, tools
from datetime import datetime, timedelta, time
from collections import defaultdict
import pytz


class AttendanceSummaryAnalysis(models.Model):
    """Model to analyze comprehensive attendance including absences, late, overtime"""
    _name = 'attendance.summary.analysis'
    _description = 'Attendance Summary Analysis'
    _auto = False
    _order = 'attendance_date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    attendance_date = fields.Date(string='Date', readonly=True)
    status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'On Leave'),
        ('public_holiday', 'Public Holiday'),
        ('weekend', 'Weekend/Holiday'),
    ], string='Status', readonly=True)

    check_in_time = fields.Datetime(string='Check In', readonly=True)
    check_out_time = fields.Datetime(string='Check Out', readonly=True)
    worked_hours = fields.Float(string='Worked Hours', readonly=True)

    is_late = fields.Boolean(string='Is Late', readonly=True)
    late_minutes = fields.Float(string='Late (Minutes)', readonly=True)

    overtime_hours = fields.Float(string='Overtime (Hours)', readonly=True)
    undertime_hours = fields.Float(string='Undertime (Hours)', readonly=True)

    expected_hours = fields.Float(string='Expected Hours', readonly=True)

    def init(self):
        """Create SQL view for attendance summary"""
        tools.drop_view_if_exists(self._cr, 'attendance_summary_analysis')
        query = """
            CREATE OR REPLACE VIEW attendance_summary_analysis AS (
                WITH attendance_dates AS (
                    -- Get all dates with attendance records
                    SELECT DISTINCT
                        employee_id,
                        DATE(check_in) as attendance_date,
                        MIN(check_in) as check_in_time,
                        MAX(check_out) as check_out_time,
                        EXTRACT(EPOCH FROM (MAX(check_out) - MIN(check_in))) / 3600.0 as worked_hours
                    FROM hr_attendance
                    WHERE check_in IS NOT NULL
                    GROUP BY employee_id, DATE(check_in)
                )
                SELECT
                    ROW_NUMBER() OVER (ORDER BY employee_id, attendance_date) as id,
                    employee_id,
                    attendance_date,
                    'present' as status,
                    check_in_time,
                    check_out_time,
                    COALESCE(worked_hours, 0) as worked_hours,
                    FALSE as is_late,
                    0.0 as late_minutes,
                    CASE
                        WHEN worked_hours > 8 THEN worked_hours - 8
                        ELSE 0
                    END as overtime_hours,
                    CASE
                        WHEN worked_hours < 8 THEN 8 - worked_hours
                        ELSE 0
                    END as undertime_hours,
                    8.0 as expected_hours
                FROM attendance_dates
            )
        """
        self._cr.execute(query)

    def _get_utc_datetime_range(self, date):
        """
        Convert a local date to UTC datetime range for proper comparison.
        This ensures we query the correct date boundaries in UTC timezone.
        """
        # Get user's timezone or default to UTC
        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(tz_name)

        # Create timezone-aware datetime for start and end of day
        start_datetime = local_tz.localize(datetime.combine(date, time.min))
        end_datetime = local_tz.localize(datetime.combine(date, time.max))

        # Convert to UTC and remove timezone info (Odoo stores naive UTC datetimes)
        utc_start = start_datetime.astimezone(pytz.utc).replace(tzinfo=None)
        utc_end = end_datetime.astimezone(pytz.utc).replace(tzinfo=None)

        return utc_start, utc_end

    @api.model
    def get_attendance_summary(self, employee_ids=None, start_date=None, end_date=None):
        """
        Get comprehensive attendance summary with absences, late arrivals, overtime
        This is called from the dashboard controller
        """
        if not start_date:
            end_date = fields.Date.today()
            start_date = end_date - timedelta(days=30)

        Employee = self.env['hr.employee']
        Attendance = self.env['hr.attendance']

        # Check if hr.leave model exists (from hr_holidays module)
        has_leave_module = 'hr.leave' in self.env

        # Get employees
        if employee_ids:
            employees = Employee.browse(employee_ids)
        else:
            employees = Employee.search([('active', '=', True)])

        summary_data = []

        # Iterate through each day in the range
        current_date = start_date
        while current_date <= end_date:
            for employee in employees:
                day_data = self._analyze_employee_day(employee, current_date, has_leave_module)
                if day_data:
                    summary_data.append(day_data)
            current_date += timedelta(days=1)

        return summary_data

    def _analyze_employee_day(self, employee, date, has_leave_module=False):
        """Analyze a single employee's attendance for a single day"""
        Attendance = self.env['hr.attendance']

        # Get UTC datetime range for proper timezone handling
        utc_start, utc_end = self._get_utc_datetime_range(date)

        # Get attendance records for this day
        attendance_records = Attendance.search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', utc_start),
            ('check_in', '<=', utc_end),
        ], order='check_in')

        # Unified OFF-day determination via the shared precedence helper:
        #   personal working schedule → company weekend policy (all-unchecked =
        #   7-day week) → default Fri+Sat. A mandatory day overrides an off-day.
        off_weekdays = employee._dotbd_weekend_weekdays()
        is_mandatory_day = bool(employee._dotbd_mandatory_dates(date, date))
        is_off_day = (date.weekday() in off_weekdays) and not is_mandatory_day

        # OFF day with no attendance → Weekend. If the employee punched anyway
        # (exceptional attendance) → fall through to 'present' so the cell shows
        # P/LT, not W.
        if is_off_day and not attendance_records:
            return {
                'employee_id': employee.id,
                'employee_name': employee.name,
                'date': date,
                'status': 'weekend',
                'check_in': None,
                'check_out': None,
                'worked_hours': 0,
                'expected_hours': 0,
                'is_late': False,
                'late_minutes': 0,
                'overtime': 0,
                'undertime': 0,
            }

        # Get working schedule (drives expected hours / lateness)
        resource_calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id

        if not resource_calendar:
            # No calendar defined, assume standard 8-hour day
            expected_hours = 8.0
            expected_start_time = time(9, 0)   # 9 AM
            expected_end_time = time(18, 0)    # 6 PM
        else:
            # Find working hours for this day
            attendance_lines = resource_calendar.attendance_ids.filtered(
                lambda a: a.dayofweek == str(date.weekday())
            )

            if not attendance_lines:
                # No shift defined for this weekday. Off-days already returned
                # above; reaching here means it is a working / mandatory /
                # exceptional-attendance day with no defined shift → neutral
                # defaults so the employee cannot be marked late.
                expected_hours = 0.0
                expected_start_time = time(23, 59)
                expected_end_time = time(23, 59)

            else:
                # Normal working day — calculate expected hours, start, and end
                expected_hours = sum(
                    (line.hour_to - line.hour_from) for line in attendance_lines
                )
                expected_start_time = min(line.hour_from for line in attendance_lines)
                expected_end_float = max(line.hour_to for line in attendance_lines)
                _eh = int(expected_end_float)
                _em = int((expected_end_float - _eh) * 60)
                expected_end_time = time(_eh, _em)

        # Check for Public Holidays (company-wide time off)
        # Search by company instead of strict calendar match because public holidays
        # are typically linked to the company's default calendar, not each employee's
        # individual schedule.
        CalendarLeaves = self.env['resource.calendar.leaves']
        company_id = employee.company_id.id
        public_holidays = CalendarLeaves.search([
            ('resource_id', '=', False),  # Public holidays have no specific resource
            ('date_from', '<=', utc_end),
            ('date_to', '>=', utc_start),
            '|',
            ('calendar_id.company_id', '=', company_id),
            ('calendar_id', '=', False),
        ])
        if public_holidays:
            return {
                'employee_id': employee.id,
                'employee_name': employee.name,
                'date': date,
                'status': 'public_holiday',
                'holiday_name': public_holidays[0].name,
                'check_in': None,
                'check_out': None,
                'worked_hours': 0,
                'expected_hours': 0,
                'is_late': False,
                'late_minutes': 0,
                'overtime': 0,
                'undertime': 0,
            }

        # Check if on leave (only if hr_holidays module is installed)
        if has_leave_module:
            Leave = self.env['hr.leave']
            leave_records = Leave.search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', utc_end),
                ('date_to', '>=', utc_start),
            ])

            if leave_records:
                leave_type_rec = leave_records[0].holiday_status_id
                leave_code = leave_type_rec.leave_short_code or leave_type_rec.name[:3].upper()
                leave_category = leave_type_rec.leave_attendance_category or 'absence'
                is_mandatory = getattr(leave_type_rec, 'is_mandatory', False)
                # Mandatory days (like public holidays) are treated separately
                if is_mandatory:
                    return {
                        'employee_id': employee.id,
                        'employee_name': employee.name,
                        'date': date,
                        'status': 'mandatory_day',
                        'leave_type': leave_type_rec.name,
                        'leave_code': leave_code,
                        'leave_type_id': leave_type_rec.id,
                        'leave_category': leave_category,
                        'mandatory_name': leave_type_rec.name,  # For display
                        'check_in': None,
                        'check_out': None,
                        'worked_hours': 0,
                        'expected_hours': 0,
                        'is_late': False,
                        'late_minutes': 0,
                        'overtime': 0,
                        'undertime': 0,
                    }
                else:
                    return {
                        'employee_id': employee.id,
                        'employee_name': employee.name,
                        'date': date,
                        'status': 'leave',
                        'leave_type': leave_type_rec.name,  # Full name for summary
                        'leave_code': leave_code,  # Short code for display
                        'leave_type_id': leave_type_rec.id,  # For grouping
                        'leave_category': leave_category,  # 'absence' or 'worked'
                        'check_in': None,
                        'check_out': None,
                        'worked_hours': 0,
                        'expected_hours': expected_hours,
                        'is_late': False,
                        'late_minutes': 0,
                        'overtime': 0,
                        'undertime': 0,
                    }

        # Analyze attendance
        if not attendance_records:
            # Absent
            return {
                'employee_id': employee.id,
                'employee_name': employee.name,
                'date': date,
                'status': 'absent',
                'check_in': None,
                'check_out': None,
                'worked_hours': 0,
                'expected_hours': expected_hours,
                'is_late': False,
                'late_minutes': 0,
                'overtime': 0,
                'undertime': expected_hours,
            }

        # Present - calculate details
        check_out = attendance_records[-1].check_out if attendance_records[-1].check_out else None

        # Sum each record's worked_hours — matches Odoo's native calculation.
        # Do NOT use (last_check_out - first_check_in) as that inflates hours
        # when there are multiple punches or breaks during the day.
        worked_hours = sum(r.worked_hours for r in attendance_records if r.check_out)

        # Check if late.
        # hour_from is stored in the calendar's own timezone, so we must convert
        # check_in (stored in UTC) to calendar.tz before comparing.
        cal_tz_name = (resource_calendar.tz if resource_calendar else None) or \
                      self.env.context.get('tz') or self.env.user.tz or 'UTC'
        cal_tz = pytz.timezone(cal_tz_name)

        if isinstance(expected_start_time, float):
            _sh = int(expected_start_time)
            _sm = int((expected_start_time - _sh) * 60)
            expected_time_obj = time(_sh, _sm)
        else:
            expected_time_obj = expected_start_time

        # Find the first check-in that falls within the working schedule window.
        # Ignore extra evening check-ins (outside working hours) — they must not
        # inflate late minutes or become the reference check-in for the day.
        regular_check_in = None
        for rec in attendance_records:
            rec_local = pytz.utc.localize(rec.check_in).astimezone(cal_tz)
            rec_time = rec_local.time()
            # Accept if the punch is before (or at) the end of the working day
            if rec_time <= expected_end_time:
                regular_check_in = rec.check_in
                break

        # Use regular check-in for late calc; fall back to first record if none found
        check_in = regular_check_in or attendance_records[0].check_in
        check_in_local = pytz.utc.localize(check_in).astimezone(cal_tz)
        check_in_time = check_in_local.time()

        # Calculate late minutes (apply tolerance from settings)
        tolerance_minutes = int(self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.late_check_in_after', default=0))
        raw_late_minutes = 0.0
        # Only mark late if the check-in is within the working day window
        if regular_check_in and check_in_time > expected_time_obj:
            check_in_datetime = datetime.combine(date, check_in_time)
            expected_datetime = datetime.combine(date, expected_time_obj)
            raw_late_minutes = (check_in_datetime - expected_datetime).total_seconds() / 60.0
        late_minutes = max(0.0, raw_late_minutes - tolerance_minutes)
        is_late = late_minutes > 0

        # Calculate overtime/undertime
        overtime = max(0, worked_hours - expected_hours)
        undertime = max(0, expected_hours - worked_hours)

        return {
            'employee_id': employee.id,
            'employee_name': employee.name,
            'date': date,
            'status': 'present',
            'check_in': check_in,
            'check_out': check_out,
            'worked_hours': round(worked_hours, 2),
            'expected_hours': expected_hours,
            'is_late': is_late,
            'late_minutes': round(late_minutes, 0),
            'overtime': round(overtime, 2),
            'undertime': round(undertime, 2),
        }

    @api.model
    def get_monthly_summary_statistics(self, start_date, end_date, employee_ids=None):
        """Get aggregated statistics for dashboard"""
        summary_data = self.get_attendance_summary(employee_ids, start_date, end_date)

        stats = {
            'total_days': 0,
            'present_days': 0,
            'absent_days': 0,
            'leave_days': 0,
            'public_holiday_days': 0,
            'late_arrivals': 0,
            'total_overtime': 0,
            'total_undertime': 0,
            'total_worked_hours': 0,
            'total_expected_hours': 0,
        }

        for record in summary_data:
            stats['total_days'] += 1

            if record['status'] == 'present':
                stats['present_days'] += 1
                stats['total_worked_hours'] += record['worked_hours']
                if record['is_late']:
                    stats['late_arrivals'] += 1
                stats['total_overtime'] += record['overtime']
                stats['total_undertime'] += record['undertime']
            elif record['status'] == 'absent':
                stats['absent_days'] += 1
            elif record['status'] == 'leave':
                stats['leave_days'] += 1
            elif record['status'] == 'public_holiday':
                stats['public_holiday_days'] += 1

            if record['status'] in ['present', 'absent']:
                stats['total_expected_hours'] += record['expected_hours']

        return stats
