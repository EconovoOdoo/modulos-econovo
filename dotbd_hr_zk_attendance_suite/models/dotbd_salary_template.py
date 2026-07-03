# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DotbdSalaryTemplate(models.Model):
    """Reusable salary structure template defining earnings, allowances and fine rules."""
    _name = 'dotbd.salary.template'
    _description = 'Salary Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Template Name', required=True, tracking=True,
        help='e.g. Standard Package, Management Grade, Field Staff')
    template_type = fields.Selection([
        # ── Bangladesh ─────────────────────────────────────────────
        ('bd_private',    'BD — Private Sector'),
        ('bd_public',     'BD — Government / Public Service'),
        ('bd_garments',   'BD — Garments (RMG)'),
        ('bd_bank',       'BD — Banking Sector'),
        ('bd_ngo',        'BD — NGO / Development'),
        ('bd_it',         'BD — IT / Technology'),
        ('bd_healthcare', 'BD — Healthcare / Hospital'),
        ('bd_education',  'BD — Education / School'),
        # ── Middle East ────────────────────────────────────────────
        ('uae_gcc',       'UAE / GCC (Middle East)'),
        # ── South Asia ─────────────────────────────────────────────
        ('india',         'India'),
        ('pakistan',      'Pakistan'),
        ('nepal',         'Nepal / Sri Lanka'),
        # ── Southeast Asia ─────────────────────────────────────────
        ('malaysia',      'Malaysia'),
        ('philippines',   'Philippines'),
        ('indonesia',     'Indonesia'),
        # ── General ────────────────────────────────────────────────
        ('general',       'General / Other'),
        ('custom',        'Custom'),
    ], string='Template Type', default='general', required=True,
        help='Category of this salary structure for easy identification.')
    wage_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('daily',   'Daily'),
        ('hourly',  'Hourly'),
        ('fixed',   'Fixed Contract'),
    ], string='Wage Type', default='monthly', required=True,
        help='How the basic wage (from contract) is interpreted:\n'
             '• Monthly: Full basic wage per month (standard).\n'
             '• Daily: Wage = daily rate × attendance days.\n'
             '• Hourly: Wage = hourly rate × worked hours.\n'
             '• Fixed: Full contract amount regardless of attendance.')
    # ── Employee type / category link ────────────────────────────────────────
    suitable_employee_type = fields.Selection([
        ('all',          'All Employee Types'),
        ('employee',     'Regular Employees'),
        ('student',      'Students / Interns'),
        ('freelance',    'Freelancers / Contractors'),
        ('daily_labour', 'Daily Labour / Casual Workers'),
    ], string='Suitable For', default='all',
        help='Advisory: which employee type this template is designed for. '
             'A warning is shown on the salary assignment if the employee\'s '
             'type does not match.')
    suitable_category_ids = fields.Many2many(
        'hr.employee.category',
        'dotbd_salary_template_category_rel',
        'template_id', 'category_id',
        string='Pay Categories',
        help='Optional: Employee Tags (from the Employee module) that this '
             'template is designed for. Informational — no restriction enforced.')

    working_days_per_month = fields.Integer(
        string='Working Days / Month', default=26,
        help='Used to compute per-day rate for leave deductions. '
             'Common values: 26 (private), 25 (government), 30 (calendar).')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    component_ids = fields.One2many(
        'dotbd.salary.component', 'template_id',
        string='Salary Components')
    fine_rule_ids = fields.One2many(
        'dotbd.fine.rule', 'template_id',
        string='Fine / Deduction Rules')
    leave_rule_ids = fields.One2many(
        'dotbd.salary.leave.rule', 'template_id',
        string='Leave Rules')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Internal Notes')

    employee_count = fields.Integer(
        string='Employees', compute='_compute_employee_count')

    def _compute_employee_count(self):
        data = self.env['dotbd.employee.salary'].read_group(
            [('template_id', 'in', self.ids), ('state', '=', 'active')],
            ['template_id'], ['template_id'])
        counts = {d['template_id'][0]: d['template_id_count'] for d in data}
        for rec in self:
            rec.employee_count = counts.get(rec.id, 0)

    def action_view_employees(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Salary Assignments',
            'res_model': 'dotbd.employee.salary',
            'view_mode': 'list,form',
            'domain': [('template_id', '=', self.id)],
            'context': {'default_template_id': self.id},
        }

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = f"{self.name} (Copy)"
        return super().copy(default)


