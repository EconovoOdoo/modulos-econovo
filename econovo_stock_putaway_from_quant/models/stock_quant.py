from odoo import _, api, models
from odoo.exceptions import UserError


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def action_open_putaway(self):
        """
        Open the appropriate putaway wizard based on selection count.
        Single quant: Opens detailed wizard with existing rules preview.
        Multiple quants: Opens bulk creation wizard.
        """
        self.ensure_one() if len(self) == 1 else None

        if len(self) == 1:
            return self._action_open_putaway_single()
        else:
            return self._action_open_putaway_multi()

    def _action_open_putaway_single(self):
        """Open single quant putaway wizard with existing rules preview."""
        self.ensure_one()
        
        # Find the warehouse for this quant's location
        location_in_id = False
        warehouse = self.env['stock.warehouse'].search([
            ('lot_stock_id', 'parent_of', self.location_id.id),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if warehouse:
            location_in_id = warehouse.lot_stock_id.id
        else:
            # Fallback: find any warehouse for this company
            warehouse = self.env['stock.warehouse'].search([
                ('company_id', '=', self.company_id.id),
            ], limit=1)
            if warehouse:
                location_in_id = warehouse.lot_stock_id.id
        
        # Use context to pass defaults - standard Odoo pattern
        return {
            'name': 'Create Putaway Rule',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant.putaway.single',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                **self.env.context,
                'default_quant_id': self.id,
                'default_location_in_id': location_in_id,
            },
        }

    def _action_open_putaway_multi(self):
        """Open multi quant putaway wizard for bulk creation.
        
        Following portal.wizard pattern: create wizard first, then open it.
        This ensures lines are created before the form is displayed.
        """
        # Validate all quants belong to the same company
        companies = self.mapped('company_id')
        if len(companies) > 1:
            raise UserError(_(
                "Debe seleccionar productos cuya ubicación de stock actual "
                "pertenezca a una misma empresa.\n\n"
                "Empresas seleccionadas: %(companies)s",
                companies=', '.join(companies.mapped('name'))
            ))
        
        # Find the warehouse for the first quant's location
        location_in_id = False
        first_quant = self[0] if self else False
        if first_quant:
            warehouse = self.env['stock.warehouse'].search([
                ('lot_stock_id', 'parent_of', first_quant.location_id.id),
                ('company_id', '=', first_quant.company_id.id),
            ], limit=1)
            if warehouse:
                location_in_id = warehouse.lot_stock_id.id
            else:
                # Fallback: find any warehouse for this company
                warehouse = self.env['stock.warehouse'].search([
                    ('company_id', '=', first_quant.company_id.id),
                ], limit=1)
                if warehouse:
                    location_in_id = warehouse.lot_stock_id.id
        
        # Create wizard first with all line data (portal.wizard pattern)
        line_vals = []
        for quant in self:
            line_vals.append((0, 0, {
                'quant_id': quant.id,
                'location_out_id': quant.location_id.id,
                'selected': True,
            }))
        
        wizard = self.env['stock.quant.putaway.multi'].create({
            'company_id': first_quant.company_id.id if first_quant else False,
            'location_in_id': location_in_id,
            'line_ids': line_vals,
        })
        
        # Open the created wizard
        return {
            'name': 'Create Putaway Rules',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant.putaway.multi',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
