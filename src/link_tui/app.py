"""Main TUI application: Wi-Fi and Bluetooth network manager."""
from __future__ import annotations

import asyncio
from typing import Any

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static, Switch

from .backend import bluetooth, wifi
from .screens.password_modal import PasswordModal


# ---------------------------------------------------------------------------
# Transparency patch (workaround for Textual 8.2.x)
#
# Textual 8.2.8 has a bug: `Color.rich_color` drops the alpha channel
# (`r, g, b, a, ansi, _ = self` but never uses `a`). So `background:
# transparent` (rgba(0,0,0,0)) becomes OPAQUE BLACK (#000000) on every
# rendered cell and the terminal transparency disappears.
#
# The 3 patches below make the transparent color travel as a "default"
# color (the terminal background) and keep Textual's color filters from
# turning it back to black. They are applied when this module is imported
# and only activate for Textual 8.2.x: if the bug is fixed or the
# internals change in another version, they are skipped without breaking
# app startup.
#
# Note: only full transparency (a == 0) is fixed; semi-transparent colors
# still ignore alpha (original behavior).
# ---------------------------------------------------------------------------
import rich.color as _rich_color_mod
import textual as _textual_mod
import textual.color as _textual_color_mod
import textual.filter as _textual_filter

from functools import lru_cache

from rich.color import ColorTriplet as _ColorTriplet
from rich.color import ColorType as _RichColorType
from rich.color import Color as _RichColor
from rich.style import Style as _RichStyle


def _rich_color_with_transparency(self) -> _RichColor:
    """rich_color that respects alpha: transparent -> 'default' color."""
    r, g, b, a, ansi, _ = self
    if ansi is not None:
        return _RichColor.parse("default") if ansi < 0 else _RichColor.from_ansi(ansi)
    if a == 0:
        return _RichColor.parse("default")
    return _RichColor(
        f"#{r:02x}{g:02x}{b:02x}", _RichColorType.TRUECOLOR, None, _ColorTriplet(r, g, b)
    )


def _truecolor_style_with_transparency(
    self, style: _RichStyle, background: _RichColor
) -> _RichStyle:
    """truecolor_style that does NOT convert 'default' colors to dark."""
    terminal_theme = self._terminal_theme
    changed = False
    color = style.color
    bgcolor = style.bgcolor
    if color is not None and not color.is_default:
        if color.triplet is None:
            color = _RichColor.from_triplet(
                color.get_truecolor(terminal_theme, foreground=True)
            )
            changed = True
    if bgcolor is not None and not bgcolor.is_default:
        if bgcolor.triplet is None:
            bgcolor = _RichColor.from_triplet(
                bgcolor.get_truecolor(terminal_theme, foreground=False)
            )
            changed = True
    if style.dim and color is not None:
        color = _textual_filter.dim_color(
            background if bgcolor is None else bgcolor, color
        )
        style += _textual_filter.NO_DIM
        changed = True
    return style + _RichStyle.from_color(color, bgcolor) if changed else style


@lru_cache(1024)
def _safe_dim_color(
    background: _RichColor, color: _RichColor, factor: float = _textual_filter.DIM_FACTOR
) -> _RichColor:
    """dim_color that does not crash if a color has no triplet (default)."""
    if color.triplet is None or background.triplet is None:
        return color
    red1, green1, blue1 = background.triplet
    red2, green2, blue2 = color.triplet
    return _RichColor.from_rgb(
        red1 + (red2 - red1) * factor,
        green1 + (green2 - green1) * factor,
        blue1 + (blue2 - blue1) * factor,
    )


try:
    if _textual_mod.__version__.startswith("8.2"):
        _textual_color_mod.Color.rich_color = property(_rich_color_with_transparency)
        _textual_filter.ANSIToTruecolor.truecolor_style = _truecolor_style_with_transparency
        _textual_filter.dim_color = _safe_dim_color
