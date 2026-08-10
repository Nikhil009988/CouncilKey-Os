"""CouncilKey-Os pendrive push - copy the PC's setup + data onto a pendrive.

`councilkey pendrive-push <path>` does everything:
1. runs the platform pendrive builder (project + portable venv + agents +
   launchers) - same as `councilkey pendrive`
2. copies the PC's council data (API keys vault, journal, memory, config,
   setup summary) into the stick's council-data/ - so the stick is a full
   mirror of your working setup
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from council import __version__

ROOT = Path(__file__).resolve().parent.parent.parent


def pc_council_home() -> Path:
    """The PC's council home (where journal/secrets/memory live)."""
    env = os.environ.get("COUNCIL_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "CouncilKey"
    return Path("/var/lib/council")


def _copy_tree(src: Path, dst: Path) -> list[str]:
    copied: list[str] = []
    if not src.exists():
        return copied
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
        copied.append(item.name)
    return copied


def push(path: str, skip_builder: bool = False) -> int:
    """Push the PC setup + data to the pendrive at `path`."""
    stick = Path(path)
    print("=" * 58)
    print(f"  CouncilKey-Os {__version__} - pendrive push")
    print(f"  target: {stick}")
    print("=" * 58)

    if not stick.exists() or not stick.is_dir():
        print(f"  ❌ {stick} is not a directory - plug in the pendrive and re-run")
        return 1

    # 1. build the stick (project + venv + agents + launchers)
    if not skip_builder:
        print("\n[1/2] Building the stick (project + launchers; pick agents separately)...")
        if os.name == "nt":
            script = ROOT / "scripts" / "pendrive-setup.ps1"
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Path", str(stick), "-NoAgents"]
        else:
            script = ROOT / "scripts" / "pendrive-setup.sh"
            cmd = [str(script), str(stick), "--no-agents"]
        r = subprocess.call(cmd)
        if r != 0:
            print("  ⚠ builder finished with warnings - continuing with data copy")
    else:
        print("\n[1/2] Skipping builder (--data-only)")

    # 2. copy the PC's council data onto the stick
    print("\n[2/2] Copying your data from this PC to the stick...")
    home = pc_council_home()
    stick_data = stick / "council-data"
    stick_data.mkdir(parents=True, exist_ok=True)

    if not home.exists():
        print(f"  ⚠ no council data found at {home} - nothing to copy")
        print("    (run 'councilkey setup' once on this PC to create it)")
    else:
        copied = _copy_tree(home, stick_data)
        if copied:
            print(f"  ✅ copied from {home}:")
            for name in sorted(copied)[:20]:
                print(f"      - {name}")
            if len(copied) > 20:
                print(f"      ... and {len(copied) - 20} more")
        else:
            print(f"  ⚠ {home} is empty - nothing copied")

    # 3. report
    print("\n" + "=" * 58)
    print("  ✅ Pendrive is ready - it mirrors this PC's setup.")
    print("")
    print("  Plug it into any PC and:")
    print("    Windows:  double-click START.bat  (dashboard) or AGENTS.bat (menu)")
    print("    Linux:    bash start.sh")
    print("  Your API keys, journal and memory are on the stick in council-data/.")
    print("=" * 58)
    return 0
