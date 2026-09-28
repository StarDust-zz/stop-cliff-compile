#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stop-cliff-compile: long-horizon agent horizon gate joining three keepers.

Stages over an evidence/session stream (source, not an executable dump):
  A. stop-dont-drift  — principled stop (KL + quality-peak) vs full-budget
  B. cliff-dont-drift — under token pressure, cliff truncate+signature;
                        discard prior cliff; never nest summarization
  C. compile-dont-inject — executable is state-conditioned compile/cliff,
                           not AMMI dump of the whole library/history

Final action ∈ {continue, cliff, stop}.
Blind inject = full-budget retrieval AND nested LLM summary of prior cliffs.

Stdlib only. No network. No GPU. No vendor API.
Run: python3 experiment.py
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from stop_stub import (
    DEFAULT_BUDGET,
    false_beneficial_rate,
    simulate_null_query,
)
from cliff_stub import (
    Msg,
    Session,
    TOOL_RESULT_KEEP,
    any_rewritten,
    apply_cliff,
    cliff_compact,
    context_tokens,
    is_faithful_to_source,
    prior_cliff_discarded,
    summarize_nest,
)
from compile_stub import (
    BriefState,
    WeakExecutor,
    compile_step,
    inject_all,
    kitchen_memory,
)


# ---------------------------------------------------------------------------
# Session fixtures (coding-agent trajectory; tool-heavy)
# ---------------------------------------------------------------------------
SYSTEM = Msg("system", "You are a long-horizon agent. Use tools.")
TASK = Msg("task", "Complete the multi-step subgoal under a token budget.")
SHORT_GREP = "parser.py:42: assert tok == expected"


def _turn(i: int, write_body: bool = True) -> List[Msg]:
    thought = (
        f"Step {i}: inspect and apply a small patch. " + ("analysis " * 40)
    )
    long_body = f"FILE_BODY_{i}_" + ("x" * 2400)
    call_body = (
        f"write_file contents={long_body}"
        if write_body
        else f"grep -n assert src/parser.py #{i}"
    )
    path = f"src/parser_{i}.py"
    result = long_body if write_body else f"{SHORT_GREP} #{i}"
    return [
        Msg("assistant", thought),
        Msg(
            "tool_call",
            call_body,
            tool_name="file_editor" if write_body else "grep",
            path=path,
        ),
        Msg("tool_result", result),
    ]


def _long_live(n_turns: int = 6) -> List[Msg]:
    live: List[Msg] = []
    for i in range(n_turns):
        live.extend(_turn(i, write_body=(i % 2 == 0)))
    return live


def _mark_window(live: List[Msg], tag: str) -> List[Msg]:
    out: List[Msg] = []
    for m in live:
        text = m.text
        if not (m.kind == "tool_result" and len(m.text) > TOOL_RESULT_KEEP):
            text = m.text + f" {tag}"
        path = (m.path + f".{tag.lower()}") if m.path else m.path
        out.append(Msg(m.kind, text, m.tool_name, path, m.rewritten, m.is_prior_cliff))
    return out


# ---------------------------------------------------------------------------
# Horizon gate
# ---------------------------------------------------------------------------

