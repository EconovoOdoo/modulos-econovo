# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models


class PurchaseRequestLine(models.Model):
    _inherit = "purchase.request.line"

    def _get_pending_qty_to_purchase(self):
        """Return the qty still pending to be ordered, in the PR line's UoM.

        Unlike the stock ``pending_qty_to_receive`` field (which only
        subtracts physically received qty tracked via allocations), this
        method also subtracts qty already booked on non-cancelled PO lines,
        regardless of whether allocations were created.

        This is the reliable measure of "what still needs to be purchased"
        when:

        * POs are auto-locked by ``res.company.po_lock = 'lock'``.
        * POs were generated from ``stock.rule`` / Manufacturing Orders and
          therefore have no ``purchase.request.allocation`` records.
        * The user manually edited PO line quantities.

        Formula::

            max(0, product_qty - sum(active po_line.product_qty in PR UoM))
        """
        self.ensure_one()
        pr_uom = self.product_uom_id or self.product_id.uom_id
        booked_qty = 0.0
        for po_line in self.purchase_lines:
            if po_line.state == "cancel":
                continue
            line_uom = po_line.product_uom
            if line_uom and pr_uom and line_uom != pr_uom:
                booked_qty += line_uom._compute_quantity(
                    po_line.product_qty, pr_uom
                )
            else:
                booked_qty += po_line.product_qty
        return max(0.0, self.product_qty - booked_qty)
