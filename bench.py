import random
from scheduler import (
    generate_interviewers, generate_loops, schedule_week, build_availability_index,
)

rng = random.Random(1337)
people = generate_interviewers(100_000, rng)
index = build_availability_index(people)

for label, split in (("back-to-back (industry default)", False), ("split across days", True)):
    loops = generate_loops(2_000, random.Random(99), index, split=split)
    _, s = schedule_week(people, loops, max_seconds_per_shard=8.0)
    seats = s["panel_seats_by_shift"]
    total = sum(seats.values()) or 1
    prod = sum(v for k, v in seats.items() if k != "corporate")
    print(f"\n--- {label} ---")
    print(f"  fill rate             {s['fill_rate']:.1%}  ({s['loops_scheduled']:,}/{s['loops_total']:,})")
    print(f"  wall time             {s['wall_seconds']:.1f}s over {s['shards']} shards")
    print(f"  distinct interviewers {s['interviewers_used']:,}")
    print(f"  max / mean load       {s['max_interviewer_load']} / {s['mean_interviewer_load']:.2f}")
    print(f"  seats held by shift workers: {prod/total:.1%}")
    for k in sorted(seats, key=lambda x: -seats[x]):
        print(f"      {k:<10} {seats[k]:>6,}  ({seats[k]/total:.1%})")
