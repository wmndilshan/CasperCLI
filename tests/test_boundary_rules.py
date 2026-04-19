from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.policies.boundary_rules import BoundaryPolicyEngine
from agent.runtime.patch_pipeline import PatchFragment, PatchOperation, PatchProposal
from agent.team import TeamSynthesisOptions, TeamSynthesizer


class BoundaryPolicyTests(unittest.TestCase):
    def test_backend_cannot_modify_frontend_scope_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "agent").mkdir()
            (root / "agent" / "service.py").write_text("print('backend')\n", encoding="utf-8")
            (root / "ui").mkdir()
            (root / "ui" / "page.tsx").write_text("export const Page = () => null;\n", encoding="utf-8")

            team = TeamSynthesizer().synthesize(
                "ship backend and frontend changes",
                root,
                TeamSynthesisOptions(team="fullstack", team_size=4, strict=True),
            )
            engine = BoundaryPolicyEngine(team)
            backend = next(agent for agent in team.agents if agent.id == "backend")
            proposal = PatchProposal(
                agent_id="backend",
                task_id="implement-backend",
                title="bad ui edit",
                rationale="should be rejected",
                fragments=[
                    PatchFragment(
                        path="ui/page.tsx",
                        operation=PatchOperation.UPDATE,
                        expected_old_content="export const Page = () => null;\n",
                        new_content="export const Page = () => 'changed';\n",
                    )
                ],
            )

            decision = engine.validate_patch(backend, proposal)
            self.assertFalse(decision.allowed)
            self.assertTrue(
                "path-owned-by-frontend" in decision.reasons
                or "path-outside-agent-scope" in decision.reasons
            )

    def test_schema_changes_require_migration_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "schema").mkdir()
            (root / "schema" / "users.sql").write_text("create table users(id int);\n", encoding="utf-8")

            team = TeamSynthesizer().synthesize(
                "update schema",
                root,
                TeamSynthesisOptions(team="solo", team_size=1),
            )
            engine = BoundaryPolicyEngine(team)
            generalist = next(agent for agent in team.agents if agent.id == "generalist")
            proposal = PatchProposal(
                agent_id="generalist",
                task_id="implement-generalist",
                title="schema edit",
                rationale="should require migration artifact",
                fragments=[
                    PatchFragment(
                        path="schema/users.sql",
                        operation=PatchOperation.UPDATE,
                        expected_old_content="create table users(id int);\n",
                        new_content="create table users(id bigint);\n",
                    )
                ],
            )

            decision = engine.validate_patch(generalist, proposal)
            self.assertFalse(decision.allowed)
            self.assertIn("schema-change-requires-migration-artifact", decision.reasons)

    def test_delete_obeys_ownership_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "agent").mkdir()
            (root / "agent" / "service.py").write_text("print('backend')\n", encoding="utf-8")
            (root / "ui").mkdir()
            (root / "ui" / "page.tsx").write_text("export const Page = () => null;\n", encoding="utf-8")

            team = TeamSynthesizer().synthesize(
                "ship backend and frontend changes",
                root,
                TeamSynthesisOptions(team="fullstack", team_size=4, strict=True),
            )
            engine = BoundaryPolicyEngine(team)
            backend = next(agent for agent in team.agents if agent.id == "backend")
            proposal = PatchProposal(
                agent_id="backend",
                task_id="implement-backend",
                title="bad ui delete",
                rationale="should be rejected",
                fragments=[
                    PatchFragment(
                        path="ui/page.tsx",
                        operation=PatchOperation.DELETE,
                        expected_old_content="export const Page = () => null;\n",
                        metadata={"approved_delete": True},
                    )
                ],
            )

            decision = engine.validate_patch(backend, proposal)
            self.assertFalse(decision.allowed)
            self.assertIn("path-owned-by-frontend", decision.reasons)
