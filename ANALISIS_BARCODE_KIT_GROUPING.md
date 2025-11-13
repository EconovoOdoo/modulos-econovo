# ANÁLISIS PROFUNDO: econovo_barcode_kit_bom_stock_move_line_grouping

**Fecha**: 2025-11-10  
**Autor**: Jose D. Leonett  
**Objetivo**: Agrupar líneas de stock.move.line por kit/BOM en la app móvil de barcode usando collapse/expand

---

## 1. ANÁLISIS DEL CÓDIGO FUENTE DE ODOO

### 1.1. Estructura de Kits/BOM en Odoo

#### **Modelo: mrp.bom** (`mrp/models/mrp_bom.py`)
```python
class MrpBom(models.Model):
    _name = 'mrp.bom'
    
    type = fields.Selection([
        ('normal', 'Manufacture this product'),
        ('phantom', 'Kit')  # ← Tipo "phantom" = KIT
    ], 'BoM Type', default='normal', required=True)
    
    product_tmpl_id = fields.Many2one('product.template', 'Product')
    product_id = fields.Many2one('product.product', 'Product Variant')
    bom_line_ids = fields.One2many('mrp.bom.line', 'bom_id', 'BoM Lines')
    # ... campos adicionales
```

**KEY INSIGHT**: Los kits son BOMs con `type='phantom'`

#### **Modelo: stock.move** (`mrp/models/stock_move.py`)
```python
class StockMove(models.Model):
    _inherit = 'stock.move'
    
    bom_line_id = fields.Many2one('mrp.bom.line', 'BoM Line')
    description_bom_line = fields.Char('Kit', compute='_compute_description_bom_line')
    
    @api.depends('bom_line_id')
    def _compute_description_bom_line(self):
        for move in self:
            if move.bom_line_id and move.bom_line_id.bom_id.type == 'phantom':
                # Genera: "Kit Name - 1/3", "Kit Name - 2/3", etc.
                move.description_bom_line = '%s - %d/%d' % (
                    bom.display_name, 
                    index + 1, 
                    total_components
                )
```

**KEY INSIGHT**: Cada componente de un kit tiene `bom_line_id` que apunta al BOM padre

#### **Modelo: stock.move.line** (`mrp/models/stock_move.py`)
```python
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'
    
    description_bom_line = fields.Char(related='move_id.description_bom_line')
    
    def _get_aggregated_properties(self, move_line=False, move=False):
        aggregated_properties = super()._get_aggregated_properties(move_line, move)
        bom = aggregated_properties['move'].bom_line_id.bom_id
        aggregated_properties['bom'] = bom or False
        aggregated_properties['line_key'] += f'_{bom.id if bom else ""}'
        return aggregated_properties
```

**KEY INSIGHT**: stock.move.line tiene acceso a BOM via `move_id.bom_line_id.bom_id`

---

### 1.2. Agrupamiento en stock_barcode

#### **Archivo: barcode_model.js** (líneas 169-220)

**Método `groupKey(line)` - Define la clave de agrupamiento**:
```javascript
groupKey(line) {
    return `${line.product_id.id}_${line.location_id.id}_${line.move_id}`;
}
```
**Criterios actuales**: Producto + Ubicación Origen + Movimiento

**Método `get groupedLines` - Construye estructura agrupada**:
```javascript
get groupedLines() {
    if (!this.groups.group_production_lot) {
        return this._sortLine(this.pageLines);
    }

    const lines = [...this.pageLines];
    const groupedLinesByKey = {};
    
    // PASO 1: Agrupar líneas por clave
    for (let index = lines.length - 1; index >= 0; index--) {
        const line = lines[index];
        
        // Solo agrupa productos con tracking
        if (line.product_id.tracking === 'none' || line.lines) {
            continue;
        }
        
        const key = this.groupKey(line);
        if (!groupedLinesByKey[key]) {
            groupedLinesByKey[key] = [];
        }
        groupedLinesByKey[key].push(...lines.splice(index, 1));
    }
    
    // PASO 2: Crear líneas agrupadas
    for (const sublines of Object.values(groupedLinesByKey)) {
        if (sublines.length === 1) {
            lines.push(...sublines);
            continue;
        }
        
        const ids = [];
        const virtual_ids = [];
        let [qtyDemand, qtyDone] = [0, 0];
        
        for (const subline of sublines) {
            ids.push(subline.id);
            virtual_ids.push(subline.virtual_id);
            qtyDemand += this.getQtyDemand(subline);
            qtyDone += this.getQtyDone(subline);
        }
        
        const groupedLine = this._groupSublines(sublines, ids, virtual_ids, qtyDemand, qtyDone);
        lines.push(groupedLine);
    }
    
    return this._sortLine(lines);
}
```

