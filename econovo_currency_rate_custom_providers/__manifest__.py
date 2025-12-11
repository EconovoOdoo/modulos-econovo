# -*- coding: utf-8 -*-
{
    'name': 'Currency Rate Custom Providers',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Automatically update currency rates from custom api/web sources',
    'description': """
Currency Rate Custom Providers
==============================

This module allows you to automatically update currency exchange rates from any 
web source using multiple extraction methods.

Features
--------
* **Agnostic Design:** Works for any country, currency, or asset (USD, EUR, Bitcoin, Gold, etc.)
* **Multiple Extraction Methods:**
    - Automatic detection
    - Regular Expressions (Regex)
    - XPath selectors
    - JSONPath expressions
    - CSS Selectors
* **Multi-company Support:** Updates rates for all or selected companies
* **Flexible Scheduling:** Configure execution times and days with dedicated cron per source
* **Complete Logging:** Execution history with error tracking
* **Validation:** Rate range validation and change percentage limits
* **Odoo.sh Compatible:** Works without restrictions on Odoo.sh

Configuration
-------------
1. Go to Invoicing > Configuration > Currency Rate Sources
2. Create a new source with the URL and extraction configuration
3. Test the extraction to verify it works
4. Enable automatic updates

Technical Requirements
----------------------
* Python packages: requests, lxml (included in Odoo)
* Optional: jsonpath-ng for advanced JSONPath support
    """,
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'account',
        'mail',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        'views/currency_rate_source_views.xml',
        'views/currency_rate_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
        'wizards/test_extraction_wizard_views.xml',
        'data/ir_cron_data.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'assets': {},
}
