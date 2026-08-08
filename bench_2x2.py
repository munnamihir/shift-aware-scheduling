import random
import scheduler as S

people = S.generate_interviewers(100_000, random.Random(1337))
index = S.build_availability_index(people)
by_id = {p.id: p for p in people}

for debrief in (False, True):
    S.ENFORCE_DEBRIEF = debrief
    for split in (False, True):
        loops = S.generate_loops(2_000, random.Random(99), index, split=split)
        asg, s = S.schedule_week(people, loops, max_seconds_per_shard=20.0)
        seats = s["panel_seats_by_shift"]; total = sum(seats.values()) or 1
        pure = mixed = 0
        for a in asg:
            sh = {by_id[i].shift.value for i in a.panel}
            if "day_a" in sh:
                if sh == {"day_a"}: pure += 1
                else: mixed += 1
        proto = "split     " if split else "contiguous"
        print(f"{proto}  debrief={'on ' if debrief else 'off'}  "
              f"fill {s['fill_rate']:5.1%}  day_a {seats.get('day_a',0)/total:5.1%}  "
              f"panels w/ day_a {pure+mixed:4d} (pure {pure}, mixed {mixed})")
