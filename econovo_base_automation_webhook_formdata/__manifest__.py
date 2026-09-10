# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Automation Webhook - Form-Encoded Payload Support',
    'version': '17.0.1.0.0',
    'summary': "Let base.automation 'On Webhook' rules also read classic form-encoded POST bodies, not only JSON.",
    'description': '''
Extends the "On Webhook" trigger of Automation Rules (base.automation) so it
also understands a classic `application/x-www-form-urlencoded` request body,
not only JSON.

Problem it solves
------------------
Odoo's own webhook endpoint (`/web/hook/<uuid>`) only tries to parse the
request body as JSON; if that fails it falls back to the URL query string
only, never to a POSTed form body. Many no-code website form builders (for
example Elementor Pro's native "Webhook" action) send their data as a plain
form-encoded POST, so the automation rule's `record_getter` always saw an
empty payload and never ran.

Solution
--------
Overrides the webhook controller so that, when the body isn't valid JSON and
the query string is empty, it also falls back to the parsed form body. The
rest of the "On Webhook" mechanism (record_getter, linked server actions,
webhook logs) is untouched.
    ''',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Technical',
    'depends': ['base_automation'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