**Método `_groupSublines()` - Crea objeto de línea agrupada**:
```javascript
_groupSublines(sublines, ids, virtual_ids, qtyDemand, qtyDone) {
    const sortedSublines = this._sortLine(sublines);
    return Object.assign({}, sortedSublines[0], {
        ids,                 // Array de IDs de sublíneas
        lines: sortedSublines,  // Array de objetos de sublíneas
        opened: false,       // Estado del collapse
        virtual_ids,         // Array de virtual_ids
    });
}
```

**Método `toggleSublines()` - Maneja collapse/expand**:
```javascript
toggleSublines(line) {
    const lineKey = this.groupKey(line);
    this.unfoldLineKey = this.unfoldLineKey === lineKey ? false : lineKey;
    if (this.unfoldLineKey === lineKey && (!this.selectedLine || this.unfoldLineKey != this.groupKey(this.selectedLine))) {
        this.selectLine(line);
    }
    this.trigger('update');
}
```

---

#### **Archivo: barcode_picking_model.js** (línea 134-135)

**Override de groupKey para pickings**:
```javascript
groupKey(line) {
    return super.groupKey(...arguments) + `_${line.location_dest_id.id}`;
}
```
**Criterio extendido**: Producto + Ubicación Origen + Movimiento + **Ubicación Destino**

**Override de _groupSublines**:
```javascript
_groupSublines(sublines, ids, virtual_ids, qtyDemand, qtyDone) {
    return Object.assign(super._groupSublines(...arguments), {
        reserved_uom_qty: qtyDemand,  // Cantidad reservada
        qty_done: qtyDone,              // Cantidad realizada
    });
}
```

---

#### **Componente: grouped_line.js**
```javascript
export default class GroupedLineComponent extends LineComponent {
    get opened() {
        return this.env.model.groupKey(this.line) === this.env.model.unfoldLineKey;
    }

    toggleSublines(ev) {
        ev.stopPropagation();
        this.env.model.toggleSublines(this.line);
    }
}
```

#### **Template: grouped_line.xml**
```xml
<div class="o_barcode_line_summary">
    <div class="o_barcode_line_details">
        <!-- Muestra resumen: producto, cantidad total -->
    </div>
    <button t-on-click="toggleSublines" class="o_toggle_sublines">
        <i t-att-class="'fa fa-caret-' + (opened ? 'up' : 'down')"/>
    </button>
</div>

<!-- Sublíneas visibles solo si opened=true -->
<div class="o_sublines" t-if="opened">
    <t t-foreach="line.lines" t-as="subline">
        <LineComponent line="subline" subline="true"/>
    </t>
</div>
```

---

### 1.3. Integración stock_barcode_mrp (ACTUAL)

#### **Archivo: barcode_picking_model.js** (stock_barcode_mrp)
```javascript
patch(BarcodePickingModel.prototype, {
    async validate() {
        if (this.currentState.lines.some(line => line.product_id.is_kits)) {
            // Explota kits en componentes antes de validar
            await this.orm.call('stock.move', 'action_explode', [move_ids]);
            this.trigger('refresh');
            return this.notification(_t("Lines with kits replaced with components"));
        } else {
            return await super.validate();
        }
    },
});
```

**LIMITACIÓN ACTUAL**: Solo explota kits, **NO agrupa visualmente**

---

## 2. PUNTOS DE EXTENSIÓN IDENTIFICADOS

### 2.1. Métodos a heredar/parchear

| Método | Archivo | Propósito | Estrategia |
|--------|---------|-----------|------------|
| `groupKey(line)` | `barcode_model.js` | Definir clave de agrupamiento | **Patch**: Agregar `bom_id` a la clave |
| `_groupSublines()` | `barcode_picking_model.js` | Crear objeto agrupado | **Patch**: Agregar campos `bom_id`, `bom_name` |
| `get groupedLines` | `barcode_model.js` | Lógica de agrupamiento | **NO TOCAR** (funciona si cambiamos groupKey) |
| `toggleSublines()` | `barcode_model.js` | Manejo de collapse | **NO TOCAR** (reutilizar) |

### 2.2. Componentes a reutilizar

| Componente | Archivo | Uso |
|------------|---------|-----|
| `GroupedLineComponent` | `grouped_line.js` | **REUTILIZAR** (funciona automáticamente) |
| Template `grouped_line.xml` | `grouped_line.xml` | **REUTILIZAR** (mostrar nombre kit) |

---

## 3. DATOS NECESARIOS DEL BACKEND

### 3.1. Campos adicionales en stock.move

**Ya existen en Odoo**:
- ✅ `bom_line_id` (Many2one a `mrp.bom.line`)
- ✅ `description_bom_line` (Char computed, ej: "Kit A - 1/3")

**Relación**:
```python
stock.move → bom_line_id → mrp.bom.line → bom_id → mrp.bom
```

### 3.2. Campos a exponer en RPC

