# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ComexOperationStage(models.Model):
    """Stage model for COMEX operations (Kanban-style like CRM/Project)."""

    _name = 'comex.operation.stage'
    _description = 'COMEX Operation Stage'
    _order = 'sequence, id'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Stage Name",
        required=True,
        translate=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Used to order stages in Kanban view.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    fold = fields.Boolean(
        string="Folded in Kanban",
        default=False,
        help="Folded stages are minimized in the Kanban view.",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Description of this stage for documentation purposes.",
    )
    operation_type = fields.Selection(
        selection=[
            ('import', 'Import'),
            ('export', 'Export'),
            ('all', 'All'),
        ],
        string="Operation Type",
        default='all',
        required=True,
        help="Type of operations this stage applies to.",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        (
            'sequence_operation_type_unique',
            'UNIQUE(sequence, operation_type)',
            'Sequence must be unique per operation type! Each operation type (import/export/all) must have unique sequences.'
        ),
    ]
    )
    is_starting_stage = fields.Boolean(
        string="Starting Stage",
        default=False,
        help="If checked, this stage will be used as default for new operations.",
    )
    is_closing_stage = fields.Boolean(
        string="Closing Stage",
        default=False,
        help="If checked, operations in this stage are considered completed.",
    )
    is_cancel_stage = fields.Boolean(
        string="Cancellation Stage",
        default=False,
        help="If checked, this stage represents cancelled operations.",
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
        help="Leave empty to share this stage across all companies.",
    )
    parent_location_id = fields.Many2one(
        'stock.location',
        string="Parent Location (COMEX)",
        domain="[('usage', 'in', ['view', 'transit'])]",
        help="Parent stock location for this stage. "
             "Child transit locations will be selectable in operations.",
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        (
            'unique_starting_stage_per_type',
            'EXCLUDE (operation_type WITH =) WHERE (is_starting_stage = TRUE AND active = TRUE)',
            'Only one starting stage is allowed per operation type.',
        ),
    ]

    # -------------------------------------------------------------------------
    # BUSINESS METHODS
    # -------------------------------------------------------------------------
    @api.model
    def get_default_stage(self, operation_type='import'):
        """Get the default starting stage for an operation type."""
        domain = [
            ('is_starting_stage', '=', True),
            ('active', '=', True),
            '|',
            ('operation_type', '=', operation_type),
            ('operation_type', '=', 'all'),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.env.company.id),
        ]
        return self.search(domain, limit=1, order='sequence')
