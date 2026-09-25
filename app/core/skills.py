import re
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SkillRegistry:
    """Discovers, parses, and provides runtime access to SKILL.md playbooks for agents."""

    def __init__(self, skills_dir: str | None = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            # Default to skills directory relative to project root
            project_root = Path(__file__).resolve().parent.parent.parent
            self.skills_dir = project_root / "skills"

        self._skills: dict[str, dict[str, Any]] = {}
        self._tool_to_skill: dict[str, str] = {}
        self.reload_skills()

    def reload_skills(self) -> None:
        """Scan skills directory and load all valid SKILL.md files."""
        self._skills.clear()
        self._tool_to_skill.clear()

        if not self.skills_dir.exists():
            return

        for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
            try:
                content = skill_file.read_text(encoding="utf-8")
                parsed = self._parse_skill_file(content)
                if parsed:
                    skill_name = parsed["name"]
                    self._skills[skill_name] = parsed
            except Exception as e:
                logger.warning("skill_load_failed", file=str(skill_file), error=str(e))

        # Build tool to skill mapping prioritizing direct server namespace ownership
        for skill_name, data in self._skills.items():
            s_tokens = set(re.split(r"[-_]", skill_name.lower()))
            for tool in data.get("tools", []):
                clean_t = tool.removeprefix("mcp-")
                bare_t = clean_t.split("__", 1)[-1] if "__" in clean_t else clean_t
                server_prefix = clean_t.split("__", 1)[0].replace("_server", "") if "__" in clean_t else ""
                server_tokens = set(re.split(r"[-_]", server_prefix.lower())) if server_prefix else set()

                # Calculate token overlap score between skill name and server prefix
                overlap = len(s_tokens & server_tokens) if server_tokens else 0

                for t_key in (tool, f"mcp-{tool}", clean_t, bare_t, f"mcp-{bare_t}"):
                    if t_key not in self._tool_to_skill:
                        self._tool_to_skill[t_key] = (overlap, skill_name)
                    else:
                        prev_overlap, _ = self._tool_to_skill[t_key]
                        if overlap > prev_overlap:
                            self._tool_to_skill[t_key] = (overlap, skill_name)

    def get_skill(self, skill_name: str) -> dict[str, Any] | None:
        """Retrieve a specific skill by its name."""
        return self._skills.get(skill_name)

    def list_skills(self) -> list[dict[str, Any]]:
        """List metadata for all registered skills without their full markdown bodies."""
        return [
            {
                "name": data["name"],
                "description": data.get("description", ""),
                "tools": data.get("tools", []),
            }
            for data in self._skills.values()
        ]

    def _parse_skill_file(self, content: str) -> dict[str, Any] | None:
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

    def get_skill_for_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Retrieve the skill specification for a given MCP tool name."""
        clean_name = tool_name.removeprefix("mcp-")
        entry = self._tool_to_skill.get(tool_name) or self._tool_to_skill.get(clean_name)
        if not entry and "__" in clean_name:
            bare_tool = clean_name.split("__", 1)[-1]
            entry = self._tool_to_skill.get(bare_tool)

        skill_name = entry[1] if isinstance(entry, tuple) else entry

        if not skill_name:
            for s_name in self._skills:
                s_prefix = s_name.replace("-", "_")
                if clean_name.startswith(s_prefix) or s_prefix in clean_name:
                    skill_name = s_name
                    break

        if skill_name:
            return self._skills.get(skill_name)
        return None

    def get_skills_overview(self) -> str:
        """Return a lightweight progressive summary (names + descriptions) of available skills for the base system prompt."""
        if not self._skills:
            return ""
        lines = []
        for name, data in self._skills.items():
            desc = data.get("description", "No description available.")
            lines.append(f"- **`{name}`**: {desc}")
        return "\n".join(lines)

    def get_relevant_skills_instructions(
        self,
        prompt: str = "",
        document_ids: list[str] | None = None,
        tool_names: list[str] | None = None,
    ) -> str:
        """Progressively load and format full SKILL.md bodies ONLY for skills relevant to the active prompt/context."""
        if not self._skills:
            return ""

        prompt_lower = prompt.lower()
        matched_skills: dict[str, dict[str, Any]] = {}

        # 1. Match based on document_ids (triggers RAG knowledge base skill)
        if document_ids:
            for name, data in self._skills.items():
                if "rag" in name.lower() or "document" in name.lower() or "knowledge" in name.lower():
                    matched_skills[name] = data

        # 2. Match based on explicit tool names if provided
        if tool_names:
            for t in tool_names:
                skill_name = self._tool_to_skill.get(t)
                if skill_name and skill_name in self._skills:
                    matched_skills[skill_name] = self._skills[skill_name]

        # 3. Match based on prompt domain triggers
        for name, data in self._skills.items():
            if name in matched_skills:
                continue

            name_lower = name.lower()
            desc_lower = data.get("description", "").lower()
            tools = data.get("tools", [])

            is_relevant = False

            # Check presentation / storytelling triggers
            if "presentation" in name_lower or "storytelling" in name_lower or "presentation" in desc_lower:
                if any(w in prompt_lower for w in ("presentation", "slide", "deck", "pitch", "powerpoint", "pptx", "briefing", "qbr")):
                    is_relevant = True

            # Check RAG / document search triggers
            elif "rag" in name_lower or "knowledge" in name_lower:
                if any(w in prompt_lower for w in ("document", "docs", "rag", "pdf", "file", "knowledge base", "uploaded", "chunk", "attachment")):
                    is_relevant = True

            # Check procurement / spend analytics triggers
            elif "sgs" in name_lower or "spend" in name_lower or "procurement" in name_lower:
                if any(w in prompt_lower for w in ("procurement", "spend", "vendor", "supplier", "po", "purchase order", "invoice", "cost center", "gl account", "savings", "shadow it", "attribution")):
                    is_relevant = True

            # Check sales / product analytics triggers
            elif "sales" in name_lower or "product" in name_lower:
                if any(w in prompt_lower for w in ("sales", "product", "customer", "inventory", "retail", "store", "order", "omnichannel", "regional", "restock")):
                    is_relevant = True

            # Check weather / air quality triggers
            elif "weather" in name_lower or "air" in name_lower:
                if any(w in prompt_lower for w in ("weather", "temperature", "forecast", "air quality", "aqi", "pm2.5", "timezone", "rain", "humidity", "wind")):
                    is_relevant = True

            # Check tool triggers
            if not is_relevant:
                for t in tools:
                    bare = t.split("__")[-1].lower()
                    if bare in prompt_lower or t.lower() in prompt_lower:
                        is_relevant = True
                        break

            if is_relevant:
                matched_skills[name] = data

        if not matched_skills:
            return ""

        blocks = []
        for name, data in matched_skills.items():
            blocks.append(f"#### Active Skill Playbook: `{name}`\n{data['body']}")
        return "\n\n".join(blocks)

    def get_all_skills_instructions(self) -> str:
        """Combine all loaded skill bodies. Used for tests and full-compilation scenarios."""
        if not self._skills:
            return ""
        blocks = []
        for name, data in self._skills.items():
            blocks.append(f"### Skill: {name}\n{data['body']}")
        return "\n\n".join(blocks)


# Global singleton instance
skill_registry = SkillRegistry()
