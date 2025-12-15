# Plan Detallado: Modulo econovo_stock_quant_count_history

## Informacion General

| Campo | Valor |
|-------|-------|
| **Nombre Técnico** | `econovo_stock_quant_count_history` |
| **Nombre Funcional** | Historial de Conteos de Inventario |
| **Versión Odoo** | 17.0 |
| **Autor** | Jose D. Leonett |
| **Website** | https://github.com/josedleonett |
| **Licencia** | AGPL-3 |
| **Categoría** | Inventory/Inventory |
| **Dependencias** | `stock` |
| **Idiomas** | Inglés (base), Español Argentina (es_AR) |

---

## Objetivo del Modulo

**Proposito Principal**: Llevar un registro de cantidades contadas, tanto **APLICADAS** como **NO APLICADAS**.

### Problema que Resuelve

En Odoo 17 estandar:
- Si un usuario cuenta el inventario y la cantidad es igual, NO hay registro
- No se puede auditar quien conto que y cuando
- No hay trazabilidad de conteos sin diferencias
- No se puede guardar un conteo para referencia sin aplicarlo

### Solucion Propuesta

- Registrar conteos automaticamente al presionar **"Aplicar"**
- Registrar conteos manualmente con boton **"Guardar cantidad contada en historial"**
- Historial incluye conteos **APLICADOS y NO APLICADOS**
- Boton dedicado **"Conteos"** para ver historial por linea (similar al de ajustes)
- UI con componentes **100% nativos de Odoo** (patrones estandar)
- Soporte **i18n** con espanol Argentina (es_AR)
- **Codigo no invasivo** para facilitar migracion a Odoo 18+

---

## Flujos de Registro de Conteos

### Cuando se registra un conteo?

| Accion del Usuario | Se registra? | Estado del Registro |
|--------------------|--------------|---------------------|
| Clic en **"Establecer"** | NO | Solo habilita edicion |
| Clic en **"Guardar cantidad contada en historial"** (nuevo boton) | SI (manual) | `saved` (guardado) |
| Clic en **"Aplicar"** | SI (automatico) | `applied` (aplicado) |
| Clic en **"Limpiar"** | NO | No hay nada que registrar |

### Flujo Visual

```
+------------------------------------------------------------------------------+
|  USUARIO en vista "Ajustes de Inventario"                                    |
+------------------------------------------------------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
    [Establecer]          [Guardar en Historial]        [Aplicar]
            |                       |                       |
            v                       v                       v
    Solo habilita             Crea registro           Crea registro
    edicion (NO registra)     state='saved'           state='applied'
```

---

## Arquitectura del Modulo

### Principios de Diseno

1. **Codigo no invasivo**: Usar herencia y extension, NO modificar metodos base
2. **Minima dependencia**: Solo depender del modulo `stock`
3. **Facil migracion**: Evitar hacks o parches monkey-patching
4. **Patrones Odoo**: Seguir convenciones OCA y Odoo estandar

### Estrategia de Integracion (No Invasiva)

```python
# EN LUGAR DE sobrescribir action_apply_inventory:
class StockQuant(models.Model):
    _inherit = 'stock.quant'
    
    # CORRECTO: Extender sin romper funcionalidad base
    def action_apply_inventory(self):
        # Capturar valores ANTES de aplicar
        vals_to_save = self._prepare_count_history_values()
        
        # Llamar al metodo original SIN MODIFICARLO
        result = super().action_apply_inventory()
        
        # Crear historial DESPUES de aplicar exitosamente
        if vals_to_save:
            self.env['stock.quant.count.history'].create(vals_to_save)
        
        return result
```

### Estructura de Archivos

