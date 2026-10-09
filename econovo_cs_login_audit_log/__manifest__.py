# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Econovo Login Audit Compatibility',
    'summary': 'Keep login auditing compatible with non-interactive RPC checks',
    'description': """
Econovo Login Audit Compatibility
=================================

Keeps credential checks compatible with requestless RPC calls while preserving
the complete Odoo method chain. Successful browser logins are audited from HTTP
controllers where request metadata is available.
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'category': 'Administration',
    'version': '17.0.1.0.1',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'web',
        'cs_login_audit_log',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}