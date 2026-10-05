##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import format_date
from odoo.tools.safe_eval import safe_eval


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
    copies_desc = fields.Char(
        string='Descripción de Copias',
        default='ORIGINAL(Blanco) DUPLICADO(Color) TRIPLICADO(Color)',
        help='Texto que describe las copias del talonario',
    )
    logo = fields.Binary(string='Logo')


class StockBook(models.Model):
    _inherit = 'stock.book'

    active = fields.Boolean(
        default=True,
        help='Talonarios archivados (CAI vencido o secuencias agotadas) se '
             'ocultan al asignar libro a un picking.',
    )
    is_digital = fields.Boolean(
        string='Remito Digital',
        help='Activar para usar el template digital A4 al imprimir este talonario. '
             'Fuerza autoprinted=True automáticamente.',
    )
    copies_mode = fields.Selection(
        selection=[
            ('original', 'Solo Original'),
            ('duplicate', 'Original + Duplicado'),
            ('triplicate', 'Original, Duplicado y Triplicado'),
            ('quadruplicate', 'Original, Duplicado, Triplicado y Cuadruplicado'),
        ],
        string='Copias a Imprimir',
        default='original',
        required=True,
        help='Cantidad de copias que se generarán en el PDF del remito digital, '
             'cada una identificada con su leyenda (ORIGINAL, DUPLICADO, etc.) '
             'siguiendo el estilo de los comprobantes oficiales de AFIP.',
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
    print_date = fields.Date(
        string='Fecha de Impresión',
        help='Fecha en la que la imprenta imprimió este talonario físico. '
             'Es propiedad del talonario porque una misma imprenta puede '
             'imprimir distintos talonarios en fechas distintas.',
    )
    print_date_display = fields.Char(
        string='Fecha de Impresión (texto)',
        compute='_compute_print_date_display',
    )
    remito_footer_active = fields.Boolean(
        string='Pie de remito activo',
        default=False,
        help='Si está activo, el texto configurado se imprime en el pie del PDF '
             'del remito digital cuando el dominio coincide con el picking.',
    )
    remito_footer_text = fields.Html(
        string='Texto del pie de remito',
        sanitize=False,
        help='Texto HTML o plano que se mostrará en el pie del remito digital al '
             'imprimir, solo cuando aplique el dominio configurado.',
    )
    remito_footer_domain = fields.Char(
        string='Dominio de aplicación',
        default='[]',
        help='Dominio de Odoo evaluado sobre el picking. Si coincide, se imprime '
             'el texto del pie. Ejemplo: [("partner_id.country_id.code", "=", '
             '"AR")]',
    )

    @api.constrains('remito_footer_domain')
    def _check_remito_footer_domain(self):
        for record in self:
            if not record.remito_footer_domain:
                continue
            try:
                safe_eval(record.remito_footer_domain, mode='eval')
            except Exception as exc:
                raise ValidationError(_(
                    'Dominio del pie del remito inválido: %s', exc,
                )) from exc

    @api.depends('print_date')
    def _compute_print_date_display(self):
        for record in self:
            record.print_date_display = (
                format_date(self.env, record.print_date, date_format='dd MMMM yyyy')
                if record.print_date else ''
            )

    @api.onchange('is_digital')
    def _onchange_is_digital(self):
        if self.is_digital:
            self.autoprinted = True

    def _get_remito_copies_labels(self):
        """Return the ordered list of copy legends to print in the PDF.

        Mirrors the AFIP style used on official printed vouchers (e.g.
        'ORIGINAL', 'DUPLICADO'): every copy gets its own full set of pages,
        each one bearing the corresponding legend. Controlled by
        copies_mode. Safe to call on an empty recordset (falls back to a
        single 'ORIGINAL' copy, e.g. when no book is assigned yet).
        """
        all_labels = [_('ORIGINAL'), _('DUPLICADO'), _('TRIPLICADO'), _('CUADRUPLICADO')]
        if not self:
            return all_labels[:1]
        self.ensure_one()
        copies_by_mode = {
            'original': 1,
            'duplicate': 2,
            'triplicate': 3,
            'quadruplicate': 4,
        }
        return all_labels[:copies_by_mode.get(self.copies_mode, 1)]
