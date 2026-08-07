"""Sweep POOL_CAP to find where shortlist size stops buying fill rate."""
import random
import scheduler as S

rng = random.Random(1337)
people = S.generate_interviewers(60_000, rng)
index = S.build_availability_index(people)

print(f"{'POOL_CAP':>9} {'fill':>7} {'vars':>9} {'wall':>7}")
for cap in (5, 10, 20, 40):
    S.POOL_CAP = cap
    loops = S.generate_loops(1_000, random.Random(99), index, split=False)
    _, s = S.schedule_week(people, loops, max_seconds_per_shard=10.0)
    nvars = sum(st["num_vars"] for st in s["shard_stats"])
    print(f"{cap:>9} {s['fill_rate']:>6.1%} {nvars:>9,} {s['wall_seconds']:>6.1f}s")
