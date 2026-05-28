{
    'name': 'Econovo Website Field Blacklist Manager',
    'version': '17.0.1.0.0',
    'summary': 'Whitelist model fields so they become available in the Website Form Builder',
    'description': """
Econovo Website Field Blacklist Manager
========================================

By default Odoo hides many model fields from the Website Form Builder using the
``website_form_blacklisted=True`` attribute set in the Python field definition.
Changing this attribute from the UI is not allowed: writing it directly on
``ir.model.fields`` raises:

    "Las propiedades de los campos base no se pueden modificar de esta forma.
     Modifiquelas mediante codigo Python, de preferencia a traves de un modulo
     personalizado."

This module exposes a configuration screen under *Website > Configuration* that
lets an administrator pick the model + field pairs to whitelist. The change is
applied to the live registry and re-applied on every worker startup via
``_register_hook``, so it survives restarts and module updates.
""",
    'category': 'Website/Website',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'website',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/website_form_field_whitelist_views.xml',
    ],
    'installable': True,
    'application': False,
}
