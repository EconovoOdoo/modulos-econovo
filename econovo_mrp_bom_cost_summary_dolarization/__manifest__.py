# -*- coding: utf-8 -*-
{
    'name': 'Econovo - BOM Cost Summary (Dolarization)',
    'version': '17.0.1.0.0',
    'category': 'Manufacturing',
    'summary': (
        'Bridge module: adds direct-USD columns (from standard_price_usd) '
        'to the BOM Cost Summary and hides exchange-rate USD columns to '
        'developer mode only.'
    ),
    'description': """
Bridge module that extends econovo_mrp_bom_cost_summary when
gg_cost_dolarization is also installed.

This module installs automatically when both:
- econovo_mrp_bom_cost_summary
- gg_cost_dolarization
are installed.

New columns added to BOM Cost Summary:
- BoM Cost USD (direct): quantity × product.standard_price_usd  (components)
- Product Cost USD (direct): quantity × product.standard_price_usd  (components)
- BoM Cost USD (direct): (duration ÷ 60) × workcenter.costs_hour_usd  (operations)

New field on mrp.workcenter:
- costs_hour_usd: direct USD hourly rate, auto-updated from exchange rate
  when costs_hour (ARS) is saved; can be manually overridden.

Existing exchange-rate USD columns are hidden behind developer mode to
avoid confusion between the two different USD calculation methods.

USD column order per section:
  Components: BoM Cost ARS | BoM Cost USD direct | BoM Cost USD (TC, devmode)
              | Product Cost ARS | Product Cost USD direct | Product Cost USD (TC, devmode)
  Operations: BoM Cost ARS | BoM Cost USD direct | BoM Cost USD (TC, devmode)
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'econovo_mrp_bom_cost_summary',
        'gg_cost_dolarization',
    ],
    'data': [
        'views/mrp_workcenter_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_mrp_bom_cost_summary_dolarization/static/src/**/*.js',
            'econovo_mrp_bom_cost_summary_dolarization/static/src/**/*.xml',
        ],
    },
    'auto_install': True,
    'installable': True,
    'application': False,
}
