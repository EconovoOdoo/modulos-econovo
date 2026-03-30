# -*- coding: utf-8 -*-
{
    'name': 'Econovo Quality Alert Report',
    'version': '17.0.1.0.0',
    'summary': 'PDF report for Quality Alerts (Non-Conformity / ISO)',
    'description': """
        Adds a printable PDF report to Quality Alerts.
        Designed for ISO 9001 audit documentation of non-conformities,
        including corrective and preventive actions.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Manufacturing/Quality',
    'depends': [
        'quality_control',
    ],
    'data': [
        'report/quality_alert_report.xml',
        'report/quality_alert_report_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
