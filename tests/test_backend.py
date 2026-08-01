"""Tests for backend parsers and helpers (no hardware required)."""
import unittest

from link_tui.backend import bluetooth, wifi


class TestWifiParsers(unittest.TestCase):
    def test_parse_wifi_list(self):
        out = (
            "yes:TIGO-B768:54:WPA2\n"
            "no:Liahona:39:WPA2\n"
            "no:Red\\:Abierta:41:\n"
            "no::24:WPA2\n"
        )
        nets = wifi.parse_wifi_list(out)
        self.assertEqual(len(nets), 3)
        self.assertTrue(nets[0]["active"])
        self.assertEqual(nets[0]["ssid"], "TIGO-B768")
        self.assertEqual(nets[0]["signal"], 54)
        self.assertEqual(nets[0]["security"], "WPA2")
        self.assertEqual(nets[1]["ssid"], "Liahona")
        self.assertEqual(nets[2]["ssid"], "Red:Abierta")
        self.assertEqual(nets[2]["security"], "")

    def test_parse_wifi_list_empty(self):
        self.assertEqual(wifi.parse_wifi_list(""), [])


class TestBluetoothParsers(unittest.TestCase):
    def test_parse_devices(self):
        out = "Device 41:42:54:65:48:46 BassPods Boost Pro\nDevice AA:BB:CC:DD:EE:FF Teclado\n"
        devices = bluetooth.parse_devices(out)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["mac"], "41:42:54:65:48:46")
        self.assertEqual(devices[0]["name"], "BassPods Boost Pro")
        self.assertEqual(devices[1]["name"], "Teclado")

    def test_parse_battery(self):
        out = "\tBattery Percentage: 0x32 (50)\n"
        self.assertEqual(bluetooth.parse_battery(out), 50)
        self.assertIsNone(bluetooth.parse_battery("no battery"))


if __name__ == "__main__":
    unittest.main()
