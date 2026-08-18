from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.contracts import ContextPack, Evidence, NextAction, TeamTask, ToolNotAllowed
from app.core.verification import Facts, verify_proposal
from app.modules.customer_ops.billing import BillingSubscriptionTeam
from app.modules.customer_ops.technical import TechnicalEntitlementTeam
from app.modules.customer_ops.verification_policy import CUSTOMER_OPS_POLICY
from app.tools.read_tools import ReadToolbox, ToolLoopExceeded


NOW = datetime.now(UTC)


def pack(team_id: str, degraded: bool = False) -> ContextPack:
    return ContextPack(pack_id=uuid4(), case_id=uuid4(), team_id=team_id, tenant_id="test-team-tenant", knowledge_scope=["billing", "technical"], current_state={"customer_id": str(uuid4()), "status": "running"}, estimated_input_tokens=10, degraded=degraded, omissions=["fixture"] if degraded else [])


def task(team_id: str, capability: str, context: ContextPack, allowed: list[str]) -> TeamTask:
    return TeamTask(task_id=uuid4(), run_id=uuid4(), case_id=context.case_id, team_id=team_id, capability=capability, case_version=1, input_text="고객 요청", context=context, allowed_tools=allowed, deadline_at=NOW + timedelta(seconds=90))


class FakeTools:
    def __init__(self, values): self.values = values
    def call(self, name, context, arguments, allowed_tools, seen):
        if name not in allowed_tools: raise ToolNotAllowed(name)
        return self.values[name]


def policy():
    return [Evidence(evidence_id="policy:refund#c1", source_type="policy", source_id="refund#c1", claim="policy", value={}, confidence=1, observed_at=NOW)]


@pytest.mark.asyncio
async def test_billing_cancelled_subscription_waits_for_refund_approval():
    payment_id = str(uuid4())
    context = pack("billing_subscription")
    tools = FakeTools({"read.subscription":{"status":"cancelled","plan":"Pro"},
                       "read.payment_history":[{"payment_id": payment_id, "status":"paid","amount_cents":19900}],
                       "read.policy":policy()})
    result = await BillingSubscriptionTeam(tools).execute(task("billing_subscription", "billing.investigate", context, BillingSubscriptionTeam.manifest.allowed_tools))
    assert result.outcome == "waiting" and result.next_action is NextAction.WAIT_FOR_APPROVAL
    assert result.action_proposals[0].action_type == "refund.request"
    assert result.action_proposals[0].rationale_evidence_ids
    # ★버그사냥 2026-08-17 — Team 이 만든 제안이 실제로 verify_proposal() 을
    #   통과하는지까지 확인한다. 전에는 Team 테스트와 verification 테스트가
    #   서로 다른 손으로 만든 arguments 만 봐서, 실제 Team 출력이 매번 거부
    #   당하는 걸 아무도 못 잡았다 — 여기서 그 연결을 검사한다.
    proposal = result.action_proposals[0]
    assert proposal.arguments == {"payment_id": payment_id, "amount_cents": 19900}
    facts = Facts(collections={"payments": {payment_id: {"payment_id": payment_id, "amount_cents": 19900}}},
                  evidence_ids=frozenset(e.evidence_id for e in result.evidence))
    problems = verify_proposal(arguments=proposal.arguments, rationale_evidence_ids=proposal.rationale_evidence_ids,
                               facts=facts, policy=CUSTOMER_OPS_POLICY)
    assert problems == [], f"실제 Team 이 만든 제안이 검증을 통과하지 못한다: {problems}"


@pytest.mark.asyncio
async def test_technical_mismatch_returns_procedure_without_mutation():
    context = pack("technical_entitlement")
    tools = FakeTools({"read.entitlement":{"plan":"Free"}, "read.account":{"plan":"Pro"}, "read.incident":[], "read.policy":policy()})
    result = await TechnicalEntitlementTeam(tools).execute(task("technical_entitlement", "entitlement.diagnose", context, TechnicalEntitlementTeam.manifest.allowed_tools))
    assert result.outcome == "completed"
    assert "동기화" in result.answer
    assert result.decisions[-1]["side_effects"] == []


@pytest.mark.asyncio
async def test_degraded_context_escalates_without_answer():
    context = pack("billing_subscription", degraded=True)
    result = await BillingSubscriptionTeam(FakeTools({})).execute(task("billing_subscription", "billing.investigate", context, BillingSubscriptionTeam.manifest.allowed_tools))
    assert result.outcome == "escalated" and result.next_action is NextAction.ESCALATE
    assert result.answer is None


def test_tool_allowlist_and_repetition_guard():
    toolbox = ReadToolbox(lambda: None)
    context = pack("billing_subscription")
    with pytest.raises(ToolNotAllowed):
        toolbox.call("read.account", context, {}, ["read.subscription"], set())
    seen = set()
    # no DB call is needed: the second identical request is rejected first
    toolbox.subscription = lambda scope, **kwargs: {"status":"cancelled"}
    toolbox.call("read.subscription", context, {}, ["read.subscription"], seen)
    with pytest.raises(ToolLoopExceeded):
        toolbox.call("read.subscription", context, {}, ["read.subscription"], seen)
