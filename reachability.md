# Cohort reachability under contiguity constraints

Working note. The question: can the day-shift exclusion be stated as a theorem rather
than a simulation result?

## Setup

Let $T = \{1, \dots, n\}$ be a discretized time horizon (slots).

Let $P$ be a population of *assessors*. Each $p \in P$ has an **availability set**
$A_p \subseteq T$ — the slots in which $p$ can participate.

A **cohort** $C \subseteq P$ is a maximal set of assessors sharing an availability
pattern; write $A_C$ for that common set. (Shifts: corporate, day, swing, night.)

A **process** requires $k$ rounds, each filled by one assessor. A **protocol**
$\Pi \subseteq T^k$ is the set of round-time tuples the process permits. Two of interest:

- **Contiguous:** $\Pi_{\text{cont}} = \{(t, t+1, \dots, t+k-1) : t \in T\}$ — the
  standard back-to-back onsite loop.
- **Split:** $\Pi_{\text{split}} = \{(t_1, \dots, t_k) : t_i \text{ distinct}\}$ — rounds
  may fall anywhere.

Let $N(t) = \{p \in P : t \in A_p\}$ be the assessors available at slot $t$, and let

$$S = \{t \in T : N(t) \neq \emptyset\}$$

be the **staffed set**. A schedule $s \in \Pi$ is **viable** if $N(s_i) \neq \emptyset$
for every round $i$ — that is, every round can be filled by someone.

**Definition (reachability).** Assessor $p$ is *reachable* under $\Pi$ if there exists a
viable $s \in \Pi$ and a round $i$ with $s_i \in A_p$. A cohort is *excluded* if no member
is reachable.

Reachability is a necessary condition for participation, not a sufficient one — it says
a person *could* be assigned, not that they will be, and says nothing about what share of
assignments they receive.

## Contiguous protocols

Write $S$ as a disjoint union of **maximal runs** $R_1, \dots, R_m$ of consecutive slots.

**Proposition 1.** Under $\Pi_{\text{cont}}$, assessor $p$ is reachable if and only if
there exists a run $R_j$ with $|R_j| \geq k$ and $A_p \cap R_j \neq \emptyset$.

*Proof.* ($\Leftarrow$) If $|R_j| \geq k$ and $t^* \in A_p \cap R_j$, choose a window of
$k$ consecutive slots inside $R_j$ containing $t^*$; possible since $R_j$ is a run of
length at least $k$. Every slot of that window lies in $R_j \subseteq S$, so the schedule
is viable, and $t^*$ is one of its rounds.

($\Rightarrow$) A viable contiguous schedule occupies $k$ consecutive slots, each in $S$;
consecutive slots of $S$ lie in a common maximal run, so the schedule lies within some
$R_j$ with $|R_j| \geq k$. If $p$ fills a round then $A_p$ meets $R_j$. $\square$

The content is the quantifier: reachability depends on the run containing a cohort's
window, **not on the length of that window**. A cohort whose own availability is only two
slots long is reachable whenever those slots abut enough other staffed slots to complete a
run of length $k$.

**Corollary 1 (isolation).** If $A_C \subseteq R_j$ for a run with $|R_j| < k$, cohort $C$
is excluded.

This is the day-shift case, and on its own it is close to arithmetic. The next result is
not.

## Severance

**Proposition 2.** Let $t^\dagger \in S$ and let $S' = S \setminus \{t^\dagger\}$. There
exist populations for which some cohort is reachable under $S$ and excluded under $S'$,
even though no member of that cohort is available at $t^\dagger$.

*Proof by construction.* Take $k = 4$ and a cohort $C$ with $A_C = \{18, 19\}$, and
another cohort $D$ with $A_D = \{14,15,16,17\}$. Then $S = \{14,\dots,19\}$ is a single
run of length $6 \geq 4$, so by Proposition 1 every member of $C$ is reachable — e.g. the
window $\{16,17,18,19\}$ is viable and contains slot 18.

Now remove slot 17 from the staffed set (nobody is available during shift changeover).
$S' = \{14,15,16\} \cup \{18,19\}$ splits into runs of length 3 and 2, both less than $k$.
No viable contiguous schedule exists at all, and $C$ is excluded — despite $17 \notin
A_C$. $\square$

