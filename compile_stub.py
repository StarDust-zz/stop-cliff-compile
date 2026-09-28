"""Minimal compile-dont-inject stub for the stop-cliff-compile join.

Faithful subset of Ding et al., arXiv:2605.07594 (compile-dont-inject):
memory is source; Brief-State compile vs AMMI inject.
Copied into this pack so the join is self-contained for GitHub.

Stdlib only. No GPU, no network, no product imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Literal, Optional

Action = str
Kind = Literal["experience", "brief", "hybrid", "noaction"]
Channel = Literal["text", "both"]


@dataclass(frozen=True)
class MemoryEntry:
    label: str
    when: str
    needs: FrozenSet[str]
    text: str
    percept: FrozenSet[str]
    action: Action
    trap: bool = False


@dataclass
class BriefState:
    subgoal: str
    pending: tuple[str, ...]
    beliefs: set[str] = field(default_factory=set)

    def fold(self, done: str, next_subgoal: Optional[str], new_beliefs: FrozenSet[str] = frozenset()) -> None:
        self.pending = tuple(s for s in self.pending if s != done)
        if next_subgoal is not None:
            self.subgoal = next_subgoal
        self.beliefs.update(new_beliefs)


@dataclass(frozen=True)
class Compiled:
    kind: Kind
    entries: tuple[MemoryEntry, ...]
    delta: tuple[str, ...] = ()
    channel: Channel = "both"

    @property
    def text(self) -> tuple[str, ...]:
        return tuple(e.text for e in self.entries)

    @property
    def percept(self) -> FrozenSet[str]:
        if self.channel == "text":
            return frozenset()
        out: set[str] = set()
        for e in self.entries:
            out.update(e.percept)
        return frozenset(out)


def applicable(entry: MemoryEntry, brief: BriefState) -> bool:
    return entry.when == brief.subgoal and entry.needs <= brief.beliefs


def compile_step(
    memory: tuple[MemoryEntry, ...],
    brief: BriefState,
    *,
    update: tuple[str, ...] = (),
    channel: Channel = "both",
) -> Compiled:
    hits = tuple(e for e in memory if applicable(e, brief))
    if hits and update:
        return Compiled("hybrid", hits, update, channel)
    if hits:
        return Compiled("experience", hits, channel=channel)
    if update:
        return Compiled("brief", (), update, channel)
    return Compiled("noaction", (), channel=channel)


def inject_all(memory: tuple[MemoryEntry, ...]) -> Compiled:
    """AMMI: the whole library, once, regardless of Brief State."""
    return Compiled("experience", memory)


class WeakExecutor:
    """Small executor. AMMI lets a global trap shout down the useful line."""

    def __init__(self, *, need_percept: bool = False):
        self.need_percept = need_percept

    def act(self, compiled: Compiled, brief: BriefState, default: Action) -> Action:
        if compiled.kind == "noaction" or not compiled.entries:
            return default
        if any(e.trap for e in compiled.entries) and len(compiled.entries) > 1:
            return next(e.action for e in compiled.entries if e.trap)
        best = next((e for e in compiled.entries if applicable(e, brief)), compiled.entries[0])
        if self.need_percept and best.percept and not (best.percept <= compiled.percept):
            return default
        return best.action


def kitchen_memory() -> tuple[MemoryEntry, ...]:
    return (
        MemoryEntry(
            "find-apple",
            when="find",
            needs=frozenset(),
            text="look in the fridge for the apple",
            percept=frozenset({"fridge-left"}),
            action="open-fridge",
        ),
        MemoryEntry(
            "wash-apple",
            when="wash",
            needs=frozenset({"have-apple"}),
            text="use the faucet",
            percept=frozenset({"faucet-behind-microwave"}),
            action="use-faucet",
        ),
        MemoryEntry(
            "place-apple",
            when="place",
            needs=frozenset({"clean-apple"}),
            text="put the apple on the table",
            percept=frozenset({"table-center"}),
            action="put-table",
        ),
        MemoryEntry(
            "banana-trap",
            when="always",
            needs=frozenset(),
            text="always pick up the banana first",
            percept=frozenset(),
            action="pick-banana",
            trap=True,
        ),
    )
