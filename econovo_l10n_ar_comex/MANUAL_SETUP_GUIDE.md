# COMEX Module - Manual Configuration Guide

## Overview
This module provides COMEX operations management but requires manual setup of stock infrastructure (locations, routes, picking types, push rules). This approach gives you full control and flexibility to adapt the workflow to your company's specific needs.

---

## Configuration Steps

### 1. Stock Locations Setup

Create the COMEX location hierarchy under **Inventory > Configuration > Locations**.

#### Suggested Structure:
```
├── Physical Locations
│   └── COMEX (view location)
│       ├── En Viaje (view location)
│       │   ├── En Viaje Marítimo (transit)
│       │   └── En Viaje Aéreo (transit)
│       ├── Puerto (view location)
│       │   ├── Puerto de Buenos Aires (transit)
│       │   └── Puerto de Rosario (transit)
│       ├── Zona Franca (view location)
│       │   ├── Zona Franca La Plata (transit)
│       │   └── Zona Franca TDF (transit)
│       └── Depósito Fiscal (view location)
│           ├── Depósito Fiscal Exolgan (transit)
│           └── Depósito Fiscal Terminal 4 (transit)
```

#### Location Configuration:
- **COMEX** (parent):
  - Location Type: **View**
  - External ID: `stock_location_comex` (optional)

- **En Viaje** (transit):
  - Location Type: **View**
  - Parent Location: COMEX
  - External ID: `stock_location_comex_in_transit` (optional)

- **En Viaje Marítimo/Aéreo**:
  - Location Type: **Transit Location**
  - Parent Location: En Viaje

- **Puerto** (at port):
  - Location Type: **View**
  - Parent Location: COMEX
  - External ID: `stock_location_comex_port` (optional)

- **Puerto de Buenos Aires/Rosario**:
  - Location Type: **Transit Location**
  - Parent Location: Puerto

- **Zona Franca** (free zone):
  - Location Type: **View**
  - Parent Location: COMEX
  - External ID: `stock_location_comex_free_zone` (optional)

- **Zona Franca La Plata/TDF**:
  - Location Type: **Transit Location**
  - Parent Location: Zona Franca

- **Depósito Fiscal** (fiscal warehouse):
  - Location Type: **View**
  - Parent Location: COMEX
  - External ID: `stock_location_comex_fiscal_warehouse` (optional)

- **Depósito Fiscal Exolgan/Terminal 4**:
  - Location Type: **Transit Location**
  - Parent Location: Depósito Fiscal

---

### 2. Stock Route Setup

Create the COMEX import route under **Inventory > Configuration > Routes**.

#### Route: "COMEX - Importación Argentina"
- **Applicable On**: 
  - ☑ Products
  - ☑ Product Categories
- **Company**: Your company
- **External ID**: `stock_route_comex_import` (optional)

#### Why This Is Important:
The route must be assigned to products or categories for push rules to trigger automatically. Users will select this route in product configuration.

---

### 3. Picking Types Setup

Create 4 picking types per company under **Inventory > Configuration > Operations Types**.

#### 3.1 COMEX/IN - Recepción COMEX
- **Operation Type**: Receipts
- **Sequence Code**: `COMEX/IN`
- **Default Source Location**: Vendors
- **Default Destination Location**: En Viaje Marítimo (or your preferred transit)
- **Sequence Prefix**: `COMEX/IN/`
- **Company**: Your company

#### 3.2 COMEX/ARR - Llegada a Puerto
- **Operation Type**: Internal Transfers
- **Sequence Code**: `COMEX/ARR`
- **Default Source Location**: En Viaje Marítimo (or view: En Viaje)
- **Default Destination Location**: Puerto de Buenos Aires (or view: Puerto)
- **Sequence Prefix**: `COMEX/ARR/`
- **Company**: Your company

#### 3.3 COMEX/FIS - Ingreso Depósito Fiscal
- **Operation Type**: Internal Transfers
- **Sequence Code**: `COMEX/FIS`
- **Default Source Location**: Puerto de Buenos Aires (or view: Puerto)
- **Default Destination Location**: Depósito Fiscal Exolgan (or view: Depósito Fiscal)
- **Sequence Prefix**: `COMEX/FIS/`
- **Company**: Your company

#### 3.4 COMEX/NAC - Nacionalización
- **Operation Type**: Internal Transfers
- **Sequence Code**: `COMEX/NAC`
- **Default Source Location**: Depósito Fiscal Exolgan (or view: Depósito Fiscal)
- **Default Destination Location**: Stock (WH/Stock)
- **Sequence Prefix**: `COMEX/NAC/`
- **Company**: Your company

**Important**: The sequence codes (COMEX/IN, COMEX/ARR, etc.) are referenced in module views for filtering actions.

---

### 4. Push Rules Setup

Create 3 push rules under **Inventory > Configuration > Routes > [COMEX Route] > Rules tab**.

#### Rule 1: En Viaje → Puerto
- **Action**: Push From
- **Source Location**: En Viaje (view location)
- **Destination Location**: Puerto (view location)
- **Operation Type**: COMEX/ARR - Llegada a Puerto
- **Move Supply Method**: Manual Operation
- **Route**: COMEX - Importación Argentina

#### Rule 2: Puerto → Depósito Fiscal
- **Action**: Push From
- **Source Location**: Puerto (view location)
- **Destination Location**: Depósito Fiscal (view location)
- **Operation Type**: COMEX/FIS - Ingreso Depósito Fiscal
- **Move Supply Method**: Manual Operation
- **Route**: COMEX - Importación Argentina

