"""
Interview loop scheduler for a shift-based workforce.

The problem most HR scheduling tools get wrong: they assume every interviewer is a
9-to-5 desk worker with an open calendar. In a manufacturing-heavy company most
interviewers are production or maintenance staff on rotating shifts, whose real
availability is a 90-minute window adjacent to their shift, at one physical site.

This module builds a panel-assignment model under those constraints and solves it
sharded by (site, day) so it stays tractable at 100k+ interviewers.
"""

from __future__ import annotations

import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from ortools.sat.python import cp_model


# --------------------------------------------------------------------------
# Domain model
# --------------------------------------------------------------------------

SLOT_MINUTES = 60
DAY_SLOTS = 24                      # slot t = hour t, site-local
ROUNDS_PER_LOOP = 4                 # 4 back-to-back interviews
DEBRIEF_SLOTS = 1                   # debrief occupies the slot after the last round
SENIOR_LEVEL = 4                    # level >= this counts toward the "bar raiser" rule


class Shift(Enum):
    """Availability windows are site-local hours, expressed as [start, end)."""
    CORPORATE = "corporate"
    DAY_A = "day_a"
    SWING_B = "swing_b"
    NIGHT_C = "night_c"
    WEEKEND_D = "weekend_d"
    CHANGEOVER = "changeover"      # spans the 17:00 gap


# Hours during which someone on this shift can actually sit in an interview.
# Note how narrow the production windows are compared to corporate.
SHIFT_WINDOWS: dict[Shift, list[tuple[int, int]]] = {
    Shift.CORPORATE: [(9, 17)],
    Shift.DAY_A:     [(18, 20)],     # after a 05:00-17:30 shift
    Shift.SWING_B:   [(15, 17)],     # before a 17:00-05:30 shift
    Shift.NIGHT_C:   [(14, 17)],     # before a night shift
    Shift.WEEKEND_D: [(9, 17)],      # Fri-Sun only
    # Tests Proposition 2: a small cohort spanning the 17:00 changeover reconnects
    # the staffed set. If reachability is about connectivity rather than window
    # length, day shift should come off zero WITHOUT splitting the loop.
    Shift.CHANGEOVER: [(16, 19)],
}

# Which weekdays each shift works. 0 = Monday.
SHIFT_DAYS: dict[Shift, set[int]] = {
    Shift.CORPORATE: {0, 1, 2, 3, 4},
    Shift.DAY_A:     {0, 1, 2, 3, 4},
    Shift.SWING_B:   {0, 1, 2, 3, 4},
    Shift.NIGHT_C:   {0, 1, 2, 3, 4},
    Shift.WEEKEND_D: {4, 5, 6},
    Shift.CHANGEOVER: {0, 1, 2, 3, 4},
}


@dataclass(frozen=True)
class Interviewer:
    id: int
    site: str
    function: str
    level: int
    shift: Shift
    weekly_cap: int                  # max loops this person will sit on per week

    def available_slots(self, day: int) -> set[int]:
        if day not in SHIFT_DAYS[self.shift]:
            return set()
        out: set[int] = set()
        for start, end in SHIFT_WINDOWS[self.shift]:
            out.update(range(start, end))
        return out


@dataclass(frozen=True)
class Loop:
    """One candidate's onsite loop, with candidate-proposed start windows."""
    id: int
    req_id: int
    site: str
    function: str
    level: int
    # Each option is an explicit schedule: one (day, slot) per round.
    # Contiguous options put all four rounds back-to-back on one day; split
    # options spread them across days, which is the only way a two-hour
    # post-shift window can host a panel at all.
    options: tuple[tuple[tuple[int, int], ...], ...]


@dataclass
class Assignment:
    loop_id: int
    day: int
    start_slot: int
    panel: list[int] = field(default_factory=list)   # interviewer ids, by round


# --------------------------------------------------------------------------
# Synthetic data
# --------------------------------------------------------------------------

SITES = ["fremont", "austin", "sparks", "berlin", "shanghai", "palo_alto"]
FUNCTIONS = ["manufacturing", "quality", "maintenance", "software", "supply_chain", "ehs"]

# Corporate sites skew desk-worker; factories skew shift.
SITE_SHIFT_MIX: dict[str, list[tuple[Shift, float]]] = {
    "palo_alto": [(Shift.CORPORATE, 0.95), (Shift.DAY_A, 0.05)],
    "default": [
        (Shift.CORPORATE, 0.18),
        (Shift.DAY_A, 0.28),
        (Shift.SWING_B, 0.24),
        (Shift.NIGHT_C, 0.16),
        (Shift.WEEKEND_D, 0.10),
        (Shift.CHANGEOVER, 0.04),
    ],
}


