# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
#    Force-hide DotBD Payroll menus when the user toggles them off.
#
#    WHY THIS IS NEEDED:
#    Odoo's group-based menu visibility (`groups="..."` on <menuitem>) is
#    bypassed for admin users (base.group_system). So even when the admin
#    un-ticks "Show DotBD Payroll" and we remove group_dotbd_payroll_visible,
#    the menus remain visible because admin sees everything.
#
#    This override intercepts _visible_menu_ids() — the actual method Odoo
#    calls to decide which menus to show — and removes all DotBD Payroll
#    menu IDs when the user lacks group_dotbd_payroll_visible.
#
################################################################################
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

_PAYROLL_GROUP = 'dotbd_hr_zk_attendance_suite.group_dotbd_payroll_visible'

# All DotBD Payroll menu xmlids that should be hidden when toggle is OFF
_PAYROLL_MENU_XMLIDS = [
    'dotbd_hr_zk_attendance_suite.menu_dotbd_payroll_app_root',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_payroll_dashboard',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_payroll_payslips',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_generate_payslips',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_payslip_batches',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_payslips',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_salary_certificates',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_payroll_salary',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_salary_assignments',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_bulk_salary_assign',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_payroll_config',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_salary_templates',
    'dotbd_hr_zk_attendance_suite.menu_dotbd_festive_bonus',
]


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        """Override to force-hide DotBD Payroll menus when toggle is OFF.

        This runs AFTER Odoo's default visibility check (which lets admins
        see everything), so we can subtract our payroll menus even for
        base.group_system users.
        """
        visible = super()._visible_menu_ids(debug=debug)

        # Check if the current user has the payroll visibility group
        group = self.env.ref(_PAYROLL_GROUP, raise_if_not_found=False)
        if not group:
            return visible  # group not installed yet — don't break

        user = self.env.user
        has_payroll = group in user.sudo().groups_id

        if not has_payroll:
            # Collect all payroll menu IDs to remove
            menu_ids_to_hide = set()
            for xmlid in _PAYROLL_MENU_XMLIDS:
                menu = self.env.ref(xmlid, raise_if_not_found=False)
                if menu:
                    menu_ids_to_hide.add(menu.id)

            if menu_ids_to_hide:
                visible -= menu_ids_to_hide

        return visible