#### Rule 3: Depósito Fiscal → Stock
- **Action**: Push From
- **Source Location**: Depósito Fiscal (view location)
- **Destination Location**: Stock (WH/Stock)
- **Operation Type**: COMEX/NAC - Nacionalización
- **Move Supply Method**: Manual Operation
- **Route**: COMEX - Importación Argentina

#### How Push Rules Work:
1. When a picking is validated, Odoo checks: `move.location_dest_id == rule.location_src_id`
2. If match found, creates new picking: `rule.location_src_id → rule.location_dest_id`
3. Routes searched in order: move.route_ids → product.route_ids → category.route_ids → warehouse.route_ids
4. **Critical**: Exact location match required (or parent-child relationship)

---

### 5. COMEX Operation Stages Setup (Optional Location Assignment)

Navigate to **COMEX > Configuration > Stages** and optionally assign parent locations to stages:

- **En Tránsito Marítimo**: Parent Location = En Viaje
- **En Tránsito Aéreo**: Parent Location = En Viaje
- **En Puerto**: Parent Location = Puerto
- **Zona Franca**: Parent Location = Zona Franca
- **Depósito Fiscal**: Parent Location = Depósito Fiscal

**Why This Helps**:
- Automatically filters stock moves by stage location
- Smart buttons show stock in correct location
- Enables automatic location suggestion when changing stages

---

### 6. Product Configuration

For products imported via COMEX:

1. Go to **Inventory > Products > [Your Product]**
2. **Inventory tab > Routes section**:
   - ☑ COMEX - Importación Argentina
3. **Advanced tab**:
   - Configure HS Code, Tariff Code, NCM if needed

**Alternative**: Assign route to product category instead of individual products.

---

## Testing Your Setup

### Test Workflow:

1. **Create Product**:
   - Assign "COMEX - Importación Argentina" route
   - HS Code: 8517.62.39 (example)

2. **Create COMEX Operation**:
   - Type: Import
   - Stage: En Tránsito Marítimo
   - Operation Number: MULC 123456
   - Estimated Arrival Date: [Future date]

3. **Create Purchase Order**:
   - Product: [Your COMEX product]
   - Assign COMEX Operation in "COMEX" tab

4. **Confirm Purchase Order**:
   - ✅ Verify: Receipt picking goes to "En Viaje Marítimo" location
   - ✅ Verify: Receipt picking has comex_operation_id

5. **Validate Receipt (COMEX/IN)**:
   - ✅ Verify: Next picking auto-created (COMEX/ARR: En Viaje → Puerto)
   - ✅ Verify: New picking has comex_operation_id propagated

6. **Validate Arrival (COMEX/ARR)**:
   - ✅ Verify: Next picking auto-created (COMEX/FIS: Puerto → Depósito)

7. **Validate Fiscal Entry (COMEX/FIS)**:
   - ✅ Verify: Final picking auto-created (COMEX/NAC: Depósito → Stock)

8. **Validate Nationalization (COMEX/NAC)**:
   - ✅ Verify: Product quantity in WH/Stock location
   - ✅ Complete workflow!

---

## Troubleshooting

### Push Rules Not Triggering

**Problem**: After validating a picking, the next picking is not auto-created.

**Common Causes**:
1. ❌ Route not assigned to product/category/warehouse
   - **Solution**: Assign "COMEX - Importación Argentina" route to product
   
2. ❌ Location mismatch
   - **Solution**: Verify `move.location_dest_id` matches `rule.location_src_id` exactly
   - Use view locations in rules for flexibility
   
3. ❌ Wrong operation type
   - **Solution**: Verify picking type matches rule configuration
   
4. ❌ Route not in move
   - **Solution**: Check `stock.move` has route_ids or inherits from product

### Locations Not Appearing in Filters

**Problem**: COMEX locations don't appear in location filters.

**Solution**: 
- Verify location type is **Transit Location** (not View)
- Check location is marked as active
- Verify parent location hierarchy is correct

### Picking Types Not Showing in Actions

**Problem**: COMEX/IN, COMEX/ARR actions show no pickings.

**Solution**:
- Verify sequence_code matches exactly: `COMEX/IN`, `COMEX/ARR`, `COMEX/FIS`, `COMEX/NAC`
- Check company assignment
- Verify picking types are active

---

## Multi-Company Setup

For multi-company installations:

1. **Locations**: Create once, share across companies (or create per company)
2. **Routes**: Create per company
3. **Picking Types**: Create 4 types per company with unique sequence codes
4. **Push Rules**: Create per route (3 rules per company route)

---

## Advanced Customizations

### Different Transit Routes

You can create multiple routes for different scenarios:
- Maritime import route
- Air import route
- Export routes
- Different customs procedures

### Custom Stage Locations

Add custom stages with their own locations:
- Customs inspection areas
- Quarantine zones
- Sample inspection areas

### Integration with External Systems

Module provides full API for external integrations:
- Customs broker systems
- MULC BCRA reporting
- ARCA (ex-AFIP) SIMI integration
- Shipping line EDI

---

## Support & Documentation

- **Technical Design**: See `TECHNICAL_DESIGN.md` for detailed architecture
- **API Reference**: See `README.md` for API usage
- **Odoo Documentation**: [Odoo Inventory Routes & Rules](https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/inventory/routes.html)

---

## Change Log

### v17.0.1.0.0 (Current)
- Removed automatic location/route/picking type creation
- User must configure stock infrastructure manually
- Provides full flexibility and control over COMEX workflow
- All business logic and views remain functional