```
econovo_stock_quant_count_history/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── stock_quant_count_history.py    # Modelo principal de historial
│   └── stock_quant.py                   # Herencia de stock.quant
├── security/
│   ├── ir.model.access.csv
│   └── stock_quant_count_history_security.xml
├── views/
│   ├── stock_quant_count_history_views.xml
│   ├── stock_quant_count_history_menus.xml
│   └── stock_quant_views.xml            # Herencia de vistas de quant
├── i18n/
│   ├── es_AR.po                          # Traduccion espanol Argentina
│   └── econovo_stock_quant_count_history.pot  # Template de traducciones
└── README.md
```

---

## Modelo de Datos

### Modelo Principal: stock.quant.count.history

| Campo | Tipo | Descripcion | Requerido | Indice |
|-------|------|-------------|-----------|--------|
| `name` | Char | Secuencia automatica (CNT/0001) | Si | Si |
| `company_id` | Many2one -> res.company | Empresa del conteo | Si | Si |
| `quant_id` | Many2one -> stock.quant | Quant contado | No* | Si |
| `product_id` | Many2one -> product.product | Producto | Si | Si |
| `location_id` | Many2one -> stock.location | Ubicacion | Si | Si |
| `warehouse_id` | Many2one -> stock.warehouse | Almacen (computed) | No | Si |
| `lot_id` | Many2one -> stock.lot | Lote/Serie | No | Si |
| `package_id` | Many2one -> stock.quant.package | Paquete | No | No |
| `owner_id` | Many2one -> res.partner | Propietario | No | No |
| `quantity_on_hand` | Float | Cantidad en mano al momento del conteo | Si | No |
| `quantity_counted` | Float | Cantidad contada por el usuario | Si | No |
| `difference` | Float | Diferencia (computed stored) | Si | No |
| `user_id` | Many2one -> res.users | Usuario que realizo el conteo | Si | Si |
| `count_datetime` | Datetime | Fecha y hora del conteo | Si | Si |
| `state` | Selection | Estado del conteo | Si | Si |
| `was_applied` | Boolean | Se aplico un ajuste? | Si | No |
| `notes` | Text | Notas/comentarios del usuario | No | No |
| `product_uom_id` | Many2one -> uom.uom | Unidad de medida | No | No |

*quant_id puede ser nulo si el quant fue eliminado

#### Estados del Conteo (state)

| Estado | Etiqueta | Descripcion |
|--------|----------|-------------|
| `saved` | Saved | Registrado manualmente con boton dedicado |
| `applied` | Applied | El conteo fue aplicado (automatico al aplicar ajuste) |

---

## Vistas y UI/UX (Componentes Nativos Odoo)

### 1. Boton "Conteos" en Vista de Ajustes de Inventario

Se anadira un boton **junto al boton "Historial" existente**, con el mismo estilo:

```xml
<!-- Patron similar al boton Historial nativo de Odoo -->
<button name="action_view_count_history" type="object" 
        class="btn-link" icon="fa-clock-o"
        string="Counts"/>
```

**Visualizacion en la fila:**
```
+----------------------------------------------------------------------------------------------+
| Producto     | Cantidad | Contado | Diferencia | Usuario | [Historial] [Conteos] | ...      |
+----------------------------------------------------------------------------------------------+
```

### 2. Boton "Guardar cantidad contada en historial"

Nuevo boton en la columna de acciones, visible solo cuando `inventory_quantity_set = True`:

```xml
<button name="action_save_count_to_history" type="object"
        class="btn btn-secondary btn-sm"
        icon="fa-save"
        title="Save counted quantity to history"
        invisible="not inventory_quantity_set"/>
```

### 3. Vista Tree del Historial de Conteos

```xml
<!-- Patron estandar Odoo: tree view con filtros y agrupaciones -->
<tree string="Count History">
    <field name="name"/>
    <field name="count_datetime"/>
    <field name="product_id"/>
    <field name="location_id"/>
    <field name="quantity_on_hand"/>
    <field name="quantity_counted"/>
    <field name="difference" decoration-danger="difference &lt; 0" 
           decoration-success="difference == 0"/>
    <field name="state" widget="badge" 
           decoration-warning="state == 'saved'"
           decoration-success="state == 'applied'"/>
    <field name="user_id" widget="many2one_avatar_user"/>
</tree>
```

