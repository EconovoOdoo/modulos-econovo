# MPS - BoM Multi-Level Cascade Explode

## Description

Extends the Master Production Schedule (MPS) to allow adding all BoM component
levels (children, grandchildren, etc.) when adding a product, instead of only
the first level.

## Features

- Adds a checkbox **"Include multi-level cascade products"** to the MPS product
  creation dialog
- When enabled, recursively traverses the entire BoM tree and creates MPS
  entries for every component at every level
- Cycle detection prevents infinite loops in circular BoM references
- Skips consumable products (type `consu`)
- Respects existing MPS entries (avoids duplicates via UNIQUE constraint)
- Handles variant-specific BoM lines via `_skip_bom_line()`

## Usage

1. Open **Manufacturing > Planning > Master Production Schedule**
2. Click **"Add a product"**
3. Select a product and its Bill of Materials
4. Check **"Include multi-level cascade products"**
5. Click **Save**
6. All components at every level of the BoM will be added to the MPS

## Dependencies

- `mrp_mps` (Enterprise)

## Author

Jose D. Leonett
