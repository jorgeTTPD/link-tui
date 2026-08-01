"""Bluetooth backend via BlueZ (bluetoothctl), non-blocking."""
from __future__ import annotations

import asyncio
import re
from typing import Any


async def _run(cmd: list[str], timeout: float = 20.0) -> str:
    """Run a bluetoothctl command and return its output; raises RuntimeError on failure."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
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


def parse_devices(output: str) -> list[dict[str, Any]]:
    """Convert `Device <MAC> <Name>` lines into dictionaries."""
    devices: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) >= 3 and parts[0] == "Device":
            devices.append({"mac": parts[1], "name": parts[2]})
    return devices


def parse_battery(output: str) -> int | None:
    """Extract the battery percentage from `bluetoothctl info` if present."""
    m = re.search(r"Battery Percentage:.*?\((\d+)\)", output)
    return int(m.group(1)) if m else None


async def powered() -> bool:
    """Return True if the Bluetooth adapter is powered on."""
    out = await _run(["bluetoothctl", "show"])
    for line in out.splitlines():
        if line.strip().startswith("Powered:"):
            return "yes" in line
    return False


async def set_power(on: bool) -> None:
    """Power the Bluetooth adapter on/off."""
    await _run(["bluetoothctl", "power", "on" if on else "off"])


async def scan(duration: float = 5.0) -> None:
    """Run a discovery scan for `duration` seconds.

    `bluetoothctl scan on` is interactive and never exits, so it is
    launched as a subprocess and stopped once the time has elapsed.
    """
    proc = await asyncio.create_subprocess_exec(
        "bluetoothctl", "scan", "on",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.sleep(duration)
    finally:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


async def list_devices() -> list[dict[str, Any]]:
    """Return known devices with paired/connected state and battery."""
    out = await _run(["bluetoothctl", "devices"])
    devices = parse_devices(out)
    if not devices:
        return devices
    paired = {d["mac"] for d in parse_devices(await _run(["bluetoothctl", "devices", "Paired"]))}
    connected = {d["mac"] for d in parse_devices(await _run(["bluetoothctl", "devices", "Connected"]))}
    async def _fetch_info(dev: dict[str, Any]) -> dict[str, Any]:
        dev["paired"] = dev["mac"] in paired
        dev["connected"] = dev["mac"] in connected
        try:
            info = await _run(["bluetoothctl", "info", dev["mac"]], timeout=8.0)
        except RuntimeError:
            info = ""
        dev["battery"] = parse_battery(info)
        return dev

    return await asyncio.gather(*(_fetch_info(dev) for dev in devices))


async def pair(mac: str) -> None:
    """Pair a device; raises an error if bluetoothctl reports a failure."""
    out = await _run(["bluetoothctl", "pair", mac], timeout=30.0)
    _check_failure(out, f"Could not pair {mac}")


async def connect(mac: str) -> None:
    """Connect an already paired device; raises an error on failure."""
    out = await _run(["bluetoothctl", "connect", mac], timeout=30.0)
    _check_failure(out, f"Could not connect {mac}")


async def disconnect(mac: str) -> None:
    """Disconnect a device; raises an error on failure."""
    out = await _run(["bluetoothctl", "disconnect", mac], timeout=20.0)
    _check_failure(out, f"Could not disconnect {mac}")


def _check_failure(output: str, message: str) -> None:
    """bluetoothctl often returns exit code 0 even on failure; detect the failure in the output."""
    if any(word in output for word in ("Failed", "failed", "Error", "not available", "Not Found")):
        raise RuntimeError(f"{message}: {output.strip() or 'no details'}")
