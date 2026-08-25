# -*- coding: utf-8 -*-
{
    'name': 'MRP Cross-Company Workcenter Employee',
    'version': '17.0.1.1.0',
    'category': 'Manufacturing/Manufacturing',
    'summary': "Let an employee whose HR record lives in another company start a work order, without duplicating their employee record.",
    'description': """
Odoo's Shop Floor ``button_start()`` (``mrp_workorder/models/mrp_workorder.py``)
requires the logged in user to have an ``hr.employee`` record whose
``company_id`` matches the CURRENTLY ACTIVE company: ``res.users.employee_id``
is computed per active company (``hr/models/res_users.py``
``_compute_company_employee``, scoped by ``self.env.company``), not per
allowed company.

This blocks a common multi-company group scenario: an employee hired/paid
through one company (e.g. Agrovial) who physically operates work centers
that belong to a different company of the same group (e.g. Oscar Scorza).
Granting the user access to both companies (``res.users.company_ids``) only
fixes document VISIBILITY (record rules); it does not change which company
this specific check looks at, so it keeps raising::

    You need to link this user to an employee of this company to process
    the work order

The usual workaround is to create a SECOND ``hr.employee`` record for the
same person in the other company. That duplicates HR data (and headcount in
reports) for no real reason, and this module exists specifically to avoid
it.

**What this module does**

* Overrides ``mrp.workorder.button_start()``: only when the user has NO
  employee record in the current active company, it looks for one HR
  already linked to this same user in another company
  (``hr.employee.user_id``), and lets that employee be used for this one
  call. This deliberately does NOT grant ``res.users.company_ids`` (multi-
  company access): that would also expose every other record of that
  company the user's groups can read, and show the company switcher in the
  top bar, neither of which this needs -- the only fact that authorizes
  this is that HR already linked that employee record to this user.
* Relaxes the "Allowed Employees" field domain on the Work Center form
  (``mrp.workcenter.employee_ids``), which otherwise only lets you pick
  employees from the work center's own company, for work centers that use
  that optional restriction.
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': [
        'mrp_workorder',
    ],
    'data': [
        'views/mrp_workcenter_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
