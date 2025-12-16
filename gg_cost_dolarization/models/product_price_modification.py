from odoo import models, fields

class ProductPriceModification(models.Model):
    _name = 'product.price.modification'

    price = fields.Float(
        string="Nuevo costo",
        help="Nuevo costo del producto",
        required=True,
        copy=False
    )

    date = fields.Datetime(
        string="Fecha y Hora de Modificación",
        default=fields.Datetime.now,
        help="Fecha y hora en que se realizó la modificación del precio.",
        required=True,
        index=True,
        copy=False
    )

    user_id = fields.Many2one(
        'res.users',
        string="Usuario que Modificó",
        default=lambda self: self.env.user,
        help="Usuario que realizó la modificación del precio.",
        required=True,
        copy=False,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string="Producto Modificado",
        help="Producto cuyo precio fue modificado.",
        required=False,
        copy=False,
        ondelete='cascade'
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string="Producto Modificado",
        help="Producto cuyo precio fue modificado.",
        required=False,
        copy=False,
        ondelete='cascade'
    )