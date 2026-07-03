# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
import base64
import calendar
import logging
import pytz
from collections import defaultdict
from datetime import datetime, date, timedelta

from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError

try:
    # Odoo's built-in PDF merge utility (pypdf-based)
    from odoo.tools.pdf import merge_pdf
except Exception:  # pragma: no cover
    merge_pdf = None

_logger = logging.getLogger(__name__)


# ── Keyword sets for salary-component classification ─────────────────────────
# Used for BOTH our own dotbd payroll system AND native Odoo payroll (hr_payroll)
TRANSPORT_KW = frozenset([
    'transport', 'travel', 'conveyance', 'commute', 'مواصلات', 'تنقل', 'trn', 'ta',
])
HOUSING_KW = frozenset([
    'housing', 'house', 'accommodation', 'rent', 'سكن', 'إيجار', 'hra', 'hr',
])
ADVANCE_KW = frozenset([
    'advance', 'loan', 'ساحب', 'سلفة',
])
BONUS_KW = frozenset([
    'bonus', 'incentive', 'يونيس', 'حافز', 'مكافأة', 'bnc', 'bonc',
])

# ── Additional keyword sets for native Odoo payroll classification ────────────
# Matching is case-insensitive; checked against (rule_code + ' ' + rule_name)
_NATIVE_HOUSING_KW  = {'HOUSE', 'HOUSING', 'ACCOMMODATION', 'RENT', 'LODGE', 'SHELTER'}
_NATIVE_TRANSPORT_KW = {'TRANS', 'TRANSPORT', 'TRAVEL', 'COMMUTE', 'FUEL', 'CAR', 'VEHICLE'}
_NATIVE_ADVANCE_KW  = {'ADVANCE', 'LOAN', 'ADV', 'RECOVERY', 'DEDUCT_ADV'}
_NATIVE_BONUS_KW    = {'BONUS', 'COMMISSION', 'INCENTIVE', 'REWARD', 'ALLOWANCE'}


def _native_kw_match(text, keywords):
    """Case-insensitive keyword match for native payroll rule classification."""
    t = (text or '').upper()
    return any(k in t for k in keywords)

# Levantine/Lebanese calendar month names (Lebanon, Syria, Palestine, Jordan)
LEVANTINE_MONTHS = {
    1: 'كانون الثاني',
    2: 'شباط',
    3: 'آذار',
    4: 'نيسان',
    5: 'أيار',
    6: 'حزيران',
    7: 'تموز',
    8: 'آب',
    9: 'أيلول',
    10: 'تشرين الأول',
    11: 'تشرين الثاني',
    12: 'كانون الأول',
}


class DotbdMonthlyStatementRuleLine(models.TransientModel):
    """One row per salary rule per employee.

    When native Odoo payroll is ON, these records mirror the salary computation
    tab of the hr.payslip — showing every rule name, code, category and amount.
    This gives HR a full breakdown per employee without needing dynamic columns.

    Developer note — to add a custom column:
      1. This model already captures every payslip line automatically.
      2. To show a specific rule in the main editable list (Step 2), add its
         keyword to the classification sets (_NATIVE_HOUSING_KW etc.) in the
         parent wizard so it maps into the editable Wage / Housing / Transport /
         Advance / Deductions fields.
      3. Client-specific extra columns can be added as Float fields on
         DotbdMonthlyStatementLine and populated in _build_lines_for().
    """
    _name = 'dotbd.monthly.statement.rule.line'
    _description = 'Monthly Statement — Payslip Rule Line'
    _order = 'sequence, id'

    statement_line_id = fields.Many2one(
        'dotbd.monthly.statement.line',
        required=True, ondelete='cascade', string='Employee Line')
    sequence = fields.Integer(default=10)
    employee_id = fields.Many2one(
        'hr.employee', related='statement_line_id.employee_id',
        store=True, string='Employee')

    rule_name = fields.Char(string='Rule')
    rule_code = fields.Char(string='Code')
    category_name = fields.Char(string='Category')
    category_code = fields.Char(string='Cat. Code')
    amount = fields.Float(string='Amount', digits=(16, 2))
    total = fields.Float(string='Total', digits=(16, 2))


class DotbdMonthlyStatementLine(models.TransientModel):
    """One row per employee — holds that employee's financial details for the statement."""
    _name = 'dotbd.monthly.statement.line'
    _description = 'Monthly Statement — Per-Employee Financial Line'
    _order = 'sequence, employee_id'

    wizard_id = fields.Many2one(
        'dotbd.monthly.statement', string='Wizard',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True)
    department = fields.Char(
        string='Department',
        compute='_compute_department', store=True)

    # Linked payslip (set by action_reload_from_payroll)
    payslip_id = fields.Many2one(
        'dotbd.payslip', string='Linked Payslip',
        ondelete='set null')

    # Linked native hr.payslip (set when native payroll is used)
    native_payslip_id = fields.Many2one(
        'hr.payslip', string='Native Payslip',
        ondelete='set null')

    # Wage / basic salary — editable; auto-filled from active salary assignment
    wage = fields.Float(
        string='Wage (الراتب)',
        digits=(16, 2),
        help='Basic wage / salary for this month. Auto-filled from active salary '
             'assignment if available. Never printed as "gross salary".')

    # Financial fields — entered manually by HR or filled from payroll
    advance_amount = fields.Float(
        string='Advance (ساحب)',
        help='Cash advance / money taken before salary')
    deduction_amount = fields.Float(
        string='Deductions (خصومات)',
        help='Fines or general deductions')
    housing_deduction = fields.Float(
        string='Housing (سكن)',
        help='Housing-related deduction')
    transport_allowance = fields.Float(
        string='Transport (مواصلات)',
        help='Transport allowance (positive = added)')
    bonus_amount = fields.Float(
        string='Bonus (يونيس)',
        help='Extra bonus / incentive (positive = added)')

    # Payslip state (populated from hr.payslip when native payroll is ON)
    payslip_state = fields.Selection([
        ('done',      'Done'),
        ('paid',      'Paid'),
        ('waiting',   'Waiting / Verify'),
        ('draft',     'Draft'),
        ('none',      'No Payslip'),
    ], string='Payslip State', default='none', readonly=True)

    payslip_state_label = fields.Char(
        string='State', compute='_compute_payslip_state_label', store=False)

    @api.depends('payslip_state')
    def _compute_payslip_state_label(self):
        labels = {
            'done': '✓ Done',
            'paid': '✓ Paid',
            'waiting': '⏳ Waiting',
            'draft': '📝 Draft',
            'none': '✗ No Payslip',
        }
        for rec in self:
            rec.payslip_state_label = labels.get(rec.payslip_state, '')

    # Full payslip rule lines (populated when native payroll is ON)
    rule_line_ids = fields.One2many(
        'dotbd.monthly.statement.rule.line', 'statement_line_id',
        string='Payslip Computation Details')

    has_rule_lines = fields.Boolean(
        compute='_compute_has_rule_lines', store=True)

    @api.depends('rule_line_ids')
    def _compute_has_rule_lines(self):
        for rec in self:
            rec.has_rule_lines = bool(rec.rule_line_ids)

    @api.depends('employee_id')
    def _compute_department(self):
        for line in self:
            line.department = (line.employee_id.department_id.name
                               if line.employee_id.department_id else '')

    def web_read(self, specification):
        # Strip native_payslip_id from the web client's field specification
        # BEFORE Odoo processes Many2one display_name resolution.
        # web_read accesses record[field] directly (not via read()), which
        # triggers ORM comodel resolution → _unknown crash.
        specification = {k: v for k, v in specification.items()
                         if k != 'native_payslip_id'}
        return super(DotbdMonthlyStatementLine, self).web_read(specification)

    def read(self, fields=None, load='_classic_read'):
        # ALWAYS strip native_payslip_id from ORM reads.
        # This Many2one's comodel (hr.payslip) can resolve to the _unknown
        # pseudo-model even when hr_payroll IS installed (partial registry
        # reload on odoo.sh workers).  We never display this field in views;
        # when we need the FK value we use _safe_native_payslip_ids() which
        # reads the column via raw SQL, completely bypassing the ORM.
        if fields is None:
            fields = [f for f in self._fields if f != 'native_payslip_id']
        else:
            fields = [f for f in fields if f != 'native_payslip_id']
        res = super(DotbdMonthlyStatementLine, self).read(fields=fields, load=load)
        for r in res:
            r['native_payslip_id'] = False
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # Strip native_payslip_id from ORM create — we write it via
        # direct SQL or let the write() override handle it safely.
        for vals in vals_list:
            vals.pop('native_payslip_id', None)
        return super(DotbdMonthlyStatementLine, self).create(vals_list)

    def write(self, vals):
        # Strip native_payslip_id from ORM write — we handle it via SQL.
        vals.pop('native_payslip_id', None)
        return super(DotbdMonthlyStatementLine, self).write(vals)

    def _set_native_payslip_id_sql(self, payslip_id):
        """Write native_payslip_id directly via SQL, bypassing ORM.

        The ORM's Many2one comodel resolution for hr.payslip can resolve to
        _unknown on odoo.sh, so we must never let the ORM touch this column.
        """
        if self and payslip_id:
            self.env.cr.execute(
                "UPDATE dotbd_monthly_statement_line "
                "SET native_payslip_id = %s WHERE id IN %s",
                [payslip_id, tuple(self.ids)]
            )
            self.invalidate_recordset(['native_payslip_id'])


