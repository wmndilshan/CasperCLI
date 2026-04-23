from pathlib import Path

from runtime.team_synthesizer import TeamSynthesizer


def test_synthesizer_includes_all_archetypes(tmp_path: Path):
    team = TeamSynthesizer().synthesize(
        project_root=tmp_path,
        goal="Ship feature",
        team_size=10,
        strict=True,
    )
    kinds = {a.kind for a in team.agents}
    assert len(kinds) >= 8
    assert len(team.agents) >= 10
