from markupsafe import Markup
from odoo import _, fields, models


class EconovoMoveRejectWizard(models.TransientModel):
    """Wizard that lets an approver reject a journal entry with a mandatory reason.

    Steps performed on confirmation:
    1. Cancel all pending "Aprobar Asiento" activities on the entry.
    2. Post a rejection note to the chatter so it is auditable.
    3. Create an "Asiento Rechazado" activity assigned to the original entry creator
       so the accountant is alerted and can take corrective action.
    """

    _name = 'econovo.move.reject.wizard'
    _description = 'Journal Entry Rejection Wizard'

    move_id = fields.Many2one(
        'account.move',
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string='Motivo del rechazo',
        required=True,
        help='Describe the reason for rejecting this entry. This note will appear in the chatter.',
    )

    def action_confirm_rejection(self):
        """Process the rejection: cancel activities, post chatter note, notify creator."""
        self.ensure_one()
        move = self.move_id

        # 1. Cancel pending approval activities.
        move._cancel_approval_activities()

        # 2. Post an auditable rejection note to the chatter.
        move.message_post(
            body=Markup('<strong>\u26d4 Asiento rechazado por {approver}</strong><br/>{reason}').format(
                approver=self.env.user.name,
                reason=self.reason,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        # 3. Create an "Asiento Rechazado" activity for the entry creator.
        rejected_type = self.env.ref(
            'econovo_payment_approval.mail_activity_type_asiento_rechazado',
            raise_if_not_found=False,
        )
        if rejected_type:
            move.activity_schedule(
                activity_type_id=rejected_type.id,
                summary=_('Asiento rechazado — revisar y corregir'),
                note=self.reason,
                date_deadline=fields.Date.today(),
                user_id=move.create_uid.id,
            )

        return {'type': 'ir.actions.act_window_close'}