Necesitamos agregar a `_get_fields_stock_barcode()`:

```python
# En stock.move
def _get_fields_stock_barcode(self):
    fields = super()._get_fields_stock_barcode()
    return fields + [
        'bom_line_id',           # ID de la línea de BOM
        'description_bom_line',  # "Kit Name - 1/3"
    ]
```

Agregar campos relacionados del BOM:
```python
'bom_line_id.bom_id',          # ID del BOM padre
'bom_line_id.bom_id.type',     # 'phantom' para kits
'bom_line_id.bom_id.product_id',  # Producto del kit
```

### 3.3. Estructura de datos en JS

Después del RPC, cada línea tendrá:
```javascript
{
    id: 123,
    product_id: {...},
    move_id: 456,
    bom_line_id: {
        id: 789,
        bom_id: {
            id: 101,
            type: 'phantom',      // Indica que es kit
            product_id: {...},    // Producto del kit
            display_name: "Kit A"
        }
    },
    description_bom_line: "Kit A - 1/3",
    // ... otros campos
}
```

---

## 4. LÓGICA DE AGRUPAMIENTO PROPUESTA

### 4.1. Estrategia de Agrupación: Ignorar Ubicación de Origen para Kits

**DECISIÓN DE DISEÑO**:
- **Realidad operativa**: Los componentes de un kit normalmente están almacenados en **diferentes ubicaciones físicas** (Shelf A, Shelf B, Shelf C, etc.)
- **Concepto de kit**: Un kit es una **unidad lógica**, no física. El usuario piensa en "Kit A" como un todo, no en ubicaciones individuales
- **UX deseada**: Agrupar SIEMPRE todos los componentes del mismo kit juntos, independientemente de sus ubicaciones de origen
- **Información preservada**: Al expandir, cada componente muestra su ubicación origen/destino específica

### 4.2. Nuevo groupKey() - Ignorar location_id para Kits

**Criterio**: Agrupar componentes del mismo kit **SIN incluir location_id en la clave**

```javascript
groupKey(line) {
    // Si la línea pertenece a un kit/BOM phantom
    if (line.bom_line_id && line.bom_line_id.bom_id && line.bom_line_id.bom_id.type === 'phantom') {
        // Agrupar por: BOM + Move + Destino
        // ❌ NO incluir location_id (origen)
        // ✅ SÍ incluir location_dest_id (destino)
        // Esto agrupa TODOS los componentes del mismo kit juntos
        // independientemente de sus ubicaciones de origen
        return `kit_${line.bom_line_id.bom_id.id}_${line.move_id}_${line.location_dest_id.id}`;
    }
    
    // Para líneas normales (no kits), usar la lógica estándar de Odoo
    // Esto mantiene el comportamiento actual para productos individuales
    return super.groupKey(...arguments);
}
```

**Resultado**:
- Componentes del **mismo kit** → **misma clave** → **se agrupan SIEMPRE**
  - ✅ Producto 1 en Shelf A + Producto 2 en Shelf B + Producto 3 en Shelf C = **1 grupo "Kit A"**
- Componentes de **kits diferentes** → **claves diferentes** → **NO se agrupan**
  - ✅ Kit A componentes + Kit B componentes = **2 grupos separados**
- Líneas **sin kit** → **clave normal** → **comportamiento actual de Odoo**
  - ✅ Producto individual en Shelf A ≠ Producto individual en Shelf B = **2 grupos separados**

**Comparación con groupKey estándar de Odoo**:
```javascript
// Odoo estándar (barcode_model.js):
groupKey(line) {
    return `${line.product_id.id}_${line.location_id.id}_${line.move_id}`;
    //                               ^^^^^^^^^^^^^^^^^^^^^^
    //                               Incluye location_id → Componentes en diferentes ubicaciones NO se agrupan
}

// Odoo picking override (barcode_picking_model.js):
groupKey(line) {
    return super.groupKey(...arguments) + `_${line.location_dest_id.id}`;
}

// Nuestro módulo (SOLO para kits):
groupKey(line) {
    if (is_kit_component) {
        return `kit_${bom_id}_${move_id}_${dest_location_id}`;
        //      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        //      NO incluye location_id → Todos los componentes del kit se agrupan
    }
    return super.groupKey(...arguments);  // Comportamiento normal para no-kits
}
```

### 4.3. Nuevo _groupSublines() - Agregar Metadata del Kit

**Objetivo**: Agregar información del kit a la línea agrupada + detectar ubicaciones múltiples

