import pytest

from models.schemas import TaskSpec, TaskStatus
from scheduler.dag_scheduler import DagScheduler


def test_ready_respects_dependencies():
    tasks = {
        "a": TaskSpec(id="a", title="a", assigned_agent_id="x"),
        "b": TaskSpec(id="b", title="b", dependencies=["a"], assigned_agent_id="x"),
    }
    sched = DagScheduler(tasks)
    assert sched.ready() == ["a"]
    sched.mark_completed("a")
    assert sched.ready() == ["b"]


def test_cycle_raises():
    tasks = {
        "a": TaskSpec(id="a", title="a", dependencies=["b"], assigned_agent_id="x"),
        "b": TaskSpec(id="b", title="b", dependencies=["a"], assigned_agent_id="x"),
    }
    with pytest.raises(ValueError):
        DagScheduler(tasks)
