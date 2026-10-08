# -*- coding: utf-8 -*-
{
    'name': 'Sunu Login Log — User Connection Tracker & Geolocation',
    'version': '17.0.1.0.0',
    'category': 'Technical/Security',
    'summary': 'Track every Odoo login: IP address, GPS geolocation, city, country, browser, device type — with Google Maps link. Free.',
    'description': """
Sunu Login Log — User Connection Tracker for Odoo 17
=====================================================

Know exactly WHO connects to your Odoo, FROM WHERE and WITH WHAT device.
Every login is automatically recorded with full geolocation and device details.

Key Features
------------
* Automatic login recording on every successful authentication
* IP address capture
* GPS geolocation — latitude & longitude via IP (no API key needed)
* City & country detection
* Direct Google Maps link for each login location
* Browser detection (Chrome, Firefox, Safari, Edge...)
* Operating system detection (Windows, macOS, Linux, Android, iOS...)
* Device type detection (Desktop, Mobile, Tablet, Bot)
* Session ID tracking
* Admin login flag
* Company, language & timezone context
* Read-only audit log — records cannot be modified

Ideal For
---------
* Security-conscious organizations
* Administrators needing full traceability
* Compliance and audit requirements
* Detecting suspicious or unauthorized access
* Multi-company Odoo deployments

Free & Open Source
------------------
This module is completely free. No API key required.
Geolocation uses the free ip-api.com service (no account needed).

Developed by XARELAM — https://xarelam.com/
    """,

    'author': 'XARELAM',
    'website': 'https://xarelam.com/',
    'maintainers': ['xarelam'],
    'support': 'support@xarelam.com',
    'license': 'LGPL-3',
    'price': 0.0,
    'currency': 'EUR',

    'depends': ['base', 'web'],

    'data': [
        'security/sunu_login_log_groups.xml',
        'security/ir.model.access.csv',
        'views/login_log_views.xml',
    ],

    'images': ['static/description/banner.png'],

    'installable': True,
    'application': True,
    'auto_install': False,

    'external_dependencies': {
        'python': ['user_agents'],
    },
}
