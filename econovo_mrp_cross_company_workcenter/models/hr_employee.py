# -*- coding: utf-8 -*-
from odoo import fields, models

_WORKCENTER_IDS_FIELD = {
    'comodel_name': 'mrp.workcenter',
    # Reuses the relation table mrp_workorder already created for
    # mrp.workcenter.employee_ids, so this exposes no new data of its own.
    'relation': 'hr_employee_mrp_workcenter_rel',
    'column1': 'hr_employee_id',
    'column2': 'mrp_workcenter_id',
    'string': 'Allowed On Work Centers',
    'readonly': True,
    'help': "Work centers listing this employee under their allowed employees. "
            "Declared so the employee record rule can grant read access based "
            "on it, for employees explicitly authorized on a work center of "
            "the reader's own company.",
}


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    workcenter_ids = fields.Many2many(**_WORKCENTER_IDS_FIELD)


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    # hr.employee.public is a SQL view over hr_employee and shares its ids, so
    # the same relation rows apply. Odoo explicitly allows two models to share
    # a relation table when one of them is _auto=False, and skips the foreign
    # key for non-ordinary tables (odoo/fields.py, Many2many.update_db*).
    workcenter_ids = fields.Many2many(**_WORKCENTER_IDS_FIELD)
