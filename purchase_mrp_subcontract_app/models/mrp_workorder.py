# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class WorkOrder(models.Model):
	_inherit='mrp.workorder'

	purchase_id = fields.Many2one('purchase.order', string="Purchase Order")
	picking_delivery_id = fields.Many2one('stock.picking', string="Receipt Picking ")
	picking_return_id = fields.Many2one('stock.picking', string="Return Picking")
	is_subcontract = fields.Boolean("Is Subcontract")

	def generate_subcontracting_order(self):
		if self.workcenter_id.is_subcontract:
			if not self.workcenter_id.picking_type_id.default_location_src_id and not self.workcenter_id.partner_id.property_stock_supplier:
				raise UserError(_("Please configure Default Source Location and Default Destination Location -> Inventory -> Operation Type"))
			if not self.workcenter_id.partner_id.property_stock_supplier:
				raise UserError(_('Please configure partner vendor location first.'))
			po_data = {
				'product_id' :self.workcenter_id.product_id.id,
				'product_uom' :self.workcenter_id.product_id.uom_po_id.id,
				'name':self.workcenter_id.product_id.name,
				'product_qty':self.qty_production,
				'price_subtotal':self.workcenter_id.cost, 
				'price_unit':self.workcenter_id.cost,
				'date_planned':fields.Date.today()}
			purchase_id = self.env['purchase.order'].create({'order_line':[(0,0,po_data)],
				'is_mo_order':True,
				'origin':self.production_id.name,
				'partner_id':self.workcenter_id.partner_id.id})
			self.purchase_id = purchase_id

			
			picking_line = {'name':self.product_id.name,
				'product_id':self.product_id.id,
				'location_id':self.workcenter_id.picking_type_id.default_location_src_id.id,
				'location_dest_id':self.workcenter_id.picking_type_id.default_location_dest_id.id,
				'product_uom_qty':self.qty_production,
				'reserved_availability':self.qty_production,
				'quantity_done':0.0,'product_uom':self.product_id.uom_po_id.id}

			picking_out_line = {'name':self.product_id.name,
				'product_id':self.product_id.id,
				'location_id':self.workcenter_id.return_type_id.default_location_src_id.id,
				'location_dest_id':self.workcenter_id.return_type_id.default_location_dest_id.id,
				'product_uom_qty':self.qty_production,
				'reserved_availability':self.qty_production,
				'quantity_done':0.0,'product_uom':self.product_id.uom_po_id.id}
			
			# picking depend on delivery picking type
			if self.workcenter_id.picking_type_id.code == 'incoming' and self.workcenter_id.picking_type_id.default_location_src_id:
				picking_data = {'move_ids_without_package':[(0,0,picking_line)],
					'picking_type_id': self.workcenter_id.picking_type_id.id,
					'state': 'draft',
					'origin':self.production_id.name,
					'location_id':self.workcenter_id.picking_type_id.default_location_src_id.id,
					'location_dest_id':self.workcenter_id.picking_type_id.default_location_dest_id.id,
					'origin':self.production_id.name,
					'partner_id':self.workcenter_id.partner_id.id,
					}
				picking = self.env['stock.picking'].create(picking_data)
				self.picking_delivery_id = picking

			
			if self.workcenter_id.picking_type_id.code == 'outgoing' and self.workcenter_id.picking_type_id.default_location_dest_id:
				picking_data = {'move_ids_without_package':[(0,0,picking_out_line)],
					'picking_type_id': self.workcenter_id.picking_type_id.id,
					'state': 'draft',
					'origin': _("Return of %s") % self.production_id.name,
					'location_id':self.workcenter_id.picking_type_id.default_location_dest_id.id,
					'location_dest_id':self.workcenter_id.picking_type_id.default_location_dest_id.id,
					'origin':self.production_id.name,
					'partner_id':self.workcenter_id.partner_id.id,
					}
				picking = self.env['stock.picking'].create(picking_data)
				self.picking_return_id = picking

			# picking depend on return type
			if self.workcenter_id.return_type_id.code == 'incoming' and self.workcenter_id.return_type_id.default_location_src_id:
				outgoing_picking = self.env['stock.picking'].create({'move_ids_without_package':[(0,0,picking_line)],
					'picking_type_id': self.workcenter_id.return_type_id.id,
					'state': 'draft',
					'origin':self.production_id.name,
					'location_id':self.workcenter_id.return_type_id.default_location_src_id.id,
					'location_dest_id':self.workcenter_id.picking_type_id.default_location_dest_id.id,
					'origin':self.production_id.name,
					'partner_id':self.workcenter_id.partner_id.id,
					})

				self.picking_delivery_id = outgoing_picking

			if self.workcenter_id.return_type_id.code == 'outgoing' and self.workcenter_id.return_type_id.default_location_dest_id:
				incoming_picking = self.env['stock.picking'].create({'move_ids_without_package':[(0,0,picking_out_line)],
					'picking_type_id': self.workcenter_id.return_type_id.id,
					'state': 'draft',
					'origin': _("Return of %s") % self.production_id.name,
					'location_id':self.workcenter_id.picking_type_id.default_location_dest_id.id,
					'location_dest_id':self.workcenter_id.return_type_id.default_location_dest_id.id,
					'origin':self.production_id.name,
					'partner_id':self.workcenter_id.partner_id.id,
					})
			
				self.picking_return_id = incoming_picking

			if self.purchase_id and self.picking_delivery_id and self.picking_return_id:
				self.write({'is_subcontract':self.workcenter_id.is_subcontract})
				self.production_id.write({'is_subcontract':self.workcenter_id.is_subcontract})
		else:
			raise UserError(_('Please configure MRP Subcontracting first.'))
