# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockPackageType(models.Model):
    """Extend package types for COMEX container types.
    
    Adds fields to identify shipping containers and their characteristics.
    """
    
    _inherit = 'stock.package.type'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    is_comex_container = fields.Boolean(
        string="Is COMEX Container",
        help="Whether this package type represents a shipping container",
    )
    container_size = fields.Selection(
        selection=[
            ('20', "20 feet"),
            ('40', "40 feet"),
            ('45', "45 feet"),
        ],
        string="Container Size",
        help="Standard container length in feet",
    )
    container_category = fields.Selection(
        selection=[
            ('GP', "General Purpose"),
            ('HC', "High Cube"),
            ('RF', "Reefer"),
            ('OT', "Open Top"),
            ('FR', "Flat Rack"),
            ('TK', "Tank"),
        ],
        string="Container Category",
        help="Container category/type classification",
    )
