##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import api, fields, models


class StockBookPrinter(models.Model):
    _name = 'stock.book.printer'
    _description = 'Imprenta Autorizada de Talonario'

    name = fields.Char(
        string='Nombre Comercial',
        required=True,
        help='Nombre comercial de la imprenta (ej. TCLAS)',
    )
    legal_name = fields.Char(
        string='Razón Social',
        help='Razón social completa del titular',
    )
    phone = fields.Char(string='Teléfono / Cel.')
    vat = fields.Char(
        string='CUIT',
        help='CUIT de la imprenta en formato XX-XXXXXXXX-X',
    )
    gross_income = fields.Char(
        string='Ing. Brutos',
        help='Número de inscripción en Ingresos Brutos',
    )
    hab_mun = fields.Char(
        string='Hab. Municipal',
        help='Número de habilitación municipal',
    )
    print_date = fields.Date(
        string='Fecha de Impresión',
        help='Fecha en la que se imprimió el talonario físico',
    )
    copies_desc = fields.Char(
        string='Descripción de Copias',
        default='ORIGINAL(Blanco) DUPLICADO(Color) TRIPLICADO(Color)',
        help='Texto que describe las copias del talonario',
    )
    logo = fields.Binary(string='Logo')


class StockBook(models.Model):
    _inherit = 'stock.book'

    is_digital = fields.Boolean(
        string='Remito Digital',
        help='Activar para usar el template digital A4 al imprimir este talonario. '
             'Fuerza autoprinted=True automáticamente.',
    )
    sequence_start = fields.Char(
        string='Nro. Desde',
        help='Número inicial del rango autorizado por AFIP (ej. 00000101)',
    )
    sequence_end = fields.Char(
        string='Nro. Hasta',
        help='Número final del rango autorizado por AFIP (ej. 00000200)',
    )
    is_interwarehouse_company_transfer = fields.Boolean(
        string='Traslado entre Sucursales',
        help='Si está activo, el remito mostrará la leyenda '
             '"TRASLADO DE MERCADERIA ENTRE SUCURSALES".',
    )
    printer_id = fields.Many2one(
        'stock.book.printer',
        string='Imprenta',
        help='Datos de la imprenta autorizada que imprimió el talonario físico.',
        ondelete='restrict',
    )

    @api.onchange('is_digital')
    def _onchange_is_digital(self):
        if self.is_digital:
            self.autoprinted = True