class DotbdSalaryComponent(models.Model):
    """A single earning, allowance or deduction line inside a salary template."""
    _name = 'dotbd.salary.component'
    _description = 'Salary Component'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'dotbd.salary.template', string='Template',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Component Name', required=True,
                       help='e.g. House Rent Allowance, Medical Allowance')
    code = fields.Char(string='Code', required=True,
                       help='Short code used in payslip lines. e.g. HRA, MED, TRN')
    component_type = fields.Selection([
        ('earning',    'Earning'),
        ('allowance',  'Allowance'),
        ('bonus',      'Bonus'),
        ('deduction',  'Deduction'),
    ], string='Type', required=True, default='allowance')
    calculation_type = fields.Selection([
        ('percentage',     'Percentage of Basic'),
        ('fixed',          'Fixed Amount'),
        ('per_working_day', 'Per Working Day'),
    ], string='Calculation', required=True, default='percentage')
    percentage = fields.Float(
        string='Percentage (%)',
        digits=(5, 2),
        help='Percentage of basic wage. e.g. 60 means 60% of basic.')
    fixed_amount = fields.Monetary(
        string='Fixed Amount',
        currency_field='currency_id',
        help='Fixed amount added every month regardless of basic wage.')
    daily_amount = fields.Monetary(
        string='Daily Amount',
        currency_field='currency_id',
        help='Amount per attended working day. e.g. Lunch allowance ৳100/day.')
    show_in_payslip = fields.Boolean(
        string='Show as Earning',
        default=True,
        help='Enabled: appears as an earning line (employee receives cash).\n'
             'Disabled: appears as a deduction — use when the company provides '
             'the benefit physically (e.g. lunch) and deducts the cash equivalent.')
    currency_id = fields.Many2one(
        related='template_id.currency_id', store=True)
    active = fields.Boolean(default=True)

    @api.constrains('calculation_type', 'percentage', 'fixed_amount', 'daily_amount')
    def _check_amounts(self):
        for rec in self:
            if rec.calculation_type == 'percentage' and rec.percentage <= 0:
                raise ValidationError(
                    f"Component '{rec.name}': percentage must be greater than 0.")
            if rec.calculation_type == 'fixed' and rec.fixed_amount <= 0:
                raise ValidationError(
                    f"Component '{rec.name}': fixed amount must be greater than 0.")
            if rec.calculation_type == 'per_working_day' and rec.daily_amount <= 0:
                raise ValidationError(
                    f"Component '{rec.name}': daily amount must be greater than 0.")

    @api.onchange('calculation_type')
    def _onchange_calculation_type(self):
        if self.calculation_type == 'percentage':
            self.fixed_amount = 0.0
            self.daily_amount = 0.0
        elif self.calculation_type == 'fixed':
            self.percentage = 0.0
            self.daily_amount = 0.0
        else:
            self.percentage = 0.0
            self.fixed_amount = 0.0

    def get_amount(self, basic_wage, attendance_days=0):
        """Return computed amount for this component.

        Args:
            basic_wage: employee's monthly basic wage.
            attendance_days: actual days attended (used for per_working_day type).
        """
        self.ensure_one()
        if not self.active:
            return 0.0
        if self.calculation_type == 'percentage':
            return round(basic_wage * (self.percentage / 100.0), 2)
        if self.calculation_type == 'per_working_day':
            return round(self.daily_amount * attendance_days, 2)
        return round(self.fixed_amount, 2)


