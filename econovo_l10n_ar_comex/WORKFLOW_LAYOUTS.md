# WORKFLOW Y LAYOUTS - Módulo COMEX Argentina

**Autor**: Jose D. Leonett  
**Versión**: 1.0  
**Fecha**: 16 de Diciembre de 2025

---

## 1. WORKFLOW GENERAL DEL MÓDULO

### 1.1 Diagrama de Flujo Principal

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                          WORKFLOW OPERACIÓN COMEX - IMPORTACIÓN                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │  COMPRAS    │         │   COMEX     │         │  LOGÍSTICA  │
    │  (purchase) │         │ (operation) │         │   (stock)   │
    └──────┬──────┘         └──────┬──────┘         └──────┬──────┘
           │                       │                       │
           ▼                       ▼                       ▼
    ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
    │ 1. ORDEN DE  │───────▶│ 2. CREAR    │        │              │
    │    COMPRA    │        │  OPERACIÓN  │        │              │
    │              │        │    COMEX    │        │              │
    └──────────────┘        └──────┬──────┘        │              │
                                   │               │              │
                            ┌──────▼──────┐        │              │
                            │ 3. COORDINAR│        │              │
                            │   EMBARQUE  │        │              │
                            └──────┬──────┘        │              │
                                   │               │              │
                            ┌──────▼──────┐        │              │
                            │ 4. REGISTRAR│        │              │
                            │   B/L, ETD  │        │              │
                            │   ETA       │        │              │
                            └──────┬──────┘        │              │
                                   │               │              │
                            ┌──────▼──────┐        │              │
                            │ 5. EN       │        │              │
                            │   TRÁNSITO  │        │              │
                            └──────┬──────┘        │              │
                                   │               │              │
                            ┌──────▼──────┐        │              │
                            │ 6. ARRIBO   │        │              │
                            │   PUERTO    │        │              │
                            └──────┬──────┘        │              │
                                   │               │              │
                            ┌──────▼──────┐        │              │
                            │ 7. DESPACHO │        │              │
                            │   ADUANERO  │        │              │
                            └──────┬──────┘        │              │
                                   │               │              │
                            ┌──────▼──────┐        ┌──────▼──────┐
                            │ 8. LIBERADO │───────▶│ 9. RECEPCIÓN│
                            │             │        │    STOCK    │
                            └──────┬──────┘        └──────┬──────┘
                                   │                      │
    ┌──────────────┐        ┌──────▼──────┐        ┌──────▼──────┐
    │ 11. PAGO     │◀───────│ 10. GESTIÓN │        │ PRODUCTOS   │
    │   PROVEEDOR  │        │    MULC     │        │ EN ALMACÉN  │
    │   (account)  │        │             │        │             │
    └──────────────┘        └─────────────┘        └─────────────┘
```

---

## 2. ESTADOS DE LA OPERACIÓN

### 2.1 Diagrama de Estados

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ESTADOS DE OPERACIÓN COMEX                           │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   DRAFT     │ ◄─── Estado inicial
                              │  (Borrador) │
                              └──────┬──────┘
                                     │ action_confirm()
                                     ▼
                              ┌─────────────┐
                              │  CONFIRMED  │
                              │ (Confirmado)│
                              └──────┬──────┘
                                     │ action_coordinate()
                                     ▼
                              ┌─────────────┐
                              │COORDINATING │
                              │(Coordinando)│
                              └──────┬──────┘
                                     │ action_in_transit()
                                     ▼
                              ┌─────────────┐
                              │  IN_TRANSIT │
                              │  (En Viaje) │
                              └──────┬──────┘
                                     │ action_at_port()
                                     ▼
                              ┌─────────────┐
                              │   AT_PORT   │
                              │ (En Puerto) │
                              └──────┬──────┘
                                     │ action_in_customs()
                                     ▼
                              ┌─────────────┐
                              │   CUSTOMS   │
                              │ (En Aduana) │
                              └──────┬──────┘
                                     │ action_release()
                                     ▼
                              ┌─────────────┐
                              │  RELEASED   │
                              │ (Liberado)  │
                              └──────┬──────┘
                                     │ action_warehouse()
                                     ▼
                              ┌─────────────┐
                              │IN_WAREHOUSE │
                              │(En Depósito)│
                              └──────┬──────┘
                                     │ action_receive()
                                     ▼
                              ┌─────────────┐
                              │  RECEIVED   │
                              │ (Recibido)  │
                              └──────┬──────┘
                                     │ action_close()
                                     ▼
                              ┌─────────────┐
                              │   CLOSED    │ ◄─── Estado final
                              │  (Cerrado)  │
                              └─────────────┘

            ┌─────────────┐
            │  CANCELLED  │ ◄─── Desde cualquier estado
            │ (Cancelado) │       (excepto CLOSED)
            └─────────────┘
```