def horizon_gate(
    *,
    # Stage A — stop evidence
    stop_policy: str = "principled",
    b: float = 0.18,
    budget: int = DEFAULT_BUDGET,
    seed: int = 7,
    reports: Optional[Sequence[bool]] = None,
    delta: float = 0.05,
    alpha: float = 0.12,
    peak_at: int = 4,
    # Stage B — session / token pressure
    session: Optional[Session] = None,
    token_pressure: bool = False,
    nest_summarize: bool = False,
    # Stage C — Brief State / memory
    brief: Optional[BriefState] = None,
    memory=None,
    force_ammi: bool = False,
) -> dict:
    """Compile stop → (optional) cliff → state-conditioned executable.

    Mapping:
      principled stop before B     → stop
      continue + token_pressure    → cliff (truncate+signature; discard prior)
      continue + no pressure       → continue (with Brief-State compile)
      blind: full_budget + nest    → drifts (must differ from gate)
    """
    audit: dict = {
        "stop_policy": stop_policy,
        "token_pressure": token_pressure,
        "nest_summarize": nest_summarize,
        "force_ammi": force_ammi,
    }

    # --- Stage A: principled stop vs full-budget ---
    stop_out = simulate_null_query(
        b,
        budget,
        seed=seed,
        delta=delta,
        alpha=alpha,
        policy=stop_policy,
        reports=reports,
        peak_at=peak_at,
    )
    audit["stopped_at"] = stop_out["stopped_at"]
    audit["stop_reason"] = stop_out["stop_reason"]
    audit["final_vote"] = stop_out["final_vote"]
    audit["drift_event"] = stop_out["drift_event"]
    audit["budget"] = budget

    if stop_out["stopped_at"] < budget and stop_policy == "principled":
        audit["action"] = "stop"
        audit["reason"] = f"principled:{stop_out['stop_reason']}"
        audit["faithful"] = True
        audit["rewritten"] = False
        return audit

    # Full-budget (or principled that hit budget) → still deciding continue/cliff
    # --- Stage B: cliff vs nest ---
    sess = session
    if sess is None:
        sess = Session(SYSTEM, TASK, prior_cliff=None, live=_long_live(6))

    if nest_summarize:
        after = summarize_nest(sess)
        audit["action"] = "cliff"  # pretends to compact, but injects
        audit["reason"] = "blind:nest_summary"
        audit["session"] = after
        audit["rewritten"] = any_rewritten(after)
        audit["faithful"] = False
        audit["tokens"] = context_tokens(after)
        # Stage C still recorded for audit
        mem = memory if memory is not None else kitchen_memory()
        br = brief if brief is not None else BriefState("find", ("find", "wash", "place"), set())
        audit["executable"] = inject_all(mem) if force_ammi else compile_step(mem, br)
        audit["ammi"] = force_ammi or True  # nest path is AMMI-like
        return audit

    if token_pressure:
        after = apply_cliff(sess)
        live_src = list(sess.live)
        cliff_msgs = list(after.prior_cliff or [])
        audit["action"] = "cliff"
        audit["reason"] = "token_pressure:cliff_compile"
        audit["session"] = after
        audit["rewritten"] = any_rewritten(after)
        audit["faithful"] = is_faithful_to_source(cliff_msgs, live_src)
        audit["tokens"] = context_tokens(after)
        audit["cliff_msgs"] = cliff_msgs
        audit["live_src"] = live_src
    else:
        after = sess
        audit["action"] = "continue"
        audit["reason"] = "under_budget:continue"
        audit["session"] = after
        audit["rewritten"] = any_rewritten(after)
        audit["faithful"] = True
        audit["tokens"] = context_tokens(after)

    # --- Stage C: state-conditioned compile vs AMMI ---
    mem = memory if memory is not None else kitchen_memory()
    br = brief if brief is not None else BriefState("find", ("find", "wash", "place"), set())
    if force_ammi:
        exe = inject_all(mem)
        audit["ammi"] = True
    else:
        exe = compile_step(mem, br)
        audit["ammi"] = False
    audit["executable"] = exe
    audit["brief_subgoal"] = br.subgoal
    return audit


def blind_inject(
    *,
    session: Optional[Session] = None,
    brief: Optional[BriefState] = None,
    b: float = 0.18,
    budget: int = DEFAULT_BUDGET,
    seed: int = 7,
) -> dict:
    """AMMI-like lowering: full-budget retrieval + nested rewrite summary."""
    return horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        nest_summarize=True,
        force_ammi=True,
        session=session,
        brief=brief,
        b=b,
        budget=budget,
        seed=seed,
    )