### 4. Vista Form del Registro de Conteo

```xml
<!-- Patron estandar Odoo: form con header y grupos -->
<form string="Inventory Count">
    <header>
        <field name="state" widget="statusbar" 
               statusbar_visible="saved,applied"/>
    </header>
    <sheet>
        <div class="oe_title">
            <h1><field name="name"/></h1>
        </div>
        <group>
            <group string="Product">
                <field name="product_id"/>
                <field name="lot_id"/>
                <field name="package_id"/>
            </group>
            <group string="Location">
                <field name="location_id"/>
                <field name="warehouse_id"/>
                <field name="company_id" groups="base.group_multi_company"/>
            </group>
        </group>
        <group>
            <group string="Quantities">
                <field name="quantity_on_hand"/>
                <field name="quantity_counted"/>
                <field name="difference"/>
                <field name="product_uom_id"/>
            </group>
            <group string="Audit">
                <field name="user_id"/>
                <field name="count_datetime"/>
                <field name="was_applied"/>
            </group>
        </group>
        <group string="Notes">
            <field name="notes" nolabel="1" placeholder="Additional notes..."/>
        </group>
    </sheet>
</form>
```

### 5. Filtros de Busqueda (search view)

```xml
<search string="Search Counts">
    <field name="name"/>
    <field name="product_id"/>
    <field name="location_id"/>
    <field name="user_id"/>
    <separator/>
    <filter name="today" string="Today" 
            domain="[('count_datetime', '>=', datetime.datetime.combine(context_today(), datetime.time(0,0,0)))]"/>
    <filter name="this_week" string="This Week" 
            domain="[('count_datetime', '>=', (context_today() - relativedelta(days=context_today().weekday())).strftime('%Y-%m-%d'))]"/>
    <filter name="this_month" string="This Month"
            domain="[('count_datetime', '>=', context_today().strftime('%Y-%m-01'))]"/>
    <separator/>
    <filter name="my_counts" string="My Counts" 
            domain="[('user_id', '=', uid)]"/>
    <filter name="with_difference" string="With Difference" 
            domain="[('difference', '!=', 0)]"/>
    <filter name="applied" string="Applied" 
            domain="[('state', '=', 'applied')]"/>
    <filter name="saved" string="Saved" 
            domain="[('state', '=', 'saved')]"/>
    <separator/>
    <group expand="0" string="Group By">
        <filter name="group_user" string="User" context="{'group_by': 'user_id'}"/>
        <filter name="group_product" string="Product" context="{'group_by': 'product_id'}"/>
        <filter name="group_location" string="Location" context="{'group_by': 'location_id'}"/>
        <filter name="group_warehouse" string="Warehouse" context="{'group_by': 'warehouse_id'}"/>
        <filter name="group_date" string="Date" context="{'group_by': 'count_datetime:day'}"/>
        <filter name="group_state" string="State" context="{'group_by': 'state'}"/>
    </group>
</search>
```

### 6. Menu de Navegacion

```
Inventory
+-- Overview
+-- Operations
|   +-- Transfers
|   +-- Inventory Adjustments      <- (Vista existente)
|   +-- Count History              <- (NUEVO - sequence=25)
+-- Products
+-- Configuration
```

---

## Seguridad y Permisos

### Matriz de Permisos (ir.model.access.csv)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_stock_quant_count_history_user,stock.quant.count.history.user,model_stock_quant_count_history,stock.group_stock_user,1,0,1,0
access_stock_quant_count_history_manager,stock.quant.count.history.manager,model_stock_quant_count_history,stock.group_stock_manager,1,1,1,1
```

### Reglas de Registro (Record Rules)

```xml
<!-- Multi-empresa -->
<record id="stock_quant_count_history_company_rule" model="ir.rule">
    <field name="name">Stock Count History: Multi-company</field>
    <field name="model_id" ref="model_stock_quant_count_history"/>
    <field name="domain_force">
        ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
    </field>
