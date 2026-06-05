from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountPaymentBatchSt(models.Model):
    """Extends account.payment.batch.st with approval workflow integration.

    The approval activity is placed on the batch record (not on each individual
    payment). This model adds:
      - has_pending_approval_activity: computed from batch's activity_ids
      - action_approve: marks the current user's activity done, propagates
        approved_by_id to all contained payments
      - action_open_reject_wizard_batch: opens the batch rejection wizard
    """

    _inherit = 'account.payment.batch.st'

    has_pending_approval_activity = fields.Boolean(
        compute='_compute_has_pending_approval_activity',
        help='True when at least one "Aprobar Pago" activity is pending on this batch.',
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
        copy=False,
        help='Last user who approved this batch.',
    )

    def _compute_has_pending_approval_activity(self):
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago',
            raise_if_not_found=False,
        )
        for batch in self:
            if activity_type:
                batch.has_pending_approval_activity = any(
                    a.activity_type_id == activity_type
                    for a in batch.activity_ids
                )
            else:
                batch.has_pending_approval_activity = False

    def action_approve(self):
        """Approve: mark current user's pending approval activity as done.

        Also propagates approved_by_id to all individual payments in the batch.
        """
        activity_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_revisar_pago',
            raise_if_not_found=False,
        )
        if not activity_type:
            return

        approved_count = 0
        for batch in self:
            activities = self.env['mail.activity'].sudo().search([
                ('res_model', '=', batch._name),
                ('res_id', '=', batch.id),
                ('activity_type_id', '=', activity_type.id),
                ('user_id', '=', self.env.uid),
            ])
            if not activities:
                if len(self) == 1:
                    raise UserError(
                        _('No tiene actividades de aprobación pendientes asignadas para este lote.')
                    )
                continue
            activities.sudo().unlink()
            approver_id = self.env.uid
            batch.write({'approved_by_id': approver_id})
            # Propagate to each contained payment so the field is set there too.
            if batch.payment_ids:
                batch.payment_ids.write({'approved_by_id': approver_id})
            batch.message_post(
                body=_(
                    '<strong>✅ Lote aprobado por %s</strong>',
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
                    'message': _('%s lote(s) aprobado(s).', approved_count),
                    'type': 'success',
                    'sticky': False,
                },
            }

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