---

## 3. INTEGRACIÓN CON MÓDULOS ODOO

### 3.1 Mapa de Integración

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    INTEGRACIÓN CON MÓDULOS ODOO NATIVOS                      │
└──────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │         COMEX OPERATION         │
                    │      (econovo_l10n_ar_comex)    │
                    └─────────────────┬───────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        │                             │                             │
        ▼                             ▼                             ▼
┌───────────────┐            ┌───────────────┐            ┌───────────────┐
│   PURCHASE    │            │     SALE      │            │    STOCK      │
│   (Compras)   │            │   (Ventas)    │            │  (Inventario) │
├───────────────┤            ├───────────────┤            ├───────────────┤
│• purchase.    │            │• sale.order   │            │• stock.picking│
│  order        │            │• Facturas     │            │• stock.move   │
│• incoterm_id  │            │  comerciales  │            │• Recepciones  │
│• proforma_ref │            │• FOB export   │            │• Entregas     │
└───────┬───────┘            └───────┬───────┘            └───────┬───────┘
        │                             │                             │
        └─────────────────────────────┼─────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
            ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
            │    ACCOUNT    │ │   CONTACTS    │ │   PRODUCTS    │
            │ (Contabilidad)│ │  (Contactos)  │ │  (Productos)  │
            ├───────────────┤ ├───────────────┤ ├───────────────┤
            │• account.move │ │• res.partner  │ │• product.     │
            │• Pagos MULC   │ │• Agentes      │ │  template     │
            │• Tributos     │ │• Despachantes │ │• NCM/HS Code  │
            │• incoterms    │ │• Bancos       │ │• País origen  │
            └───────────────┘ └───────────────┘ └───────────────┘
```

### 3.2 Flujo de Datos Entre Módulos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUJO DE DATOS DETALLADO                            │
└─────────────────────────────────────────────────────────────────────────────┘

PURCHASE.ORDER                    COMEX.OPERATION                    STOCK.PICKING
─────────────────                 ─────────────────                  ─────────────────
│ partner_id    │────────────────▶│ partner_id    │                 │               │
│ incoterm_id   │────────────────▶│ incoterm_id   │                 │               │
│ order_line    │                 │               │                 │               │
│ amount_total  │────────────────▶│ amount_fob    │                 │               │
│               │                 │               │                 │               │
│               │     ┌───────────│ shipment_ids  │──────────┐      │               │
│               │     │           │               │          │      │               │
│               │     ▼           │               │          ▼      │               │
│               │  COMEX.SHIPMENT │               │     ┌──────────┐│               │
│               │  ───────────────│               │     │date_eta  ││               │
│               │  │bill_of_lading│               │     │container ││ scheduled_date│
│               │  │date_etd      │               │     │products  ││◀──────────────│
│               │  │date_eta      │───────────────┼────▶│          ││               │
│               │                 │               │     └──────────┘│               │
│               │     ┌───────────│customs_       │                 │               │
│               │     │           │clearance_ids  │                 │               │
│               │     ▼           │               │                 │               │
│               │  COMEX.CUSTOMS  │               │                 │               │
│               │  ───────────────│               │                 │               │
│               │  │nro_despacho  │───────────────┼────────────────▶│ origin        │
│               │  │tributos      │               │                 │               │
│               │  │fecha_lib     │───────────────┼────────────────▶│ date_done     │
│               │                 │               │                 │               │
│               │     ┌───────────│ mulc_ids      │                 │               │
│               │     │           │               │                 │               │
│               │     ▼           │               │     ACCOUNT.MOVE│               │
│               │  COMEX.MULC     │               │     ─────────────               │
│               │  ───────────────│               │     │           │               │
│               │  │bank_id       │───────────────┼────▶│ Pago USD  │               │
│               │  │amount        │               │     │ TC oficial│               │
│               │  │exchange_rate │───────────────┼────▶│ Diferencia│               │
└───────────────┘  └──────────────┘               │     │ cambio    │               │
                                                  │     └───────────┘               │
```

---

## 4. LAYOUTS DE INTERFAZ

