"""Hybrid runtime package.

This module keeps imports intentionally lazy so leaf modules such as
`agent.runtime.task_graph` can be imported without pulling the whole
orchestrator dependency graph into memory.
"""

from importlib import import_module

__all__ = [
    "CommitDecision",
    "CommitStatus",
    "HybridOrchestrator",
    "HybridRunRequest",
    "HybridRunResult",
    "LockLease",
    "LockManager",
    "LockRequest",
    "LockTable",
    "LockType",
    "PatchBundle",
    "PatchFragment",
    "PatchPipeline",
    "PatchProposal",
    "PatchValidationResult",
    "RuntimeEvent",
    "RuntimeEventBus",
    "RuntimeEventType",
    "Scheduler",
    "SessionOrchestrator",
    "TaskEdge",
    "TaskGraph",
    "TaskNode",
    "TaskResult",
    "TaskStatus",
]

_MODULE_BY_NAME = {
    "CommitDecision": "agent.runtime.patch_pipeline",
    "CommitStatus": "agent.runtime.patch_pipeline",
    "HybridOrchestrator": "agent.runtime.orchestrator",
    "HybridRunRequest": "agent.runtime.orchestrator",
    "HybridRunResult": "agent.runtime.orchestrator",
    "LockLease": "agent.runtime.lock_manager",
    "LockManager": "agent.runtime.lock_manager",
    "LockRequest": "agent.runtime.lock_manager",
    "LockTable": "agent.runtime.lock_manager",
    "LockType": "agent.runtime.lock_manager",
    "PatchBundle": "agent.runtime.patch_pipeline",
    "PatchFragment": "agent.runtime.patch_pipeline",
    "PatchPipeline": "agent.runtime.patch_pipeline",
    "PatchProposal": "agent.runtime.patch_pipeline",
    "PatchValidationResult": "agent.runtime.patch_pipeline",
    "RuntimeEvent": "agent.runtime.events",
    "RuntimeEventBus": "agent.runtime.events",
    "RuntimeEventType": "agent.runtime.events",
    "Scheduler": "agent.runtime.scheduler",
    "SessionOrchestrator": "agent.runtime.orchestrator",
    "TaskEdge": "agent.runtime.task_graph",
    "TaskGraph": "agent.runtime.task_graph",
    "TaskNode": "agent.runtime.task_graph",
    "TaskResult": "agent.runtime.task_graph",
    "TaskStatus": "agent.runtime.task_graph",
}


def __getattr__(name: str):
    module_name = _MODULE_BY_NAME.get(name)
    if not module_name:
        raise AttributeError(name)
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
