import tomllib
from pathlib import Path

import pytest

from kr_patch import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_matches_pyproject():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert __version__ == project["version"]


# the install line is what game projects copy, so it must name the current release tag
@pytest.mark.parametrize("readme", ["README.md", "README.ko.md"])
def test_readme_install_line_names_current_tag(readme):
    text = (ROOT / readme).read_text(encoding="utf-8")
    assert f"kr-patch-toolkit@v{__version__}" in text
