# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'PCP',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'sequence': 5,
    'summary': 'Planeamiento y Control de Produccion: seguimiento de avance por Plan de Produccion',
    'description': """
PCP - Planeamiento y Control de Produccion
============================================

Extiende el modelo ``mrp.plan`` (provisto por ``gg_automatic_mrp_schedule``) con prioridad,
fechas objetivo y compania, agrega un motivo de fabricacion por Orden de Fabricacion, y provee
un dashboard nativo de Odoo (OWL) para el seguimiento de avance de produccion agrupado por Plan
y por proceso/operacion.

Key Features
------------
* Catalogo editable de Prioridades (``pcp.priority``) y Motivos de Fabricacion (``pcp.reason``),
  mismo patron que ``crm.lost.reason``.
* Prioridad heredada del Plan hacia sus Ordenes de Fabricacion y Ordenes de Trabajo.
* Motivo de fabricacion especificado por Orden de Fabricacion (no en el Plan ni en la OT).
* Archivado nativo de Planes (campo ``active``).
* Dashboard de avance agrupado por Plan x Proceso (componente OWL, mismo patron arquitectonico
  que ``dotbd_hr_zk_attendance_suite``: ``ir.actions.client`` + controller JSON).
* Acceso de Operario restringido por ``mrp.workcenter.employee_ids`` (Empleados permitidos),
  sin necesidad de dar de alta usuarios nuevos.
* Reporte de avance en XLSX (``report_xlsx``).
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp',
        'mrp_workorder',
        'gg_automatic_mrp_schedule',
        'report_xlsx',
    ],
    'data': [
        'security/pcp_security.xml',
        'security/ir.model.access.csv',
        'security/mrp_workorder_security.xml',
        'data/pcp_priority_data.xml',
        'data/pcp_reason_data.xml',
        'views/pcp_priority_views.xml',
        'views/pcp_reason_views.xml',
        'views/mrp_plan_views.xml',
        'views/mrp_production_views.xml',
        'views/pcp_menus.xml',
        'report/report_plan_progress_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_mrp_pcp/static/src/pcp_dashboard.js',
            'econovo_mrp_pcp/static/src/pcp_dashboard.xml',
            'econovo_mrp_pcp/static/src/pcp_dashboard.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
