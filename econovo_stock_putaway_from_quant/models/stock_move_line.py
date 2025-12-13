from odoo import _, api, models
from odoo.exceptions import UserError


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def action_open_putaway(self):
        """
        Open putaway wizard from move lines in detailed operations.
        Only available for incoming pickings (receipts).
        """
        if not self:
            return

        # Validate all move lines are from incoming pickings
        for line in self:
            if not line.picking_id:
                raise UserError(_(
                    "La línea '%(product)s' no está asociada a una operación de picking.",
                    product=line.product_id.display_name,
                ))
            if line.picking_id.picking_type_id.code != 'incoming':
                raise UserError(_(
                    "Esta acción solo está disponible para operaciones de recepción.\n\n"
                    "El picking '%(picking)s' es de tipo '%(type)s'.",
                    picking=line.picking_id.name,
                    type=line.picking_id.picking_type_id.name,
                ))

        # Validate all lines are from the same company
        companies = self.mapped('company_id')
        if len(companies) > 1:
            raise UserError(_(
                "Debe seleccionar líneas de la misma empresa.\n\n"
                "Empresas seleccionadas: %(companies)s",
                companies=', '.join(companies.mapped('name'))
            ))

        # Validate all lines are from the same picking
        pickings = self.mapped('picking_id')
        if len(pickings) > 1:
            raise UserError(_(
                "Debe seleccionar líneas del mismo picking.\n\n"
                "Pickings seleccionados: %(pickings)s",
                pickings=', '.join(pickings.mapped('name'))
            ))

        picking = pickings[0]
        company = companies[0] if companies else self.env.company

        # location_in_id = picking destination (e.g., WH/Stock)
        location_in_id = picking.location_dest_id.id

        # Create wizard with line data (portal.wizard pattern)
        line_vals = []
        for move_line in self:
            line_vals.append((0, 0, {
                'move_line_id': move_line.id,
                'location_out_id': move_line.location_dest_id.id,
                'selected': True,
            }))

        wizard = self.env['stock.move.line.putaway'].create({
            'picking_id': picking.id,
            'company_id': company.id,
            'location_in_id': location_in_id,
            'line_ids': line_vals,
        })

        return {
            'name': _('Create Putaway Rules'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move.line.putaway',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