</record>
```

---

## Casos Edge y Manejo de Errores

### Caso 1: Quant Eliminado Durante Conteo

**Problema**: El quant se elimina (por merge o ajuste a 0) mientras hay un conteo.

**Solucion**:
```python
quant_id = fields.Many2one('stock.quant', ondelete='set null')

# Preservar info del producto/ubicacion de forma independiente
product_id = fields.Many2one('product.product', required=True)  # No related
location_id = fields.Many2one('stock.location', required=True)  # No related
```

### Caso 2: Usuario Cambia Cantidad Contada Multiples Veces

**Problema**: Usuario modifica `inventory_quantity` varias veces antes de aplicar.

**Solucion**: El boton "Guardar cantidad contada en historial" crea un **nuevo registro** cada vez. Al "Aplicar" se crea otro registro independiente.

### Caso 3: Conteo de Producto con Tracking Serial

**Problema**: Productos con `tracking='serial'` no permiten cantidad > 1.

**Solucion**:
```python
@api.constrains('quantity_counted', 'product_id', 'lot_id')
def _check_serial_tracking(self):
    for record in self:
        if (record.product_id.tracking == 'serial' and 
            record.lot_id and 
            record.quantity_counted > 1):
            raise ValidationError(_(
                "Product '%(product)s' has serial tracking. "
                "Counted quantity cannot be greater than 1.",
                product=record.product_id.display_name
            ))
```

### Caso 4: Cantidad en Mano Cambia Entre Establecer y Aplicar

**Problema**: Otro usuario/proceso modifica el stock entre el conteo y la aplicacion.

**Solucion**: El registro guarda la cantidad en mano **al momento del conteo**. No se actualiza despues. Esto permite auditoria historica precisa.

### Caso 5: Multi-Almacen con Ubicaciones Homonimas

**Problema**: Ubicaciones con el mismo nombre en diferentes almacenes.

**Solucion**: Siempre almacenar y mostrar `warehouse_id`:
```python
@api.depends('location_id')
def _compute_warehouse_id(self):
    for record in self:
        record.warehouse_id = record.location_id.warehouse_id
```

### Caso 6: Permisos Insuficientes para Ver Historial

**Problema**: Usuario sin permisos intenta ver historial.

**Solucion**: El boton "Conteos" verifica permisos antes de mostrar:
```python
def action_view_count_history(self):
    self.ensure_one()
    # Las record rules manejan el filtrado automaticamente
    return {
        'name': _('Count History'),
        'type': 'ir.actions.act_window',
        'res_model': 'stock.quant.count.history',
        'view_mode': 'tree,form',
        'domain': [('quant_id', '=', self.id)],
        'context': {'default_quant_id': self.id},
    }
```

---

## Internacionalizacion (i18n)

### Archivo i18n/es_AR.po

```po
# Translation of Odoo Server.
# This file contains the translation of the following modules:
# * econovo_stock_quant_count_history
#
msgid ""
msgstr ""
"Project-Id-Version: Odoo Server 17.0\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2025-12-15 10:00+0000\n"
"PO-Revision-Date: 2025-12-15 10:00+0000\n"
"Last-Translator: Jose D. Leonett\n"
"Language-Team: Spanish (Argentina)\n"
"Language: es_AR\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"

#. module: econovo_stock_quant_count_history
#: model:ir.model,name:econovo_stock_quant_count_history.model_stock_quant_count_history
msgid "Inventory Count History"
msgstr "Historial de Conteos de Inventario"

#. module: econovo_stock_quant_count_history
#: model:ir.model.fields,field_description:econovo_stock_quant_count_history.field_stock_quant_count_history__name
msgid "Reference"
msgstr "Referencia"

#. module: econovo_stock_quant_count_history
#: model:ir.model.fields,field_description:econovo_stock_quant_count_history.field_stock_quant_count_history__quantity_on_hand
msgid "Quantity On Hand"
msgstr "Cantidad Disponible"

