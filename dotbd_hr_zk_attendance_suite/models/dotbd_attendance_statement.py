# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
#    Attendance Statement Wizard
#    Generates per-employee attendance + salary statements.
#
#    Payroll source compatibility matrix:
#    ┌─────────────────────────┬────────────────────────────────────────────┐
#    │ Odoo Edition            │ Behaviour                                  │
#    ├─────────────────────────┼────────────────────────────────────────────┤
#    │ Enterprise 18 (hr_payroll) │ hr.contract · state done/paid           │
#    │ Enterprise 19 (hr_payroll) │ hr.version  · state validated/paid      │
#    │ Community 18 / 19       │ hr_payroll NOT available → our own system  │
#    └─────────────────────────┴────────────────────────────────────────────┘
#
#    Salary data source priority:
#      1. Confirmed hr.payslip lines for the period (most accurate)
#      2. Active contract/version + salary structure rules (fix/% only)
#      3. dotbd.employee.salary (our own system, when native payroll is off)
#
################################################################################
import calendar
import logging
from datetime import date, datetime, time

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Keyword sets for classifying salary rule components
# ─────────────────────────────────────────────────────────────────────────────
_HOUSING_KW  = {'HOUSE', 'HOUSING', 'ACCOMMODATION', 'RENT', 'LODGE', 'SHELTER'}
_TRANSPORT_KW = {'TRANS', 'TRANSPORT', 'TRAVEL', 'COMMUTE', 'FUEL', 'CAR', 'VEHICLE'}
_ADVANCE_KW  = {'ADVANCE', 'LOAN', 'ADV', 'RECOVERY', 'DEDUCT_ADV'}
_BONUS_KW    = {'BONUS', 'COMMISSION', 'INCENTIVE', 'REWARD', 'ALLOWANCE'}


def _kw_match(text, keywords):
    t = (text or '').upper()
    return any(k in t for k in keywords)


