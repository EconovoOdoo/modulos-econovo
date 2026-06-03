from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_priority = fields.Selection(
        selection=[
            ('low', 'Not a priority'),
            ('normal', 'Normal'),
            ('urgent', 'Urgent'),
        ],
        string='Payment Priority',
        default='normal',
        help="Urgency level used to prioritize payment processing.",
    )

    def action_post_and_new(self):
        """Override to pre-assign the batch before action_post is intercepted by Studio Approval.

        Root cause of the bug: Sumitec's action_post calls _ensure_batch() and assigns
        batch_payment_st_id. When Studio Approval Rules block action_post, that assignment
        never runs, so batch_payment_st_id stays False and the next payment form opens
        without a batch — breaking the entire "Confirmar y Nuevo" chaining flow.

        Fix: pre-assign the batch HERE, before super() calls action_post (which Studio
        intercepts). This guarantees the batch exists in context for the next payment
        even when posting is blocked by approval rules.
        """
        self.ensure_one()
        if not self.batch_payment_st_id:
            self.batch_payment_st_id = self._ensure_batch().id
        res = super().action_post_and_new()
        # Sumitec already propagates batch_id via context, but may propagate False
        # if action_post was blocked. Enforce the correct value here as a safeguard.
        if self.batch_payment_st_id:
            res.setdefault('context', {})
            res['context']['default_batch_payment_st_id'] = self.batch_payment_st_id.id
        return res
