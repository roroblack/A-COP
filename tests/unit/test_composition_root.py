from __future__ import annotations

from app.composition import build_registry
from app.core.contracts import NextAction, TeamManifest, TeamResult
from app.tools.read_tools import ReadToolbox


class ExtraTeam:
    manifest = TeamManifest(
        team_id="demo_team",
        display_name="Demo Team",
        contract_name="a_cop.team_task",
        supported_contract_versions=["1.0"],
        capabilities=["demo.investigate"],
        accepted_case_types=["demo"],
        required_context=["case_state", "policy", "db_facts", "history"],
        allowed_tools=[], knowledge_scope=["demo"], implementation_revision="test",
    )

    async def execute(self, task):
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id,
                          outcome="completed", confidence=1, next_action=NextAction.RESPOND)


def test_composition_registers_the_two_builtin_teams_and_allows_extension():
    registry = build_registry(tools=ReadToolbox(lambda: None), llm=object())
    assert {manifest.team_id for manifest in registry.manifests()} == {
        "order_shipping", "return_exchange"
    }

    registry.register(ExtraTeam())
    assert registry.resolve(case_type="demo", intent="demo").manifest.team_id == "demo_team"
