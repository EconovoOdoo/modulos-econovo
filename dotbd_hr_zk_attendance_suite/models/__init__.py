# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit

################################################################################
from . import biometric_device_details
from . import biometric_device_log
from . import biometric_log_cleanup_wizard
from . import zk_machine_attendance
from . import daily_attendance
from . import hr_employee
from . import hr_employee_public
from . import attendance_anomaly_analysis
from . import attendance_summary_analysis
from . import attendance_report_wizard
from . import late_check_in
from . import hr_attendance
from . import res_config_settings
from . import employee_attendance_sheet_wizard
from . import hr_leave_type
from . import adms_device_command
from . import dotbd_monthly_statement

# Payroll — salary templates, employee salary assignments, payslips, wizards
from . import dotbd_festive_bonus
from . import dotbd_salary_template
from . import dotbd_employee_salary
from . import dotbd_payslip
from . import dotbd_payslip_wizard
from . import dotbd_contract_wizard
from . import dotbd_salary_certificate

from . import dotbd_attendance_statement

# NOTE: hr.payslip integration is handled at runtime inside dotbd_payslip.py
# via _sync_to_hr_payroll(), which guards with 'hr.payslip' in self.env before
# touching anything. A model _inherit = 'hr.payslip' is intentionally NOT used
# here because Odoo resolves _inherit at registry build time — a try/except
# wrapper cannot prevent that crash on instances where hr_payroll is absent.
from . import res_users
from . import ir_ui_menu
