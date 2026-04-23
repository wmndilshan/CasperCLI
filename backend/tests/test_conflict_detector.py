from models.schemas import FileHunk, PatchProposal, PatchStatus
from conflicts.detector import ConflictDetector


def test_detects_overlapping_hunks():
    p1 = PatchProposal(
        id="p1",
        task_id="t1",
        agent_id="a1",
        status=PatchStatus.PROPOSED,
        hunks=[FileHunk(path="f.txt", start_line=1, end_line=5, content="a")],
    )
    p2 = PatchProposal(
        id="p2",
        task_id="t2",
        agent_id="a2",
        status=PatchStatus.PROPOSED,
        hunks=[FileHunk(path="f.txt", start_line=4, end_line=8, content="b")],
    )
    conflicts = ConflictDetector().detect([p1, p2])
    assert len(conflicts) == 1


def test_no_conflict_disjoint():
    p1 = PatchProposal(
        id="p1",
        task_id="t1",
        agent_id="a1",
        hunks=[FileHunk(path="f.txt", start_line=1, end_line=2, content="a")],
    )
    p2 = PatchProposal(
        id="p2",
        task_id="t2",
        agent_id="a2",
        hunks=[FileHunk(path="f.txt", start_line=10, end_line=11, content="b")],
    )
    assert ConflictDetector().detect([p1, p2]) == []