### 4.1 Layout Principal - Form Operación COMEX

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [←] Operaciones COMEX                                          [⭐] [📎] [⋮] │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [Confirmar] [Coordinar] [En Viaje] [En Puerto] [Aduana] [Liberar] [Cerrar] │
│  ════════════════════════════════════════════════════════════════════════   │
│  ○ Borrador → ○ Confirmado → ○ En Viaje → ○ Puerto → ○ Aduana → ● Cerrado  │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ ┌──────────────┐                                                             │
│ │ 🚢 Embarques │  IMP/2025/00001                                             │
│ │      3       │                                                             │
│ └──────────────┘                                                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐           │
│  │ Tipo Operación              │  │ Incoterm                    │           │
│  │ [● Importación ○ Export.]   │  │ [FOB - Free On Board    ▼]  │           │
│  ├─────────────────────────────┤  ├─────────────────────────────┤           │
│  │ Proveedor                   │  │ Lugar Incoterm              │           │
│  │ [ACME Corp. - USA       ▼]  │  │ [Shanghai, China        ]   │           │
│  ├─────────────────────────────┤  ├─────────────────────────────┤           │
│  │ Fecha Orden                 │  │ Estado Pago                 │           │
│  │ [16/12/2025             📅] │  │ [Pendiente MULC         ▼]  │           │
│  └─────────────────────────────┘  └─────────────────────────────┘           │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Valores] [Fechas] [Embarques] [Agentes] [Despachos] [MULC] [Documentos]    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ══════════════════════════ PESTAÑA: VALORES ═══════════════════════════    │
│                                                                              │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐           │
│  │ Moneda                      │  │                             │           │
│  │ [USD - Dólar USA        ▼]  │  │                             │           │
│  ├─────────────────────────────┤  │      VALOR CIF              │           │
│  │ Valor FOB                   │  │                             │           │
│  │ [         45,000.00    USD] │  │   USD 48,500.00             │           │
│  ├─────────────────────────────┤  │                             │           │
│  │ Flete                       │  │   (Base imponible para      │           │
│  │ [          2,500.00    USD] │  │    derechos de importación) │           │
│  ├─────────────────────────────┤  │                             │           │
│  │ Seguro                      │  │                             │           │
│  │ [          1,000.00    USD] │  │                             │           │
│  └─────────────────────────────┘  └─────────────────────────────┘           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Layout Pestaña Embarques

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [Valores] [Fechas] [Embarques] [Agentes] [Despachos] [MULC] [Documentos]    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ═══════════════════════ PESTAÑA: EMBARQUES ════════════════════════════    │
│                                                                              │
│  [+ Agregar Embarque]                                                        │
│                                                                              │
│  ┌────────┬────────────────┬────────────┬────────────┬────────────┬────────┐│
│  │Ref.    │ Bill of Lading │ Contenedor │    ETD     │    ETA     │ Estado ││
│  ├────────┼────────────────┼────────────┼────────────┼────────────┼────────┤│
│  │EMB/001 │ MSCUXYZ123456  │ MSCU789012 │ 01/12/2025 │ 28/12/2025 │En Viaje││
│  ├────────┼────────────────┼────────────┼────────────┼────────────┼────────┤│
│  │EMB/002 │ MSCUXYZ123457  │ MSCU789013 │ 01/12/2025 │ 28/12/2025 │En Viaje││
│  ├────────┼────────────────┼────────────┼────────────┼────────────┼────────┤│
│  │EMB/003 │ MSCUXYZ123458  │ MSCU789014 │ 05/12/2025 │ 02/01/2026 │Pendient││
│  └────────┴────────────────┴────────────┴────────────┴────────────┴────────┘│
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Layout Vista Tree (Lista)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Operaciones COMEX                                    [🔍 Buscar...] [Filtros]│
├──────────────────────────────────────────────────────────────────────────────┤
│ [+ Crear]                                [📊 Lista] [📈 Kanban] [📅 Calendar]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ ┌──────────────┬──────┬────────────────┬─────────┬──────────┬──────┬───────┐│
│ │   Número     │ Tipo │   Proveedor    │Incoterm │   FOB    │ ETA  │ Estado││
│ ├──────────────┼──────┼────────────────┼─────────┼──────────┼──────┼───────┤│
│ │IMP/2025/0001 │ 🔵   │ ACME Corp.     │  FOB    │ 45,000   │28/12 │En Viaje│
│ │IMP/2025/0002 │ 🔵   │ Global Trade   │  CIF    │ 32,500   │15/01 │Borrador│
│ │IMP/2025/0003 │ 🔵   │ Asian Supplies │  FOB    │ 78,000   │20/01 │Confirm.│
│ │EXP/2025/0001 │ 🟢   │ Brazil Import  │  FOB    │ 25,000   │10/01 │Cerrado │
│ │IMP/2025/0004 │ 🔵   │ Euro Parts     │  DDU    │ 15,800   │05/01 │Aduana  │
│ └──────────────┴──────┴────────────────┴─────────┴──────────┴──────┴───────┘│
│                                                                              │
│ 🔵 = Importación    🟢 = Exportación                                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Layout Vista Kanban

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Operaciones COMEX                                              [Vista Kanban]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ BORRADOR     CONFIRMADO    EN VIAJE      EN PUERTO     EN ADUANA    CERRADO │
│ ──────────   ──────────   ──────────    ──────────    ──────────   ──────── │
│                                                                              │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐  ┌──────────┐  ┌──────────┐ ┌───────┐│
│ │IMP/0002  │ │IMP/0003  │ │IMP/0001  │  │IMP/0006  │  │IMP/0004  │ │EXP/01 ││
│ │──────────│ │──────────│ │──────────│  │──────────│  │──────────│ │───────││
│ │Global    │ │Asian     │ │ACME Corp │  │Tech Supp │  │Euro Parts│ │Brazil ││
│ │Trade     │ │Supplies  │ │          │  │          │  │          │ │Import ││
│ │──────────│ │──────────│ │──────────│  │──────────│  │──────────│ │───────││
│ │FOB 32.5K │ │FOB 78K   │ │FOB 45K   │  │CIF 22K   │  │DDU 15.8K │ │FOB 25K││
│ │ETA: 15/01│ │ETA: 20/01│ │ETA: 28/12│  │ETA: 02/01│  │ETA: 05/01│ │✓ Cerr.││
│ │          │ │          │ │🚢 3 emb. │  │🚢 1 emb. │  │🚢 2 emb. │ │       ││
│ └──────────┘ └──────────┘ └──────────┘  └──────────┘  └──────────┘ └───────┘│
│                                                                              │
│ ┌──────────┐              ┌──────────┐                                       │
│ │IMP/0005  │              │IMP/0007  │                                       │
│ │──────────│              │──────────│                                       │
│ │China Mfg │              │USA Parts │                                       │
│ │──────────│              │──────────│                                       │
│ │FOB 120K  │              │FOB 8.5K  │                                       │
│ │ETA: 25/01│              │ETA: 30/12│                                       │
│ └──────────┘              └──────────┘                                       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. MENÚS Y NAVEGACIÓN

