#!/usr/bin/env python3

"""Ensure all Home Assistant version declarations stay in sync."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
REQUIREMENTS_HA_PATH = ROOT_DIR / "requirements-ha.txt"
HACS_JSON_PATH = ROOT_DIR / "hacs.json"
LOCAL_HA_VERSION_PATH = ROOT_DIR / "config" / ".HA_VERSION"
HACS_HOMEASSISTANT_KEY = "homeassistant"
HOMEASSISTANT_REQUIREMENT_PATTERN = re.compile(r"^homeassistant==(?P<version>\S+)$", re.MULTILINE)


#
# parse_args
#
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rewrite derived version files to match requirements-ha.txt.",
    )
    return parser.parse_args()


#
# read_required_homeassistant_version
#
def read_required_homeassistant_version() -> str:
    """Read the canonical Home Assistant version from requirements-ha.txt."""

    matches = HOMEASSISTANT_REQUIREMENT_PATTERN.findall(REQUIREMENTS_HA_PATH.read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one 'homeassistant==...' entry in {REQUIREMENTS_HA_PATH}, found {len(matches)}.")

    return matches[0]


#
# read_hacs_homeassistant_version
#
def read_hacs_homeassistant_version() -> str:
    """Read the HACS minimum Home Assistant version."""

    hacs_data = json.loads(HACS_JSON_PATH.read_text(encoding="utf-8"))
    version = hacs_data.get(HACS_HOMEASSISTANT_KEY)
    if not isinstance(version, str) or not version:
        raise ValueError(f"Expected a non-empty '{HACS_HOMEASSISTANT_KEY}' string in {HACS_JSON_PATH}.")

    return version


#
# read_local_homeassistant_version
#
def read_local_homeassistant_version() -> str:
    """Read the local dev Home Assistant version used by the config directory."""

    if not LOCAL_HA_VERSION_PATH.is_file():
        raise ValueError(f"Expected tracked Home Assistant version file at {LOCAL_HA_VERSION_PATH.relative_to(ROOT_DIR)}.")

    version = LOCAL_HA_VERSION_PATH.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError(f"Expected a non-empty version in {LOCAL_HA_VERSION_PATH}.")

    return version


#
# write_hacs_homeassistant_version
#
def write_hacs_homeassistant_version(version: str) -> None:
    """Rewrite hacs.json to use the canonical Home Assistant version."""

    hacs_data = json.loads(HACS_JSON_PATH.read_text(encoding="utf-8"))
    hacs_data[HACS_HOMEASSISTANT_KEY] = version
    HACS_JSON_PATH.write_text(f"{json.dumps(hacs_data, indent=4)}\n", encoding="utf-8")


#
# write_local_homeassistant_version
#
def write_local_homeassistant_version(version: str) -> None:
    """Rewrite the local Home Assistant version marker."""

    LOCAL_HA_VERSION_PATH.write_text(f"{version}\n", encoding="utf-8")


#
# check_versions
#
def check_versions(fix_versions: bool) -> int:
    """Validate or synchronize all tracked Home Assistant version declarations."""

    required_version = read_required_homeassistant_version()
    hacs_version = read_hacs_homeassistant_version()
    local_version = read_local_homeassistant_version()

    mismatches: list[str] = []
    if hacs_version != required_version:
        mismatches.append(f"{HACS_JSON_PATH.relative_to(ROOT_DIR)} has {hacs_version}, expected {required_version}.")
    if local_version != required_version:
        mismatches.append(f"{LOCAL_HA_VERSION_PATH.relative_to(ROOT_DIR)} has {local_version}, expected {required_version}.")

    if not mismatches:
        print(f"Home Assistant versions are in sync at {required_version}.")
        return 0

    if fix_versions:
        write_hacs_homeassistant_version(required_version)
        write_local_homeassistant_version(required_version)
        print(f"Synchronized Home Assistant versions to {required_version}.")
        return 0

    print("Home Assistant version mismatch detected:", file=sys.stderr)
    for mismatch in mismatches:
        print(f"- {mismatch}", file=sys.stderr)
    print("Run 'python3 scripts/check_ha_version_sync.py --fix' to synchronize them.", file=sys.stderr)
    return 1


#
# main
#
def main() -> int:
    """Run the version consistency check."""

    args = parse_args()
    return check_versions(fix_versions=args.fix)


if __name__ == "__main__":
    raise SystemExit(main())
