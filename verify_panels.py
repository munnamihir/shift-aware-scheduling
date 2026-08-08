"""Verify the claim in Section 9.4: do day-crew assessors appear only on
single-cohort panels?

Run this against your own scheduler.py. It reports, for the split protocol:
  - how many scheduled panels are drawn from a single shift cohort
  - how many panels contain at least one day_a assessor
  - of those, how many are composed entirely of day_a assessors

The paper's claim is that the second and third numbers are equal. If they are
not, Section 9.4 is wrong and Corollary 14 needs revisiting.
"""
import random
from collections import Counter

from scheduler import (
    generate_interviewers, generate_loops, schedule_week, build_availability_index,
)

people = generate_interviewers(100_000, random.Random(1337))
index = build_availability_index(people)
by_id = {p.id: p for p in people}

loops = generate_loops(2_000, random.Random(99), index, split=True)
assignments, s = schedule_week(people, loops, max_seconds_per_shard=20.0)

print(f"fill rate {s['fill_rate']:.1%}   panels scheduled {len(assignments):,}")

comp = Counter()
day_a_panels = 0
day_a_pure = 0
mixed_with_day_a = []

for a in assignments:
    shifts = {by_id[i].shift.value for i in a.panel}
    comp["single-cohort" if len(shifts) == 1 else "mixed-cohort"] += 1
    if "day_a" in shifts:
        day_a_panels += 1
        if shifts == {"day_a"}:
            day_a_pure += 1
        elif len(mixed_with_day_a) < 5:
            mixed_with_day_a.append(sorted(shifts))

print(f"single-cohort panels   {comp['single-cohort']:,}")
print(f"mixed-cohort panels    {comp['mixed-cohort']:,}")
print(f"panels with day_a      {day_a_panels:,}")
print(f"  of which pure day_a  {day_a_pure:,}")

if day_a_panels and day_a_pure == day_a_panels:
    print("\nCLAIM HOLDS: every day_a panel is single-cohort.")
elif day_a_panels:
    print(f"\nCLAIM FAILS: {day_a_panels - day_a_pure} mixed panels contain day_a.")
    print("examples:", mixed_with_day_a)
else:
    print("\nNo day_a panels scheduled — check the run.")