### 5.1 Estructura de Menú

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ESTRUCTURA DE MENÚ                                 │
└──────────────────────────────────────────────────────────────────────────────┘

📦 COMEX (Menú Principal)
│
├── 📋 Operaciones
│   ├── Todas las Operaciones
│   ├── Importaciones
│   └── Exportaciones
│
├── 🚢 Logística
│   ├── Embarques
│   ├── Contenedores
│   └── Puertos
│
├── 🏛️ Aduanas
│   ├── Despachos
│   ├── Posiciones Arancelarias (NCM)
│   └── Aduanas
│
├── 💱 MULC
│   ├── Operaciones MULC
│   └── Bancos Autorizados
│
├── 📊 Reportes
│   ├── Operaciones por Estado
│   ├── Embarques Pendientes
│   └── Resumen MULC
│
└── ⚙️ Configuración
    ├── Tipos de Contenedor
    ├── Puertos
    ├── Aduanas
    └── Ajustes COMEX
```

### 5.2 Accesos Rápidos desde Otros Módulos

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ACCESOS DESDE OTROS MÓDULOS                               │
└──────────────────────────────────────────────────────────────────────────────┘

DESDE PURCHASE.ORDER (Orden de Compra):
┌─────────────────────────────────────────────────────────────────┐
│ Orden de Compra: PO00123                                        │
│ ┌────────────────┐                                              │
│ │ 🚢 Operación   │  ← Smart Button que muestra operación COMEX  │
│ │    COMEX       │     vinculada o permite crear una nueva      │
│ │    1           │                                              │
│ └────────────────┘                                              │
│                                                                 │
│ Campo adicional en form:                                        │
│ ┌─────────────────────────────┐                                 │
│ │ Operación COMEX             │                                 │
│ │ [IMP/2025/0001          ▼]  │ ← Link directo a operación     │
│ └─────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘

DESDE RES.PARTNER (Contacto):
┌─────────────────────────────────────────────────────────────────┐
│ Contacto: ACME Corporation                                      │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐        │
│ │ 📦 Operaciones │ │ 🧾 Facturas    │ │ 📋 Compras     │        │
│ │    COMEX       │ │                │ │                │        │
│ │      5         │ │      12        │ │      8         │        │
│ └────────────────┘ └────────────────┘ └────────────────┘        │
│                                                                 │
│ Nueva pestaña "COMEX":                                          │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ☑️ Es Agente de Carga       ☑️ Es Despachante               │ │
│ │ ☐ Es Transportista/Naviera  ☐ Es Banco Autorizado MULC     │ │
│ │                                                             │ │
│ │ Matrícula Despachante: [1234          ]                     │ │
│ │ Incoterm por Defecto:  [FOB               ▼]                │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

DESDE STOCK.PICKING (Recepción):
┌─────────────────────────────────────────────────────────────────┐
│ Recepción: WH/IN/00045                                          │
│                                                                 │
│ Campos adicionales:                                             │
│ ┌─────────────────────────────┐                                 │
│ │ Operación COMEX             │                                 │
│ │ [IMP/2025/0001          ▼]  │                                 │
│ ├─────────────────────────────┤                                 │
│ │ Nro. Despacho               │                                 │
│ │ [25-001-IC04-012345-K   ]   │ ← Autocompletado desde COMEX   │
│ └─────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. CASOS DE USO DETALLADOS

### 6.1 Caso de Uso: Importación Completa

```
┌──────────────────────────────────────────────────────────────────────────────┐
│              CASO DE USO: IMPORTACIÓN DESDE CHINA                            │
└──────────────────────────────────────────────────────────────────────────────┘

