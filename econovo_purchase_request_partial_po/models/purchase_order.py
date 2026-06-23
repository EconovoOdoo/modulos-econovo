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

        The check must exclude the lines belonging to the PO being confirmed
        from the "already booked" calculation. If the current PO's lines were
        included, the pending qty would appear as 0 (because this PO is the
        one supposed to cover the remaining qty), and the guard would still
        block the confirmation incorrectly.

        We only raise if the qty covered by *other* non-cancelled POs already
        equals or exceeds the requested qty (PR truly completed by others).
        """
        for po in self:
            for line in po.order_line:
                for request_line in line.purchase_request_lines:
                    rl = request_line.sudo()
                    if rl.purchase_state != "done":
                        continue
                    # Compute qty booked by OTHER POs (exclude current PO).
                    pr_uom = rl.product_uom_id or rl.product_id.uom_id
                    booked_by_others = 0.0
                    for po_line in rl.purchase_lines:
                        if po_line.state == "cancel":
                            continue
                        if po_line.order_id == po:
                            continue
                        l_uom = po_line.product_uom
                        if l_uom and pr_uom and l_uom != pr_uom:
                            booked_by_others += l_uom._compute_quantity(
                                po_line.product_qty, pr_uom
                            )
                        else:
                            booked_by_others += po_line.product_qty
                    pending = max(0.0, rl.product_qty - booked_by_others)
                    if pending <= 0.0:
                        raise UserError(
                            _(
                                "Purchase Request %s has already been completed"
                            )
                            % rl.request_id.name
                        )
        return True
