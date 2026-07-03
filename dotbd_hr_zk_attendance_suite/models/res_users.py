# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
#    Per-user DotBD Payroll visibility toggle.
#
#    DESIGN (compute + inverse, store=False):
#    - store=False  → no DB column, so a git-pull + restart WITHOUT -u cannot
#      crash the instance with UndefinedColumn (res_users is read every request).
#    - compute      → reflects current membership of group_dotbd_payroll_visible.
#    - inverse      → makes the toggle EDITABLE. Without an inverse a computed
#      field is rendered readonly (greyed out) in the form — the bug we hit.
#
#    WHY THE INVERSE IS SAFE NOW:
#    group_dotbd_payroll_visible is a STANDALONE group — it is not implied by
#    any other group (unlike group_payroll_access, which group_attendance_manager
#    implies). So removing a user from it STAYS removed; Odoo does not re-add it
#    via implied-group recomputation. That earlier re-add was why a prior
#    inverse approach "flipped back to ON".
#
################################################################################
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_PAYROLL_GROUP = 'dotbd_hr_zk_attendance_suite.group_dotbd_payroll_visible'


class ResUsers(models.Model):
    _inherit = 'res.users'

    dotbd_show_payroll = fields.Boolean(
        string='Show DotBD Payroll',
        compute='_compute_dotbd_show_payroll',
        inverse='_inverse_dotbd_show_payroll',
        store=False,
        help='When ON, this user can see the DotBD Payroll app (payslips, '
             'salary templates, payroll menus). When OFF, payroll is completely '
             'hidden — the user still has full attendance access.')

    @api.depends('groups_id')
    def _compute_dotbd_show_payroll(self):
        group = self.env.ref(_PAYROLL_GROUP, raise_if_not_found=False)
        for user in self:
            # sudo() so reading another user's groups_id never raises access errors
            user.dotbd_show_payroll = bool(group) and (group in user.sudo().groups_id)

    def _inverse_dotbd_show_payroll(self):
        """Add/remove the standalone payroll-visibility group when toggled.

        Safe to add or remove directly: group_dotbd_payroll_visible has no
        implied_ids and is not implied by any other group, so the change sticks.
        """
        group = self.env.ref(_PAYROLL_GROUP, raise_if_not_found=False)
        if not group:
            return
        for user in self:
            if user.dotbd_show_payroll:
                user.sudo().write({'groups_id': [(4, group.id)]})
            else:
                user.sudo().write({'groups_id': [(3, group.id)]})
