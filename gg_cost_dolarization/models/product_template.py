from odoo import models, fields, api
from datetime import datetime

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    standard_price_usd = fields.Float(
        string="Costo Estándar en USD",
        help="Costo estándar del producto en dólares estadounidenses (USD).",
        store=True
    )

    def write(self, vals):
        if 'standard_price' in vals:
            # Register a product price modification
            self.env['product.price.modification'].create({
                'date': fields.Datetime.now(),
                'user_id': self.env.user.id,
                'product_tmpl_id': self.id,
                'price': vals['standard_price'],
            })

            dolar_currency = self.env.ref('base.USD')
            now = datetime.now()
            dolar_quotation_with_date = self.env['res.currency.rate'].search(
                [('name', '<=', now),
                 ('currency_id', '=', dolar_currency.id)],
                order='name desc',
                limit=1
            )
            vals['standard_price_usd'] = vals['standard_price'] * (dolar_quotation_with_date.rate or 0.0)
            self.standard_price_usd = vals['standard_price_usd']
        res = super(ProductTemplate, self).write(vals)
        return res


class ProductProduct(models.Model):
    _inherit = 'product.product'

    standard_price_usd = fields.Float(
        string="Costo Estándar en USD",
        help="Costo estándar del producto en dólares estadounidenses (USD).",
        store=True
    )


    def write(self, vals):
        if 'standard_price' in vals:
            # Register a product price modification
            self.env['product.price.modification'].create({
                'date': fields.Datetime.now(),
                'user_id': self.env.user.id,
                'product_id': self.id,
                'price': vals['standard_price'],
            })
            dolar_currency = self.env.ref('base.USD')
            now = datetime.now()
            dolar_quotation_with_date = self.env['res.currency.rate'].search(
                [('name', '<=', now),
                 ('currency_id', '=', dolar_currency.id)],
                order='name desc',
                limit=1
            )
            vals['standard_price_usd'] = vals['standard_price'] * (dolar_quotation_with_date.rate or 0.0)
            self.standard_price_usd = vals['standard_price_usd']
            self.product_tmpl_id.write({'standard_price_usd': vals['standard_price_usd']})
        res = super(ProductProduct, self).write(vals)
        return res