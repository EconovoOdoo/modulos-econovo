# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    origin_type = fields.Selection(
        selection=[
            ('raw_material', 'Raw Material'),
            ('commercial', 'Commercial'),
            ('subassembly', 'Subassembly'),
            ('component', 'Component'),
            ('consumable', 'Consumable'),
            ('service', 'Service'),
        ],
        string='Origin Type',
        default='component',
        help='Product classification for BOM cost analysis. '
             'Used to group and analyze components by their nature.'
    )
