# Stop-cliff-compile

A synergy deep-dive joining three keepers into one measurable
**long-horizon agent horizon gate**. The evidence/session stream is
source (not an executable dump). Before the next turn the gate compiles
three stages — principled stop, cliff compaction under token pressure,
and state-conditioned compile — into a final action
`continue | cliff | stop`. Blind inject (full-budget retrieval **and**
nested LLM summarization of prior cliffs) is the AMMI-like lowering.

This is **not** a fresh arXiv pack. It reuses the discrete objects from:

- [stop-dont-drift](https://github.com/StarDust-zz/stop-dont-drift)
  (Sun & Guo, [arXiv:2609.24101](https://arxiv.org/abs/2609.24101))
  — evidence stream source; principled stop (KL + quality-peak); full-budget inject drifts
- [cliff-dont-drift](https://github.com/StarDust-zz/cliff-dont-drift)
  (Nguyen et al., [arXiv:2609.26779](https://arxiv.org/abs/2609.26779))
  — live turns source; cliff truncate+signature never rewrite/nest; nested LLM summary inject drifts
- [compile-dont-inject](https://github.com/StarDust-zz/compile-dont-inject)
  (Ding et al., [arXiv:2605.07594](https://arxiv.org/abs/2605.07594))
  — memory source; Brief-State compile vs AMMI inject

```
python3 experiment.py
```

No GPU. No live model. No vendor API. No product import. Pure Python
stdlib.

## The object

```
# Stage A — principled stop (stop-dont-drift)
evidence    = publication-biased report stream (source)
Layer1      = stop if KL(q_t ‖ q_{t−1}) < δ
Layer2      = stop if r_t < r_max − α
full-budget = never stop until t = B          ← inject
stop        = Layer1 ∨ Layer2 before B

# Stage B — cliff compile (cliff-dont-drift), if continuing under token pressure
S_t         = C_{t-1} ⊕ L_t
C_t         = Cliff(L_t)                     # truncate+signature; discard C_{t-1}
nest        = LLM summary of C_{t-1} ⊕ L_t   ← inject (rewrite)

# Stage C — state-conditioned executable (compile-dont-inject)
M           = source library
b_t         = Brief State (subgoal + beliefs)
compile     = { e ∈ M | applicable(e, b_t) }
AMMI        = dump all of M at t=0 and hold   ← inject

# Final gate
stop        = principled halt before B
cliff       = continue ∧ token_pressure ∧ Cliff(L_t) ∧ ¬nest
continue    = under budget ∧ ¬token_pressure ∧ Brief-State compile
blind       = full-budget ∧ nest ∧ AMMI       ← must differ
```

**Claim.** A long-horizon evidence/session stream is not an executable.
The horizon gate joins principled stop, cliff truncate+signature
(discard prior cliff), and Brief-State compile into one measurable
`continue|cliff|stop` decision. Blind inject — keep retrieving to budget
**and** nest LLM summaries of prior cliffs — is a different lowering.

**Falsifier.** If blind full-budget+nest matched the gate on action and
fidelity; if full-budget did not raise NoEffect→Beneficial vs early stop;
if nested summary counted as faithful while cliff rewrote; if prior cliff
nested into the next and token mass nest-grew; if a stale t=0 AMMI dump
stayed correct after Brief-State Fold; if principled stop never halted
before B while full-budget did; or if the safe path failed to bound
faithful context while blind did not drift — the join collapses.

## What this pack tests (7/7 join, not each pack alone)

1. **Blind inject ≠ gate.** Full-budget + nested rewrite summary differs
   from the gate on action and/or fidelity.
2. **Full-budget raises drift.** NoEffect→Beneficial rate under
   full-budget exceeds principled early stop; blind never stops early.
3. **Nest is inject; cliff is faithful.** Nested summarization rewrites
   (⊈ source); cliff path is truncate/signature of live.
4. **Prior cliff discarded.** C_t from L_t only; token mass does not
   nest-grow across successive cliffs.
5. **Stale dump vs recompile.** After Brief-State Fold, t=0 / AMMI dump
   is the wrong executable; recompile (and cliff+recompile) wins.
6. **Stop before B.** Principled gate can `stop` with t < B; full-budget
   and blind never stop early.
7. **Safe path vs blind drift.** Principled stop **or** (continue + cliff
   compile) yields bounded faithful context; concurrent full-budget+nest
   drifts (rewrite + AMMI).

## Synergy

Joins the stop / cliff / compile cluster:

- [stop-dont-drift](https://github.com/StarDust-zz/stop-dont-drift)
  — evidence is source; principled stop is the compile; full-budget drifts
- [cliff-dont-drift](https://github.com/StarDust-zz/cliff-dont-drift)
  — live turns are source; cliff truncate+signature; nested summary drifts
- [compile-dont-inject](https://github.com/StarDust-zz/compile-dont-inject)
  — memory is source; Brief-State compile vs AMMI inject

Also sits next to
[trust-compile-gate](https://github.com/StarDust-zz/trust-compile-gate)
(CRM/outbound `send|hold|escalate` gate) and
[access-dont-dump](https://github.com/StarDust-zz/access-dont-dump).
Here the product object is the long-horizon **horizon gate**.

## Keepers

If 7/7 pass: **Evidence/session stream is source; the horizon gate
compiles principled stop + cliff truncate/signature + Brief-State
compile into continue|cliff|stop. Blind full-budget + nested summary
is the AMMI-like lowering.**
