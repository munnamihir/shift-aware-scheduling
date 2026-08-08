"""Proposition 2 test: does staffing the changeover hour free the day shift
WITHOUT splitting the loop?

Back-to-back only. If reachability is governed by connectivity of the staffed set
rather than by cohort window length, a small cohort bridging 17:00 should bring
day_a off zero under the standard contiguous protocol.
"""
import random

from scheduler import (
    generate_interviewers, generate_loops, schedule_week, build_availability_index,
)

rng = random.Random(1337)
people = generate_interviewers(100_000, rng)
index = build_availability_index(people)

# Confirm 17:00 is actually staffed now.
staffed_17 = len(index.get(("fremont", 1, 17), []))
print(f"interviewers available at 17:00 (fremont, Tue): {staffed_17:,}")
if staffed_17 == 0:
    raise SystemExit("17:00 still unstaffed — the CHANGEOVER edits didn't take.")

loops = generate_loops(2_000, random.Random(99), index, split=False)
_, s = schedule_week(people, loops, max_seconds_per_shard=20.0)

seats = s["panel_seats_by_shift"]
total = sum(seats.values()) or 1
print(f"\nfill rate {s['fill_rate']:.1%}  ({s['loops_scheduled']:,}/{s['loops_total']:,})")
for k in sorted(seats, key=lambda x: -seats[x]):
    print(f"  {k:<12} {seats[k]:>6,}  ({seats[k]/total:.1%})")
print(f"\nday_a seats: {seats.get('day_a', 0):,}   <- prediction: nonzero")