```javascript
_groupSublines(sublines, ids, virtual_ids, qtyDemand, qtyDone) {
    const groupedLine = super._groupSublines(...arguments);
    
    // Si las sublíneas pertenecen a un kit
    const firstSubline = sublines[0];
    if (firstSubline.bom_line_id && firstSubline.bom_line_id.bom_id && firstSubline.bom_line_id.bom_id.type === 'phantom') {
        const bom = firstSubline.bom_line_id.bom_id;
        
        // Detectar ubicaciones de origen únicas
        const uniqueSourceLocations = new Set(
            sublines.map(sub => sub.location_id.id)
        );
        
        // Detectar ubicaciones de destino únicas
        const uniqueDestLocations = new Set(
            sublines.map(sub => sub.location_dest_id.id)
        );
        
        return Object.assign(groupedLine, {
            is_kit_group: true,              // Flag para identificar grupo de kit
            kit_bom_id: bom.id,              // ID del BOM
            kit_name: bom.display_name,     // "Kit A"
            kit_product_id: bom.product_id,  // Producto del kit
            component_count: sublines.length, // 3 componentes
            
            // Información de ubicaciones múltiples
            has_multiple_source_locations: uniqueSourceLocations.size > 1,
            source_location_count: uniqueSourceLocations.size,
            has_multiple_dest_locations: uniqueDestLocations.size > 1,
            dest_location_count: uniqueDestLocations.size,
        });
    }
    
    return groupedLine;
}
```

**Datos disponibles en la línea agrupada**:
```javascript
{
    // Campos heredados de la primera sublínea
    product_id: {...},        // Producto del primer componente
    location_id: {...},       // Ubicación del primer componente (IGNORAR en vista agrupada)
    location_dest_id: {...},  // Destino del primer componente
    
    // Campos agregados por _groupSublines estándar
    ids: [123, 124, 125],     // IDs de las 3 sublíneas
    lines: [...],             // Array con los 3 componentes
    opened: false,            // Estado del collapse
    
    // Campos agregados por nuestro módulo
    is_kit_group: true,
    kit_bom_id: 202,
    kit_name: "Kit A",
    kit_product_id: {id: 303, display_name: "Kit A Product"},
    component_count: 3,
    has_multiple_source_locations: true,   // Shelf A, B, C
    source_location_count: 3,
    has_multiple_dest_locations: false,    // Todos a WH/Output
    dest_location_count: 1,
}
```
            kit_product_id: bom.product_id,  // Producto del kit
            kit_name: bom.display_name,   // "Kit A"
            kit_component_count: sublines.length,  // Número de componentes
        });
    }
    
    return groupedLine;
}
```

---

## 5. MODIFICACIONES EN VISTA

### 5.1. Vista Agrupada (Colapsada) - SIN Ubicación de Origen

**DISEÑO**: Como los componentes del kit están en **diferentes ubicaciones**, mostrar una sola ubicación en la vista agrupada es **engañoso**. En su lugar:
- ✅ Mostrar nombre del kit
- ✅ Mostrar cantidad de componentes
- ✅ Mostrar ubicación de **destino** (si es común)
- ❌ **NO** mostrar ubicación de origen (evitar confusión)

**Template personalizado**:
```xml
<template id="KitGroupedLineComponent" name="Kit Grouped Line">
    <!-- Vista COLAPSADA del kit -->
    <div class="o_barcode_line_summary o_kit_summary">
        <div class="o_barcode_line_details">
            <!-- TÍTULO DEL KIT -->
            <t t-call="econovo_barcode_kit.KitLineTitle"/>
            
            <!-- CANTIDAD TOTAL -->
            <t t-call="stock_barcode.LineQuantity"/>
            
            <!-- UBICACIÓN DE DESTINO (si todas van al mismo lugar) -->
            <t t-if="!line.has_multiple_dest_locations">
                <t t-call="stock_barcode.LineDestinationLocation"/>
            </t>
            <t t-else="">
                <div class="o_line_multiple_dests">
                    <i class="fa fa-fw fa-sign-in text-warning"/>
                    <span class="fst-italic text-muted">
                        <t t-esc="line.dest_location_count"/> ubicaciones
                    </span>
                </div>
            </t>
        </div>
        
        <!-- Botón de collapse/expand -->
        <button t-on-click="toggleSublines" class="o_toggle_sublines">
            <i t-att-class="'fa fa-caret-' + (opened ? 'up' : 'down')"/>
        </button>
    </div>
    
    <!-- Vista EXPANDIDA: Componentes del kit -->
    <div class="o_sublines o_kit_components" t-if="opened">
        <t t-foreach="line.lines" t-as="subline">
            <!-- Cada componente muestra su ubicación origen/destino -->
            <LineComponent line="subline" displayUOM="props.displayUOM" subline="true"/>
        </t>
    </div>
</template>
```

**Template del título del kit** (reemplaza LineTitle estándar):
```xml
<t t-name="econovo_barcode_kit.KitLineTitle">
    <div class="o_line_title o_kit_title">
        <i class="fa fa-cubes text-primary me-2"/> <!-- Icono de kit -->
        <strong t-esc="line.kit_name" class="text-primary"/>
        <span class="badge bg-info ms-2">
            <t t-esc="line.component_count"/> componentes
        </span>
    </div>
