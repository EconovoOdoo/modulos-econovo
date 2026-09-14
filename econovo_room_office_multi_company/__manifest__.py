# -*- coding: utf-8 -*-
{
    'name': 'Room Office Multi-Company',
    'version': '17.0.1.0.2',
    'category': 'Services/Room',
    'summary': "Let a Room Office (and its rooms) be shared across every company instead of a single one",
    'description': """
Odoo's Room app (``room.office``/``room.room``) requires every office to
belong to exactly one company (``company_id`` is required), and a global
``ir.rule`` on both models only lets a company's users see offices/rooms
owned by that same company.

This makes it impossible to model one physical meeting room shared by
several companies of the same group with a single, common booking
calendar: it would need to be duplicated once per company, which defeats
``room.booking``'s own overlap check (``_check_unique_slot``) since it
would no longer be the same ``room_id``, and each copy could then be
double-booked independently of the other.

**What this module does**

* Makes ``room.office.company_id`` optional. Leaving it empty marks the
  office -- and all its ``room.room`` records, through the existing
  ``company_id = fields.Many2one(related="office_id.company_id",
  store=True)`` -- as shared: visible and bookable by users of ANY
  company, through a single set of records and a single shared calendar.
* Widens ``room``'s own multi-company record rules
  (``room_office_comp_rule``/``room_room_comp_rule``, both global) to also
  allow records with no company, applied from ``_register_hook`` (so it
  self-heals) and reverted to the original core domain on uninstall.
* The kiosk/tablet booking flow (``/room/<code>/book``) already works this
  way today regardless of company, since its controller uses ``sudo()``
  throughout -- this module extends the same company-agnostic behavior to
  the regular backend Room app menus and views.
* Ensures that the Room kiosk loads the official ``room`` web translations
  before mounting its public OWL component. Odoo 17's lightweight Room page
  uses Website's translation endpoint, which excludes the Enterprise
  ``room`` module and leaves the interface in English.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['room'],
    'assets': {
      'room.assets_room_booking': [
        'econovo_room_office_multi_company/static/src/js/room_translation_service.js',
      ],
    },
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
