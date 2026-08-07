# Interview loop scheduling for a shift-based workforce

Panel-assignment solver for a company where most interviewers are not desk workers.

## The premise

Interview scheduling tools assume the interviewer is a knowledge worker with an open
calendar between 9 and 5. In a manufacturing-heavy company, most of the people
qualified to assess a candidate are production, maintenance, or quality staff on
rotating shifts. Their real availability is a short window adjacent to a shift, at one
physical site, on the days that shift runs.

Modeling that honestly turns out to have a consequence nobody schedules around.

## The finding

The default onsite format — four interviews back to back on a single day — silently
excludes the largest interviewer cohort in the building.

At a factory site, availability by hour looks like this:

```
09:00–13:00   643   corporate only
14:00         1163  corporate + night shift (pre-shift)
15:00–16:00   1989  corporate + night + swing (pre-shift)
17:00         0     shift changeover, nobody
18:00–19:00   1118  day shift (post-shift)
```

The 18:00–19:00 block is 1,118 available interviewers — and a four-round back-to-back
loop can never use it, because it needs four consecutive hours and that window is two.
Day-shift production staff are the single largest cohort at the site and they fill
**0% of panel seats** under back-to-back scheduling.

Allowing a loop's four rounds to land on different days changes that:

| | back-to-back | split across days |
|---|---|---|
| loops filled | 41.3% | 59.7% |
| panel seats held by shift workers | 32.4% | 50.3% |
| day-shift (`day_a`) seats | 0% | 14.7% |
| distinct interviewers drawn on | 2,591 | 4,001 |

Both directions improve: splitting the loop fills more of them *and* spreads the load
over a wider bench, because it stops competing for the same narrow corporate window.

The 17:00 dead hour is the other artifact worth naming: it's shift changeover, and every
calendar-based tool will happily offer it.

## Model

Constraint program, one shard per site, full week in a single model. Sharding per-day
doesn't work once a loop can straddle days.

**Decision variables**

- `w[loop, option]` — loop runs under this proposed schedule (at most one per loop)
- `a[loop, option, round, interviewer]` — this person takes this round

**Constraints**

- Every round of a chosen option gets exactly one interviewer
- No interviewer in two places at the same (day, slot)
- No interviewer twice on the same panel
- Bar-raiser: ≥1 panelist at level 4+
- Cross-functional: ≥1 panelist outside the req's function
- Never assess above your own level
- Per-interviewer weekly cap

**Objective** — `maximize 100 * loops_filled - max_interviewer_load`. Filling loops
dominates; load fairness breaks ties, so nobody eats nine panels while a peer sits idle.

## What keeps it tractable

Two things, and they matter more than the solver:

1. **Precomputed availability index** — `(site, day, slot) -> [interviewer]`, built once.
   Scanning the roster per round is O(loops × rounds × roster) and OOMs at 100k people.
2. **Capped candidate pool** — several thousand people clear the hard filters for any
   given slot at a large site. Handing all of them to CP-SAT produces tens of millions
   of booleans and no better answer. Shortlist 10, biased toward least-loaded so far.
   Running load carries across shards, which is what a human scheduler does anyway.

Current numbers: 100,000 interviewers, 2,000 loops, 6 shards, ~72s wall at an 8s
per-shard budget. Small shards prove OPTIMAL in under 6s.

## Known gaps

Ordered by how much they'd change the result.

1. **Fill rate ceiling is the pool cap, not solve time.** Small shards prove OPTIMAL in
   under 6s and still land at ~75%, so the gap is `POOL_CAP=10` shortlisting colliding
   with weekly caps — not the solver giving up. Sweep POOL_CAP and plot fill vs. model
   size; that curve is the interesting engineering result.
2. **No debrief scheduling.** `DEBRIEF_SLOTS` is defined and unused. Debrief needs all
   four panelists free within 24h of the last round, which is a real constraint and is
   harder under split loops, not easier.
3. **No timezone handling.** Slots are site-local; a remote panelist across sites needs
   offset conversion.
4. **No interviewer skill/competency matching** beyond function and level.
5. **No candidate-side UX.** The whole point of a deskless-first tool is that the
   interviewer confirms from a phone or a kiosk, not Outlook.

## Running it

```
pip install ortools
python scheduler.py     # single run at 100k / 5k
python bench.py         # back-to-back vs split comparison
```
