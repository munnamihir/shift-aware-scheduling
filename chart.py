"""The one chart: panel seats by shift cohort, back-to-back vs split."""
import random

import scheduler as S
from chart_render import draw

rng = random.Random(1337)
people = S.generate_interviewers(100_000, rng)
index = S.build_availability_index(people)

results = {}
for label, split in (("Back-to-back\n(industry default)", False),
                     ("Split across days", True)):
    loops = S.generate_loops(2_000, random.Random(99), index, split=split)
    _, s = S.schedule_week(people, loops, max_seconds_per_shard=20.0)
    seats = s["panel_seats_by_shift"]
    total = sum(seats.values()) or 1
    results[label] = {k: 100 * v / total for k, v in seats.items()}
    print(f"{label.splitlines()[0]:<20} fill {s['fill_rate']:.1%}")

draw(results)
print("wrote panel_seats.png")
