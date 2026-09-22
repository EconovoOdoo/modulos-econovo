# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    operation_category_id = fields.Many2one(
        'mrp.routing.operation.category',
        string='Operation Category',
        help='Determines the suffix of the intermediate products generated when this '
             'operation is externalized to a subcontractor.',
    )
