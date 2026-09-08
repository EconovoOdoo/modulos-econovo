# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.http import request

# Same saw/folding unification rule as the original React app's constants/procesos.ts
SAW_PROCESSES = {'CORTE PERFILES', 'CORTE SIERRA RECTO', 'CORTE SIERRA ANGULO', 'CORTE SIERRA'}
FOLDING_PROCESSES = {'PLEGADO', 'PLEGADO C-CUCHILLA'}
VALID_STATES = ['done', 'waiting', 'ready', 'pending', 'progress']
DISPLAY_PROCESSES = [
    'CORTE PERFILES', 'MECANIZADO', 'CORTE GUILLOTINA', 'CORTE LASER',
    'PLEGADO', 'CORTE PANTOGRAFO', 'ROLADO', 'SOLDADURA',
]


def _display_process(name):
    clean_name = (name or '').strip().upper()
    if clean_name in SAW_PROCESSES:
        return 'CORTE PERFILES'
    if clean_name in FOLDING_PROCESSES:
        return 'PLEGADO'
    return clean_name


class PcpDashboardController(http.Controller):

    def _is_pcp_manager(self):
        return request.env.user.has_group('econovo_mrp_pcp.group_pcp_manager')

    @http.route('/pcp/dashboard/filters', type='json', auth='user')
    def get_filters(self):
        # mrp.workorder read is already scoped by the module's own ir.rule for
        # non-managers, so no extra access logic is needed here.
        workorders = request.env['mrp.workorder'].search_read(
            [('state', 'in', VALID_STATES)], ['name'])
        present_processes = {_display_process(wo['name']) for wo in workorders}
        processes = [p for p in DISPLAY_PROCESSES if p in present_processes]
        priorities = request.env['pcp.priority'].search_read([], ['id', 'name'])
        reasons = request.env['pcp.reason'].search_read([], ['id', 'name'])
        return {
            'processes': processes,
            'priorities': priorities,
            'reasons': reasons,
            'is_manager': self._is_pcp_manager(),
        }

    @http.route('/pcp/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, include_archived=False):
        domain = [('state', 'in', VALID_STATES)]
        if not include_archived:
            domain += ['|', ('plan_id', '=', False), ('plan_active', '=', True)]

        workorders = request.env['mrp.workorder'].search_read(
            domain,
            ['name', 'qty_produced', 'qty_production', 'plan_id', 'plan_priority_id', 'plan_active'],
        )

        plans = {}
        for wo in workorders:
            plan = wo['plan_id']
            plan_key = plan[0] if plan else 0
            if plan_key not in plans:
                priority = wo['plan_priority_id']
                plans[plan_key] = {
                    'plan_id': plan_key,
                    'plan_name': plan[1] if plan else 'Sin Plan Asignado',
                    'priority_id': priority[0] if priority else False,
                    'priority': priority[1] if priority else False,
                    'active': wo['plan_active'] if plan else True,
                    'qty_production': 0.0,
                    'qty_produced': 0.0,
                    'by_process': {},
                }
            row = plans[plan_key]
            row['qty_production'] += wo['qty_production'] or 0.0
            row['qty_produced'] += wo['qty_produced'] or 0.0

            process = _display_process(wo['name'])
            process_stats = row['by_process'].setdefault(
                process, {'qty_production': 0.0, 'qty_produced': 0.0})
            process_stats['qty_production'] += wo['qty_production'] or 0.0
            process_stats['qty_produced'] += wo['qty_produced'] or 0.0

        result = []
        for row in plans.values():
            row['progress'] = (
                round(row['qty_produced'] / row['qty_production'] * 100, 1)
                if row['qty_production'] else 0.0
            )
            for stats in row['by_process'].values():
                stats['progress'] = (
                    round(stats['qty_produced'] / stats['qty_production'] * 100, 1)
                    if stats['qty_production'] else 0.0
                )
            result.append(row)

        return {
            'plans': result,
            'display_processes': DISPLAY_PROCESSES,
        }
