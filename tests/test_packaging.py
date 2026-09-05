from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_checkpoint_runtime_dependency_is_in_wheel_package_closure() -> None:
    config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    setuptools_section = re.search(
        r"(?ms)^\[tool\.setuptools\]\s*(.*?)(?=^\[|\Z)",
        config,
    )
    assert setuptools_section is not None
    package_list = re.search(r"(?m)^packages\s*=\s*\[(.*?)\]", setuptools_section.group(1))
    assert package_list is not None
    packages = set(re.findall(r'"([^"]+)"', package_list.group(1)))

    assert {"ahaos", "scripts"}.issubset(packages)
    assert (ROOT / "scripts" / "__init__.py").is_file()
    assert (ROOT / "scripts" / "pilot.py").is_file()
