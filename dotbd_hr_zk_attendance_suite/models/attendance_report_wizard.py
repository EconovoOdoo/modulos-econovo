# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
from io import BytesIO
import xlsxwriter
import pytz
from datetime import datetime, timedelta


class AttendanceReportWizard(models.TransientModel):
    """Wizard to generate attendance reports"""
    _name = 'attendance.report.wizard'
    _description = 'Attendance Report Generator'

    start_date = fields.Date(string='Start Date', required=True,
                             default=lambda self: fields.Date.today().replace(day=1))
    end_date = fields.Date(string='End Date', required=True,
                           default=fields.Date.today)
    employee_ids = fields.Many2many('hr.employee', string='Employees',
                                    help='Leave empty for all employees')
    department_ids = fields.Many2many(
        'hr.department', string='Departments',
        help='Filter by specific department(s). Leave empty to include all '
             'departments. If both Employees and Departments are set, '
             'Employees takes precedence.'
    )
    report_type = fields.Selection([
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('anomaly', 'Anomaly Report'),
        ('late_checkin', 'Late Check-in Report'),
    ], string='Report Type', default='summary', required=True)

    device_ids = fields.Many2many(
        'biometric.device.details',
        string='Device Source',
        help='Filter by specific biometric device(s). Leave empty to include attendance from all devices.'
    )

    report_file = fields.Binary('Report File', readonly=True)
    report_filename = fields.Char('Filename', readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')],
                            default='draft')

    def _get_filtered_employee_ids(self):
        """Return the list of employee ids constrained by this wizard's filters,
        or None when no employee/department filter is set (= "all employees").

        Employees field, when filled, takes precedence; otherwise the department
        filter is expanded to its member employees.
        """
        if self.employee_ids:
            return self.employee_ids.ids
        if self.department_ids:
            emps = self.env['hr.employee'].sudo().search(
                [('department_id', 'in', self.department_ids.ids)])
            return emps.ids
        return None

    def _build_device_map(self):
        """Build a device-per-attendance-day map from ZK punch records.

        Returns:
            device_map  : {(employee_id, date): {'checkin': name, 'checkout': name}}
            allowed_keys: set of (employee_id, date) where a punch came from the
                          selected device_ids, or None when no device filter is set.
        """
        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        tz = pytz.timezone(tz_name)

        start_dt = datetime(self.start_date.year, self.start_date.month, self.start_date.day)
        end_dt = datetime(self.end_date.year, self.end_date.month, self.end_date.day, 23, 59, 59)
        start_utc = tz.localize(start_dt).astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = tz.localize(end_dt).astimezone(pytz.utc).replace(tzinfo=None)

        punches = self.env['zk.machine.attendance'].sudo().search([
            ('punching_time', '>=', start_utc),
            ('punching_time', '<=', end_utc),
        ])

        device_map = {}
        allowed_keys = set() if self.device_ids else None
        filter_ids = set(self.device_ids.ids) if self.device_ids else set()

        for punch in punches:
            emp_id = punch.employee_id.id
            if not emp_id:
                continue
            local_dt = pytz.utc.localize(punch.punching_time).astimezone(tz)
            punch_date = local_dt.date()
            key = (emp_id, punch_date)

            if key not in device_map:
                device_map[key] = {'checkin': '-', 'checkout': '-'}

            device_name = punch.device_id.name if punch.device_id else 'Manual/Unknown'
            if punch.punch_type == '0':        # Check In
                device_map[key]['checkin'] = device_name
            elif punch.punch_type == '1':      # Check Out
                device_map[key]['checkout'] = device_name

            if filter_ids and punch.device_id and punch.device_id.id in filter_ids:
                allowed_keys.add(key)

        return device_map, allowed_keys

    def action_generate_report(self):
        """Generate Excel report"""
        self.ensure_one()

        if self.report_type == 'summary':
            report_data = self._generate_summary_report()
        elif self.report_type == 'detailed':
            report_data = self._generate_detailed_report()
        elif self.report_type == 'late_checkin':
            report_data = self._generate_late_checkin_report()
        else:
            report_data = self._generate_anomaly_report()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'attendance.report.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _generate_summary_report(self):
        """Generate summary Excel report"""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Attendance Summary')

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center'
        })

        cell_format = workbook.add_format({'border': 1, 'align': 'center'})
        number_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0.00'})
        duration_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '[h]:mm'})

        # Title
        worksheet.merge_range('A1:M1', 'Monthly Attendance Report', title_format)
        worksheet.write('A2', f'Period: {self.start_date} to {self.end_date}')
        if self.department_ids:
            dept_names = ', '.join(self.department_ids.mapped('name'))
            worksheet.write('A3', f'Departments: {dept_names}')

        # Headers
        headers = [
            'Employee ID', 'Employee Name', 'Department', 'Designation',
            'Total Days', 'Present', 'Absent',
            'On Leave', 'Late Arrivals', 'Total Worked Hours', 'Expected Hours',
            'Overtime', 'Undertime'
        ]

        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_format)

        # Get data
        AttendanceSummary = self.env['attendance.summary.analysis']
        employee_ids = self._get_filtered_employee_ids()

        summary_data = AttendanceSummary.get_attendance_summary(
            employee_ids, self.start_date, self.end_date
        )

        # Device map for filtering
        _, allowed_keys = self._build_device_map()

        # Prefetch device IDs + department + job for all employees in one query
        emp_id_set = {r['employee_id'] for r in summary_data}
        employees = self.env['hr.employee'].browse(list(emp_id_set))
        emp_device_map = {
            emp.id: emp.device_id_num or emp.barcode or 'No ID'
            for emp in employees
        }
        emp_dept_map = {
            emp.id: emp.department_id.name if emp.department_id else ''
            for emp in employees
        }
        emp_job_map = {
            emp.id: (emp.job_id.name if emp.job_id else '') or emp.job_title or ''
            for emp in employees
        }

        # Device filter note in header
        if self.device_ids:
            device_names = ', '.join(self.device_ids.mapped('name'))
            worksheet.merge_range('A4:M4',
                f'Device Filter: {device_names} — Only days with a punch from these device(s) counted as Present.',
                workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'align': 'center', 'border': 1}))

        # Aggregate by employee
        employee_stats = {}
        for record in summary_data:
            emp_id = record['employee_id']
            rec_date = record['date']
            key = (emp_id, rec_date)

            if emp_id not in employee_stats:
                employee_stats[emp_id] = {
                    'name': record['employee_name'],
                    'device_id': emp_device_map.get(emp_id, ''),
                    'department': emp_dept_map.get(emp_id, ''),
                    'job_title': emp_job_map.get(emp_id, ''),
                    'total_days': 0,
                    'present': 0,
                    'absent': 0,
                    'leave': 0,
                    'late': 0,
                    'worked_hours': 0,
                    'expected_hours': 0,
                    'overtime': 0,
                    'undertime': 0,
                }

            stats = employee_stats[emp_id]
            # Count only working days (exclude weekends and public holidays)
            if record['status'] not in ('weekend', 'public_holiday'):
                stats['total_days'] += 1

            effective_status = record['status']
            # Device filter: if present but punch not from selected device → treat as absent
            if effective_status == 'present' and allowed_keys is not None and key not in allowed_keys:
                effective_status = 'absent'

            if effective_status == 'present':
                stats['present'] += 1
                stats['worked_hours'] += record['worked_hours']
                if record['is_late']:
                    stats['late'] += 1
                stats['overtime'] += record.get('overtime', 0)
                stats['undertime'] += record.get('undertime', 0)
            elif effective_status == 'absent':
                stats['absent'] += 1
            elif effective_status == 'leave':
                stats['leave'] += 1

            if effective_status in ['present', 'absent']:
                stats['expected_hours'] += record['expected_hours']

        # Write data
        row = 4
        for emp_id, stats in employee_stats.items():
            worksheet.write(row, 0, stats['device_id'], cell_format)
            worksheet.write(row, 1, stats['name'], cell_format)
            worksheet.write(row, 2, stats['department'], cell_format)
            worksheet.write(row, 3, stats['job_title'], cell_format)
            worksheet.write(row, 4, stats['total_days'], cell_format)
            worksheet.write(row, 5, stats['present'], cell_format)
            worksheet.write(row, 6, stats['absent'], cell_format)
            worksheet.write(row, 7, stats['leave'], cell_format)
            worksheet.write(row, 8, stats['late'], cell_format)
            worksheet.write(row, 9, stats['worked_hours'] / 24.0, duration_format)
            worksheet.write(row, 10, stats['expected_hours'] / 24.0, duration_format)
            worksheet.write(row, 11, stats['overtime'] / 24.0, duration_format)
            worksheet.write(row, 12, stats['undertime'] / 24.0, duration_format)
            row += 1

        # Adjust column widths
        worksheet.set_column('A:A', 12)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:D', 18)
        worksheet.set_column('E:M', 15)

        workbook.close()
        output.seek(0)

        # Save file
        filename = f'Attendance_Summary_{self.start_date}_{self.end_date}.xlsx'
        self.write({
            'report_file': base64.b64encode(output.read()),
            'report_filename': filename,
            'state': 'done'
        })

        return True

    def _generate_detailed_report(self):
        """Generate detailed daily Excel report with device source columns"""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Daily Attendance')

        # Formats
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#4F81BD', 'font_color': 'white',
            'border': 1, 'align': 'center'
        })
        title_format = workbook.add_format({'bold': True, 'font_size': 16, 'align': 'center'})
        cell_format = workbook.add_format({'border': 1})
        date_format = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})
        time_format = workbook.add_format({'border': 1, 'num_format': 'hh:mm:ss'})
        number_format = workbook.add_format({'border': 1, 'num_format': '0.00'})
        duration_format = workbook.add_format({'border': 1, 'num_format': '[h]:mm'})
        minutes_format = workbook.add_format({'border': 1, 'num_format': '0'})
        warning_format = workbook.add_format({
            'bold': True, 'italic': True,
            'bg_color': '#FFC7CE', 'font_color': '#9C0006',
            'border': 1, 'text_wrap': True, 'align': 'left', 'valign': 'vcenter'
        })
        cross_fmt = workbook.add_format({'border': 1, 'bg_color': '#FFE699'})
        cross_time_fmt = workbook.add_format({'border': 1, 'bg_color': '#FFE699', 'num_format': 'hh:mm:ss'})
        cross_num_fmt = workbook.add_format({'border': 1, 'bg_color': '#FFE699', 'num_format': '0.00'})
        cross_duration_fmt = workbook.add_format({'border': 1, 'bg_color': '#FFE699', 'num_format': '[h]:mm'})
        cross_minutes_fmt = workbook.add_format({'border': 1, 'bg_color': '#FFE699', 'num_format': '0'})
        device_filter_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#D9E1F2', 'align': 'center', 'border': 1
        })

        # Status formats
        present_format = workbook.add_format({'border': 1, 'bg_color': '#C6EFCE'})
        absent_format = workbook.add_format({'border': 1, 'bg_color': '#FFC7CE'})
        leave_format = workbook.add_format({'border': 1, 'bg_color': '#FFEB9C'})

        # Build device map (for device source columns + device filter)
        device_map, allowed_keys = self._build_device_map()

        # ── Title row ──────────────────────────────────────────────────────────
        # 17 columns: Date, EmpID, Employee, Department, Designation, Status,
        #             CheckIn, CheckOut, WorkedH, ExpectedH, Late?, LateMin,
        #             OT, UnderTime, CheckIn-Device, CheckOut-Device, Remarks
        worksheet.merge_range('A1:Q1', 'Detailed Daily Attendance Report', title_format)
        next_row = 1  # 0-indexed; row 1 is the 2nd row

        if self.device_ids:
            device_names = ', '.join(self.device_ids.mapped('name'))
            worksheet.merge_range(next_row, 0, next_row, 16,
                f'Device Filter Active: {device_names}', device_filter_fmt)
            next_row += 1

        if self.department_ids:
            dept_names = ', '.join(self.department_ids.mapped('name'))
            worksheet.merge_range(next_row, 0, next_row, 16,
                f'Department Filter: {dept_names}', device_filter_fmt)
            next_row += 1

        worksheet.write(next_row, 0, f'Period: {self.start_date} to {self.end_date}')
        next_row += 1

        # Reserve one row for the cross-device warning (written later)
        warning_row = next_row
        next_row += 1

        # ── Header row ─────────────────────────────────────────────────────────
        headers = [
            'Date', 'Employee ID', 'Employee', 'Department', 'Designation', 'Status',
            'Check In', 'Check Out',
            'Worked Hours', 'Expected Hours', 'Late?', 'Late Minutes',
            'Overtime', 'Undertime',
            'Check-in Device', 'Check-out Device', 'Remarks'
        ]
        for col, header in enumerate(headers):
            worksheet.write(next_row, col, header, header_format)
        data_start_row = next_row + 1

        # ── Data ───────────────────────────────────────────────────────────────
        AttendanceSummary = self.env['attendance.summary.analysis']
        employee_ids = self._get_filtered_employee_ids()
        summary_data = AttendanceSummary.get_attendance_summary(
            employee_ids, self.start_date, self.end_date
        )

        emp_id_set = {r['employee_id'] for r in summary_data}
        employees = self.env['hr.employee'].browse(list(emp_id_set))
        emp_device_map = {
            emp.id: emp.device_id_num or emp.barcode or 'No ID'
            for emp in employees
        }
        emp_dept_map = {
            emp.id: emp.department_id.name if emp.department_id else ''
            for emp in employees
        }
        emp_job_map = {
            emp.id: (emp.job_id.name if emp.job_id else '') or emp.job_title or ''
            for emp in employees
        }

        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(tz_name)

        def _to_local(dt):
            if not dt:
                return None
            return pytz.utc.localize(dt).astimezone(local_tz).replace(tzinfo=None)

        row = data_start_row
        has_cross_device = False

        for record in sorted(summary_data, key=lambda x: (x['date'], x['employee_name'])):
            emp_id = record['employee_id']
            rec_date = record['date']
            key = (emp_id, rec_date)

            # Device filter: skip 'present' rows whose punch is not from the selected device
            if allowed_keys is not None and record['status'] == 'present' and key not in allowed_keys:
                continue

            if record['status'] == 'present':
                status_fmt = present_format
            elif record['status'] == 'absent':
                status_fmt = absent_format
            else:
                status_fmt = leave_format

            # Device info for this day
            dev = device_map.get(key, {'checkin': '-', 'checkout': '-'})
            checkin_dev = dev['checkin']
            checkout_dev = dev['checkout']
            is_cross = (
                checkin_dev not in ('-', 'Manual/Unknown') and
                checkout_dev not in ('-', 'Manual/Unknown') and
                checkin_dev != checkout_dev
            )
            if is_cross:
                has_cross_device = True

            cf = cross_fmt if is_cross else cell_format
            tf = cross_time_fmt if is_cross else time_format
            nf = cross_num_fmt if is_cross else number_format
            df = cross_duration_fmt if is_cross else duration_format
            mf = cross_minutes_fmt if is_cross else minutes_format

            local_checkin = _to_local(record['check_in'])
            local_checkout = _to_local(record['check_out'])

            worksheet.write(row, 0, record['date'], date_format)
            worksheet.write(row, 1, emp_device_map.get(emp_id, ''), cf)
            worksheet.write(row, 2, record['employee_name'], cf)
            worksheet.write(row, 3, emp_dept_map.get(emp_id, ''), cf)
            worksheet.write(row, 4, emp_job_map.get(emp_id, ''), cf)
            worksheet.write(row, 5, record['status'].upper(), status_fmt)

            if local_checkin:
                worksheet.write_datetime(row, 6, local_checkin, tf)
            else:
                worksheet.write(row, 6, '-', cf)

            if local_checkout:
                worksheet.write_datetime(row, 7, local_checkout, tf)
            else:
                worksheet.write(row, 7, '-', cf)

            worksheet.write(row, 8, (record['worked_hours'] or 0) / 24.0, df)
            worksheet.write(row, 9, (record['expected_hours'] or 0) / 24.0, df)
            worksheet.write(row, 10, 'YES' if record['is_late'] else 'NO', cf)
            worksheet.write(row, 11, record['late_minutes'] or 0, mf)
            worksheet.write(row, 12, (record.get('overtime', 0) or 0) / 24.0, df)
            worksheet.write(row, 13, (record.get('undertime', 0) or 0) / 24.0, df)
            worksheet.write(row, 14, checkin_dev, cf)
            worksheet.write(row, 15, checkout_dev, cf)

            remarks = []
            if record['is_late']:
                remarks.append(f"Late by {record['late_minutes']} min")
            if record.get('overtime', 0) > 0:
                ot_h = int(record['overtime'])
                ot_m = int(round((record['overtime'] - ot_h) * 60))
                remarks.append(f"OT: {ot_h}h {ot_m:02d}m")
            if is_cross:
                remarks.append('Cross-device')
            worksheet.write(row, 16, '; '.join(remarks), cf)

            row += 1

        # ── Cross-device warning (fills reserved row) ──────────────────────────
        if has_cross_device:
            worksheet.set_row(warning_row, 40)  # Taller row for wrapped text
            worksheet.merge_range(warning_row, 0, warning_row, 16,
                '⚠ WARNING: Rows highlighted in yellow indicate cross-device attendance — the employee '
                'checked in at one device and checked out at a different device. '
                'Worked hours are still accurate, but device-specific filtering may show this employee '
                'in reports for both devices.',
                warning_format)
        else:
            worksheet.merge_range(warning_row, 0, warning_row, 16, '',
                workbook.add_format())

        # ── Column widths ──────────────────────────────────────────────────────
        worksheet.set_column(0, 0, 12)   # Date
        worksheet.set_column(1, 1, 12)   # Employee ID
        worksheet.set_column(2, 2, 25)   # Employee
        worksheet.set_column(3, 4, 18)   # Department / Designation
        worksheet.set_column(5, 5, 10)   # Status
        worksheet.set_column(6, 7, 12)   # Check In / Check Out
        worksheet.set_column(8, 13, 12)  # Hours + Late columns
        worksheet.set_column(14, 15, 22) # Device columns
        worksheet.set_column(16, 16, 28) # Remarks

        workbook.close()
        output.seek(0)

        filename = f'Attendance_Detailed_{self.start_date}_{self.end_date}.xlsx'
        self.write({
            'report_file': base64.b64encode(output.read()),
            'report_filename': filename,
            'state': 'done'
        })

        return True

    def _generate_anomaly_report(self):
        """Generate anomaly Excel report"""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Anomalies')

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center'
        })

        date_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd',
            'align': 'center',
            'border': 1
        })

        datetime_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd hh:mm:ss',
            'align': 'center',
            'border': 1
        })

        cell_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'text_wrap': True
        })

        center_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        # Anomaly type specific formats
        missing_checkout_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#FFC7CE',
            'font_color': '#9C0006'
        })

        duplicate_checkin_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#FFEB9C',
            'font_color': '#9C6500'
        })

        missing_checkin_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#FFC7CE',
            'font_color': '#9C0006'
        })

        # Title
        worksheet.merge_range('A1:K1', 'Attendance Anomalies Report', title_format)
        worksheet.write('A2', f'Period: {self.start_date} to {self.end_date}')
        if self.department_ids:
            dept_names = ', '.join(self.department_ids.mapped('name'))
            worksheet.write('A3', f'Departments: {dept_names}')

        # Write headers
        headers = [
            'Employee', 'Department', 'Designation',
            'Date', 'Anomaly Type', 'Check-in Time',
            'Last Punch Time', 'Total Punches', 'Check-in Count',
            'Check-out Count', 'Working Address'
        ]

        for col, header in enumerate(headers):
            worksheet.write(3, col, header, header_format)

        # Set column widths
        worksheet.set_column(0, 0, 25)   # Employee
        worksheet.set_column(1, 2, 18)   # Department / Designation
        worksheet.set_column(3, 3, 12)   # Date
        worksheet.set_column(4, 4, 20)   # Anomaly Type
        worksheet.set_column(5, 5, 18)   # Check-in Time
        worksheet.set_column(6, 6, 18)   # Last Punch Time
        worksheet.set_column(7, 7, 12)   # Total Punches
        worksheet.set_column(8, 8, 12)   # Check-in Count
        worksheet.set_column(9, 9, 14)   # Check-out Count
        worksheet.set_column(10, 10, 25) # Working Address

        # Query anomaly data
        domain = [
            ('attendance_date', '>=', self.start_date),
            ('attendance_date', '<=', self.end_date),
        ]

        filtered_emp_ids = self._get_filtered_employee_ids()
        if filtered_emp_ids is not None:
            domain.append(('employee_id', 'in', filtered_emp_ids))

        anomaly_records = self.env['attendance.anomaly.analysis'].search(
            domain, order='attendance_date desc, employee_id'
        )

        # Anomaly type labels
        anomaly_type_labels = {
            'missing_checkout': 'Missing Check-out',
            'duplicate_checkin': 'Duplicate Check-in',
            'missing_checkin': 'Missing Check-in',
        }

        # Write data rows
        row = 4
        for anomaly in anomaly_records:
            # Determine format based on anomaly type
            if anomaly.anomaly_type == 'missing_checkout':
                anomaly_format = missing_checkout_format
            elif anomaly.anomaly_type == 'duplicate_checkin':
                anomaly_format = duplicate_checkin_format
            elif anomaly.anomaly_type == 'missing_checkin':
                anomaly_format = missing_checkin_format
            else:
                anomaly_format = cell_format

            emp = anomaly.employee_id
            worksheet.write(row, 0, emp.name or '', cell_format)
            worksheet.write(row, 1, emp.department_id.name if emp.department_id else '', cell_format)
            worksheet.write(row, 2, (emp.job_id.name if emp.job_id else '') or emp.job_title or '', cell_format)
            worksheet.write(row, 3, anomaly.attendance_date, date_format)
            worksheet.write(row, 4, anomaly_type_labels.get(anomaly.anomaly_type, anomaly.anomaly_type or ''), anomaly_format)

            if anomaly.check_in_time:
                worksheet.write_datetime(row, 5, anomaly.check_in_time, datetime_format)
            else:
                worksheet.write(row, 5, '', center_format)

            if anomaly.last_punch_time:
                worksheet.write_datetime(row, 6, anomaly.last_punch_time, datetime_format)
            else:
                worksheet.write(row, 6, '', center_format)

            worksheet.write(row, 7, anomaly.total_punches or 0, center_format)
            worksheet.write(row, 8, anomaly.checkin_count or 0, center_format)
            worksheet.write(row, 9, anomaly.checkout_count or 0, center_format)
            worksheet.write(row, 10, anomaly.address_id.name or '', cell_format)

            row += 1

        # Add summary section
        row += 2
        summary_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'align': 'left',
            'border': 1
        })

        worksheet.write(row, 0, 'Summary', summary_header_format)
        row += 1

        # Count anomalies by type
        missing_checkout_count = len(anomaly_records.filtered(lambda a: a.anomaly_type == 'missing_checkout'))
        duplicate_checkin_count = len(anomaly_records.filtered(lambda a: a.anomaly_type == 'duplicate_checkin'))
        missing_checkin_count = len(anomaly_records.filtered(lambda a: a.anomaly_type == 'missing_checkin'))

        worksheet.write(row, 0, 'Total Anomalies:', cell_format)
        worksheet.write(row, 1, len(anomaly_records), center_format)
        row += 1

        worksheet.write(row, 0, 'Missing Check-out:', missing_checkout_format)
        worksheet.write(row, 1, missing_checkout_count, center_format)
        row += 1

        worksheet.write(row, 0, 'Duplicate Check-in:', duplicate_checkin_format)
        worksheet.write(row, 1, duplicate_checkin_count, center_format)
        row += 1

        worksheet.write(row, 0, 'Missing Check-in:', missing_checkin_format)
        worksheet.write(row, 1, missing_checkin_count, center_format)

        workbook.close()
        output.seek(0)

        filename = f'Attendance_Anomalies_{self.start_date}_{self.end_date}.xlsx'
        self.write({
            'report_file': base64.b64encode(output.read()),
            'report_filename': filename,
            'state': 'done'
        })

        return True

    def _generate_late_checkin_report(self):
        """Generate late check-in Excel report with penalty details"""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Late Check-in Report')

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#f59e0b',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'font_color': '#f59e0b'
        })

        cell_format = workbook.add_format({'border': 1})
        number_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '0'})
        currency_format = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '#,##0" ৳"'})
        date_format = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})

        # Status formats with colors
        draft_format = workbook.add_format({'border': 1, 'bg_color': '#dbeafe', 'align': 'center'})
        approved_format = workbook.add_format({'border': 1, 'bg_color': '#d1fae5', 'align': 'center'})
        refused_format = workbook.add_format({'border': 1, 'bg_color': '#fee2e2', 'align': 'center'})
        deducted_format = workbook.add_format({'border': 1, 'bg_color': '#e5e7eb', 'align': 'center'})

        # Title and period
        worksheet.merge_range('A1:M1', 'Late Check-in Report with Penalties', title_format)
        worksheet.write('A2', f'Period: {self.start_date} to {self.end_date}')
        worksheet.write('A3', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        if self.department_ids:
            dept_names = ', '.join(self.department_ids.mapped('name'))
            worksheet.write('A4', f'Departments: {dept_names}')

        # Headers
        headers = [
            'Date', 'Employee ID', 'Employee Name', 'Department', 'Designation',
            'Actual Late (min)',
            'Counted Late (min)', 'Tolerance Applied', 'Penalty Amount (৳)',
            'Status', 'Attendance Ref', 'Approved By', 'Notes'
        ]

        for col, header in enumerate(headers):
            worksheet.write(4, col, header, header_format)

        # Get late check-in data
        LateCheckIn = self.env['late.check.in']
        domain = [
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date)
        ]

        filtered_emp_ids = self._get_filtered_employee_ids()
        if filtered_emp_ids is not None:
            domain.append(('employee_id', 'in', filtered_emp_ids))

        late_records = LateCheckIn.search(domain, order='date desc, employee_id')

        # Write data
        row = 5
        total_penalty = 0
        total_incidents = 0

        for record in late_records:
            # Select status format
            if record.state == 'draft':
                status_format = draft_format
            elif record.state == 'approved':
                status_format = approved_format
            elif record.state == 'refused':
                status_format = refused_format
            else:
                status_format = deducted_format

            tolerance_applied = record.actual_late_minutes - record.late_minutes

            emp = record.employee_id
            worksheet.write(row, 0, record.date, date_format)
            worksheet.write(row, 1, emp.device_id_num or emp.barcode or 'No ID', cell_format)
            worksheet.write(row, 2, emp.name, cell_format)
            worksheet.write(row, 3, emp.department_id.name if emp.department_id else '', cell_format)
            worksheet.write(row, 4, (emp.job_id.name if emp.job_id else '') or emp.job_title or '', cell_format)
            worksheet.write(row, 5, record.actual_late_minutes, number_format)
            worksheet.write(row, 6, record.late_minutes, number_format)
            worksheet.write(row, 7, tolerance_applied, number_format)
            worksheet.write(row, 8, record.penalty_amount, currency_format)
            worksheet.write(row, 9, record.state.upper(), status_format)
            worksheet.write(row, 10, record.name or '-', cell_format)
            worksheet.write(row, 11, '-', cell_format)  # Approved by (can be added if tracking is implemented)
            worksheet.write(row, 12, record.notes or '-', cell_format)

            total_penalty += record.penalty_amount
            total_incidents += 1

            row += 1

        # Add summary section
        row += 2
        summary_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#f59e0b',
            'font_color': 'white',
            'border': 1
        })
        summary_value_format = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'right'
        })

        worksheet.write(row, 0, 'SUMMARY', summary_header_format)
        worksheet.merge_range(row, 1, row, 2, '', summary_header_format)
        row += 1

        worksheet.write(row, 0, 'Total Late Incidents:', cell_format)
        worksheet.write(row, 1, total_incidents, summary_value_format)
        row += 1

        worksheet.write(row, 0, 'Total Penalty Amount:', cell_format)
        worksheet.write(row, 1, total_penalty, workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'right',
            'num_format': '#,##0" ৳"'
        }))
        row += 1

        if total_incidents > 0:
            worksheet.write(row, 0, 'Average Penalty per Incident:', cell_format)
            worksheet.write(row, 1, total_penalty / total_incidents, workbook.add_format({
                'border': 1,
                'align': 'right',
                'num_format': '#,##0" ৳"'
            }))

        # Group by Employee Summary
        row += 3
        worksheet.merge_range(row, 0, row, 9, 'EMPLOYEE SUMMARY', summary_header_format)
        row += 1

        employee_summary_headers = [
            'Employee ID', 'Employee Name', 'Department', 'Designation', 'Total Incidents',
            'Total Late Minutes', 'Total Penalty (৳)', 'Draft', 'Approved/Deducted', 'Refused'
        ]
        for col, header in enumerate(employee_summary_headers):
            worksheet.write(row, col, header, header_format)
        row += 1

        # Aggregate by employee
        employee_stats = {}
        for record in late_records:
            emp = record.employee_id
            emp_id = emp.id
            if emp_id not in employee_stats:
                employee_stats[emp_id] = {
                    'device_id': emp.device_id_num or emp.barcode or 'No ID',
                    'name': emp.name,
                    'department': emp.department_id.name if emp.department_id else '',
                    'job_title': (emp.job_id.name if emp.job_id else '') or emp.job_title or '',
                    'count': 0,
                    'total_minutes': 0,
                    'total_penalty': 0,
                    'draft': 0,
                    'approved': 0,
                    'refused': 0,
                }
            stats = employee_stats[emp_id]
            stats['count'] += 1
            stats['total_minutes'] += record.late_minutes
            stats['total_penalty'] += record.penalty_amount
            if record.state in ['approved', 'deducted']:
                stats['approved'] += 1
            elif record.state == 'draft':
                stats['draft'] += 1
            elif record.state == 'refused':
                stats['refused'] += 1

        # Write employee summary
        for emp_id, stats in sorted(employee_stats.items(), key=lambda x: x[1]['total_penalty'], reverse=True):
            worksheet.write(row, 0, stats['device_id'], cell_format)
            worksheet.write(row, 1, stats['name'], cell_format)
            worksheet.write(row, 2, stats['department'], cell_format)
            worksheet.write(row, 3, stats['job_title'], cell_format)
            worksheet.write(row, 4, stats['count'], number_format)
            worksheet.write(row, 5, stats['total_minutes'], number_format)
            worksheet.write(row, 6, stats['total_penalty'], currency_format)
            worksheet.write(row, 7, stats['draft'], number_format)
            worksheet.write(row, 8, stats['approved'], number_format)
            worksheet.write(row, 9, stats['refused'], number_format)
            row += 1

        # Adjust column widths
        worksheet.set_column('A:A', 12)   # Date
        worksheet.set_column('B:B', 10)   # Employee ID
        worksheet.set_column('C:C', 25)   # Employee Name
        worksheet.set_column('D:E', 18)   # Department / Designation
        worksheet.set_column('F:I', 15)   # Late + Penalty
        worksheet.set_column('J:J', 12)   # Status
        worksheet.set_column('K:K', 15)   # Attendance Ref
        worksheet.set_column('L:M', 20)   # Approved By / Notes

        workbook.close()
        output.seek(0)

        filename = f'Late_Check_in_Report_{self.start_date}_{self.end_date}.xlsx'
        self.write({
            'report_file': base64.b64encode(output.read()),
            'report_filename': filename,
            'state': 'done'
        })

        return True

    def action_download_report(self):
        """Download the generated report"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/attendance.report.wizard/{self.id}/report_file/{self.report_filename}?download=true',
            'target': 'self',
        }
