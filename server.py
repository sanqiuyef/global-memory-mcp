"""global-memory: ZCode 跨项目全局记忆 MCP server.

存储位置：~/.zcode/memories/global/（可用环境变量 GLOBAL_MEMORY_DIR 覆盖），
与 ZCode 原生 memories/projects/ 并列，文件格式与 ZCode auto-memory 一致：
frontmatter(name/description/metadata.type) + 短正文。索引文件 MEMORY.md 自动维护。
"""
import os
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

DEFAULT_DIR = Path.home() / ".zcode" / "memories" / "global"
MEMORY_DIR = Path(os.environ.get("GLOBAL_MEMORY_DIR") or DEFAULT_DIR)
INDEX_NAME = "MEMORY.md"
VALID_TYPES = ("env", "user", "feedback", "project", "reference")
TYPE_DESC = {
    "env": "机器/环境事实（硬件配置、软件版本、全局路径）",
    "user": "用户身份与偏好（角色、习惯、明确要求）",
    "feedback": "用户给过的工作方式指导（含原因与做法）",
    "project": "跨项目进行中的工作、目标、约束（日期用绝对日期）",
    "reference": "外部资源指针（URL、面板、单据）",
}

INSTRUCTIONS = (
    "全局记忆库：跨项目共享的机器级/用户级事实（硬件配置、软件版本、路径、已验证踩坑）。"
    "遇到环境、配置、路径、版本类问题时先用 memory_search / memory_list 查询，查到即用、不重查实测；"
    "会话中确认的新稳定事实（尤其是排查过的环境问题）收尾时用 memory_write 回写。"
)

mcp = FastMCP("global-memory", instructions=INSTRUCTIONS)


# ---------- 路径与格式 ----------

def _safe_name(name: str) -> str:
    """清理为文件名安全字符串；非法字符替换为连字符。"""
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", name.strip())
    cleaned = cleaned.strip(". ")
    if not cleaned or cleaned.lower() == "memory":
        raise ValueError(f"无效的记忆名: {name!r}")
    return cleaned


def _frontmatter(name: str, description: str, mtype: str) -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description.strip()}\n"
        "metadata:\n"
        f"  type: {mtype}\n"
        "---\n\n"
    )


def _parse_note(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    note = {"file": path.name, "name": path.stem, "description": "",
            "type": "project", "content": text}
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not m:
        return note
    fm, body = m.group(1), text[m.end():]
    note["content"] = body.lstrip("\n")
    in_meta = False
    for line in fm.splitlines():
        if re.match(r"^metadata:\s*$", line):
            in_meta = True
            continue
        km = re.match(r"^\s*(\w+):\s?(.*)$", line)
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        if key == "type" and in_meta:
            note["type"] = val
        elif key == "name" and not in_meta:
            note["name"] = val
        elif key == "description" and not in_meta:
            note["description"] = val
    return note


def _iter_notes() -> list[dict]:
    notes = []
    for path in sorted(MEMORY_DIR.glob("*.md")):
        if path.name == INDEX_NAME:
            continue
        try:
            notes.append(_parse_note(path))
        except OSError:
            continue
    return notes


# ---------- 索引维护 ----------

def _update_index(name: str, description: str, remove_only: bool = False) -> None:
    index_path = MEMORY_DIR / INDEX_NAME
    lines = []
    if index_path.exists():
        lines = index_path.read_text(encoding="utf-8").splitlines()
    marker = f"]({name}.md)"
    lines = [ln for ln in lines if marker not in ln]
    if not remove_only:
        lines.append(f"- [{name}]({name}.md) — {description.strip()}")
    index_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


# ---------- 检索打分 ----------

def _tokens(text: str) -> set[str]:
    """英文按词，中文按整串+相邻二字组，兼顾中英混合查询。"""
    text = text.lower()
    chunks = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text)
    tokens: set[str] = set()
    zh_all = []
    for chunk in chunks:
        if chunk[0].isascii():
            tokens.add(chunk)
        else:
            zh_all.append(chunk)
    zh = "".join(zh_all)
    if zh:
        tokens.add(zh)
        tokens.update(zh[i:i + 2] for i in range(len(zh) - 1))
    return tokens


def _score(note: dict, query_toks: set[str], full: str) -> int:
    name_toks = _tokens(note["name"])
    desc_toks = _tokens(note["description"])
    body_toks = _tokens(note["content"])
    score = sum(4 * (t in name_toks) + 3 * (t in desc_toks) + (t in body_toks)
                for t in query_toks)
    if full and (full in note["name"].lower()
                 or full in note["description"].lower()
                 or full in note["content"].lower()):
        score += 3
    return score


