# Econovo Remito Digital

Remito digital A4 para Argentina (talonarios digitalizados con CAI).

## Características

- Layout A4 con paginación automática y pie fijo en la parte inferior de cada página.
- Encabezado con datos del remitente, destinatario, CAI/CAE y código de barras del talonario.
- Pie con código de barras del remito, datos de imprenta y vencimiento de CAI.
- Plantilla QWeb basada en el patrón oficial `web.external_layout_standard` (sibling
  `<div class="article">` + `<div class="footer">`), de modo que wkhtmltopdf extraiga el
  footer mediante `--footer-html` y lo posicione siempre al pie de cada página.

## Configuración del Paperformat

El reporte usa un `report.paperformat` propio (`paperformat_remito_digital`) con
`margin_bottom = 55` mm para reservar espacio suficiente al footer renderizado por
wkhtmltopdf 0.12.x (QtWebKit 2.2) en Windows y Linux.

**No** se utiliza el campo `footer_spacing` porque no existe en el modelo
`report.paperformat` en Odoo 17. El margen inferior del paperformat es lo único
necesario para reservar espacio bajo el footer.

## ⚠️ Consideración para desarrollo local en Windows

Si el nombre de usuario de Windows contiene un punto (por ejemplo `j.leonett`), el
footer **no se renderizará** en el PDF generado localmente por wkhtmltopdf.

### Causa raíz

Odoo, al invocar wkhtmltopdf, escribe el HTML del footer en un archivo temporal
con ruta del tipo:

```
C:\Users\<usuario>\AppData\Local\Temp\report.body.tmp.0.<hash>.html
```

La plantilla `web.minimal_layout` (en `web/views/webclient_templates.xml`) contiene
JavaScript que ejecuta:

```js
var index = vars['webpage'].split('.', 4)[3];
var footer = document.getElementById('minimal_layout_report_footers');
if (footer) {
    var companyFooter = footer.children[index];
    footer.textContent = '';
    footer.appendChild(companyFooter);
}
```

El propósito de ese código es elegir el footer correcto por índice
(`report.body.tmp.0.<hash>` → `split('.', 4)[3] === '0'`). Cuando el usuario
contiene un punto, el `split('.', 4)` se rompe antes de llegar al índice numérico
y devuelve `'tmp'`, lo que produce `footer.children['tmp'] === undefined`. El
`textContent = ''` vacía el contenedor y `appendChild(undefined)` lanza una
excepción, dejando el PDF sin footer.

### Impacto

- **Solo afecta** instalaciones locales de desarrollo en Windows cuyo nombre de
  usuario contiene un punto.
- **Odoo.sh (Linux) no se ve afectado**: las rutas son `/tmp/report.body.tmp.0.<hash>.html`
  y el split funciona correctamente.

### Workaround local

Antes de iniciar Odoo, redirigir `TEMP`/`TMP` a una carpeta sin puntos en su ruta:

```powershell
Set-Location D:\Odoo\ODOO-SRC\odoo-17e
New-Item -ItemType Directory -Force -Path C:\OdooTmp | Out-Null
$env:TEMP = "C:\OdooTmp"
$env:TMP  = "C:\OdooTmp"
.\venv-ee\Scripts\python.exe -m odoo -c odoo-ee.conf
```

Con esta configuración wkhtmltopdf escribe los temporales en
`C:\OdooTmp\report.body.tmp.0.<hash>.html` y el footer se renderiza correctamente.
