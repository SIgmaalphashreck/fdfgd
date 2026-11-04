"""SquallowTweaks - Hardware-Erkennung (CPU/GPU/RAM-Typ, Temperaturen). Qt-frei und testbar.

Grundsaetze: nichts erfinden. Was nicht zuverlaessig lesbar ist, bleibt None (die UI zeigt dann "Nicht verfuegbar").
Alle Abfragen laufen in einem Hintergrund-Thread (siehe service.Sampler), nie im UI-Thread.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from typing import Callable, Optional

Runner = Callable[[list[str], int], tuple[int, str]]

VENDORS = {"genuineintel": "Intel", "authenticamd": "AMD", "hygongenuine": "Hygon", "centaurhauls": "VIA"}
RAM_TYPES = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 34: "DDR5"}
VIRTUAL_GPU = re.compile(r"basic render|basic display|remote display|virtual|parsec|meta virtual|citrix|vmware|hyper-v|displaylink|idd", re.I)


def clean_cpu_name(raw: Optional[str]) -> Optional[str]:
    """Registry/WMI-Namen glaetten: (R)/(TM) weg, Leerraum normalisieren. Leer -> None."""
    if not raw or not isinstance(raw, str):
        return None
    s = re.sub(r"\((?:R|TM|r|tm)\)", "", raw)
    s = re.sub(r"\s+", " ", s).strip(" \t\r\n\x00")
    return s or None


def detect_vendor(raw_vendor: Optional[str], name: Optional[str]) -> Optional[str]:
    v = (raw_vendor or "").strip().lower()
    if v in VENDORS:
        return VENDORS[v]
    n = (name or "").lower()
    for key, label in (("intel", "Intel"), ("amd", "AMD"), ("ryzen", "AMD"), ("apple", "Apple"), ("qualcomm", "Qualcomm")):
        if key in n:
            return label
    return None


# --------------------------------------------------------------------------
# CPU
# --------------------------------------------------------------------------
def _registry_cpu() -> tuple[Optional[str], Optional[str]]:
    if os.name != "nt":
        return None, None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            name = winreg.QueryValueEx(k, "ProcessorNameString")[0]
            try:
                vendor = winreg.QueryValueEx(k, "VendorIdentifier")[0]
            except OSError:
                vendor = None
        return name, vendor
    except Exception:  # noqa: BLE001
        return None, None


def _proc_cpuinfo() -> tuple[Optional[str], Optional[str]]:
    try:
        name = vendor = None
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("model name") and not name:
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("vendor_id") and not vendor:
                    vendor = line.split(":", 1)[1].strip()
                if name and vendor:
                    break
        return name, vendor
    except Exception:  # noqa: BLE001
        return None, None


def read_cpu(registry: Optional[Callable] = None, cim: Optional[Callable[[], Optional[dict]]] = None) -> dict:
    """Exaktes CPU-Modell: 1. Registry, 2. CIM/WMI (Win32_Processor), 3. /proc/cpuinfo. Sonst name=None."""
    raw, vendor_id = (registry or _registry_cpu)()
    name = clean_cpu_name(raw)
    manufacturer = None
    if not name and cim:
        info = cim() or {}
        name = clean_cpu_name(info.get("Name"))
        manufacturer = info.get("Manufacturer")
    if not name and os.name != "nt":
        raw, vendor_id = _proc_cpuinfo()
        name = clean_cpu_name(raw)
    return {"name": name, "vendor": detect_vendor(vendor_id or manufacturer, name)}


# --------------------------------------------------------------------------
# PowerShell-/CIM-Abfragen
# --------------------------------------------------------------------------
def _ps(runner: Runner, script: str, timeout: int = 15) -> Optional[object]:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        return None
    code, out = runner([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], timeout)
    if code != 0 or not out:
        return None
    start = min([i for i in (out.find("{"), out.find("[")) if i >= 0], default=-1)
    if start < 0:
        return None
    try:
        return json.loads(out[start:])
    except ValueError:
        return None


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


STATIC_SCRIPT = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$r=@{};"
    "$r.cpu=@(Get-CimInstance Win32_Processor|Select-Object -First 1 Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed);"
    "$r.gpu=@(Get-CimInstance Win32_VideoController|Select-Object Name,DriverVersion,AdapterCompatibility);"
    "$r.ram=@(Get-CimInstance Win32_PhysicalMemory|Select-Object SMBIOSMemoryType,ConfiguredClockSpeed,Speed,Capacity);"
    "$r|ConvertTo-Json -Depth 4 -Compress"
)

TEMP_SCRIPT = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$r=@{};"
    "$r.lhm=@(Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor|Where-Object{$_.SensorType -eq 'Temperature'}|Select-Object Name,Value,Identifier);"
    "$r.ohm=@(Get-CimInstance -Namespace root/OpenHardwareMonitor -ClassName Sensor|Where-Object{$_.SensorType -eq 'Temperature'}|Select-Object Name,Value,Identifier);"
    "$r.acpi=@(Get-CimInstance -Namespace root/cimv2 -ClassName Win32_PerfFormattedData_Counters_ThermalZoneInformation|Select-Object Name,Temperature);"
    "$r|ConvertTo-Json -Depth 4 -Compress"
)

CPU_TEMP_PREFS = ("cpu package", "core (tctl/tdie)", "cpu (tctl/tdie)", "tdie", "tctl", "core max", "cpu total", "cpu")


def pick_gpu(adapters: list[dict]) -> Optional[dict]:
    """Beste echte GPU waehlen: NVIDIA > AMD Radeon RX/Pro > Intel Arc > sonstige. Virtuelle Adapter ignorieren."""
    real = [a for a in adapters if a.get("Name") and not VIRTUAL_GPU.search(str(a["Name"]))]

    def score(a: dict) -> int:
        n = str(a["Name"]).lower()
        if "nvidia" in n or "geforce" in n or "rtx" in n or "quadro" in n:
            return 4
        if re.search(r"radeon (rx|pro|vii)|radeon r[579]", n):
            return 3
        if "arc" in n:
            return 2
        return 1
    return max(real, key=score, default=None)


def ram_kind(modules: list[dict]) -> tuple[Optional[str], Optional[int]]:
    kinds = {RAM_TYPES.get(int(m.get("SMBIOSMemoryType") or 0)) for m in modules}
    kinds.discard(None)
    kind = next(iter(kinds)) if len(kinds) == 1 else None
    speeds = [int(m.get("ConfiguredClockSpeed") or m.get("Speed") or 0) for m in modules]
    speeds = [s for s in speeds if s > 0]
    return kind, (min(speeds) if speeds else None)


def read_static(runner: Runner) -> dict:
    """Einmalig beim Start: CPU-Modell, GPU-Modell, RAM-Typ. Fehlende Werte = None."""
    data = _ps(runner, STATIC_SCRIPT) or {}
    cpu_cim = (_as_list(data.get("cpu")) or [None])[0] if isinstance(data, dict) else None
    cpu = read_cpu(cim=lambda: cpu_cim)
    gpu = pick_gpu(_as_list(data.get("gpu")) if isinstance(data, dict) else [])
    kind, speed = ram_kind(_as_list(data.get("ram")) if isinstance(data, dict) else [])
    out = {"cpu_name": cpu["name"], "cpu_vendor": cpu["vendor"], "cpu_base_mhz": None,
           "gpu_name": clean_cpu_name(gpu.get("Name")) if gpu else None, "gpu_driver": (gpu or {}).get("DriverVersion") or None,
           "ram_kind": kind, "ram_mhz": speed}
    if isinstance(cpu_cim, dict) and cpu_cim.get("MaxClockSpeed"):
        out["cpu_base_mhz"] = int(cpu_cim["MaxClockSpeed"])
    return out


def pick_cpu_temp(sensors: list[dict]) -> Optional[float]:
    cpu_sensors = [s for s in sensors if "cpu" in str(s.get("Identifier", "")).lower() and s.get("Value") is not None]
    for pref in CPU_TEMP_PREFS:
        for s in cpu_sensors:
            if str(s.get("Name", "")).lower().startswith(pref):
                return _sane(s["Value"])
    return _sane(cpu_sensors[0]["Value"]) if cpu_sensors else None


def pick_gpu_temp(sensors: list[dict]) -> Optional[float]:
    gs = [s for s in sensors if "gpu" in str(s.get("Identifier", "")).lower() and s.get("Value") is not None]
    for s in gs:
        if "core" in str(s.get("Name", "")).lower():
            return _sane(s["Value"])
    return _sane(gs[0]["Value"]) if gs else None


def pick_acpi_temp(zones: list[dict]) -> Optional[float]:
    """Win32_PerfFormattedData ThermalZone: Temperature in Kelvin. Hoechste plausible Zone."""
    vals = []
    for z in zones:
        try:
            vals.append(float(z.get("Temperature")) - 273.15)
        except (TypeError, ValueError):
            continue
    vals = [v for v in vals if 10 <= v <= 115]
    return round(max(vals), 1) if vals else None


def _sane(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 1) if 5 <= f <= 125 else None


def read_temps(runner: Runner) -> dict:
    """Temperaturen. CPU: LibreHardwareMonitor/OpenHardwareMonitor (genau) sonst ACPI-Zone (ungefaehr). Sonst None."""
    data = _ps(runner, TEMP_SCRIPT, 20)
    res = {"cpu_temp": None, "cpu_temp_src": None, "gpu_temp_ext": None}
    if not isinstance(data, dict):
        return res
    ext = _as_list(data.get("lhm")) + _as_list(data.get("ohm"))
    t = pick_cpu_temp(ext)
    if t is not None:
        res.update(cpu_temp=t, cpu_temp_src="Sensor")
    else:
        t = pick_acpi_temp(_as_list(data.get("acpi")))
        if t is not None:
            res.update(cpu_temp=t, cpu_temp_src="ACPI")
    res["gpu_temp_ext"] = pick_gpu_temp(ext)
    return res


def fmt_temp(v: Optional[float]) -> str:
    return f"{v:.0f} °C" if v is not None else "Nicht verfügbar"