</t>
```

### 5.2. Vista Expandida - Componentes con Ubicaciones

**COMPORTAMIENTO**: Al expandir, cada componente usa el template estándar `LineComponent` de Odoo, que **automáticamente** muestra:
- ✅ `LineSourceLocation` → Ubicación de origen (Shelf A, Shelf B, Shelf C)
- ✅ `LineTitle` → Nombre del producto componente
- ✅ `LineQuantity` → Cantidad del componente
- ✅ `LineDestinationLocation` → Ubicación de destino

**NO SE MODIFICA** - Usa el componente nativo de Odoo.

### 5.3. Mockup Visual - Estrategia Final

```
┌────────────────────────────────────────────────────────┐
│ 📦 Kit A                           🔢 0/6 Units    ▼   │ ← AGRUPADA (sin ubicación origen)
│    ℹ️ 3 componentes                🚪 → WH/Output     │
└────────────────────────────────────────────────────────┘

Click en ▼ para expandir:

┌────────────────────────────────────────────────────────┐
│ 📦 Kit A                           🔢 0/6 Units    ▲   │ ← AGRUPADA
│    ℹ️ 3 componentes                🚪 → WH/Output     │
│                                                        │
│ COMPONENTES:                                           │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 🚪 WH/Stock → Shelf A                              │ │ ← Componente 1 (ubicación A)
│ │ 🏷️ Product 1                                       │ │
│ │ 🔢 0.00 / 2.00 Units                               │ │
│ │ 🚪 → WH/Output                                     │ │
│ └────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 🚪 WH/Stock → Shelf B                              │ │ ← Componente 2 (ubicación B)
│ │ 🏷️ Product 2                                       │ │
│ │ 🔢 0.00 / 2.00 Units                               │ │
│ │ 🚪 → WH/Packing Zone                               │ │ ← Destino diferente!
│ └────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 🚪 WH/Stock → Shelf C                              │ │ ← Componente 3 (ubicación C)
│ │ 🏷️ Product 3                                       │ │
│ │ 🔢 0.00 / 2.00 Units                               │ │
│ │ 🚪 → WH/Output                                     │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

**Ventajas de esta estrategia**:
1. ✅ **Vista agrupada limpia**: No muestra ubicación origen confusa (ya que hay múltiples)
2. ✅ **Vista expandida detallada**: Cada componente muestra su ubicación real
3. ✅ **Usa componentes nativos de Odoo**: `LineComponent` para sublines sin modificación
4. ✅ **Semánticamente correcto**: "Kit A" es una unidad lógica, las ubicaciones son detalles de componentes
5. ✅ **Escalable**: Funciona con 3, 10 o 50 componentes en diferentes ubicaciones

### 5.4. CSS Personalizado

```scss
// Estilo para línea agrupada de kit
.o_barcode_line_summary.o_kit_summary {
    background-color: #f0f8ff;  // Fondo azul claro
    border-left: 4px solid #007bff;  // Borde azul
    
    .o_kit_title {
        font-size: 1.1em;
        
        i.fa-cubes {
            font-size: 1.2em;
        }
    }
}

// Estilo para componentes expandidos
.o_sublines.o_kit_components {
    background-color: #fafafa;
    padding-left: 10px;
    border-left: 2px dashed #ccc;
    
    .o_barcode_line {
        margin: 5px 0;
        padding-left: 15px;
        border-left: 3px solid #e9ecef;
        
        &:hover {
            background-color: #fff;
            border-left-color: #007bff;
        }
    }
}

// Badge de componentes
.badge.bg-info {
    font-size: 0.75em;
    padding: 0.25em 0.5em;
}
```

---

## 6. COMPATIBILIDAD Y CONDICIONES

### 6.1. Compatibilidad con stock_barcode_mrp

**Situación actual**:
- `stock_barcode_mrp` solo parchea `validate()` para explotar kits
- **NO interfiere** con la lógica de agrupación visual
- **Compatibilidad total**: Nuestro módulo opera en la capa de presentación (groupKey, templates)

**Orden de ejecución**:
1. Usuario abre picking con kit → BOM ya explotado en `stock.move.line` (componentes individuales)
2. Barcode app carga líneas → Nuestro `groupKey()` agrupa componentes del mismo kit
3. Usuario completa picking → `stock_barcode_mrp` NO se ejecuta (solo en validación de kits no explotados)

**Conclusión**: ✅ Totalmente compatible, operan en diferentes fases

### 6.2. Condiciones de Agrupamiento

**CRITERIO FINAL** (basado en requerimiento del usuario):

