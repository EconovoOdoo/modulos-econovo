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

* Overrides `mrp.workorder.button_start()`: only when the user has no
  employee record in the current active company, it looks for one in
  **another** company the user is already allowed into
  (`res.users.company_ids`), and lets that employee be used for this one
  call (by seeding the ORM cache for `res.users.employee_id`, then
  restoring it right after). The active company itself is never switched,
  so every other multi-company check triggered by the same call (e.g. on
  the resulting stock moves) keeps seeing the same companies as before.
  **No new access is granted** — the employee record used must already
  belong to a company the user was explicitly given access to.
* Relaxes the "Allowed Employees" domain on the Work Center form
  (`mrp.workcenter.employee_ids`, otherwise restricted to the work center's
  own company), for work centers that use that optional restriction.

## Scope

* Depends only on `mrp_workorder` (Enterprise Shop Floor).
* No new models, fields, security rules or data. No `hr.employee` records
  are created, merged or modified.