def _weighted(rng: random.Random, pairs: list[tuple[Shift, float]]) -> Shift:
    r, acc = rng.random(), 0.0
    for value, weight in pairs:
        acc += weight
        if r <= acc:
            return value
    return pairs[-1][0]


def generate_interviewers(n: int, rng: random.Random) -> list[Interviewer]:
    people: list[Interviewer] = []
    for i in range(n):
        site = rng.choice(SITES)
        mix = SITE_SHIFT_MIX.get(site, SITE_SHIFT_MIX["default"])
        level = rng.choices([1, 2, 3, 4, 5], weights=[30, 30, 22, 13, 5])[0]
        people.append(
            Interviewer(
                id=i,
                site=site,
                function=rng.choice(FUNCTIONS),
                level=level,
                shift=_weighted(rng, mix),
                # More senior people are pulled into more loops but cap out lower.
                weekly_cap=rng.choice([2, 3, 3, 4, 5]) if level < 4 else rng.choice([2, 3]),
            )
        )
    return people


def _feasible_times(
    site: str,
    level: int,
    index: dict[tuple[str, int, int], list["Interviewer"]],
    min_pool: int = 3,
) -> list[tuple[int, int]]:
    """(day, slot) pairs at this site with a real pool of level-eligible interviewers."""
    out = []
    for (s, day, slot), people in index.items():
        if s != site:
            continue
        if sum(1 for p in people if p.level >= level) >= min_pool:
            out.append((day, slot))
    return sorted(out)


