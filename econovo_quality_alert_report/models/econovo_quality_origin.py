# -*- coding: utf-8 -*-

from odoo import fields, models


class EconovoQualityOrigin(models.Model):
    """Origin (source) of a non-conformity.

    OCA equivalent: mgmtsystem.nonconformity.origin
    Hierarchical model using parent_store for performance.
    """

    _name = 'econovo.quality.origin'
    _description = 'Non-Conformity Origin'
    _parent_store = True
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        'econovo.quality.origin',
        string='Parent Origin',
        index=True,
        ondelete='restrict',
    )
    child_ids = fields.One2many(
        'econovo.quality.origin',
        'parent_id',
        string='Child Origins',
    )
    ref_code = fields.Char(string='Reference Code')
    active = fields.Boolean(default=True)
    parent_path = fields.Char(index=True, unaccent=False)