def _ok(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Seven join assertions (test the JOIN, not each pack alone)
# ---------------------------------------------------------------------------

def scenario_1():
    """Blind inject (full-budget + nested rewrite) ≠ gate action / fidelity."""
    live = _long_live(6)
    sess = Session(SYSTEM, TASK, prior_cliff=None, live=live)
    # Force gate past Stage A stop by using full reports that keep principled
    # from stopping early only when we want continue/cliff — use a seed where
    # principled does stop early, and compare actions/fidelity to blind.
    gate = horizon_gate(
        stop_policy="principled",
        token_pressure=True,
        nest_summarize=False,
        session=Session(SYSTEM, TASK, prior_cliff=None, live=list(live)),
        seed=7,
        b=0.18,
        budget=20,
        delta=0.05,
        alpha=0.12,
    )
    blind = blind_inject(session=sess, seed=7, b=0.18, budget=20)

    # Blind always retrieves to budget and rewrites; gate either stops early
    # or cliffs faithfully — never rewritten.
    _ok(blind["rewritten"] is True, "blind nest must rewrite")
    _ok(blind["faithful"] is False, "blind nest is not faithful")
    _ok(blind["stopped_at"] == blind["budget"], "blind full-budget never stops early")
    _ok(blind["ammi"] is True, "blind forces AMMI dump")

    if gate["action"] == "stop":
        _ok(gate["stopped_at"] < gate["budget"], "principled stop before B")
        _ok(gate["faithful"] is True, "stop path is faithful")
        _ok(gate["rewritten"] is False, "stop path never rewrites")
        _ok(gate["action"] != blind["action"] or gate["rewritten"] != blind["rewritten"],
            "gate stop must differ from blind")
    else:
        _ok(gate["action"] == "cliff", f"expected cliff under pressure; got {gate['action']}")
        _ok(gate["faithful"] is True, "cliff must be faithful")
        _ok(gate["rewritten"] is False, "cliff must not rewrite")
        _ok(gate["rewritten"] != blind["rewritten"], "fidelity must differ")

    return {
        "gate": gate["action"],
        "gate_faithful": gate["faithful"],
        "blind_action": blind["action"],
        "blind_rewritten": blind["rewritten"],
        "blind_stopped_at": blind["stopped_at"],
        "gate_stopped_at": gate["stopped_at"],
    }


def scenario_2():
    """Full-budget without principled stop raises NoEffect→Beneficial vs early stop."""
    b = 0.18
    budget = 20
    n = 300
    early = false_beneficial_rate(
        b, budget, "principled", n_trials=n, seed=7, delta=0.05, alpha=0.12
    )
    full = false_beneficial_rate(
        b, budget, "full_budget", n_trials=n, seed=7, delta=0.05, alpha=0.12
    )
    _ok(full > early, f"full-budget drift risk {full:.3f} should exceed early {early:.3f}")
    _ok(full - early > 0.02, f"gap too small: full={full:.3f} early={early:.3f}")

    # Join surface: gate with principled can stop; blind full-budget never does
    g = horizon_gate(stop_policy="principled", seed=11, b=b, budget=budget)
    bl = blind_inject(seed=11, b=b, budget=budget)
    _ok(bl["stopped_at"] == budget, bl["stopped_at"])
    # At least one of: gate stopped early, or full risk > early (already asserted)
    _ok(
        g["action"] == "stop" or full > early,
        "join must show principled path safer than full-budget",
    )
    return {
        "early_rate": round(early, 4),
        "full_rate": round(full, 4),
        "gap": round(full - early, 4),
        "gate_action": g["action"],
        "blind_stopped_at": bl["stopped_at"],
    }


def scenario_3():
    """Nested summarization is inject (rewrite; ⊈ source); cliff path is faithful."""
    live = _long_live(6)
    sess = Session(SYSTEM, TASK, prior_cliff=None, live=live)

    # Force past Stage A by using full_budget so we exercise Stage B join
    cliff_path = horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        nest_summarize=False,
        session=Session(SYSTEM, TASK, prior_cliff=None, live=list(live)),
    )
    nest_path = horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        nest_summarize=True,
        session=sess,
    )
    _ok(cliff_path["action"] == "cliff", cliff_path["action"])
    _ok(cliff_path["faithful"] is True, "cliff must be faithful truncate/signature")
    _ok(cliff_path["rewritten"] is False, "cliff must not rewrite")
    _ok(nest_path["rewritten"] is True, "nest must rewrite")
    _ok(nest_path["faithful"] is False, "nest is not ⊆ source")
    # Explicit fragment check
    cliff_msgs = cliff_path.get("cliff_msgs") or list(
        (cliff_path["session"].prior_cliff or [])
    )
    _ok(is_faithful_to_source(cliff_msgs, live), "cliff ⊆ live source")
    nest_msgs = list(nest_path["session"].prior_cliff or [])
    _ok(any(m.rewritten for m in nest_msgs), "nest messages carry rewrite flag")
    _ok(
        not is_faithful_to_source(nest_msgs, live),
        "nest summary must not count as faithful to live",
    )
    return {
        "cliff_faithful": cliff_path["faithful"],
        "nest_rewritten": nest_path["rewritten"],
        "n_cliff": len(cliff_msgs),
        "n_nest": len(nest_msgs),
    }


