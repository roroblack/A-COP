"""Technical Entitlement Team: diagnose and propose support, never mutate access."""
from __future__ import annotations

import json
from typing import Any
from app.core.contracts import Evidence, NextAction, TeamManifest, TeamResult, TeamTask
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


class TechnicalEntitlementTeam:
    manifest = TeamManifest(team_id="technical_entitlement", display_name="Technical Entitlement Team", contract_name="a_cop.team_task", supported_contract_versions=["1.0"], capabilities=["entitlement.diagnose", "entitlement.propose_support_action"], accepted_case_types=["technical"], required_context=["case_state", "policy", "db_facts", "history"], allowed_tools=["read.entitlement", "read.account", "read.incident", "read.policy"], knowledge_scope=["entitlement", "incident", "technical"], max_steps=6, active=True, implementation_revision="2026-08-12")

    def __init__(self, tools: ReadToolbox, llm: Any | None = None) -> None:
        self.tools, self.llm = tools, llm

    async def _llm_answer(self, task: TeamTask, evidence: list[Evidence]) -> str | None:
        context = {"evidence": evidence, "context": task.context.model_dump(mode="json")}
        response = await self.llm.complete("technical.answer", task.input_text, context)
        answer = self._answer_from_response(response)
        if answer is not None:
            return answer
        repaired = await self.llm.complete(
            "technical.answer.repair",
            task.input_text,
            {**context, "invalid_response": response, "repair_instruction": "Return a JSON object with a non-empty string answer field only."},
        )
        return self._answer_from_response(repaired)

    @staticmethod
    def _answer_from_response(response: Any) -> str | None:
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                return None
        if not isinstance(response, dict):
            return None
        answer = response.get("answer")
        return answer.strip() if isinstance(answer, str) and answer.strip() else None

    async def execute(self, task: TeamTask) -> TeamResult:
        if task.context.degraded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE, failure_code="degraded_context", warnings=["정책 근거가 불완전하여 확정 답변을 만들지 않음"])
        seen: set[str] = set()
        try:
            ent = self.tools.call("read.entitlement", task.context, {}, task.allowed_tools, seen)
            account = self.tools.call("read.account", task.context, {}, task.allowed_tools, seen)
            incidents = self.tools.call("read.incident", task.context, {}, task.allowed_tools, seen)
            policy = self.tools.call("read.policy", task.context, {"query": task.input_text}, task.allowed_tools, seen)
        except ToolLoopExceeded:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="escalated", confidence=0.0, next_action=NextAction.ESCALATE, failure_code="tool_loop_guard")
        evidence = list(task.context.evidence)
        if not policy:
            return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="escalated", confidence=0.0, evidence=evidence, next_action=NextAction.ESCALATE, failure_code="policy_not_found")
        evidence.append(Evidence(evidence_id="tool:technical", source_type="tool_result", source_id="read.technical", claim="계정·권한·incident를 비교했다", value={"entitlement":ent,"account":account,"incidents":incidents,"policy":policy}, confidence=1.0, observed_at=evidence[0].observed_at if evidence else __import__("datetime").datetime.now(__import__("datetime").UTC)))
        mismatch = ent and account and ent.get("plan") != account.get("plan")
        answer = "권한 동기화 불일치가 확인되었습니다. 계정 동기화와 캐시 갱신 절차를 안내합니다." if mismatch else "계정·권한·incident를 확인했고 정책 근거에 따라 해결 절차를 안내합니다."
        if self.llm is not None:
            answer = await self._llm_answer(task, evidence)
            if answer is None:
                return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="failed", confidence=0.0, evidence=evidence, next_action=NextAction.ESCALATE, failure_code="malformed_llm_response", warnings=["LLM 응답이 TeamResult answer 스키마와 일치하지 않음"])
        return TeamResult(task_id=task.task_id, run_id=task.run_id, team_id=self.manifest.team_id, outcome="completed", confidence=0.85, answer=answer, evidence=evidence, next_action=NextAction.RESPOND, decisions=[{"classification":"entitlement_sync_mismatch" if mismatch else "technical_investigation"},{"side_effects":[] }])


__all__ = ["TechnicalEntitlementTeam"]
