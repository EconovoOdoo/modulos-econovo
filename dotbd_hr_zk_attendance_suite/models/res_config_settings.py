# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#
################################################################################
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    """Inherit the model to add late check-in configuration fields"""
    _inherit = 'res.config.settings'

    # ── Native Payroll Integration ────────────────────────────────────────────
    enable_native_payroll = fields.Boolean(
        string='Use Native Odoo Payroll for Attendance Statements',
        config_parameter='dotbd_hr_zk_attendance_suite.enable_native_payroll',
        default=True,
        help='When enabled, the Attendance Statement wizard auto-fills salary data '
             '(wage, housing, transport, deductions, etc.) from native Odoo payroll '
             '(hr.contract / hr.payslip). Works with both Community and Enterprise. '
             'When disabled, salary data is read from our own salary assignment system.')

    native_payroll_installed = fields.Boolean(
        string='Native Payroll Installed',
        compute='_compute_native_payroll_installed', store=False)

    @api.depends('enable_native_payroll')
    def _compute_native_payroll_installed(self):
        available = 'hr.payslip' in self.env
        for rec in self:
            rec.native_payroll_installed = available

    enable_late_penalties = fields.Boolean(
        string="Enable Late Check-in Penalties",
        config_parameter='dotbd_hr_zk_attendance_suite.enable_late_penalties',
        default=True,
        help='Enable automatic tracking and penalty calculation for late check-ins')

    late_check_in_after = fields.Integer(
        config_parameter='dotbd_hr_zk_attendance_suite.late_check_in_after',
        string="Tolerance (Minutes)",
        default=0,
        help='Grace period in minutes. Employees arriving within this time are not marked as late. '
             'For example: 15 minutes means if an employee is 10 minutes late, it will not count.')

    maximum_minutes = fields.Integer(
        config_parameter='dotbd_hr_zk_attendance_suite.maximum_minutes',
        string="Maximum Late Time (Minutes)",
        default=240,
        help="Maximum time limit an employee is considered as late. "
             "Beyond this, they may be marked as absent. (Default: 240 minutes = 4 hours)")

    deduction_amount = fields.Float(
        config_parameter='dotbd_hr_zk_attendance_suite.deduction_amount',
        string="Penalty Amount",
        help='Amount to be deducted for late check-in')

    deduction_type = fields.Selection(
        selection=[('minutes', 'Per Minute'), ('fixed', 'Fixed Amount')],
        config_parameter='dotbd_hr_zk_attendance_suite.deduction_type',
        default="minutes",
        string='Penalty Type',
        help='Per Minute: Deduct specified amount for each late minute\n'
             'Fixed Amount: Deduct fixed amount per late instance')

    # IMPORTANT: Must NOT be named 'currency_id' — that name is reserved by
    # Odoo Accounting on res.config.settings as a related field to
    # company_id.currency_id.  Using the same name triggers a full accounting
    # recomputation on every Settings save, causing indefinite hangs on
    # production databases with thousands of invoices/journal entries.
    dotbd_currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        default=lambda self: self.env.company.currency_id.id)

    # ── Weekend day configuration ──────────────────────────────────────────
    # NOTE: Do NOT use config_parameter on Boolean fields — Odoo stores 'False'
    # as the string 'False' in ir.config_parameter, which is truthy when read back.
    # We handle persistence manually in get_values / set_values below.
    weekend_monday = fields.Boolean(string="Monday", default=False)
    weekend_tuesday = fields.Boolean(string="Tuesday", default=False)
    weekend_wednesday = fields.Boolean(string="Wednesday", default=False)
    weekend_thursday = fields.Boolean(string="Thursday", default=False)
    weekend_friday = fields.Boolean(string="Friday", default=True)
    weekend_saturday = fields.Boolean(string="Saturday", default=True)
    weekend_sunday = fields.Boolean(string="Sunday", default=False)

    # ── Payroll (auto payslip) ─────────────────────────────────────────────
    enable_auto_payslip = fields.Boolean(
        string='Enable Auto Monthly Payslip Generation',
        config_parameter='dotbd_hr_zk_attendance_suite.enable_auto_payslip',
        default=False,
        help='When enabled, payslips are automatically generated on the 1st of '
             'each month for all employees with an active salary assignment.')

    payslip_notify_hr = fields.Boolean(
        string='Notify HR Manager After Auto Generation',
        config_parameter='dotbd_hr_zk_attendance_suite.payslip_notify_hr',
        default=False,
        help='Send an internal message to HR managers when the auto payslip cron finishes.')

    payslip_auto_email = fields.Boolean(
        string='Auto-Email Payslip to Employee on Confirm',
        config_parameter='dotbd_hr_zk_attendance_suite.payslip_auto_email',
        default=False,
        help='When a payslip is confirmed, automatically send the PDF to the employee\'s work email.')

    # ── hr_payroll sync (bonus — when Enterprise/hr_payroll_community detected) ──
    enable_hr_payroll_sync = fields.Boolean(
        string='Sync Deductions to Odoo Payroll (if installed)',
        config_parameter='dotbd_hr_zk_attendance_suite.enable_hr_payroll_sync',
        default=False,
        help='When enabled and hr_payroll or hr_payroll_community is installed, '
             'our deduction totals are pushed to the matching hr.payslip as an input line on confirm.')

    # ── Absence Fine ───────────────────────────────────────────────────────
    enable_absence_fine = fields.Boolean(
        string='Enable Absence Fine',
        config_parameter='dotbd_hr_zk_attendance_suite.enable_absence_fine',
        default=False,
        help='When enabled, a deduction is automatically added to the payslip '
             'for each absent day (useful when Time Off module is not used).')

    absence_fine_amount = fields.Float(
        string='Absence Fine Per Day',
        config_parameter='dotbd_hr_zk_attendance_suite.absence_fine_amount',
        default=0.0,
        help='Amount deducted from the payslip per absent day. '
             'Set to 0 to calculate automatically (daily wage = basic_wage / total_working_days).')

    # ── Shift-aware auto-close (night-shift safe) ──────────────────────────
    enable_auto_close = fields.Boolean(
        string='Enable Shift-Aware Auto-Close',
        config_parameter='dotbd_hr_zk_attendance_suite.enable_auto_close',
        default=False,
        help='When enabled, the module automatically closes open check-in records '
             'whose shift has ended. Uses each employee\'s work schedule when available '
             '(night-shift safe). When disabled, stuck open records must be closed manually.')

    auto_close_checkout_offset_hours = fields.Integer(
        string='Check-Out Offset After Shift End (Hours)',
        config_parameter='dotbd_hr_zk_attendance_suite.auto_close_checkout_offset_hours',
        default=0,
        help='Hours added to the shift end when auto-closing. 0 = exact shift end '
             '(strict). Positive values (1, 2, 5, ...) give employees credit for '
             'brief overtime before the auto-close runs. Also delays the cron '
             'trigger by the same amount.')

    max_shift_hours = fields.Integer(
        string='Max Shift Length (Hours)',
        config_parameter='dotbd_hr_zk_attendance_suite.max_shift_hours',
        default=16,
        help='Fallback maximum shift length when employee has no fixed work schedule. '
             'A check-out punch within this window of the last check-in is paired as same shift. '
             'Night shifts crossing midnight need this >= 12. Default: 16 hours.')

    max_open_attendance_hours = fields.Integer(
        string='Auto-Close Open Attendance After (Hours)',
        config_parameter='dotbd_hr_zk_attendance_suite.max_open_attendance_hours',
        default=18,
        help='If a check-in has no check-out for longer than this, auto-close it at the '
             'expected shift end (or check-in + default shift hours if no schedule). '
             'Prevents stuck open records from blocking future punches. Default: 18 hours.')

    shift_hours_default = fields.Integer(
        string='Default Shift Hours',
        config_parameter='dotbd_hr_zk_attendance_suite.default_shift_hours',
        default=8,
        help='When auto-closing a stale record and no work schedule is defined, '
             'set check-out = check-in + this many hours. Default: 8 hours.')

    native_fallback_hours = fields.Integer(
        string='Native Safety Net After (Hours)',
        config_parameter='dotbd_hr_zk_attendance_suite.native_fallback_hours',
        default=36,
        help='Safety net for Odoo native Automatic Check-Out. Normally we skip '
             'records that native should handle (fixed-schedule employees in a '
             'company with auto_check_out=ON). If such a record is STILL open '
             'after this many hours past check-in — meaning native missed it '
             '(cron failure, manual edit, schedule changed mid-shift) — our '
             'module steps in and closes it using the current work schedule. '
             'Set 0 to disable the safety net and always defer to native.')

    # ── UI / Navigation preferences ───────────────────────────────────────────
    attendance_landing_page = fields.Selection(
        selection=[('dashboard', 'Dashboard'), ('overview', 'Overview')],
        string='Default Landing Page',
        config_parameter='dotbd_hr_zk_attendance_suite.attendance_landing_page',
        default='dashboard',
        help='Choose which page opens first when entering the Attendance module.\n'
             'Dashboard: our custom summary dashboard.\n'
             'Overview: Odoo\'s built-in attendance list/overview.')

    # ── Accounting detection ───────────────────────────────────────────────────
    has_accounting = fields.Boolean(
        compute='_compute_has_accounting', store=False,
        string='Has Accounting Module')

    def _compute_has_accounting(self):
        has_acc = 'account.move' in self.env
        for rec in self:
            rec.has_accounting = has_acc

    # ── Payroll Accounting (optional — unlocked when account module present) ──
    # IMPORTANT: We use Integer fields (storing record IDs) instead of Many2one
    # fields referencing account.journal / account.account. In Odoo 19, declaring
    # Many2one fields with comodels from uninstalled modules (e.g. 'account')
    # crashes the entire model registry at build time, making ALL our fields
    # (including has_accounting) "undefined" in the web client.
    # The get_values/set_values methods convert these IDs back to recordsets.
    dotbd_salary_journal_id = fields.Integer(
        string='Default Salary Journal',
        help="Record ID of the journal used to post salary entries when a payslip is confirmed.")
    dotbd_salary_expense_account_id = fields.Integer(
        string='Salary Expense Account',
        help="Record ID of the debit account for salary expense (usually a P&L expense account).")
    dotbd_salary_payable_account_id = fields.Integer(
        string='Salary Payable Account',
        help="Record ID of the credit account for net salary payable to employee.")
    dotbd_salary_deduction_account_id = fields.Integer(
        string='Deduction Payable Account',
        help="Record ID of the separate credit account for deductions (tax, fine, etc.). "
             "0 or empty = deductions combined into the Payable account.")

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()

        def _get_bool(param, default):
            val = ICP.get_param(param)
            if val is False or val is None:
                return default
            return val == 'True'

        res['weekend_monday'] = _get_bool('dotbd_hr_zk_attendance_suite.weekend_mon', False)
        res['weekend_tuesday'] = _get_bool('dotbd_hr_zk_attendance_suite.weekend_tue', False)
        res['weekend_wednesday'] = _get_bool('dotbd_hr_zk_attendance_suite.weekend_wed', False)
        res['weekend_thursday'] = _get_bool('dotbd_hr_zk_attendance_suite.weekend_thu', False)
        res['weekend_friday'] = _get_bool('dotbd_hr_zk_attendance_suite.weekend_fri', True)
        res['weekend_saturday'] = _get_bool('dotbd_hr_zk_attendance_suite.weekend_sat', True)
        res['weekend_sunday'] = _get_bool('dotbd_hr_zk_attendance_suite.weekend_sun', False)

        def _get_id(param):
            return int(ICP.get_param(param, 0) or 0) or 0

        res['dotbd_salary_journal_id'] = _get_id(
            'dotbd_hr_zk_attendance_suite.salary_journal_id')
        res['dotbd_salary_expense_account_id'] = _get_id(
            'dotbd_hr_zk_attendance_suite.salary_expense_account_id')
        res['dotbd_salary_payable_account_id'] = _get_id(
            'dotbd_hr_zk_attendance_suite.salary_payable_account_id')
        res['dotbd_salary_deduction_account_id'] = _get_id(
            'dotbd_hr_zk_attendance_suite.salary_deduction_account_id')
        return res

    def set_values(self):
        # Read current tolerance BEFORE super() writes the new value so we can
        # detect whether it changed and trigger a recompute on existing records.
        ICP_pre = self.env['ir.config_parameter'].sudo()
        _old_tolerance = int(ICP_pre.get_param(
            'dotbd_hr_zk_attendance_suite.late_check_in_after', default=0))

        # ── Validate shift-aware auto-close settings ────────────────────────
        # These durations must be strictly positive; zero/negative values
        # would make the shift window collapse and corrupt attendance data.
        if self.enable_auto_close:
            if self.max_shift_hours is not None and self.max_shift_hours < 1:
                raise ValidationError(_(
                    "Max Shift Length must be at least 1 hour."))
            if (self.max_open_attendance_hours is not None
                    and self.max_open_attendance_hours < 1):
                raise ValidationError(_(
                    "Auto-Close Open Attendance After must be at least 1 hour."))
            if (self.shift_hours_default is not None
                    and self.shift_hours_default < 1):
                raise ValidationError(_(
                    "Default Shift Hours must be at least 1 hour."))
            if (self.auto_close_checkout_offset_hours is not None
                    and self.auto_close_checkout_offset_hours < 0):
                raise ValidationError(_(
                    "Check-Out Offset cannot be negative."))
            if (self.native_fallback_hours is not None
                    and self.native_fallback_hours < 0):
                raise ValidationError(_(
                    "Native Safety Net hours cannot be negative "
                    "(use 0 to disable the safety net)."))

        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_mon', str(self.weekend_monday))
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_tue', str(self.weekend_tuesday))
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_wed', str(self.weekend_wednesday))
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_thu', str(self.weekend_thursday))
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_fri', str(self.weekend_friday))
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_sat', str(self.weekend_saturday))
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_sun', str(self.weekend_sunday))
        # Mark weekend settings as user-configured so the loaders stop applying
        # the Fri+Sat default fallback. An empty selection now means "no
        # weekends — 7-day work week".
        ICP.set_param('dotbd_hr_zk_attendance_suite.weekend_configured', 'True')
        ICP.set_param(
            'dotbd_hr_zk_attendance_suite.salary_journal_id',
            self.dotbd_salary_journal_id or 0)
        ICP.set_param(
            'dotbd_hr_zk_attendance_suite.salary_expense_account_id',
            self.dotbd_salary_expense_account_id or 0)
        ICP.set_param(
            'dotbd_hr_zk_attendance_suite.salary_payable_account_id',
            self.dotbd_salary_payable_account_id or 0)
        ICP.set_param(
            'dotbd_hr_zk_attendance_suite.salary_deduction_account_id',
            self.dotbd_salary_deduction_account_id or 0)

        # ── Recompute tolerance on existing records when setting changes ─────────
        # _compute_tolerance_late_time only depends on late_check_in (Odoo ORM
        # cannot track ir.config_parameter reads), so when the tolerance setting
        # changes we must trigger recomputation manually.
        _new_tolerance = self.late_check_in_after
        if _old_tolerance != _new_tolerance:
            late_recs = self.env['hr.attendance'].sudo().search(
                [('late_check_in', '>', 0)])
            if late_recs:
                late_recs._compute_tolerance_late_time()
                late_recs._sync_late_check_in()

        # ── Apply landing page preference by adjusting menu sequences ──────────
        # Same approach as v18: both menus are direct children of root.
        # v17: menu_hr_attendance_view_attendances (list view)
        # Our dashboard: menu_attendance_main_dashboard (same in both versions)
        # Landing = Dashboard: dashboard seq 1, overview seq 5
        # Landing = Overview:  overview seq 1, dashboard seq 10
        try:
            dashboard_menu = self.env.ref(
                'dotbd_hr_zk_attendance_suite.menu_attendance_main_dashboard')
            overview_menu = self.env.ref(
                'hr_attendance.menu_hr_attendance_view_attendances')
            if self.attendance_landing_page == 'overview':
                dashboard_menu.sudo().write({'sequence': 10})
                overview_menu.sudo().write({'sequence': 1})
            else:
                dashboard_menu.sudo().write({'sequence': 1})
                overview_menu.sudo().write({'sequence': 5})
        except Exception:
            pass