# ─────────────────────────────────────────────────────────────────────────────
# WIZARD
# ─────────────────────────────────────────────────────────────────────────────
class DotbdAttendanceStatementWizard(models.TransientModel):
    """Two-step wizard:
    Step 1 — select period + employee filter.
    Step 2 — editable table of employees with auto-filled salary & attendance data.
    """
    _name = 'dotbd.attendance.statement.wizard'
    _description = 'Attendance & Salary Statement Wizard'

    # ── Period ────────────────────────────────────────────────────────────────
    month = fields.Selection([
        ('1', 'January'),  ('2', 'February'), ('3', 'March'),
        ('4', 'April'),    ('5', 'May'),       ('6', 'June'),
        ('7', 'July'),     ('8', 'August'),    ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month', required=True,
        default=lambda self: str(
            (fields.Date.today().replace(day=1) - __import__('datetime').timedelta(days=1)).month
        ))
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: (
            fields.Date.today().replace(day=1) - __import__('datetime').timedelta(days=1)
        ).year)

    # ── Filter ────────────────────────────────────────────────────────────────
    employee_ids = fields.Many2many(
        'hr.employee', string='Employees',
        help='Leave empty to include all employees (or filter by department).')
    department_ids = fields.Many2many(
        'hr.department', string='Departments',
        help='Filter by department. Ignored when Employees field is filled.')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)

    # ── Payroll source ────────────────────────────────────────────────────────
    use_native_payroll = fields.Boolean(
        string='Use Native Odoo Payroll',
        default=lambda self: self._default_use_native(),
        help='When enabled, salary data (wage, allowances, deductions) is read '
             'from native Odoo payroll (hr.contract / hr.payslip). '
             'When disabled, data is read from our own salary assignment system.')

    native_payroll_available = fields.Boolean(
        string='Native Payroll Available',
        compute='_compute_native_payroll_available', store=False)

    @api.depends('use_native_payroll')
    def _compute_native_payroll_available(self):
        available = self._has_native_payroll()
        for rec in self:
            rec.native_payroll_available = available

    def _default_use_native(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'dotbd_hr_zk_attendance_suite.enable_native_payroll', 'True')
        return enabled == 'True' and self._has_native_payroll()

    # ── Wizard state ──────────────────────────────────────────────────────────
    state = fields.Selection([
        ('step1', 'Step 1 — Select Period'),
        ('step2', 'Step 2 — Review & Print'),
    ], default='step1', string='Step')

    line_ids = fields.One2many(
        'dotbd.attendance.statement.line', 'wizard_id', string='Employee Lines')

    employee_count = fields.Integer(
        string='Employee Count', compute='_compute_employee_count')

    @api.depends('line_ids')
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.line_ids)

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS — native payroll detection
    # ─────────────────────────────────────────────────────────────────────────

    def _has_native_payroll(self):
        """True if hr.payslip model is available (community or enterprise)."""
        return 'hr.payslip' in self.env

    def _has_hr_contract(self):
        return 'hr.contract' in self.env and hasattr(self.env['hr.contract'], 'wage')

    def _has_hr_version(self):
        return 'hr.version' in self.env and hasattr(self.env['hr.version'], 'wage')

    def _get_active_contract(self, employee):
        """Return the employee's active contract (v18 hr.contract or v19 hr.version)."""
        if self._has_hr_contract():
            return self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open'),
            ], limit=1)
        if self._has_hr_version():
            version = getattr(employee, 'version_id', False)
            if not version:
                version = self.env['hr.version'].search([
                    ('employee_id', '=', employee.id),
                    ('active', '=', True),
                ], limit=1, order='date_version desc')
            return version
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # DATE RANGE
    # ─────────────────────────────────────────────────────────────────────────

    def _get_date_range(self):
        m = int(self.month)
        y = self.year
        last = calendar.monthrange(y, m)[1]
        return date(y, m, 1), date(y, m, last)

    # ─────────────────────────────────────────────────────────────────────────
    # NATIVE PAYROLL SALARY DATA
    # ─────────────────────────────────────────────────────────────────────────

    def _get_native_salary(self, employee, date_from, date_to):
        """Return salary components from native Odoo payroll.

        Priority:
        1. Confirmed/paid hr.payslip for the period — read line totals directly.
        2. Active hr.contract (v18) / hr.version (v19) + salary structure rules.
        3. Returns zeroes if nothing is found.

        Compatibility:
        - Enterprise 18: hr.contract · state='done'/'paid' · contract_id on inputs
        - Enterprise 19: hr.version  · state='validated'/'paid' · version_id on inputs
        - Community 18/19: hr_payroll NOT available → falls back to our own system
        """
        result = {
            'wage': 0.0, 'housing': 0.0, 'transport': 0.0,
            'advance': 0.0, 'deductions': 0.0, 'bonus': 0.0,
            'source': 'none',
        }
        if not self._has_native_payroll():
            return result

        # Payslip terminal states differ between v18E ('done') and v19E ('validated')
        _DONE_STATES = ['done', 'validated', 'paid']

        # ── 1. Confirmed payslip ──────────────────────────────────────────────
        payslip = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', _DONE_STATES),
        ], limit=1)

        if payslip and payslip.line_ids:
            result['source'] = 'payslip'
            for line in payslip.line_ids.filtered(lambda l: l.total != 0):
                cat  = line.category_id.code if line.category_id else ''
                code = line.salary_rule_id.code or ''
                name = line.salary_rule_id.name or ''
                combo = code + ' ' + name

                if cat == 'BASIC':
                    result['wage'] += line.total
                elif cat == 'ALW':
                    if _kw_match(combo, _HOUSING_KW):
                        result['housing'] += line.total
                    elif _kw_match(combo, _TRANSPORT_KW):
                        result['transport'] += line.total
                    elif _kw_match(combo, _BONUS_KW):
                        result['bonus'] += line.total
                    else:
                        # Other allowances → bonus bucket
                        result['bonus'] += line.total
                elif cat == 'DED':
                    if _kw_match(combo, _ADVANCE_KW):
                        result['advance'] += abs(line.total)
                    else:
                        result['deductions'] += abs(line.total)
                # GROSS / NET / COMP categories are skipped intentionally
            return result

        # ── 2. Contract + salary structure rules ──────────────────────────────
        contract = self._get_active_contract(employee)
        if not contract:
            return result

        result['source'] = 'contract'
        result['wage'] = getattr(contract, 'wage', 0.0) or 0.0

        structure = getattr(contract, 'struct_id', False)
        if not structure:
            return result

        for rule in structure.rule_ids.filtered(lambda r: r.active and r.appears_on_payslip):
            cat  = rule.category_id.code if rule.category_id else ''
            code = rule.code or ''
            name = rule.name or ''
            combo = code + ' ' + name

            if cat == 'BASIC':
                continue  # already have wage from contract.wage

            # Compute rule amount.
            # amount_select values (same in v18E and v19E):
            #   'fix'        → fixed monetary amount (amount_fix)
            #   'percentage' → % of wage (amount_percentage / 100)
            #   'input'      → driven by hr.payslip.input — skip (no payslip context)
            #   'code'       → Python expression — skip (needs full payslip context)
            amount = 0.0
            if rule.amount_select == 'fix':
                amount = rule.amount_fix or 0.0
            elif rule.amount_select == 'percentage':
                amount = result['wage'] * ((rule.amount_percentage or 0.0) / 100.0)
            else:
                # 'input' or 'code' — cannot compute without running full payslip
                continue

            if cat == 'ALW':
                if _kw_match(combo, _HOUSING_KW):
                    result['housing'] += amount
                elif _kw_match(combo, _TRANSPORT_KW):
                    result['transport'] += amount
                elif _kw_match(combo, _BONUS_KW):
                    result['bonus'] += amount
                else:
                    result['bonus'] += amount
            elif cat == 'DED':
                if _kw_match(combo, _ADVANCE_KW):
                    result['advance'] += abs(amount)
                else:
                    result['deductions'] += abs(amount)

        # ── 2b. Payslip inputs (advance/loan entries on payslips in the period) ─
        # hr.payslip.input structure is the same in v18E and v19E:
        #   Fields: payslip_id, input_type_id, code, name, amount
        #   v18E: also has contract_id (safe to ignore via payslip_id path)
        #   v19E: also has version_id, employee_id, date_from (extra metadata)
        # We use payslip_id relational path which works on both versions.
        try:
            inputs = self.env['hr.payslip.input'].search([
                ('payslip_id.employee_id', '=', employee.id),
                ('payslip_id.date_from', '>=', date_from),
                ('payslip_id.date_to', '<=', date_to),
                ('payslip_id.state', 'in', _DONE_STATES),
            ])
            for inp in inputs:
                # Prefer input_type_id.code (v18E/v19E), fallback to direct code field
                type_code = ''
                if hasattr(inp, 'input_type_id') and inp.input_type_id:
                    type_code = inp.input_type_id.code or ''
                direct_code = getattr(inp, 'code', '') or ''
                inp_name = (inp.name or '').upper()
                txt = (type_code + ' ' + direct_code + ' ' + inp_name).upper()
                if any(k in txt for k in _ADVANCE_KW):
                    result['advance'] += abs(inp.amount or 0.0)
        except Exception as e:
            _logger.debug('Attendance statement: hr.payslip.input read failed: %s', e)

        return result

    def _get_our_salary(self, employee):
        """Fallback: read from dotbd.employee.salary (our own system)."""
        result = {
            'wage': 0.0, 'housing': 0.0, 'transport': 0.0,
            'advance': 0.0, 'deductions': 0.0, 'bonus': 0.0,
            'source': 'dotbd',
        }
        assignment = self.env['dotbd.employee.salary'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'active'),
        ], limit=1)
        if not assignment:
            return result
        result['wage'] = assignment.basic_wage or 0.0
        for comp in assignment.template_id.component_ids.filtered(lambda c: c.active):
            cat = (comp.component_type or '').upper()
            amt = comp.amount or 0.0
            if _kw_match(cat + ' ' + (comp.name or ''), _HOUSING_KW):
                result['housing'] += amt
            elif _kw_match(cat + ' ' + (comp.name or ''), _TRANSPORT_KW):
                result['transport'] += amt
            elif cat == 'DEDUCTION':
                result['deductions'] += abs(amt)
            elif cat in ('ALLOWANCE', 'BONUS'):
                result['bonus'] += amt
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # ATTENDANCE DATA
    # ─────────────────────────────────────────────────────────────────────────

    def _get_attendance_data(self, employee, date_from, date_to):
        """Return attendance summary for the given period."""
        tz_name = self.env.user.tz or 'UTC'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.UTC

        dt_from = tz.localize(datetime.combine(date_from, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        dt_to   = tz.localize(datetime.combine(date_to,   time.max)).astimezone(pytz.UTC).replace(tzinfo=None)

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in',    '>=', fields.Datetime.to_string(dt_from)),
            ('check_in',    '<=', fields.Datetime.to_string(dt_to)),
        ])

        worked_hours = sum(a.worked_hours for a in attendances if a.worked_hours)
        unique_days  = len({a.check_in.date() for a in attendances if a.check_in})

        # Overtime = hours beyond 8h/day × present days
        standard_hours = unique_days * 8.0
        overtime_hours = max(0.0, worked_hours - standard_hours)

        # Late minutes from our late check-in model (if installed)
        late_minutes = 0.0
        if 'late.check.in' in self.env:
            try:
                lates = self.env['late.check.in'].search([
                    ('employee_id', '=', employee.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                ])
                late_minutes = sum(getattr(l, 'late_minutes', 0) or 0 for l in lates)
            except Exception:
                pass

        return {
            'attendance_days': float(unique_days),
            'worked_hours': worked_hours,
            'overtime_hours': overtime_hours,
            'late_minutes': late_minutes,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1 → STEP 2: load employees + fill data
    # ─────────────────────────────────────────────────────────────────────────

    def action_load(self):
        """Load employees and auto-fill all financial & attendance data."""
        self.ensure_one()

        # Build employee list
        if self.employee_ids:
            employees = self.employee_ids
        elif self.department_ids:
            employees = self.env['hr.employee'].search([
                ('department_id', 'in', self.department_ids.ids),
                ('active', '=', True),
                ('company_id', '=', self.company_id.id),
            ])
        else:
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('company_id', '=', self.company_id.id),
            ])

        if not employees:
            raise UserError(_('No employees found for the selected filter.'))

        date_from, date_to = self._get_date_range()
        use_native = self.use_native_payroll and self._has_native_payroll()

        # Clear existing lines
        self.line_ids.unlink()

        currency = self.company_id.currency_id or self.env.company.currency_id
        lines = []

        for emp in employees:
            # Salary data
            if use_native:
                sal = self._get_native_salary(emp, date_from, date_to)
            else:
                sal = self._get_our_salary(emp)

            # Attendance data
            att = self._get_attendance_data(emp, date_from, date_to)

            lines.append({
                'wizard_id':     self.id,
                'employee_id':   emp.id,
                'currency_id':   currency.id,
                'salary_source': sal.get('source', 'none'),
                'wage':          sal['wage'],
                'housing':       sal['housing'],
                'transport':     sal['transport'],
                'advance':       sal['advance'],
                'deductions':    sal['deductions'],
                'bonus':         sal['bonus'],
                'attendance_days':  att['attendance_days'],
                'worked_hours':     att['worked_hours'],
                'overtime_hours':   att['overtime_hours'],
                'late_minutes':     att['late_minutes'],
            })

        self.env['dotbd.attendance.statement.line'].create(lines)
        self.state = 'step2'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_back(self):
        self.state = 'step1'
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_print_statements(self):
        """Generate PDF attendance + salary statement."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No employees loaded. Please click Load Employees first.'))
        return self.env.ref(
            'dotbd_hr_zk_attendance_suite.action_report_attendance_statement'
        ).report_action(self)

    def action_export_excel(self):
        """Export statement as Excel."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('No employees loaded.'))
        import io
        import base64
        import xlsxwriter

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Statement')

        # Styles
        bold = wb.add_format({'bold': True, 'bg_color': '#1c3a5e', 'font_color': '#ffffff', 'border': 1})
        normal = wb.add_format({'border': 1})
        money = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        total_fmt = wb.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00', 'bg_color': '#e8f5e9'})

        month_name = dict(self._fields['month'].selection).get(self.month, self.month)
        ws.set_column('A:A', 5)
        ws.set_column('B:B', 28)
        ws.set_column('C:C', 20)
        ws.set_column('D:P', 14)

        headers = [
            '#', 'Employee', 'Department',
            'Wage', 'Housing', 'Transport', 'Bonus',
            'Advance', 'Deductions',
            'Days', 'Hours', 'Overtime', 'Late (min)',
            'Gross', 'Net',
        ]
        for col, h in enumerate(headers):
            ws.write(0, col, h, bold)

        row = 1
        for i, line in enumerate(self.line_ids, 1):
            gross = line.wage + line.housing + line.transport + line.bonus
            net   = gross - line.advance - line.deductions
            data  = [
                i, line.employee_id.name,
                line.employee_id.department_id.name or '',
                line.wage, line.housing, line.transport, line.bonus,
                line.advance, line.deductions,
                line.attendance_days, line.worked_hours, line.overtime_hours, line.late_minutes,
                gross, net,
            ]
            for col, val in enumerate(data):
                fmt = money if col >= 3 else normal
                ws.write(row, col, val, fmt)
            row += 1

        # Totals row
        ws.write(row, 1, 'TOTAL', bold)
        for col in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
            ws.write_formula(row, col,
                f'=SUM({chr(65+col)}2:{chr(65+col)}{row})', total_fmt)

        wb.close()
        content = base64.b64encode(output.getvalue()).decode()
        filename = f'Attendance_Statement_{month_name}_{self.year}.xlsx'

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': content,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }


