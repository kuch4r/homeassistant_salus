"""Tests for the Salus switch entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.salus.models import SwitchDevice
from custom_components.salus.switch import SalusSwitch


def _make_entity(
    device: SwitchDevice,
) -> tuple[SalusSwitch, AsyncMock]:
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    gateway = AsyncMock()
    gateway.get_switch_device = MagicMock(return_value=device)
    entity = SalusSwitch(coordinator, device.unique_id, gateway)
    return entity, gateway


class TestSalusSwitchProperties:
    """Test switch entity property delegation."""

    def test_unique_id(self, switch_device):
        entity, _ = _make_entity(switch_device)
        assert entity.unique_id == "switch_001_1"

    def test_name(self, switch_device):
        entity, _ = _make_entity(switch_device)
        assert entity.name == "Kitchen Plug"

    def test_available(self, switch_device):
        entity, _ = _make_entity(switch_device)
        assert entity.available is True

    def test_is_on(self, switch_device):
        entity, _ = _make_entity(switch_device)
        assert entity.is_on is True

    def test_device_class(self, switch_device):
        entity, _ = _make_entity(switch_device)
        assert entity.device_class == "outlet"

    def test_should_poll_false(self, switch_device):
        entity, _ = _make_entity(switch_device)
        assert entity.should_poll is False

    def test_device_info(self, switch_device):
        entity, _ = _make_entity(switch_device)
        info = entity.device_info
        assert info["manufacturer"] == "SALUS"
        assert info["model"] == "SP600"


class TestSalusSwitchCommands:
    """Test switch command forwarding."""

    async def test_turn_on(self, switch_device):
        entity, gw = _make_entity(switch_device)
        await entity.async_turn_on()
        gw.turn_on_switch_device.assert_awaited_once_with("switch_001_1")

    async def test_turn_off(self, switch_device):
        entity, gw = _make_entity(switch_device)
        await entity.async_turn_off()
        gw.turn_off_switch_device.assert_awaited_once_with("switch_001_1")

    async def test_turn_on_triggers_refresh(self, switch_device):
        entity, _ = _make_entity(switch_device)
        await entity.async_turn_on()
        entity.coordinator.async_request_refresh.assert_awaited_once()

    async def test_turn_off_triggers_refresh(self, switch_device):
        entity, _ = _make_entity(switch_device)
        await entity.async_turn_off()
        entity.coordinator.async_request_refresh.assert_awaited_once()


class TestSalusSwitchPendingState:
    """The gateway reports the old state for a while after a write; the entity must
    not jump back to it (which made users switch twice)."""

    async def test_keeps_new_state_while_gateway_lags(self, switch_device):
        entity, _ = _make_entity(switch_device)  # gateway still reports on
        await entity.async_turn_off()
        assert entity.is_on is False

    async def test_follows_gateway_once_confirmed(self, switch_device):
        from dataclasses import replace

        entity, gw = _make_entity(switch_device)
        await entity.async_turn_off()
        gw.get_switch_device.return_value = replace(switch_device, is_on=False)
        assert entity.is_on is False
        # Later changes made elsewhere (Salus app, panel) are shown again.
        gw.get_switch_device.return_value = switch_device
        assert entity.is_on is True

    async def test_gives_up_after_timeout(self, switch_device, monkeypatch):
        import custom_components.salus.switch as switch_mod

        now = [1000.0]
        monkeypatch.setattr(switch_mod.time, "monotonic", lambda: now[0])
        entity, _ = _make_entity(switch_device)
        await entity.async_turn_off()
        now[0] += switch_mod.PENDING_TIMEOUT_S + 1
        assert entity.is_on is True  # command never took effect
