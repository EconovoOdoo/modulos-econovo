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
filtered to the Wheel BOM, plus any other sub-assembly BOM used anywhere in
that tree - Bicycle's own BOM is not repeated in the result. The breadcrumb
trail shows "Sub-BOMs of Bicycle", so it's clear which BOM the cascade came
from.

## Usage

1. Go to **Manufacturing > Products > Bills of Materials**.
2. Any row whose BOM has at least one component with its own BOM shows a
   sitemap icon button.
3. Click it to reopen the list filtered to every sub-BOM found at any depth
   (the BOM you clicked from is excluded, so it isn't shown as its own
   child). The breadcrumb trail shows "Sub-BOMs of <that BOM>", so you can
   navigate back to where you came from.

## Technical Details

### Models

* `mrp.bom` (inherited): adds `has_sub_bom` (computed, gates the button so it
  only shows for BOMs that actually have a sub-assembly), `_get_descendant_bom_ids()`
  (a self-contained recursive helper, walking `mrp.bom.line.child_bom_id` at
  any depth, that deliberately excludes the BOM it is called on - only its
  descendants), and `action_view_bom_hierarchy_cascade()`, which reopens the
  native `mrp.mrp_bom_form_action` ("Bills of Materials") action with an
  `id in (...)` domain built from that helper, and sets the action's `name`
  to "Sub-BOMs of <BOM>" so the breadcrumb trail shows which BOM the cascade
  came from.
* Self-contained: no dependency on any other Econovo module.

### Multi-company

No extra company filtering is added: the reused native action and
`child_bom_id` are already scoped by the current company context/record
rules, exactly as they are on the native Bills of Materials list.

## Dependencies

* `mrp`: Manufacturing module

## License

AGPL-3

## Author

Jose D. Leonett - [GitHub](https://github.com/josedleonett)
