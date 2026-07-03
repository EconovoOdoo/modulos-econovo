# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models
from odoo.exceptions import UserError


class DotbdContractWizard(models.TransientModel):
    """
    Bulk salary assignment wizard.

    Always creates dotbd.employee.salary records (our payroll).
    If hr.contract is available (Enterprise), also creates an hr.contract.
    """
    _name = 'dotbd.contract.wizard'
    _description = 'Bulk Salary Assignment Wizard'

    # ── Employee selection ────────────────────────────────────────────────────
    employee_ids = fields.Many2many(
        'hr.employee', string='Employees',
        required=True,
        help='Select one or more employees to assign the salary template to.')
    department_id = fields.Many2one(
        'hr.department', string='Department',
        help='Quick-fill: adds all employees in this department to the list.')

    # ── Salary ────────────────────────────────────────────────────────────────
    template_id = fields.Many2one(
        'dotbd.salary.template', string='Salary Template',
        required=True)
    basic_wage = fields.Monetary(
        string='Basic Wage', required=True,
        currency_field='currency_id',
        help='Monthly basic wage applied to all selected employees.')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id)
    effective_date = fields.Date(
        string='Effective From', required=True,
        default=fields.Date.today)

    # ── hr.contract options (enterprise only) ─────────────────────────────────
    also_create_contract = fields.Boolean(
        string='Also Create HR Contract',
        compute='_compute_also_create_contract',
        store=False,
        help='Shown only when hr.contract is available (Enterprise/hr_payroll).')
    create_hr_contract = fields.Boolean(
        string='Create HR Contract',
        default=False,
        help='When enabled, also creates an hr.contract record for each employee.')
    contract_date_end = fields.Date(
        string='Contract End Date',
        help='Leave empty for open-ended contracts.')

    @api.depends()
    def _compute_also_create_contract(self):
        has_contract = 'hr.contract' in self.env
        for rec in self:
            rec.also_create_contract = has_contract

    # ── Helpers ───────────────────────────────────────────────────────────────
    def action_add_department_employees(self):
        """Add all employees from the selected department to employee_ids."""
        self.ensure_one()
        if not self.department_id:
            return
        employees = self.env['hr.employee'].search([
            ('department_id', '=', self.department_id.id),
            ('active', '=', True),
        ])
        self.employee_ids = [(4, emp.id) for emp in employees]
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # ── Summary ───────────────────────────────────────────────────────────────
    employee_count = fields.Integer(
        string='Employees Selected',
        compute='_compute_employee_count')

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec.employee_ids)

    # ── Main action ───────────────────────────────────────────────────────────
    def action_assign(self):
        self.ensure_one()

        if not self.employee_ids:
            raise UserError('Please select at least one employee.')

        SalaryAssignment = self.env['dotbd.employee.salary']
        created, skipped = [], []

        for employee in self.employee_ids:
            # Expire any existing active assignment
            existing_active = SalaryAssignment.search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'active'),
            ])
            if existing_active:
                existing_active.write({'state': 'expired'})

            # Create new active salary assignment
            assignment = SalaryAssignment.create({
                'employee_id': employee.id,
                'template_id': self.template_id.id,
                'basic_wage': self.basic_wage,
                'currency_id': self.currency_id.id,
                'effective_date': self.effective_date,
                'state': 'active',
            })
            created.append(assignment.id)

            # Also create hr.contract if requested and model exists
            if self.create_hr_contract and 'hr.contract' in self.env:
                self._create_hr_contract(employee)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Salary Assignments',
            'res_model': 'dotbd.employee.salary',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created)],
        }

    def _create_hr_contract(self, employee):
        """Create an hr.contract for the employee (Enterprise only)."""
        Contract = self.env['hr.contract']
        # Check for existing open contract to avoid duplicates
        existing = Contract.search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ['draft', 'open']),
        ], limit=1)
        if existing:
            # Update wage instead of creating duplicate
            existing.write({'wage': self.basic_wage})
            return

        vals = {
            'name': f"{employee.name} – {self.template_id.name}",
            'employee_id': employee.id,
            'wage': self.basic_wage,
            'date_start': self.effective_date,
        }
        if self.contract_date_end:
            vals['date_end'] = self.contract_date_end

        # structure_type_id may be required on some versions — use default if available.
        # Guard both the field existence AND the model existence: the model only
        # exists when Enterprise hr_payroll (or hr_payroll_community) is installed.
        if (hasattr(Contract, 'structure_type_id')
                and 'hr.payroll.structure.type' in self.env):
            default_struct = self.env['hr.payroll.structure.type'].search(
                [], limit=1)
            if default_struct:
                vals['structure_type_id'] = default_struct.id

        Contract.create(vals)
