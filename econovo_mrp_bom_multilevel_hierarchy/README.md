# Econovo MRP BOM Multilevel Hierarchy

## Overview

Adds a **fa-sitemap** button to the **Bills of Materials** list (Manufacturing
> Products > Bills of Materials): clicking it reopens the same list, in tree
view, filtered to that BOM plus every sub-BOM used by its components, at any
depth.

## Why

[OCA's `mrp_bom_hierarchy`](https://github.com/OCA/manufacture/tree/17.0/mrp_bom_hierarchy)
adds inline buttons to that same list to jump to a BOM's parent BOMs, its
product's other BOMs, or its **direct** child BOMs only (one level down).
There is no button to see the **whole** multi-level tree (a BOM, its
sub-assemblies, their own sub-assemblies, and so on) in a single filtered
list.

Example: clicking this button on "Bicycle" opens the Bills of Materials list
filtered to Bicycle's own BOM, plus the Wheel BOM, plus any other
sub-assembly BOM used anywhere in that tree.

## Usage

1. Go to **Manufacturing > Products > Bills of Materials**.
2. Any row whose BOM has at least one component with its own BOM shows a
   sitemap icon button.
3. Click it to reopen the list filtered to that BOM and every sub-BOM found
   at any depth.

## Technical Details

### Models

* `mrp.bom` (inherited): adds `has_sub_bom` (computed, gates the button so it
  only shows for BOMs that actually have a sub-assembly) and
  `action_view_bom_hierarchy_cascade()`, which reopens the native `mrp.
  mrp_bom_form_action` ("Bills of Materials") action with a `bom_id in (...)`
  domain.
* Depends on `econovo_mrp_operations_multilevel_filter` to reuse its
  `mrp.bom._get_multilevel_bom_ids()` helper (the same recursive BOM
  explosion, walking `mrp.bom.line.child_bom_id`, already used by that
  module's "Multi-level Operations" action) instead of duplicating it.

### Multi-company

No extra company filtering is added: the reused native action and
`child_bom_id` are already scoped by the current company context/record
rules, exactly as they are on the native Bills of Materials list.

## Dependencies

* `mrp`: Manufacturing module
* `econovo_mrp_operations_multilevel_filter`: provides the recursive BOM
  explosion helper this module reuses

## License

AGPL-3

## Author

Jose D. Leonett - [GitHub](https://github.com/josedleonett)