class DotbdMonthlyStatement(models.TransientModel):
    """Monthly Employee Attendance & Deductions Statement.

    Admin selects month/year and one or more employees (empty = all).
    A line per employee is auto-created in employee_line_ids where HR can
    enter advance, deductions and allowances.
    Printing generates one page per employee — ordered as the lines appear.

    Summary box values (matching client reference image):
      243   = عدد الساعات المطلوبة  → auto from work schedule
      249.7 = عدد الساعات الفعلي   → auto from hr.attendance records
      200   = ساحب (advance)       → manually entered per employee
    """
    _name = 'dotbd.monthly.statement'
    _description = 'Monthly Employee Statement (Attendance + Financials)'

    # ─── Period ──────────────────────────────────────────────────────────────
    month = fields.Selection([
        ('1', 'January'),   ('2', 'February'),  ('3', 'March'),
        ('4', 'April'),     ('5', 'May'),        ('6', 'June'),
        ('7', 'July'),      ('8', 'August'),     ('9', 'September'),
        ('10', 'October'),  ('11', 'November'),  ('12', 'December'),
    ], string='Month',
        default=lambda self: str(fields.Date.today().month))

    year = fields.Integer(
        string='Year',
        default=lambda self: fields.Date.today().year)

    # Optional custom date range — overrides Month / Year when both are set
    date_from = fields.Date(
        string='From Date',
        help='Custom start date. When filled together with "To Date", '
             'overrides the Month / Year selection.')
    date_to = fields.Date(
        string='To Date',
        help='Custom end date.')

    # ─── Employee selection ──────────────────────────────────────────────────
    employee_ids = fields.Many2many(
        'hr.employee', string='Employees',
        help='Select employees to print. Leave empty and click "Load All Employees" '
             'to include every active employee.')

    employee_line_ids = fields.One2many(
        'dotbd.monthly.statement.line', 'wizard_id',
        string='Employee Lines')

    print_in_arabic = fields.Boolean(
        string='Print in Arabic (طباعة بالعربية)',
        default=False,
        help='If checked, all table headers and labels will be printed in Arabic. '
             'The summary box is always in Arabic.')

    # Flat view of ALL payslip rule lines across all employee lines.
    # Used by the "Payslip Computation Details" table in Step 2.
    # Shows the same rows as the Salary Computation tab on each hr.payslip,
    # with Employee name added so HR can see all employees' breakdowns at once.
    all_rule_line_ids = fields.Many2many(
        'dotbd.monthly.statement.rule.line',
        'dotbd_monthly_stmt_all_rule_rel', 'wizard_id', 'rule_line_id',
        string='All Payslip Rule Lines',
        compute='_compute_all_rule_line_ids', store=False)

    @api.depends('employee_line_ids', 'employee_line_ids.rule_line_ids')
    def _compute_all_rule_line_ids(self):
        for rec in self:
            rec.all_rule_line_ids = rec.employee_line_ids.mapped('rule_line_ids')

    # ─── Payroll integration ─────────────────────────────────────────────────
    auto_fill_from_wage = fields.Boolean(
        string='Calculate from Employee Wage Automatically',
        default=False,
        help='When loading employees, auto-fill Transport, Housing, Bonus, '
             'and Deduction amounts from the active salary template components.')

    auto_create_payslip = fields.Boolean(
        string='Create Payslip Automatically',
        default=False,
        help='When enabled, a "Reload Financial Details by Payroll" button '
             'appears. Clicking it finds or generates dotbd.payslip records '
             'for the period and fills all financial fields from payslip lines.')

    include_payslip_in_print = fields.Boolean(
        string='Include Payslip in Print',
        default=False,
        help='If checked, the payslip page is appended after each employee\'s '
             'attendance statement page in the PDF.')

    # ─── PDF generation ──────────────────────────────────────────────────────
    pdf_batch_size = fields.Integer(
        string='Employees per PDF Batch',
        default=20,
        help='To avoid wkhtmltopdf crashing on large runs, the statement PDF is '
             'rendered in batches of this many employees and then merged into one '
             'file. 0 or empty = render everyone in a single pass (not recommended '
             'above ~30 employees). Recommended: 20.')

    # ─── PDF Print Filters ───────────────────────────────────────────────────
    pdf_include_mode = fields.Selection([
        ('all',          'All loaded employees (with or without payslip)'),
        ('payslip_only', 'Only employees with a payslip'),
    ], string='Include in PDF',
        default='payslip_only',
        help='Controls which employees appear in the printed PDF statement.')

    pdf_filter_done    = fields.Boolean(string='Done', default=True,
        help='Include employees whose payslip is in Done state.')
    pdf_filter_paid    = fields.Boolean(string='Paid', default=True,
        help='Include employees whose payslip is in Paid state.')
    pdf_filter_waiting = fields.Boolean(string='Waiting / Verify', default=False,
        help='Include employees whose payslip is in Waiting/Verify state.')
    pdf_filter_draft   = fields.Boolean(string='Draft', default=False,
        help='Include employees whose payslip is still in Draft state.')

    # ─────────────────────────────────────────────────────────────────────────
    check_payslip_status = fields.Boolean(
        string='Check Payslip Status After Loading',
        default=False,
        help='When enabled, after clicking Load Employees a notification shows '
             'how many employees have confirmed payslips (Done), how many are '
             'still in Draft/Waiting, and how many have no payslip for the period. '
             'Useful to verify payroll is complete before printing statements.')

    # ─── Native Odoo Payroll (hr_payroll enterprise) ─────────────────────────
    use_native_payroll = fields.Boolean(
        string='Use Odoo Native Payroll',
        default=lambda self: self._default_use_native(),
        help='When enabled, wage and salary components are auto-filled from '
             'native Odoo payroll (hr.payslip confirmed lines → hr.contract/'
             'hr.version structure rules). '
             'Works with both Odoo 18 (hr.contract) and 19 (hr.version).')
    native_payroll_available = fields.Boolean(
        string='Native Payroll Installed',
        compute='_compute_native_payroll_available', store=False)

    @api.depends('use_native_payroll')
    def _compute_native_payroll_available(self):
        available = self._has_native_payroll()
        for rec in self:
            rec.native_payroll_available = available

    def _default_use_native(self):
        return self._has_native_payroll()

    def _has_native_payroll(self):
        """True if native Odoo payroll (hr_payroll) is installed."""
        return 'hr.payslip' in self.env

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if not (rec.date_from and rec.date_to) and rec.year:
                if rec.year < 2000 or rec.year > 2100:
                    raise ValidationError(
                        _('Please enter a valid year between 2000 and 2100.'))

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_('From Date cannot be after To Date.'))

    def _get_period_dates(self):
        """Return (start_date, end_date, num_days, month_int, year, period_label).

        If date_from + date_to are both set, use them as a custom date range.
        Otherwise fall back to month + year selection.
        """
        if self.date_from and self.date_to:
            start = self.date_from
            end = self.date_to
            num_days = (end - start).days + 1
            month_int = start.month
            year = start.year
            label = '{} — {}'.format(
                start.strftime('%d %b %Y'), end.strftime('%d %b %Y'))
        else:
            if not self.month or not self.year:
                raise ValidationError(
                    _('Please select a Month and Year, or provide a custom From / To date range.'))
            month_int = int(self.month)
            year = self.year
            num_days = calendar.monthrange(year, month_int)[1]
            start = date(year, month_int, 1)
            end = date(year, month_int, num_days)
            month_names = dict(self._fields['month'].selection)
            label = '{} {}'.format(month_names.get(self.month, ''), year)
        return start, end, num_days, month_int, year, label

    # ─── Helpers ─────────────────────────────────────────────────────────────

    # ─── Our own payroll helpers (dotbd.payslip) ─────────────────────────────

    def _classify_component(self, code, name, comp_type):
        """Return the financial field to map this component onto, or None.

        Checks transport → housing → advance → bonus keywords; falls back to
        'deduction_amount' for any deduction-type component.
        """
        text = (code + ' ' + name).lower()
        if any(kw in text for kw in TRANSPORT_KW):
            return 'transport_allowance'
        if any(kw in text for kw in HOUSING_KW):
            return 'housing_deduction'
        if any(kw in text for kw in ADVANCE_KW):
            return 'advance_amount'
        if any(kw in text for kw in BONUS_KW):
            return 'bonus_amount'
        if comp_type in ('deduction',):
            return 'deduction_amount'
        return None

    # ─── Native Odoo Payroll helpers (hr.payslip) ────────────────────────────
    # Compatibility:
    #   Odoo 18 Enterprise: hr.contract · state='done'/'paid'
    #   Odoo 19 Enterprise: hr.version  · state='validated'/'paid'
    #   Community (no hr_payroll): falls back to our own system

    def _get_native_salary(self, employee, date_from, date_to):
        """Read salary data from native Odoo payroll (hr_payroll enterprise).

        Priority:
        1. Confirmed/paid/draft hr.payslip lines for the period (most accurate)
        2. Active hr.contract (v18) or hr.version (v19) + salary structure rules
        3. Returns zeroes if nothing found

        Returns dict with keys: wage, transport_allowance, housing_deduction,
        advance_amount, bonus_amount, deduction_amount, source.
        """
        result = {
            'wage': 0.0,
            'transport_allowance': 0.0,
            'housing_deduction': 0.0,
            'advance_amount': 0.0,
            'bonus_amount': 0.0,
            'deduction_amount': 0.0,
            'source': 'none',
            'payslip_state': 'none',
        }
        if not self._has_native_payroll():
            return result

        # Arabic support: if print_in_arabic is ON and ar_001 language is installed,
        # try to get Arabic rule/category names from native payroll translations.
        _use_arabic = getattr(self, 'print_in_arabic', False)
        _ar_env = self.env.with_context(lang='ar_001') if _use_arabic else self.env

        # ── 1. Find any payslip for the period, prioritizing active/confirmed states ──────────────
        payslips = self.env['hr.payslip'].search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['paid', 'done', 'validated', 'verify', 'draft']),
        ])
        
        payslip = False
        if payslips:
            state_priority = {'paid': 0, 'done': 0, 'validated': 0, 'verify': 1, 'draft': 2}
            payslip = sorted(payslips, key=lambda p: state_priority.get(p.state, 99))[0]

        if payslip:
            result['native_payslip_id'] = payslip.id
            if payslip.state == 'paid':
                result['payslip_state'] = 'paid'
            elif payslip.state in ('done', 'validated'):
                result['payslip_state'] = 'done'
            elif payslip.state == 'verify':
                result['payslip_state'] = 'waiting'
            elif payslip.state == 'draft':
                result['payslip_state'] = 'draft'

            if payslip.line_ids:
                result['source'] = 'payslip'
                rule_lines = []
                seq = 10
                for line in payslip.line_ids.filtered(lambda l: l.appears_on_payslip if hasattr(l, 'appears_on_payslip') else True):
                    cat  = line.category_id.code if line.category_id else ''
                    code = line.salary_rule_id.code or ''
                    # Try Arabic name if Arabic printing is enabled
                    try:
                        name = _ar_env['hr.salary.rule'].browse(line.salary_rule_id.id).name or line.salary_rule_id.name or ''
                        cat_name = _ar_env['hr.salary.rule.category'].browse(line.category_id.id).name if line.category_id else ''
                    except Exception:
                        name = line.salary_rule_id.name or ''
                        cat_name = line.category_id.name if line.category_id else ''
                    combo = code + ' ' + (line.salary_rule_id.name or '')  # Always English for keyword matching

                    # Collect rule line for the payslip breakdown display
                    rule_lines.append({
                        'sequence': seq,
                        'rule_name': name,
                        'rule_code': code,
                        'category_name': cat_name,
                        'category_code': cat,
                        'amount': line.amount if hasattr(line, 'amount') else 0.0,
                        'total': line.total,
                    })
                    seq += 10

                    # Map into summary financial fields
                    if cat == 'BASIC':
                        result['wage'] += line.total
                    elif cat == 'ALW':
                        if _native_kw_match(combo, _NATIVE_HOUSING_KW):
                            result['housing_deduction'] += line.total
                        elif _native_kw_match(combo, _NATIVE_TRANSPORT_KW):
                            result['transport_allowance'] += line.total
                        elif _native_kw_match(combo, _NATIVE_BONUS_KW):
                            result['bonus_amount'] += line.total
                        else:
                            result['bonus_amount'] += line.total
                    elif cat == 'DED':
                        if _native_kw_match(combo, _NATIVE_ADVANCE_KW):
                            result['advance_amount'] += abs(line.total)
                        else:
                            result['deduction_amount'] += abs(line.total)
                    # GROSS / NET / COMP categories added to rule_lines but not to summary

                result['rule_lines'] = rule_lines
                return result

        # ── 2. Contract/Version + salary structure rules ─────────────────────
        # v18: hr.contract (open/close, date-aware), struct_id on contract
        # v19: hr.version, struct_id on version
        contract = self._get_active_contract_or_version(employee, date_from, date_to)
        if not contract:
            return result

        result['source'] = 'contract'
        result['wage'] = getattr(contract, 'wage', 0.0) or 0.0

        structure = getattr(contract, 'struct_id', False)
        if not structure:
            return result

        for rule in structure.rule_ids.filtered(
                lambda r: r.active and r.appears_on_payslip):
            cat  = rule.category_id.code if rule.category_id else ''
            code = rule.code or ''
            name = rule.name or ''
            combo = code + ' ' + name

            if cat == 'BASIC':
                continue  # already have wage from contract

            # Compute rule amount — only fixed and percentage types
            amount = 0.0
            if rule.amount_select == 'fix':
                amount = rule.amount_fix or 0.0
            elif rule.amount_select == 'percentage':
                amount = result['wage'] * (
                    (rule.amount_percentage or 0.0) / 100.0)
            else:
                # 'input' / 'code' — cannot compute without payslip context
                continue

            if cat == 'ALW':
                if _native_kw_match(combo, _NATIVE_HOUSING_KW):
                    result['housing_deduction'] += amount
                elif _native_kw_match(combo, _NATIVE_TRANSPORT_KW):
                    result['transport_allowance'] += amount
                elif _native_kw_match(combo, _NATIVE_BONUS_KW):
                    result['bonus_amount'] += amount
                else:
                    result['bonus_amount'] += amount
            elif cat == 'DED':
                if _native_kw_match(combo, _NATIVE_ADVANCE_KW):
                    result['advance_amount'] += abs(amount)
                else:
                    result['deduction_amount'] += abs(amount)

        return result

    def _get_active_contract_or_version(self, employee, date_from=None, date_to=None):
        """Return the employee's contract (v18) or version (v19) for the period.

        Matches Odoo's native batch payslip wizard logic:
          - Uses employee._get_contracts(date_from, date_to, states=['open','close'])
            which is DATE-RANGE aware and accepts both running ('open') AND
            expired ('close') contracts — exactly what the native
            "Generate Payslips" batch does.
          - Falls back to a plain open/close search when the native method
            is unavailable or no period dates are given.

        Previously we searched only state='open' with NO date filter, which
        skipped employees whose contract was 'close' or out of range.
        """
        # Resolve period if not provided
        if date_from is None or date_to is None:
            try:
                date_from, date_to, _n, _m, _y, _l = self._get_period_dates()
            except Exception:
                date_from = date_to = None

        # ── v18: hr.contract ──────────────────────────────────────────────────
        if 'hr.contract' in self.env and hasattr(self.env['hr.contract'], 'wage'):
            # Preferred: native period-aware finder (open + close, date range)
            if date_from and date_to and hasattr(employee, '_get_contracts'):
                try:
                    contracts = employee._get_contracts(
                        date_from, date_to, states=['open', 'close'])
                    if contracts:
                        # Prefer a running (open) contract if several match
                        running = contracts.filtered(lambda c: c.state == 'open')
                        return (running[:1] or contracts[:1])
                except Exception as e:
                    _logger.debug("native _get_contracts failed for %s: %s",
                                  employee.name, e)
            # Fallback: open or close, no date filter
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', 'in', ['open', 'close']),
            ], order="state desc, date_start desc", limit=1)
            if contract:
                return contract

        # ── v19: hr.version ───────────────────────────────────────────────────
        if 'hr.version' in self.env:
            version = getattr(employee, 'current_version_id', False)
            if not version:
                try:
                    version = self.env['hr.version'].search([
                        ('employee_id', '=', employee.id),
                        ('active', '=', True),
                    ], limit=1, order='date_version desc')
                except Exception:
                    pass
            if version:
                return version
        return False

    def _fill_line_from_salary_template(self, line, working_days):
        """Auto-fill financial fields on line from the employee's active salary template."""
        salary = self.env['dotbd.employee.salary'].search([
            ('employee_id', '=', line.employee_id.id),
            ('state', '=', 'active'),
        ], limit=1)
        if not salary or not salary.template_id:
            return
        transport = housing = advance = bonus = deduction = 0.0
        for comp in salary.template_id.component_ids.filtered('active'):
            field = self._classify_component(
                comp.code or '', comp.name or '', comp.component_type)
            if field is None:
                continue
            amount = comp.get_amount(salary.basic_wage, working_days)
            if field == 'transport_allowance':
                transport += amount
            elif field == 'housing_deduction':
                housing += amount
            elif field == 'advance_amount':
                advance += amount
            elif field == 'bonus_amount':
                bonus += amount
            elif field == 'deduction_amount':
                deduction += amount
        vals = {'wage': salary.basic_wage}
        if transport:   vals['transport_allowance'] = transport
        if housing:     vals['housing_deduction'] = housing
        if advance:     vals['advance_amount'] = advance
        if bonus:       vals['bonus_amount'] = bonus
        if deduction:   vals['deduction_amount'] = deduction
        if vals:
            line.write(vals)

    def _fill_line_from_payslip(self, line, payslip):
        """Fill financial fields on line from a dotbd.payslip's lines."""
        transport = housing = advance = bonus = deduction = 0.0
        for pl in payslip.line_ids:
            field = self._classify_component(
                pl.code or '', pl.name or '', pl.line_type)
            if field is None:
                continue
            amount = abs(pl.amount)
            if field == 'transport_allowance':
                transport += amount
            elif field == 'housing_deduction':
                housing += amount
            elif field == 'advance_amount':
                advance += amount
            elif field == 'bonus_amount':
                bonus += amount
            elif field == 'deduction_amount':
                deduction += amount
        vals = {
            'transport_allowance': transport,
            'housing_deduction': housing,
            'advance_amount': advance,
            'bonus_amount': bonus,
            'deduction_amount': deduction,
        }
        if payslip.basic_wage:
            vals['wage'] = payslip.basic_wage
        line.write(vals)

    def action_reload_from_payroll(self):
        """Find or create payslips for all loaded employees, then fill financial fields."""
        self.ensure_one()
        if not self.employee_line_ids:
            raise ValidationError(
                _('No employees loaded. Please click "Load Selected" or '
                  '"Load All Employees" first.'))

        date_from, date_to, _num, _mi, _yr, _lbl = self._get_period_dates()

        DotbdPayslip = self.env['dotbd.payslip']
        skipped = []

        for line in self.employee_line_ids:
            # Look for existing payslip (any state) for this employee + period
            payslip = DotbdPayslip.search([
                ('employee_id', '=', line.employee_id.id),
                ('date_from', '=', date_from),
            ], limit=1)

            if not payslip:
                # Try to generate
                payslip = DotbdPayslip.generate_for_employee(
                    line.employee_id, date_from, date_to)

            if payslip:
                line.payslip_id = payslip.id
                self._fill_line_from_payslip(line, payslip)
            else:
                skipped.append(line.employee_id.name)

        result = {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }
        if skipped:
            # Show warning then reopen wizard
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Salary Setup'),
                    'message': _(
                        'Payslip could not be generated for: %s\n'
                        '(No active salary assignment found.)'
                    ) % ', '.join(skipped),
                    'sticky': True,
                    'type': 'warning',
                    'next': result,
                },
            }
        return result

    def _build_lines_for(self, employees):
        """(Re)build employee_line_ids for the given employee recordset."""
        self.ensure_one()
        # Keep existing lines that are still in the selection (preserve edits)
        existing = {line.employee_id.id: line for line in self.employee_line_ids}
        new_lines = []
        seq = 10
        for emp in employees:
            if emp.id in existing:
                existing[emp.id].sequence = seq
            else:
                # Pre-fill wage from active salary assignment (always — it's not sensitive)
                salary = self.env['dotbd.employee.salary'].search([
                    ('employee_id', '=', emp.id),
                    ('state', '=', 'active'),
                ], limit=1)
                new_lines.append((0, 0, {
                    'employee_id': emp.id,
                    'sequence': seq,
                    'wage': salary.basic_wage if salary else 0.0,
                }))
            seq += 10
        # Remove lines for employees no longer selected
        remove_cmds = [(2, line.id) for emp_id, line in existing.items()
                       if emp_id not in employees.ids]
        self.write({'employee_line_ids': remove_cmds + new_lines})

        # Auto-fill salary data.
        # Trigger conditions:
        #   - native payroll ON  → always auto-fill from hr.payslip/hr.contract
        #   - native payroll OFF → auto-fill from our own templates if auto_fill_from_wage
        _do_native = self.use_native_payroll and self._has_native_payroll()
        _do_own    = self.auto_fill_from_wage and not _do_native
        if _do_native or _do_own:
            if _do_native:
                # ── Use native Odoo payroll (hr.payslip / hr.contract) ────────
                date_from, date_to, _nd, _mi, _yr, _lbl = self._get_period_dates()
                for line in self.employee_line_ids:
                    native = self._get_native_salary(
                        line.employee_id, date_from, date_to)
                    if native['source'] != 'none':
                        vals = {
                            'wage': native['wage'],
                            'transport_allowance': native['transport_allowance'],
                            'housing_deduction': native['housing_deduction'],
                            'advance_amount': native['advance_amount'],
                            'bonus_amount': native['bonus_amount'],
                            'deduction_amount': native['deduction_amount'],
                        }
                        # Store payslip state on the line for filter/display
                        vals['payslip_state'] = native.get('payslip_state', 'none')
                        line.write(vals)
                        # Write native_payslip_id via SQL (ORM strips it)
                        if native.get('native_payslip_id'):
                            line._set_native_payslip_id_sql(native['native_payslip_id'])
                        # Write individual rule lines for payslip computation display
                        if native.get('rule_lines'):
                            line.rule_line_ids.unlink()
                            for rl in native['rule_lines']:
                                rl['statement_line_id'] = line.id
                            self.env['dotbd.monthly.statement.rule.line'].create(
                                native['rule_lines'])
            else:
                # ── Fallback to our own salary template system ────────────────
                num_days = calendar.monthrange(self.year, int(self.month))[1]
                cfg = self.env['hr.employee']._dotbd_company_weekend_config()
                period_start = date(self.year, int(self.month), 1)
                period_end = date(self.year, int(self.month), num_days)
                all_days = [date(self.year, int(self.month), dn)
                            for dn in range(1, num_days + 1)]
                for line in self.employee_line_ids:
                    emp = line.employee_id
                    # Per-employee OFF weekdays (personal schedule → company policy)
                    off = emp._dotbd_weekend_weekdays(*cfg) if emp else set(self._get_weekend_days())
                    base_working = {dt for dt in all_days if dt.weekday() not in off}
                    # Mandatory days add the off-days the employee must still work.
                    mand = emp._dotbd_mandatory_dates(period_start, period_end) if emp else set()
                    working_days = len(base_working | mand)
                    self._fill_line_from_salary_template(line, working_days)

    def _get_payslip_status_summary(self, employees):
        """Return payslip status counts for all employees in the current period.

        Used to show a warning notification after loading employees so HR knows
        which employees have no payslip, which are still in draft/waiting, etc.

        Returns dict with counts per state + list of employee names per issue.
        """
        if not self._has_native_payroll():
            return None

        try:
            date_from, date_to, _nd, _mi, _yr, _lbl = self._get_period_dates()
        except Exception:
            return None

        # Terminal states that provide salary data
        _DONE_STATES = ['done', 'validated', 'paid', 'verify']  # verify=Waiting: compute_sheet() sets this state in Odoo 18
        _PENDING_STATES = ['draft', 'verify', 'waiting', 'cancel']

        result = {
            'done': [],    # has confirmed payslip → data loaded ✅
            'draft': [],   # payslip exists but Draft → needs computation
            'waiting': [], # payslip exists but Waiting/Verify → needs confirmation
            'paid': [],    # payslip paid → data loaded ✅
            'none': [],    # no payslip at all → no data
        }

        for emp in employees:
            payslips = self.env['hr.payslip'].search([
                ('employee_id', '=', emp.id),
                ('date_from', '>=', date_from),
                ('date_to', '<=', date_to),
            ])
            if not payslips:
                result['none'].append(emp.name)
                continue

            # Check states — prefer done/validated first
            # NOTE: 'verify' = Waiting in Odoo 18 Enterprise. compute_sheet()
            # sets this state. We treat it as ready (salary data is computed).
            states = payslips.mapped('state')
            if any(s in ('done', 'validated', 'verify') for s in states):
                result['done'].append(emp.name)
            elif any(s == 'paid' for s in states):
                result['paid'].append(emp.name)
            else:
                result['draft'].append(emp.name)

        return result

    def _payslip_status_notification(self, employees):
        """Build a display_notification message showing payslip status per employee."""
        summary = self._get_payslip_status_summary(employees)
        if not summary or not self.use_native_payroll or not self.check_payslip_status:
            return None

        total = len(employees)
        ok_count = len(summary['done']) + len(summary['paid'])
        none_count = len(summary['none'])
        draft_count = len(summary['draft'])
        wait_count = len(summary['waiting'])

        if ok_count == total:
            # All good — brief success message
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Payslips Loaded'),
                    'message': _(
                        '✅ All %(total)s employees have confirmed payslips — salary data loaded.',
                        total=total),
                    'type': 'success',
                    'sticky': False,
                },
            }

        # Build warning message
        lines = []
        if ok_count:
            lines.append(_('✅ %(n)s employees — confirmed payslip (Done/Paid) → data loaded', n=ok_count))
        if draft_count:
            lines.append(_(
                '📝 %(n)s employees — payslip in Draft → needs Compute Sheet + Confirm:\n   %(names)s',
                n=draft_count, names=', '.join(summary['draft'][:10])))
        if wait_count:
            lines.append(_(
                '⏳ %(n)s employees — payslip Waiting/Verify → needs confirmation:\n   %(names)s',
                n=wait_count, names=', '.join(summary['waiting'][:10])))
        if none_count:
            lines.append(_(
                '❌ %(n)s employees — NO payslip found for this period → no salary data:\n   %(names)s',
                n=none_count, names=', '.join(summary['none'][:10])))

        msg = '\n\n'.join(lines)
        notify_type = 'danger' if none_count or draft_count else 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payslip Status — %(ok)s/%(total)s employees ready', ok=ok_count, total=total),
                'message': msg,
                'type': notify_type,
                'sticky': True,  # Keep visible so HR can take action
            },
        }

    def _wizard_reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }

    def action_load_selected(self):
        """Load lines for the employees selected in employee_ids."""
        self.ensure_one()
        employees = self.employee_ids or self.env['hr.employee'].search(
            [('active', '=', True)], order='name asc')
        self._build_lines_for(employees)

        # Show payslip status warning if native payroll ON
        notification = self._payslip_status_notification(employees)
        if notification:
            notification['params']['next'] = self._wizard_reopen()
            return notification
        return self._wizard_reopen()

    def action_load_all(self):
        """Load lines for ALL active employees."""
        self.ensure_one()
        employees = self.env['hr.employee'].search(
            [('active', '=', True)], order='name asc')
        self._build_lines_for(employees)

        # Show payslip status warning if native payroll ON
        notification = self._payslip_status_notification(employees)
        if notification:
            notification['params']['next'] = self._wizard_reopen()
            return notification
        return self._wizard_reopen()

    def action_generate_native_payslips(self):
        """Generate + compute hr.payslip for all loaded employees, then reload data.

        Client extra feature: pressing this button creates confirmed payslips for
        every employee in the current period using their active salary structure,
        then re-fills all financial fields and rule lines from those payslips.
        """
        self.ensure_one()
        if not self._has_native_payroll():
            raise ValidationError(_('Native Odoo payroll (hr_payroll) is not installed.'))
        if not self.employee_line_ids:
            raise ValidationError(_('Load employees first before generating payslips.'))

        HrPayslip = self.env['hr.payslip']
        date_from, date_to, _nd, _mi, _yr, _lbl = self._get_period_dates()
        generated, skipped = 0, []

        # ── Find or create a payslip BATCH (hr.payslip.run) for this period ───
        # So generated payslips appear grouped under a named batch in
        # Payroll → Payslips Batches and under "Batch Name" in the Payslips list
        # — exactly like Odoo's native batch generation.
        batch = False
        if 'hr.payslip.run' in self.env:
            batch = self.env['hr.payslip.run'].search([
                ('date_start', '=', date_from),
                ('date_end', '=', date_to),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
            if not batch:
                try:
                    batch = self.env['hr.payslip.run'].create({
                        'name': _lbl,            # auto name e.g. "May 2026"
                        'date_start': date_from,
                        'date_end': date_to,
                    })
                except Exception as e:
                    _logger.warning('Could not create payslip batch: %s', e)
                    batch = False

        created_payslips = HrPayslip.browse()

        for line in self.employee_line_ids:
            emp = line.employee_id
            # Find contract (open/close, date-aware) — matches native batch wizard
            contract = self._get_active_contract_or_version(emp, date_from, date_to)
            if not contract:
                skipped.append(emp.name)
                continue

            # Check if a payslip already exists for this period
            existing = HrPayslip.search([
                ('employee_id', '=', emp.id),
                ('date_from', '=', date_from),
                ('date_to', '=', date_to),
            ], limit=1)

            if existing:
                payslip = existing
                # Attach to the batch if not already in one
                if batch and not existing.payslip_run_id:
                    try:
                        existing.payslip_run_id = batch.id
                    except Exception:
                        pass
            else:
                # Create a new payslip
                struct = getattr(contract, 'struct_id', False)
                vals = {
                    'employee_id': emp.id,
                    'date_from': date_from,
                    'date_to': date_to,
                    'name': f'{emp.name} - {_lbl}',
                }
                if batch:
                    vals['payslip_run_id'] = batch.id
                if struct:
                    vals['struct_id'] = struct.id
                # v18: contract_id, v19: version_id / contract_id
                if hasattr(contract, 'struct_id'):
                    if self._has_hr_contract() and contract._name == 'hr.contract':
                        vals['contract_id'] = contract.id
                    elif 'hr.version' in self.env and contract._name == 'hr.version':
                        # v19 uses version_id on payslip
                        if hasattr(HrPayslip, 'version_id'):
                            vals['version_id'] = contract.id
                        else:
                            vals['contract_id'] = contract.id
                try:
                    payslip = HrPayslip.create(vals)
                except Exception as e:
                    _logger.warning('Could not create payslip for %s: %s', emp.name, e)
                    skipped.append(emp.name)
                    continue

            # Compute the payslip (run salary rules)
            try:
                payslip.compute_sheet()
                created_payslips |= payslip
                generated += 1
            except Exception as e:
                _logger.warning('Could not compute payslip for %s: %s', emp.name, e)
                skipped.append(emp.name)

        # Move the batch to 'verify' (Waiting) state, like the native wizard does
        if batch and created_payslips:
            try:
                created_payslips.filtered(
                    lambda p: p.state == 'draft').write({'state': 'verify'})
                if hasattr(batch, 'state'):
                    batch.state = 'verify'
            except Exception as e:
                _logger.debug('Could not set batch/payslip verify state: %s', e)

        # Re-fill all lines from the newly generated payslips
        for line in self.employee_line_ids:
            native = self._get_native_salary(line.employee_id, date_from, date_to)
            if native['source'] != 'none':
                vals = {
                    'wage': native['wage'],
                    'transport_allowance': native['transport_allowance'],
                    'housing_deduction': native['housing_deduction'],
                    'advance_amount': native['advance_amount'],
                    'bonus_amount': native['bonus_amount'],
                    'deduction_amount': native['deduction_amount'],
                    'payslip_state': native.get('payslip_state', 'none'),
                }
                line.write(vals)
                # Write native_payslip_id via SQL (ORM strips it)
                if native.get('native_payslip_id'):
                    line._set_native_payslip_id_sql(native['native_payslip_id'])
                if native.get('rule_lines'):
                    line.rule_line_ids.unlink()
                    for rl in native['rule_lines']:
                        rl['statement_line_id'] = line.id
                    self.env['dotbd.monthly.statement.rule.line'].create(native['rule_lines'])

        msg = _('%d payslip(s) generated/updated.') % generated
        if batch:
            msg += ' ' + _('Grouped in batch "%s" (Payroll → Payslips Batches).') % batch.name
        if skipped:
            msg += ' ' + _('Skipped (no active/expired contract for this period): %s') % ', '.join(skipped)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Payslips Generated'),
                'message': msg,
                'type': 'success' if not skipped else 'warning',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'res_id': self.id,
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                    'target': 'new',
                },
            },
        }

    # ─── Data builder ────────────────────────────────────────────────────────

    def _get_required_hours(self, employee, start_date, end_date, tz):
        """Return expected working hours for one employee in [start_date, end_date]."""
        cal = employee.resource_calendar_id or self.env.company.resource_calendar_id
        if not cal:
            return 0.0
        try:
            cal_tz = pytz.timezone(cal.tz or 'UTC')
            start_dt = cal_tz.localize(
                datetime.combine(start_date, datetime.min.time()))
            end_dt = cal_tz.localize(
                datetime.combine(end_date, datetime.max.time()))
            work_data = cal.get_work_duration_data(start_dt, end_dt)
            return round(work_data.get('hours', 0.0), 1)
        except Exception:
            # Fallback: working days × 8 hrs (skip Fri + Sat)
            count = 0
            d = start_date
            while d <= end_date:
                if d.weekday() not in (4, 5):
                    count += 1
                d += timedelta(days=1)
            return round(count * 8.0, 1)

    def _get_weekend_days(self):
        """Return set of weekday ints (0=Mon … 6=Sun) that are weekends per system config."""
        ICP = self.env['ir.config_parameter'].sudo()
        _codes = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
        weekend = set()
        for num, code in _codes.items():
            val = ICP.get_param(
                f'dotbd_hr_zk_attendance_suite.weekend_{code}', 'False')
            if val in ('True', '1', 'true'):
                weekend.add(num)
        return weekend or {4, 5}   # default: Fri + Sat

    def _get_leave_map(self, employee, start_utc, end_utc, start_date, end_date, tz):
        """Return dict {date: leave_type_name} for validated leaves in the period."""
        leaves = self.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'validate'),
            ('date_from', '<=', end_utc),
            ('date_to', '>=', start_utc),
        ])
        leave_map = {}
        for leave in leaves:
            # date_from/date_to are stored in UTC as Datetime
            lf = (pytz.utc.localize(leave.date_from).astimezone(tz).date()
                  if leave.date_from else start_date)
            lt = (pytz.utc.localize(leave.date_to).astimezone(tz).date()
                  if leave.date_to else end_date)
            lf = max(lf, start_date)
            lt = min(lt, end_date)
            d = lf
            while d <= lt:
                leave_map[d] = leave.holiday_status_id.name or _('Leave')
                d += timedelta(days=1)
        return leave_map

    def _get_public_holiday_dates(self, employee, start_date, end_date):
        """Return set of date objects that are public holidays in [start_date, end_date]."""
        resource_calendar = (employee.resource_calendar_id
                             or employee.company_id.resource_calendar_id)
        domain = [
            ('resource_id', '=', False),
            ('date_from', '<=', datetime.combine(end_date, datetime.max.time())),
            ('date_to', '>=', datetime.combine(start_date, datetime.min.time())),
        ]
        if resource_calendar:
            domain.insert(0, ('calendar_id', 'in', [False, resource_calendar.id]))
        else:
            domain.insert(0, ('calendar_id', '=', False))

        holidays = set()
        for leave in self.env['resource.calendar.leaves'].sudo().search(domain):
            lf = leave.date_from.date() if hasattr(leave.date_from, 'date') else leave.date_from
            lt = leave.date_to.date() if hasattr(leave.date_to, 'date') else leave.date_to
            d = max(lf, start_date)
            while d <= min(lt, end_date):
                holidays.add(d)
                d += timedelta(days=1)
        return holidays

    def _build_employee_data(self, employee, line, month_int, year,
                              num_days, start_date, end_date,
                              start_utc, end_utc, tz, cache=None):
        """Build attendance data dict for one employee.

        ``cache`` is a per-print-run dict that memoises values which vary only
        by calendar / system config, not by employee — so on a 244-employee run
        we don't re-read the 7 weekend config params, re-search public holidays,
        and re-run get_work_duration_data once per employee. Big speed-up.
        """
        if cache is None:
            cache = {}
        # ── Attendance records ────────────────────────────────────────────────
        attendances = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ], order='check_in asc')

        # day → list of (local_in, local_out, late_with_tol, late_raw, worked_hours)
        day_records = defaultdict(list)
        for att in attendances:
            local_in = pytz.utc.localize(att.check_in).astimezone(tz)
            local_out = (pytz.utc.localize(att.check_out).astimezone(tz)
                         if att.check_out else None)
            late_tol = getattr(att, 'tolerance_late_time', 0) or 0  # after tolerance
            late_raw = getattr(att, 'late_check_in', 0) or 0         # without tolerance
            day_records[local_in.date()].append((local_in, local_out, late_tol, late_raw, att.worked_hours or 0.0))

        # ── Leave map ─────────────────────────────────────────────────────────
        leave_map = self._get_leave_map(
            employee, start_utc, end_utc, start_date, end_date, tz)

        # ── Weekend + Public Holiday sets ─────────────────────────────────────
        # Company weekend policy is read once per run; the per-employee OFF
        # weekdays then honour any personal working schedule (see helper).
        if 'weekend_cfg' not in cache:
            cache['weekend_cfg'] = employee._dotbd_company_weekend_config()
        emp_off_weekdays = employee._dotbd_weekend_weekdays(*cache['weekend_cfg'])

        cal = (employee.resource_calendar_id
               or employee.company_id.resource_calendar_id)
        # Key on calendar AND company: only share a cached value when both match
        # (the underlying helpers fall back to a company calendar when an
        # employee has none, so company must be part of the key to stay correct).
        cal_key = (cal.id if cal else False, employee.company_id.id)
        hol_cache = cache.setdefault('holidays', {})
        if cal_key not in hol_cache:
            hol_cache[cal_key] = self._get_public_holiday_dates(
                employee, start_date, end_date)
        holiday_dates = hol_cache[cal_key]

        # Mandatory days (hr.leave.mandatory.day) for THIS employee — a mandatory
        # day overrides a normal weekend so the employee is expected to work.
        emp_mandatory_dates = employee._dotbd_mandatory_dates(start_date, end_date)

        # ── Build per-day rows ────────────────────────────────────────────────
        rows = []
        total_actual_hours = 0.0
        working_days = 0
        time_off_days = 0
        absent_days = 0

        # Late counters — with tolerance / without tolerance
        late_count_tol = 0        # days late after tolerance
        late_count_raw = 0        # days late before tolerance (any raw lateness)
        total_late_min_tol = 0.0  # sum of tolerance_late_time
        total_late_min_raw = 0.0  # sum of late_check_in (raw)

        for day_num in range(num_days):
            d = start_date + timedelta(days=day_num)
            records = day_records.get(d, [])
            time_off_type = leave_map.get(d, '')
            is_weekend = d.weekday() in emp_off_weekdays
            if is_weekend and d in emp_mandatory_dates:
                is_weekend = False   # mandatory day → treated as a working day
            is_holiday = d in holiday_dates

            if records:
                first_in = min(r[0] for r in records)
                outs = [r[1] for r in records if r[1] is not None]
                last_out = max(outs) if outs else None
                # Sum each record's worked_hours — matches Odoo native calculation.
                # Do NOT use (last_out - first_in) span: inflates hours when employee
                # has multiple sessions (e.g. morning + evening extra meeting).
                hours = sum(r[4] for r in records)
                late_tol = sum(r[2] for r in records)
                late_raw = sum(r[3] for r in records)

                total_actual_hours += hours
                working_days += 1
                if late_tol > 0:
                    late_count_tol += 1
                    total_late_min_tol += late_tol
                if late_raw > 0:
                    late_count_raw += 1
                    total_late_min_raw += late_raw

                rows.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'check_in': first_in.strftime('%H:%M'),
                    'check_out': last_out.strftime('%H:%M') if last_out else '',
                    'hours': round(hours, 1) if hours else '',
                    'late_minutes': round(late_tol, 0) if late_tol else '',
                    'time_off': time_off_type,
                    'is_weekend': is_weekend,
                    'has_data': True,
                })
            elif time_off_type:
                time_off_days += 1
                rows.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'check_in': '', 'check_out': '', 'hours': '',
                    'late_minutes': '', 'time_off': time_off_type,
                    'is_weekend': is_weekend, 'has_data': False,
                })
            else:
                # Absent only if working day AND not a public holiday
                if not is_weekend and not is_holiday:
                    absent_days += 1
                rows.append({
                    'date': d.strftime('%Y-%m-%d'),
                    'check_in': '', 'check_out': '', 'hours': '',
                    'late_minutes': '', 'time_off': '',
                    'is_weekend': is_weekend, 'has_data': False,
                })

        total_actual_hours = round(total_actual_hours, 1)
        total_late_min_tol = int(round(total_late_min_tol))
        total_late_min_raw = int(round(total_late_min_raw))
        # Required hours depend only on calendar + period (fixed for the run).
        rh_cache = cache.setdefault('required_hours', {})
        if cal_key not in rh_cache:
            rh_cache[cal_key] = self._get_required_hours(
                employee, start_date, end_date, tz)
        required_hours = rh_cache[cal_key]

        payslip = (line.payslip_id
                   if (line and self.auto_create_payslip
                       and self.include_payslip_in_print and line.payslip_id)
                   else None)

        return {
            'employee_name': employee.name,
            'employee_code': getattr(employee, 'device_id_num', '') or '',
            'department': employee.department_id.name if employee.department_id else '',
            'job_title': employee.job_title or (employee.job_id.name if employee.job_id else ''),
            'month_name_ar': LEVANTINE_MONTHS.get(month_int, ''),
            'month_name_en': dict(self._fields['month'].selection).get(self.month, ''),
            'year': year,
            'rows': rows,
            # Totals
            'working_days': working_days,
            'total_actual_hours': total_actual_hours,
            'required_hours': required_hours,
            # Late — with tolerance (penalised)
            'total_late_minutes': total_late_min_tol,
            'late_count_with_tolerance': late_count_tol,
            'total_late_minutes_with_tolerance': total_late_min_tol,
            # Late — without tolerance (raw arrivals after schedule)
            'late_count_without_tolerance': late_count_raw,
            'total_late_minutes_without_tolerance': total_late_min_raw,
            # Leave & absent
            'total_time_off_days': time_off_days,
            'total_absent_days': absent_days,  # excludes weekends & public holidays
            # Financial (from per-employee line)
            'wage': line.wage if line else 0.0,
            'advance_amount': line.advance_amount if line else 0.0,
            'deduction_amount': line.deduction_amount if line else 0.0,
            'housing_deduction': line.housing_deduction if line else 0.0,
            'transport_allowance': line.transport_allowance if line else 0.0,
            'bonus_amount': line.bonus_amount if line else 0.0,
            'net_due': round(
                (line.wage if line else 0.0)
                - (line.advance_amount if line else 0.0)
                - (line.deduction_amount if line else 0.0)
                - (line.housing_deduction if line else 0.0)
                + (line.transport_allowance if line else 0.0)
                + (line.bonus_amount if line else 0.0),
                2
            ),
            # Payslip (optional — only when include_payslip_in_print is set)
            'payslip': payslip,
            # Language
            'print_in_arabic': self.print_in_arabic,
            # Native payroll: True when use_native_payroll is ON and payslip rule
            # lines were loaded — drives the PDF summary box layout
            'use_native_payroll': self.use_native_payroll and self._has_native_payroll(),
            # List of dicts: rule_name, rule_code, category_name, category_code,
            # amount, total — mirrors the salary computation tab on the hr.payslip.
            # Empty when native payroll is OFF or no payslip lines were found.
            'rule_lines': [
                {
                    'sequence': rl.sequence,
                    'rule_name': rl.rule_name,
                    'rule_code': rl.rule_code,
                    'category_name': rl.category_name,
                    'category_code': rl.category_code,
                    'amount': rl.amount,
                    'total': rl.total,
                }
                for rl in (line.rule_line_ids.sorted('sequence') if line else [])
            ],
        }

    def get_all_employees_data(self):
        """Return list of data dicts — one per employee line, in line order.
        Called by the QWeb template to generate one PDF page per employee.
        """
        self.ensure_one()
        if not self.employee_line_ids:
            raise ValidationError(
                _('No employees loaded. Please click "Load Selected" or '
                  '"Load All Employees" first.'))

        start_date, end_date, num_days, month_int, year, _lbl = self._get_period_dates()

        tz_name = self.env.context.get('tz') or self.env.user.tz or 'UTC'
        tz = pytz.timezone(tz_name)

        start_utc = (tz.localize(datetime.combine(start_date, datetime.min.time()))
                     .astimezone(pytz.utc).replace(tzinfo=None))
        end_utc = (tz.localize(datetime.combine(end_date, datetime.max.time()))
                   .astimezone(pytz.utc).replace(tzinfo=None))

        # Apply print filter — only include lines matching pdf_include_mode + stage filter
        filtered_lines = self._get_filtered_lines_for_print()

        # Chunked rendering: when action_print_pdf renders in batches it sets
        # chunk_line_ids in context so each wkhtmltopdf call only processes that
        # subset of employees (prevents the segfault on large runs).
        chunk_ids = self.env.context.get('chunk_line_ids')
        if chunk_ids:
            chunk_set = set(chunk_ids)
            filtered_lines = filtered_lines.filtered(lambda l: l.id in chunk_set)

        # Per-run cache: memoises weekend config, public holidays and required
        # hours (all calendar/config-scoped) so they aren't recomputed for every
        # employee — the main cost on large (100-244 employee) runs.
        cache = {}

        result = []
        for line in filtered_lines.sorted('sequence'):
            emp_data = self._build_employee_data(
                line.employee_id, line,
                month_int, year, num_days,
                start_date, end_date,
                start_utc, end_utc, tz, cache,
            )
            # Add payslip state for PDF display
            emp_data['payslip_state'] = line.payslip_state or 'none'
            emp_data['payslip_state_label'] = {
                'done': 'Done ✓',
                'paid': 'Paid ✓',
                'waiting': 'Waiting',
                'draft': 'Draft',
                'none': 'No Payslip',
            }.get(line.payslip_state or 'none', '')
            result.append(emp_data)
        return result

    # ─── Print action ────────────────────────────────────────────────────────

    def _get_filtered_lines_for_print(self):
        """Return employee lines filtered by the print mode and stage checkboxes.

        pdf_include_mode:
          'all'          → all loaded employees (regardless of payslip state)
          'payslip_only' → only employees who have a payslip, filtered by stage

        Stage filters (only used when payslip_only):
          pdf_filter_done, pdf_filter_paid, pdf_filter_waiting, pdf_filter_draft
        """
        lines = self.employee_line_ids

        if self.pdf_include_mode == 'all':
            return lines  # everyone, no filter

        # payslip_only — apply stage filter
        allowed_states = []
        if self.pdf_filter_done:    allowed_states.extend(['done'])
        if self.pdf_filter_paid:    allowed_states.extend(['paid'])
        if self.pdf_filter_waiting: allowed_states.extend(['waiting'])
        if self.pdf_filter_draft:   allowed_states.extend(['draft'])

        if not allowed_states:
            # No stage selected → default to Done+Paid to avoid empty PDF
            allowed_states = ['done', 'paid']

        return lines.filtered(lambda l: l.payslip_state in allowed_states)

    def _safe_native_payslip_ids(self, lines=None):
        """Return list of raw hr.payslip IDs for the given statement lines.

        Reads the FK column directly via SQL, completely bypassing the ORM's
        Many2one comodel resolution.  This prevents crashes on odoo.sh (and
        similar environments) where the hr_payroll module is not yet fully
        registered in the current worker's registry and the ORM resolves the
        comodel to the ``_unknown`` pseudo-model.  That pseudo-model has **no**
        ``.id`` / ``.ids`` attributes, so even ``line.native_payslip_id.id``
        raises ``AttributeError``, and ``.exists()`` issues a query against a
        non-existent ``"_unknown"`` table (``UndefinedTable``).
        """
        if lines is None:
            lines = self.employee_line_ids
        if not lines:
            return []
        self.env.cr.execute(
            "SELECT native_payslip_id "
            "FROM dotbd_monthly_statement_line "
            "WHERE id IN %s AND native_payslip_id IS NOT NULL",
            [tuple(lines.ids)]
        )
        return [r[0] for r in self.env.cr.fetchall()]

    def _mark_linked_payslips_done(self):
        """Best-effort: move linked native payslips from Waiting/Draft → Done
        before printing, so the statement reflects confirmed (Done) payslips.

        We stop at 'Done' — NOT 'Paid' — because Paid requires fully
        reconcilable accounting setup (the NET salary rule needs a reconcilable
        credit account), which many installs don't have.

        Each payslip is handled in its own savepoint + try/except so that one
        payslip that cannot be confirmed (e.g. "contract outside payslip
        period", or an accounting config issue) never blocks the PDF download
        or the other payslips.
        """
        if not (self.use_native_payroll and self._has_native_payroll()):
            return
        payslip_ids = self._safe_native_payslip_ids()
        payslips = self.env['hr.payslip'].browse(payslip_ids).exists()
        for slip in payslips.filtered(lambda p: p.state in ('draft', 'verify')):
            try:
                with self.env.cr.savepoint():
                    if slip.state == 'draft':
                        slip.compute_sheet()
                    slip.action_payslip_done()
            except Exception as e:
                _logger.warning(
                    'Print: could not confirm payslip %s to Done: %s',
                    slip.id, e)


    def action_print_pdf(self):
        """Render the statement PDF in safe batches, merge, then download.

        WHY BATCHED: wkhtmltopdf segfaults (error -11) when one call renders too
        many pages — each employee is a full page with its own external_layout
        header/footer, so 50-200 employees overwhelm it. We render
        pdf_batch_size employees per wkhtmltopdf call and merge the results with
        Odoo's merge_pdf — each call stays small and stable.

        ORDER OF OPERATIONS (fixes the 'payslip marked done even if PDF crashes'
        bug): we render ALL batches first; only after every batch succeeds do we
        mark the linked payslips Done. If any batch raises, the exception
        propagates and NO payslip state is changed.
        """
        self.ensure_one()
        if not self.employee_line_ids:
            raise ValidationError(
                _('No employees loaded. Please click "Load Selected" or '
                  '"Load All Employees" first.'))

        filtered = self._get_filtered_lines_for_print().sorted('sequence')
        if not filtered:
            raise ValidationError(
                _('No employees match the selected print filter. '
                  'Check the "Include in PDF" and stage filter settings, '
                  'or confirm payslips first.'))

        report = self.env.ref(
            'dotbd_hr_zk_attendance_suite.dotbd_monthly_statement_report')
        report_name = report.report_name
        line_ids = filtered.ids

        batch_size = self.pdf_batch_size or 0
        # Decide chunking. If batch_size is 0 or covers everyone, single pass.
        if batch_size and len(line_ids) > batch_size:
            chunks = [line_ids[i:i + batch_size]
                      for i in range(0, len(line_ids), batch_size)]
        else:
            chunks = [line_ids]

        # ── Render every batch BEFORE changing any payslip state ──────────────
        pdf_parts = []
        for chunk in chunks:
            ctx_report = report.with_context(
                chunk_line_ids=chunk,
                report_pdf_no_attachment=True,  # don't auto-store per-batch
            )
            pdf_content, _ftype = ctx_report._render_qweb_pdf(
                report_name, self.ids)
            pdf_parts.append(pdf_content)

        # Merge batches into one file (single batch → use it directly)
        if len(pdf_parts) == 1:
            final_pdf = pdf_parts[0]
        elif merge_pdf:
            final_pdf = merge_pdf(pdf_parts)
        else:
            # Fallback: merge_pdf unavailable — return the first batch only.
            _logger.warning('merge_pdf unavailable; returning first batch only')
            final_pdf = pdf_parts[0]

        # ── All batches rendered OK → NOW confirm payslips to Done ────────────
        self._mark_linked_payslips_done()

        # Save merged PDF and return a download URL
        filename = 'Monthly_Statement_%s_%s.pdf' % (self.month or '', self.year or '')
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(final_pdf),
            'mimetype': 'application/pdf',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
        }

    def action_print_pdf_paid_all(self):
        """Mark all linked native payslips as PAID, then print the statements.

        Convenience action for managers: before downloading the PDF, every
        native payslip linked to the loaded employees is moved to 'paid' state
        in Payroll (so it reflects there too). Then the same PDF as
        action_print_pdf is generated.

        Odoo payslip state flow is draft → verify → done → paid, so we step
        each payslip up to 'paid' safely:
          verify  → done (action_payslip_done)
          done    → paid (action_payslip_paid)
        Payslips already paid are left as-is. Only applies when native payroll
        is ON; otherwise this behaves exactly like Print Statements.

        ACCOUNTING NOTE (verified against Odoo 18 source):
        - Base hr_payroll: action_payslip_done / action_payslip_paid are pure
          STATE changes — no journal entries, no accounting impact.
          action_payslip_paid only sets state='paid' + paid_date.
        - With hr_payroll_account installed: action_payslip_done is overridden
          to call _action_create_account_move(), which posts a journal entry
          ONLY for payslips whose salary structure has a journal_id set
          (slip.struct_id.journal_id). Structures without a journal create no
          move — so no accounting unless the customer explicitly configured a
          payroll journal on the structure. action_payslip_paid still posts
          nothing itself (payment registration is a separate manual action).
        We call done only on draft/verify slips (never on already-paid ones),
        which avoids the 'journal entry for a paid payslip' ValidationError.
        Each step is wrapped in try/except so an incomplete accounting setup
        cannot block the PDF download.
        """
        self.ensure_one()
        if not self.employee_line_ids:
            raise ValidationError(
                _('No employees loaded. Please click "Load Selected" or '
                  '"Load All Employees" first.'))

        if self.use_native_payroll and self._has_native_payroll():
            # Re-browse via the real hr.payslip model. The native_payslip_id
            # Many2one can resolve to the '_unknown' pseudo-model on servers
            # where hr_payroll is only partially registered, which would make
            # p.state raise AttributeError. Browsing by id through self.env
            # guarantees genuine hr.payslip records (and .exists() drops any
            # that were deleted).
            payslip_ids = self._safe_native_payslip_ids()
            payslips = self.env['hr.payslip'].browse(payslip_ids).exists()
            if payslips:
                # Step 1: verify/draft → done
                to_done = payslips.filtered(
                    lambda p: p.state in ('draft', 'verify'))
                if to_done:
                    try:
                        # compute first if still draft (no lines yet)
                        draft = to_done.filtered(lambda p: p.state == 'draft')
                        if draft:
                            draft.compute_sheet()
                        to_done.action_payslip_done()
                    except Exception as e:
                        _logger.warning(
                            'Paid All: could not confirm payslips to done: %s', e)
                # Step 2: done → paid
                to_pay = payslips.filtered(lambda p: p.state == 'done')
                if to_pay:
                    try:
                        to_pay.action_payslip_paid()
                    except Exception as e:
                        _logger.warning(
                            'Paid All: could not set payslips to paid: %s', e)

        # Now produce the PDF exactly like the normal print action
        return self.action_print_pdf()
