# -*- coding: utf-8 -*-

from odoo import fields, models


class QualityAlert(models.Model):
    """Extend quality.alert with non-conformity fields aligned to OCA.

    Fields mapped to mgmtsystem_nonconformity for future migration.
    """

    _inherit = 'quality.alert'

    # --- Fields replacing Studio custom fields ---
    severity_id = fields.Many2one(
        'econovo.quality.severity',
        string='Severity',
        tracking=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        tracking=True,
    )
    containment_responsible_id = fields.Many2one(
        'res.users',
        string='Containment Responsible',
        domain=[('share', '=', False)],
        tracking=True,
    )
    verification_date = fields.Date(
        string='Verification Date',
        tracking=True,
    )

    # --- New fields aligned to OCA ---
    origin_ids = fields.Many2many(
        'econovo.quality.origin',
        string='Origins',
    )
    cause_ids = fields.Many2many(
        'econovo.quality.cause',
        string='Causes',
    )
    system_id = fields.Many2one(
        'econovo.quality.system',
        string='Management System',
    )
    immediate_action = fields.Html(
        string='Immediate Action',
    )
    analysis = fields.Text(
        string='Analysis',
    )
    evaluation_comments = fields.Text(
        string='Evaluation Comments',
    )
    manager_user_id = fields.Many2one(
        'res.users',
        string='Manager',
        domain=[('share', '=', False)],
        tracking=True,
    )
