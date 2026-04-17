# -*- coding: utf-8 -*-
{
    'name': 'Econovo FSM Worksheet — Orden de Trabajo SVT-04',
    'version': '17.0.1.1.0',
    'summary': 'Worksheet template REG-SVT-04 for FSM field service tasks (Gestión Operativa)',
    'description': """
        Implements the REG-SVT-04 worksheet template for the Field Service module.
        Provides:
        - Equipment (lot_id) field on project.task for technician assignment
        - Worksheet model with operational fields (horómetro, tipo servicio, tipo falla, etc.)
        - Custom PDF report replicating the REG-SVT-04 form layout
        - Materials table from the linked sale order lines
        - Native timesheet integration for work description
        - Stored lot_id mirror on the worksheet model for pivot/Analysis grouping
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Field Service',
    'depends': [
        'industry_fsm',
        'industry_fsm_report',
        'industry_fsm_sale',
        'stock',
        'worksheet',
        'gg_lot_data',
    ],
    'data': [
        'data/worksheet_template_data.xml',
        'views/project_task_views.xml',
        'report/ir_actions_report.xml',
        'report/fsm_worksheet_svt04.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
