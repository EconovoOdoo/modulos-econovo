# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    origin_type_id = fields.Many2one(
        comodel_name='product.category.origin.type',
        string='Origin Type',
        help='Product classification for BOM cost analysis. '
             'Used to group and analyze components by their nature.'
    )
