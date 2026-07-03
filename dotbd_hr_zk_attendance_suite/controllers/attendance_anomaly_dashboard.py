# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit

################################################################################
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta, time
import json


class AttendanceAnomalyDashboard(http.Controller):

    @http.route('/attendance/anomaly/dashboard', type='http', auth='user', website=False)
    def attendance_anomaly_dashboard(self, start_date=None, end_date=None, **kwargs):
        """Main dashboard route with date range support"""
        # Parse date parameters if provided, otherwise use default (last 30 days)
        if start_date and end_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                # If invalid dates, fall back to default
                end_date_obj = datetime.now().date()
                start_date_obj = end_date_obj - timedelta(days=30)
        else:
            # Default: last 30 days
            end_date_obj = datetime.now().date()
            start_date_obj = end_date_obj - timedelta(days=30)

        # Get anomaly data
        dashboard_data = self._get_dashboard_data(start_date_obj, end_date_obj)

        return request.render('dotbd_hr_zk_attendance_suite.attendance_anomaly_dashboard_template', {
            'dashboard_data': dashboard_data,
            'start_date': start_date_obj,
            'end_date': end_date_obj,
            'json': json,
        })

    @http.route('/attendance/anomaly/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, start_date=None, end_date=None, **kwargs):
        """JSON endpoint for dashboard data"""
        if not start_date or not end_date:
            end_date_obj = datetime.now().date()
            start_date_obj = end_date_obj - timedelta(days=30)
        else:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

        return self._get_dashboard_data(start_date_obj, end_date_obj)

    def _get_dashboard_data(self, start_date, end_date):
        """Get all dashboard statistics and data"""
        Anomaly = request.env['attendance.anomaly.analysis']
        AttendanceSummary = request.env['attendance.summary.analysis']
        Employee = request.env['hr.employee']
        LateCheckIn = request.env['late.check.in']

        # Base domain for date range
        domain = [
            ('attendance_date', '>=', start_date),
            ('attendance_date', '<=', end_date)
        ]

        # Domain for late check-in
        late_domain = [
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ]

        # Get total counts by anomaly type
        missing_checkout_count = Anomaly.search_count(
            domain + [('anomaly_type', '=', 'missing_checkout')]
        )
        duplicate_checkin_count = Anomaly.search_count(
            domain + [('anomaly_type', '=', 'duplicate_checkin')]
        )
        missing_checkin_count = Anomaly.search_count(
            domain + [('anomaly_type', '=', 'missing_checkin')]
        )

        total_anomalies = missing_checkout_count + duplicate_checkin_count + missing_checkin_count

        # Get top 10 employees with most anomalies
        anomalies = Anomaly.search(domain)
        employee_anomaly_count = {}
        for anomaly in anomalies:
            emp_id = anomaly.employee_id.id
            if emp_id not in employee_anomaly_count:
                emp_obj = anomaly.employee_id
                employee_anomaly_count[emp_id] = {
                    'employee': emp_obj.name,
                    'device_id_num': emp_obj.device_id_num or emp_obj.barcode or 'No ID',
                    'count': 0,
                    'missing_checkout': 0,
                    'duplicate_checkin': 0,
                    'missing_checkin': 0,
                }
            employee_anomaly_count[emp_id]['count'] += 1
            if anomaly.anomaly_type == 'missing_checkout':
                employee_anomaly_count[emp_id]['missing_checkout'] += 1
            elif anomaly.anomaly_type == 'duplicate_checkin':
                employee_anomaly_count[emp_id]['duplicate_checkin'] += 1
            elif anomaly.anomaly_type == 'missing_checkin':
                employee_anomaly_count[emp_id]['missing_checkin'] += 1

        # Sort by count and get top 10
        top_employees = sorted(
            employee_anomaly_count.values(),
            key=lambda x: x['count'],
            reverse=True
        )[:10]

        # Get daily anomaly trend (last 30 days)
        daily_trend = {}
        for anomaly in anomalies:
            date_str = str(anomaly.attendance_date)
            if date_str not in daily_trend:
                daily_trend[date_str] = {
                    'date': date_str,
                    'missing_checkout': 0,
                    'duplicate_checkin': 0,
                    'missing_checkin': 0,
                    'total': 0,
                }
            daily_trend[date_str][anomaly.anomaly_type] += 1
            daily_trend[date_str]['total'] += 1

        # Sort by date
        daily_trend_list = sorted(daily_trend.values(), key=lambda x: x['date'])

        # Get recent anomalies (last 10)
        recent_anomalies = Anomaly.search(domain, order='attendance_date desc', limit=10)
        recent_anomalies_data = [{
            'employee': a.employee_id.name,
            'device_id_num': a.employee_id.device_id_num or a.employee_id.barcode or 'No ID',
            'date': str(a.attendance_date),
            'type': dict(Anomaly._fields['anomaly_type'].selection).get(a.anomaly_type),
            'checkin_count': a.checkin_count,
            'checkout_count': a.checkout_count,
            'total_punches': a.total_punches,
        } for a in recent_anomalies]

        # Get attendance summary statistics
        attendance_stats = AttendanceSummary.get_monthly_summary_statistics(start_date, end_date)

        # Get detailed attendance summary for employee lists
        attendance_summary_data = AttendanceSummary.get_attendance_summary(employee_ids=None, start_date=start_date, end_date=end_date)

        # Build device_id map for all employees in summary data
        _emp_ids = {r['employee_id'] for r in attendance_summary_data}
        _emp_device_map = {
            e.id: e.device_id_num or e.barcode or 'No ID'
            for e in request.env['hr.employee'].sudo().browse(list(_emp_ids))
        }

        # Process employee attendance data
        employee_attendance = {}
        for record in attendance_summary_data:
            emp_id = record['employee_id']
            emp_name = record['employee_name']

            if emp_id not in employee_attendance:
                employee_attendance[emp_id] = {
                    'employee_id': emp_id,
                    'employee_name': emp_name,
                    'device_id_num': _emp_device_map.get(emp_id, ''),
                    'present_count': 0,
                    'absent_count': 0,
                    'late_count': 0,
                    'on_time_count': 0,
                    'total_worked_hours': 0,
                    'total_overtime': 0,
                }

            if record['status'] == 'present':
                employee_attendance[emp_id]['present_count'] += 1
                employee_attendance[emp_id]['total_worked_hours'] += record.get('worked_hours', 0)
                employee_attendance[emp_id]['total_overtime'] += record.get('overtime', 0)

                if record.get('is_late'):
                    employee_attendance[emp_id]['late_count'] += 1
                else:
                    employee_attendance[emp_id]['on_time_count'] += 1
            elif record['status'] == 'absent':
                employee_attendance[emp_id]['absent_count'] += 1

        # Convert to list and sort
        employee_list = list(employee_attendance.values())

        # Top 10 most present employees
        top_present = sorted(employee_list, key=lambda x: x['present_count'], reverse=True)[:10]

        # Top 10 most absent employees
        top_absent = sorted(employee_list, key=lambda x: x['absent_count'], reverse=True)[:10]

        # Top 10 most late employees - with percentage calculation
        for emp in employee_list:
            total_days = emp['present_count']
            emp['total_present_days'] = total_days
            emp['late_percentage'] = (emp['late_count'] / total_days * 100) if total_days > 0 else 0
            emp['on_time_percentage'] = (emp['on_time_count'] / total_days * 100) if total_days > 0 else 0

        top_late = sorted(employee_list, key=lambda x: x['late_count'], reverse=True)[:10]

        # Top 10 most on-time employees
        top_on_time = sorted(employee_list, key=lambda x: x['on_time_count'], reverse=True)[:10]

        # ===== EMPLOYEE LEAVE (TIME OFF) LIST =====
        # Get employees on leave with detailed information
        employee_leave_list = []
        for record in attendance_summary_data:
            if record['status'] == 'leave':
                emp_id = record['employee_id']
                # Find or create employee entry
                emp_entry = next((e for e in employee_leave_list if e['employee_id'] == emp_id), None)
                if not emp_entry:
                    emp_entry = {
                        'employee_id': emp_id,
                        'employee_name': record['employee_name'],
                        'device_id_num': _emp_device_map.get(emp_id, ''),
                        'leave_days': 0,
                        'leave_hours': 0.0,
                        'leave_dates': [],
                    }
                    employee_leave_list.append(emp_entry)

                # Add this leave day
                emp_entry['leave_days'] += 1
                emp_entry['leave_hours'] += record.get('expected_hours', 8.0)
                emp_entry['leave_dates'].append({
                    'date': str(record['date']),
                    'leave_type': record.get('leave_type', 'Time Off'),
                })

        # Sort by leave days (most to least)
        employee_leave_list = sorted(employee_leave_list, key=lambda x: x['leave_days'], reverse=True)

        # ===== LATE CHECK-IN STATISTICS =====
        # Get all late check-in records
        late_records = LateCheckIn.search(late_domain)

        # Late check-in summary counts
        total_late_incidents = len(late_records)
        total_penalty_amount = sum(late_records.mapped('penalty_amount'))
        avg_late_minutes = sum(late_records.mapped('late_minutes')) / len(late_records) if late_records else 0
        avg_penalty_per_incident = total_penalty_amount / total_late_incidents if total_late_incidents else 0

        # Count by state
        draft_count = LateCheckIn.search_count(late_domain + [('state', '=', 'draft')])
        approved_count = LateCheckIn.search_count(late_domain + [('state', '=', 'approved')])
        refused_count = LateCheckIn.search_count(late_domain + [('state', '=', 'refused')])
        deducted_count = LateCheckIn.search_count(late_domain + [('state', '=', 'deducted')])

        # Daily late check-in trend
        daily_late_trend = {}
        for record in late_records:
            date_str = str(record.date)
            if date_str not in daily_late_trend:
                daily_late_trend[date_str] = {
                    'date': date_str,
                    'count': 0,
                    'total_minutes': 0,
                    'total_penalty': 0,
                }
            daily_late_trend[date_str]['count'] += 1
            daily_late_trend[date_str]['total_minutes'] += record.late_minutes
            daily_late_trend[date_str]['total_penalty'] += record.penalty_amount

        daily_late_trend_list = sorted(daily_late_trend.values(), key=lambda x: x['date'])

        # Top employees with late check-ins
        employee_late_stats = {}
        for record in late_records:
            emp_id = record.employee_id.id
            if emp_id not in employee_late_stats:
                _emp_obj = record.employee_id
                employee_late_stats[emp_id] = {
                    'employee_id': emp_id,
                    'employee_name': _emp_obj.name,
                    'device_id_num': _emp_obj.device_id_num or _emp_obj.barcode or 'No ID',
                    'late_count': 0,
                    'total_late_minutes': 0,
                    'total_penalty': 0,
                    'draft': 0,
                    'approved': 0,
                    'refused': 0,
                    'deducted': 0,
                }
            stats = employee_late_stats[emp_id]
            stats['late_count'] += 1
            stats['total_late_minutes'] += record.late_minutes
            stats['total_penalty'] += record.penalty_amount
            stats[record.state] += 1

        # Sort and get top 10
        top_late_employees = sorted(
            employee_late_stats.values(),
            key=lambda x: x['late_count'],
            reverse=True
        )[:10]

        # Top employees by penalty amount
        top_penalty_employees = sorted(
            employee_late_stats.values(),
            key=lambda x: x['total_penalty'],
            reverse=True
        )[:10]

        # Recent late check-ins (last 10)
        recent_late_records = LateCheckIn.search(late_domain, order='date desc', limit=10)
        recent_late_data = [{
            'employee': r.employee_id.name,
            'device_id_num': r.employee_id.device_id_num or r.employee_id.barcode or 'No ID',
            'date': str(r.date),
            'late_minutes': r.late_minutes,
            'actual_late_minutes': getattr(r, 'actual_late_minutes', r.late_minutes),  # Safe fallback
            'penalty_amount': r.penalty_amount,
            'state': r.state,
            'state_label': dict(LateCheckIn._fields['state'].selection).get(r.state),
        } for r in recent_late_records]

        # ===== MANUAL ATTENDANCE TRACKING =====
        HrAttendance = request.env['hr.attendance']
        ZkMachine = request.env['zk.machine.attendance']

        # Get attendance entries that appear to be manual (no linked biometric punches).
        # We use TWO checks:
        #   1. zk_punch_count = 0  (computed from One2many linkage)
        #   2. Cross-check against zk.machine.attendance by employee + time
        #      to catch old records where hr_attendance_id was never set.
        dt_start = datetime.combine(start_date, time.min)
        dt_end = datetime.combine(end_date, time.max)
        candidate_domain = [
            ('check_in', '>=', dt_start),
            ('check_in', '<=', dt_end),
            ('zk_punch_count', '=', 0),
        ]

        candidates = HrAttendance.search(candidate_domain, order='check_in desc')

        # Build a set of (employee_id, punching_date) from raw device logs
        # so we can exclude entries that DO have a device punch, even if
        # the hr_attendance_id linkage is missing.
        device_punches = ZkMachine.sudo().search([
            ('punching_time', '>=', dt_start.strftime('%Y-%m-%d %H:%M:%S')),
            ('punching_time', '<=', dt_end.strftime('%Y-%m-%d %H:%M:%S')),
        ])
        device_punch_keys = set()
        for dp in device_punches:
            try:
                dp_dt = dp.punching_time if isinstance(dp.punching_time, datetime) \
                    else datetime.strptime(str(dp.punching_time), '%Y-%m-%d %H:%M:%S')
                device_punch_keys.add((dp.employee_id.id, dp_dt.date()))
            except Exception:
                pass

        # Filter out candidates that actually have device punches
        manual_attendances = candidates.filtered(
            lambda att: (att.employee_id.id,
                         att.check_in.date() if att.check_in else None)
            not in device_punch_keys
        )

        # Count manual entries
        total_manual_entries = len(manual_attendances)

        # Identify manual entry anomalies
        # Use Odoo's standard context_timestamp — same as native Attendance list view
        from odoo import fields as odoo_fields

        manual_anomalies = []
        for att in manual_attendances[:20]:  # Last 20 manual entries
            anomaly_type = None
            if not att.check_out:
                anomaly_type = 'Missing Check-out'
            elif att.check_in and att.check_out and att.check_in >= att.check_out:
                anomaly_type = 'Invalid Time'

            # Use Odoo's context_timestamp (same as native attendance views)
            check_in_display = 'N/A'
            check_out_display = 'N/A'
            if att.check_in:
                check_in_display = odoo_fields.Datetime.context_timestamp(
                    att, att.check_in).strftime('%Y-%m-%d %H:%M:%S')
            if att.check_out:
                check_out_display = odoo_fields.Datetime.context_timestamp(
                    att, att.check_out).strftime('%Y-%m-%d %H:%M:%S')

            manual_anomalies.append({
                'employee': att.employee_id.name,
                'device_id_num': att.employee_id.device_id_num or att.employee_id.barcode or 'No ID',
                'check_in': check_in_display,
                'check_out': check_out_display,
                'date': str(att.check_in.date()) if att.check_in else 'N/A',
                'anomaly_type': anomaly_type or 'Normal',
                'source': 'Manual Entry',
            })

        # Count anomalies
        manual_missing_checkout = len([a for a in manual_anomalies if a['anomaly_type'] == 'Missing Check-out'])
        manual_invalid_time = len([a for a in manual_anomalies if a['anomaly_type'] == 'Invalid Time'])

        return {
            'summary': {
                'total': total_anomalies,
                'missing_checkout': missing_checkout_count,
                'duplicate_checkin': duplicate_checkin_count,
                'missing_checkin': missing_checkin_count,
            },
            'attendance_stats': attendance_stats,
            'top_employees': top_employees,
            'daily_trend': daily_trend_list,
            'recent_anomalies': recent_anomalies_data,
            'top_present': top_present,
            'top_absent': top_absent,
            'top_late': top_late,
            'top_on_time': top_on_time,
            # Employee leave data
            'employee_leave_list': employee_leave_list,
            # Late check-in data
            'late_check_in_stats': {
                'total_incidents': total_late_incidents,
                'total_penalty': total_penalty_amount,
                'avg_late_minutes': avg_late_minutes,
                'avg_penalty': avg_penalty_per_incident,
                'draft': draft_count,
                'approved': approved_count,
                'refused': refused_count,
                'deducted': deducted_count,
            },
            'late_daily_trend': daily_late_trend_list,
            'top_late_employees': top_late_employees,
            'top_penalty_employees': top_penalty_employees,
            'recent_late_records': recent_late_data,
            # Manual attendance tracking
            'manual_attendance_stats': {
                'total_manual_entries': total_manual_entries,
                'manual_missing_checkout': manual_missing_checkout,
                'manual_invalid_time': manual_invalid_time,
            },
            'manual_attendance_list': manual_anomalies,
        }
