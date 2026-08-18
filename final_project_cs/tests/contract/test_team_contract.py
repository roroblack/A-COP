from __future__ import annotations

from app.core.contracts import TeamModule, TeamManifest
from app.modules.customer_ops.order_shipping import OrderShippingTeam
from app.modules.customer_ops.return_exchange import ReturnExchangeTeam


def test_team_manifests_implement_protocol():
    for team in (OrderShippingTeam, ReturnExchangeTeam):
        assert isinstance(team.__new__(team), TeamModule)
        manifest = team.manifest
        assert isinstance(manifest, TeamManifest)
        assert manifest.contract_name == "a_cop.team_task"
        assert manifest.supported_contract_versions == ["1.0"]
        assert manifest.max_steps == 6
        assert manifest.active


def test_manifest_scopes_are_exact():
    assert OrderShippingTeam.manifest.allowed_tools == ["read.order", "read.shipment", "read.policy"]
    assert ReturnExchangeTeam.manifest.allowed_tools == ["read.order", "read.return", "read.policy"]
