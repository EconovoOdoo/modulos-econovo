# -*- coding: utf-8 -*-

from odoo import fields, models


class EconovoQualitySeverity(models.Model):
    """Severity level of a non-conformity.

    OCA equivalent: mgmtsystem.nonconformity.severity
    """

    _name = 'econovo.quality.severity'
    _description = 'Non-Conformity Severity'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
