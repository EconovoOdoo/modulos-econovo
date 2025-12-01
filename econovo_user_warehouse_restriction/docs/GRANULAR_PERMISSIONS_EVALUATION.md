# Granular Permissions Expansion - Evaluation Report

## Executive Summary

**Proposal**: Split combined permission fields into more granular controls:
- `allow_write_picking` → `allow_modify_picking` + `allow_validate_picking`
- `allow_delete_picking` → `allow_delete_picking` + `allow_cancel_picking`

**Estimated Effort**: Medium-High (3-5 days)
**Risk Level**: Medium
**Recommendation**: Proceed with caution - implement in phases

---

## 1. Current State Analysis

### 1.1 Current Permission Fields (Operation-Level)

| Field | Current Behavior |
|-------|------------------|
| `allow_write_picking` | Controls: modify picking data + validate picking |
| `allow_delete_picking` | Controls: delete picking + cancel picking |

### 1.2 Code Usage Map

```
stock_picking.py:
├── write()           → checks allow_write_picking
├── button_validate() → checks allow_write_picking  
├── unlink()          → checks allow_delete_picking
└── action_cancel()   → checks allow_delete_picking
```

### 1.3 Test Coverage Analysis

| Test File | `allow_write_picking` refs | `allow_delete_picking` refs |
|-----------|---------------------------|----------------------------|
| test_granular_permissions.py | 12 | 8 |
| test_edge_cases.py | 9 | 2 |
| test_mrp_integration.py | 8 | 0 |
| test_directional_permissions.py | 2 | 0 |
| test_batch_picking.py | ~3 | ~1 |
| **TOTAL** | **~34** | **~11** |

---

## 2. Proposed Changes

### 2.1 New Field Structure

```python
# BEFORE (2 fields)
allow_write_picking = fields.Boolean(string='Modify/Validate Transfers')
allow_delete_picking = fields.Boolean(string='Delete/Cancel Transfers')

# AFTER (4 fields)
allow_modify_picking = fields.Boolean(string='Modify Transfers')
allow_validate_picking = fields.Boolean(string='Validate Transfers')
allow_delete_picking = fields.Boolean(string='Delete Transfers')
allow_cancel_picking = fields.Boolean(string='Cancel Transfers')
```

### 2.2 UI Impact

| Component | Current Columns | New Columns |
|-----------|-----------------|-------------|
| Tree View (Matrix) | 10 | 12 |
| Form View | 3 operation fields | 5 operation fields |
| Wizard/Views | Affected | Need update |

---

## 3. Risk Assessment

### 3.1 Breaking Changes

| Risk | Severity | Mitigation |
|------|----------|------------|
| Migration script required | HIGH | Create `pre_init_hook` to copy old values |
| Existing permissions invalidated | HIGH | Default new fields based on old values |
| UI becomes wider/cluttered | MEDIUM | Consider grouping or collapsible sections |
| External integrations | LOW | API remains similar |

### 3.2 Migration Strategy

```python
# Migration Logic (pre_init_hook or post_init_hook)
def _migrate_split_permissions(cr, registry):
    """
    Migration: Split combined permissions into granular ones.
    
    Mapping:
    - allow_write_picking=True  → allow_modify_picking=True, allow_validate_picking=True
    - allow_delete_picking=True → allow_delete_picking=True, allow_cancel_picking=True
    """
    cr.execute("""
        ALTER TABLE warehouse_user_permission 
        ADD COLUMN IF NOT EXISTS allow_modify_picking BOOLEAN DEFAULT FALSE;
        
        ALTER TABLE warehouse_user_permission 
        ADD COLUMN IF NOT EXISTS allow_validate_picking BOOLEAN DEFAULT FALSE;
        
        ALTER TABLE warehouse_user_permission 
        ADD COLUMN IF NOT EXISTS allow_cancel_picking BOOLEAN DEFAULT FALSE;
        
        -- Migrate existing data
        UPDATE warehouse_user_permission 
        SET allow_modify_picking = allow_write_picking,
            allow_validate_picking = allow_write_picking
        WHERE allow_write_picking IS NOT NULL;
        
        UPDATE warehouse_user_permission 
        SET allow_cancel_picking = allow_delete_picking
        WHERE allow_delete_picking IS NOT NULL;
    """)
```

### 3.3 Test Impact

| Category | Estimated Changes | Effort |
|----------|-------------------|--------|
| Field name updates | ~45 occurrences | 2 hours |
| New test cases needed | ~8 new tests | 4 hours |
| Assertion updates | ~20 assertions | 2 hours |
| **TOTAL** | | **~8 hours** |

---

## 4. Implementation Plan

### Phase 1: Database & Model (Day 1)

- [ ] Add new fields to `warehouse_user_permission.py`
- [ ] Keep old fields as computed (backward compatibility)
- [ ] Create migration hook in `hooks.py`
- [ ] Update `__manifest__.py` version

