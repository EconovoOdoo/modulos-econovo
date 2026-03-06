# -*- coding: utf-8 -*-
{
    'name': 'Econovo - Domain Filter: Starts/Ends With Operator',
    'version': '17.0.1.0.0',
    'category': 'Web',
    'summary': (
        'Adds "starts / ends with (use %)" and "does not start / end with (use %)" '
        'operators to the custom filter dialog for char, text and html fields. '
        'These operators correspond to the Odoo =ilike domain operator.'
    ),
    'description': """
Odoo 17 exposes the =ilike domain operator on the server side (see TERM_OPERATORS
in odoo/osv/expression.py) but the "Add custom filter" dialog only lists "contains"
(ilike) and "does not contain" (not ilike) for text fields.

This module patches DomainSelector.prototype.getOperatorEditorInfo so that the
dropdown for char / text / html fields also shows:

  - "empieza / termina con (usar %)"   → =ilike  negate=false
  - "no empieza / termina con (usar %)" → =ilike  negate=true   (= ["!", (..., "=ilike", ...)])

The user provides the pattern manually, e.g. "4%" for "starts with 4",
"%GT" for "ends with GT", or "4%" for an exact starts-with match.

Usage examples:
  [("default_code", "=ilike", "4%")]    -- internal ref starts with 4
  [("default_code", "=ilike", "%GT")]   -- internal ref ends with GT
  [("name",         "=ilike", "A%")]    -- product name starts with A

This is a pure JavaScript patch — no server-side changes, no new models.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'econovo_web_domain_filter_operators/static/src/**/*.js',
        ],
    },
    'auto_install': False,
    'installable': True,
    'application': False,
}
