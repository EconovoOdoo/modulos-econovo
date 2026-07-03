# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import fields, models, _


class HrEmployeePublic(models.Model):
    """Inherit hr.employee.public to add late check-in functionality"""
    _inherit = 'hr.employee.public'

    device_id_num = fields.Char(string='ZK Device User ID')

    late_check_in_count = fields.Integer(
        string="Late Check-In", compute="_compute_late_check_in_count",
        help="Count of employee's late checkin")

    def action_to_open_late_check_in_records(self):
        """
            :return: dictionary defining the action to open the late check-in
            records window.
            :rtype: dict
        """
        return {
            'name': _('Employee Late Check-in'),
            'domain': [('employee_id', '=', self.id)],
            'res_model': 'late.check.in',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'limit': 80,
        }

    def _compute_late_check_in_count(self):
        """Compute the late check-in count"""
        for rec in self:
            rec.late_check_in_count = self.env['late.check.in'].search_count(
                [('employee_id', '=', rec.id)])
