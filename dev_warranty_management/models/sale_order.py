# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class sale_order(models.Model):
    _inherit = 'sale.order'
    
    warranty_flag = fields.Boolean(string='Warranty Created',copy=False)
    warranty_count = fields.Integer(string='Warranty', compute='_warranty_count')
    warranty_ids = fields.One2many('warranty.warranty','sale_id',string='Warranty')
    
    def _warranty_count(self):
        for data in self:
            warranty_ids = self.env['warranty.warranty'].search([('sale_id','=',self.id)])
            data.warranty_count = len(warranty_ids)
    
#    @api.model
    def action_confirm(self):
        res = super(sale_order, self).action_confirm()
        for data in self:
            for line in data.order_line:
                if line.product_id.allow_warranty:
                    warranty_data = {'customer_id':self.partner_id and self.partner_id.id,
                                      'sale_id':self.id,
                                      'product_id':line.product_id.id,
                                     }
                    warranty_id = self.env['warranty.warranty'].create(warranty_data)
                    warranty_id.onchange_customer_id()
                    warranty_id.onchange_sale_id()
                    warranty_id.onchange_product_id()
                    self.warranty_flag = True
        return res    
        

    def action_view_warranty(self):
        warranty_ids = self.env['warranty.warranty'].search([('sale_id','=',self.id)])
        action = self.env.ref('dev_warranty_management.action_warranty_warranty').read()[0]
        if len(warranty_ids) > 1:
            action['domain'] = [('id', 'in', warranty_ids.ids)]
        else:
            action['views'] = [(self.env.ref('dev_warranty_management.form_warranty_warranty').id, 'form')]
            action['res_id'] = warranty_ids.id
        return action
   
   
        
