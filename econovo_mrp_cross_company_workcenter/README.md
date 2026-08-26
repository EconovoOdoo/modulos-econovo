# MRP Cross-Company Workcenter Employee

Lets an employee whose HR record lives in one company start a work order
that belongs to a different company of the same group, without duplicating
their `hr.employee` record.

## The problem

`mrp.workorder.button_start()` (Shop Floor, `mrp_workorder` module) requires
the logged in user to have an `hr.employee` record whose `company_id`
matches the **currently active** company. `res.users.employee_id`
(`hr/models/res_users.py` `_compute_company_employee`) is computed scoped to
`self.env.company`, not to the full set of companies the user is allowed
into.

This blocks a common scenario for a multi-company group: an employee
hired/paid through one company (e.g. Agrovial) who physically operates work
centers belonging to another company of the group (e.g. Oscar Scorza).
Granting the user access to both companies (`res.users.company_ids`) only
fixes document **visibility** (record rules); it does not change which
company this specific check looks at, so it keeps raising:

```
You need to link this user to an employee of this company to process the
work order
```

The usual workaround is creating a **second** `hr.employee` record for the
same person in the other company. That duplicates HR data (and headcount in
reports) for no real reason — this module exists specifically to avoid it.

## The fix

* Overrides `mrp.workorder.button_start()`, `action_mark_as_done()` and
  `_set_default_time_log()` (the finish/time-log actions repeat the same
  employee lookup) through one shared context manager: only when the user
  has no employee record in the current active company, it looks for one HR
  already linked to this same user in **another** company
  (`hr.employee.user_id`), and lets that employee be used for the call (by
  seeding the ORM cache for `res.users.employee_id`, then restoring it right
  after). The active company itself is never switched, so every other
  multi-company check triggered by the same call (e.g. on the resulting
  stock moves) keeps seeing the same companies as before.
  **This deliberately does NOT grant `res.users.company_ids`** (multi-company
  access): that would also expose every other record of that company the
  user's groups can read, and show the company switcher in the top bar,
  neither of which this needs — the only fact that authorizes this is that
  HR already linked that employee record to this user. Neither
  `mrp.workorder.employee_ids` nor `mrp.workcenter.productivity.employee_id`
  are `check_company`-constrained (verified in core/`mrp_workorder` source),
  so recording that employee on another company's documents isn't blocked
  at the ORM level either.
* `hr.employee` also carries its own standalone, global multi-company
  `ir.rule` (independent of `check_company`), which would otherwise reject
  the very next plain (non-`sudo()`) read core code makes on that employee
  record (e.g. reading `active` while updating `employee_ids`). The same
  context manager also warms that field into the ORM cache via a narrowly
  scoped `sudo()` read on that one record, so the rule is never hit for it
  — this is deliberately much narrower than `sudo()`-ing the whole method,
  which would also bypass rules on unrelated records touched by the same
  call (e.g. stock moves/production).
* Relaxes the "Allowed Employees" domain on the Work Center form
  (`mrp.workcenter.employee_ids`, otherwise restricted to the work center's
  own company), for work centers that use that optional restriction.
* Widens `hr`'s own multi-company employee record rules so an employee
  explicitly listed on a work center of one of the reader's companies stays
  readable — see below.

## Reading a work center's cross-company employees

Once a work center lists an employee of another company, **every** user of
the work center's own company needs to be able to read that employee's
name: creating a manufacturing order, opening a work order, seeing who is
currently working, the assigned operators or the time logs all render it.
Otherwise they get:

```
Perea, Esteban ... doesn't have 'read' access to:
- Public Employee (hr.employee.public: 1005)
Rules: Employee multi company rule
```

Both `hr.employee` and `hr.employee.public` carry a **global** multi-company
record rule. Global rules are ANDed into every access check, so an extra
rule could only restrict further, never widen: editing their domain is the
only way. This module adds the reverse of `mrp.workcenter.employee_ids`
(`hr.employee.workcenter_ids`, reusing the existing relation table, no new
data) and widens both domains to:

```python
['|', ('company_id', 'in', company_ids + [False]),
      ('workcenter_ids.company_id', 'in', company_ids)]
```

That grants strictly what the work center configuration already authorizes
and nothing else: no access to any other record of the other company, and
the access disappears by itself as soon as the employee is removed from the
work center.

`hr` ships those rules as `noupdate`, so a data record here would be
silently skipped on upgrade; they are applied from `_register_hook` (every
registry load, so it also self-heals) and reverted to their original core
domain by the module's `uninstall_hook`.

## Scope

* Depends only on `hr` and `mrp_workorder` (Enterprise Shop Floor).
* No `hr.employee` records are created, merged or modified.

