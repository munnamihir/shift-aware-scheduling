# Two patches for `scheduler.py`

I cannot test these against your file — my reconstruction of your `scheduler.py` gives
23.4% where yours gives 73.7%, so it is a different model and any number I produced from
it would be meaningless. Apply these, then run the experiment and trust your own output.

Work on a branch:

```bash
git checkout -b debrief-test
```

---

## Patch 1 — the debrief constraint

Add near the top of the file, beside `POOL_CAP`:

```python
ENFORCE_DEBRIEF = True   # synchronous debrief in the slot after the final session
```

In `solve_shard`, find this block:

```python
    for loop in loops:
        for k, rounds in enumerate(loop.options):
            wk = model.NewBoolVar(f"w_{loop.id}_{k}")
            w[(loop.id, k)] = wk
            scheduled_terms[loop.id].append(wk)

            for r, (day, slot) in enumerate(rounds):
                pool = eligible_interviewers(loop, day, slot, index, load, rng)
```

Replace it with:

```python
    for loop in loops:
        for k, rounds in enumerate(loop.options):
            # Debrief occupies the slot after the LAST session, wherever that falls.
            # Every panelist must be free then, which is a much stronger requirement
            # than "each session slot is staffed by someone": it forces the whole
            # panel into a shared free slot.
            if ENFORCE_DEBRIEF:
                d_day, d_slot = max(rounds)
                d_slot += 1
                if d_slot >= DAY_SLOTS:
                    continue
            else:
                d_day = d_slot = None

            wk = model.NewBoolVar(f"w_{loop.id}_{k}")
            w[(loop.id, k)] = wk
            scheduled_terms[loop.id].append(wk)

            for r, (day, slot) in enumerate(rounds):
                pool = eligible_interviewers(loop, day, slot, index, load, rng)
                if ENFORCE_DEBRIEF:
                    pool = [p for p in pool if d_slot in p.available_slots(d_day)]
```

Then find this line, still inside the same loop:

```python
                    by_person_time[(person.id, day, slot)].append(av)
```

and replace it with:

```python
                    by_person_time[(person.id, day, slot)].append(av)
                    # A panelist is occupied during debrief too, so cannot sit
                    # elsewhere in that slot.
                    if ENFORCE_DEBRIEF and (d_day, d_slot) != (day, slot):
                        by_person_time[(person.id, d_day, d_slot)].append(av)
```

---

## Patch 2 — cohort-coherent scheduling options

This is the part that decides the experiment. Your current generator draws each session
time independently from the site's feasible slots, which are overwhelmingly corporate
hours. The all-18:00 schedule a single-cohort day-crew panel needs is almost never
*offered*, so the solver has no chance to build one. Without this patch, a zero result
tells you nothing about Corollary 11.

Add this helper above `generate_loops`:

```python
def _cohort_times(
    site: str,
    shift: Shift,
    level: int,
    index: dict[tuple[str, int, int], list["Interviewer"]],
    min_pool: int = 3,
) -> list[tuple[int, int]]:
    """(day, slot) pairs at this site staffed by THIS cohort at the required level."""
    out = []
    for (s, day, slot), people in index.items():
        if s != site:
            continue
        if sum(1 for p in people if p.shift is shift and p.level >= level) >= min_pool:
            out.append((day, slot))
    return sorted(out)
```

Then in `generate_loops`, add a parameter and a branch. The signature becomes:

```python
def generate_loops(
    n: int,
    rng: random.Random,
    index: dict[tuple[str, int, int], list["Interviewer"]],
    n_options: int = 4,
    split: bool = False,
    cohort_option_rate: float = 0.5,
) -> list[Loop]:
```

Inside the `while len(options) < n_options` loop, in the `if split:` branch, replace

```python
                rounds = tuple(rng.choice(feasible) for _ in range(ROUNDS_PER_LOOP))
```

with

```python
                # With some probability, propose a schedule drawn entirely from one
                # cohort's availability. Corollary 14 says this is the only shape a
                # disjoint cohort can be served by; drawing every option from the
                # site-wide pool means such a shape is essentially never offered.
                if rng.random() < cohort_option_rate:
                    shift = rng.choice(list(Shift))
                    ct = _cohort_times(site, shift, level, index)
                    if len(ct) < ROUNDS_PER_LOOP:
                        continue
                    rounds = tuple(rng.sample(ct, ROUNDS_PER_LOOP))
                else:
                    rounds = tuple(rng.choice(feasible) for _ in range(ROUNDS_PER_LOOP))
```

---

## The experiment

Save as `bench_2x2.py`:

```python
"""Does splitting still free the day crew once debrief is enforced?

Four cells: {contiguous, split} x {debrief off, debrief on}. The theory predicts
day_a > 0 only in (split, debrief on) AND only via single-cohort panels.
"""
import random
from collections import Counter

import scheduler as S

people = S.generate_interviewers(100_000, random.Random(1337))
index = S.build_availability_index(people)
by_id = {p.id: p for p in people}

for debrief in (False, True):
    S.ENFORCE_DEBRIEF = debrief
    for split in (False, True):
        loops = S.generate_loops(2_000, random.Random(99), index, split=split)
        asg, s = S.schedule_week(people, loops, max_seconds_per_shard=20.0)
        seats = s["panel_seats_by_shift"]
        total = sum(seats.values()) or 1

        pure = mixed = 0
        for a in asg:
            shifts = {by_id[i].shift.value for i in a.panel}
            if "day_a" in shifts:
                if shifts == {"day_a"}:
                    pure += 1
                else:
                    mixed += 1

        proto = "split     " if split else "contiguous"
        print(f"{proto}  debrief={'on ' if debrief else 'off'}  "
              f"fill {s['fill_rate']:5.1%}  "
              f"day_a {seats.get('day_a', 0) / total:5.1%}  "
              f"panels with day_a: {pure + mixed:4d} (pure {pure}, mixed {mixed})")
```

Run it:

```bash
python bench_2x2.py
```

---

## Reading the result

**If `debrief=on, split` gives day_a > 0 with `mixed = 0`** — Corollary 14 is confirmed
under the harder model, the paper's central claim holds, and it holds for the stated
reason. This is the strong outcome.

**If `debrief=on, split` gives day_a = 0** — the remedy fails under a synchronous
debrief. Then the paper's conclusion inverts: contiguity is not the binding constraint in
practice, simultaneity is, and the actionable recommendation becomes removing the
synchronous debrief rather than splitting the loop. Still publishable, different paper.

**If any run shows `mixed > 0` with debrief on** — that contradicts
Proposition 10, which would mean the debrief constraint isn't doing what the code
intends. Check the patch before believing it.

The `debrief=off` rows should reproduce your existing numbers (74.6% / 73.7%). If they
don't, something in the patch has changed behaviour it shouldn't have.
