# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
import calendar
from datetime import date, datetime, timedelta

import pytz

from odoo import http
from odoo.http import request


def _export_flag_key(uid):
    return f'attendance.export.running.{uid}'


class AttendanceMainDashboard(http.Controller):

    def _is_attendance_officer(self):
        """Return True if the current user has Officer or higher access."""
        env = request.env
        return (
            env.user.has_group('dotbd_hr_zk_attendance_suite.group_attendance_officer')
            or env.user.has_group('dotbd_hr_zk_attendance_suite.group_attendance_manager')
            or env.user.has_group('dotbd_hr_zk_attendance_suite.group_attendance_admin')
        )

    @http.route('/attendance/export/status', type='json', auth='user')
    def get_export_status(self):
        """Return whether a report generation is currently running for this user."""
        uid = request.env.uid
        key = _export_flag_key(uid)
        val = request.env['ir.config_parameter'].sudo().get_param(key, '')
        if not val:
            return {'running': False}
        # Treat flags older than 30 minutes as stale (handles server crash/restart)
        try:
            ts = datetime.fromisoformat(val)
            if (datetime.now() - ts).total_seconds() > 1800:
                request.env['ir.config_parameter'].sudo().set_param(key, '')
                return {'running': False}
        except Exception:
            pass
        return {'running': True}

    @http.route('/attendance/main/dashboard/filters', type='json', auth='user')
    def get_filters(self):
        """Return departments and employees for filter dropdowns."""
        if not self._is_attendance_officer():
            # Regular employees see no filter options — data is locked to themselves
            return {'departments': [], 'employees': []}

        departments = request.env['hr.department'].sudo().search_read(
            [], ['id', 'name'], order='name asc'
        )
        employees = request.env['hr.employee'].sudo().search_read(
            [('active', '=', True)],
            ['id', 'name', 'department_id', 'device_id_num'],
            order='name asc'
        )
        # Add "Others" entry if any active employee has no department assigned
        if any(not e['department_id'] for e in employees):
            departments.append({'id': -1, 'name': 'Others (No Department)'})
        return {
            'departments': departments,
            'employees': employees,
        }

    @http.route('/attendance/main/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, month, year, department_id=False, employee_id=False):
        """Return today's summary counts and monthly attendance calendar matrix."""
        month = int(month)
        year = int(year)

        # Use the logged-in user's local timezone for "today" so the dashboard
        # never jumps to the next day for western-timezone users while they are
        # still in the previous local day (e.g. 10 PM Chicago = 3 AM UTC next day).
        _user_tz_name = request.env.user.tz or 'UTC'
        try:
            _user_tz = pytz.timezone(_user_tz_name)
            today = datetime.now(_user_tz).date()
        except Exception:
            today = date.today()

        # ── Access control: non-officers can only see their own data ──────────
        if not self._is_attendance_officer():
            own_employee = request.env['hr.employee'].sudo().search(
                [('user_id', '=', request.env.uid)], limit=1)
            if own_employee:
                employee_id = own_employee.id
            else:
                # No linked employee record — return empty data
                return {
                    'today': {
                        'total': 0, 'present': 0, 'absent': 0, 'on_leave': 0,
                        'late': 0, 'total_fine': 0.0, 'currency_symbol': '',
                        'late_enabled': False,
                    },
                    'days': [], 'month_name': '', 'calendar': [],
                }
            department_id = False  # ignore any dept filter passed by client

        # ── Penalty settings ───────────────────────────────────────────────────
        ICP = request.env['ir.config_parameter'].sudo()
        enable_late_raw = ICP.get_param(
            'dotbd_hr_zk_attendance_suite.enable_late_penalties', 'False')
        enable_late = enable_late_raw in ('True', '1', 'true')

        # ── Weekend day configuration ──────────────────────────────────────────
        # Apply the Fri+Sat (Bangladesh) default only when the user has never
        # saved settings; once saved, an empty set means "no weekends, 7-day
        # work week" and must be respected.
        _day_codes = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
        weekend_days = set()
        for _num, _code in _day_codes.items():
            _val = ICP.get_param(f'dotbd_hr_zk_attendance_suite.weekend_{_code}', 'False')
            if _val in ('True', '1', 'true'):
                weekend_days.add(_num)
        # weekend_configured: True when ANY weekend param record exists in the DB,
        # meaning settings were saved at least once (even with all boxes unchecked).
        # Using search() instead of get_param() so existing installs work without
        # requiring the user to re-save settings after upgrading the module.
        weekend_configured = bool(
            ICP.search(
                [('key', '=', 'dotbd_hr_zk_attendance_suite.weekend_fri')], limit=1
            )
        )
        if not weekend_days and not weekend_configured:
            weekend_days = {4, 5}  # Default: Friday + Saturday (Bangladesh)

        currency_symbol = request.env.company.currency_id.symbol or ''

        # ── Today's holiday + upcoming holidays ───────────────────────────────
        today_holiday_name = ''
        upcoming_holidays = []
        all_holidays = request.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('date_to', '>=', datetime(today.year, today.month, today.day)),
        ], order='date_from asc', limit=30)
        for _h in all_holidays:
            _h_start = _h.date_from.date()
            _h_end = _h.date_to.date()
            if _h_start <= today <= _h_end:
                today_holiday_name = _h.name or 'Public Holiday'
            elif _h_start > today and len(upcoming_holidays) < 2:
                upcoming_holidays.append({
                    'name': _h.name or 'Public Holiday',
                    'date': _h_start.strftime('%b %d'),
                })

        # ── Resolve department filter ───────────────────────────────────────────
        # -1 is the sentinel for "Others (No Department)" — employees with no dept.
        dept_filter = None       # domain leaf for attendance/leave records
        emp_dept_filter = None   # domain leaf for hr.employee records
        if department_id:
            dept_id_int = int(department_id)
            if dept_id_int == -1:
                dept_filter = ('employee_id.department_id', '=', False)
                emp_dept_filter = ('department_id', '=', False)
            else:
                dept_filter = ('employee_id.department_id', '=', dept_id_int)
                emp_dept_filter = ('department_id', '=', dept_id_int)

        # ── Build domain for summary view ──────────────────────────────────────
        domain = []
        if dept_filter:
            domain.append(dept_filter)
        if employee_id:
            domain.append(('employee_id', '=', int(employee_id)))

        # ── Today's summary counts ─────────────────────────────────────────────
        today_domain = domain + [('attendance_date', '=', today)]
        summary_recs = request.env['attendance.summary.analysis'].sudo().search(today_domain)

        total_employees = request.env['hr.employee'].sudo().search_count(
            [('active', '=', True)]
            + ([emp_dept_filter] if emp_dept_filter else [])
            + ([('id', '=', int(employee_id))] if employee_id else [])
        )
        present = sum(1 for r in summary_recs if r.status == 'present')

        # ── Today's on-leave count (hr.leave, include pending approvals) ──────
        # The SQL view only contains present records so we query hr.leave directly.
        on_leave = 0
        if 'hr.leave' in request.env:
            today_leave_domain = [
                ('state', 'in', ['validate', 'validate1', 'confirm']),
                ('request_date_from', '<=', today),
                ('request_date_to', '>=', today),
            ]
            if dept_filter:
                today_leave_domain.append(dept_filter)
            if employee_id:
                today_leave_domain.append(('employee_id', '=', int(employee_id)))
            on_leave = request.env['hr.leave'].sudo().search_count(today_leave_domain)

        # ── Today's late & fine ────────────────────────────────────────────────
        late_today = 0
        total_fine_today = 0.0
        if enable_late:
            late_today_domain = [('date', '=', today)]
            if dept_filter:
                late_today_domain.append(dept_filter)
            if employee_id:
                late_today_domain.append(('employee_id', '=', int(employee_id)))
            late_today_recs = request.env['late.check.in'].sudo().search(
                late_today_domain)
            late_today = len(late_today_recs)
            total_fine_today = sum(r.penalty_amount for r in late_today_recs)

        absent = total_employees - present - on_leave

        # ── Monthly calendar data ──────────────────────────────────────────────
        days_in_month = calendar.monthrange(year, month)[1]
        month_domain = domain + [
            ('attendance_date', '>=', date(year, month, 1)),
            ('attendance_date', '<=', date(year, month, days_in_month)),
        ]
        month_recs = request.env['attendance.summary.analysis'].sudo().search(month_domain)

        # Index by (employee_id, local_date).
        # The SQL view's attendance_date is DATE(check_in) in UTC which is
        # wrong for users west of UTC — a 10 PM Chicago punch becomes the next
        # UTC day.  Re-key using the check_in_time converted to the user's
        # local timezone so the calendar cell matches the user's local date.
        rec_index = {}
        for r in month_recs:
            if r.check_in_time:
                local_ci = pytz.utc.localize(r.check_in_time).astimezone(_user_tz)
                local_date = local_ci.date()
            else:
                local_date = r.attendance_date
            rec_index[(r.employee_id.id, local_date)] = r

        # ── Monthly late lookup (from hr.attendance stored fields) ────────────
        # Querying hr.attendance directly (late_check_in, is_within_tolerance are
        # stored computed fields) keeps the dashboard consistent with the Excel
        # export which also uses the work-schedule comparison — not late.check.in
        # records that depend on a cron job. This fixes P/LT mismatches.
        late_set = set()  # {(employee_id, date)}
        if enable_late:
            max_limit = int(ICP.get_param(
                'dotbd_hr_zk_attendance_suite.maximum_minutes', default=240))
            month_start_dt = datetime(year, month, 1)
            month_end_dt = datetime(year, month, days_in_month, 23, 59, 59)
            att_late_domain = [
                ('check_in', '>=', month_start_dt),
                ('check_in', '<=', month_end_dt),
                ('late_check_in', '>', 0),
                ('is_within_tolerance', '=', False),
            ]
            if dept_filter:
                att_late_domain.append(dept_filter)
            if employee_id:
                att_late_domain.append(('employee_id', '=', int(employee_id)))
            late_atts = request.env['hr.attendance'].sudo().search(att_late_domain)
            for att in late_atts:
                if max_limit > 0 and att.late_check_in > max_limit:
                    continue
                # Use local date so late markers align with local calendar cells
                local_ci = pytz.utc.localize(att.check_in).astimezone(_user_tz)
                key = (att.employee_id.id, local_ci.date())
                # Only mark the day as late if this is the FIRST check-in of the day.
                # rec_index[key].check_in_time = earliest check_in (from SQL view).
                # A diff > 60 s means this is a re-entry (after lunch etc.) — skip it
                # so a second check-in never turns an on-time day into LT.
                day_rec = rec_index.get(key)
                if day_rec and day_rec.check_in_time:
                    diff = abs((att.check_in - day_rec.check_in_time).total_seconds())
                    if diff > 60:
                        continue
                late_set.add(key)

        # ── Monthly leave lookup ────────────────────────────────────────────────
        # Build {(employee_id, date): short_code} for all leave days in the month.
        # Includes validated, awaiting-second-approval, and pending-approval leaves
        # so that employees on leave are never shown as absent.
        # leave_map stores {(employee_id, date): {'code': str, 'name': str, 'desc': str}}
        # code  = short display code (CL, SL, etc.)
        # name  = full leave type name (Annual Leave, Sick Leave, etc.)
        # desc  = leave request reason/name (shown in popup)
        leave_map = {}
        if 'hr.leave' in request.env:
            month_leave_domain = [
                ('state', 'in', ['validate', 'validate1', 'confirm']),
                ('request_date_from', '<=', date(year, month, days_in_month)),
                ('request_date_to', '>=', date(year, month, 1)),
            ]
            if dept_filter:
                month_leave_domain.append(dept_filter)
            if employee_id:
                month_leave_domain.append(('employee_id', '=', int(employee_id)))
            month_leave_recs = request.env['hr.leave'].sudo().search(month_leave_domain)
            month_start = date(year, month, 1)
            month_end = date(year, month, days_in_month)
            for lr in month_leave_recs:
                ht = lr.holiday_status_id
                code = (ht.leave_short_code if ht and ht.leave_short_code
                        else (ht.name[:2].upper() if ht else 'L'))
                leave_name = ht.name if ht else ''
                leave_desc = lr.name or ''
                lv_start = max(lr.request_date_from, month_start)
                lv_end = min(lr.request_date_to, month_end)
                d_iter = lv_start
                while d_iter <= lv_end:
                    key = (lr.employee_id.id, d_iter)
                    if key not in leave_map:
                        leave_map[key] = {
                            'code': code,
                            'name': leave_name,
                            'desc': leave_desc,
                        }
                    d_iter += timedelta(days=1)

        # Public holidays
        holiday_dates = set()
        public_holidays = request.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', '=', False),
            ('date_from', '>=', datetime(year, month, 1)),
            ('date_to', '<=', datetime(year, month, days_in_month, 23, 59, 59)),
        ])
        for h in public_holidays:
            d = h.date_from.date()
            while d <= h.date_to.date():
                if d.month == month:
                    holiday_dates.add(d)
                d = date(d.year, d.month, d.day + 1) if d.day < days_in_month else date(d.year, d.month + 1, 1) if d.month < 12 else date(d.year + 1, 1, 1)

        # Mandatory days (Odoo hr.leave.mandatory.day): dates on which employees
        # MUST work even when the weekday is normally an off-day / weekend.
        # Scopable by company, department and working schedule — matches Odoo core.
        # A mandatory day overrides the normal off-day so absence counts as Absent.
        mandatory_rules = []  # [{dates:set, dept_ids:set, calendar_id:int|False, company_id:int}]
        if 'hr.leave.mandatory.day' in request.env:
            md_recs = request.env['hr.leave.mandatory.day'].sudo().search([
                ('start_date', '<=', date(year, month, days_in_month)),
                ('end_date', '>=', date(year, month, 1)),
            ])
            for md in md_recs:
                md_dates = set()
                dd = md.start_date
                while dd <= md.end_date:
                    if dd.year == year and dd.month == month:
                        md_dates.add(dd)
                    dd += timedelta(days=1)
                if md_dates:
                    mandatory_rules.append({
                        'dates': md_dates,
                        'dept_ids': set(md.department_ids.ids),
                        'calendar_id': md.resource_calendar_id.id or False,
                        'company_id': md.company_id.id,
                    })

        # Get employees
        emp_domain = [('active', '=', True)]
        if emp_dept_filter:
            emp_domain.append(emp_dept_filter)
        if employee_id:
            emp_domain.append(('id', '=', int(employee_id)))
        employees = request.env['hr.employee'].sudo().search(emp_domain, order='name asc')

        # Build calendar rows
        calendar_data = []
        days_list = list(range(1, days_in_month + 1))

        for emp in employees:
            cal = getattr(emp, 'resource_calendar_id', None) or getattr(emp.company_id, 'resource_calendar_id', None)
            # Effective OFF weekdays for this employee: personal working schedule
            # → company weekend policy (authoritative; empty = 7-day week) → default.
            _emp_off = emp._dotbd_weekend_weekdays(weekend_days, weekend_configured)
            # Mandatory dates that apply to THIS employee (scope: company → dept → calendar)
            _emp_mandatory = set()
            if mandatory_rules:
                _emp_dept = emp.department_id.id
                _emp_cal_id = cal.id if cal else False
                for mr in mandatory_rules:
                    if mr['company_id'] and mr['company_id'] != emp.company_id.id:
                        continue
                    if mr['dept_ids'] and _emp_dept not in mr['dept_ids']:
                        continue
                    if mr['calendar_id'] and mr['calendar_id'] != _emp_cal_id:
                        continue
                    _emp_mandatory |= mr['dates']
            row = {
                'employee_id': emp.id,
                'employee_name': emp.name,
                'job_title': emp.job_title or emp.job_id.name if emp.job_id else '',
                'device_id_num': emp.device_id_num or 'No ID',
                'avatar_url': f'/web/image/hr.employee/{emp.id}/image_128',
                'days': [],
                'summary': {'P': 0, 'A': 0, 'L': 0, 'W': 0, 'H': 0, 'LT': 0, 'Late': 0},
            }
            for day in days_list:
                d = date(year, month, day)
                weekday = d.weekday()  # 0=Mon, 6=Sun
                is_weekend = weekday in _emp_off
                # A mandatory day overrides a normal off-day: the employee is
                # expected to work, so it is NOT treated as weekend.
                if is_weekend and d in _emp_mandatory:
                    is_weekend = False
                is_holiday = d in holiday_dates
                is_future = d > today
                is_late_day = (emp.id, d) in late_set

                rec = rec_index.get((emp.id, d))
                # Exceptional attendance: employee came in on a weekend or holiday —
                # show P/LT rather than W/H so the cell reflects actual presence.
                if rec and rec.status == 'present':
                    if is_late_day:
                        cell_class = 'o_cell_present_late'
                        cell_text = 'LT'
                        row['summary']['P'] += 1
                        row['summary']['LT'] += 1
                        row['summary']['Late'] += 1
                    else:
                        cell_class = 'o_cell_present'
                        cell_text = 'P'
                        row['summary']['P'] += 1
                elif is_holiday:
                    cell_class = 'o_cell_holiday'
                    cell_text = 'H'
                    row['summary']['H'] += 1
                elif is_weekend:
                    cell_class = 'o_cell_weekend'
                    cell_text = 'W'
                    row['summary']['W'] += 1
                elif is_future:
                    cell_class = 'o_cell_none'
                    cell_text = ''
                elif rec:
                    status = rec.status
                    if status == 'leave':
                        cell_class = 'o_cell_leave'
                        cell_text = 'L'
                        row['summary']['L'] += 1
                    else:
                        cell_class = 'o_cell_absent'
                        cell_text = 'A'
                        row['summary']['A'] += 1
                else:
                    # No attendance record — check if employee is on leave
                    leave_info = leave_map.get((emp.id, d))
                    if leave_info:
                        cell_class = 'o_cell_leave'
                        cell_text = leave_info['code']
                        row['summary']['L'] += 1
                    else:
                        cell_class = 'o_cell_absent'
                        cell_text = 'A'
                        row['summary']['A'] += 1

                # ── Popup detail data ──────────────────────────────────────
                check_in_str = ''
                check_out_str = ''
                worked_h = 0.0
                late_min = 0
                if rec and rec.check_in_time:
                    _local_ci = pytz.utc.localize(rec.check_in_time).astimezone(_user_tz)
                    check_in_str = _local_ci.strftime('%H:%M')
                    if rec.check_out_time:
                        _local_co = pytz.utc.localize(rec.check_out_time).astimezone(_user_tz)
                        check_out_str = _local_co.strftime('%H:%M')
                    worked_h = round(float(rec.worked_hours or 0), 2)
                    late_min = int(rec.late_minutes or 0)

                _leave_info = leave_map.get((emp.id, d)) or {}
                row['days'].append({
                    'day': day,
                    'day_name': d.strftime('%a'),
                    'cell_class': cell_class,
                    'cell_text': cell_text,
                    'is_weekend': is_weekend,
                    'is_today': d == today,
                    # Popup detail fields
                    'check_in': check_in_str,
                    'check_out': check_out_str,
                    'worked_hours': worked_h,
                    'late_minutes': late_min,
                    'leave_type': _leave_info.get('name', ''),
                    'leave_desc': _leave_info.get('desc', ''),
                })
            calendar_data.append(row)

        tolerance_minutes = int(ICP.get_param(
            'dotbd_hr_zk_attendance_suite.late_check_in_after', default=0))

        return {
            'today': {
                'total': total_employees,
                'present': present,
                'absent': absent,
                'on_leave': on_leave,
                'late': late_today,
                'total_fine': total_fine_today,
                'currency_symbol': currency_symbol,
                'late_enabled': enable_late,
            },
            'today_holiday': today_holiday_name,
            'upcoming_holidays': upcoming_holidays,
            'weekend_days': sorted(weekend_days),
            'days': days_list,
            'month_name': date(year, month, 1).strftime('%B %Y'),
            'calendar': calendar_data,
            'tolerance_minutes': tolerance_minutes,
        }
