# COMEX Module Refactor - Implementation Checklist

**Date Started:** 2026-01-15
**Goal:** Simplify COMEX flow with manual operations and dynamic stage-based routing

---

## Architecture Changes

### ❌ Removed Logic
- [ ] Automatic location assignment based on stages
- [ ] `_get_default_transit_location()` usage in picking linking
- [ ] Automatic `location_dest_id` updates on pickings
- [ ] Automatic `location_dest_id` updates on stock moves

### ✅ New Logic
- Manual stage advancement
- Stage-based dynamic routing
- Simple picking linking (comex_operation_id only)

---

## Implementation Progress

### Phase 1: Cleanup & Simple Linking

#### 1.1 Remove Location Logic
- [ ] Clean `_link_pickings_to_comex_operation()` method
- [ ] Remove location assignment from pickings
- [ ] Remove location assignment from moves
- [ ] Remove logging related to locations

#### 1.2 Simple Picking Linking (✅ Punto 1)
- [ ] Link pickings on operation creation from PO
- [ ] Link pickings on manual `comex_operation_id` assignment
- [ ] Link pickings on PO confirmation with existing operation
- [ ] **Edge case:** Vincular pickings done (validated)
- [ ] **Edge case:** Vincular pickings cancelados
- [ ] **Edge case:** Desvincular pickings al remover operación de PO

---

### Phase 2: Stage Configuration

#### 2.1 Stage Sequence Fields (🔄 Punto 2)
- [ ] Add `next_stage_id` field to `comex.operation.stage`
- [ ] Add `location_dest_id` field to stage
- [ ] Add `require_picking_validation` boolean field
- [ ] Update stage views to show new fields
- [ ] Create stage configuration documentation

---

### Phase 3: COMEX Picking Type

#### 3.1 Create COMEX Import Picking Type (📦 Punto 3)
- [ ] Create "En Viaje" location (transit, no warehouse)
- [ ] Create "COMEX Import Reception" picking type
- [ ] Set default locations: Suppliers → En Viaje
- [ ] Make it selectable in PO `picking_type_id`
- [ ] Add to module data files

#### 3.2 PO Integration
- [ ] Validate picking type selection on PO
- [ ] Handle picking type change on confirmed POs
- [ ] Update views to show COMEX picking type

---

### Phase 4: Dynamic Routing

#### 4.1 Manual Stage Advancement (🛤️ Punto 4)
- [ ] Create `action_advance_stage()` method
- [ ] Generate internal pickings between stage locations
- [ ] Use `product_line_ids` for move generation
- [ ] Add validation for missing locations
- [ ] Add button in operation form view

#### 4.2 Route Configuration
- [ ] Document manual routing workflow
- [ ] Add stage transition wizard (optional)
- [ ] Validate stage sequence before advancing

---

## Testing Checklist

### Scenario 1: Create Operation from PO
- [ ] PO with products → Create COMEX → Pickings linked
- [ ] Multiple POs → Same operation → All pickings linked
- [ ] Confirmed PO with existing pickings → Pickings linked

### Scenario 2: Manual Assignment
- [ ] Assign operation to PO → Pickings linked
- [ ] Remove operation from PO → Pickings unlinked
- [ ] Change operation on PO → Pickings re-linked

### Scenario 3: Stage Advancement
- [ ] Advance stage → Internal picking created
- [ ] Validate picking → Advance again → Next picking
- [ ] Skip stage → Handle gracefully

### Scenario 4: Edge Cases
- [ ] Done pickings → Linked correctly
- [ ] Canceled pickings → Linked correctly
- [ ] PO without operation → No linking
- [ ] Stage without location → No picking generated

---

## Commits to Make

1. `[REF] econovo_l10n_ar_comex: remove automatic location logic`
   - Clean picking linking method
   - Remove location updates

2. `[IMP] econovo_l10n_ar_comex: simple picking linking`
   - Link pickings via comex_operation_id only
   - Handle edge cases (done, canceled, unlink)

3. `[ADD] econovo_l10n_ar_comex: stage sequence configuration`
   - Add next_stage_id field
   - Add location_dest_id to stage

4. `[ADD] econovo_l10n_ar_comex: COMEX import picking type`
   - Create En Viaje location
   - Create COMEX picking type

5. `[IMP] econovo_l10n_ar_comex: manual stage advancement`
   - action_advance_stage method
   - Internal picking generation

---

## Notes & Decisions

- **Picking linking:** Always link, regardless of state (done/cancel)
- **Unlink behavior:** Remove comex_operation_id when PO operation cleared
- **Stage advancement:** Fully manual, no automation
- **Location strategy:** Stage-defined destinations, user-controlled movement

---

## Current Status

**Phase:** 1.1 - Cleanup in progress
**Last Updated:** 2026-01-15
**Blocking Issues:** None
