import logging
import tomllib
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Distribution:
    """
    Loads distribution info (name, version, description) from pyproject.toml at instantiation.
    """

    _name: str
    _version: str
    _description: str

    def __init__(self, pyproject_path: Path | None = None) -> None:
        self._name = "ai-plt-agents"
        self._version = "0.1.0"
        self._description = "AI Platform Agents Service"
        self._load_from_pyproject(pyproject_path)

    def _load_from_pyproject(self, pyproject_path: Path | None) -> None:
        try:
            if pyproject_path is None:
                pyproject_path = PROJECT_ROOT / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    project = data.get("project", {})
                    self._name = project.get("name", self._name)
                    self._version = project.get("version", self._version)
                    self._description = project.get("description", self._description)
        except (
            OSError,
            tomllib.TOMLDecodeError,
            AttributeError,
            TypeError,
            ValueError,
        ) as e:
            log.warning("Failed to load distribution info from pyproject.toml: %s", e)

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        return self._description


APP_DISTRIBUTION = Distribution(PROJECT_ROOT / "pyproject.toml")
APP_VERSION = APP_DISTRIBUTION.version