# ---------- 工具逻辑 ----------

def _write_memory(name: str, description: str, content: str,
                  mtype: str = "env") -> str:
    mtype = (mtype or "env").strip().lower()
    if mtype not in VALID_TYPES:
        return (f"错误: type 必须是 {' / '.join(VALID_TYPES)}；"
                f"{mtype!r} 无效。\n各类型含义: {TYPE_DESC}")
    if not description.strip():
        return "错误: description 必填（一行式摘要，用于检索与索引）。"
    if not content.strip():
        return "错误: content 必填（正文，直接给结论的短句）。"
    try:
        safe = _safe_name(name)
    except ValueError as e:
        return f"错误: {e}"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = MEMORY_DIR / f"{safe}.md"
    path.write_text(_frontmatter(safe, description, mtype)
                    + content.strip() + "\n", encoding="utf-8")
    _update_index(safe, description)
    return f"已保存: {path} (type={mtype})"


def _read_memory(name: str) -> str:
    safe = _safe_name(name)
    path = MEMORY_DIR / f"{safe}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    low = safe.lower()
    for note in _iter_notes():
        if note["name"].lower() == low or note["file"].lower() == f"{low}.md":
            return (MEMORY_DIR / note["file"]).read_text(encoding="utf-8")
    return f"未找到记忆: {name!r}。可用 memory_search 或 memory_list 查找。"


def _list_memories(mtype: str = "") -> str:
    notes = _iter_notes()
    if mtype:
        notes = [n for n in notes if n["type"] == mtype.lower()]
    if not notes:
        return "（暂无记忆" + (f"，type={mtype}" if mtype else "") + "）"
    lines = [f"[{n['type']}] {n['name']} — {n['description']}" for n in notes]
    return f"共 {len(notes)} 条:\n" + "\n".join(lines)


def _search_memories(query: str, mtype: str = "", limit: int = 8) -> str:
    notes = _iter_notes()
    if mtype:
        notes = [n for n in notes if n["type"] == mtype.lower()]
    q_toks, full = _tokens(query), query.strip().lower()
    ranked = sorted(((_score(n, q_toks, full), n) for n in notes),
                    key=lambda x: x[0], reverse=True)
    hits = [(s, n) for s, n in ranked if s > 0][:limit]
    if not hits:
        return f"无匹配: {query!r}。可试试 memory_list 浏览全部。"
    lines = [f"[{n['type']}] {n['name']} — {n['description']} (相关度 {s})"
             for s, n in hits]
    return f"命中 {len(hits)} 条:\n" + "\n".join(lines)


def _delete_memory(name: str) -> str:
    safe = _safe_name(name)
    path = MEMORY_DIR / f"{safe}.md"
    if not path.exists():
        low = safe.lower()
        for note in _iter_notes():
            if note["name"].lower() == low:
                path = MEMORY_DIR / note["file"]
                break
        else:
            return f"未找到记忆: {name!r}"
    path.unlink()
    _update_index(path.stem, "", remove_only=True)
    return f"已删除: {path}"


# ---------- MCP 工具 ----------

@mcp.tool()
def memory_write(name: str, description: str, content: str,
                 type: str = "env") -> str:
    """写入或更新一条全局记忆（跨项目共享）。

    name: 短文件名标识（kebab-case 或中文）；description: 一行摘要；
    content: 正文短句，直接给结论；type: env(机器环境) / user(用户偏好) /
    feedback(工作方式指导) / project(跨项目进行中事项) / reference(外部资源)。
    同名记忆会被覆盖。
    """
    return _write_memory(name, description, content, mtype=type)


@mcp.tool()
def memory_read(name: str) -> str:
    """按名称读取一条全局记忆的完整内容。"""
    return _read_memory(name)


@mcp.tool()
def memory_search(query: str, type: str = "", limit: int = 8) -> str:
    """按关键词检索全局记忆（支持中英文与混合查询）。"""
    return _search_memories(query, mtype=type, limit=limit)


@mcp.tool()
def memory_list(type: str = "") -> str:
    """列出全局记忆索引（可按 type 过滤: env/user/feedback/project/reference）。"""
    return _list_memories(type)


@mcp.tool()
def memory_delete(name: str) -> str:
    """删除一条全局记忆（按名称，含索引行）。"""
    return _delete_memory(name)


if __name__ == "__main__":
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    mcp.run(transport="stdio")
