"""Modal to capture the WPA/WPA2 password of a Wi-Fi network."""
from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class PasswordModal(ModalScreen[str | None]):
    """Ask for the password of a protected network and return the key when closed."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Cancel"),
    ]

    CSS = """
    ModalScreen {
        background: transparent;
    }
    #password-dialog {
        width: 62;
        height: auto;
        border: thick white;
        background: transparent;
        padding: 1 2;
        align: center middle;
    }
    #password-title {
        text-align: center;
        text-style: bold;
        color: white;
        margin-bottom: 1;
    }
    #password-input {
        margin-bottom: 1;
        background: transparent;
        border: tall white;
    }
    #password-input:focus {
        border: tall white;
    }
    #password-actions {
        height: 3;
        align-horizontal: center;
    }
    #password-actions Button {
        margin: 0 1;
        background: transparent;
        color: white;
        border: tall white;
    }
    #password-actions Button:hover,
    #password-actions Button:focus {
        background: $foreground 10%;
    }
    """

    def __init__(self, ssid: str) -> None:
        super().__init__()
        self.ssid = ssid

    def action_cancel(self) -> None:
        self.dismiss(None)

    def compose(self) -> ComposeResult:
        with Vertical(id="password-dialog"):
            yield Label(f"Password for [bold]{escape(self.ssid)}[/]", id="password-title")
            yield Input(password=True, placeholder="WPA/WPA2 password", id="password-input")
            with Horizontal(id="password-actions"):
                yield Button("Connect", variant="primary", id="password-ok")
                yield Button("Cancel", variant="error", id="password-cancel")

    def on_mount(self) -> None:
        self.query_one("#password-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "password-ok":
            self._submit()
        elif event.button.id == "password-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        value = self.query_one("#password-input", Input).value
        if value:
            self.dismiss(value)
        else:
            self.notify("Password cannot be empty", severity="warning")
