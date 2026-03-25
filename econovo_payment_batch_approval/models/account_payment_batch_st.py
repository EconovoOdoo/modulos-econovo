from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class AccountPaymentBatchSt(models.Model):
    _inherit = 'account.payment.batch.st'

    has_draft_payments = fields.Boolean(
        compute='_compute_has_draft_payments',
        help='True if at least one payment in this batch is still in draft state.',
    )

    @api.depends('payment_ids.state')
    def _compute_has_draft_payments(self):
        for batch in self:
            batch.has_draft_payments = any(p.state == 'draft' for p in batch.payment_ids)

    def action_approve_batch(self):
        """Propagate approval to all draft payments in this batch, then confirm them.

        For each draft payment:
        - Creates a studio.approval.entry for every active Studio Approval Rule
          whose domain matches that payment. Studio then finds those entries when
          action_post() is called and allows posting to proceed.
        - Finds the linked studio.approval.request and marks its mail.activity as
          done (action_feedback), attributed to the current batch approver. Uses
          sudo() to bypass the activity owner check while keeping env.uid so the
          chatter note shows the actual approver.
        """
        self.ensure_one()
        if not self.env.user.has_group(
            'econovo_payment_batch_approval.grp_aprobadores_lote_pago'
        ):
            raise UserError(_('You do not have the rights to approve payment batches.'))

        draft_payments = self.payment_ids.filtered(lambda p: p.state == 'draft')
        if not draft_payments:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No pending payments'),
                    'message': _('There are no draft payments to confirm in this batch.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        # Retrieve all active Studio Approval Rules for account.payment.action_post.
        ApprovalRule = self.env['studio.approval.rule'].sudo()
        rules = ApprovalRule.search([
            ('model_name', '=', 'account.payment'),
            ('method', '=', 'action_post'),
            ('active', '=', True),
        ])

        ApprovalEntry = self.env['studio.approval.entry'].sudo()
        for payment in draft_payments:
            for rule in rules:
                # Skip rules whose domain does not apply to this specific payment.
                if rule.domain:
                    domain = safe_eval(rule.domain)
                    if not payment.filtered_domain(domain):
                        continue

                # Skip if an entry already exists (unique DB constraint per rule + record).
                if ApprovalEntry.search(
                    [('rule_id', '=', rule.id), ('res_id', '=', payment.id)], limit=1
                ):
                    continue

                # Create the approval entry attributed to the current approver.
                ApprovalEntry.create({
                    'user_id': self.env.uid,
                    'rule_id': rule.id,
                    'res_id': payment.id,
                    'approved': True,
                })

                # Mark the pending Studio approval activity as done.
                # sudo() bypasses the activity owner check (activity may be
                # assigned to a different responsible user); env.uid is unchanged
                # so the chatter note is attributed to the actual batch approver.
                request = self.env['studio.approval.request'].sudo().search(
                    [('rule_id', '=', rule.id), ('res_id', '=', payment.id)], limit=1
                )
                if request and request.mail_activity_id:
                    request.mail_activity_id.sudo().action_feedback(
                        feedback=_('Approved via batch %s', self.name)
                    )

        # Studio will now find the entries above and allow action_post to proceed.
        draft_payments.action_post()

        # Soft-refresh: re-open the same form record so the view updates in place
        # (button disappears, statusbar shows posted) without a full page reload.
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.batch.st',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
