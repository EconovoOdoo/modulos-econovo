from odoo import models, fields

class WorkOrderLabelLayout(models.TransientModel):
    _inherit = 'mrp.workorder'

    production_date = fields.Datetime(string='Production Date')
    display_name = fields.Char(string='Display Name', related='name')
    production_id = fields.Many2one('mrp.production', string='Production ID')
    product_id = fields.Many2one('product.product', string='Product ID')
    needed_by_workorder_ids = fields.Many2many('mrp.workorder', string='Needed By Work Orders')
    blocked_by_workorder_ids = fields.Many2many('mrp.workorder', string='Blocked By Work Orders')
    quantity_produced = fields.Float(string='Quantity Produced')
    parent_product_id = fields.Many2one('product.product', string='Parent Product', related='product_id.product_tmpl_id')
    ancestor_product_ids = fields.Many2many('product.product', string='Ancestor Products', related='product_id.product_tmpl_id.ancestor_ids')

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        # Prepare additional data for the report
        data.update({
            'production_date': self.production_date,
            'display_name': self.display_name,
            'production_id': self.production_id.id,
            'product_id': self.product_id.id,
            'needed_by_workorder_ids': self.needed_by_workorder_ids.ids,
            'blocked_by_workorder_ids': self.blocked_by_workorder_ids.ids,
            'quantity_produced': self.quantity_produced,
            'parent_product_id': self.parent_product_id.id,
            'ancestor_product_ids': self.ancestor_product_ids.ids,
        })
        return xml_id, data