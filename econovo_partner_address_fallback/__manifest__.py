# -*- coding: utf-8 -*-
{
    'name': 'Econovo - Partner Address Fallback to Company',
    'version': '17.0.1.0.0',
    'category': 'Contacts',
    'summary': (
        'When an individual contact (type=contact) with a parent company is used '
        'on a sale order and no explicit invoice/delivery address is defined, '
        'the invoice and delivery addresses fall back to the commercial partner '
        '(the top-level company) instead of the individual contact.'
    ),
    'description': """
Problem
-------
In Odoo 17, when you select a person contact (type='contact', child of a company)
as the customer on a sale order, ``res.partner.address_get`` uses that individual
as the fallback for both the invoice and delivery addresses.  This causes invoices
and stock pickings to be addressed to the person rather than to the company, which
is almost never the desired behaviour.

Root cause
----------
``address_get`` adds ``'contact'`` to its scan set, so it immediately captures the
individual as ``result['contact']``.  The final fallback line::

    default = result.get('contact', self.id or False)
    result[adr_type] = result.get(adr_type) or default

then propagates that individual's id to every address type it could not resolve
(e.g. ``invoice``, ``delivery``).

Fix (this module)
-----------------
After calling ``super().address_get()``, if ``self`` is a single individual contact
(not a company, has a ``parent_id``) and the resolved address for a non-*contact*
type still equals the individual (i.e. no explicit child with that type was found),
the id is replaced with ``commercial_partner_id`` — the top-level commercial entity.

Edge cases handled
------------------
* Partner **is** a company → not affected.
* Partner has no ``parent_id`` → not affected.
* Company has an explicit ``type='invoice'`` or ``type='delivery'`` child → that
  child wins; this module does not override it.
* Multi-partner recordset → not affected (original behaviour preserved).
* Address type ``'contact'`` → never overridden; a contact search should still
  return the person.
* ``partner_invoice_id`` / ``partner_shipping_id`` on the sale order can still be
  changed manually per-order.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['base'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