#. module: econovo_stock_quant_count_history
#: model:ir.model.fields,field_description:econovo_stock_quant_count_history.field_stock_quant_count_history__quantity_counted
msgid "Quantity Counted"
msgstr "Cantidad Contada"

#. module: econovo_stock_quant_count_history
#: model:ir.model.fields,field_description:econovo_stock_quant_count_history.field_stock_quant_count_history__difference
msgid "Difference"
msgstr "Diferencia"

#. module: econovo_stock_quant_count_history
#: model:ir.model.fields,field_description:econovo_stock_quant_count_history.field_stock_quant_count_history__count_datetime
msgid "Count Date/Time"
msgstr "Fecha/Hora del Conteo"

#. module: econovo_stock_quant_count_history
#: model:ir.model.fields.selection,name:econovo_stock_quant_count_history.selection__stock_quant_count_history__state__saved
msgid "Saved"
msgstr "Guardado"

#. module: econovo_stock_quant_count_history
#: model:ir.model.fields.selection,name:econovo_stock_quant_count_history.selection__stock_quant_count_history__state__applied
msgid "Applied"
msgstr "Aplicado"

#. module: econovo_stock_quant_count_history
#: model:ir.ui.menu,name:econovo_stock_quant_count_history.menu_stock_count_history
msgid "Count History"
msgstr "Historial de Conteos"

#. module: econovo_stock_quant_count_history
#: model:ir.actions.act_window,name:econovo_stock_quant_count_history.action_stock_quant_count_history
msgid "Count History"
msgstr "Historial de Conteos"

#. module: econovo_stock_quant_count_history
#: code:addons/econovo_stock_quant_count_history/models/stock_quant.py
msgid "Counts"
msgstr "Conteos"
```

---

## Alternativas de Desarrollo

### Alternativa A: Desarrollo Incremental Minimalista (Recomendado)

**Filosofia**: Minimo viable, maximo valor, codigo NO invasivo.

**Alcance**:
- Modelo stock.quant.count.history con campos esenciales
- Registro automatico al "Aplicar" un ajuste
- Boton "Guardar cantidad contada en historial" (manual)
- Boton "Conteos" en la vista de ajustes
- Vistas tree/form basicas
- Menu bajo Operaciones
- Seguridad basica (usuarios y managers)
- i18n es_AR

**NO incluye**:
- Reportes avanzados
- Dashboard/Kanban
- Configuracion parametrizable
- Migracion de historial existente

**Duracion estimada**: 2-3 dias

**Estructura**:
```
econovo_stock_quant_count_history/
|-- __init__.py
|-- __manifest__.py
|-- models/
|   |-- __init__.py
|   |-- stock_quant_count_history.py
|   +-- stock_quant.py
|-- security/
|   |-- ir.model.access.csv
|   +-- stock_quant_count_history_security.xml
|-- views/
|   |-- stock_quant_count_history_views.xml
|   +-- stock_quant_views.xml
|-- i18n/
|   |-- es_AR.po
|   +-- econovo_stock_quant_count_history.pot
+-- README.md
```

---

### Alternativa B: Desarrollo Completo con Reportes

**Filosofia**: Funcionalidad completa de analisis y auditoria.

**Alcance** (todo de A mas):
- Todo de Alternativa A
- Vista Kanban para resumen rapido
- Reporte de analisis por usuario/ubicacion
- Accion programada para limpieza de datos antiguos
- Wizard para migracion de historial existente
- Campos adicionales (notas, tags)

**Duracion estimada**: 5-6 dias

**Estructura adicional**:
```
econovo_stock_quant_count_history/
|-- ...todo de A...
|-- report/
|   |-- __init__.py
|   |-- stock_quant_count_report.py
|   +-- stock_quant_count_report_views.xml
|-- wizard/
|   |-- __init__.py
|   |-- stock_count_history_migrate.py
|   +-- stock_count_history_migrate_views.xml
|-- data/
|   +-- stock_quant_count_history_cron.xml
+-- views/
    +-- stock_quant_count_history_kanban.xml
