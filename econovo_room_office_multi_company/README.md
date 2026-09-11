# Room Office Multi-Company

Lets a `room.office` (and all its `room.room` records) be shared across
every company, instead of being restricted to a single one.

## The problem

Odoo's Room app requires every office to belong to exactly one company
(`company_id` is required on `room.office`), and a global `ir.rule` on
both `room.office` and `room.room` only lets a company's users see
offices/rooms owned by that same company.

This makes it impossible to model a single physical meeting room shared by
several companies of the same group with one common booking calendar: the
office/room would need to be duplicated once per company, and each copy
would keep its own separate calendar -- `room.booking`'s own overlap check
(`_check_unique_slot`) would no longer see both copies as the same
`room_id`, so the same physical room could be double-booked from each
company independently.

## The fix

* `room.office.company_id` becomes optional. Leaving it empty marks the
  office as shared with every company; all its rooms follow automatically
  through the existing `room.room.company_id = fields.Many2one(
  related="office_id.company_id", store=True)`.
* Widens `room`'s own multi-company record rules
  (`room_office_comp_rule`/`room_room_comp_rule`, both global) to
  `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`,
  applied from `_register_hook` (self-healing on every registry load) and
  reverted to the original core domain by `uninstall_hook`.
* The kiosk/tablet booking flow (`/room/<code>/book`) already works this
  way today regardless of company, since its controller uses `sudo()`
  throughout -- this module only extends the same company-agnostic
  behavior to the regular backend Room app menus and views.

## Configuration

Open **Room > Configuration > Offices**, open the office to share, and
clear its **Company** field (multi-company only, visible with 2+
companies). All of that office's rooms follow automatically, with a single
shared calendar -- no duplicate records, and no risk of a clash between
companies, since `room.booking` already rejects overlapping bookings on
the same room regardless of company.

Users of another company still need that company listed in their own
allowed companies (**Settings > Users**) to actually see it, exactly like
any other multi-company resource.

## Scope

Depends only on `room` (Enterprise). No new models, views or access
rights.
