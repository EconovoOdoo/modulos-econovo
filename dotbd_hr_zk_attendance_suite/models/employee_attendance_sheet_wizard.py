# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit

################################################################################
from odoo import api, models, fields, registry as odoo_registry, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import calendar
import xlsxwriter
import io
import base64


def _fmt_hm(hours):
    """Format decimal hours as 'Xh YYm' for readability (e.g. 8.5 -> '8h 30m')."""
    if not hours:
        return '0h 00m'
    total_minutes = int(round(float(hours) * 60))
    h, m = divmod(total_minutes, 60)
    return f"{h}h {m:02d}m"


class EmployeeAttendanceSheetWizard(models.TransientModel):
    _name = 'employee.attendance.sheet.wizard'
    _description = 'Employee Attendance Sheet Generator'

    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string='Month', default=lambda self: str(datetime.now().month))

    year = fields.Integer(
        string='Year',
        default=lambda self: datetime.now().year
    )

    # Custom date range — overrides month/year when both are set
    start_date = fields.Date(string='From Date',
                             help='If set together with To Date, overrides Month/Year selection.')
    end_date = fields.Date(string='To Date')

    device_ids = fields.Many2many(
        'biometric.device.details',
        string='Device Source',
        help='Filter by specific biometric device(s). Leave empty for all devices.'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        string='Employees',
        help='Leave empty to use Department filter or include all employees'
    )

    department_ids = fields.Many2many(
        'hr.department',
        string='Departments',
        help='Filter by specific department(s). Leave empty for all '
             'departments. If both Employees and Departments are set, '
             'Employees takes precedence.'
    )

    report_format = fields.Selection([
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
    ], string='Report Format', required=True, default='excel')

    sheet_type = fields.Selection([
        ('combined', 'Combined Sheet (All Employees)'),
        ('individual', 'Individual Sheets (Per Employee)'),
    ], string='Sheet Type', required=True, default='combined')

    # ── Problem Employee Filter ───────────────────────────────────────────────
    # Tick one or more boxes. Employees with at least ONE day of that type
    # appear in the report. Tolerance is already applied — an employee who
    # arrived within the configured grace period is shown as Present (P),
    # NOT Late (L), and does NOT trigger the late filter.
    filter_late = fields.Boolean(
        string='Late employees',
        help='Show employees who have at least one late check-in (after tolerance).'
    )
    filter_absent = fields.Boolean(
        string='Absent employees',
        help='Show employees who have at least one absent day.'
    )
    filter_leave = fields.Boolean(
        string='Time-off / Leave employees',
        help='Show employees who have at least one leave or time-off day.'
    )
    # ─────────────────────────────────────────────────────────────────────────

    file_data = fields.Binary(string='File', readonly=True)
    file_name = fields.Char(string='File Name', readonly=True)

    @api.constrains('year')
    def _check_year(self):
        """Validate year is reasonable (only when month/year mode is used)"""
        for record in self:
            if not (record.start_date and record.end_date) and record.year:
                if record.year < 2000 or record.year > 2100:
                    raise ValidationError(_('Please enter a valid year between 2000 and 2100.'))

    @api.constrains('start_date', 'end_date')
    def _check_date_range(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValidationError(_('From Date cannot be after To Date.'))

    def _get_date_range(self):
        """Return (start_date, end_date, month_name, year_int, num_days) for report generation."""
        if self.start_date and self.end_date:
            s = self.start_date
            e = self.end_date
            num_days = (e - s).days + 1
            # Derive month_name/year from start_date for backward compat with title helpers
            month_name = s.strftime('%b %Y') + (f' – {e.strftime("%b %Y")}' if s.month != e.month or s.year != e.year else '')
            year_int = s.year
            return s, e, month_name, year_int, num_days
        else:
            # Month/Year mode
            if not self.month or not self.year:
                raise ValidationError(_('Please select a Month and Year, or provide a custom From/To date range.'))
            month_int = int(self.month)
            year_int = self.year
            month_name = dict(self._fields['month'].selection).get(self.month)
            num_days = calendar.monthrange(year_int, month_int)[1]
            s = datetime(year_int, month_int, 1).date()
            e = datetime(year_int, month_int, num_days).date()
            return s, e, month_name, year_int, num_days

    def _export_flag_key(self):
        return f'attendance.export.running.{self.env.uid}'

    def _set_export_flag(self, running):
        """Set or clear the export-in-progress flag using a separate cursor so it
        is immediately visible to concurrent HTTP requests (e.g. the status check)."""
        db = self.env.cr.dbname
        uid = self.env.uid
        key = self._export_flag_key()
        with odoo_registry(db).cursor() as cr:
            env2 = api.Environment(cr, uid, self.env.context)
            env2['ir.config_parameter'].set_param(key, datetime.now().isoformat() if running else '')
            cr.commit()

    def action_generate_report(self):
        """Generate attendance sheet based on selected format"""
        self.ensure_one()
        self._set_export_flag(True)
        try:
            if self.report_format == 'excel':
                return self._generate_excel_report()
            else:
                return self._generate_pdf_report()
        finally:
            self._set_export_flag(False)

    def action_batch_pdf_wizard(self):
        """Open batch PDF generation wizard for 150+ employees."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Batch PDF Generation (150+ Employees)'),
            'res_model': 'batch.pdf.generation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_month': self.month,
                'default_year': self.year,
                'default_employee_ids': self.employee_ids.ids if self.employee_ids else [],
                'default_sheet_type': self.sheet_type,
                'default_batch_size': 25,
            },
        }

    # ── Problem employee filter helpers ──────────────────────────────────────

    def _filter_problem_employees(self, employee_stats):
        """Return only employees who have at least one day of the selected problem type(s).

        Tolerance is already reflected in late_count — days where the employee
        arrived within the grace period are counted as on-time, not late.
        """
        if not self.filter_late and not self.filter_absent and not self.filter_leave:
            return employee_stats  # No filter active → return everyone

        result = []
        for stat in employee_stats:
            match = False
            if self.filter_late and stat['late_count'] > 0:
                match = True
            if self.filter_absent and stat['absent_count'] > 0:
                match = True
            if self.filter_leave and stat.get('leave_count', 0) > 0:
                match = True
            if match:
                result.append(stat)

        return result

    def _create_problem_summary_sheet(self, workbook, filtered_stats, all_count,
                                      start_date, end_date):
        """Add a ⚠ Problem Summary sheet listing flagged employees sorted by severity."""
        ws = workbook.add_worksheet('Problem Summary')

        # ── Formats ──────────────────────────────────────────────────────────
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 13, 'align': 'center', 'valign': 'vcenter'
        })
        info_fmt = workbook.add_format({'italic': True, 'font_size': 9})
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#C00000', 'font_color': 'white',
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True
        })
        critical_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#FFC7CE', 'font_color': '#9C0006',
            'border': 1, 'align': 'center'
        })
        warning_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#FFEB9C', 'font_color': '#9C6500',
            'border': 1, 'align': 'center'
        })
        watch_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#BDD7EE', 'font_color': '#1F4E78',
            'border': 1, 'align': 'center'
        })
        cell_fmt = workbook.add_format({'border': 1})
        num_fmt = workbook.add_format({'border': 1, 'align': 'center'})

        # ── Header section ───────────────────────────────────────────────────
        row = 0
        ws.merge_range(row, 0, row, 8, 'PROBLEM EMPLOYEE REPORT', title_fmt)
        row += 1
        ws.merge_range(row, 0, row, 8, f'Period: {start_date} to {end_date}', info_fmt)
        row += 1

        # Filter criteria
        criteria = []
        if self.filter_late:
            criteria.append('Has Late days (tolerance applied)')
        if self.filter_absent:
            criteria.append('Has Absent days')
        if self.filter_leave:
            criteria.append('Has Time-off / Leave days')

        criteria_str = ' OR '.join(criteria) if criteria else 'None'
        ws.merge_range(row, 0, row, 8, f'Criteria: {criteria_str}', info_fmt)
        row += 1
        ws.merge_range(row, 0, row, 8,
            f'Result: {len(filtered_stats)} flagged out of {all_count} employees', info_fmt)
        row += 2

        # ── Table ────────────────────────────────────────────────────────────
        col_headers = [
            '#', 'Emp. ID', 'Employee Name',
            'Late\nDays', 'Late\nMinutes',
            'Absent\nDays', 'Leave/T-off\nDays',
            'Att. Rate\n%', 'Severity'
        ]
        for col, h in enumerate(col_headers):
            ws.write(row, col, h, header_fmt)
        row += 1

        # Sort: most absent first, then most late
        def _severity_score(s):
            return s['absent_count'] * 3 + s['late_count'] + s.get('leave_count', 0)

        # Severity baseline: score needed to reach "WARNING" level
        # (relative to what a "mild" problem employee looks like)
        base_threshold = 3  # 1 absent = 3pts, adjust for scale

        for idx, stat in enumerate(
            sorted(filtered_stats, key=_severity_score, reverse=True), 1
        ):
            emp = stat['employee']
            score = _severity_score(stat)

            if score >= base_threshold * 2:
                severity, sev_fmt = 'CRITICAL', critical_fmt
            elif score >= base_threshold:
                severity, sev_fmt = 'WARNING', warning_fmt
            else:
                severity, sev_fmt = 'WATCH', watch_fmt

            ws.write(row, 0, idx, num_fmt)
            ws.write(row, 1, emp.device_id_num or emp.barcode or '-', cell_fmt)
            ws.write(row, 2, emp.name, cell_fmt)
            ws.write(row, 3, stat['late_count'], num_fmt)
            ws.write(row, 4, stat['total_late_minutes'], num_fmt)
            ws.write(row, 5, stat['absent_count'], num_fmt)
            ws.write(row, 6, stat.get('leave_count', 0), num_fmt)
            ws.write(row, 7, f"{stat['attendance_rate']:.1f}%", num_fmt)
            ws.write(row, 8, severity, sev_fmt)
            row += 1

        # ── Severity legend ──────────────────────────────────────────────────
        row += 2
        ws.write(row, 0, 'SEVERITY LEGEND', workbook.add_format({'bold': True}))
        row += 1
        ws.write(row, 0, 'CRITICAL', critical_fmt)
        ws.write(row, 1, '2x or more above threshold', cell_fmt)
        row += 1
        ws.write(row, 0, 'WARNING', warning_fmt)
        ws.write(row, 1, 'At or above threshold', cell_fmt)
        row += 1
        ws.write(row, 0, 'WATCH', watch_fmt)
        ws.write(row, 1, 'Just below — worth monitoring', cell_fmt)

        # ── Column widths ────────────────────────────────────────────────────
        ws.set_column(0, 0, 4)    # #
        ws.set_column(1, 1, 12)   # ID
        ws.set_column(2, 2, 28)   # Name
        ws.set_column(3, 7, 13)   # Stats
        ws.set_column(8, 8, 11)   # Severity

    # ─────────────────────────────────────────────────────────────────────────

    def _get_device_allowed_keys(self, start_date, end_date):
        """Return set of (employee_id, date) that have a punch from selected device_ids,
        or None if no device filter is active."""
        if not self.device_ids:
            return None

        import pytz as _pytz
        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        tz = _pytz.timezone(tz_name)
        start_utc = tz.localize(datetime(start_date.year, start_date.month, start_date.day)).astimezone(_pytz.utc).replace(tzinfo=None)
        end_utc = tz.localize(datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)).astimezone(_pytz.utc).replace(tzinfo=None)

        punches = self.env['zk.machine.attendance'].sudo().search([
            ('punching_time', '>=', start_utc),
            ('punching_time', '<=', end_utc),
            ('device_id', 'in', self.device_ids.ids),
        ])

        allowed = set()
        for punch in punches:
            if not punch.employee_id.id:
                continue
            local_dt = _pytz.utc.localize(punch.punching_time).astimezone(tz)
            allowed.add((punch.employee_id.id, local_dt.date()))
        return allowed

    def _resolve_employees(self):
        """Apply employee + department filters to find target employees.

        Employees field takes precedence when set; otherwise the department
        filter is expanded to its members; otherwise all active employees.
        """
        if self.employee_ids:
            return self.employee_ids
        if self.department_ids:
            return self.env['hr.employee'].search([
                ('department_id', 'in', self.department_ids.ids),
            ])
        return self.env['hr.employee'].search([])

    def _generate_excel_report(self):
        """Generate Excel attendance sheet"""
        # Get employees
        employees = self._resolve_employees()

        if not employees:
            raise ValidationError(_('No employees found to generate report.'))

        start_date, end_date, month_name, year_int, num_days = self._get_date_range()

        # Create Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        if self.sheet_type == 'combined':
            self._create_combined_sheet(workbook, employees, start_date, end_date, month_name, year_int, num_days)
        else:
            self._create_individual_sheets(workbook, employees, start_date, end_date, month_name, year_int, num_days)

        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        safe_name = month_name.replace(' ', '_').replace('–', '-')
        file_name = f'Attendance_Sheet_{safe_name}.xlsx'
        self.write({
            'file_data': file_data,
            'file_name': file_name,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/employee.attendance.sheet.wizard/{self.id}/file_data/{file_name}?download=true',
            'target': 'self',
        }

    def _create_combined_sheet(self, workbook, employees, start_date, end_date, month_name, year, num_days):
        """Create combined sheet with all employees - Horizontal layout matching template"""
        worksheet = workbook.add_worksheet(f'{month_name} {year}')

        # Load weekend days from system configuration
        ICP = self.env['ir.config_parameter'].sudo()
        _day_codes = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
        weekend_days = set()
        for _num, _code in _day_codes.items():
            if ICP.get_param(f'dotbd_hr_zk_attendance_suite.weekend_{_code}', 'False') in ('True', '1', 'true'):
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

        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#B4C7E7',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 9,
        })

        weekend_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 9,
        })

        employee_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E7E6E6',
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
        })

        present_format = workbook.add_format({
            'bg_color': '#C6EFCE',
            'font_color': '#006100',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
        })

        absent_format = workbook.add_format({
            'bg_color': '#FFC7CE',
            'font_color': '#9C0006',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
        })

        late_format = workbook.add_format({
            'bg_color': '#FFEB9C',
            'font_color': '#9C6500',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
        })

        weekend_format = workbook.add_format({
            'bg_color': '#F2F2F2',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })

        leave_format = workbook.add_format({
            'bg_color': '#BDD7EE',
            'font_color': '#1F4E78',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
        })

        public_holiday_format = workbook.add_format({
            'bg_color': '#FFF2CC',
            'font_color': '#7F6000',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
        })

        mandatory_day_format = workbook.add_format({
            'bg_color': '#E6B8FF',  # Light blue for mandatory days
            'font_color': '#003366',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bold': True,
        })

        summary_format = workbook.add_format({
            'bold': True,
            'bg_color': '#FFF2CC',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })

        stats_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })

        # Set column widths
        # Layout: col 0 = Employee Name, col 1 = Department, col 2 = Designation,
        # cols 3..num_days+2 = day columns, cols num_days+3..num_days+15 = stats
        worksheet.set_column(0, 0, 12)  # Device ID column
        worksheet.set_column(1, 1, 22)  # Employee name column
        worksheet.set_column(2, 2, 18)  # Department
        worksheet.set_column(3, 3, 18)  # Designation
        worksheet.set_column(4, num_days + 3, 3.5)  # Day columns (narrower)
        worksheet.set_column(num_days + 4, num_days + 16, 12)  # Stats columns

        # Build the ordered date list for the entire range
        from datetime import timedelta as _td
        all_dates = [start_date + _td(days=i) for i in range(num_days)]

        # Device filter note at top (row 0); pushes title/header down by 1
        if self.device_ids:
            device_names = ', '.join(self.device_ids.mapped('name'))
            worksheet.merge_range(0, 0, 0, num_days + 15,
                f'Device Filter: {device_names}', workbook.add_format({
                    'bold': True, 'bg_color': '#D9E1F2', 'align': 'center', 'border': 1
                }))
            title_row, header_row, daynum_row, data_row_start = 1, 2, 3, 4
        else:
            title_row, header_row, daynum_row, data_row_start = 0, 1, 2, 3

        # Title row
        worksheet.merge_range(title_row, 0, title_row, num_days + 16,
            f'ATTENDANCE RECORD - {month_name}', title_format)

        # Headers - Day of week row
        row = header_row
        worksheet.write(row, 0, 'DEVICE\nID', header_format)
        worksheet.write(row, 1, 'EMPLOYEE\nNAME', header_format)
        worksheet.write(row, 2, 'DEPARTMENT', header_format)
        worksheet.write(row, 3, 'DESIGNATION', header_format)

        # Write day of week headers
        day_names = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
        for day_idx, current_date in enumerate(all_dates):
            col = day_idx + 4
            weekday = current_date.weekday()
            is_weekend = weekday in weekend_days
            day_format = weekend_header_format if is_weekend else header_format
            worksheet.write(row, col, day_names[weekday], day_format)

        # Write stats headers
        worksheet.write(row, num_days + 4, 'Total\nPresent', stats_header_format)
        worksheet.write(row, num_days + 5, 'Total\nAbsent', stats_header_format)
        worksheet.write(row, num_days + 6, 'Worked\nLeave Days', stats_header_format)
        worksheet.write(row, num_days + 7, 'Worked\nLeave Hours', stats_header_format)
        worksheet.write(row, num_days + 8, 'Absence\nLeave Days', stats_header_format)
        worksheet.write(row, num_days + 9, 'Absence\nLeave Hours', stats_header_format)
        worksheet.write(row, num_days + 10, 'Total\nLate', stats_header_format)
        worksheet.write(row, num_days + 11, 'Work\nHours', stats_header_format)
        worksheet.write(row, num_days + 12, 'Total Late\nTime (min)', stats_header_format)
        worksheet.write(row, num_days + 13, 'Late\nDays', stats_header_format)
        worksheet.write(row, num_days + 14, 'On Time\nDays', stats_header_format)
        worksheet.write(row, num_days + 15, 'Attendance\nRate %', stats_header_format)
        worksheet.write(row, num_days + 16, 'Ranking', stats_header_format)

        # Day numbers row (show dd or dd/mm for multi-month ranges)
        row = daynum_row
        worksheet.write(row, 0, '', header_format)
        worksheet.write(row, 1, '', header_format)
        worksheet.write(row, 2, '', header_format)
        worksheet.write(row, 3, '', header_format)
        single_month = (start_date.month == end_date.month and start_date.year == end_date.year)
        for day_idx, current_date in enumerate(all_dates):
            col = day_idx + 4
            is_weekend = current_date.weekday() in weekend_days
            day_format = weekend_header_format if is_weekend else header_format
            label = str(current_date.day) if single_month else f"{current_date.day}/{current_date.month}"
            worksheet.write(row, col, label, day_format)

        # Empty cells for stats headers row
        for col in range(num_days + 4, num_days + 17):
            worksheet.write(row, col, '', stats_header_format)

        # Get attendance data for all employees
        attendance_data = self._get_attendance_data(employees, start_date, end_date)

        # Calculate statistics for ranking
        employee_stats = []
        for employee in employees:
            emp_data = attendance_data.get(employee.id, {})
            # OFF weekdays for this employee (personal schedule → company policy
            # → default). Empty set = 7-day work week.
            _emp_off = employee._dotbd_weekend_weekdays(weekend_days, weekend_configured)
            # Mandatory days (hr.leave.mandatory.day) override a normal off-day.
            _emp_mandatory = employee._dotbd_mandatory_dates(start_date, end_date)

            present_count = 0
            absent_count = 0
            late_count = 0
            total_work_hours = 0
            total_late_minutes = 0
            on_time_count = 0
            leave_count = 0
            leave_types_dict = {}  # Track leave types: {leave_type_id: {name, code, count, hours}}

            daily_status = []

            for _di, current_date in enumerate(all_dates):
                day = _di + 1
                _wd = current_date.weekday()
                is_weekend = _wd in _emp_off
                if is_weekend and current_date in _emp_mandatory:
                    is_weekend = False   # mandatory day → working day
                day_data = emp_data.get(current_date, {})
                status = day_data.get('status', '')

                if status == 'present':
                    total_work_hours += day_data.get('worked_hours', 0)
                    if day_data.get('is_late'):
                        late_count += 1
                        total_late_minutes += day_data.get('late_minutes', 0)
                        daily_status.append('LT')
                    else:
                        on_time_count += 1
                        daily_status.append('P')
                    present_count += 1
                elif status == 'leave':
                    # On Leave - show leave code (e.g., SL, PL, CL)
                    leave_count += 1
                    leave_code = day_data.get('leave_code', 'L')
                    leave_type = day_data.get('leave_type', 'Leave')
                    leave_type_id = day_data.get('leave_type_id', 0)
                    leave_category = day_data.get('leave_category', 'absence')  # 'worked' or 'absence'
                    expected_hours = day_data.get('expected_hours', 8)

                    # Track this leave type
                    if leave_type_id not in leave_types_dict:
                        leave_types_dict[leave_type_id] = {
                            'name': leave_type,
                            'code': leave_code,
                            'category': leave_category,
                            'count': 0,
                            'hours': 0
                        }
                    leave_types_dict[leave_type_id]['count'] += 1
                    leave_types_dict[leave_type_id]['hours'] += expected_hours

                    daily_status.append(leave_code)
                elif status == 'mandatory_day':
                    # Mandatory Day - show 'M' for mandatory days
                    daily_status.append('M')
                elif status == 'public_holiday':
                    # Public Holiday - show 'H' for holiday
                    daily_status.append('H')
                elif status == 'weekend':
                    daily_status.append('-')
                elif status == 'absent':
                    if not is_weekend:
                        absent_count += 1
                        daily_status.append('A')
                    else:
                        daily_status.append('-')
                else:
                    if is_weekend:
                        daily_status.append('-')
                    else:
                        daily_status.append('')

            # Calculate attendance rate: only days employee was expected (not on leave/holiday)
            effective_days = present_count + absent_count
            attendance_rate = (present_count / effective_days * 100) if effective_days > 0 else 100.0

            employee_stats.append({
                'employee': employee,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'total_work_hours': total_work_hours,
                'total_late_minutes': total_late_minutes,
                'on_time_count': on_time_count,
                'leave_count': leave_count,
                'leave_types': leave_types_dict,  # Leave types breakdown
                'attendance_rate': attendance_rate,
                'daily_status': daily_status,
            })

        max_work_hours = max([stat['total_work_hours'] for stat in employee_stats]) if employee_stats else 1
        max_on_time = max([stat['on_time_count'] for stat in employee_stats]) if employee_stats else 1

        for stat in employee_stats:
            # POSITIVE POINTS
            # 1. Attendance Rate Points (40 points max)
            attendance_points = (stat['attendance_rate'] / 100) * 70

            # 2. On-time Days Points (30 points max)
            on_time_points = 0
            if max_on_time > 0:
                on_time_points = (stat['on_time_count'] / max_on_time) * 15

            # 3. Work Hours Points (30 points max)
            work_hours_points = 0
            if max_work_hours > 0:
                work_hours_points = (stat['total_work_hours'] / max_work_hours) * 15

            # NEGATIVE POINTS
            # 4. Absent Days Penalty (-3 points per absent day)
            absent_penalty = stat['absent_count'] * 3

            # 5. Late Days Penalty (-1 point per late day)
            late_penalty = stat['late_count'] * 1

            # 6. Late Minutes Penalty (-0.1 points per minute)
            late_minutes_penalty = stat['total_late_minutes'] * 0.1

            # 7. Absence Leave Penalty (-2 points per absence leave day)
            absence_leave_days = sum(lt['count'] for lt in stat['leave_types'].values() if lt.get('category') == 'absence')
            absence_leave_penalty = absence_leave_days * 2

            # BONUS POINTS FOR WORKED LEAVE
            # 8. Worked Leave Bonus (+1 point per worked leave day - counts as productive time)
            worked_leave_days = sum(lt['count'] for lt in stat['leave_types'].values() if lt.get('category') == 'worked')
            worked_leave_bonus = worked_leave_days * 1

            # Calculate total points
            total_points = (attendance_points + on_time_points + work_hours_points + worked_leave_bonus -
                            absent_penalty - late_penalty - late_minutes_penalty - absence_leave_penalty)

            stat['total_points'] = round(total_points, 2)

        # ── Apply problem employee filter (if thresholds set) ─────────────────
        all_employee_count = len(employee_stats)
        filter_active = self.filter_late or self.filter_absent or self.filter_leave
        if filter_active:
            employee_stats = self._filter_problem_employees(employee_stats)

        # Sort filtered set by total points (highest first) and re-rank
        sorted_stats = sorted(employee_stats, key=lambda x: x['total_points'], reverse=True)
        for rank, stat in enumerate(sorted_stats, 1):
            stat['rank'] = rank

        # ── Filter note on title ───────────────────────────────────────────
        if filter_active:
            criteria_parts = []
            if self.filter_late:
                criteria_parts.append('Has Late days')
            if self.filter_absent:
                criteria_parts.append('Has Absent days')
            if self.filter_leave:
                criteria_parts.append('Has Time-off/Leave')
            filter_note = f'  |  FILTER: {" OR ".join(criteria_parts)}  |  {len(employee_stats)} of {all_employee_count} employees'
            # Rewrite the title cell to include filter info (cells already merged at line 496)
            worksheet.write(title_row, 0,
                f'ATTENDANCE RECORD - {month_name}{filter_note}',
                workbook.add_format({
                    'bold': True, 'font_size': 11, 'align': 'center', 'valign': 'vcenter',
                    'bg_color': '#FFE699'
                }))
            if not employee_stats:
                # Nothing to show — write a message and skip rows
                worksheet.merge_range(data_row_start, 0, data_row_start, num_days + 16,
                    'No employees matched the filter criteria.',
                    workbook.add_format({'italic': True, 'align': 'center', 'border': 1}))
                return

        # Write employee rows
        row = data_row_start
        for stats in employee_stats:
            emp = stats['employee']
            device_id = emp.device_id_num or emp.barcode or ''
            worksheet.write(row, 0, device_id, employee_format)
            worksheet.write(row, 1, emp.name, employee_format)
            worksheet.write(row, 2, emp.department_id.name or '' if emp.department_id else '', employee_format)
            worksheet.write(row, 3, (emp.job_id.name if emp.job_id else '') or emp.job_title or '', employee_format)

            # Write daily attendance
            _emp_off_row = emp._dotbd_weekend_weekdays(weekend_days, weekend_configured)
            for _dj, current_date in enumerate(all_dates):
                day = _dj + 1
                _wd = current_date.weekday()
                is_weekend = _wd in _emp_off_row
                col = _dj + 4
                status = stats['daily_status'][_dj]

                if status == 'P':
                    worksheet.write(row, col, 'P', present_format)
                elif status == 'A':
                    worksheet.write(row, col, 'A', absent_format)
                elif status == 'LT':
                    worksheet.write(row, col, 'LT', late_format)
                elif status == 'M':
                    worksheet.write(row, col, 'M', mandatory_day_format)
                elif status == 'H':
                    worksheet.write(row, col, 'H', public_holiday_format)
                elif status == '-':
                    worksheet.write(row, col, '-', weekend_format)
                elif status and status not in ['P', 'A', 'LT', 'H', '-', '']:
                    # Leave codes (L, SL, PL, CL, etc.)
                    worksheet.write(row, col, status, leave_format)
                else:
                    worksheet.write(row, col, '', weekend_format if is_weekend else None)

            # Write statistics
            worksheet.write(row, num_days + 4, stats['present_count'], summary_format)
            worksheet.write(row, num_days + 5, stats['absent_count'], summary_format)

            # Calculate worked and absence leave days/hours separately
            worked_leave_days = sum(lt['count'] for lt in stats['leave_types'].values() if lt.get('category') == 'worked')
            worked_leave_hours = sum(lt['hours'] for lt in stats['leave_types'].values() if lt.get('category') == 'worked')
            absence_leave_days = sum(lt['count'] for lt in stats['leave_types'].values() if lt.get('category') == 'absence')
            absence_leave_hours = sum(lt['hours'] for lt in stats['leave_types'].values() if lt.get('category') == 'absence')

            worksheet.write(row, num_days + 6, worked_leave_days, summary_format)
            worksheet.write(row, num_days + 7, _fmt_hm(worked_leave_hours), summary_format)
            worksheet.write(row, num_days + 8, absence_leave_days, summary_format)
            worksheet.write(row, num_days + 9, _fmt_hm(absence_leave_hours), summary_format)
            worksheet.write(row, num_days + 10, stats['late_count'], summary_format)
            worksheet.write(row, num_days + 11, _fmt_hm(stats['total_work_hours']), summary_format)
            worksheet.write(row, num_days + 12, stats['total_late_minutes'], summary_format)
            worksheet.write(row, num_days + 13, stats['late_count'], summary_format)
            worksheet.write(row, num_days + 14, stats['on_time_count'], summary_format)
            worksheet.write(row, num_days + 15, f"{stats['attendance_rate']:.1f}%", summary_format)

            # Ranking with color coding
            rank_format = workbook.add_format({
                'bold': True,
                'bg_color': '#C6EFCE' if stats['rank'] <= 3 else '#FFC7CE' if stats['rank'] > len(employees) - 3 else '#FFEB9C',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
            })
            worksheet.write(row, num_days + 16, stats['rank'], rank_format)

            row += 1

        # Add legend
        # ============================================
        # RANKING CALCULATION TABLE
        # ============================================
        row += 3

        # Title
        ranking_title_format = workbook.add_format({
            'bold': True, 'font_size': 12, 'align': 'center',
            'bg_color': '#4472C4', 'font_color': 'white', 'border': 1
        })
        worksheet.merge_range(row, 0, row, 11, 'EMPLOYEE RANKING CALCULATION BREAKDOWN', ranking_title_format)
        row += 1

        # Headers
        ranking_header_format = workbook.add_format({
            'bold': True, 'bg_color': '#B4C7E7', 'align': 'center',
            'valign': 'vcenter', 'border': 1, 'text_wrap': True
        })

        headers = ['Device\nID', 'Department', 'Employee Name', 'Present\nPoints', 'Late\nPoints',
                   'Absent\nPoints', 'Leave\nPoints', 'Overtime\nPoints', 'Undertime\nPoints',
                   'Other\nPoints', 'Total\nPoints', 'Rank']

        for col, header in enumerate(headers):
            worksheet.write(row, col, header, ranking_header_format)

        worksheet.set_column(0, 0, 12)
        worksheet.set_column(1, 1, 18)
        worksheet.set_column(2, 2, 25)
        worksheet.set_column(3, 11, 12)
        row += 1

        # Build detailed stats by reusing the already-computed employee_stats
        # (avoids a second different formula that would produce inconsistent rankings)
        stats_by_rank = sorted(employee_stats, key=lambda x: x['total_points'], reverse=True)
        detailed_stats = []
        for rank, stat in enumerate(stats_by_rank, 1):
            lt = stat['leave_types']
            absence_leave_days = sum(v['count'] for v in lt.values() if v.get('category') == 'absence')
            worked_leave_days = sum(v['count'] for v in lt.values() if v.get('category') == 'worked')

            # Mirror the same formula used in the main ranking
            attendance_points = (stat['attendance_rate'] / 100) * 70
            on_time_points = (stat['on_time_count'] / max_on_time) * 15 if max_on_time > 0 else 0
            work_hours_points = (stat['total_work_hours'] / max_work_hours) * 15 if max_work_hours > 0 else 0
            absent_penalty = stat['absent_count'] * 3
            late_penalty = stat['late_count'] * 1
            late_minutes_penalty = stat['total_late_minutes'] * 0.1
            absence_leave_penalty = absence_leave_days * 2
            worked_leave_bonus = worked_leave_days * 1

            detailed_stats.append({
                'employee': stat['employee'],
                'present_points': round(attendance_points + on_time_points + work_hours_points, 2),
                'late_points': round(-late_penalty - late_minutes_penalty, 2),
                'absent_points': round(-absent_penalty, 2),
                'leave_points': round(worked_leave_bonus - absence_leave_penalty, 2),
                'overtime_points': 0,
                'undertime_points': 0,
                'other_points': 0,
                'total_points': stat['total_points'],
                'rank': rank,
            })

        # Formats
        positive_format = workbook.add_format({
            'border': 1, 'align': 'center', 'bg_color': '#C6EFCE',
            'font_color': '#006100', 'num_format': '0.00'
        })
        negative_format = workbook.add_format({
            'border': 1, 'align': 'center', 'bg_color': '#FFC7CE',
            'font_color': '#9C0006', 'num_format': '0.00'
        })
        neutral_format = workbook.add_format({
            'border': 1, 'align': 'center', 'num_format': '0.00'
        })
        employee_name_format = workbook.add_format({
            'border': 1, 'align': 'left', 'bold': True
        })
        total_format = workbook.add_format({
            'border': 1, 'align': 'center', 'bold': True,
            'bg_color': '#FFF2CC', 'num_format': '0.00'
        })

        # Write data
        for stat in detailed_stats:
            _re = stat['employee']
            worksheet.write(row, 0, _re.device_id_num or _re.barcode or '', employee_name_format)
            worksheet.write(row, 1, _re.department_id.name or '' if _re.department_id else '', employee_name_format)
            worksheet.write(row, 2, _re.name, employee_name_format)
            worksheet.write(row, 3, stat['present_points'],
                            positive_format if stat['present_points'] > 0 else neutral_format)
            worksheet.write(row, 4, stat['late_points'],
                            negative_format if stat['late_points'] < 0 else neutral_format)
            worksheet.write(row, 5, stat['absent_points'],
                            negative_format if stat['absent_points'] < 0 else neutral_format)
            worksheet.write(row, 6, stat['leave_points'],
                            negative_format if stat['leave_points'] < 0 else neutral_format)
            worksheet.write(row, 7, stat['overtime_points'],
                            positive_format if stat['overtime_points'] > 0 else neutral_format)
            worksheet.write(row, 8, stat['undertime_points'],
                            negative_format if stat['undertime_points'] < 0 else neutral_format)
            worksheet.write(row, 9, stat['other_points'],
                            negative_format if stat['other_points'] < 0 else neutral_format)
            worksheet.write(row, 10, stat['total_points'], total_format)

            rank_color = workbook.add_format({
                'border': 1, 'align': 'center', 'bold': True,
                'bg_color': '#C6EFCE' if stat['rank'] <= 3 else
                '#FFC7CE' if stat['rank'] > len(employees) - 3 else '#FFEB9C'
            })
            worksheet.write(row, 11, stat['rank'], rank_color)
            row += 1

        # ============================================
        # POINTS LEGEND
        # ============================================
        row += 2
        point_legend_format = workbook.add_format({
            'bold': True, 'font_size': 11, 'bg_color': '#D9E1F2', 'border': 1
        })
        worksheet.merge_range(row, 0, row, 9, 'POINTS CALCULATION LEGEND', point_legend_format)
        row += 1

        legend_label = workbook.add_format({'bold': True, 'border': 1})
        legend_desc = workbook.add_format({'border': 1})

        legends = [
            ('Present Points:', '+1.0 point per on-time day (P status)', positive_format),
            ('Late Points:', '-1.0 point per late arrival (LT status)', negative_format),
            ('Absent Points:', '-3.0 points per absent day (A status)', negative_format),
            ('Leave Points:', '-2.0 points per leave day (V status)', negative_format),
            ('Overtime Points:', '+0.25 points per extra hour worked', positive_format),
            ('Undertime Points:', '-0.25 points per hour short', negative_format),
            ('Other Points:', '-0.1 points per late minute', negative_format),
        ]

        for label, desc, fmt in legends:
            worksheet.write(row, 0, label, legend_label)
            worksheet.merge_range(row, 1, row, 8, desc, legend_desc)
            worksheet.write(row, 9, 'Sample', fmt)
            row += 1

        # ============================================
        # STATUS LEGEND (Original)
        # ============================================
        row += 2
        legend_label_format = workbook.add_format({'bold': True})
        worksheet.write(row, 0, 'STATUS LEGEND:', legend_label_format)
        row += 1
        worksheet.write(row, 0, 'P = Present (On Time)', present_format)
        row += 1
        worksheet.write(row, 0, 'A = Absent', absent_format)
        row += 1
        worksheet.write(row, 0, 'LT = Late Check-in', late_format)
        row += 1
        worksheet.write(row, 0, 'L / Code = Leave (e.g. SL, PL, CL)', leave_format)
        row += 1
        worksheet.write(row, 0, 'H = Public Holiday', public_holiday_format)
        row += 1
        worksheet.write(row, 0, 'M = Mandatory Day', mandatory_day_format)
        row += 1
        worksheet.write(row, 0, '- = Weekend/Holiday', weekend_format)

        # ============================================
        # LEAVE TYPES SUMMARY
        # ============================================
        # Collect all unique leave types from all employees
        all_leave_types = {}
        for stat in employee_stats:
            for leave_type_id, leave_data in stat.get('leave_types', {}).items():
                if leave_type_id not in all_leave_types:
                    all_leave_types[leave_type_id] = {
                        'name': leave_data['name'],
                        'code': leave_data['code'],
                        'total_days': 0,
                        'total_hours': 0
                    }
                all_leave_types[leave_type_id]['total_days'] += leave_data['count']
                all_leave_types[leave_type_id]['total_hours'] += leave_data['hours']

        if all_leave_types:
            row += 2
            worksheet.write(row, 0, 'LEAVE TYPES SUMMARY:', legend_label_format)
            row += 1

            # Table header
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D9E1F2',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            data_format = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })

            worksheet.write(row, 0, 'Code', header_format)
            worksheet.write(row, 1, 'Leave Type', header_format)
            worksheet.write(row, 2, 'Total Days', header_format)
            worksheet.write(row, 3, 'Total Hours', header_format)
            row += 1

            # Sort by leave code for consistent display
            sorted_leaves = sorted(all_leave_types.values(), key=lambda x: x['code'])

            for leave_info in sorted_leaves:
                worksheet.write(row, 0, leave_info['code'], leave_format)
                worksheet.write(row, 1, leave_info['name'], data_format)
                worksheet.write(row, 2, leave_info['total_days'], data_format)
                worksheet.write(row, 3, _fmt_hm(leave_info['total_hours']), data_format)
                row += 1

            # Add explanation
            row += 1
            explanation_format = workbook.add_format({
                'italic': True,
                'font_size': 9,
                'text_wrap': True
            })
            worksheet.merge_range(row, 0, row, 3,
                'Note: Leave codes appear in the attendance grid. Each leave type has a unique code for easy identification.',
                explanation_format)

        # ── Problem Summary sheet (only when filter is active) ────────────────
        if filter_active and employee_stats:
            self._create_problem_summary_sheet(
                workbook, employee_stats, all_employee_count, start_date, end_date
            )

        # ── Holiday & Mandatory Days Summary ───────────────────────────────────
        self._create_holiday_summary_sheet(
            workbook, start_date, end_date, month_name, year
        )

    def _create_holiday_summary_sheet(self, workbook, start_date, end_date, month_name, year):
        """Add a sheet listing all public holidays and mandatory days in the date range"""
        ws = workbook.add_worksheet('Holidays & Mandatory Days')

        # ── Formats ─────────────────────────────────────────────────────
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E2EFDA',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        holiday_format = workbook.add_format({
            'bg_color': '#FFF2CC',
            'font_color': '#7F6000',
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
        })

        mandatory_format = workbook.add_format({
            'bg_color': '#E6B8FF',
            'font_color': '#003366',
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
        })

        data_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        # ── Title ───────────────────────────────────────────────────────
        ws.merge_range(0, 0, 0, 5, f'Holidays & Mandatory Days - {month_name} {year}', title_format)

        row = 2
        ws.write(row, 0, 'Type', header_format)
        ws.write(row, 1, 'Date', header_format)
        ws.write(row, 2, 'Date', header_format)
        ws.write(row, 3, 'Name / Leave Type', header_format)
        ws.write(row, 4, 'Description', header_format)
        ws.set_column(0, 0, 20)
        ws.set_column(1, 1, 12)
        ws.set_column(2, 2, 12)
        ws.set_column(3, 3, 25)
        ws.set_column(4, 4, 40)
        row += 1

        # ── Public Holidays ─────────────────────────────────────────────
        company = self.env.company
        CalendarLeaves = self.env['resource.calendar.leaves']
        public_holidays = CalendarLeaves.search([
            ('resource_id', '=', False),  # Public holidays
            ('date_from', '<=', end_date),
            ('date_to', '>=', start_date),
            '|', ('calendar_id.company_id', '=', company.id),
                 ('calendar_id', '=', False)  # Include global holidays too
        ], order='date_from asc')

        if public_holidays:
            row += 1
            ws.merge_range(row, 0, row, 5, 'PUBLIC HOLIDAYS', header_format)
            row += 1
            for holiday in public_holidays:
                h_start = holiday.date_from.date()
                h_end = holiday.date_to.date()
                ws.write(row, 0, 'Public Holiday', holiday_format)
                ws.write(row, 1, h_start.strftime('%b %d, %Y'), data_format)
                ws.write(row, 2, h_end.strftime('%b %d, %Y'), data_format)
                ws.write(row, 3, holiday.name or 'Public Holiday', data_format)
                ws.write(row, 4, '', data_format)
                row += 1
        row += 1

        # ── Mandatory Leave Days ───────────────────────────────────────────
        has_leave_module = 'hr.leave' in self.env
        if has_leave_module:
            LeaveType = self.env['hr.leave.type']
            mandatory_leave_types = LeaveType.search([('is_mandatory', '=', True)])

            if mandatory_leave_types:
                Leave = self.env['hr.leave']
                mandatory_leaves = Leave.search([
                    ('holiday_status_id', 'in', mandatory_leave_types.ids),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', end_date),
                    ('date_to', '>=', start_date),
                ], order='date_from asc')

                if mandatory_leaves:
                    ws.merge_range(row, 0, row, 5, 'MANDATORY DAYS', header_format)
                    row += 1
                    for leave in mandatory_leaves:
                        lt = leave.holiday_status_id
                        l_start = leave.date_from.date()
                        l_end = leave.date_to.date()
                        code = lt.leave_short_code or 'M'
                        ws.write(row, 0, f'Mandatory ({code})', mandatory_format)
                        ws.write(row, 1, l_start.strftime('%b %d, %Y'), data_format)
                        ws.write(row, 2, l_end.strftime('%b %d, %Y'), data_format)
                        ws.write(row, 3, lt.name, data_format)
                        ws.write(row, 4, leave.name or '', data_format)
                        row += 1
                    row += 1

        # ── Add legend ─────────────────────────────────────────────────
        row += 1
        ws.merge_range(row, 0, row, 5,
            'Legend: Public holidays are company-wide days off. Mandatory days are specific leave types marked as required.',
            workbook.add_format({'italic': True, 'font_size': 9}))

    def _create_individual_sheets(self, workbook, employees, start_date, end_date, month_name, year, num_days):
        """Create individual sheets for each employee - Horizontal layout matching template"""
        # Get attendance data for all employees at once
        attendance_data = self._get_attendance_data(employees, start_date, end_date)

        from datetime import timedelta as _td2
        all_dates = [start_date + _td2(days=i) for i in range(num_days)]
        single_month = (start_date.month == end_date.month and start_date.year == end_date.year)

        # Load weekend days from system configuration
        ICP = self.env['ir.config_parameter'].sudo()
        _day_codes = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
        weekend_days = set()
        for _num, _code in _day_codes.items():
            if ICP.get_param(f'dotbd_hr_zk_attendance_suite.weekend_{_code}', 'False') in ('True', '1', 'true'):
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

        for employee in employees:
            # Create sheet for each employee
            # Sanitize sheet name (Excel has 31 char limit and special char restrictions)
            sheet_name = employee.name[:31].replace('/', '-').replace('\\', '-').replace('[', '(').replace(']', ')')
            worksheet = workbook.add_worksheet(sheet_name)

            # Define formats
            title_format = workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'center',
                'valign': 'vcenter',
            })

            info_format = workbook.add_format({
                'bold': True,
                'align': 'left',
                'valign': 'vcenter',
                'font_size': 11,
            })

            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#B4C7E7',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'font_size': 9,
            })

            weekend_header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#D9E1F2',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'font_size': 9,
            })

            present_format = workbook.add_format({
                'bg_color': '#C6EFCE',
                'font_color': '#006100',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bold': True,
            })

            absent_format = workbook.add_format({
                'bg_color': '#FFC7CE',
                'font_color': '#9C0006',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bold': True,
            })

            late_format = workbook.add_format({
                'bg_color': '#FFEB9C',
                'font_color': '#9C6500',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bold': True,
            })

            weekend_format = workbook.add_format({
                'bg_color': '#F2F2F2',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
            })

            leave_format = workbook.add_format({
                'bg_color': '#BDD7EE',
                'font_color': '#1F4E78',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bold': True,
            })

            public_holiday_format = workbook.add_format({
                'bg_color': '#FFF2CC',
                'font_color': '#7F6000',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bold': True,
            })

            mandatory_day_format = workbook.add_format({
                'bg_color': '#E6B8FF',
                'font_color': '#003366',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
                'bold': True,
            })

            summary_format = workbook.add_format({
                'bold': True,
                'bg_color': '#FFF2CC',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
            })

            stats_header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
                'font_color': 'white',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1,
            })

            # Set column widths
            worksheet.set_column(0, 0, 20)  # Label column
            worksheet.set_column(1, num_days, 3.5)  # Day columns (narrower)
            worksheet.set_column(num_days + 1, num_days + 12, 12)  # Stats columns

            # Title row
            row = 0
            worksheet.merge_range(row, 0, row, num_days + 12,
                                 f'ATTENDANCE RECORD - {month_name} {year}', title_format)

            # Employee info section
            row += 2
            worksheet.write(row, 0, 'Employee:', info_format)
            worksheet.merge_range(row, 1, row, 5, employee.name)
            row += 1

            device_id = employee.device_id_num or employee.barcode or 'No ID'
            if device_id:
                worksheet.write(row, 0, 'Device ID:', info_format)
                worksheet.merge_range(row, 1, row, 5, device_id)
                row += 1

            if employee.department_id:
                worksheet.write(row, 0, 'Department:', info_format)
                worksheet.merge_range(row, 1, row, 5, employee.department_id.name)
                row += 1

            if employee.job_id:
                worksheet.write(row, 0, 'Job Position:', info_format)
                worksheet.merge_range(row, 1, row, 5, employee.job_id.name)
                row += 1

            row += 1

            # Headers - Day of week row
            worksheet.write(row, 0, 'Status', header_format)

            # Write day of week headers (M/T/W/T/F/S/S pattern)
            day_names = ['M', 'T', 'W', 'T', 'F', 'S', 'S']
            for _di, current_date in enumerate(all_dates):
                col = _di + 1
                weekday = current_date.weekday()
                is_weekend = weekday in weekend_days
                day_format = weekend_header_format if is_weekend else header_format
                worksheet.write(row, col, day_names[weekday], day_format)

            # Write stats headers
            worksheet.write(row, num_days + 1, 'Total\nPresent', stats_header_format)
            worksheet.write(row, num_days + 2, 'Total\nAbsent', stats_header_format)
            worksheet.write(row, num_days + 3, 'Worked\nLeave Days', stats_header_format)
            worksheet.write(row, num_days + 4, 'Worked\nLeave Hours', stats_header_format)
            worksheet.write(row, num_days + 5, 'Absence\nLeave Days', stats_header_format)
            worksheet.write(row, num_days + 6, 'Absence\nLeave Hours', stats_header_format)
            worksheet.write(row, num_days + 7, 'Total\nLate', stats_header_format)
            worksheet.write(row, num_days + 8, 'Work\nHours', stats_header_format)
            worksheet.write(row, num_days + 9, 'Total Late\nTime (min)', stats_header_format)
            worksheet.write(row, num_days + 10, 'Late\nDays', stats_header_format)
            worksheet.write(row, num_days + 11, 'On Time\nDays', stats_header_format)
            worksheet.write(row, num_days + 12, 'Attendance\nRate %', stats_header_format)

            # Day numbers row
            row += 1
            worksheet.write(row, 0, '', header_format)
            for _dj, current_date in enumerate(all_dates):
                col = _dj + 1
                is_weekend = current_date.weekday() in weekend_days
                day_format = weekend_header_format if is_weekend else header_format
                label = str(current_date.day) if single_month else f"{current_date.day}/{current_date.month}"
                worksheet.write(row, col, label, day_format)

            # Empty cells for stats headers row
            for col in range(num_days + 1, num_days + 13):
                worksheet.write(row, col, '', stats_header_format)

            # Get employee attendance data
            emp_data = attendance_data.get(employee.id, {})

            # Per-employee OFF weekdays (personal schedule -> company policy -> default)
            _ind_off = employee._dotbd_weekend_weekdays(weekend_days, weekend_configured)

            # Calculate statistics
            present_count = 0
            absent_count = 0
            late_count = 0
            total_work_hours = 0
            total_late_minutes = 0
            on_time_count = 0
            leave_count = 0
            leave_types_dict = {}  # Track leave types for this employee
            daily_status = []

            for _di, current_date in enumerate(all_dates):
                day = _di + 1
                _wd = current_date.weekday()
                is_weekend = _wd in _ind_off
                day_data = emp_data.get(current_date, {})
                status = day_data.get('status', '')

                if status == 'present':
                    total_work_hours += day_data.get('worked_hours', 0)
                    if day_data.get('is_late'):
                        late_count += 1
                        total_late_minutes += day_data.get('late_minutes', 0)
                        daily_status.append('LT')
                    else:
                        on_time_count += 1
                        daily_status.append('P')
                    present_count += 1
                elif status == 'leave':
                    leave_count += 1
                    # On Leave - show leave code (e.g., SL, PL, CL)
                    leave_code = day_data.get('leave_code', 'L')
                    leave_type = day_data.get('leave_type', 'Leave')
                    leave_type_id = day_data.get('leave_type_id', 0)
                    leave_category = day_data.get('leave_category', 'absence')  # 'worked' or 'absence'
                    expected_hours = day_data.get('expected_hours', 8)

                    # Track this leave type
                    if leave_type_id not in leave_types_dict:
                        leave_types_dict[leave_type_id] = {
                            'name': leave_type,
                            'code': leave_code,
                            'category': leave_category,
                            'count': 0,
                            'hours': 0
                        }
                    leave_types_dict[leave_type_id]['count'] += 1
                    leave_types_dict[leave_type_id]['hours'] += expected_hours

                    daily_status.append(leave_code)
                elif status == 'mandatory_day':
                    # Mandatory Day - show 'M' for mandatory days
                    daily_status.append('M')
                elif status == 'public_holiday':
                    # Public Holiday - show 'H' for holiday
                    daily_status.append('H')
                elif status == 'weekend':
                    daily_status.append('-')
                elif status == 'absent':
                    if not is_weekend:
                        absent_count += 1
                        daily_status.append('A')
                    else:
                        daily_status.append('-')
                else:
                    if is_weekend:
                        daily_status.append('-')
                    else:
                        daily_status.append('')

            # Calculate attendance rate: only days employee was expected (not on leave/holiday)
            effective_days = present_count + absent_count
            attendance_rate = (present_count / effective_days * 100) if effective_days > 0 else 100.0

            # Write attendance row
            row += 1
            worksheet.write(row, 0, '', header_format)

            # Write daily attendance
            for _dk, current_date in enumerate(all_dates):
                day = _dk + 1
                _wd = current_date.weekday()
                is_weekend = _wd in _ind_off
                col = day
                status = daily_status[_dk]

                if status == 'P':
                    worksheet.write(row, col, 'P', present_format)
                elif status == 'A':
                    worksheet.write(row, col, 'A', absent_format)
                elif status == 'LT':
                    worksheet.write(row, col, 'LT', late_format)
                elif status == 'M':
                    worksheet.write(row, col, 'M', mandatory_day_format)
                elif status == 'H':
                    worksheet.write(row, col, 'H', public_holiday_format)
                elif status == '-':
                    worksheet.write(row, col, '-', weekend_format)
                elif status and status not in ['P', 'A', 'LT', 'H', '-', '']:
                    # Leave codes (L, SL, PL, CL, etc.)
                    worksheet.write(row, col, status, leave_format)
                else:
                    worksheet.write(row, col, '', weekend_format if is_weekend else None)

            # Calculate worked and absence leave days/hours separately
            worked_leave_days = sum(lt['count'] for lt in leave_types_dict.values() if lt.get('category') == 'worked')
            worked_leave_hours = sum(lt['hours'] for lt in leave_types_dict.values() if lt.get('category') == 'worked')
            absence_leave_days = sum(lt['count'] for lt in leave_types_dict.values() if lt.get('category') == 'absence')
            absence_leave_hours = sum(lt['hours'] for lt in leave_types_dict.values() if lt.get('category') == 'absence')

            # Write statistics
            worksheet.write(row, num_days + 1, present_count, summary_format)
            worksheet.write(row, num_days + 2, absent_count, summary_format)
            worksheet.write(row, num_days + 3, worked_leave_days, summary_format)
            worksheet.write(row, num_days + 4, _fmt_hm(worked_leave_hours), summary_format)
            worksheet.write(row, num_days + 5, absence_leave_days, summary_format)
            worksheet.write(row, num_days + 6, _fmt_hm(absence_leave_hours), summary_format)
            worksheet.write(row, num_days + 7, late_count, summary_format)
            worksheet.write(row, num_days + 8, _fmt_hm(total_work_hours), summary_format)
            worksheet.write(row, num_days + 9, total_late_minutes, summary_format)
            worksheet.write(row, num_days + 10, late_count, summary_format)
            worksheet.write(row, num_days + 11, on_time_count, summary_format)
            worksheet.write(row, num_days + 12, f"{attendance_rate:.1f}%", summary_format)

            # Add legend
            row += 3
            legend_label_format = workbook.add_format({'bold': True})
            worksheet.write(row, 0, 'Legend:', legend_label_format)
            row += 1
            worksheet.write(row, 0, 'P = Present (On Time)', present_format)
            row += 1
            worksheet.write(row, 0, 'A = Absent', absent_format)
            row += 1
            worksheet.write(row, 0, 'LT = Late Check-in', late_format)
            row += 1
            worksheet.write(row, 0, 'L / Code = Leave (e.g. SL, PL, CL)', leave_format)
            row += 1
            worksheet.write(row, 0, 'H = Public Holiday', public_holiday_format)
            row += 1
            worksheet.write(row, 0, '- = Weekend/Holiday', weekend_format)

            # Add leave types summary for this employee if they have leaves
            if leave_types_dict:
                row += 2
                worksheet.write(row, 0, 'Leave Types Summary:', legend_label_format)
                row += 1

                # Table header
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#D9E1F2',
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter'
                })
                data_format = workbook.add_format({
                    'border': 1,
                    'align': 'center',
                    'valign': 'vcenter'
                })

                worksheet.write(row, 0, 'Code', header_format)
                worksheet.write(row, 1, 'Leave Type', header_format)
                worksheet.write(row, 2, 'Days', header_format)
                worksheet.write(row, 3, 'Hours', header_format)
                row += 1

                # Sort by leave code for consistent display
                sorted_leaves = sorted(leave_types_dict.values(), key=lambda x: x['code'])

                for leave_info in sorted_leaves:
                    worksheet.write(row, 0, leave_info['code'], leave_format)
                    worksheet.write(row, 1, leave_info['name'], data_format)
                    worksheet.write(row, 2, leave_info['count'], data_format)
                    worksheet.write(row, 3, _fmt_hm(leave_info['hours']), data_format)
                    row += 1

    def _get_attendance_data(self, employees, start_date, end_date):
        """Get attendance data for employees in date range with Time Off integration.
        Applies device filter (self.device_ids) when set."""
        AttendanceSummary = self.env['attendance.summary.analysis']
        summary_data = AttendanceSummary.get_attendance_summary(
            employee_ids=employees.ids,
            start_date=start_date,
            end_date=end_date
        )

        # Device filter: build allowed (employee_id, date) set
        allowed_keys = self._get_device_allowed_keys(start_date, end_date)

        attendance_dict = {}
        for record in summary_data:
            emp_id = record['employee_id']
            date = record['date']

            if emp_id not in attendance_dict:
                attendance_dict[emp_id] = {}

            status = record['status']
            # Device filter: a 'present' day where the punch didn't come from the selected
            # device(s) is treated as absent in the report.
            if status == 'present' and allowed_keys is not None and (emp_id, date) not in allowed_keys:
                status = 'absent'

            attendance_dict[emp_id][date] = {
                'status': status,
                'is_late': record.get('is_late', False),
                'worked_hours': record.get('worked_hours', 0),
                'expected_hours': record.get('expected_hours', 8),
                'late_minutes': record.get('late_minutes', 0),
                'leave_type': record.get('leave_type', ''),
                'leave_code': record.get('leave_code', 'L'),
                'leave_type_id': record.get('leave_type_id', False),
                'leave_category': record.get('leave_category', 'absence'),
                'holiday_name': record.get('holiday_name', ''),
            }

        return attendance_dict

    def _get_holidays_mandatory_for_pdf(self, start_date, end_date):
        """Get holidays and mandatory days for PDF report display"""
        holidays = []
        mandatory_days = []

        company = self.env.company

        # Public Holidays
        CalendarLeaves = self.env['resource.calendar.leaves']
        public_holidays = CalendarLeaves.search([
            ('resource_id', '=', False),
            ('date_from', '<=', end_date),
            ('date_to', '>=', start_date),
            '|', ('calendar_id.company_id', '=', company.id),
                 ('calendar_id', '=', False)
        ], order='date_from asc')

        for holiday in public_holidays:
            holidays.append({
                'date_from': holiday.date_from.strftime('%b %d, %Y'),
                'date_to': holiday.date_to.strftime('%b %d, %Y'),
                'name': holiday.name or 'Public Holiday',
                'type': 'public_holiday',
                'description': '',
            })

        # Mandatory Leave Days
        has_leave_module = 'hr.leave' in self.env
        if has_leave_module:
            LeaveType = self.env['hr.leave.type']
            mandatory_leave_types = LeaveType.search([('is_mandatory', '=', True)])

            if mandatory_leave_types:
                Leave = self.env['hr.leave']
                mandatory_leaves = Leave.search([
                    ('holiday_status_id', 'in', mandatory_leave_types.ids),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', end_date),
                    ('date_to', '>=', start_date),
                ], order='date_from asc')

                for leave in mandatory_leaves:
                    lt = leave.holiday_status_id
                    mandatory_days.append({
                        'date_from': leave.date_from.strftime('%b %d, %Y'),
                        'date_to': leave.date_to.strftime('%b %d, %Y'),
                        'name': lt.name,
                        'code': lt.leave_short_code or 'M',
                        'type': 'mandatory_day',
                        'description': leave.name or '',
                    })

        return {
            'public_holidays': holidays,
            'mandatory_days': mandatory_days,
        }

    def get_pdf_report_data(self):
        """Prepare all data needed for PDF report (QWeb template compatible)"""
        self.ensure_one()

        start_date, end_date, month_name, year_int, num_days = self._get_date_range()
        month_int = start_date.month

        # Get employees
        employees = self._resolve_employees()

        # Get attendance data (applies device filter if device_ids is set)
        attendance_data = self._get_attendance_data(employees, start_date, end_date)

        # Weekend days configuration
        ICP = self.env['ir.config_parameter'].sudo()
        _day_codes = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
        weekend_days = set()
        for _num, _code in _day_codes.items():
            if ICP.get_param(f'dotbd_hr_zk_attendance_suite.weekend_{_code}', 'False') in ('True', '1', 'true'):
                weekend_days.add(_num)
        # Only apply the Fri+Sat default when the user has never saved
        # settings. After saving, an empty set means "no weekends — 7-day
        # work week" and must be honoured.
        weekend_configured = ICP.get_param(
            'dotbd_hr_zk_attendance_suite.weekend_configured', 'False'
        ) in ('True', '1', 'true')
        if not weekend_days and not weekend_configured:
            weekend_days = {4, 5}

        # Prepare day information list
        from datetime import timedelta as _td3
        days_info = []
        for i in range(num_days):
            current_date = start_date + _td3(days=i)
            days_info.append({
                'day': i + 1,
                'date': current_date,
                'is_weekend': current_date.weekday() in weekend_days,
                'weekday': current_date.weekday(),
            })

        # Prepare employee data with attendance
        employees_data = []
        for employee in employees:
            emp_data = attendance_data.get(employee.id, {})

            # Build daily attendance list
            daily_attendance = []
            present_count = 0
            absent_count = 0
            late_count = 0
            total_work_hours = 0
            total_late_minutes = 0
            on_time_count = 0
            leave_count = 0
            leave_types_dict = {}  # Track leave types for PDF

            for day_info in days_info:
                current_date = day_info['date']
                is_weekend = day_info['is_weekend']
                day_data = emp_data.get(current_date, {})
                status = day_data.get('status', '')

                # Determine display status
                if status == 'present':
                    total_work_hours += day_data.get('worked_hours', 0)
                    present_count += 1
                    if day_data.get('is_late'):
                        display_status = 'LT'
                        css_class = 'late'
                        late_count += 1
                        total_late_minutes += day_data.get('late_minutes', 0)
                    else:
                        display_status = 'P'
                        css_class = 'present'
                        on_time_count += 1
                elif status == 'leave':
                    # Use leave code instead of 'V'
                    leave_code = day_data.get('leave_code', 'L')
                    leave_type = day_data.get('leave_type', 'Leave')
                    leave_type_id = day_data.get('leave_type_id', 0)
                    leave_category = day_data.get('leave_category', 'absence')
                    expected_hours = day_data.get('expected_hours', 8)

                    # Track this leave type
                    if leave_type_id not in leave_types_dict:
                        leave_types_dict[leave_type_id] = {
                            'name': leave_type,
                            'code': leave_code,
                            'category': leave_category,
                            'count': 0,
                            'hours': 0
                        }
                    leave_types_dict[leave_type_id]['count'] += 1
                    leave_types_dict[leave_type_id]['hours'] += expected_hours

                    display_status = leave_code
                    css_class = 'leave'
                    leave_count += 1
                elif status == 'mandatory_day':
                    display_status = 'M'
                    css_class = 'mandatory_day'
                elif status == 'public_holiday':
                    display_status = 'H'
                    css_class = 'public_holiday'
                elif status == 'weekend':
                    display_status = '-'
                    css_class = 'weekend'
                elif status == 'absent':
                    if not is_weekend:
                        display_status = 'A'
                        css_class = 'absent'
                        absent_count += 1
                    else:
                        display_status = '-'
                        css_class = 'weekend'
                else:
                    if is_weekend:
                        display_status = '-'
                        css_class = 'weekend'
                    else:
                        display_status = ''
                        css_class = ''

                daily_attendance.append({
                    'day': day_info['day'],
                    'date': current_date,
                    'date_str': current_date.strftime('%d/%m/%Y'),
                    'status': display_status,
                    'css_class': css_class,
                    'is_weekend': is_weekend,
                })

            # Calculate attendance rate: only days employee was expected (not on leave/holiday)
            effective_days = present_count + absent_count
            attendance_rate = (present_count / effective_days * 100) if effective_days > 0 else 100.0

            employees_data.append({
                'id': employee.id,
                'name': employee.name,
                'device_id_num': employee.device_id_num or employee.barcode or 'No ID',
                'department': employee.department_id.name if employee.department_id else '',
                'job_position': employee.job_id.name if employee.job_id else '',
                'daily_attendance': daily_attendance,
                'present_count': present_count,
                'absent_count': absent_count,
                'late_count': late_count,
                'total_work_hours': total_work_hours,
                'total_late_minutes': total_late_minutes,
                'on_time_count': on_time_count,
                'leave_count': leave_count,
                'leave_types': leave_types_dict,  # Leave types breakdown for PDF
                'attendance_rate': attendance_rate,
            })

        # Sort by attendance rate for ranking
        max_work_hours = max([emp['total_work_hours'] for emp in employees_data]) if employees_data else 1
        max_on_time = max([emp['on_time_count'] for emp in employees_data]) if employees_data else 1

        for emp_data in employees_data:
            # POSITIVE POINTS
            attendance_points = (emp_data['attendance_rate'] / 100) * 70
            on_time_points = (emp_data['on_time_count'] / max_on_time) * 15 if max_on_time > 0 else 0
            work_hours_points = (emp_data['total_work_hours'] / max_work_hours) * 15 if max_work_hours > 0 else 0

            # NEGATIVE POINTS
            absent_penalty = emp_data['absent_count'] * 3
            late_penalty = emp_data['late_count'] * 1
            late_minutes_penalty = emp_data['total_late_minutes'] * 0.1
            # Distinguish absence leave (-2/day) vs worked leave (+1 bonus/day)
            absence_leave_days = sum(lt['count'] for lt in emp_data.get('leave_types', {}).values() if lt.get('category') == 'absence')
            worked_leave_days = sum(lt['count'] for lt in emp_data.get('leave_types', {}).values() if lt.get('category') == 'worked')
            absence_leave_penalty = absence_leave_days * 2
            worked_leave_bonus = worked_leave_days * 1

            # Calculate total points
            total_points = (attendance_points + on_time_points + work_hours_points + worked_leave_bonus -
                            absent_penalty - late_penalty - late_minutes_penalty - absence_leave_penalty)

            emp_data['total_points'] = round(total_points, 2)

        # Sort by total points (highest first)
        sorted_employees = sorted(employees_data, key=lambda x: x['total_points'], reverse=True)
        for rank, emp_data in enumerate(sorted_employees, 1):
            emp_data['rank'] = rank

        # Collect all unique leave types from all employees for summary
        all_leave_types = {}
        for emp in employees_data:
            for leave_type_id, leave_data in emp.get('leave_types', {}).items():
                if leave_type_id not in all_leave_types:
                    all_leave_types[leave_type_id] = {
                        'name': leave_data['name'],
                        'code': leave_data['code'],
                        'total_days': 0,
                        'total_hours': 0
                    }
                all_leave_types[leave_type_id]['total_days'] += leave_data['count']
                all_leave_types[leave_type_id]['total_hours'] += leave_data['hours']

        # Sort leave types by code for consistent display
        leave_types_summary = sorted(all_leave_types.values(), key=lambda x: x['code'])

        # ── Get Holidays & Mandatory Days for PDF ─────────────────────
        holidays_mandatory_data = self._get_holidays_mandatory_for_pdf(start_date, end_date)

        return {
            'month_int': month_int,
            'year_int': year_int,
            'month_name': month_name,
            'num_days': num_days,
            'days_info': days_info,
            'employees_data': employees_data,
            'leave_types_summary': leave_types_summary,  # Overall leave types summary
            'holidays_mandatory': holidays_mandatory_data,  # Holidays & mandatory days
            'sheet_type': self.sheet_type,
            'total_employees': len(employees),
        }

    def _generate_pdf_report(self):
        """Generate PDF attendance sheet"""
        # This will call the QWeb PDF report
        return self.env.ref('dotbd_hr_zk_attendance_suite.action_report_employee_attendance_sheet').report_action(self)
