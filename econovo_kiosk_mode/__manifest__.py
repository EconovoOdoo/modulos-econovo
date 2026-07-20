# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Econovo - Kiosk Mode for Window Actions",
    'version': '17.0.1.1.1',
    'category': 'Technical',
    'summary': "Generic full-screen, auto-refreshing kiosk mode for any window action",
    'description': """
Kiosk Mode Framework for Window Actions
========================================

Turns any existing window action (list/kanban/...) into a full-screen,
auto-refreshing "wall display" screen (kitchen-display style), configurable
directly from the action's own form view. No custom development is needed
per view/model.

Features
--------
* New "Kiosco" tab on Window Actions (Settings > Technical > Actions >
  Actions > Window Actions, with developer mode enabled).
* Reuses Odoo's standard web client renderer: any view type the action
  already supports (list, kanban, calendar, pivot, ...) works as-is.
* Two refresh strategies, configurable per action:
  - Real Time: pushed through Odoo's bus, no polling.
  - Interval: simple periodic refresh.
* Real-time refresh is powered by automatically managed Automated Actions
  (`base.automation`), one pair per watched model, created/removed as
  needed - fully visible and debuggable from Settings > Technical.
* Hides the floating Discuss chat window popups while a kiosk screen is
  active, so an incoming message to the logged-in kiosk user never pops
  up on the shared wall screen.
    """,
    'author': "Jose D. Leonett",
    'website': "https://github.com/josedleonett",
    'license': 'AGPL-3',
    'depends': ['base_automation', 'bus', 'mail', 'web'],
    'data': [
        'views/ir_actions_act_window_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'econovo_kiosk_mode/static/src/kiosk/*.js',
            'econovo_kiosk_mode/static/src/kiosk/*.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
