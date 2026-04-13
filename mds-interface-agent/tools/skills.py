"""Skill search and loading tools — reads investigation procedures from markdown files."""

from pathlib import Path
from langchain_core.tools import tool

SKILLS_PATH = Path(__file__).parent.parent / "skills"
MAX_SKILL_CHARS = 20_000


@tool
def search_skills(query: str) -> str:
    """Search investigation skills by keyword. Skills are step-by-step investigation procedures.

    Args:
        query: Search query (e.g. 'interface flap', 'health check', 'slow drain')
    """
    results = []
    query_lower = query.lower()

    for md_file in sorted(SKILLS_PATH.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        score = 0
        for word in query_lower.split():
            if word in md_file.stem.lower():
                score += 3
            if word in content.lower():
                score += 1
        if score > 0:
            title = md_file.stem
            for line in content.split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                    break
            description = ""
            for line in content.split("\n"):
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"')
                    break
            results.append({"title": title, "file": md_file.name,
                            "description": description, "score": score})

    results.sort(key=lambda r: r["score"], reverse=True)

    if not results:
        available = [f.name for f in SKILLS_PATH.glob("*.md")]
        return f"No skills found matching '{query}'. Available: {available}"

    lines = [f"Found {len(results)} matching skill(s):\n"]
    for r in results:
        lines.append(f"**{r['title']}** (`{r['file']}`, relevance={r['score']})")
        if r["description"]:
            lines.append(f"  {r['description'][:200]}\n")
    lines.append("\nUse `load_skill` with the filename to load the full investigation procedure.")
    return "\n".join(lines)


@tool
def load_skill(skill_name: str) -> str:
    """Load the full content of an investigation skill. Follow the steps in order.

    Args:
        skill_name: Skill filename (e.g. 'mds-interface-issues.md')
    """
    if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
        return "Error: Invalid skill name."

    target = SKILLS_PATH / skill_name
    if not target.exists():
        target = SKILLS_PATH / f"{skill_name}.md"
    if not target.exists():
        available = [f.name for f in SKILLS_PATH.glob("*.md")]
        return f"Skill '{skill_name}' not found. Available: {available}"

    content = target.read_text(encoding="utf-8")
    if len(content) > MAX_SKILL_CHARS:
        content = content[:MAX_SKILL_CHARS] + f"\n\n... [truncated at {MAX_SKILL_CHARS} chars]"
    return content
