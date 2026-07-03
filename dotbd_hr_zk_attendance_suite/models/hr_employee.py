# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
################################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    """Inherit the model to add field"""
    _inherit = 'hr.employee'

    # ── Extend Odoo's built-in employee_type with labour worker ──────────────
    employee_type = fields.Selection(
        selection_add=[
            ('daily_labour', 'Daily Labour / Casual Worker'),
        ],
        ondelete={'daily_labour': 'set default'})

    device_id_num = fields.Char(string='ZK Device User ID',
                                help="Give the biometric device id")
    dotbd_payslip_count = fields.Integer(
        string='ZK Payslips', compute='_compute_dotbd_payslip_count')
    late_check_in_count = fields.Integer(
        string="Late Check-In", compute="_compute_late_check_in_count",
        help="Count of employee's late checkin")
    fp_template_count = fields.Integer(
        string='Biometrics', compute='_compute_fp_template_count',
        help='Number of biometric templates stored for this employee')

    # ── Salary / Payroll link ─────────────────────────────────────────────
    dotbd_salary_assignment_id = fields.Many2one(
        'dotbd.employee.salary', string='Active Salary Assignment',
        compute='_compute_salary_info', store=False)
    dotbd_salary_template_id = fields.Many2one(
        'dotbd.salary.template', string='Salary Template',
        compute='_compute_salary_info', store=False)
    dotbd_basic_wage = fields.Monetary(
        string='Basic Wage (Template)',
        compute='_compute_salary_info', store=False,
        currency_field='dotbd_currency_id')
    dotbd_currency_id = fields.Many2one(
        'res.currency', compute='_compute_salary_info', store=False)

    def _compute_salary_info(self):
        """Fetch salary info from the active dotbd assignment,
        but wage is pulled from the contract/version (source of truth)."""
        Salary = self.env['dotbd.employee.salary']
        has_contract = ('hr.contract' in self.env and
                        hasattr(self.env['hr.contract'], 'wage'))
        has_version = ('hr.version' in self.env and
                       hasattr(self.env['hr.version'], 'wage'))
        for emp in self:
            assignment = Salary.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'active'),
            ], limit=1)
            emp.dotbd_salary_assignment_id = assignment
            emp.dotbd_salary_template_id = assignment.template_id if assignment else False
            emp.dotbd_currency_id = (
                assignment.currency_id if assignment
                else self.env.company.currency_id)

            # Wage: contract/version is the source of truth
            wage = 0.0
            if has_contract:
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', emp.id),
                    ('state', '=', 'open'),
                ], limit=1)
                if contract:
                    wage = contract.wage
            elif has_version:
                version = getattr(emp, 'version_id', False)
                if not version:
                    version = self.env['hr.version'].search([
                        ('employee_id', '=', emp.id),
                        ('active', '=', True),
                    ], limit=1, order='date_version desc')
                if version:
                    wage = version.wage
            # Fallback to assignment basic_wage if no contract
            if not wage and assignment:
                wage = assignment.basic_wage
            emp.dotbd_basic_wage = wage

    _sql_constraints = [
        ('device_id_num_unique', 'unique(device_id_num, company_id)', 
         'The ZK Device User ID must be unique per company! Duplicate IDs lead to cross-assigned attendance.')
    ]

    def _compute_dotbd_payslip_count(self):
        for rec in self:
            rec.dotbd_payslip_count = self.env['dotbd.payslip'].search_count([
                ('employee_id', '=', rec.id),
            ])

    def action_view_dotbd_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payslips'),
            'res_model': 'dotbd.payslip',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def _compute_fp_template_count(self):
        """Compute fingerprint template count"""
        for rec in self:
            rec.fp_template_count = self.env['biometric.fp.template'].search_count(
                [('employee_id', '=', rec.id)])

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
            'limit': 80}

    def _compute_late_check_in_count(self):
        """Compute the late check-in count"""
        for rec in self:
            rec.late_check_in_count = self.env['late.check.in'].search_count(
                [('employee_id', '=', rec.id)])

    def action_view_fp_templates(self):
        """View fingerprint templates for this employee."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fingerprint Templates'),
            'res_model': 'biometric.fp.template',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_enroll_fingerprint(self):
        """Trigger fingerprint enrollment on an ADMS device.
        User selects which device and finger to enroll on."""
        self.ensure_one()
        if not self.device_id_num:
            raise UserError(_(
                'Please set the ZK Device User ID first before enrolling fingerprint.'))

        # Find ADMS/hybrid devices
        adms_devices = self.env['biometric.device.details'].search([
            ('connection_mode', 'in', ['adms', 'hybrid']),
        ])
        if not adms_devices:
            raise UserError(_(
                'No ADMS or Hybrid devices configured. '
                'Fingerprint enrollment from Odoo requires a device in Cloud (ADMS) or Hybrid mode.'))

        # Open enrollment wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Enroll Fingerprint'),
            'res_model': 'adms.device.command',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_command_type': 'enroll_fp',
                'default_employee_id': self.id,
                'default_device_id': adms_devices[0].id if len(adms_devices) == 1 else False,
            },
        }

    def _dotbd_mandatory_dates(self, date_from, date_to):
        """Return the set of dates in [date_from, date_to] on which THIS employee
        must work per Odoo's Mandatory Days (``hr.leave.mandatory.day``), scoped
        by company → department → working schedule.

        A mandatory day overrides a normal off-day / weekend: on such a date the
        employee is expected to work, so reports treat it as a working day
        (absence counts as Absent and it is excluded from the weekend tally).
        Public holidays still take precedence and are handled separately.
        Returns an empty set when hr_holidays is not installed.
        """
        from datetime import timedelta
        self.ensure_one()
        if 'hr.leave.mandatory.day' not in self.env:
            return set()
        md_recs = self.env['hr.leave.mandatory.day'].sudo().search([
            ('start_date', '<=', date_to),
            ('end_date', '>=', date_from),
        ])
        if not md_recs:
            return set()
        cal = (getattr(self, 'resource_calendar_id', None)
               or getattr(self.company_id, 'resource_calendar_id', None))
        cal_id = cal.id if cal else False
        dept_id = self.department_id.id
        company_id = self.company_id.id
        result = set()
        for md in md_recs:
            # Scope: company must match; if departments/calendar are set on the
            # mandatory day, the employee must fall within that scope.
            if md.company_id.id and md.company_id.id != company_id:
                continue
            if md.department_ids and dept_id not in md.department_ids.ids:
                continue
            if md.resource_calendar_id and md.resource_calendar_id.id != cal_id:
                continue
            dd = md.start_date if md.start_date >= date_from else date_from
            end = md.end_date if md.end_date <= date_to else date_to
            while dd <= end:
                result.add(dd)
                dd += timedelta(days=1)
        return result

    @api.model
    def _dotbd_company_weekend_config(self):
        """Read the module Weekend Days settings once.

        Returns ``(weekend_days, weekend_configured)`` where ``weekend_days`` is
        the set of weekday ints (0=Mon … 6=Sun) ticked as weekend, and
        ``weekend_configured`` is True once the settings have been saved at least
        once (so an all-unchecked save means a real 7-day work week).
        """
        ICP = self.env['ir.config_parameter'].sudo()
        codes = {0: 'mon', 1: 'tue', 2: 'wed', 3: 'thu', 4: 'fri', 5: 'sat', 6: 'sun'}
        weekend_days = {
            n for n, c in codes.items()
            if ICP.get_param('dotbd_hr_zk_attendance_suite.weekend_%s' % c, 'False')
            in ('True', '1', 'true')
        }
        weekend_configured = bool(ICP.search(
            [('key', '=', 'dotbd_hr_zk_attendance_suite.weekend_fri')], limit=1))
        return weekend_days, weekend_configured

    def _dotbd_weekend_weekdays(self, weekend_days=None, weekend_configured=None):
        """Return the set of weekday integers (0=Mon … 6=Sun) that are OFF
        (non-working) for THIS employee. Single source of truth for weekend /
        off-day detection across the dashboard, statements, payslip and exports.

        Precedence (company policy with per-employee override):
          1. The employee's OWN working schedule — a ``resource_calendar_id`` that
             is set AND differs from the company's default calendar. Off-days are
             the weekdays with no attendance line. This lets employees in the same
             company have different days off.
          2. The company weekend policy (module Settings → Weekend Days). Once it
             has been saved (``weekend_configured``) it is authoritative — an empty
             set means a 7-day work week (no weekend at all). This takes priority
             over the default company calendar so unchecking every box really does
             give a 7-day week.
          3. Fallback: Friday + Saturday when nothing has ever been configured.

        Pass ``weekend_days`` / ``weekend_configured`` (from
        ``_dotbd_company_weekend_config``) to avoid re-reading the config for
        every employee; when omitted they are read on demand.
        """
        self.ensure_one()
        if weekend_days is None or weekend_configured is None:
            weekend_days, weekend_configured = self._dotbd_company_weekend_config()
        emp_cal = getattr(self, 'resource_calendar_id', None)
        company_cal = getattr(self.company_id, 'resource_calendar_id', None)
        if emp_cal and emp_cal != company_cal and emp_cal.attendance_ids:
            working = {int(line.dayofweek) for line in emp_cal.attendance_ids}
            return set(range(7)) - working
        if weekend_configured:
            return set(weekend_days)
        return set(weekend_days) if weekend_days else {4, 5}

