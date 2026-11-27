"""Pipeline steps: what each item went through, and how it went.

The pipeline lives in code (fetch, tasks). It adds a step, pending, the
moment it knows the item needs it, and records every attempt as a run.
An item's status is derived from its steps, not stored.
"""

import uuid
from contextlib import contextmanager

from django.utils import timezone

from apps.items.models import Item, ItemStep, ItemStepRun

Outcome = ItemStepRun.Outcome
PENDING = "pending"

# Steps that decide whether an item is usable; the rest are extras whose
# failure leaves the item done.
CORE = {"fetch_http", "fetch_browser", "extract", "save_original"}
# Per type, the step that must have succeeded.
REQUIRED = {Item.Type.PAGE: "extract", Item.Type.IMAGE: "save_original"}
# Outcomes that are problems, for the item's error message.
PROBLEMS = {Outcome.FAILED, Outcome.BLOCKED, Outcome.NO_CONTENT}


def new_run_id() -> uuid.UUID:
    """One per pass through the pipeline: a save, a retry, a reextract."""
    return uuid.uuid7()


def need(item: Item, *names: str) -> list[ItemStep]:
    """The item's steps by these names, added pending if new."""
    existing = {s.name: s for s in ItemStep.objects.filter(item=item)}
    position = len(existing)
    found = []
    for name in names:
        if name not in existing:
            existing[name] = ItemStep.objects.create(
                item=item, name=name, position=position
            )
            position += 1
        found.append(existing[name])
    return found


class Run:
    """An ItemStepRun in progress."""

    def __init__(self, row: ItemStepRun):
        self.row = row
        self.finished = False

    def note(self, **meta):
        self.row.meta.update(meta)

    def finish(self, outcome: str, message: str = "", **meta):
        self.row.outcome = outcome
        self.row.message = message
        self.row.meta.update(meta)
        self.row.finished_at = timezone.now()
        self.row.save()
        self.finished = True


@contextmanager
def run(item: Item, name: str, run_id: uuid.UUID):
    """Records one attempt at a step. Ends ok unless finished otherwise;
    an exception ends it failed, with the message, and is re-raised."""
    (step,) = need(item, name)
    row = ItemStepRun.objects.create(
        step=step, run_id=run_id, outcome=Outcome.RUNNING, started_at=timezone.now()
    )
    attempt = Run(row)
    try:
        yield attempt
    except Exception as e:
        if not attempt.finished:
            attempt.finish(Outcome.FAILED, str(e) or type(e).__name__)
        raise
    if not attempt.finished:
        attempt.finish(Outcome.OK)


def latest(step: ItemStep) -> ItemStepRun | None:
    # In Python, so prefetched runs are used.
    runs = step.runs.all()
    return max(runs, key=lambda r: (r.started_at, r.id)) if runs else None


def state(step: ItemStep) -> str:
    """pending, or the latest run's outcome."""
    run_ = latest(step)
    return run_.outcome if run_ else PENDING


def status(item: Item) -> tuple[str, str]:
    """The item's status and error, from its steps. Prefetch
    steps__runs for lists."""
    steps = list(item.steps.all())
    if not steps:
        return Item.Status.PENDING, ""
    states = {s.name: state(s) for s in steps}
    if any(
        states[name] in (PENDING, Outcome.RUNNING) for name in states if name in CORE
    ):
        return Item.Status.FETCHING, ""
    required = REQUIRED.get(item.type)
    if required and states.get(required) == Outcome.OK:
        return Item.Status.DONE, ""
    problems = [
        r for s in steps if (r := latest(s)) is not None and r.outcome in PROBLEMS
    ]
    last = max(
        problems, key=lambda r: (r.finished_at or r.started_at, r.id), default=None
    )
    return Item.Status.FAILED, last.message if last else ""