class DotbdFineRule(models.Model):
    """A deduction rule applied to a payslip based on attendance data."""
    _name = 'dotbd.fine.rule'
    _description = 'Fine / Deduction Rule'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'dotbd.salary.template', string='Template',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Rule Name', required=True,
                       help='e.g. Late Arrival Fine, Absent Deduction')
    rule_type = fields.Selection([
        ('per_minute_late', 'Per Minute Late'),
        ('per_day_absent',  'Per Day Absent'),
        ('late_threshold',  'N Late Days = 1 Absent Deduction'),
        ('fixed_per_late',  'Fixed Amount Per Late Occurrence'),
    ], string='Rule Type', required=True, default='per_minute_late')
    amount = fields.Monetary(
        string='Amount', required=True,
        currency_field='currency_id',
        help='Deduction amount per unit (per minute, per day, or per occurrence).')
    threshold_days = fields.Integer(
        string='Threshold (Days)',
        default=3,
        help='Only for "N Late Days = 1 Absent": number of late days that equal 1 absent deduction.')
    currency_id = fields.Many2one(
        related='template_id.currency_id', store=True)
    active = fields.Boolean(default=True)

    rule_type_description = fields.Char(
        string='Description', compute='_compute_rule_description')

    @api.depends('rule_type', 'amount', 'threshold_days', 'currency_id')
    def _compute_rule_description(self):
        for rec in self:
            symbol = rec.currency_id.symbol or ''
            if rec.rule_type == 'per_minute_late':
                rec.rule_type_description = (
                    f"{symbol}{rec.amount:.2f} deducted per late minute")
            elif rec.rule_type == 'per_day_absent':
                rec.rule_type_description = (
                    f"{symbol}{rec.amount:.2f} deducted per absent day")
            elif rec.rule_type == 'late_threshold':
                rec.rule_type_description = (
                    f"Every {rec.threshold_days} late days "
                    f"= 1 absent deduction ({symbol}{rec.amount:.2f})")
            elif rec.rule_type == 'fixed_per_late':
                rec.rule_type_description = (
                    f"{symbol}{rec.amount:.2f} flat fee per late occurrence")
            else:
                rec.rule_type_description = ''

    @api.constrains('rule_type', 'threshold_days')
    def _check_threshold(self):
        for rec in self:
            if rec.rule_type == 'late_threshold' and rec.threshold_days < 1:
                raise ValidationError(
                    "Threshold days must be at least 1.")

    def compute_deduction(self, late_count, absent_days, total_late_minutes):
        """
        Compute deduction amount from this rule given attendance stats.
        Returns (amount, note_string).
        """
        self.ensure_one()
        if not self.active:
            return 0.0, ''

        symbol = self.currency_id.symbol or ''

        if self.rule_type == 'per_minute_late':
            amount = round(self.amount * total_late_minutes, 2)
            note = (f"{total_late_minutes} min "
                    f"&times; {symbol}{self.amount:.2f} = {symbol}{amount:,.2f}")

        elif self.rule_type == 'per_day_absent':
            amount = round(self.amount * absent_days, 2)
            note = (f"{absent_days} days "
                    f"&times; {symbol}{self.amount:.2f} = {symbol}{amount:,.2f}")

        elif self.rule_type == 'late_threshold':
            deduct_count = late_count // self.threshold_days
            amount = round(self.amount * deduct_count, 2)
            note = (f"{late_count} late &divide; {self.threshold_days} "
                    f"= {deduct_count} &times; {symbol}{self.amount:.2f} "
                    f"= {symbol}{amount:,.2f}")

        elif self.rule_type == 'fixed_per_late':
            amount = round(self.amount * late_count, 2)
            note = (f"{late_count} occurrences "
                    f"&times; {symbol}{self.amount:.2f} = {symbol}{amount:,.2f}")

        else:
            amount, note = 0.0, ''

        return amount, note