except Exception:
    # Never block app startup: if Textual changes its internals, the patch
    # is skipped and the app still starts (just without transparency).
    pass


class NetworkApp(App):
    """TUI manager for Wi-Fi and Bluetooth networks."""

    TITLE = "Network Manager"
    SUB_TITLE = "Wi-Fi & Bluetooth"

    CSS = """
    /* The App root paints $background (#121212) by default: make it
       transparent so the terminal's transparency shows through the whole
       tree (including the footer's rich_style). */
    App {
        background: transparent;
    }
    Screen {
        background: transparent;
    }
    #columns {
        height: 1fr;
    }
    .column {
        width: 1fr;
        height: 1fr;
        border: round white;
        margin: 0 1;
        padding: 0 1;
        background: transparent;
    }
    .column-title {
        height: 3;
        content-align: center middle;
        text-style: bold;
        color: white;
        background: transparent;
    }
    ListView {
        height: 1fr;
        border: none;
        padding: 0;
        background: transparent;
        /* Scrollbars transparent too */
        scrollbar-background: transparent;
        scrollbar-background-hover: transparent;
        scrollbar-background-active: transparent;
        scrollbar-color: $foreground 25%;
        scrollbar-color-hover: $foreground 25%;
        scrollbar-color-active: $foreground 25%;
    }
    ListView > ListItem,
    ListView > ListItem.-hovered {
        background: transparent;
    }
    /* Selection without a solid block: only highlighted text (full transparency) */
    ListView > ListItem.-highlight {
        color: white;
        text-style: bold underline;
    }
    ListView:focus > ListItem.-highlight {
        color: white;
        text-style: bold underline;
    }
    ListView:focus {
        background-tint: transparent;
    }
    #wifi-list, #bt-list {
        height: 1fr;
    }
    .net-item {
        height: 1;
        padding: 0 1;
    }
    #status-bar {
        height: 1;
        background: transparent;
        color: white;
        padding: 0 2;
    }
    .switch-row {
        height: 3;
        align: center middle;
    }
    .switch-label {
        width: 1fr;
        content-align: right middle;
        text-style: bold;
        color: white;
    }
    /* Header and Footer: transparent, white keys, gray descriptions */
    Header {
        background: transparent;
        color: white;
    }
    Footer {
        background: transparent;
        color: white;
    }
    FooterKey {
        background: transparent;
    }
    FooterKey:hover {
        background: transparent;
    }
    FooterKey .footer-key--key {
        color: white;
        background: transparent;
    }
    FooterKey .footer-key--description {
        color: gray;
        background: transparent;
    }
    FooterLabel {
        color: gray;
        background: transparent;
    }
    /* White on/off switch (instead of default green), transparent background */
    Switch {
        background: transparent;
        border: tall white;
    }
    Switch:focus {
        border: tall white;
        background-tint: transparent;
    }
    Switch .switch--slider {
        color: white;
        background: transparent;
    }
    Switch:hover .switch--slider,
    Switch.-on .switch--slider,
    Switch.-on:hover .switch--slider {
        color: white;
        background: transparent;
    }
    """

    BINDINGS = [
        Binding("w", "toggle_wifi", "Wi-Fi"),
        Binding("b", "toggle_bt", "Bluetooth"),
        Binding("r", "rescan", "Rescan"),
        Binding("tab", "switch_column", "Column"),
        Binding("d", "disconnect", "Disconnect"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._wifi_nets: list[dict[str, Any]] = []
        self._bt_devices: list[dict[str, Any]] = []
        self._refreshing = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="columns"):
            with Vertical(id="wifi-col", classes="column"):
                with Horizontal(classes="switch-row"):
                    yield Label("Wi-Fi", classes="switch-label")
                    yield Switch(id="wifi-switch")
                yield ListView(id="wifi-list")
            with Vertical(id="bt-col", classes="column"):
                with Horizontal(classes="switch-row"):
                    yield Label("Bluetooth", classes="switch-label")
                    yield Switch(id="bt-switch")
                yield ListView(id="bt-list")
        yield Static("[dim][[r]] Rescan · [[Enter]] Connect · [[d]] Disconnect · [[q]] Quit[/]", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self.set_interval(30, self.refresh_all)
        self.run_worker(self._initial_load())

    async def _initial_load(self) -> None:
        try:
            await self._sync_switches()
            await self.refresh_all()
        except Exception as exc:
            self._set_status(f"Initial error: {exc}")

    async def _sync_switches(self) -> None:
        """Update switches from the real system state without firing events."""
        with self.prevent(Switch.Changed):
            try:
                self.query_one("#wifi-switch", Switch).value = await wifi.radio_status()
            except Exception:
                pass
            try:
                self.query_one("#bt-switch", Switch).value = await bluetooth.powered()
            except Exception:
                pass

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "wifi-switch":
            self.run_worker(self._toggle_wifi(event.value))
        elif event.switch.id == "bt-switch":
            self.run_worker(self._toggle_bt(event.value))

    async def _toggle_wifi(self, on: bool) -> None:
        try:
            await wifi.set_radio(on)
            self._set_status(f"Wi-Fi {'on' if on else 'off'}")
        except Exception as exc:
            self._set_status(f"Wi-Fi error: {exc}")
            await self._sync_switches()
        await self.refresh_all()

    async def _toggle_bt(self, on: bool) -> None:
        try:
            await bluetooth.set_power(on)
            self._set_status(f"Bluetooth {'on' if on else 'off'}")
        except Exception as exc:
            self._set_status(f"Bluetooth error: {exc}")
            await self._sync_switches()
        await self.refresh_all()

    def action_toggle_wifi(self) -> None:
        switch = self.query_one("#wifi-switch", Switch)
        switch.toggle()

    def action_toggle_bt(self) -> None:
        switch = self.query_one("#bt-switch", Switch)
        switch.toggle()

    def action_rescan(self) -> None:
        self.run_worker(self._do_rescan())

    async def _do_rescan(self) -> None:
        self._set_status("Scanning…")
        try:
            await wifi.rescan()
        except Exception:
            pass
        try:
            # Discovery scan in parallel with list refresh
            await bluetooth.scan()
        except Exception:
            pass
        await self.refresh_all()
        self._set_status("Scan complete")

    def action_switch_column(self) -> None:
        wifi_list = self.query_one("#wifi-list", ListView)
        bt_list = self.query_one("#bt-list", ListView)
        if self.focused is wifi_list or self.focused is None:
            bt_list.focus()
        else:
            wifi_list.focus()

    def action_disconnect(self) -> None:
        focused = self.focused
        if focused is self.query_one("#wifi-list", ListView):
            self.run_worker(self._disconnect_wifi_selected())
        elif focused is self.query_one("#bt-list", ListView):
            self.run_worker(self._disconnect_bt_selected())

    async def refresh_all(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            await asyncio.gather(self._refresh_wifi(), self._refresh_bt())
        finally:
            self._refreshing = False

    async def _refresh_wifi(self) -> None:
        try:
            self._wifi_nets = await wifi.list_networks()
        except Exception as exc:
            self._set_status(f"Error scanning Wi-Fi: {exc}")
            return
        list_view = self.query_one("#wifi-list", ListView)
        index = list_view.index
        await list_view.clear()
        for net in self._wifi_nets:
            await list_view.append(self._wifi_item(net))
        if self._wifi_nets:
            list_view.index = 0 if index is None or index >= len(self._wifi_nets) else index

    def _wifi_item(self, net: dict[str, Any]) -> ListItem:
        if net["active"]:
            state = "●"
            state_style = "bold green"
        else:
            state = "○"
            state_style = "dim"
        lock = "🔒" if net["security"] else "🔓"
        bars = "▁▂▃▄▅▆▇█"[max(0, min(7, net["signal"] // 12))]
        label = (
            f"[{state_style}]{state}[/] [b]{escape(net['ssid'])}[/] "
            f"[dim]{bars} {net['signal']}% {lock} {escape(net['security']) or 'open'}[/]"
        )
        return ListItem(Label(label, classes="net-item"))

    async def _refresh_bt(self) -> None:
        try:
            self._bt_devices = await bluetooth.list_devices()
        except Exception as exc:
            self._set_status(f"Error scanning Bluetooth: {exc}")
            return
        list_view = self.query_one("#bt-list", ListView)
        index = list_view.index
        await list_view.clear()
        for dev in self._bt_devices:
            await list_view.append(self._bt_item(dev))
        if self._bt_devices:
            list_view.index = 0 if index is None or index >= len(self._bt_devices) else index

    def _bt_item(self, dev: dict[str, Any]) -> ListItem:
        if dev["connected"]:
            state = "●"
            state_style = "bold green"
        else:
            state = "○"
            state_style = "dim"
        battery = f" 🔋{dev['battery']}%" if dev.get("battery") is not None else ""
        tag = "connected" if dev["connected"] else ("paired" if dev["paired"] else "discovered")
        label = (
            f"[{state_style}]{state}[/] [b]{escape(dev['name'])}[/] "
            f"[dim]{dev['mac']} · {tag}{battery}[/]"
        )
        return ListItem(Label(label, classes="net-item"))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "wifi-list":
            self.run_worker(self._connect_wifi_selected(event.list_view.index))
        elif event.list_view.id == "bt-list":
            self.run_worker(self._connect_bt_selected(event.list_view.index))

    async def _connect_wifi_selected(self, index: int | None) -> None:
        if index is None or index >= len(self._wifi_nets):
            return
        net = self._wifi_nets[index]
        if net["active"]:
            self._set_status(f"Already connected to {net['ssid']}")
            return
        password = None
        if net["security"]:
            password = await self.push_screen_wait(PasswordModal(net["ssid"]))
            if password is None:
                return
        self._set_status(f"Connecting to {net['ssid']}…")
        try:
            await wifi.connect(net["ssid"], password)
            self._set_status(f"Connected to {net['ssid']}")
        except Exception as exc:
            self._set_status(f"Error connecting to {net['ssid']}: {exc}")
        await self.refresh_all()

    async def _connect_bt_selected(self, index: int | None) -> None:
        if index is None or index >= len(self._bt_devices):
            return
        dev = self._bt_devices[index]
        if dev["connected"]:
            self._set_status(f"Already connected to {dev['name']}")
            return
        self._set_status(f"Connecting to {dev['name']}…")
        try:
            if not dev["paired"]:
                await bluetooth.pair(dev["mac"])
            await bluetooth.connect(dev["mac"])
            self._set_status(f"Connected to {dev['name']}")
        except Exception as exc:
            self._set_status(f"Error connecting to {dev['name']}: {exc}")
        await self.refresh_all()

    async def _disconnect_wifi_selected(self) -> None:
        try:
            await wifi.disconnect_active()
            self._set_status("Wi-Fi disconnected")
        except Exception as exc:
            self._set_status(f"Error: {exc}")
        await self.refresh_all()

    async def _disconnect_bt_selected(self) -> None:
        focused = self.query_one("#bt-list", ListView)
        index = focused.index
        if index is None or index >= len(self._bt_devices):
            return
        dev = self._bt_devices[index]
        try:
            await bluetooth.disconnect(dev["mac"])
            self._set_status(f"Disconnected from {dev['name']}")
        except Exception as exc:
            self._set_status(f"Error: {exc}")
        await self.refresh_all()

    def _set_status(self, message: str) -> None:
        # The Static widget interprets markup: escape the message so SSIDs,
        # names or errors with brackets don't break the rendering.
        self.query_one("#status-bar", Static).update(escape(message))


def main() -> None:
    NetworkApp().run()
