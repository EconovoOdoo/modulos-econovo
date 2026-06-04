from odoo import _, api, fields, models
from odoo.tools.safe_eval import safe_eval


class AccountPayment(models.Model):
    _inherit = 'account.payment'

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
        """Reset to draft and cancel any pending approval activities."""
        self._cancel_approval_activities()
        return super().action_draft()

    def action_cancel(self):
        """Cancel and remove pending approval activities."""
        self._cancel_approval_activities()
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

        rules = self.env['econovo.payment.approval.rule'].search(
            [('active', '=', True)], order='sequence'
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
                    summary=_('Revisar Pago: %s', payment.name),
                    date_deadline=fields.Date.today(),
                    user_id=rule.user_id.id,
                )

    def _cancel_approval_activities(self):
        """Remove pending 'Revisar Pago' activities from payment or its batch."""
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago',
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        targets_seen = set()
        for payment in self:
            target = payment._get_approval_activity_target()
            key = (target._name, target.id)
            if key in targets_seen:
                continue
            targets_seen.add(key)

            activities = self.env['mail.activity'].sudo().search([
                ('res_model', '=', target._name),
                ('res_id', '=', target.id),
                ('activity_type_id', '=', activity_type.id),
            ])
            # unlink instead of action_feedback so no done message is posted.
            activities.unlink()

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
