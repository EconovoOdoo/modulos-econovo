# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
import calendar
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class DotbdPayslipGeneratorWizard(models.TransientModel):
    """Wizard to generate payslips for a selected month/year."""
    _name = 'dotbd.payslip.generator.wizard'
    _description = 'Payslip Generator Wizard'

    # ── Period ────────────────────────────────────────────────────────────────
    month = fields.Selection([
        ('1',  'January'),   ('2',  'February'), ('3',  'March'),
        ('4',  'April'),     ('5',  'May'),       ('6',  'June'),
        ('7',  'July'),      ('8',  'August'),    ('9',  'September'),
        ('10', 'October'),   ('11', 'November'),  ('12', 'December'),
    ], string='Month', required=True,
        default=lambda self: str(
            (fields.Date.today().replace(day=1) - timedelta(days=1)).month
        ))
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: (
            fields.Date.today().replace(day=1) - timedelta(days=1)
        ).year)

    # ── Employee filter ───────────────────────────────────────────────────────
    employee_ids = fields.Many2many(
        'hr.employee', string='Employees',
        help='Leave empty to generate for all employees with an active salary.')
    department_id = fields.Many2one(
        'hr.department', string='Department',
        help='Filter by department (applied only when Employees field is empty).')

    # ── Override template ─────────────────────────────────────────────────────
    template_id = fields.Many2one(
        'dotbd.salary.template', string='Override Template',
        help='Leave empty to use each employee\'s assigned template.')

    # ── Batch name ────────────────────────────────────────────────────────────
    batch_name = fields.Char(
        string='Batch Name',
        compute='_compute_batch_name', store=False)

    @api.depends('month', 'year')
    def _compute_batch_name(self):
        for rec in self:
            if rec.month and rec.year:
                month_name = dict(rec._fields['month'].selection)[rec.month]
                rec.batch_name = f'Payroll – {month_name} {rec.year}'
            else:
                rec.batch_name = ''

    # ── Preview counts ────────────────────────────────────────────────────────
    employee_count = fields.Integer(
        string='Employees to Process',
        compute='_compute_employee_count')

    @api.depends('employee_ids', 'department_id')
    def _compute_employee_count(self):
        for rec in self:
            rec.employee_count = len(rec._get_target_assignments())

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_date_range(self):
        month = int(self.month)
        year = self.year
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    def _get_target_assignments(self):
        domain = [('state', '=', 'active')]
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        elif self.department_id:
            domain.append(
                ('employee_id.department_id', '=', self.department_id.id))
        return self.env['dotbd.employee.salary'].search(domain)

    # ── Main action ───────────────────────────────────────────────────────────
    def action_generate(self):
        self.ensure_one()

        assignments = self._get_target_assignments()
        if not assignments:
            raise UserError(
                'No active salary assignments found for the selected filter. '
                'Please assign and activate a salary for the target employees first.')

        date_from, date_to = self._get_date_range()
        month_name = dict(self._fields['month'].selection)[self.month]
        label = f'Payroll – {month_name} {self.year}'

        # Create batch
        batch = self.env['dotbd.payslip.batch'].create({
            'name': label,
            'date_from': date_from,
            'date_to': date_to,
        })

        Payslip = self.env['dotbd.payslip']
        # Pass template_override directly — no DB mutation needed
        template_override = self.template_id or False
        generated, skipped, errors = 0, 0, []

        for assignment in assignments:
            try:
                result = Payslip.generate_for_employee(
                    employee=assignment.employee_id,
                    date_from=date_from,
                    date_to=date_to,
                    salary=assignment,
                    batch=batch,
                    template_override=template_override,
                )
                if result:
                    generated += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"{assignment.employee_id.name}: {e}")

        # Post result message on batch
        msg = (f"<b>Manual generation complete:</b><br/>"
               f"{generated} payslip(s) generated, {skipped} skipped.")
        if errors:
            msg += ("<br/><span style='color:red;'>Errors:<br/>"
                    + '<br/>'.join(errors) + '</span>')
        batch.message_post(body=msg)

        # Return action to view the batch
        return {
            'type': 'ir.actions.act_window',
            'name': label,
            'res_model': 'dotbd.payslip.batch',
            'res_id': batch.id,
            'view_mode': 'form',
            'target': 'current',
        }
