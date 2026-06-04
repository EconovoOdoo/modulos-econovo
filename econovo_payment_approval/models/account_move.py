from odoo import _, api, fields, models
from odoo.tools.safe_eval import safe_eval


class AccountMove(models.Model):
    _inherit = 'account.move'

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
        """Reset to draft and cancel any pending approval activities."""
        self._cancel_approval_activities()
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

        rules = self.env['econovo.move.approval.rule'].search(
            [('active', '=', True)], order='sequence'
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
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_aprobar_asiento',
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        for move in self:
            activities = self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'account.move'),
                ('res_id', '=', move.id),
                ('activity_type_id', '=', activity_type.id),
            ])
            activities.unlink()
