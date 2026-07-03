# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models, SUPERUSER_ID


# Check if hr_payroll_community is installed before defining the class
def _is_payroll_installed(env):
    """Check if hr_payroll_community module is installed"""
    return env['ir.module.module'].sudo().search([
        ('name', '=', 'hr_payroll_community'),
        ('state', '=', 'installed')
    ], limit=1)


# Only define the class if payroll module exists
try:
    # Test if hr.payslip model exists
    from odoo import registry
    from odoo.api import Environment
    import odoo

    class HrPayslip(models.Model):
        """Inherit hr.payslip to add late check-in deduction functionality"""
        _inherit = 'hr.payslip'

        late_check_in_ids = fields.Many2many(
            'late.check.in', string='Late Check-in',
            help='Late check-in records of the employee')

        @api.model
        def get_inputs(self, contracts, date_from, date_to):
            """Function used for writing late check-in record in the payslip input
             list."""
            res = super().get_inputs(contracts, date_from, date_to)

            try:
                late_check_in_type = self.env.ref(
                    'dotbd_hr_zk_attendance_suite.late_check_in_salary_rule')
            except:
                # If salary rule doesn't exist, return without adding input
                return res

            late_check_in_id = self.env['late.check.in'].search(
                [('employee_id', '=', self.employee_id.id),
                 ('date', '<=', self.date_to),
                 ('date', '>=', self.date_from),
                 ('state', '=', 'approved')])

            if late_check_in_id:
                self.late_check_in_ids = late_check_in_id
                input_data = {
                    'name': late_check_in_type.name,
                    'code': late_check_in_type.code,
                    'amount': sum(late_check_in_id.mapped('penalty_amount')),
                    'contract_id': self.contract_id.id,
                }
                res.append(input_data)
            return res

        def action_payslip_done(self):
            """Function used for marking deducted Late check-in request."""
            for rec in self.late_check_in_ids:
                rec.write({'state': 'deducted'})
            return super().action_payslip_done()

except Exception:
    # hr.payslip model doesn't exist, skip this file
    pass
