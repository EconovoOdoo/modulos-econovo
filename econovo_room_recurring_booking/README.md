# Room Recurring Booking

## The problem
The Meeting Rooms app (`room.booking`) has no recurrence concept: keeping a
room permanently reserved on a fixed schedule (e.g. every Monday from 8:30 to
9:30 for a weekly general meeting) means creating every occurrence by hand.

## The fix
Adds `room.booking.recurrence`, a pattern (room, first occurrence, repeat
every X days/weeks/months, end condition) that generates individual
`room.booking` records, one per occurrence:

- Every generated booking still goes through `room.booking`'s own overlap
  check (`_check_unique_slot`), so it blocks any other booking -- from any
  company -- during that slot, exactly like a manual booking would. If a
  specific occurrence conflicts with an existing booking, that single
  occurrence is skipped (logged on the recurrence's chatter) instead of
  failing the whole series.
- Recurrences can end after a number of repetitions, on a fixed end date, or
  never end ("Forever"): a daily scheduled action keeps a rolling horizon
  (default 8 weeks, configurable per recurrence) of upcoming occurrences
  generated for recurrences without an end date.
- The schedule-defining fields (room, first occurrence, interval, frequency)
  become read-only once a recurrence has generated at least one booking, to
  avoid desyncing the pattern from what was actually created. Use the "Stop
  Recurrence" button to end a series (keeps past/ongoing bookings, removes
  only the not-yet-started ones) and create a new recurrence instead.

## Configuration
Room > Recurrences > New. Access is read-only for regular users and full for
the existing "Manage Rooms" (`room.group_room_manager`) group, matching the
same split already used for Offices/Rooms in the base app.

## Scope
Depends only on `room`. Independent from `econovo_room_office_multi_company`
(no hard dependency either way) -- combine both if you need a recurring
booking on a room shared across every company.
