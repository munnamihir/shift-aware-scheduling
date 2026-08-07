"""The one chart: panel seats by shift cohort, back-to-back vs split."""
import random
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import scheduler as S

rng = random.Random(1337)
people = S.generate_interviewers(60_000, rng)
index = S.build_availability_index(people)

COHORTS = ["corporate", "weekend_d", "swing_b", "night_c", "day_a"]
results = {}
for label, split in (("Back-to-back\n(industry default)", False), ("Split across days", True)):
    loops = S.generate_loops(1_200, random.Random(99), index, split=split)
    _, s = S.schedule_week(people, loops, max_seconds_per_shard=10.0)
    seats = s["panel_seats_by_shift"]
    total = sum(seats.values()) or 1
    results[label] = [100 * seats.get(c, 0) / total for c in COHORTS]

fig, ax = plt.subplots(figsize=(7, 5))
bottoms = [0.0] * len(results)
labels = list(results)
for i, cohort in enumerate(COHORTS):
    vals = [results[l][i] for l in labels]
    ax.bar(labels, vals, bottom=bottoms, label=cohort,
           color=plt.cm.viridis(i / len(COHORTS)))
    bottoms = [b + v for b, v in zip(bottoms, vals)]

ax.set_ylabel("share of interview panel seats (%)")
ax.set_title("Who actually gets to sit on panels")
ax.legend(loc="upper right", fontsize=9)
plt.tight_layout()
plt.savefig("panel_seats.png", dpi=180)
print("wrote panel_seats.png")
