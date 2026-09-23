"""
Simple Coding Agent - Claude API + 3 tools (read_file, write_file, run_command)
With sandbox: all file ops confined to a workspace folder, commands blacklisted.
"""

import os
import re
import subprocess
import json
from pathlib import Path
from anthropic import Anthropic

# ── Memory management config ────────────────────────────────────
MAX_HISTORY_TOKENS = 40_000   # rough budget for conversation history
OVERFLOW_RATIO = 0.6          # what fraction of budget to try to keep after pruning
MIN_KEEP_TURNS = 8            # never drop below this many recent turns

# ── Sandbox config ──────────────────────────────────────────────
SANDBOX_DIR = Path(os.environ.get("AGENT_WORKSPACE", "./agent_workspace")).resolve()
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

# Commands that are never allowed (case-insensitive check)
BLOCKED_COMMANDS = [
    "rm -rf /", "rm -rf ~", "rmdir /s", "del /s", "del /q",
    "format ", "mkfs", ":(){ :", "dd if=", "shutdown", "reboot",
    "sudo ", "su ", "chmod 777", "curl|sh", "curl|bash", "wget|sh",
    "powershell -enc", "cmd /c format", "reg delete",
]

client = Anthropic()

TOOLS = [
    {
        "name": "read_file",
        "description": f"Read file contents. Path must be relative to workspace ({SANDBOX_DIR}).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": f"Write content to a file. Path must be relative to workspace ({SANDBOX_DIR}).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path from workspace root"},
                "content": {"type": "string", "description": "Content to write to the file"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_command",
        "description": "Execute a shell command inside the sandbox. Dangerous commands (rm -rf, sudo, etc.) are blocked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "list_files",
        "description": f"List files and folders inside the sandbox ({SANDBOX_DIR}), optionally filtered by a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Optional glob pattern, e.g. '**/*.py'. Defaults to all files."}
            }
        }
    },
    {
        "name": "search_code",
        "description": "Search file contents inside the sandbox for a keyword or regex, returning matching file:line matches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Keyword or regex to search for"},
                "include": {"type": "string", "description": "Optional filename filter, e.g. '*.py'"}
            },
            "required": ["pattern"]
        }
    }
]

SYSTEM_PROMPT = f"""You are a coding assistant. You can read, write, and execute files to help users with programming tasks.

IMPORTANT RULES:
- All files must be inside the workspace: {SANDBOX_DIR}
- When writing paths, use relative paths (e.g. "game.py", "src/main.py")
- Explore the project with list_files / search_code before making changes
- After writing code, run it to verify it works
- If there are errors, fix them and try again
- When the task is complete, give a clear summary

Always explain what you're doing and why."""


