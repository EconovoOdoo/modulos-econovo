from odoo import _, fields, models


class EconovoBatchRejectWizard(models.TransientModel):
    """Wizard that lets an approver reject a batch payment with a mandatory reason.

    Steps performed on confirmation:
    1. Cancel all pending "Aprobar Pago" activities on the batch.
    2. Post a rejection note to the batch chatter.
    3. Create a "Pago Rechazado" activity on each individual payment assigned
       to its creator, so the tesorero is alerted to take corrective action.
    """

    _name = 'econovo.batch.reject.wizard'
    _description = 'Batch Payment Rejection Wizard'

    batch_id = fields.Many2one(
        'account.payment.batch.st',
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string='Motivo del rechazo',
        required=True,
        help='Describe the reason for rejection. This note will appear in the batch chatter.',
    )

    def action_confirm_rejection(self):
        """Cancel payment activities, post chatter note on batch, notify each payment creator."""
        self.ensure_one()
        batch = self.batch_id

        # 1. Cancel pending approval activities on each individual payment.
        for payment in batch.payment_ids:
            payment._cancel_approval_activities()

        # 2. Post rejection note on the batch chatter.
        batch.message_post(
            body=_(
                '<strong>⛔ Lote rechazado por %(approver)s</strong><br/>%(reason)s',
                approver=self.env.user.name,
                reason=self.reason,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        # 3. Create a "Pago Rechazado" activity on each payment for its creator.
        rejected_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_pago_rechazado',
            raise_if_not_found=False,
        )
        if rejected_type:
            for payment in batch.payment_ids:
                payment.activity_schedule(
                    activity_type_id=rejected_type.id,
                    summary=_('Pago rechazado — revisar y corregir'),
                    note=self.reason,
                    date_deadline=fields.Date.today(),
                    user_id=payment.create_uid.id,
                )

        return {'type': 'ir.actions.act_window_close'}
