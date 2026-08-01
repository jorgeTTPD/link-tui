"""TUI tests using run_test (headless), without touching real hardware."""
import unittest
from unittest.mock import AsyncMock, patch

from textual.widgets import Input, ListView, Switch

from link_tui.app import NetworkApp


class TestApp(unittest.IsolatedAsyncioTestCase):
    @patch("link_tui.backend.wifi.radio_status", new_callable=AsyncMock, return_value=True)
    @patch("link_tui.backend.bluetooth.powered", new_callable=AsyncMock, return_value=True)
    @patch("link_tui.backend.wifi.list_networks", new_callable=AsyncMock, return_value=[])
    @patch("link_tui.backend.bluetooth.list_devices", new_callable=AsyncMock, return_value=[])
    async def test_mount_and_quit(self, *_mocks):
        app = NetworkApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            self.assertIsNotNone(app.query_one("#wifi-list", ListView))
            self.assertIsNotNone(app.query_one("#bt-list", ListView))
            self.assertIsNotNone(app.query_one("#wifi-switch", Switch))
            await pilot.press("q")
        self.assertTrue(app._exit)

    @patch("link_tui.backend.wifi.radio_status", new_callable=AsyncMock, return_value=True)
    @patch("link_tui.backend.bluetooth.powered", new_callable=AsyncMock, return_value=True)
    @patch(
        "link_tui.backend.wifi.list_networks",
        new_callable=AsyncMock,
        return_value=[
            {"active": True, "ssid": "MiCasa_5G", "signal": 92, "security": "WPA2"},
            {"active": False, "ssid": "Cafeteria_Free", "signal": 40, "security": ""},
        ],
    )
    @patch(
        "link_tui.backend.bluetooth.list_devices",
        new_callable=AsyncMock,
        return_value=[
            {"mac": "41:42:54:65:48:46", "name": "Sony WH-1000XM4", "paired": True, "connected": True, "battery": 80},
            {"mac": "AA:BB:CC:DD:EE:FF", "name": "MX Master 3S", "paired": True, "connected": False, "battery": 45},
        ],
    )
    async def test_lists_render(self, *_mocks):
        app = NetworkApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            wifi_list = app.query_one("#wifi-list", ListView)
            bt_list = app.query_one("#bt-list", ListView)
            self.assertEqual(len(wifi_list.children), 2)
            self.assertEqual(len(bt_list.children), 2)
            await pilot.press("q")
        self.assertTrue(app._exit)

    @patch("link_tui.backend.wifi.radio_status", new_callable=AsyncMock, return_value=True)
    @patch("link_tui.backend.bluetooth.powered", new_callable=AsyncMock, return_value=True)
    @patch("link_tui.backend.wifi.list_networks", new_callable=AsyncMock, return_value=[])
    @patch("link_tui.backend.bluetooth.list_devices", new_callable=AsyncMock, return_value=[])
    async def test_wifi_toggle_calls_backend(self, *_mocks):
        with patch("link_tui.backend.wifi.set_radio", new_callable=AsyncMock) as set_radio:
            app = NetworkApp()
            async with app.run_test() as pilot:
                await pilot.pause(0.3)
                await pilot.press("w")
                await pilot.pause(0.3)
            set_radio.assert_awaited()

    @patch("link_tui.backend.wifi.connect", new_callable=AsyncMock)
    @patch("link_tui.backend.wifi.radio_status", new_callable=AsyncMock, return_value=True)
    @patch("link_tui.backend.bluetooth.powered", new_callable=AsyncMock, return_value=True)
    @patch(
        "link_tui.backend.wifi.list_networks",
        new_callable=AsyncMock,
        return_value=[{"active": False, "ssid": "RedSegura", "signal": 70, "security": "WPA2"}],
    )
    @patch("link_tui.backend.bluetooth.list_devices", new_callable=AsyncMock, return_value=[])
    async def test_password_modal_flow(self, *_mocks):
        # The topmost decorator (wifi.connect) is the LAST argument (bottom-up order)
        wifi_connect = _mocks[-1]
        app = NetworkApp()
        async with app.run_test() as pilot:
            await pilot.pause(0.6)
            wifi_list = app.query_one("#wifi-list", ListView)
            wifi_list.focus()
            await pilot.press("enter")
            await pilot.pause(0.5)
            password_input = app.screen.query_one("#password-input", Input)
            self.assertIsNotNone(password_input)
            await pilot.press(*list("miclave"))
            await pilot.press("enter")
            await pilot.pause(0.6)
            wifi_connect.assert_awaited_once_with("RedSegura", "miclave")
            await pilot.press("q")


if __name__ == "__main__":
    unittest.main()
