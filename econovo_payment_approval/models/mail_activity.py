import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Only the two *approval* activity types are protected.
# Rejection notification types (pago_rechazado / asiento_rechazado) are
# intentionally excluded: they are assigned back to the document creator so
# they can acknowledge the rejection freely.
_PROTECTED_XML_IDS = (
    'econovo_payment_approval.mail_activity_type_revisar_pago',
    'econovo_payment_approval.mail_activity_type_aprobar_asiento',
)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def action_feedback(self, feedback=False, attachment_ids=None):
        """Block non-assigned users from completing approval activities.

        The native Odoo chatter popup exposes a 'Mark as Done' button that
        calls this method directly, bypassing action_approve() and its
        user_id == uid guard.  This override restores that guard at the
        mail.activity level so that only the assigned approver can mark an
        approval activity as done, regardless of the UI path used.
        """
        protected_type_ids = {
            record.id
            for xml_id in _PROTECTED_XML_IDS
            for record in [self.env.ref(xml_id, raise_if_not_found=False)]
            if record
        }
        if not protected_type_ids:
            return super().action_feedback(
                feedback=feedback, attachment_ids=attachment_ids
            )

        for activity in self:
            if (
                activity.activity_type_id.id in protected_type_ids
                and activity.user_id.id != self.env.uid
            ):
                raise UserError(
                    _(
                        'Solo el aprobador asignado (%s) puede completar '
                        'esta actividad de aprobación.',
                        activity.user_id.name,
                    )
                )

        return super().action_feedback(
            feedback=feedback, attachment_ids=attachment_ids
        )
