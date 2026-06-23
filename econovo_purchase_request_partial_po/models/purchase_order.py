# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _purchase_request_line_check(self):
        """Relax the "already completed" gate when pending qty still remains.

        The OCA implementation blocks ``button_confirm`` whenever any linked
        purchase request line has ``purchase_state == 'done'``. That is too
        strict when a single PR is fulfilled by multiple POs (multi-supplier
        split), because confirming the first PO can set ``purchase_state``
        to ``'done'`` on the PR line even though a second PO is still
        required to cover the remaining quantity.

        We only block if *all* linked PR lines have no pending qty left.
        """
        for po in self:
            for line in po.order_line:
                for request_line in line.purchase_request_lines:
                    rl = request_line.sudo()
                    if rl.purchase_state == "done":
                        pending = rl._get_pending_qty_to_purchase()
                        if pending <= 0.0:
                            raise UserError(
                                _(
                                    "Purchase Request %s has already been completed"
                                )
                                % rl.request_id.name
                            )
        return True
