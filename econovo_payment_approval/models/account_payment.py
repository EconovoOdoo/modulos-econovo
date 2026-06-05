from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

APPROVAL_PRIORITIES = [
    ('0', 'Normal'),
    ('1', 'Alta'),
    ('2', 'Muy Alta'),
    ('3', 'Urgente'),
]


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    priority = fields.Selection(
        APPROVAL_PRIORITIES,
        string='Prioridad',
        default='0',
        index=True,
        help='Urgency level used to flag payments that require faster approval.',
    )

    approved_by_id = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
        copy=False,
        help='Last user who approved this payment.',
    )

    # ------------------------------------------------------------------
    # Computed fields for view visibility
    # ------------------------------------------------------------------

    has_pending_approval_activity = fields.Boolean(
        compute='_compute_has_pending_approval_activity',
        help='True when at least one "Revisar Pago" activity is pending on this payment.',
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------

    @api.depends('activity_ids.activity_type_id')
    def _compute_has_pending_approval_activity(self):
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago',
            raise_if_not_found=False,
        )
        for payment in self:
            if activity_type:
                payment.has_pending_approval_activity = any(
                    a.activity_type_id == activity_type
                    for a in payment.activity_ids
                )
            else:
                payment.has_pending_approval_activity = False

    # ------------------------------------------------------------------
    # Lifecycle overrides
    # ------------------------------------------------------------------

    def action_post(self):
        """Post payments and create approval activities for each newly posted one."""
        res = super().action_post()
        newly_posted = self.filtered(lambda p: p.state == 'posted')
        newly_posted._create_approval_activities()
        return res

    def action_draft(self):
        """Reset to draft: cancel all approval/rejection activities and clear approver."""
        self._cancel_all_approval_activities()
        self.filtered(lambda p: p.approved_by_id).write({'approved_by_id': False})
        return super().action_draft()

    def action_cancel(self):
        """Cancel: remove all approval/rejection activities and clear approver."""
        self._cancel_all_approval_activities()
        self.filtered(lambda p: p.approved_by_id).write({'approved_by_id': False})
        return super().action_cancel()

    # ------------------------------------------------------------------
    # Approval activity helpers
    # ------------------------------------------------------------------

    def _get_approval_activity_target(self):
        """Return the batch record if this payment belongs to a batch, else self.

        Uses hasattr so the module does not hard-depend on account_payment_batch_st.
        """
        self.ensure_one()
        if hasattr(self, 'batch_payment_st_id') and self.batch_payment_st_id:
            return self.batch_payment_st_id
        return self

    def _create_approval_activities(self):
        """Evaluate routing rules and create mail.activity for each match.

        One activity per (rule, target) pair. When multiple payments in the same
        batch are posted together the target deduplication logic ensures only one
        activity is created per rule on the batch record.
        """
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago',
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        rules = self.env['econovo.approval.rule'].search(
            [('active', '=', True), ('target_model', '=', 'account.payment')],
            order='sequence',
        )
        if not rules:
            return

        for payment in self:
            target = payment._get_approval_activity_target()

            for rule in rules:
                if not rule.user_id:
                    continue

                # Evaluate the rule's domain against this specific payment.
                domain = safe_eval(rule.domain or '[]')
                if domain and not payment.filtered_domain(domain):
                    continue

                # Skip if this (rule.user_id, target) already has a pending
                # approval activity — avoids duplicates when a batch posts
                # multiple payments within the same transaction.
                existing = self.env['mail.activity'].sudo().search([
                    ('res_model', '=', target._name),
                    ('res_id', '=', target.id),
                    ('activity_type_id', '=', activity_type.id),
                    ('user_id', '=', rule.user_id.id),
                ], limit=1)
                if existing:
                    continue

                target.activity_schedule(
                    activity_type_id=activity_type.id,
                    summary=_('Aprobar Pago: %s', payment.name),
                    date_deadline=fields.Date.today(),
                    user_id=rule.user_id.id,
                )

    def _cancel_approval_activities(self):
        """Remove pending 'Aprobar Pago' activities from payment or its batch."""
        self._cancel_activities_by_ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago'
        )

    def _cancel_all_approval_activities(self):
        """Remove both approval and rejection activities (used on draft/cancel)."""
        self._cancel_activities_by_ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago'
        )
        self._cancel_activities_by_ref(
            'econovo_payment_approval.mail_activity_type_pago_rechazado'
        )

    def _cancel_activities_by_ref(self, xml_id):
        """Cancel all activities of the given type on the payment target."""
        activity_type = self.env.ref(xml_id, raise_if_not_found=False)
        if not activity_type:
            return
        targets_seen = set()
        for payment in self:
            target = payment._get_approval_activity_target()
            key = (target._name, target.id)
            if key in targets_seen:
                continue
            targets_seen.add(key)
            self.env['mail.activity'].sudo().search([
                ('res_model', '=', target._name),
                ('res_id', '=', target.id),
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
            'econovo_payment_approval.mail_activity_type_revisar_pago',
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        approved_count = 0
        for payment in self:
            target = payment._get_approval_activity_target()
            activities = self.env['mail.activity'].sudo().search([
                ('res_model', '=', target._name),
                ('res_id', '=', target.id),
                ('activity_type_id', '=', activity_type.id),
                ('user_id', '=', self.env.uid),
            ])
            if not activities:
                if len(self) == 1:
                    raise UserError(
                        _('No tiene actividades de aprobación pendientes asignadas para este pago.')
                    )
                continue
            # Mark each matching activity as done (no feedback popup needed).
            activities.sudo().write({'active': False})
            activities.sudo().unlink()
            payment.write({'approved_by_id': self.env.uid})
            payment.message_post(
                body=_(
                    '<strong>✅ Pago aprobado por %s</strong>',
                    self.env.user.name,
                ),
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
                    'message': _('%s pago(s) aprobado(s).', approved_count),
                    'type': 'success',
                    'sticky': False,
                },
            }

    # ------------------------------------------------------------------
    # Wizard launcher
    # ------------------------------------------------------------------

    def action_open_reject_wizard(self):
        """Open the rejection wizard for this payment."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rechazar Pago'),
            'res_model': 'econovo.payment.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_id': self.id,
            },
        }
