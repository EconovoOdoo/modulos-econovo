# -*- coding: utf-8 -*-
{
    'name': 'Currency Rate Custom Providers',
    'version': '17.0.1.1.0',
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
* **Native Cron Scheduling:** Uses Odoo's standard cron fields with dedicated cron per source
* **Timezone Support:** Configure schedule in any timezone with automatic UTC conversion
* **Real-time Updates:** All fields reflect current cron state without manual sync
* **Complete Logging:** Execution history with error tracking
* **Validation:** Rate range validation and change percentage limits
* **Odoo.sh Compatible:** Works without restrictions on Odoo.sh

Configuration
-------------
1. Go to Invoicing > Configuration > Currency Rate Sources
2. Create a new source with the URL and extraction configuration
3. Test the extraction to verify it works
4. Configure schedule using standard Odoo cron fields (interval, next execution, etc.)
5. Enable automatic updates

Scheduling
----------
Each source has a dedicated scheduled action with configurable:
- Execute Every: Interval number and unit (minutes, hours, days, weeks, months)
- Next Execution Date: Schedule specific time for next run (editable)
- Number of Calls: Limit executions or set unlimited (-1)
- Priority: Control execution order (lower = higher priority)
- Execute Missed Runs: Run missed executions after server restart

All times are stored in UTC but displayed in your configured timezone for convenience.

Technical Requirements
----------------------
* Python packages: requests, lxml (included in Odoo)
* Optional: jsonpath-ng for advanced JSONPath support

Version History
---------------
v17.0.1.1.0 (2025-12-18)
  - Refactored to use native Odoo cron fields via related= pattern
  - Removed complex custom scheduling logic (~400 lines)
  - Removed currency.rate.schedule model (no longer needed)
  - Fixed tracking TypeError on auto_update field
  - Improved real-time field updates (no store on related fields)
  - Better timezone handling with dedicated display field
  - No more deadlocks during cron execution
  
v17.0.1.0.3
  - Initial stable release
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
