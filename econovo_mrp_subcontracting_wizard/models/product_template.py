# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_subcontracting_phantom = fields.Boolean(
        string='Subcontracting Intermediate Product',
        default=False,
        copy=False,
        help='Technical product generated to represent the state of a part between two '
             'stages of its manufacturing route when one of its operations is externalized.',
    )
