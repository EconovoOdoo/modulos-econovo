# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DotbdSalaryCertificateLine(models.Model):
    """One salary component line on the certificate (editable by HR)."""
    _name = 'dotbd.salary.certificate.line'
    _description = 'Salary Certificate Line'
    _order = 'sequence, id'

    cert_id = fields.Many2one(
        'dotbd.salary.certificate', string='Certificate',
        required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Component', required=True)
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one(
        related='cert_id.currency_id', store=True)


class DotbdSalaryCertificate(models.Model):
    """Salary / Employment Certificate issued to an employee.

    Two modes:
    • auto   – HR clicks "Populate from System"; employee info + salary
               components are pulled from the active salary assignment template;
               all fields remain editable so HR can adjust before printing.
    • manual – HR builds the lines from scratch.
    """
    _name = 'dotbd.salary.certificate'
    _description = 'Salary Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'

    # ── Reference & Status ────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference', readonly=True, copy=False, default='/')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
    ], string='Status', default='draft', tracking=True, copy=False)
    date = fields.Date(
        string='Issue Date', required=True, default=fields.Date.context_today,
        tracking=True)

    # ── Mode & Purpose ────────────────────────────────────────────────────────
    mode = fields.Selection([
        ('auto', 'Auto (from system)'),
        ('manual', 'Manual'),
    ], string='Mode', required=True, default='auto',
       help="Auto: click 'Populate from System' to pull data from the active "
            "salary assignment. All fields remain editable.\n"
            "Manual: build every line yourself.")
    purpose = fields.Selection([
        ('bank_loan', 'Bank Loan'),
        ('visa', 'Visa / Immigration'),
        ('rental', 'House / Office Rental'),
        ('personal', 'Personal Use'),
        ('other', 'Other'),
    ], string='Purpose', default='bank_loan', required=True)
    purpose_other = fields.Char(string='Purpose Details')

    # ── Employee ──────────────────────────────────────────────────────────────
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True,
        ondelete='restrict', tracking=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
        ondelete='restrict', required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
        ondelete='restrict', required=True)

    # ── Employee Details (editable) ───────────────────────────────────────────
    employee_name = fields.Char(string='Employee Name')
    employee_code = fields.Char(string='Employee ID / Code')
    designation = fields.Char(string='Designation / Job Title')
    department = fields.Char(string='Department')
    join_date = fields.Date(string='Joining Date')
    employee_type_label = fields.Char(
        string='Employment Type',
        default='Permanent',
        help="e.g. Permanent, Contract, Part-Time — printed on certificate.")

    # ── Salary Lines ──────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'dotbd.salary.certificate.line', 'cert_id',
        string='Salary Components')

    # ── Computed Totals ───────────────────────────────────────────────────────
    total_amount = fields.Monetary(
        string='Total Salary',
        currency_field='currency_id',
        compute='_compute_totals', store=True)
    net_amount = fields.Monetary(
        string='Net Pay Salary',
        currency_field='currency_id',
        help="Editable. Defaults to the sum of all lines (same as Total when "
             "there are no deductions).")
    amount_in_words = fields.Char(
        string='Amount in Words',
        compute='_compute_totals', store=True)

    # ── Signatory ─────────────────────────────────────────────────────────────
    signatory_name = fields.Char(string='Signed By (Name)')
    signatory_designation = fields.Char(string='Signed By (Designation)')

    # ── Internal Notes ────────────────────────────────────────────────────────
    note = fields.Text(string='Internal Notes')

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends('line_ids.amount', 'currency_id')
    def _compute_totals(self):
        for rec in self:
            total = sum(rec.line_ids.mapped('amount'))
            rec.total_amount = total
            try:
                rec.amount_in_words = rec.currency_id.amount_to_text(total)
            except Exception:
                rec.amount_in_words = ''

    # ── Onchange ──────────────────────────────────────────────────────────────

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            emp = self.employee_id
            self.employee_name = emp.name
            self.employee_code = emp.barcode or ''
            self.designation = emp.job_id.name or ''
            self.department = emp.department_id.name or ''
            self.currency_id = emp.company_id.currency_id or self.env.company.currency_id
            self.company_id = emp.company_id or self.env.company
            contract = self._get_active_contract(emp)
            if contract:
                self.join_date = contract.date_start

    @api.onchange('total_amount')
    def _onchange_total_amount(self):
        """Keep net_amount in sync when lines change, unless HR has manually set it."""
        if not self.net_amount:
            self.net_amount = self.total_amount

    # ── ORM overrides ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'dotbd.salary.certificate') or '/'
        return super().create(vals_list)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_populate_from_system(self):
        """Pull employee info and salary component lines from the active assignment."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Can only populate a Draft certificate."))
            if not rec.employee_id:
                raise UserError(_("Please select an employee first."))

            emp = rec.employee_id

            # Employee details
            rec.employee_name = emp.name
            rec.employee_code = emp.barcode or ''
            rec.designation = emp.job_id.name or ''
            rec.department = emp.department_id.name or ''
            contract = rec._get_active_contract(emp)
            if contract:
                rec.join_date = contract.date_start

            # Active salary assignment
            salary = self.env['dotbd.employee.salary'].search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], limit=1)

            if not salary:
                raise UserError(_(
                    "No active salary assignment found for %s. "
                    "Please create one first.", emp.name))

            rec.currency_id = salary.currency_id or emp.company_id.currency_id
            basic_wage = salary.basic_wage
            template = salary.template_id
            working_days = template.working_days_per_month or 26

            # Clear existing lines
            rec.line_ids.unlink()

            lines = []
            # Line 1: Basic Salary (always first)
            lines.append((0, 0, {
                'sequence': 1,
                'name': 'Basic Salary',
                'amount': basic_wage,
            }))

            # Remaining lines: from template components (earnings + allowances)
            seq = 10
            for comp in template.component_ids.filtered(lambda c: c.active):
                # Skip deductions; show_in_payslip=False means company provides physically
                if comp.component_type == 'deduction':
                    continue
                amount = comp.get_amount(basic_wage, attendance_days=working_days)
                if amount:
                    lines.append((0, 0, {
                        'sequence': seq,
                        'name': comp.name,
                        'amount': amount,
                    }))
                seq += 10

            rec.line_ids = lines

            # Net = Total (HR can override)
            rec.net_amount = sum(l[2]['amount'] for l in lines)

    def _get_active_contract(self, employee):
        """Return the employee's active contract, compatible with Odoo 18/19."""
        try:
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open'),
            ], limit=1)
            if contract:
                return contract
        except Exception:
            pass
        try:
            return self.env['hr.contract'].search([
                ('employee_id', '=', employee.id),
            ], order='date_start desc', limit=1)
        except Exception:
            return False

    def action_sync_net(self):
        """Set net_amount = total_amount (helper button)."""
        for rec in self:
            rec.net_amount = rec.total_amount

    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Certificate is already issued."))
            if not rec.employee_name:
                raise UserError(_("Employee name is required before issuing."))
            if not rec.line_ids:
                raise UserError(_("Add at least one salary component before issuing."))
            rec.state = 'issued'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    def action_print_certificate(self):
        return self.env.ref(
            'dotbd_hr_zk_attendance_suite.action_report_salary_certificate'
        ).report_action(self)