def scenario_4():
    """Prior cliff discarded not nested; token mass does not nest-grow."""
    live1 = _mark_window(_long_live(6), "WINDOW1_UNIQUE")
    s0 = Session(SYSTEM, TASK, prior_cliff=None, live=live1)
    g1 = horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        nest_summarize=False,
        session=s0,
    )
    _ok(g1["action"] == "cliff", g1["action"])
    c1 = list(g1["session"].prior_cliff or [])
    tokens_1 = g1["tokens"]

    live2 = _mark_window(_long_live(6), "WINDOW2_UNIQUE")
    s1 = Session(SYSTEM, TASK, prior_cliff=c1, live=live2)
    g2 = horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        nest_summarize=False,
        session=s1,
    )
    _ok(g2["action"] == "cliff", g2["action"])
    c2 = list(g2["session"].prior_cliff or [])
    tokens_2 = g2["tokens"]

    _ok(prior_cliff_discarded(c1, live2, c2), "C_{t-1} must be discarded, not nested")
    _ok(tokens_2 <= tokens_1 * 1.15 + 50, f"token nest-grow: t1={tokens_1} t2={tokens_2}")
    _ok(not any(m.rewritten for m in c2), "second cliff must not rewrite")

    # Nest path grows rewrite mass
    nest = horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        nest_summarize=True,
        session=Session(SYSTEM, TASK, prior_cliff=c1, live=live2),
    )
    _ok(nest["rewritten"] is True, "nest inject rewrites")
    return {
        "tokens_c1": tokens_1,
        "tokens_c2": tokens_2,
        "discarded": True,
        "nest_rewritten": nest["rewritten"],
    }


def scenario_5():
    """After Brief-State change, stale t=0 dump is wrong; recompile/cliff from live wins."""
    M = kitchen_memory()
    brief = BriefState("find", ("find", "wash", "place"), set())
    # Gate at t=0 with find subgoal
    g0 = horizon_gate(
        stop_policy="full_budget",
        token_pressure=False,
        brief=brief,
        memory=M,
    )
    stale = g0["executable"]
    _ok(tuple(e.label for e in stale.entries) == ("find-apple",), stale.entries)

    # Fold subgoal; AMMI dump still whole library; recompile follows wash
    brief.fold("find", "wash", frozenset({"have-apple"}))
    ammi = inject_all(M)
    g1 = horizon_gate(
        stop_policy="full_budget",
        token_pressure=False,
        brief=brief,
        memory=M,
        force_ammi=False,
    )
    now = g1["executable"]
    _ok(tuple(e.label for e in now.entries) == ("wash-apple",), now.entries)
    _ok(set(e.label for e in ammi.entries) == {e.label for e in M}, "AMMI dumps all")
    _ok(ammi.entries != now.entries, "stale/AMMI dump ≠ recompiled executable")

    ex = WeakExecutor()
    _ok(ex.act(stale, brief, default="wander") == "open-fridge", "stale find artifact")
    _ok(ex.act(now, brief, default="wander") == "use-faucet", "recompile wins")
    _ok(ex.act(ammi, brief, default="wander") == "pick-banana", "AMMI trap on weak executor")

    # Under token pressure the cliff path still recompiles Brief State, not dump
    live = _long_live(5)
    g_cliff = horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        session=Session(SYSTEM, TASK, prior_cliff=None, live=live),
        brief=brief,
        memory=M,
    )
    _ok(g_cliff["action"] == "cliff", g_cliff["action"])
    _ok(
        tuple(e.label for e in g_cliff["executable"].entries) == ("wash-apple",),
        g_cliff["executable"].entries,
    )
    return {
        "stale": [e.label for e in stale.entries],
        "recompiled": [e.label for e in now.entries],
        "ammi_action": "pick-banana",
        "recompile_action": "use-faucet",
        "cliff_subgoal": g_cliff["brief_subgoal"],
    }


