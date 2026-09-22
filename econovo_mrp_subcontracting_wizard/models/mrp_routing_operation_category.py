# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CODE_PATTERN = re.compile(r'^[A-Z0-9]+$')


class MrpRoutingOperationCategory(models.Model):
    _name = 'mrp.routing.operation.category'
    _description = 'Manufacturing Operation Category'
    _order = 'code'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help='Short code used as the suffix of the intermediate products generated '
             'when an operation of this category is externalized.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)',
         'An operation category with this code already exists.'),
    ]

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for category in self:
            category.display_name = '[%s] %s' % (category.code, category.name)

    @api.constrains('code')
    def _check_code(self):
        # The code becomes part of a product internal reference, so it must be safe to append.
        for category in self:
            if not CODE_PATTERN.match(category.code or ''):
                raise ValidationError(_(
                    'The operation category code must only contain uppercase letters '
                    'and digits (no spaces or symbols): %s', category.code,
                ))
