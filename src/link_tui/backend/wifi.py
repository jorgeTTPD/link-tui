"""Wi-Fi backend via NetworkManager (nmcli), non-blocking.

All functions are asynchronous and use `asyncio.create_subprocess_exec`
so the UI never freezes while querying the system.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

_NMC_ENV = {**os.environ, "LC_ALL": "C"}


async def _run(cmd: list[str], timeout: float = 15.0) -> str:
    """Run an nmcli command and return its output; raises RuntimeError on failure."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_NMC_ENV,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"Timeout running: {' '.join(cmd)}")
    output = out.decode(errors="replace").strip()
    stderr_text = err.decode(errors="replace").strip()
    if proc.returncode != 0:
        raise RuntimeError(stderr_text or output or f"Failed: {' '.join(cmd)}")
    return output


def _unescape(field: str) -> str:
    """Unescape characters from nmcli terse output (\\: and \\\\)"""
    return field.replace("\\:", "\x00").replace("\\\\", "\\").replace("\x00", ":")


def _split_terse(line: str) -> list[str]:
    """Split an nmcli terse line respecting escapes (e.g. SSID with colons)."""
    fields: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            current.append(line[i : i + 2])
            i += 2
        elif ch == ":":
            fields.append("".join(current))
            current = []
            i += 1
        else:
            current.append(ch)
            i += 1
    fields.append("".join(current))
    return [_unescape(f) for f in fields]


def parse_wifi_list(output: str) -> list[dict[str, Any]]:
    """Convert the output of `nmcli -t -f active,ssid,signal,security dev wifi list`."""
    networks: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = _split_terse(line)
        if len(parts) < 4:
            continue
        active, ssid, signal, security = parts[0], parts[1], parts[2], parts[3]
        if not ssid:
            continue
        networks.append(
            {
                "active": active == "yes",
                "ssid": ssid,
                "signal": int(signal) if signal.isdigit() else 0,
                "security": security,
            }
        )
    return networks


async def radio_status() -> bool:
    """Return True if the Wi-Fi radio is enabled."""
    out = await _run(["nmcli", "-t", "-f", "WIFI", "radio"])
    return out.strip().lower() == "enabled"


async def set_radio(on: bool) -> None:
    """Turn the Wi-Fi radio on/off."""
    await _run(["nmcli", "radio", "wifi", "on" if on else "off"])


async def rescan() -> None:
    """Ask NetworkManager to rescan; failures are not critical."""
    try:
        await _run(["nmcli", "dev", "wifi", "rescan"], timeout=10.0)
    except RuntimeError:
        pass


async def list_networks() -> list[dict[str, Any]]:
    """Return the available Wi-Fi networks (active ones first)."""
    out = await _run(
        ["nmcli", "-t", "-f", "active,ssid,signal,security", "dev", "wifi", "list"]
    )
    networks = parse_wifi_list(out)
    networks.sort(key=lambda n: (not n["active"], -n["signal"]))
    return networks


async def connect(ssid: str, password: str | None = None) -> None:
    """Connect to a Wi-Fi network, with a password if required."""
    cmd = ["nmcli", "--wait", "20", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    await _run(cmd, timeout=25.0)


async def disconnect_active() -> None:
    """Disconnect the active Wi-Fi connection (filtered by type 802-11-wireless)."""
    out = await _run(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE,STATE", "connection", "show"])
    active = None
    for line in out.splitlines():
        parts = _split_terse(line)
        if (
            len(parts) >= 4
            and parts[1] == "802-11-wireless"
            and parts[3] == "activated"
            and parts[2]
        ):
            active = parts[0]
            break
    if active is None:
        raise RuntimeError("No active Wi-Fi connection to disconnect")
    await _run(["nmcli", "connection", "down", active])
