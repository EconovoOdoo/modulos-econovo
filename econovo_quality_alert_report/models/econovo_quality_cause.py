# -*- coding: utf-8 -*-

from odoo import fields, models


class EconovoQualityCause(models.Model):
    """Cause of a non-conformity.

    OCA equivalent: mgmtsystem.nonconformity.cause
    Hierarchical model using parent_store for performance.
    """

    _name = 'econovo.quality.cause'
    _description = 'Non-Conformity Cause'
    _parent_store = True
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        'econovo.quality.cause',
        string='Parent Cause',
        index=True,
        ondelete='restrict',
    )
    child_ids = fields.One2many(
        'econovo.quality.cause',
        'parent_id',
        string='Child Causes',
    )
    ref_code = fields.Char(string='Reference Code')
    parent_path = fields.Char(index=True, unaccent=False)
