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

    effective_approval_amount = fields.Float(
        string='Monto Efectivo de Aprobación',
        compute='_compute_effective_approval_amount',
        help=(
            'Amount used when evaluating approval routing rules. '
            'If the payment belongs to a batch, returns the sum of all non-cancelled '
            'payments in that batch so that per-batch thresholds are applied even '
            'when an individual payment is below the limit. '
            'Falls back to the payment own amount when no batch is assigned.'
        ),
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------

    @api.depends(
        'amount',
        'batch_payment_st_id',
        'batch_payment_st_id.payment_ids.amount',
        'batch_payment_st_id.payment_ids.state',
    )
    def _compute_effective_approval_amount(self):
        """Return the batch total for batched payments, or the individual amount.

        Sumitec always assigns a batch to every confirmed payment (even single
        ones). When the user clicks "Confirmar y Nuevo" multiple times within
        the same session all resulting payments share the same batch. Using the
        batch total as the threshold basis prevents the edge case where each
        individual payment is below the 1M limit but the combined batch exceeds
        it, which would otherwise route some payments to Nacho and others to
        Fabricio within the same batch.

        Cancelled payments are excluded from the sum because a cancelled
        payment in the batch no longer represents a real commitment.
        """
        for payment in self:
            if payment.batch_payment_st_id:
                active_in_batch = payment.batch_payment_st_id.payment_ids.filtered(
                    lambda p: p.state != 'cancel'
                )
                payment.effective_approval_amount = sum(
                    active_in_batch.mapped('amount')
                )
            else:
                payment.effective_approval_amount = payment.amount

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
        # Re-evaluate siblings in case the updated batch total crosses a threshold
        newly_posted._recheck_batch_siblings()
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

    def _recheck_batch_siblings(self):
        """Re-evaluate routing for previously confirmed payments in the same batch.

        When a new payment is added to a batch via "Confirmar y Nuevo", the batch
        total grows. Payments confirmed earlier were routed against a smaller total
        and may have been assigned to the wrong approver. This method cancels and
        recreates pending approval activities for siblings whose routing may have
        changed given the updated batch total.

        Only payments with a still-pending (not yet approved) activity are
        touched; approved payments are never disturbed.
        """
        for payment in self.filtered(lambda p: p.batch_payment_st_id):
            pending_siblings = payment.batch_payment_st_id.payment_ids.filtered(
                lambda p: (
                    p.id != payment.id
                    and p.state == 'posted'
                    and p.has_pending_approval_activity
                    and not p.approved_by_id
                )
            )
            if not pending_siblings:
                continue
            pending_siblings._cancel_approval_activities()
            pending_siblings._create_approval_activities()

    def _get_approval_activity_target(self):
        """Return self: activities are always placed on the individual payment.

        Even when the payment belongs to a batch, we create the activity directly
        on each account.payment so approvers can act from the payment form.
        The batch form shows a derived has_pending_approval_activity that checks
        its payments, but the source of truth is always the payment record.
        """
        self.ensure_one()
        return self

    def _create_approval_activities(self):
        """Evaluate routing rules and create approval activities.

        Rules are evaluated in ascending sequence order using exclusive priority
        routing:

        - ``always_apply=False`` (default / exclusive): the first matching rule
          creates an activity and blocks all subsequent exclusive rules for that
          payment.  ``always_apply=True`` rules are still evaluated after it.
        - ``always_apply=True`` (inclusive): always creates an activity if the
          domain matches, regardless of whether an exclusive rule already fired.
          Useful for mandatory second-approver scenarios.

        Rule domains that reference ``effective_approval_amount`` are evaluated
        against the batch total (sum of non-cancelled payments in the same
        batch) so batch-level thresholds apply consistently.

        Deduplication: if a pending activity for the same (type, user) already
        exists on the payment it is treated as already-handled for that rule.
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
            exclusive_matched = False

            for rule in rules:
                if not rule.user_id:
                    continue

                # Evaluate the rule's domain against this specific payment.
                domain = safe_eval(rule.domain or '[]')
                if domain and not payment.filtered_domain(domain):
                    continue

                # Exclusive rule blocked by a prior exclusive match.
                if not rule.always_apply and exclusive_matched:
                    continue

                # Resolve any active substitution for this rule's approver
                # (manual date-range or HR leave auto-detection).
                effective_uid = (
                    self.env['econovo.approval.substitution']
                    ._get_effective_approver(rule.user_id.id)
                )

                # Deduplication: skip if this (type, user) activity already exists.
                existing = self.env['mail.activity'].sudo().search([
                    ('res_model', '=', target._name),
                    ('res_id', '=', target.id),
                    ('activity_type_id', '=', activity_type.id),
                    ('user_id', '=', effective_uid),
                ], limit=1)
                if not existing:
                    target.activity_schedule(
                        activity_type_id=activity_type.id,
                        summary=_('Aprobar Pago: %s', payment.name),
                        date_deadline=fields.Date.today(),
                        user_id=effective_uid,
                    )

                # Mark exclusive match so subsequent exclusive rules are skipped.
                if not rule.always_apply:
                    exclusive_matched = True

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
        """Cancel all activities of the given type on each payment."""
        activity_type = self.env.ref(xml_id, raise_if_not_found=False)
        if not activity_type:
            return
        for payment in self:
            self.env['mail.activity'].sudo().search([
                ('res_model', '=', payment._name),
                ('res_id', '=', payment.id),
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
            # Find all pending approval activities on this payment
            all_activities = self.env['mail.activity'].sudo().search([
                ('res_model', '=', target._name),
                ('res_id', '=', target.id),
                ('activity_type_id', '=', activity_type.id),
            ])
            # Keep only activities the current user can approve (assigned or supervisor)
            approvable = self.env['mail.activity']
            approval_rule = self.env['econovo.approval.rule'].sudo()
            for act in all_activities:
                if act.user_id.id == self.env.uid:
                    approvable |= act
                elif self.env.uid in approval_rule._get_supervisors_for_activity(act):
                    approvable |= act

            if not approvable:
                if len(self) == 1:
                    raise UserError(
                        _('No tiene actividades de aprobación pendientes asignadas para este pago.')
                    )
                continue

            # Build chatter body: indicate supervisor approval when applicable
            supervised = approvable.filtered(lambda a: a.user_id.id != self.env.uid)
            if supervised:
                assigned_names = ', '.join(supervised.mapped('user_id.name'))
                body = Markup(
                    '<strong>\u2705 Pago aprobado por %s'
                    ' (supervisor \u2014 aprobador asignado: %s)</strong>'
                ) % (self.env.user.name, assigned_names)
            else:
                body = Markup('<strong>\u2705 Pago aprobado por %s</strong>') % self.env.user.name

            approvable.sudo().write({'active': False})
            approvable.sudo().unlink()
            payment.write({'approved_by_id': self.env.uid})
            payment.message_post(
                body=body,
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
        if len(self) > 1:
            raise UserError(_('Por favor seleccione un solo pago para rechazar.'))
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