```javascript
groupKey(line) {
    // Solo agrupar si cumple TODAS estas condiciones:
    // 1. ✅ Tiene bom_line_id (es componente de kit)
    // 2. ✅ El BOM es type='phantom' (es kit, no manufactura)
    // 3. ✅ IGNORAR location_id (permitir ubicaciones múltiples)
    // 4. ✅ RESPETAR location_dest_id (componentes con destinos diferentes NO se agrupan)
    
    if (line.bom_line_id && 
        line.bom_line_id.bom_id && 
        line.bom_line_id.bom_id.type === 'phantom') {
        
        return `kit_${line.bom_line_id.bom_id.id}_${line.move_id}_${line.location_dest_id.id}`;
    }
    
    // Líneas normales: comportamiento estándar de Odoo
    return super.groupKey(...arguments);
}
```

**Tabla de decisiones**:

| Escenario | ¿Se agrupa? | Razón |
|-----------|-------------|-------|
| Kit A, componentes en Shelf A, B, C → WH/Output | ✅ SÍ | Mismo kit, mismo destino |
| Kit A, componentes en Shelf A, B → diferentes destinos | ❌ NO | Destinos diferentes |
| Kit A + Kit B, ambos en Shelf A → WH/Output | ❌ NO | Kits diferentes (diferentes `bom_id`) |
| Producto individual en Shelf A + Shelf B | ❌ NO | No es kit, usa lógica estándar |
| Kit A en Picking 1 + Kit A en Picking 2 | ❌ NO | Diferentes `move_id` |

### 6.3. Tipos de Operación Soportados

**Funcionará en**:
- ✅ **Delivery Orders** (outgoing): Kits que salen del almacén
- ✅ **Internal Transfers**: Kits moviéndose entre ubicaciones
- ✅ **Receipts** (incoming): Kits entrando al almacén (si se usan)
- ✅ **Manufacturing**: Si hay picking de componentes de kit

**NO afecta**:
- ✅ Productos individuales (sin BOM)
- ✅ BOMs type='normal' (manufactura, no kits)
- ✅ Agrupaciones existentes por lote/serial number (se mantienen)

### 6.4. Tracking de Componentes

**Problema**: Si un componente del kit tiene tracking (serial/lot), ¿cómo manejamos el agrupamiento?

**Solución**: La lógica estándar de Odoo YA maneja esto correctamente:
- `get groupedLines` en `barcode_model.js` solo agrupa líneas con `tracking !== 'none'`
- Si un componente tiene `tracking='serial'` → NO se agrupa (aparece individualmente)
- Si un componente tiene `tracking='lot'` y diferentes lotes → NO se agrupa
- **Nuestro módulo NO interfiere** con esta lógica

**Ejemplo**:
```
Kit A con 3 componentes:
  - Product 1 (no tracking) → Se agrupa
  - Product 2 (tracking='lot', Lot#123) → Se agrupa
  - Product 3 (tracking='serial', SN-001) → NO se agrupa (aparece individual)
  - Product 3 (tracking='serial', SN-002) → NO se agrupa (aparece individual)
  
Resultado:
  📦 Kit A (2 componentes agrupados) ▼
     ├─ Product 1 (2 units)
     └─ Product 2 (2 units, Lot#123)
  🏷️ Product 3 - SN-001 (1 unit)
  🏷️ Product 3 - SN-002 (1 unit)
```

---

## 7. IMPACTO MÍNIMO EN CÓDIGO ODOO

### 7.1. Uso de Patch (NO herencia directa)

**Ventaja**: No requiere modificar código base de Odoo
```javascript
import { patch } from "@web/core/utils/patch";
import { BarcodePickingModel } from '@stock_barcode/models/barcode_picking_model';

patch(BarcodePickingModel.prototype, {
    groupKey(line) {
        if (line.bom_line_id?.bom_id?.type === 'phantom') {
            return `kit_${line.bom_line_id.bom_id.id}_${line.move_id}_${line.location_dest_id.id}`;
        }
        return super.groupKey(...arguments);
    },
    
    _groupSublines(sublines, ids, virtual_ids, qtyDemand, qtyDone) {
        const groupedLine = super._groupSublines(...arguments);
        const firstSubline = sublines[0];
        
        if (firstSubline.bom_line_id?.bom_id?.type === 'phantom') {
            const bom = firstSubline.bom_line_id.bom_id;
            const uniqueSourceLocations = new Set(sublines.map(s => s.location_id.id));
            const uniqueDestLocations = new Set(sublines.map(s => s.location_dest_id.id));
            
            return Object.assign(groupedLine, {
                is_kit_group: true,
                kit_bom_id: bom.id,
                kit_name: bom.display_name,
                kit_product_id: bom.product_id,
                component_count: sublines.length,
                has_multiple_source_locations: uniqueSourceLocations.size > 1,
                source_location_count: uniqueSourceLocations.size,
                has_multiple_dest_locations: uniqueDestLocations.size > 1,
                dest_location_count: uniqueDestLocations.size,
            });
        }
        
        return groupedLine;
    }
});
```

