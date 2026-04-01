# -*- coding: utf-8 -*-
{
    'name': 'Econovo Quality Alert Report',
    'version': '17.0.2.1.0',
    'summary': 'PDF report and non-conformity fields for Quality Alerts (ISO)',
    'description': """
        Adds a printable PDF report to Quality Alerts and extends the model
        with structured non-conformity fields aligned to OCA mgmtsystem_nonconformity
        for future migration. Includes severity, origin, cause, and management
        system catalogs.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Manufacturing/Quality',
    'depends': [
        'quality_control',
        'hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/econovo_quality_alert_data.xml',
        'views/quality_alert_views.xml',
        'report/quality_alert_report.xml',
        'report/quality_alert_report_templates.xml',
    ],
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
