# MRP Workorder Dependencies Planning Fix

Fixes an Odoo core bug that can crash while (re)planning a Manufacturing
Order whose workorders use the "Workorder Dependencies" feature across
different Manufacturing Orders (e.g. several component MOs that must finish
before one assembly/welding MO can start).

## The bug

`mrp.production._plan_workorders()` (`odoo/addons/mrp/models/mrp_production.py`)
can raise:

```
TypeError: '<' not supported between instances of 'bool' and 'datetime.datetime'
```

This happens when:

1. A workorder is the **last step of its own Manufacturing Order**, but is
   also set (through "Workorder Dependencies") to block a workorder that
   belongs to a **different** Manufacturing Order.
2. The core method decides which workorders are "final" (the entry points for
   the backward planning recursion) with `not workorder.needed_by_workorder_ids`,
   **without limiting that check to the current production**. Such a
   workorder is therefore never treated as final on its own MO, is never
   (re)planned, and keeps no calendar reservation (`leave_id`).
3. The final `date_start`/`date_finished` computation then runs
   `min()`/`max()` over every active workorder's `leave_id.date_from`/`date_to`
   with no filtering for workorders that still have none — as soon as one of
   them is `False` while another has a real value, the comparison crashes.

Typical trigger in production: an Engineering Change Order (`mrp_plm`) changes
a routing operation's work center on an already-planned Manufacturing Order.
Clicking **Update Bill of Materials** (or **Replan**) makes Odoo recreate the
affected workorder(s) and call `_plan_workorders()`, which then hits the bug
if any of the MO's own workorders is entangled in a cross-MO dependency.

## The fix

This module overrides `_plan_workorders()` to:

* Scope the "final workorder" detection to workorders of the **same**
  production (`needed_by_workorder_ids` pointing to a *different* production
  no longer prevents a workorder from being planned on its own MO).
* Defensively ignore workorders that still have no scheduled `leave_id` when
  computing the Manufacturing Order's overall `date_start`/`date_finished`,
  instead of crashing.

## Scope

* Depends only on `mrp` (core). The bug and both call sites that can trigger
  it (`write()`, `button_plan()`, `mrp.workorder.action_replan()`) live in
  core `mrp`, independently of `mrp_plm`/`mrp_workorder` being installed.
* No new fields, models, views or security rules.

## Removal

This override should be removed if/when the upstream bug is fixed in Odoo.