# ─────────────────────────────────────────────────────────────────────────────
# STATEMENT LINE
# ─────────────────────────────────────────────────────────────────────────────
class DotbdAttendanceStatementLine(models.TransientModel):
    """One row per employee in the attendance statement wizard."""
    _name = 'dotbd.attendance.statement.line'
    _description = 'Attendance Statement Line'
    _order = 'employee_id'

    wizard_id = fields.Many2one(
        'dotbd.attendance.statement.wizard', required=True, ondelete='cascade')

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id',
        string='Department', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency')

    salary_source = fields.Selection([
        ('payslip',  'From Confirmed Payslip'),
        ('contract', 'From Contract / Structure'),
        ('dotbd',    'From Our Salary System'),
        ('none',     'Not Found'),
    ], string='Data Source', readonly=True,
       help='Where the salary data was read from.')

    # ── Salary fields (auto-filled, fully editable) ───────────────────────────
    wage = fields.Monetary(string='Wage', currency_field='currency_id')
    housing = fields.Monetary(string='Housing', currency_field='currency_id')
    transport = fields.Monetary(string='Transport', currency_field='currency_id')
    bonus = fields.Monetary(string='Bonus / Other Allow.', currency_field='currency_id')
    advance = fields.Monetary(string='Advance Deduction', currency_field='currency_id')
    deductions = fields.Monetary(string='Deductions', currency_field='currency_id')

    # ── Computed ──────────────────────────────────────────────────────────────
    gross_amount = fields.Monetary(
        string='Gross', compute='_compute_totals', store=True,
        currency_field='currency_id')
    net_amount = fields.Monetary(
        string='Net', compute='_compute_totals', store=True,
        currency_field='currency_id')

    @api.depends('wage', 'housing', 'transport', 'bonus', 'advance', 'deductions')
    def _compute_totals(self):
        for rec in self:
            rec.gross_amount = rec.wage + rec.housing + rec.transport + rec.bonus
            rec.net_amount   = rec.gross_amount - rec.advance - rec.deductions

    # ── Attendance fields (auto-filled, editable) ─────────────────────────────
    attendance_days = fields.Float(string='Days Present', digits=(10, 1))
    worked_hours    = fields.Float(string='Hours Worked', digits=(10, 2))
    overtime_hours  = fields.Float(string='Overtime Hrs', digits=(10, 2))
    late_minutes    = fields.Float(string='Late (min)',   digits=(10, 0))