# ── Memory management ───────────────────────────────────────────
def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (+0.1 for non-ASCII)."""
    return int(len(text) / 3.5) + 1


def summarize_messages(messages):
    """Compress old tool_use/tool_result pairs into a single summary message."""
    # Group: find contiguous assistant(tool_use) → user(tool_result) pairs and merge older ones
    compact = []
    pairs = []
    i = 0
    while i < len(messages):
        m = messages[i]
        # look for tool_use assistant block followed by tool_result user block
        if (m["role"] == "assistant"
                and any(b.get("type") == "tool_use" for b in m["content"])
                and i + 1 < len(messages)
                and messages[i + 1]["role"] == "user"):
            pairs.append((m, messages[i + 1]))
            i += 2
        else:
            compact.append(m)
            i += 1

    # Keep at most N most recent pairs expanded; summarize the rest
    keep = MIN_KEEP_TURNS // 2
    if len(pairs) > keep:
        keep_pairs, summarize = pairs[-keep:], pairs[:-keep]
        # Build a compact textual summary of old pairs
        summary_lines = []
        for am, um in summarize:
            for blk in am["content"]:
                if blk.get("type") == "tool_use":
                    summary_lines.append(f"- used {blk['name']} with {json.dumps(blk.get('input'))}")
            # keep response results too but trimmed
        summary_msg = {
            "role": "user",
            "content": f"[Earlier tool activity summarized]\n" + "\n".join(summary_lines)
        }
        compact.append(summary_msg)
        for am, um in keep_pairs:
            compact.append(am)
            compact.append(um)
        return compact
    return messages


def trim_history(messages):
    """Truncate oldest turns if history exceeds the token budget."""
    budget = MAX_HISTORY_TOKENS
    # estimate tokens on everything except the most recent MIN_KEEP_TURNS turns
    keep_turns = messages[-MIN_KEEP_TURNS:] if len(messages) >= MIN_KEEP_TURNS else messages
    keep_tokens = sum(estimate_tokens(json.dumps(m["content"], ensure_ascii=False)) for m in keep_turns)
    if keep_tokens <= budget and len(messages) <= MIN_KEEP_TURNS:
        return messages  # nothing to trim

    # walk from oldest to newest, dropping until under budget
    result = list(messages)
    while len(result) > MIN_KEEP_TURNS:
        total = sum(estimate_tokens(json.dumps(m["content"], ensure_ascii=False)) for m in result)
        if total <= budget:
            break
        result.pop(0)  # drop the oldest turn
    return result


def manage_memory(messages):
    """Apply summarization + trimming to keep history within budget."""
    if len(messages) <= MIN_KEEP_TURNS:
        return messages
    messages = summarize_messages(messages)
    return trim_history(messages)


def _sandbox_path(rel_path: str) -> Path:
    """Resolve a user-supplied path to inside the sandbox. Raises ValueError if escapes."""
    candidate = (SANDBOX_DIR / rel_path).resolve()
    if not (candidate == SANDBOX_DIR or str(candidate).startswith(str(SANDBOX_DIR) + os.sep)):
        raise ValueError(f"Path escapes sandbox: {rel_path} -> {candidate}")
    return candidate


def _is_command_blocked(cmd: str) -> str | None:
    """Return the blocking reason if command is dangerous, else None."""
    lower = cmd.lower().strip()
    for blocked in BLOCKED_COMMANDS:
        if blocked.lower() in lower:
            return f"Blocked: command matches forbidden pattern '{blocked}'"
    return None


def execute_tool(name, input_data):
    """Execute a tool locally and return the result."""
    try:
        if name == "read_file":
            target = _sandbox_path(input_data["path"])
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            return {"output": content}

        elif name == "write_file":
            target = _sandbox_path(input_data["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(input_data["content"])
            return {"output": f"File written to {target.relative_to(SANDBOX_DIR)}"}

        elif name == "run_command":
            cmd = input_data["command"]
            reason = _is_command_blocked(cmd)
            if reason:
                return {"output": reason}

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(SANDBOX_DIR)  # always run inside sandbox
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return {"output": output or "(no output)"}

        elif name == "list_files":
            pattern = input_data.get("pattern", "**/*")
            matches = [p.relative_to(SANDBOX_DIR).as_posix()
                       for p in SANDBOX_DIR.glob(pattern)
                       if p.is_file()]
            if not matches:
                return {"output": "(no files matched)"}
            return {"output": "\n".join(sorted(matches))}

        elif name == "search_code":
            pattern = input_data["pattern"]
            include = input_data.get("include", "*")
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return {"output": f"Invalid regex: {e}"}
            results = []
            for p in SANDBOX_DIR.rglob("*"):
                if not p.is_file():
                    continue
                if not include.endswith("*") and not p.name.endswith(include.lstrip("*")):
                    continue
                try:
                    for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                        if regex.search(line):
                            results.append(f"{p.relative_to(SANDBOX_DIR).as_posix()}:{i}: {line.strip()}")
                except Exception:
                    continue
            if not results:
                return {"output": "(no matches found)"}
            return {"output": "\n".join(results)}

    except Exception as e:
        return {"output": f"Error: {str(e)}"}


def run_agent(user_task, logger=print):
    """Run the agent loop, streaming progress to `logger` and returning the final answer."""
    messages = [{"role": "user", "content": user_task}]

    while True:
        logger("\n--- Claude is thinking... ---\n")

        # Apply memory management before sending
        messages = manage_memory(messages)
        n_msgs = sum(len(m["content"]) if isinstance(m["content"], list) else 1 for m in messages)
        logger(f"  (history: {len(messages)} turns, {n_msgs} blocks)")

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        # Add Claude's response to history
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Check if Claude wants to use a tool
        tool_uses = [block for block in assistant_content if block.type == "tool_use"]

        if response.stop_reason == "tool_use" and tool_uses:
            # Execute each tool call and collect results
            tool_results = []
            for tool_block in tool_uses:
                logger(f"  Using tool: {tool_block.name}({json.dumps(tool_block.input, ensure_ascii=False)})")
                result = execute_tool(tool_block.name, tool_block.input)
                logger(f"  Result: {result['output'][:200]}{'...' if len(result['output']) > 200 else ''}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result["output"]
                })

            # Send tool results back to Claude
            messages.append({"role": "user", "content": tool_results})
        else:
            # Claude is done — print final response and collect it
            final_text = ""
            for block in assistant_content:
                if hasattr(block, "text"):
                    logger(block.text)
                    final_text += block.text + "\n"
            return final_text.strip()


if __name__ == "__main__":
    task = input("Enter your task: ")
    run_agent(task)