### 7.2. Archivos a Crear (CERO modificación de archivos core)

**Backend (Python)** - 1 archivo:
- `models/stock_move.py` - Exponer campos BOM en RPC (~20 líneas)

**Frontend (JavaScript)** - 1 archivo:
- `static/src/models/barcode_picking_model.js` - Patch groupKey y _groupSublines (~60 líneas)

**Frontend (XML)** - 2 archivos:
- `static/src/components/kit_grouped_line.xml` - Template personalizado para kits (~40 líneas)
- `static/src/components/kit_grouped_line.js` - Componente JS (opcional, ~30 líneas)

**Estilos (SCSS)** - 1 archivo:
- `static/src/scss/kit_barcode.scss` - Estilos visuales (~20 líneas)

**Manifesto y metadatos** - 2 archivos:
- `__manifest__.py` (~30 líneas)
- `__init__.py` (~5 líneas)

**TOTAL ESTIMADO**: ~205 líneas de código en 7 archivos, **0 archivos de Odoo modificados**

---

## 8. DEPENDENCIAS Y COMPATIBILIDAD

### 8.1. Módulos requeridos

```python
'depends': [
    'stock_barcode',      # Base para app móvil (REQUERIDO)
    'mrp',                # Campos bom_line_id, mrp.bom (REQUERIDO)
    'stock_barcode_mrp',  # Compatibilidad con explosión de kits (REQUERIDO)
]
```

### 8.2. Compatibilidad con stock_barcode_mrp

**Escenario**: Usuario escanea kit completo (producto padre)

**Comportamiento actual** (stock_barcode_mrp):
1. Usuario agrega kit a picking
2. Al validar, `action_explode()` reemplaza kit con componentes
3. Componentes aparecen como líneas separadas

**Comportamiento con nuestro módulo**:
1. Usuario agrega kit a picking (o kit ya viene en picking desde SO)
2. **Componentes ya están en stock.move.line** (creados automáticamente por sistema de kits de Odoo)
3. Nuestro módulo **agrupa visualmente** esos componentes bajo el nombre del kit
4. Usuario ve kit agrupado, expande para ver componentes
5. Usuario escanea componentes individuales (en sus ubicaciones reales)
6. Validación procede normalmente

**Conclusión**: ✅ Compatible. Nuestro módulo actúa **después** de que el kit ya está explotado en componentes.

---

## 9. CASOS DE USO Y FLUJO DE USUARIO

### 9.1. Caso 1: Picking de salida con kit (componentes en diferentes ubicaciones)

**Setup**:
- Kit "Kit A" = [Product 1 (Shelf A), Product 2 (Shelf B), Product 3 (Shelf C)]
- Sale Order crea picking con 2 unidades de "Kit A"
- Cada componente está almacenado en ubicación diferente

**Flujo en app barcode**:

**Flujo en app barcode**:

1. **Usuario abre picking** - ve vista colapsada del kit:
   ```
   ┌────────────────────────────────────────────────────┐
   │ 📦 Kit A                    🔢 0/6 Units       ▼  │
   │    ℹ️ 3 componentes          🚪 → WH/Output      │
   └────────────────────────────────────────────────────┘
   ```
   - ❌ **NO muestra ubicación de origen** (ya que hay múltiples: Shelf A, B, C)
   - ✅ Muestra destino común: WH/Output
   - ✅ Indica que tiene 3 componentes

2. **Usuario expande kit** (toca en ▼):
   ```
   ┌────────────────────────────────────────────────────┐
   │ 📦 Kit A                    🔢 0/6 Units       ▲  │
   │    ℹ️ 3 componentes          🚪 → WH/Output      │
   │                                                    │
   │ COMPONENTES:                                       │
   │ ┌────────────────────────────────────────────────┐ │
   │ │ 🚪 WH/Stock → Shelf A                          │ │ ← Ubicación real Componente 1
   │ │ 🏷️ Product 1                                   │ │
   │ │ 🔢 0.00 / 2.00 Units                           │ │
   │ │ 🚪 → WH/Output                                 │ │
   │ └────────────────────────────────────────────────┘ │
   │ ┌────────────────────────────────────────────────┐ │
   │ │ 🚪 WH/Stock → Shelf B                          │ │ ← Ubicación real Componente 2
   │ │ 🏷️ Product 2                                   │ │
   │ │ 🔢 0.00 / 2.00 Units                           │ │
   │ │ 🚪 → WH/Output                                 │ │
   │ └────────────────────────────────────────────────┘ │
   │ ┌────────────────────────────────────────────────┐ │
   │ │ 🚪 WH/Stock → Shelf C                          │ │ ← Ubicación real Componente 3
   │ │ 🏷️ Product 3                                   │ │
   │ │ 🔢 0.00 / 2.00 Units                           │ │
   │ │ 🚪 → WH/Output                                 │ │
   │ └────────────────────────────────────────────────┘ │
   └────────────────────────────────────────────────────┘
   ```

