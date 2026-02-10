# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ComexOperationTag(models.Model):
    """Tags for classifying and organizing COMEX operations."""

    _name = 'comex.operation.tag'
    _description = 'COMEX Operation Tag'
    _order = 'name'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Tag Name",
        required=True,
        translate=True,
    )
    color = fields.Integer(string="Color")

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    _sql_constraints = [
        ('name_uniq', 'unique (name)', "A tag with this name already exists."),
    ]
