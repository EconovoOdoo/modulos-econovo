# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, models
from odoo.exceptions import UserError


class PurchaseRequestLineMakePurchaseOrder(models.TransientModel):
    _inherit = "purchase.request.line.make.purchase.order"

    @api.model
    def _check_valid_request_line(self, request_line_ids):
        """Relax the "already completed" gate when pending qty still remains.

        The original OCA check blocks the wizard whenever
        ``line.request_id.state == 'done'`` or
        ``line.purchase_state == 'done'``. That is too strict for these
        legitimate multi-supplier scenarios:

        * Company has ``po_lock = 'lock'``: confirming the first PO moves it
          straight to ``done`` (Locked), turning ``purchase_state`` to
          ``'done'`` even though the qty is not received and a second PO is
          still required to fulfil the request.
        * The PR was manually marked Done while some lines still had qty
          pending.

        The rest of the original validations (state allowlist, single
        company, single picking type) are preserved.
        """
        PRLine = self.env["purchase.request.line"]
        picking_type = False
        company_id = False
        # ``in_progress`` is added by an Econovo customization layer that
        # extends the OCA selection; we accept it just like ``approved``.
        allowed_states = ("approved", "in_progress", "done")

        for line in PRLine.browse(request_line_ids):
            pending = line._get_pending_qty_to_purchase()

            if line.request_id.state not in allowed_states:
                raise UserError(
                    _("Purchase Request %s is not approved or in progress")
                    % line.request_id.name
                )

            if line.request_id.state == "done" and pending <= 0.0:
                raise UserError(_("The purchase has already been completed."))

            if line.purchase_state == "done" and pending <= 0.0:
                raise UserError(_("The purchase has already been completed."))

            line_company_id = line.company_id.id if line.company_id else False
            if company_id is not False and line_company_id != company_id:
                raise UserError(
                    _("You have to select lines from the same company.")
                )
            company_id = line_company_id

            line_picking_type = line.request_id.picking_type_id or False
            if not line_picking_type:
                raise UserError(_("You have to enter a Picking Type."))
            if picking_type is not False and line_picking_type != picking_type:
                raise UserError(
                    _("You have to select lines from the same Picking Type.")
                )
            picking_type = line_picking_type

    @api.model
    def _prepare_item(self, line):
        """Pre-fill the wizard with the real pending qty.

        OCA uses ``line.pending_qty_to_receive`` which only subtracts
        received qty; we use ``_get_pending_qty_to_purchase`` so that qty
        already booked on active PO lines is subtracted too.
        """
        res = super()._prepare_item(line)
        res["product_qty"] = line._get_pending_qty_to_purchase()
        return res

    @api.model
    def get_items(self, request_line_ids):
        """Exclude PR lines that are cancelled or fully purchased.

        Prevents the wizard from showing rows with qty 0 when the user
        opens it from the PR header (which sends every line of the PR).
        """
        PRLine = self.env["purchase.request.line"]
        eligible_ids = [
            line.id
            for line in PRLine.browse(request_line_ids)
            if not line.cancelled
            and line._get_pending_qty_to_purchase() > 0.0
        ]
        if not eligible_ids:
            raise UserError(
                _(
                    "All selected purchase request lines are already fully "
                    "purchased or cancelled. Nothing to add to a new RFQ."
                )
            )
        return super().get_items(eligible_ids)