```

---

### Alternativa C: Desarrollo Modular (Separado)

**Filosofia**: Modulo base + modulos de extension opcionales.

**Modulo Base** (econovo_stock_quant_count_history):
- Solo modelo y vistas basicas
- Funcionalidad core

**Modulo Reportes** (econovo_stock_quant_count_history_reports):
- Reportes y analisis
- Dashboard

**Modulo Migracion** (econovo_stock_quant_count_history_migrate):
- Wizard de migracion de datos historicos

**Duracion estimada**:
- Base: 2-3 dias
- Reportes: 2 dias adicionales
- Migracion: 1 dia adicional

**Ventajas**:
- Instalacion selectiva segun necesidades
- Mantenimiento independiente
- Testing mas focalizado

**Desventajas**:
- Mas complejidad de gestion
- Mas manifests que mantener

---

## Comparativa de Alternativas

| Criterio | Alternativa A | Alternativa B | Alternativa C |
|----------|---------------|---------------|---------------|
| **Tiempo de desarrollo** | 2-3 dias | 5-6 dias | 5-6 dias |
| **Complejidad** | Baja | Media | Media-Alta |
| **Funcionalidad** | Esencial | Completa | Modular |
| **Mantenimiento** | Facil | Medio | Complejo |
| **Escalabilidad** | Limitada | Buena | Excelente |
| **Riesgo** | Bajo | Medio | Bajo |
| **Time to value** | Rapido | Medio | Rapido (base) |
| **Migrabilidad Odoo 18+** | Alta | Media | Alta |

---

## Recomendacion

**Recomiendo la Alternativa A** para comenzar por las siguientes razones:

1. **Time to value**: Permite validar el concepto rapidamente
2. **Bajo riesgo**: Menos codigo = menos bugs potenciales
3. **Iterativo**: Puede expandirse a B o C despues
4. **Cumple el objetivo principal**: Registro de conteos aplicados y no aplicados
5. **Facil de probar**: Menos casos de prueba
6. **Codigo no invasivo**: Facilita migracion a Odoo 18+

Una vez validado el modulo base en produccion, se puede evaluar si se necesitan las funcionalidades adicionales de B o C.

---

## Cronograma Alternativa A (Recomendada)

| Dia | Tareas |
|-----|--------|
| **Dia 1** | Modelo base, seguridad, __manifest__.py |
| **Dia 2** | Herencia stock.quant, botones, acciones |
| **Dia 3** | Vistas, menus, i18n, testing, README |

---

## Casos de Prueba Minimos (Alternativa A)

| # | Test | Resultado Esperado |
|---|------|-------------------|
| 1 | Clic "Establecer" | NO crea registro (solo habilita edicion) |
| 2 | Clic "Guardar cantidad contada en historial" | Crea registro con state='saved' |
| 3 | Clic "Aplicar" (con diferencia) | Crea registro con state='applied', was_applied=True |
| 4 | Clic "Aplicar" (sin diferencia) | Crea registro con state='applied', was_applied=False |
| 5 | Clic "Limpiar" | NO crea registro |
| 6 | Boton "Conteos" | Abre lista filtrada por quant |
| 7 | Multi-empresa | Solo ve conteos de empresas permitidas |
| 8 | Idioma es_AR | Textos en espanol |

---

## Checklist Pre-Implementacion

- [ ] Confirmar alternativa de desarrollo (A, B o C)
- [ ] Validar diseno de estados con usuario final
- [ ] Confirmar texto de botones
- [ ] Definir si el boton "Conteos" debe mostrar cantidad
- [ ] Confirmar ubicacion del menu

---

*Documento actualizado: 15/12/2025*
*Autor: Analisis por GitHub Copilot para Econovo*