def scenario_6():
    """Gate can stop before budget B when KL/quality says so; full-budget never stops early."""
    budget = 20
    # Deterministic: principled with decline-friendly peak
    g = horizon_gate(
        stop_policy="principled",
        b=0.18,
        budget=budget,
        seed=7,
        delta=0.05,
        alpha=0.12,
        peak_at=4,
    )
    full = horizon_gate(
        stop_policy="full_budget",
        b=0.18,
        budget=budget,
        seed=7,
        delta=0.05,
        alpha=0.12,
    )
    _ok(full["stopped_at"] == budget, f"full-budget must hit B; got {full['stopped_at']}")
    _ok(full["action"] in ("continue", "cliff"), f"full-budget never stop; got {full['action']}")
    _ok(g["action"] == "stop", f"principled should stop; got {g['action']} reason={g.get('reason')}")
    _ok(g["stopped_at"] < budget, f"stop before B; got t={g['stopped_at']}")
    _ok(g["stop_reason"] in ("kl", "decline", "stop"), g["stop_reason"])

    # Blind never stops early either
    bl = blind_inject(budget=budget, seed=7)
    _ok(bl["stopped_at"] == budget, bl["stopped_at"])
    return {
        "principled_t": g["stopped_at"],
        "principled_reason": g["stop_reason"],
        "full_t": full["stopped_at"],
        "blind_t": bl["stopped_at"],
        "B": budget,
    }


def scenario_7():
    """Safe path: principled stop OR (continue + cliff) yields bounded faithful context;
    concurrent full-budget + nest drifts."""
    budget = 20
    live = _long_live(6)

    # Safe path A: principled stop
    stop_path = horizon_gate(
        stop_policy="principled",
        seed=7,
        b=0.18,
        budget=budget,
        session=Session(SYSTEM, TASK, prior_cliff=None, live=list(live)),
    )
    _ok(stop_path["action"] == "stop", stop_path["action"])
    _ok(stop_path["faithful"] is True, "stop is faithful")
    _ok(stop_path["rewritten"] is False, "stop does not rewrite")

    # Safe path B: continue under pressure → cliff compile (force past stop via full_budget)
    cliff_path = horizon_gate(
        stop_policy="full_budget",
        token_pressure=True,
        nest_summarize=False,
        session=Session(SYSTEM, TASK, prior_cliff=None, live=list(live)),
        brief=BriefState("wash", ("wash", "place"), {"have-apple"}),
    )
    _ok(cliff_path["action"] == "cliff", cliff_path["action"])
    _ok(cliff_path["faithful"] is True, "cliff faithful")
    _ok(cliff_path["rewritten"] is False, "cliff no rewrite")
    tokens_safe = cliff_path["tokens"]
    raw_tokens = context_tokens(Session(SYSTEM, TASK, prior_cliff=None, live=live))
    _ok(tokens_safe < raw_tokens, f"cliff bounds tokens: {tokens_safe} vs raw {raw_tokens}")
    _ok(
        tuple(e.label for e in cliff_path["executable"].entries) == ("wash-apple",),
        "state-conditioned executable, not whole dump",
    )

    # Drift path: full-budget + nest
    drift = blind_inject(
        session=Session(SYSTEM, TASK, prior_cliff=None, live=list(live)),
        budget=budget,
        seed=7,
    )
    _ok(drift["rewritten"] is True, "blind nest rewrites")
    _ok(drift["faithful"] is False, "blind nest unfaithful")
    _ok(drift["stopped_at"] == budget, "blind retrieves to B")
    _ok(drift["ammi"] is True, "blind dumps library")
    # Join inequality
    _ok(
        (stop_path["action"] == "stop" or cliff_path["faithful"])
        and drift["rewritten"]
        and not drift["faithful"],
        "safe path bounded/faithful; blind drifts",
    )
    return {
        "stop": stop_path["action"],
        "cliff_tokens": tokens_safe,
        "raw_tokens": raw_tokens,
        "cliff_exe": [e.label for e in cliff_path["executable"].entries],
        "blind_rewritten": drift["rewritten"],
        "blind_ammi": drift["ammi"],
    }


SCENARIOS = [
    ("1_blind_inject_ne_gate", scenario_1),
    ("2_full_budget_raises_drift", scenario_2),
    ("3_nest_inject_vs_cliff_faithful", scenario_3),
    ("4_prior_cliff_discarded_no_nest_grow", scenario_4),
    ("5_stale_dump_vs_recompile", scenario_5),
    ("6_stop_before_budget", scenario_6),
    ("7_safe_path_vs_blind_drift", scenario_7),
]


def main() -> int:
    passed = 0
    for name, fn in SCENARIOS:
        try:
            detail = fn()
            passed += 1
            print(f"PASS  {name}: {detail}")
        except AssertionError as e:
            print(f"FAIL  {name}: {e}")
        except Exception as e:
            print(f"ERROR {name}: {e}")
    total = len(SCENARIOS)
    print(f"\n{passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