### Phase 2: Business Logic (Day 2)

- [ ] Update `stock_picking.py`:
  - [ ] `write()` → check `allow_modify_picking`
  - [ ] `button_validate()` → check `allow_validate_picking`
  - [ ] `unlink()` → check `allow_delete_picking`
  - [ ] `action_cancel()` → check `allow_cancel_picking`
- [ ] Update `_check_granular_permission()` method

### Phase 3: Views & UI (Day 2-3)

- [ ] Update `warehouse_user_permission_views.xml`:
  - [ ] Tree view: add 2 new columns
  - [ ] Form view: reorganize operation permissions
- [ ] Update `stock_warehouse_views.xml` (permission matrix)
- [ ] Update `res_users_views.xml` (user permissions tab)

### Phase 4: Tests (Day 3-4)

- [ ] Update `test_granular_permissions.py`:
  - [ ] Rename field references
  - [ ] Add tests for new separate permissions
  - [ ] Test combinations (modify yes + validate no, etc.)
- [ ] Update `test_edge_cases.py`
- [ ] Update `test_mrp_integration.py`
- [ ] Update `test_batch_picking.py`
- [ ] Add new test file: `test_granular_permissions_v2.py`

### Phase 5: Translations & Docs (Day 4-5)

- [ ] Update `i18n/es_AR.po`
- [ ] Update `README.md`
- [ ] Update field help texts

---

## 5. Test Cases to Add

### 5.1 New Permission Combinations

```python
# Test: User can modify but NOT validate
def test_modify_without_validate(self):
    permission.allow_modify_picking = True
    permission.allow_validate_picking = False
    # User CAN change quantities
    # User CANNOT click Validate button

# Test: User can validate but NOT modify
def test_validate_without_modify(self):
    permission.allow_modify_picking = False
    permission.allow_validate_picking = True
    # User CANNOT change quantities
    # User CAN click Validate button (if already correct)

# Test: User can cancel but NOT delete
def test_cancel_without_delete(self):
    permission.allow_cancel_picking = True
    permission.allow_delete_picking = False
    # User CAN cancel draft/confirmed pickings
    # User CANNOT delete canceled pickings

# Test: User can delete but NOT cancel
def test_delete_without_cancel(self):
    permission.allow_cancel_picking = False
    permission.allow_delete_picking = True
    # User CANNOT cancel pickings
    # User CAN delete (only if already canceled by someone else)
```

---

## 6. Alternative Approaches

### 6.1 Option A: Full Split (Recommended)
- 4 separate fields
- Maximum granularity
- Most flexibility for users

### 6.2 Option B: Partial Split
- Split only `allow_write_picking`
- Keep `allow_delete_picking` combined
- Less effort, covers main use case

### 6.3 Option C: Flags with Hierarchy
- Keep 2 fields but add checkbox modifiers
- `allow_write_picking` + `validate_requires_separate_permission`
- Complex logic, confusing UX

---

## 7. Decision Matrix

| Criteria | Weight | Option A | Option B | Option C |
|----------|--------|----------|----------|----------|
| Granularity | 30% | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| Implementation Effort | 25% | ⭐ | ⭐⭐ | ⭐ |
| UX Clarity | 20% | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| Migration Risk | 15% | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Future Maintainability | 10% | ⭐⭐⭐ | ⭐⭐ | ⭐ |
| **TOTAL** | 100% | **72%** | **68%** | **48%** |

**Winner**: Option A (Full Split)

---

## 8. TODOs (If Approved)

### High Priority
- [ ] Create feature branch: `feature/granular-permissions-v2`
- [ ] Implement migration hook FIRST
- [ ] Update model with new fields
- [ ] Update stock_picking.py logic

### Medium Priority
- [ ] Update all views (tree, form, wizard)
- [ ] Update translations
- [ ] Create backward-compatible computed fields

### Low Priority (Can defer)
- [ ] Update documentation
- [ ] Performance testing with large datasets
- [ ] Consider adding "permission presets"

---

## 9. Estimated Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Planning & Migration Script | 0.5 days | None |
| Model & Business Logic | 1 day | Phase 1 |
| Views & UI | 1 day | Phase 2 |
| Tests | 1.5 days | Phase 3 |
| Translations & QA | 0.5 days | Phase 4 |
| **TOTAL** | **4.5 days** | |

---

## 10. Conclusion

**Recommendation**: Proceed with **Option A (Full Split)** in a dedicated feature branch.

**Justification**:
1. Clear user benefit (more control over permissions)
2. Manageable effort with proper migration
3. Test suite is well-structured for updates
4. Breaking changes can be contained with migration hooks

**Next Step**: Create feature branch and implement Phase 1 (Database & Model) first to validate migration approach before continuing.

---

*Document Version: 1.0*
*Created: 2025-11-28*
*Author: GitHub Copilot*
*Module: econovo_user_warehouse_restriction*
