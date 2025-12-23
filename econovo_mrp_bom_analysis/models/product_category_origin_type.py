# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductCategoryOriginType(models.Model):
    _name = 'product.category.origin.type'
    _description = 'Product Category Origin Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True
    )
    code = fields.Char(
        string='Code',
        required=True,
        help='Short code for filtering and grouping (e.g., raw_material, commercial)'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    color = fields.Integer(
        string='Color',
        default=0,
        help='Color index for badges and kanban cards'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    description = fields.Text(
        string='Description',
        translate=True
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The code must be unique!'),
    ]