PASO 1: CREAR ORDEN DE COMPRA
───────────────────────────────
Módulo: purchase
Acción: Usuario crea PO a proveedor extranjero
Datos:
  - Proveedor: Shanghai Electronics Co.
  - Incoterm: FOB Shanghai
  - Productos: Componentes electrónicos
  - Total: USD 45,000


PASO 2: CREAR OPERACIÓN COMEX
───────────────────────────────
Módulo: econovo_l10n_ar_comex
Acción: Desde PO, click en "Crear Operación COMEX"
Datos automáticos:
  - Tipo: Importación
  - Proveedor: Shanghai Electronics Co.
  - Incoterm: FOB
  - Monto FOB: USD 45,000
Datos manuales:
  - Flete: USD 2,500
  - Seguro: USD 1,000
  - Agente de Carga: DHL Global Forwarding
  - Despachante: Despachantes Asociados SRL


PASO 3: COORDINAR EMBARQUE
───────────────────────────────
Módulo: econovo_l10n_ar_comex
Acción: Agregar datos de embarque
Datos:
  - B/L: COSCO123456789
  - Contenedor: CSLU7891234
  - Tipo: 40' HC
  - Puerto Carga: Shanghai
  - Puerto Descarga: Buenos Aires
  - ETD: 15/12/2025
  - ETA: 12/01/2026
  - Naviera: COSCO Shipping


PASO 4: SEGUIMIENTO EN TRÁNSITO
───────────────────────────────
Módulo: econovo_l10n_ar_comex
Acción: Cambiar estado a "En Viaje"
Notificaciones:
  - Email al responsable cuando ETA < 7 días
  - Alerta si hay demoras


PASO 5: ARRIBO Y DESPACHO
───────────────────────────────
Módulo: econovo_l10n_ar_comex
Acción: Registrar despacho aduanero
Datos:
  - Nro. Despacho: 25-001-IC04-012345-K
  - Aduana: Buenos Aires
  - Canal: Verde
  - Tributos:
    * D.I.: ARS 4,850,000
    * Tasa Est.: ARS 242,500
    * IVA: ARS 1,940,000
    * IVA Adic.: ARS 970,000


PASO 6: LIBERACIÓN Y RECEPCIÓN
───────────────────────────────
Módulo: stock (integrado)
Acción: Generar recepción automática
Datos:
  - Picking: WH/IN/00123
  - Fecha: 15/01/2026
  - Productos validados contra PO


PASO 7: GESTIÓN MULC
───────────────────────────────
Módulo: econovo_l10n_ar_comex
Acción: Registrar acceso a divisas
Datos:
  - Banco: Banco Nación
  - Monto: USD 45,000
  - Tipo Cambio: Oficial
  - Fecha Acceso: según normativa BCRA


