from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountPaymentBatchSt(models.Model):
    """Extends account.payment.batch.st with approval workflow integration.

    Activities are placed on each individual account.payment, NOT on the batch.
    This model provides convenience fields and actions so approvers can also
    act from the batch form without needing to open each payment separately.

      - has_pending_approval_activity: True when any payment in the batch has
        a pending "Aprobar Pago" activity for the current user
      - action_approve: delegates to each contained payment's action_approve()
      - action_open_reject_wizard_batch: opens the batch rejection wizard
    """

    _inherit = 'account.payment.batch.st'

    has_pending_approval_activity = fields.Boolean(
        compute='_compute_has_pending_approval_activity',
        help='True when any payment in this batch has a pending approval activity.',
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
        copy=False,
        help='Last user who approved this batch (set when all payments are approved).',
    )

    def _compute_has_pending_approval_activity(self):
        """True when at least one payment in the batch has a pending approval activity."""
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago',
            raise_if_not_found=False,
        )
        for batch in self:
            if not activity_type or not batch.payment_ids:
                batch.has_pending_approval_activity = False
                continue
            payment_ids = batch.payment_ids.ids
            batch.has_pending_approval_activity = bool(
                self.env['mail.activity'].sudo().search_count([
                    ('res_model', '=', 'account.payment'),
                    ('res_id', 'in', payment_ids),
                    ('activity_type_id', '=', activity_type.id),
                ])
            )

    def action_approve(self):
        """Approve all payments in this batch that have a pending activity for the current user."""
        self.ensure_one()
        if not self.payment_ids:
            raise UserError(_('Este lote no contiene pagos.'))
        result = self.payment_ids.action_approve()
        # Set approved_by_id on the batch once all payments are approved.
        self.write({'approved_by_id': self.env.uid})
        self.message_post(
            body=_(
                '<strong>✅ Lote aprobado por %s</strong>',
                self.env.user.name,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        return result

    def action_open_reject_wizard_batch(self):
        """Open the batch rejection wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rechazar Lote de Pagos'),
            'res_model': 'econovo.batch.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_batch_id': self.id,
            },
        }

