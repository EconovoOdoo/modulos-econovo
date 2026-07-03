# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models


class LateCheckIn(models.Model):
    """Model to store late check-in records with penalties"""
    _name = 'late.check.in'
    _description = 'Late Check In'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        readonly=True, string='Reference', help="Reference number of the record")
    employee_id = fields.Many2one('hr.employee', string="Employee",
                                  required=True, help='Late employee')
    late_minutes = fields.Integer(string="Late Minutes",
                                  help='The field indicates the number of '
                                       'minutes the worker is late (after tolerance).')
    actual_late_minutes = fields.Integer(string="Actual Late Minutes",
                                        help='Actual late minutes without tolerance.')
    date = fields.Date(string="Date", required=True, help='Attendance date')
    penalty_amount = fields.Float(compute="_compute_penalty_amount",
                                  help='Amount needs to be deducted',
                                  string="Penalty Amount", store=True)
    state = fields.Selection(selection=[('draft', 'Draft'),
                                        ('approved', 'Approved'),
                                        ('refused', 'Refused'),
                                        ('deducted', 'Deducted')],
                             string="State", default="draft",
                             help='State of the record')
    attendance_id = fields.Many2one('hr.attendance', string='Attendance',
                                    ondelete='cascade',
                                    help='Attendance record of the employee')
    notes = fields.Text(string="Notes", help="Additional notes or reasons")

    @api.model_create_multi
    def create(self, vals_list):
        """Create a sequence for the model"""
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'late.check.in') or '/'
        return super().create(vals_list)

    @api.depends('late_minutes')
    def _compute_penalty_amount(self):
        """Compute the penalty amount if the employee was late"""
        ICP = self.env['ir.config_parameter'].sudo()
        try:
            amount = float(ICP.get_param(
                'dotbd_hr_zk_attendance_suite.deduction_amount', default='0'))
        except (ValueError, TypeError):
            amount = 0.0
        deduction_type = ICP.get_param(
            'dotbd_hr_zk_attendance_suite.deduction_type', default='minutes')

        for rec in self:
            if deduction_type == 'minutes':
                rec.penalty_amount = amount * rec.late_minutes
            elif deduction_type == 'fixed':
                rec.penalty_amount = amount
            else:
                # Fallback: treat unknown type as fixed
                rec.penalty_amount = amount

    def action_approve(self):
        """Change state to approved when approve button clicks"""
        self.write({'state': 'approved'})

    def action_reject(self):
        """Change state refused when refuse button clicks"""
        self.write({'state': 'refused'})

    def action_reset_to_draft(self):
        """Reset to draft state"""
        self.write({'state': 'draft'})