PASO 8: CIERRE DE OPERACIÓN
───────────────────────────────
Módulo: econovo_l10n_ar_comex
Acción: Cerrar operación
Validaciones:
  - ✓ Todos los embarques recibidos
  - ✓ Despacho liberado
  - ✓ MULC ejecutado
  - ✓ Pagos realizados
```

---

## 7. REPORTES DISPONIBLES

### 7.1 Layout Reporte Operación COMEX

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                        ECONOVO S.A.                                          │
│                   REPORTE DE OPERACIÓN COMEX                                 │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Operación: IMP/2025/0001                    Estado: EN VIAJE                │
│  Tipo: IMPORTACIÓN                           Fecha: 16/12/2025               │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  DATOS DEL PROVEEDOR                                                         │
│  ───────────────────                                                         │
│  Razón Social: Shanghai Electronics Co., Ltd                                 │
│  País: China                                                                 │
│  Incoterm: FOB Shanghai                                                      │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  VALORES DE LA OPERACIÓN                                                     │
│  ───────────────────────                                                     │
│  Valor FOB:        USD    45,000.00                                          │
│  Flete:            USD     2,500.00                                          │
│  Seguro:           USD     1,000.00                                          │
│                    ─────────────────                                         │
│  VALOR CIF:        USD    48,500.00                                          │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  EMBARQUES                                                                   │
│  ─────────                                                                   │
│  ┌─────────────────┬──────────────┬────────────┬────────────┬───────────┐   │
│  │ Bill of Lading  │ Contenedor   │    ETD     │    ETA     │  Estado   │   │
│  ├─────────────────┼──────────────┼────────────┼────────────┼───────────┤   │
│  │ COSCO123456789  │ CSLU7891234  │ 15/12/2025 │ 12/01/2026 │ En Viaje  │   │
│  └─────────────────┴──────────────┴────────────┴────────────┴───────────┘   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  AGENTES INVOLUCRADOS                                                        │
│  ────────────────────                                                        │
│  Agente de Carga: DHL Global Forwarding                                      │
│  Despachante: Despachantes Asociados SRL - Mat. 1234                         │
│  Banco Nominado: Banco de la Nación Argentina                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. DASHBOARD COMEX (Futuro)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 📊 Dashboard COMEX                                          [Hoy: 16/12/2025]│
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐     │
│  │   OPERACIONES      │  │   EN TRÁNSITO      │  │   PENDIENTE MULC   │     │
│  │   ACTIVAS          │  │                    │  │                    │     │
│  │        12          │  │         5          │  │   USD 125,000      │     │
│  │                    │  │   🚢 🚢 🚢 🚢 🚢   │  │                    │     │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘     │
│                                                                              │
│  ┌─────────────────────────────────────┐  ┌─────────────────────────────────┐│
│  │  PRÓXIMOS ARRIBOS (7 días)          │  │  OPERACIONES POR ESTADO         ││
│  │  ─────────────────────────────────  │  │  ─────────────────────────────  ││
│  │  18/12 - IMP/0007 - USD 8,500       │  │  ████████░░░░░░  Borrador: 2    ││
│  │  20/12 - IMP/0003 - USD 78,000      │  │  ████████████░░  Confirmado: 3  ││
│  │  22/12 - IMP/0008 - USD 12,300      │  │  ██████████████  En Viaje: 5    ││
│  │                                     │  │  ████░░░░░░░░░░  En Aduana: 1   ││
│  │  [Ver todos →]                      │  │  ██░░░░░░░░░░░░  Cerrado: 1     ││
│  └─────────────────────────────────────┘  └─────────────────────────────────┘│
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐│
│  │  LÍNEA DE TIEMPO - OPERACIONES EN CURSO                                  ││
│  │  ────────────────────────────────────────────────────────────────────    ││
│  │                                                                          ││
│  │  Dic 2025                              Ene 2026                          ││
│  │  15  16  17  18  19  20  21  22 ... 10  11  12  13  14  15               ││
│  │  ─────────────────────────────────────────────────────────────────────   ││
│  │  IMP/0001 ═══════════════════════════════════●                           ││
│  │  IMP/0003 ══════════════════●                                            ││
│  │  IMP/0007 ════●                                                          ││
│  │                                                                          ││
│  │  ● = ETA esperado                                                        ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

**Documento preparado por**: GitHub Copilot  
**Fecha**: 16 de Diciembre de 2025
