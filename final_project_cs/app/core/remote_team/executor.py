from __future__ import annotations

from typing import Protocol

from app.core.contracts import TeamResult, TeamTask


class TeamExecutorPort(Protocol):
    async def execute(self, task: TeamTask) -> TeamResult: ...


class LocalTeamExecutor:
    """Adapter preserving the existing in-process TeamModule behaviour."""

    def __init__(self, registry) -> None:
        self.registry = registry

    async def execute(self, task: TeamTask) -> TeamResult:
        return await self.registry.get(task.team_id).module.execute(task)