**This is the actual result.** The day shift is not excluded because their window is
short. They are excluded because an unstaffed changeover hour severs their window from
the adjacent staffed block. Cohort reachability is a property of the *connectivity* of
the staffed set, and a single unstaffed slot can disconnect it.

It also yields an intervention nobody would think to try: **staffing the changeover hour
restores day-shift reachability without changing the loop format at all.**

### Tested, and this is where it gets interesting

Adding a small cohort (4% of the factory mix) available 16:00–18:00 staffs the changeover
slot. Under back-to-back scheduling:

| | day-shift seats |
|---|---|
| changeover staffed, debrief enforced | **0%** |
| changeover staffed, debrief removed | **4.8%** |
| baseline (changeover unstaffed), debrief removed | 0% |

Proposition 2 is confirmed by the middle row: reconnecting the staffed set does free the
day shift under a contiguous protocol, exactly as predicted, with no change to the loop
format.

But the top row shows the prediction failing in practice, because the model above omits a
constraint the simulator enforces. See below.

## The debrief constraint, and a stronger exclusion

Viability as defined above asks only that *each* round slot be staffed by *someone*. Real
loops add a debrief: after the final round, **all $k$ panelists must be simultaneously
free**.

Formally, extend a schedule $s$ with a debrief slot $d(s)$. A panel assignment
$(p_1, \dots, p_k)$ is *debrief-feasible* if $d(s) \in A_{p_i}$ for every $i$.

**Proposition 4.** Debrief-feasibility requires
$\bigcap_{i} A_{p_i} \ni d(s)$ — the entire panel must share availability at a common
slot. Since $d(s)$ trails the last round, this forces every panelist to be available at
the *tail* of the schedule.

**Corollary 3.** A cohort available only at the tail of the day cannot be paired with
cohorts that are unavailable there, regardless of contiguity. Day shift (18:00–19:00)
cannot sit with corporate (09:00–17:00) on any loop, because no slot after a shared round
lies in both windows.

This is a strictly stronger exclusion than Proposition 2, and it is not repaired by
staffing the changeover hour — the 0% in the top row above. It is repaired by splitting
the loop, which is why the headline result survives the debrief constraint while this
intervention does not.

**The two mechanisms are independent.** Contiguity excludes cohorts whose window is
severed from a long enough run. Synchronous debrief excludes cohorts whose window does not
intersect the panel's common availability. Fixing either alone is insufficient; the split
protocol happens to address both.

Open: is asynchronous or next-day debrief sufficient on its own, without splitting? The
model predicts yes. Untested.

## Split protocols

**Proposition 3.** Under $\Pi_{\text{split}}$, assessor $p$ is reachable if and only if
$A_p \neq \emptyset$ and $|S| \geq k$.

*Proof.* ($\Rightarrow$) immediate. ($\Leftarrow$) pick $t^* \in A_p \subseteq S$ and any
$k-1$ further distinct slots of $S$; the resulting tuple is viable and contains
$t^*$. $\square$

**Corollary 2.** Contiguity is necessary for structural exclusion: if a population admits
any viable schedule at all, then under $\Pi_{\text{split}}$ no cohort with nonempty
availability is excluded.

So the exclusion is caused by the protocol, not by the workforce.

## What this does and does not establish

Establishes: exclusion follows from contiguity plus disconnection of the staffed set, and
disappears when contiguity is dropped. Both directions are exact and need no simulation.

Does **not** establish: anything about *share*. Proposition 3 says the day shift becomes
reachable; it says nothing about their reaching ~15% of seats. That number depends on
cohort sizes, capacities, and the objective, and remains empirical.

Nor does it establish that splitting is *costless* — the observed flat fill rate is an
empirical property of one population, not a theorem.

## Open

1. Under what conditions on cohort sizes does reachability translate into proportional
   share? This is the gap between Proposition 3 and the simulation, and it is the
   interesting question.
2. Given a budget of $b$ additional staffed slots, which slots maximally increase the
   number of reachable cohorts? A covering problem over runs; plausibly submodular.
3. Partial contiguity — rounds must fall within a span of $w \geq k$ slots. Propositions 1
   and 3 are the endpoints $w = k$ and $w = n$. The transition between them is unstudied
   and is where real protocols live.
