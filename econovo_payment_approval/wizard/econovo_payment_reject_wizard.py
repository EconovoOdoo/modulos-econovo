from markupsafe import Markup
from odoo import _, fields, models


class EconovoPaymentRejectWizard(models.TransientModel):
    """Wizard that lets an approver reject a payment with a mandatory reason.

    Steps performed on confirmation:
    1. Cancel all pending "Revisar Pago" activities on the payment (or its batch).
    2. Post a rejection note to the payment chatter so it is auditable.
    3. Create a "Pago Rechazado" activity assigned to the original payment creator
       so the tesorero is alerted and can take corrective action.
    """

    _name = 'econovo.payment.reject.wizard'
    _description = 'Payment Rejection Wizard'

    payment_id = fields.Many2one(
        'account.payment',
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string='Motivo del rechazo',
        required=True,
        help='Describe the reason for rejecting this payment. This note will appear in the chatter.',
    )

    def action_confirm_rejection(self):
        """Process the rejection: cancel activities, post chatter note, notify tesorero."""
        self.ensure_one()
        payment = self.payment_id

        # 1. Cancel pending approval activities.
        payment._cancel_approval_activities()

        # 2. Post an auditable rejection note to the chatter.
        payment.message_post(
            body=Markup('<strong>\u26d4 Pago rechazado por {approver}</strong><br/>{reason}').format(
                approver=self.env.user.name,
                reason=self.reason,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        # 3. Create a "Pago Rechazado" activity for the tesorero (payment creator).
        rejected_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_pago_rechazado',
            raise_if_not_found=False,
        )
        if rejected_type:
            payment.activity_schedule(
                activity_type_id=rejected_type.id,
                summary=_('Pago rechazado — revisar y corregir'),
                note=self.reason,
                date_deadline=fields.Date.today(),
                user_id=payment.create_uid.id,
            )

        return {'type': 'ir.actions.act_window_close'}
