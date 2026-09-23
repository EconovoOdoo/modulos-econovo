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
    operation_count = fields.Integer(compute='_compute_operation_count')

    _sql_constraints = [
        ('code_uniq', 'unique(code)',
         'An operation category with this code already exists.'),
    ]

    def _compute_operation_count(self):
        counts = dict(self.env['mrp.routing.workcenter']._read_group(
            [('operation_category_id', 'in', self.ids)],
            groupby=['operation_category_id'],
            aggregates=['__count'],
        ))
        for category in self:
            category.operation_count = counts.get(category, 0)

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

    def action_view_operations(self):
        self.ensure_one()
        return {
            'name': _('Operations'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.routing.workcenter',
            'view_mode': 'tree,form',
            'domain': [('operation_category_id', '=', self.id)],
            'context': {'default_operation_category_id': self.id},
        }