3. **Usuario recolecta componentes** (siguiendo las ubicaciones mostradas):
   - Va a **Shelf A** → Escanea Product 1 (2x)
   - Va a **Shelf B** → Escanea Product 2 (2x)
   - Va a **Shelf C** → Escanea Product 3 (2x)

4. **Kit se marca como completo** (cantidad 6/6):
   ```
   ┌────────────────────────────────────────────────────┐
   │ 📦 Kit A                    🔢 6/6 Units ✅    ▼  │
   │    ℹ️ 3 componentes          🚪 → WH/Output      │
   └────────────────────────────────────────────────────┘
   ```

5. Usuario valida picking → Transferencia completa

**Ventajas de esta UX**:
- ✅ Usuario ve kit como unidad lógica (coherente con concepto de negocio)
- ✅ Al expandir, ve **exactamente dónde ir a buscar cada componente**
- ✅ No se confunde con ubicación ambigua en vista colapsada
- ✅ Proceso de picking más eficiente (sabe qué componentes faltan y dónde están)
- ✅ Funciona con cualquier número de componentes y ubicaciones

### 9.2. Caso 2: Kit con componentes con destinos diferentes

**Setup**:
- Kit "Kit B" = [Product Serial (tracking=serial), Product Lot (tracking=lot)]

**Flujo**:
1. Usuario expande Kit B:
   ```
   [📦] Kit B (2 componentes)  ▲
     ├─ Product Serial: 0.00 / 1.00 Units (Lot: )
     └─ Product Lot: 0.00 / 1.00 Units (Lot: )
   ```

2. Usuario escanea serial number → se asigna a Product Serial
3. Usuario escanea lote → se asigna a Product Lot

---

## 10. RIESGOS Y MITIGACIONES

### 10.1. Riesgo: Líneas duplicadas

**Problema**: Si un kit aparece múltiples veces en el mismo picking

**Solución**: groupKey diferencia por move_id
```javascript
// Kit A (move 1) → Grupo 1
// Kit A (move 2) → Grupo 2
```

### 10.2. Riesgo: Performance con muchos componentes

**Problema**: Kit con 50+ componentes

**Solución**: El método `get groupedLines` ya optimiza (no cambiamos lógica)

### 10.3. Riesgo: Conflicto con otros módulos

**Problema**: Otro módulo también parchea `groupKey()`

**Solución**: Usar `super.groupKey()` siempre
```javascript
patch(BarcodePickingModel.prototype, {
    groupKey(line) {
        const baseKey = super.groupKey(...arguments);  // ← Llama a otros patches
        // ... nuestra lógica
    }
});
```

---

## 11. PLAN DE IMPLEMENTACIÓN (Próximo paso)

### Fase 1: Prototipo básico
1. Crear estructura del módulo
2. Exponer campos BOM en backend
3. Patch básico de `groupKey()`
4. Probar agrupamiento simple

### Fase 2: Refinamiento
1. Patch de `_groupSublines()` con metadata del kit
2. Template XML personalizado
3. CSS/SCSS para visual

### Fase 3: Casos edge
1. Manejar tracking en componentes
2. Compatibilidad con backorders
3. Validación de cantidades

### Fase 4: Testing
1. Tests unitarios (Python)
2. Tests de integración (JS tours)
3. Testing manual en móvil

---

## 12. ARCHIVOS A CREAR (ESTIMACIÓN)

```
econovo_barcode_kit_bom_stock_move_line_grouping/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── stock_move.py          # ~30 líneas - Exponer campos BOM
│   └── stock_move_line.py     # ~20 líneas - (Opcional) campos computed
├── static/src/
│   ├── models/
│   │   └── barcode_picking_model.js  # ~80 líneas - Patch groupKey/_groupSublines
│   ├── components/
│   │   ├── kit_grouped_line.xml      # ~40 líneas - Template heredado
│   │   └── kit_grouped_line.scss     # ~30 líneas - Estilos
│   └── ...
├── views/
│   └── (Opcional) - Solo si necesitamos XML backend
├── security/
│   └── ir.model.access.csv    # ~2 líneas - Si creamos modelos
└── README.md                   # Documentación
```

**Total estimado**: ~200-250 líneas de código

---

## 13. CONCLUSIÓN

✅ **Factible**: Todos los hooks necesarios existen en Odoo  
✅ **Impacto mínimo**: Solo patches, no modificación de código core  
✅ **Reutiliza componentes**: GroupedLineComponent, grouped_line.xml  
✅ **Compatible**: Con stock_barcode_mrp y otros módulos  
✅ **Escalable**: Funciona con 1 o 100 componentes  

**Próximo paso**: ¿Proceder con la implementación?
