from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

APPROVAL_PRIORITIES = [
    ('0', 'Normal'),
    ('1', 'Alta'),
    ('2', 'Muy Alta'),
    ('3', 'Urgente'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    priority = fields.Selection(
        APPROVAL_PRIORITIES,
        string='Prioridad',
        default='0',
        index=True,
        help='Urgency level used to flag journal entries that require faster approval.',
    )

    approved_by_id = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
        copy=False,
        help='Last user who approved this journal entry.',
    )

    # ------------------------------------------------------------------
    # Computed fields for view visibility
    # ------------------------------------------------------------------

    has_pending_approval_activity = fields.Boolean(
        compute='_compute_has_pending_approval_activity',
        help='True when at least one "Aprobar Asiento" activity is pending on this entry.',
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------

    @api.depends('activity_ids.activity_type_id')
    def _compute_has_pending_approval_activity(self):
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_aprobar_asiento',
            raise_if_not_found=False,
        )
        for move in self:
            if activity_type:
                move.has_pending_approval_activity = any(
                    a.activity_type_id == activity_type
                    for a in move.activity_ids
                )
            else:
                move.has_pending_approval_activity = False

    # ------------------------------------------------------------------
    # Lifecycle overrides
    # ------------------------------------------------------------------

    def action_post(self):
        """Post journal entries and create approval activities for matching rules."""
        res = super().action_post()
        newly_posted = self.filtered(
            lambda m: m.state == 'posted' and m.move_type == 'entry'
        )
        newly_posted._create_approval_activities()
        return res

    def button_draft(self):
        """Reset to draft: cancel all approval/rejection activities and clear approver."""
        self._cancel_all_approval_activities()
        self.filtered(lambda m: m.approved_by_id).write({'approved_by_id': False})
        return super().button_draft()

    # ------------------------------------------------------------------
    # Approval activity helpers
    # ------------------------------------------------------------------

    def _create_approval_activities(self):
        """Evaluate routing rules and create mail.activity for each match.

        Only called for move_type='entry' records (manual journal entries).
        One activity per (rule, move) pair; deduplication avoids double creation.
        """
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_aprobar_asiento',
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        rules = self.env['econovo.approval.rule'].search(
            [('active', '=', True), ('target_model', '=', 'account.move')],
            order='sequence',
        )
        if not rules:
            return

        for move in self:
            for rule in rules:
                if not rule.user_id:
                    continue

                domain = safe_eval(rule.domain or '[]')
                if domain and not move.filtered_domain(domain):
                    continue

                # Skip if a pending activity for this rule already exists.
                existing = self.env['mail.activity'].sudo().search([
                    ('res_model', '=', 'account.move'),
                    ('res_id', '=', move.id),
                    ('activity_type_id', '=', activity_type.id),
                    ('user_id', '=', rule.user_id.id),
                ], limit=1)
                if existing:
                    continue

                move.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=_('Aprobar Asiento: %s', move.name),
                    date_deadline=fields.Date.today(),
                    user_id=rule.user_id.id,
                )

    def _cancel_approval_activities(self):
        """Remove pending 'Aprobar Asiento' activities from these entries."""
        self._cancel_activities_by_ref(
            'econovo_payment_approval.mail_activity_type_aprobar_asiento'
        )

    def _cancel_all_approval_activities(self):
        """Remove both approval and rejection activities (used on draft/cancel)."""
        self._cancel_activities_by_ref(
            'econovo_payment_approval.mail_activity_type_aprobar_asiento'
        )
        self._cancel_activities_by_ref(
            'econovo_payment_approval.mail_activity_type_asiento_rechazado'
        )

    def _cancel_activities_by_ref(self, xml_id):
        """Cancel all activities of the given type on these moves."""
        activity_type = self.env.ref(xml_id, raise_if_not_found=False)
        if not activity_type:
            return
        for move in self:
            self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', move.id),
                ('activity_type_id', '=', activity_type.id),
            ]).unlink()

    # ------------------------------------------------------------------
    # Approve / Reject actions
    # ------------------------------------------------------------------

    def action_approve(self):
        """Approve: mark the current user's pending approval activity as done.

        Works for single records (form button) and multiple records (mass action
        from the list view). In mass mode, records where the current user has no
        pending activity are silently skipped.
        """
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_aprobar_asiento',
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        approved_count = 0
        for move in self:
            activities = self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', move.id),
                ('activity_type_id', '=', activity_type.id),
                ('user_id', '=', self.env.uid),
            ])
            if not activities:
                if len(self) == 1:
                    raise UserError(
                        _('No tiene actividades de aprobación pendientes asignadas para este asiento.')
                    )
                continue
            activities.sudo().unlink()
            move.write({'approved_by_id': self.env.uid})
            move.message_post(
                body=Markup('<strong>\u2705 Asiento aprobado por %s</strong>') % self.env.user.name,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            approved_count += 1

        if len(self) > 1:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Aprobación masiva'),
                    'message': _('%s asiento(s) aprobado(s).', approved_count),
                    'type': 'success',
                    'sticky': False,
                },
            }

    def action_open_reject_wizard_entry(self):
        """Open the rejection wizard for this journal entry."""
        if len(self) > 1:
            raise UserError(_('Por favor seleccione un solo asiento para rechazar.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rechazar Asiento'),
            'res_model': 'econovo.move.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers (kept for backward compat)
    # ------------------------------------------------------------------
