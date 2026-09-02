import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Discovers, parses, and provides runtime access to SKILL.md playbooks for agents."""

    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            # Default to skills directory relative to project root
            project_root = Path(__file__).resolve().parent.parent.parent
            self.skills_dir = project_root / "skills"

        self._skills: Dict[str, Dict[str, Any]] = {}
        self._tool_to_skill: Dict[str, str] = {}
        self.reload_skills()

    def reload_skills(self) -> None:
        """Scan skills directory and load all valid SKILL.md files."""
        self._skills.clear()
        self._tool_to_skill.clear()

        if not self.skills_dir.exists():
            return

        for skill_file in self.skills_dir.glob("*/SKILL.md"):
            try:
                content = skill_file.read_text(encoding="utf-8")
                parsed = self._parse_skill_file(content)
                if parsed:
                    skill_name = parsed["name"]
                    self._skills[skill_name] = parsed
                    for tool in parsed.get("tools", []):
                        self._tool_to_skill[tool] = skill_name
            except Exception as e:
                logger.warning("Failed to load skill from %s: %s", skill_file, e)

    def _parse_skill_file(self, content: str) -> Optional[dict[str, Any]]:
        """Parse frontmatter and markdown body of a SKILL.md file."""
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not frontmatter_match:
            return None

        fm_text = frontmatter_match.group(1)
        body = frontmatter_match.group(2).strip()

        # Parse simple YAML-like key/values without heavy external parser
        name = ""
        description = ""
        tools = []

        in_tools = False
        for line in fm_text.splitlines():
            line_str = line.strip()
            if line_str.startswith("name:"):
                name = line_str.replace("name:", "").strip()
                in_tools = False
            elif line_str.startswith("description:"):
                description = line_str.replace("description:", "").strip()
                in_tools = False
            elif line_str.startswith("tools:"):
                in_tools = True
            elif in_tools and line_str.startswith("-"):
                tool_name = line_str.lstrip("-").strip()
                if tool_name:
                    tools.append(tool_name)
            elif not line_str.startswith("-"):
                in_tools = False

        if not name:
            return None

        return {
            "name": name,
            "description": description,
            "tools": tools,
            "body": body,
        }

    def get_skill_for_tool(self, tool_name: str) -> Optional[dict[str, Any]]:
        """Retrieve the skill specification for a given MCP tool name."""
        skill_name = self._tool_to_skill.get(tool_name)
        if skill_name:
            return self._skills.get(skill_name)
        return None

    def get_all_skills_instructions(self) -> str:
        """Combine all loaded skill bodies for high-level orchestrator system prompts."""
        if not self._skills:
            return ""
        blocks = []
        for name, data in self._skills.items():
            blocks.append(f"### Skill: {name}\n{data['body']}")
        return "\n\n".join(blocks)


# Global singleton instance
skill_registry = SkillRegistry()
