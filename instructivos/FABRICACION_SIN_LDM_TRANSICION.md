# Gestión de Fabricación sin Lista de Materiales (período de transición)

**Aplica a**: Oscar Scorza Equipos y Servicios (OSEYS)  
**Contexto**: Durante la transición a Odoo, hay productos que se fabrican físicamente pero cuyas Listas de Materiales (LdM) aún no están cargadas en el sistema. Sin embargo, el stock de componentes sí está registrado en Odoo.  
**Objetivo**: Registrar el consumo de materiales y el ingreso del producto terminado al stock sin necesidad de tener una LdM cargada.

---

## Requisito previo: el producto terminado debe existir en Odoo

Antes de poder crear una Orden de Fabricación, el producto terminado debe estar cargado en Odoo. Ver opciones a continuación.

---

## Opción A — Producto terminado ya existe en Odoo (sin LdM)

El producto está cargado como almacenable pero sin LdM asignada todavía.

### Flujo operativo

1. **Fabricación → Órdenes de fabricación → Nuevo**
2. Completar:
   - **Producto**: el producto a fabricar
   - **Lista de materiales**: *(dejar vacío)*
   - **Cantidad**: la que se va a producir
3. En la pestaña **Componentes**: agregar manualmente cada material con su cantidad
4. **Confirmar** → Odoo genera automáticamente la EC (`OSEYS/EC/XXXXX`) con los componentes cargados
5. Procesar la EC normalmente (entregar materiales al puesto de trabajo)
6. **Completar** el MO → el producto terminado ingresa al stock

### Transición futura

Cuando se cargue la LdM correspondiente al producto, simplemente se la asigna en la ficha del producto. Las próximas MOs la utilizarán automáticamente. No hay nada que migrar ni corregir retroactivamente.

---

## Opción A2 — Producto terminado NO existe en Odoo (producto comodín transitorio)

Cuando el producto a fabricar no está cargado en Odoo y tampoco se quiere cargarlo todavía, se utiliza un **producto comodín genérico** como producto terminado del MO.

### Configuración única (una sola vez)

Crear un producto con los siguientes datos:

| Campo | Valor |
|-------|-------|
| Nombre | `FABRICACIÓN EN PROCESO (TRANSITORIO)` |
| Tipo de producto | `Almacenable` |
| Seguimiento | Sin seguimiento de lotes/series |

Este producto actúa como placeholder — no representa ningún artículo real, solo permite crear el MO para poder registrar el consumo de componentes vía EC.

### Flujo operativo

1. **Fabricación → Órdenes de fabricación → Nuevo**
2. Completar:
   - **Producto**: `FABRICACIÓN EN PROCESO (TRANSITORIO)`
   - **Lista de materiales**: *(dejar vacío)*
   - **Cantidad**: `1` (o la cantidad de lotes a fabricar)
   - **Origen**: anotar el nombre real del producto que se está fabricando (ej.: `Soldadora TIG 200A`)
3. En la pestaña **Componentes**: agregar manualmente cada material con su cantidad
4. **Confirmar** → se genera la EC (`OSEYS/EC/XXXXX`) con los componentes cargados
5. Procesar la EC normalmente (entregar materiales al puesto de trabajo)
6. **Completar** el MO → el stock del comodín sube (no tiene impacto real — ver nota abajo)

### Gestión del stock del comodín

Al completar el MO, el producto comodín acumula stock. Ese stock **no representa nada físico** — hay que vaciarlo periódicamente con un ajuste de inventario (llevarlo a 0). Se recomienda hacerlo al cierre de cada semana o cuando se cargue el producto real.

### Transición al producto real

Cuando en el futuro se cargue el producto real en Odoo:
1. Los próximos MOs usan el producto real (Opción A o con LdM)
2. Hacer un ajuste de inventario para vaciar el stock acumulado en el comodín
3. Si corresponde, ajustar el stock del producto real según la producción acumulada

### Limitaciones conocidas

| Limitación | Impacto |
|-----------|---------|
| El producto terminado real no entra a stock | No se puede vender ni usar en órdenes hasta ser cargado |
| El comodín acumula stock ficticio | Requiere ajuste periódico manual |
| Sin trazabilidad del producto real en el MO | Solo se identifica por el campo Origen (texto libre) |
| Costos de fabricación no se asignan al producto real | Impacto contable si se usa valorización de inventario |

### Cuándo usar esta opción vs. Opción A

| Situación | Opción recomendada |
|-----------|-------------------|
| El producto ya existe en Odoo aunque no tenga LdM | **Opción A** |
| El producto no existe y se va a cargar pronto (días) | **Opción A** — crearlo con datos mínimos primero |
| El producto no existe y su carga se demoraría semanas | **Opción A2** — comodín transitorio |
| Hay muchos productos sin cargar y urge registrar consumos | **Opción A2** — como solución temporal de corto plazo |

---

## Evolución natural del proceso

```
HOY (transición)                        FUTURO (LdM cargada)
──────────────────────────────────────  ──────────────────────────────────────
Opción A: MO manual sin LdM             Crear MO → LdM asignada automáticamente
  └─ Agregar componentes a mano           └─ Componentes se pre-cargan solos
Opción A2: MO con comodín               Producto real cargado → usar Opción A
  └─ Ajuste de inventario periódico       └─ Sin ajustes necesarios
Confirmar → EC automática               Confirmar → EC automática (igual)
Procesar EC (entregar materiales)       Procesar EC (igual)
Completar MO                            Completar MO (igual)
```

El proceso de EC es **idéntico** en todas las variantes. La diferencia está solo en cómo se gestiona el producto terminado.
