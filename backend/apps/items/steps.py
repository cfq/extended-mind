"""Pipeline steps: what each item went through, and how it went.

STEPS defines the steps and how they relate. The pipeline itself lives
in code (fetch, tasks): it adds a step, pending, the moment it knows the
item needs it, and records every attempt as a run. An item's status is
derived from its steps, not stored.
"""

import uuid
from contextlib import contextmanager
from dataclasses import dataclass

from django.utils import timezone

from apps.items.models import Item, ItemStep, ItemStepRun

Outcome = ItemStepRun.Outcome
PENDING = "pending"


@dataclass(frozen=True)
class Step:
    # Steps whose results this one needs.
    depends_on: tuple[str, ...] = ()
    # Decides whether the item is usable: while it's pending, queued or
    # running, the item is fetching. Other steps are extras whose failure
    # leaves the item done.
    core: bool = False
    # The item type that needs this step ok to be done.
    required_for: str | None = None
    # Procrastinate queue its job runs on.
    queue: str = "default"


# In pipeline order: every step comes after the steps it depends on.
STEPS: dict[str, Step] = {
    "fetch_http": Step(core=True),
    "fetch_browser": Step(depends_on=("fetch_http",), core=True),
    "extract": Step(
        depends_on=("fetch_http", "fetch_browser"),
        core=True,
        required_for=Item.Type.PAGE,
    ),
    "images": Step(depends_on=("extract",)),
    "og_image": Step(depends_on=("extract",)),
    "tag": Step(depends_on=("extract",), queue="tags"),
    "save_original": Step(
        depends_on=("fetch_http",), core=True, required_for=Item.Type.IMAGE
    ),
    "dimensions": Step(depends_on=("save_original",)),
}

CORE = {name for name, step in STEPS.items() if step.core}
# Per type, the step that must have succeeded.
REQUIRED = {
    step.required_for: name for name, step in STEPS.items() if step.required_for
}
ORDER = {name: i for i, name in enumerate(STEPS)}
# Outcomes that are problems, for the item's error message.
PROBLEMS = {Outcome.FAILED, Outcome.BLOCKED, Outcome.NO_CONTENT}
# Not finished yet.
BUSY = {PENDING, Outcome.QUEUED, Outcome.RUNNING}
# Picked up: retrying now would run it twice. A pending step can be
# retried, so one whose job was lost isn't stuck.
IN_PROGRESS = {Outcome.QUEUED, Outcome.RUNNING}


def dependents(name: str) -> list[str]:
    """Every step that depends on this one, directly or not, in order."""
    found: set[str] = set()
    for other, step in STEPS.items():  # in order: dependencies come first
        if name in step.depends_on or found & set(step.depends_on):
            found.add(other)
    return [other for other in STEPS if other in found]


def ordered(steps: list[ItemStep]) -> list[ItemStep]:
    """The item's steps in pipeline order; unknown names last."""
    return sorted(steps, key=lambda s: (ORDER.get(s.name, len(ORDER)), s.position))


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


def queue(item: Item, name: str, run_id: uuid.UUID) -> ItemStepRun:
    """Marks a step as queued for this pass, until its run starts."""
    (step,) = need(item, name)
    return ItemStepRun.objects.create(
        step=step, run_id=run_id, outcome=Outcome.QUEUED, started_at=timezone.now()
    )


@contextmanager
def run(item: Item, name: str, run_id: uuid.UUID):
    """Records one attempt at a step. Ends ok unless finished otherwise;
    an exception ends it failed, with the message, and is re-raised. A
    queued run of this pass becomes this run."""
    (step,) = need(item, name)
    row = step.runs.filter(run_id=run_id, outcome=Outcome.QUEUED).first()
    if row is None:
        row = ItemStepRun(step=step, run_id=run_id)
    row.outcome = Outcome.RUNNING
    row.started_at = timezone.now()
    row.save()
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
    """pending, or the latest run's outcome (queued, running, ok...)."""
    run_ = latest(step)
    return run_.outcome if run_ else PENDING


def status(item: Item) -> tuple[str, str]:
    """The item's status and error, from its steps. Prefetch
    steps__runs for lists."""
    steps = list(item.steps.all())
    if not steps:
        return Item.Status.PENDING, ""
    states = {s.name: state(s) for s in steps}
    if any(states[name] in BUSY for name in states if name in CORE):
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
