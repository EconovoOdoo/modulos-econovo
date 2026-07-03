# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DotbdEmployeeSalary(models.Model):
    """Links an employee to a salary template and their contract wage.

    basic_wage is computed live from the employee's active contract:
    • Odoo 18: hr.contract (state='open')
    • Odoo 19: hr.version  (active=True)

    The contract is the single source of truth for wage.
    """
    _name = 'dotbd.employee.salary'
    _description = 'Employee Salary Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'employee_id, effective_date desc'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Reference', readonly=True, default='/', copy=False)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee',
        required=True, ondelete='cascade', tracking=True,
        index=True)
    department_id = fields.Many2one(
        related='employee_id.department_id',
        string='Department', store=True)
    job_id = fields.Many2one(
        related='employee_id.job_id',
        string='Job Position', store=True)
    template_id = fields.Many2one(
        'dotbd.salary.template', string='Salary Template',
        required=True, tracking=True,
        ondelete='restrict')
    wage_type = fields.Selection(
        related='template_id.wage_type', readonly=True, store=False,
        string='Wage Type')

    # ── Employee type / category — pulled from hr.employee ────────────────
    employee_type = fields.Selection(
        related='employee_id.employee_type', readonly=True, store=True,
        string='Employee Type')
    employee_category_ids = fields.Many2many(
        related='employee_id.category_ids', readonly=True,
        string='Pay Category (Tags)')
    employee_type_mismatch = fields.Boolean(
        compute='_compute_employee_type_mismatch', store=False)

    def _compute_employee_type_mismatch(self):
        for rec in self:
            suitable = rec.template_id.suitable_employee_type or 'all'
            if suitable == 'all' or not rec.employee_type:
                rec.employee_type_mismatch = False
            else:
                rec.employee_type_mismatch = (rec.employee_type != suitable)

    # ── Contract / Version link ──────────────────────────────────────────
    import odoo
    _is_v19 = hasattr(odoo, 'release') and int(odoo.release.version_info[0]) >= 19

    contract_id = fields.Many2one(
        'hr.version' if _is_v19 else 'hr.contract', string='Contract (v18) / Version (v19)',
        compute='_compute_contract_info', store=False)
    contract_wage = fields.Monetary(
        string='Contract Wage',
        compute='_compute_contract_info', store=False,
        currency_field='currency_id',
        help='Current wage from employee contract/version (read-only).')
    has_active_contract = fields.Boolean(
        string='Has Active Contract',
        compute='_compute_contract_info', store=False)

    basic_wage = fields.Monetary(
        string='Basic Wage',
        compute='_compute_contract_info', store=False,
        currency_field='currency_id',
        help='Fetched live from the employee\'s active contract/version.')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True)
    effective_date = fields.Date(
        string='Effective From', required=True,
        default=fields.Date.today, tracking=True,
        help='Date from which this salary takes effect.')
    state = fields.Selection([
        ('draft',   'Draft'),
        ('active',  'Active'),
        ('expired', 'Expired'),
    ], string='Status', default='draft', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company)
    note = fields.Text(string='Notes')

    # ── Computed ──────────────────────────────────────────────────────────
    gross_estimate = fields.Monetary(
        string='Estimated Gross',
        compute='_compute_gross_estimate',
        currency_field='currency_id',
        help='Estimated monthly gross = Basic + all active earning components')

    payslip_count = fields.Integer(
        string='Payslips', compute='_compute_payslip_count')

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS — detect Odoo version contract model
    # ─────────────────────────────────────────────────────────────────────
    def _has_hr_contract(self):
        """Odoo 18 Community has hr.contract as a separate module."""
        return 'hr.contract' in self.env and hasattr(
            self.env['hr.contract'], 'wage')

    def _has_hr_version(self):
        """Odoo 19 replaces hr.contract with hr.version in base hr."""
        return 'hr.version' in self.env and hasattr(
            self.env['hr.version'], 'wage')

    # ─────────────────────────────────────────────────────────────────────
    # COMPUTED FIELDS
    # ─────────────────────────────────────────────────────────────────────
    def _compute_contract_info(self):
        """Resolve the employee's current contract and its wage.
        basic_wage is computed directly from the active contract."""
        for rec in self:
            rec.contract_id = False
            rec.contract_wage = 0.0
            rec.basic_wage = 0.0
            rec.has_active_contract = False
            if not rec.employee_id:
                continue

            if rec._has_hr_contract():
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'open'),
                ], limit=1)
                rec.contract_id = contract
                rec.contract_wage = contract.wage if contract else 0.0
                rec.basic_wage = contract.wage if contract else 0.0
                rec.has_active_contract = bool(contract)
            elif rec._has_hr_version():
                # Odoo 19: hr.version
                version = getattr(rec.employee_id, 'version_id', False)
                if not version:
                    version = self.env['hr.version'].search([
                        ('employee_id', '=', rec.employee_id.id),
                        ('active', '=', True),
                    ], limit=1, order='date_version desc')
                rec.contract_wage = version.wage if version else 0.0
                rec.basic_wage = version.wage if version else 0.0
                rec.has_active_contract = bool(version)

    @api.depends('basic_wage', 'template_id', 'template_id.component_ids',
                 'template_id.wage_type', 'template_id.working_days_per_month')
    def _compute_gross_estimate(self):
        for rec in self:
            if not rec.template_id or not rec.basic_wage:
                rec.gross_estimate = 0.0
                continue
            wt = rec.template_id.wage_type or 'monthly'
            wdpm = rec.template_id.working_days_per_month or 26
            # For daily/hourly, estimate a full month so the number is meaningful
            if wt == 'daily':
                base = rec.basic_wage * wdpm
            elif wt == 'hourly':
                base = rec.basic_wage * wdpm * 8  # assume 8 hrs/day
            else:
                base = rec.basic_wage
            gross = base
            for comp in rec.template_id.component_ids.filtered(
                    lambda c: c.active and c.component_type != 'deduction'):
                gross += comp.get_amount(base)
            rec.gross_estimate = gross

    def _compute_payslip_count(self):
        for rec in self:
            rec.payslip_count = self.env['dotbd.payslip'].search_count([
                ('salary_id', '=', rec.id),
            ])

    @api.depends('employee_id', 'template_id', 'effective_date')
    def _compute_display_name(self):
        for rec in self:
            emp = rec.employee_id.name or ''
            tmpl = rec.template_id.name or ''
            date = rec.effective_date or ''
            rec.display_name = f"{emp} – {tmpl} ({date})" if emp else '/'

    # ─────────────────────────────────────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'dotbd.employee.salary') or '/'
        return super().create(vals_list)

    @api.constrains('employee_id', 'effective_date', 'state')
    def _check_unique_active(self):
        for rec in self:
            if rec.state == 'active':
                duplicate = self.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', '=', 'active'),
                    ('id', '!=', rec.id),
                ])
                if duplicate:
                    raise ValidationError(
                        f"Employee '{rec.employee_id.name}' already has an "
                        f"active salary assignment. "
                        f"Please expire the existing one first.")

    # ─────────────────────────────────────────────────────────────────────
    # ACTIONS
    # ─────────────────────────────────────────────────────────────────────
    def action_activate(self):
        """Activate this salary assignment.
        Requires an active contract/version — raises error if none exists.
        """
        for rec in self:
            # Validate: employee must have an active contract
            if not rec.has_active_contract:
                if rec._has_hr_contract():
                    raise ValidationError(_(
                        "Employee '%s' has no active contract (Running state). "
                        "Please create a contract for this employee first "
                        "from the Contracts menu, then come back here.",
                        rec.employee_id.name))
                elif rec._has_hr_version():
                    raise ValidationError(_(
                        "Employee '%s' has no active version. "
                        "Please create a version for this employee first, "
                        "then come back here.",
                        rec.employee_id.name))
                else:
                    raise ValidationError(_(
                        "No contract module found. Please install "
                        "hr_contract (Odoo 18) or hr module (Odoo 19)."))

            # Expire siblings
            existing = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'active'),
                ('id', '!=', rec.id),
            ])
            existing.write({'state': 'expired'})

            rec.write({'state': 'active'})

    def action_expire(self):
        self.write({'state': 'expired'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ─────────────────────────────────────────────────────────────────────
    # NAVIGATION
    # ─────────────────────────────────────────────────────────────────────
    def action_view_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Payslips – {self.employee_id.name}',
            'res_model': 'dotbd.payslip',
            'view_mode': 'list,form',
            'domain': [('salary_id', '=', self.id)],
            'context': {'default_salary_id': self.id,
                        'default_employee_id': self.employee_id.id},
        }

    def action_view_contract(self):
        """Open the linked contract (v18) or employee form (v19)."""
        self.ensure_one()
        if self._has_hr_contract() and self.contract_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Contract'),
                'res_model': 'hr.contract',
                'view_mode': 'form',
                'res_id': self.contract_id.id,
            }
        elif self._has_hr_version():
            return {
                'type': 'ir.actions.act_window',
                'name': _('Employee'),
                'res_model': 'hr.employee',
                'view_mode': 'form',
                'res_id': self.employee_id.id,
            }
        raise ValidationError(_('No contract/version found for this employee.'))
