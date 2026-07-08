from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round


class StockSplitPicking(models.TransientModel):
    _inherit = "stock.split.picking"

    mode = fields.Selection(
        selection_add=[("counter", "Split by Count")],
        ondelete={"counter": "cascade"},
    )
    counter = fields.Integer(
        "Split Into #", default=0, compute="_compute_counter",
        store=True, readonly=False,
    )
    split_detail_ids = fields.One2many(
        "stock.split.picking.detail", "wizard_id", "Split Plan",
        compute="_compute_split_detail_ids", store=True, readonly=False,
    )
    valid_split_details = fields.Boolean("Valid", compute="_compute_valid_split_details")
    picking_count = fields.Integer("Transfer Count", compute="_compute_picking_count")

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for wizard in self:
            wizard.picking_count = len(wizard.picking_ids)

    @api.depends("split_detail_ids")
    def _compute_counter(self):
        for wizard in self:
            wizard.counter = len(wizard.split_detail_ids)

    @api.depends("counter")
    def _compute_split_detail_ids(self):
        for wizard in self:
            commands = [Command.clear()]
            moves = wizard._get_counter_moves()
            if wizard.counter < 1 or not moves:
                wizard.split_detail_ids = commands
                continue
            picking = wizard.picking_ids[:1]
            quantities_by_move = {
                move: wizard._split_quantities(
                    move.product_uom_qty, move.product_uom, wizard.counter
                )
                for move in moves
            }
            for index in range(wizard.counter):
                line_commands = [
                    Command.create({
                        "move_id": move.id,
                        "quantity": quantities_by_move[move][index],
                    })
                    for move in moves
                ]
                commands.append(Command.create({
                    "sequence": index + 1,
                    "user_id": picking.user_id.id,
                    "scheduled_date": picking.scheduled_date,
                    "line_ids": line_commands,
                }))
            wizard.split_detail_ids = commands

    @api.depends("mode", "split_detail_ids.line_ids.quantity")
    def _compute_valid_split_details(self):
        for wizard in self:
            wizard.valid_split_details = False
            if wizard.mode != "counter" or not wizard.split_detail_ids:
                continue
            moves = wizard._get_counter_moves()
            if not moves:
                continue
            all_valid = True
            for move in moves:
                lines = wizard.split_detail_ids.line_ids.filtered(lambda l: l.move_id == move)
                total = sum(lines.mapped("quantity"))
                if float_compare(total, move.product_uom_qty, precision_rounding=move.product_uom.rounding) != 0:
                    all_valid = False
                    break
            wizard.valid_split_details = all_valid

    def _get_counter_moves(self):
        self.ensure_one()
        if len(self.picking_ids) != 1:
            return self.env["stock.move"]
        return self.picking_ids.move_ids.filtered(lambda m: m.state not in ("done", "cancel"))

    @staticmethod
    def _split_quantities(total_qty, uom, counter):
        """Distribute ``total_qty`` into ``counter`` parts (rounding-safe: the
        remainder from the rounding of the first ``counter - 1`` parts is
        added to the last part, same approach as ``mrp.production.split``)."""
        quantity = float_round(total_qty / counter, precision_rounding=uom.rounding)
        quantities = [quantity] * (counter - 1)
        quantities.append(
            float_round(total_qty - quantity * (counter - 1), precision_rounding=uom.rounding)
        )
        return quantities

    def action_apply(self):
        if self.mode == "counter":
            return self._apply_counter()
        return super().action_apply()

    def _apply_counter(self):
        self.ensure_one()
        if len(self.picking_ids) != 1:
            raise UserError(_("Select exactly one transfer to use the split by count mode."))
        picking = self.picking_ids
        if picking.state in ("draft", "done", "cancel"):
            raise UserError(_(
                "The transfer must be confirmed, and not done or cancelled, "
                "before it can be split."
            ))
        if self.counter < 2:
            raise UserError(_("Enter a split count of at least 2."))
        moves = self._get_counter_moves()
        if not moves:
            raise UserError(_("There is nothing left to split on this transfer."))
        if not self.valid_split_details:
            raise UserError(_(
                "The split quantities must add up to the original demand for every product."
            ))

        details = self.split_detail_ids.sorted("sequence")
        new_pickings = self.env["stock.picking"]
        for _index in range(len(details) - 1):
            new_pickings |= picking._create_split_backorder()
        target_pickings = picking + new_pickings

        new_moves = self.env["stock.move"]
        for move in moves:
            remaining_move = move
            for target, detail in list(zip(target_pickings, details))[1:]:
                line = detail.line_ids.filtered(lambda l: l.move_id == move)
                qty = line.quantity if line else 0.0
                new_move_vals = remaining_move._split(qty)
                if not new_move_vals:
                    continue
                new_move = self.env["stock.move"].create(new_move_vals)
                new_move._action_confirm(merge=False)
                new_move.write({"picking_id": target.id})
                new_move.move_line_ids.write({"picking_id": target.id})
                new_moves |= new_move
            if float_is_zero(remaining_move.product_uom_qty, precision_rounding=remaining_move.product_uom.rounding):
                remaining_move._action_cancel()
                remaining_move.unlink()

        for target, detail in zip(target_pickings, details):
            target.write({
                "user_id": detail.user_id.id,
                "scheduled_date": detail.scheduled_date,
            })

        new_moves._action_assign()
        return self._picking_action(target_pickings)


class StockSplitPickingDetail(models.TransientModel):
    _name = "stock.split.picking.detail"
    _description = "Split Picking Detail (one resulting transfer)"
    _order = "sequence"

    wizard_id = fields.Many2one(
        "stock.split.picking", "Split Wizard", required=True, ondelete="cascade")
    sequence = fields.Integer("Split #", required=True)
    user_id = fields.Many2one("res.users", "Responsible")
    scheduled_date = fields.Datetime("Scheduled Date")
    line_ids = fields.One2many(
        "stock.split.picking.detail.line", "detail_id", "Quantities")


class StockSplitPickingDetailLine(models.TransientModel):
    _name = "stock.split.picking.detail.line"
    _description = "Split Picking Detail Line (quantity per product)"

    detail_id = fields.Many2one(
        "stock.split.picking.detail", "Split Detail", required=True, ondelete="cascade")
    move_id = fields.Many2one("stock.move", "Move", required=True, readonly=True)
    product_id = fields.Many2one(related="move_id.product_id", string="Product", readonly=True)
    product_uom = fields.Many2one(related="move_id.product_uom", string="Unit of Measure", readonly=True)
    quantity = fields.Float("Quantity", digits="Product Unit of Measure", required=True)