def generate_loops(
    n: int,
    rng: random.Random,
    index: dict[tuple[str, int, int], list["Interviewer"]],
    n_options: int = 4,
    split: bool = False,
) -> list[Loop]:
    """Generate loops with candidate-facing scheduling options.

    Options are drawn from times that are actually staffed, which is what a real
    scheduler offers a candidate. Drawing uniformly across the clock instead makes
    split loops look artificially bad, because all four rounds then have to hit a
    staffed hour independently.

    split=False is the industry-default onsite: four interviews back to back on one
    day. split=True lets rounds land on different days, which is the only way a
    two-hour post-shift window can host a panel at all.
    """
    feasible_cache: dict[tuple[str, int], list[tuple[int, int]]] = {}
    loops: list[Loop] = []

    for i in range(n):
        site = rng.choice(SITES)
        level = rng.choices([1, 2, 3, 4, 5], weights=[35, 30, 20, 10, 5])[0]

        key = (site, level)
        if key not in feasible_cache:
            feasible_cache[key] = _feasible_times(site, level, index)
        feasible = feasible_cache[key]
        if not feasible:
            continue

        by_day: dict[int, list[int]] = defaultdict(list)
        for day, slot in feasible:
            by_day[day].append(slot)

        options: set[tuple[tuple[int, int], ...]] = set()
        guard = 0
        while len(options) < n_options and guard < 60:
            guard += 1
            if split:
                rounds = tuple(rng.choice(feasible) for _ in range(ROUNDS_PER_LOOP))
                if len(set(rounds)) < ROUNDS_PER_LOOP:
                    continue
            else:
                day = rng.choice(list(by_day))
                slots = sorted(by_day[day])
                runs, run = [], [slots[0]]
                for s in slots[1:]:
                    if s == run[-1] + 1:
                        run.append(s)
                    else:
                        runs.append(run)
                        run = [s]
                runs.append(run)
                usable = [r for r in runs if len(r) >= ROUNDS_PER_LOOP]
                if not usable:
                    continue
                chosen = rng.choice(usable)
                offset = rng.randrange(0, len(chosen) - ROUNDS_PER_LOOP + 1)
                rounds = tuple((day, chosen[offset + r]) for r in range(ROUNDS_PER_LOOP))
            options.add(rounds)

        if not options:
            continue

        loops.append(
            Loop(
                id=i,
                req_id=rng.randrange(0, max(1, n // 2)),
                site=site,
                function=rng.choice(FUNCTIONS),
                level=level,
                options=tuple(sorted(options)),
            )
        )
    return loops


# --------------------------------------------------------------------------
# Eligibility pruning
# --------------------------------------------------------------------------

POOL_CAP = 10          # candidate interviewers considered per round


def build_availability_index(
    interviewers: list[Interviewer],
) -> dict[tuple[str, int, int], list[Interviewer]]:
    """(site, day, slot) -> interviewers physically able to sit then.

    Precomputed once. Scanning the full roster per round instead is what makes the
    naive version O(loops x rounds x roster).
    """
    index: dict[tuple[str, int, int], list[Interviewer]] = defaultdict(list)
    for person in interviewers:
        for day in SHIFT_DAYS[person.shift]:
            for slot in person.available_slots(day):
                index[(person.site, day, slot)].append(person)
    return index


def eligible_interviewers(
    loop: Loop,
    day: int,
    slot: int,
    index: dict[tuple[str, int, int], list[Interviewer]],
    load: dict[int, int],
    rng: random.Random,
) -> list[Interviewer]:
    """Shortlist who can sit round `slot` of this loop.

    Two things happen here, and both matter more than the solver itself:

    1. Hard filters — right site, right time, senior enough to assess this level.
    2. A capped shortlist. At a large factory site several thousand people clear
       the hard filters for any given slot. Handing all of them to CP-SAT produces
       a model with tens of millions of booleans and no better answer. We shortlist
       POOL_CAP of them, biased toward whoever is least loaded so far, which is
       also what a human scheduler does.
    """
    pool = [p for p in index.get((loop.site, day, slot), ()) if p.level >= loop.level]
    if len(pool) <= POOL_CAP:
        return pool
    sample = rng.sample(pool, min(len(pool), POOL_CAP * 4))
    sample.sort(key=lambda p: (load.get(p.id, 0), -p.weekly_cap))
    return sample[:POOL_CAP]


# --------------------------------------------------------------------------
# Solver — one shard is one (site, day)
# --------------------------------------------------------------------------

def solve_shard(
    loops: list[Loop],
    index: dict[tuple[str, int, int], list[Interviewer]],
    load: dict[int, int],
    rng: random.Random,
    max_seconds: float = 10.0,
    workers: int = 8,
) -> tuple[list[Assignment], dict]:
    """Solve one site's full week. Sharding is per-site, not per-day, because a
    split loop can straddle days and must be reasoned about as one unit."""
    model = cp_model.CpModel()

    w: dict[tuple[int, int], cp_model.IntVar] = {}
    a: dict[tuple[int, int, int, int], cp_model.IntVar] = {}

    by_person_time: dict[tuple[int, int, int], list[cp_model.IntVar]] = defaultdict(list)
    by_person: dict[int, list[cp_model.IntVar]] = defaultdict(list)
    by_loop_person: dict[tuple[int, int], list[cp_model.IntVar]] = defaultdict(list)
    senior_by_loop: dict[int, list[cp_model.IntVar]] = defaultdict(list)
    cross_by_loop: dict[int, list[cp_model.IntVar]] = defaultdict(list)
    by_round: dict[tuple[int, int, int], list[tuple[int, cp_model.IntVar]]] = defaultdict(list)
    people_by_id: dict[int, Interviewer] = {}
    scheduled_terms: dict[int, list[cp_model.IntVar]] = defaultdict(list)

    for loop in loops:
        for k, rounds in enumerate(loop.options):
            # Debrief runs immediately after the LAST round, whichever day that is.
            # Every panelist must be free then — which is strictly harder for split
            # loops, since their rounds are spread out and the debrief anchors to the
            # tail. This constraint works against the split-loop thesis on purpose.
            d_day, d_slot = max(rounds)
            d_slot += 1
            if d_slot >= DAY_SLOTS:
                continue

            wk = model.NewBoolVar(f"w_{loop.id}_{k}")
            w[(loop.id, k)] = wk
            scheduled_terms[loop.id].append(wk)

            for r, (day, slot) in enumerate(rounds):
                pool = [
                    p for p in eligible_interviewers(loop, day, slot, index, load, rng)
                    if d_slot in p.available_slots(d_day)
                ]
                round_vars = []
                for person in pool:
                    av = model.NewBoolVar(f"a_{loop.id}_{k}_{r}_{person.id}")
                    a[(loop.id, k, r, person.id)] = av
                    by_round[(loop.id, k, r)].append((person.id, av))
                    round_vars.append(av)
                    by_person_time[(person.id, day, slot)].append(av)
                    # Panelists are occupied at debrief too, so they can't be
                    # interviewing elsewhere in that slot.
                    if (d_day, d_slot) != (day, slot):
                        by_person_time[(person.id, d_day, d_slot)].append(av)
                    by_person[person.id].append(av)
                    by_loop_person[(loop.id, person.id)].append(av)
                    people_by_id[person.id] = person
                    if person.level >= SENIOR_LEVEL:
                        senior_by_loop[loop.id].append(av)
                    if person.function != loop.function:
                        cross_by_loop[loop.id].append(av)
                model.Add(sum(round_vars) == wk)

    for loop in loops:
        terms = scheduled_terms.get(loop.id)
        if not terms:
            continue
        model.Add(sum(terms) <= 1)
        # Bar-raiser: >=1 senior panelist. Cross-functional: >=1 outside the function.
        for rule in (senior_by_loop[loop.id], cross_by_loop[loop.id]):
            if rule:
                model.Add(sum(rule) >= sum(terms))
            else:
                model.Add(sum(terms) == 0)

    for vars_ in by_person_time.values():
        if len(vars_) > 1:
            model.AddAtMostOne(vars_)
    for vars_ in by_loop_person.values():
        if len(vars_) > 1:
            model.AddAtMostOne(vars_)

    for pid, vars_ in by_person.items():
        cap = people_by_id[pid].weekly_cap
        if len(vars_) > cap:
            model.Add(sum(vars_) <= cap)

    max_load = model.NewIntVar(0, 16, "max_load")
    for vars_ in by_person.values():
        model.Add(sum(vars_) <= max_load)

    filled = sum(w.values()) if w else 0
    model.Maximize(100 * filled - max_load)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_workers = workers
    status = solver.Solve(model)

    out: list[Assignment] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for loop in loops:
            for k, rounds in enumerate(loop.options):
                key = (loop.id, k)
                if key not in w or not solver.Value(w[key]):
                    continue
                panel = []
                for r in range(ROUNDS_PER_LOOP):
                    for pid, var in by_round.get((loop.id, k, r), ()):
                        if solver.Value(var):
                            panel.append(pid)
                            break
                day, slot = rounds[0]
                out.append(Assignment(loop.id, day, slot, panel))

    return out, {
        "status": solver.StatusName(status),
        "wall_time": solver.WallTime(),
        "num_vars": len(w) + len(a),
    }


def schedule_week(
    interviewers: list[Interviewer],
    loops: list[Loop],
    max_seconds_per_shard: float = 10.0,
    seed: int = 7,
) -> tuple[list[Assignment], dict]:
    rng = random.Random(seed)
    index = build_availability_index(interviewers)
    people_by_id = {p.id: p for p in interviewers}

    loops_by_site: dict[str, list[Loop]] = defaultdict(list)
    for loop in loops:
        loops_by_site[loop.site].append(loop)

    all_assignments: list[Assignment] = []
    load: dict[int, int] = defaultdict(int)
    shard_stats = []

    t0 = time.perf_counter()
    for site, site_loops in loops_by_site.items():
        assignments, stats = solve_shard(
            site_loops, index, load, rng, max_seconds=max_seconds_per_shard
        )
        for asg in assignments:
            for pid in asg.panel:
                load[pid] += 1
        all_assignments.extend(assignments)
        stats.update(site=site, loops_in=len(site_loops), scheduled=len(assignments))
        shard_stats.append(stats)
    wall = time.perf_counter() - t0

    shift_mix: dict[str, int] = defaultdict(int)
    for pid in load:
        shift_mix[people_by_id[pid].shift.value] += load[pid]

    return all_assignments, {
        "loops_total": len(loops),
        "loops_scheduled": len(all_assignments),
        "fill_rate": len(all_assignments) / max(1, len(loops)),
        "wall_seconds": wall,
        "shards": len(shard_stats),
        "interviewers_used": len(load),
        "max_interviewer_load": max(load.values()) if load else 0,
        "mean_interviewer_load": sum(load.values()) / max(1, len(load)),
        "panel_seats_by_shift": dict(shift_mix),
        "shard_stats": shard_stats,
    }


if __name__ == "__main__":
    rng = random.Random(1337)
    people = generate_interviewers(100_000, rng)
    week_loops = generate_loops(5_000, rng)

    t0 = time.perf_counter()
    assignments, summary = schedule_week(people, week_loops, max_seconds_per_shard=5.0)
    print(f"total elapsed     {time.perf_counter() - t0:.2f}s\n")

    print(f"interviewers      {len(people):,}")
    print(f"loops requested   {summary['loops_total']:,}")
    print(f"loops scheduled   {summary['loops_scheduled']:,}  ({summary['fill_rate']:.1%})")
    print(f"shards solved     {summary['shards']}")
    print(f"wall time         {summary['wall_seconds']:.2f}s")
    print(f"interviewers used {summary['interviewers_used']:,}")
    print(f"load  max/mean    {summary['max_interviewer_load']} / {summary['mean_interviewer_load']:.2f}")