class DotbdSalaryLeaveRule(models.Model):
    """
    Defines how a specific leave type affects the payslip.
    Paid leaves are ignored; unpaid leaves are deducted at a configurable rate.
    Leave encashment or bonus on leave can be modelled as 'add' rules.
    """
    _name = 'dotbd.salary.leave.rule'
    _description = 'Salary Leave Rule'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'dotbd.salary.template', string='Template',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Rule Name', required=True,
        help='e.g. Unpaid Leave Deduction, Festival Leave Encashment')
    leave_type_id = fields.Many2one(
        'hr.leave.type', string='Leave Type',
        ondelete='set null',
        help='Leave type this rule applies to. '
             'Leave blank to create a catch-all rule for any unmatched leave.')
    rule_action = fields.Selection([
        ('deduct',            'Deduct from Salary'),
        ('add',               'Add to Salary (Encashment/Bonus)'),
        ('ignore',            'Ignore — No Effect on Salary'),
        ('deduct_if_exceeded', 'Deduct if Limit Exceeded'),
    ], string='Action', required=True, default='deduct',
        help='What to do when the employee takes this type of leave.\n'
             '• Deduct: always deduct the configured amount per leave day.\n'
             '• Add: add to salary (leave encashment/bonus).\n'
             '• Ignore: paid leave — no salary effect.\n'
             '• Deduct if Limit Exceeded: fine only for days beyond the limit.')
    threshold_type = fields.Selection([
        ('allocation',    'HR Leave Allocation Balance'),
        ('monthly_limit', 'Monthly Limit (N days)'),
    ], string='Limit Based On', default='allocation',
        help='How to determine when fining starts:\n'
             '• HR Allocation: fine only when employee exceeds their validated leave balance.\n'
             '• Monthly Limit: fine for every day beyond N days taken this month.')
    monthly_threshold = fields.Integer(
        string='Free Days / Month',
        default=1,
        help='Maximum leave days allowed per month without fine.\n'
             'e.g. 2 means first 2 days are free; day 3 onwards triggers the fine.')
    amount_type = fields.Selection([
        ('per_day_basic',     'Per Working Day — from Basic Wage'),
        ('per_day_gross',     'Per Working Day — from Gross Wage'),
        ('fixed_per_day',     'Fixed Amount per Day'),
        ('fixed_total',       'Fixed Total Amount (regardless of days)'),
        ('percentage_basic',  'Percentage of Basic Wage'),
    ], string='Amount Type', default='per_day_basic',
        help='How the deduction/addition amount is calculated.')
    fixed_amount = fields.Monetary(
        string='Fixed Amount',
        currency_field='currency_id',
        help='Used when amount type is Fixed per Day or Fixed Total.')
    percentage = fields.Float(
        string='Percentage (%)', digits=(5, 2),
        help='Used when amount type is Percentage of Basic.')
    currency_id = fields.Many2one(
        related='template_id.currency_id', store=True)
    active = fields.Boolean(default=True)

    rule_summary = fields.Char(
        string='Summary', compute='_compute_rule_summary')

    @api.depends('rule_action', 'amount_type', 'fixed_amount', 'percentage',
                 'leave_type_id', 'currency_id', 'threshold_type', 'monthly_threshold')
    def _compute_rule_summary(self):
        for rec in self:
            if rec.rule_action == 'ignore':
                rec.rule_summary = 'No salary effect'
                continue
            if rec.rule_action == 'deduct_if_exceeded':
                if rec.threshold_type == 'monthly_limit':
                    action = f'Deduct (after {rec.monthly_threshold} day(s)/month)'
                else:
                    action = 'Deduct (beyond allocation)'
            elif rec.rule_action == 'deduct':
                action = 'Deduct'
            else:
                action = 'Add'
            symbol = rec.currency_id.symbol or ''
            if rec.amount_type == 'per_day_basic':
                rec.rule_summary = f'{action}: 1/working_days × Basic per leave day'
            elif rec.amount_type == 'per_day_gross':
                rec.rule_summary = f'{action}: 1/working_days × Gross per leave day'
            elif rec.amount_type == 'fixed_per_day':
                rec.rule_summary = (f'{action}: {symbol}{rec.fixed_amount:.2f}'
                                    f' per leave day')
            elif rec.amount_type == 'fixed_total':
                rec.rule_summary = (f'{action}: {symbol}{rec.fixed_amount:.2f}'
                                    f' flat')
            elif rec.amount_type == 'percentage_basic':
                rec.rule_summary = (f'{action}: {rec.percentage:.1f}%'
                                    f' of Basic')
            else:
                rec.rule_summary = ''

    def compute_amount(self, basic_wage, gross_wage, leave_days,
                       working_days_per_month):
        """
        Compute the salary impact (deduction or addition) for this leave rule.
        Returns amount (always positive; caller determines deduct vs add).
        """
        self.ensure_one()
        if not self.active or self.rule_action == 'ignore':
            return 0.0
        wdpm = working_days_per_month or 26
        if self.amount_type == 'per_day_basic':
            return round((basic_wage / wdpm) * leave_days, 2)
        elif self.amount_type == 'per_day_gross':
            base = gross_wage if gross_wage else basic_wage
            return round((base / wdpm) * leave_days, 2)
        elif self.amount_type == 'fixed_per_day':
            return round(self.fixed_amount * leave_days, 2)
        elif self.amount_type == 'fixed_total':
            return round(self.fixed_amount, 2)
        elif self.amount_type == 'percentage_basic':
            return round(basic_wage * self.percentage / 100.0, 2)
        return 0.0
