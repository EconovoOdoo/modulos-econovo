# -*- coding: utf-8 -*-

from odoo import fields, models


class EconovoQualitySystem(models.Model):
    """Management system / standard (e.g. ISO 9001:2015).

    OCA equivalent: mgmtsystem.system
    """

    _name = 'econovo.quality.system'
    _description = 'Management System'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )
