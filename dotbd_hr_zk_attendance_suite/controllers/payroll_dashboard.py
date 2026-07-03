# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited.
#    Author: Rafiur Rahman Rafit
#
################################################################################
import calendar
from datetime import date

from odoo import http
from odoo.http import request

# ── label maps ────────────────────────────────────────────────────────────────
_TYPE_LABELS = {
    'employee':     'Regular Employee',
    'student':      'Intern / Student',
    'freelance':    'Freelancer',
    'daily_labour': 'Daily Labour',
}
_WAGE_LABELS = {
    'monthly': 'Monthly',
    'daily':   'Daily',
    'hourly':  'Hourly',
    'fixed':   'Fixed Contract',
}
_STATE_LABELS = {
    'draft':     'Draft',
    'confirmed': 'Confirmed',
    'partial':   'Partial',
    'paid':      'Paid',
}


class PayrollDashboardController(http.Controller):

    def _is_payroll_manager(self):
        return request.env.user.has_group(
            'dotbd_hr_zk_attendance_suite.group_attendance_manager')

    # ── Filters endpoint ──────────────────────────────────────────────────────
    @http.route('/payroll/dashboard/filters', type='json', auth='user')
    def get_filters(self):
        env = request.env
        departments = env['hr.department'].sudo().search_read(
            [], ['id', 'name'], order='name asc')
        jobs = env['hr.job'].sudo().search_read(
            [], ['id', 'name'], order='name asc')
        templates = env['dotbd.salary.template'].sudo().search_read(
            [('active', '=', True)], ['id', 'name'], order='name asc')
        return {
            'departments': departments,
            'jobs':        jobs,
            'templates':   templates,
        }

    # ── Data endpoint ─────────────────────────────────────────────────────────
    @http.route('/payroll/dashboard/data', type='json', auth='user')
    def get_data(self, month=None, year=None,
                 department_id=None, employee_type=None,
                 wage_type=None, state_filter=None,
                 group_by='department'):
        env = request.env
        today = date.today()
        month = int(month or today.month)
        year  = int(year  or today.year)

        _, last_day = calendar.monthrange(year, month)
        date_from  = date(year, month, 1)
        date_to    = date(year, month, last_day)
        month_name = date_from.strftime('%B %Y')

        # ── Build domain ──────────────────────────────────────────────────────
        domain = [
            ('date_from', '>=', date_from),
            ('date_from', '<=', date_to),
        ]
        if department_id:
            domain.append(('department_id',  '=', int(department_id)))
        if employee_type:
            domain.append(('employee_type',  '=', employee_type))
        if wage_type:
            domain.append(('wage_type',      '=', wage_type))
        if state_filter:
            domain.append(('state',          '=', state_filter))

        Payslip  = env['dotbd.payslip'].sudo()
        payslips = Payslip.search(domain)

        # ── KPIs ─────────────────────────────────────────────────────────────
        currency        = env.company.currency_id
        total_gross     = sum(p.gross_amount    for p in payslips)
        total_deductions= sum(p.total_deductions for p in payslips)
        total_net       = sum(p.net_amount      for p in payslips)
        paid_amount     = sum(p.paid_amount     for p in payslips)
        pending_payment = sum(p.remaining_amount for p in payslips)

        # ── Status counts (always over full month, ignoring state_filter for counts) ──
        all_domain = [d for d in domain if d[0] != 'state']
        all_payslips = Payslip.search(all_domain)
        status_counts = {}
        for s in ('draft', 'confirmed', 'partial', 'paid'):
            status_counts[s] = len(all_payslips.filtered(lambda p, st=s: p.state == st))

        # ── Coverage ─────────────────────────────────────────────────────────
        sal_domain = [('state', '=', 'active')]
        if department_id:
            sal_domain.append(('department_id', '=', int(department_id)))
        if employee_type:
            sal_domain.append(('employee_type', '=', employee_type))
        active_salaries  = env['dotbd.employee.salary'].sudo().search(sal_domain)
        employees_total  = len(active_salaries)
        covered_emp_ids  = set(all_payslips.mapped('employee_id').ids)
        employees_covered = len(covered_emp_ids)
        no_payslip_count = max(employees_total - employees_covered, 0)

        # ── Alerts ────────────────────────────────────────────────────────────
        alerts = []
        if no_payslip_count:
            alerts.append({
                'type': 'warning',
                'message': f'{no_payslip_count} employee(s) with active salary have no payslip this month.',
            })
        draft_old = Payslip.search([
            ('state',     '=', 'draft'),
            ('date_from', '<', date_from),
        ], limit=10)
        if draft_old:
            alerts.append({
                'type': 'warning',
                'message': f'{len(draft_old)} payslip(s) from previous months are still in Draft.',
            })
        has_contract = ('hr.contract' in env and hasattr(env['hr.contract'], 'wage'))
        if has_contract:
            no_contract = []
            for sal in active_salaries:
                c = env['hr.contract'].sudo().search([
                    ('employee_id', '=', sal.employee_id.id),
                    ('state',       '=', 'open'),
                ], limit=1)
                if not c:
                    no_contract.append(sal.employee_id.name)
            if no_contract:
                preview = ', '.join(no_contract[:3])
                ellipsis = '…' if len(no_contract) > 3 else ''
                alerts.append({
                    'type': 'danger',
                    'message': (f'{len(no_contract)} employee(s) have no active contract: '
                                f'{preview}{ellipsis}.'),
                })

        # ── Group-By chart ────────────────────────────────────────────────────
        group_chart = self._build_group_chart(payslips, group_by)

        # ── Employee type breakdown ───────────────────────────────────────────
        type_data = {}
        for p in all_payslips:
            lbl = _TYPE_LABELS.get(p.employee_type or 'employee', p.employee_type or 'employee')
            if lbl not in type_data:
                type_data[lbl] = {'count': 0, 'net': 0.0}
            type_data[lbl]['count'] += 1
            type_data[lbl]['net']   += p.net_amount
        type_chart = [
            {'label': k, 'count': v['count'], 'net': round(v['net'], 2)}
            for k, v in type_data.items()
        ]

        # ── Wage type breakdown ───────────────────────────────────────────────
        wage_data = {}
        for p in all_payslips:
            lbl = _WAGE_LABELS.get(p.wage_type or 'monthly', p.wage_type or 'monthly')
            if lbl not in wage_data:
                wage_data[lbl] = {'count': 0, 'net': 0.0}
            wage_data[lbl]['count'] += 1
            wage_data[lbl]['net']   += p.net_amount
        wage_chart = [
            {'label': k, 'count': v['count'], 'net': round(v['net'], 2)}
            for k, v in wage_data.items()
        ]

        # ── 6-month trend ─────────────────────────────────────────────────────
        trend_chart = []
        base_trend_domain = []
        if department_id:
            base_trend_domain.append(('department_id', '=', int(department_id)))
        if employee_type:
            base_trend_domain.append(('employee_type', '=', employee_type))
        if wage_type:
            base_trend_domain.append(('wage_type', '=', wage_type))

        for i in range(5, -1, -1):
            m, y = month - i, year
            while m <= 0:
                m += 12
                y -= 1
            _, ld = calendar.monthrange(y, m)
            df = date(y, m, 1)
            dt = date(y, m, ld)
            ps = Payslip.search([
                ('date_from', '>=', df),
                ('date_from', '<=', dt),
            ] + base_trend_domain)
            trend_chart.append({
                'month': df.strftime('%b %Y'),
                'net':   round(sum(p.net_amount for p in ps), 2),
                'gross': round(sum(p.gross_amount for p in ps), 2),
                'count': len(ps),
            })

        # ── Top earners (top 5 employees by net this month) ───────────────────
        emp_net = {}
        for p in all_payslips:
            eid  = p.employee_id.id
            name = p.employee_id.name
            if eid not in emp_net:
                emp_net[eid] = {'name': name, 'net': 0.0}
            emp_net[eid]['net'] += p.net_amount
        top_earners = sorted(emp_net.values(), key=lambda x: -x['net'])[:5]

        return {
            'month_name':       month_name,
            'currency_symbol':  currency.symbol or '',
            # KPIs
            'total_gross':      round(total_gross,      2),
            'total_deductions': round(total_deductions, 2),
            'total_net':        round(total_net,        2),
            'paid_amount':      round(paid_amount,      2),
            'pending_payment':  round(pending_payment,  2),
            # Coverage
            'employees_total':   employees_total,
            'employees_covered': employees_covered,
            'no_payslip_count':  no_payslip_count,
            # Status
            'draft_count':     status_counts['draft'],
            'confirmed_count': status_counts['confirmed'],
            'partial_count':   status_counts['partial'],
            'paid_count':      status_counts['paid'],
            # Charts
            'group_chart':  group_chart,
            'type_chart':   type_chart,
            'wage_chart':   wage_chart,
            'trend_chart':  trend_chart,
            'top_earners':  top_earners,
            # Alerts
            'alerts': alerts,
        }

    def _build_group_chart(self, payslips, group_by):
        """Aggregate payslips by the selected dimension and return sorted list."""
        data = {}

        for p in payslips:
            if group_by == 'department':
                key = p.department_id.name if p.department_id else 'No Department'
            elif group_by == 'employee_type':
                key = _TYPE_LABELS.get(p.employee_type or 'employee', p.employee_type or '—')
            elif group_by == 'wage_type':
                key = _WAGE_LABELS.get(p.wage_type or 'monthly', p.wage_type or '—')
            elif group_by == 'job':
                key = p.job_id.name if p.job_id else 'No Job'
            elif group_by == 'template':
                key = p.salary_id.template_id.name if p.salary_id and p.salary_id.template_id else 'No Template'
            elif group_by == 'state':
                key = _STATE_LABELS.get(p.state, p.state)
            else:
                key = p.department_id.name if p.department_id else 'No Department'

            if key not in data:
                data[key] = {'net': 0.0, 'gross': 0.0, 'count': 0}
            data[key]['net']   += p.net_amount
            data[key]['gross'] += p.gross_amount
            data[key]['count'] += 1

        return [
            {'name': k, 'net': round(v['net'], 2),
             'gross': round(v['gross'], 2), 'count': v['count']}
            for k, v in sorted(data.items(), key=lambda x: -x[1]['net'])
        ]
