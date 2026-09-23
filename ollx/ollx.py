#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from datetime import datetime

import requests

DEFAULT_MODEL = os.environ.get("OLLX_MODEL", "llama3.2:3b")
DEFAULT_HOST = os.environ.get("OLLX_HOST", "http://127.0.0.1:11434")
LANG_SYSTEM = "Respond in the same language that the user writes in."


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _gen(prompt, model=DEFAULT_MODEL, temp=0.3, jformat=None,
         system=LANG_SYSTEM, max_tokens=None):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temp},
    }
    if jformat:
        payload["format"] = jformat
    if system is not None:
        payload["system"] = system
    if max_tokens:
        payload["options"]["num_predict"] = max_tokens
    payload["think"] = False
    r = requests.post(f"{DEFAULT_HOST}/api/generate", json=payload, timeout=600)
    r.raise_for_status()
    return r.json()["response"]


def _chat(messages, model=DEFAULT_MODEL, temp=0.3, tools=None):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temp},
    }
    if tools:
        payload["tools"] = tools
    payload["think"] = False
    r = requests.post(f"{DEFAULT_HOST}/api/chat", json=payload, timeout=600)
    r.raise_for_status()
    return r.json()


def read_text(text, file=None, prompt_hint=None):
    if file:
        with open(file, "r", encoding="utf-8") as f:
            return f.read().strip()
    if text:
        return text.strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    if prompt_hint:
        return input(prompt_hint).strip()
    return ""


def _json_result(raw):
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False)
    except Exception:
        return raw


def _run_batch(text, prompt_builder, model, temp=0.1):
    lines = [l for l in text.splitlines() if l.strip()]
    for line in lines:
        sys.stdout.buffer.write(
            (_json_result(_gen(prompt_builder(line), model=model, temp=temp,
                               jformat="json")) + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def cmd_classify(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    labels = ", ".join(a.labels)
    if a.batch:
        _run_batch(
            text,
            lambda l: f"Classify into exactly one of these labels: {labels}.\n"
                      f'Return STRICT JSON {{"label": "<label>", "reason": "<brief>"}}.\n'
                      f"Text: {l}",
            a.model,
        )
        return
    prompt = (f"Classify the text into exactly one of these labels: {labels}.\n"
              f'Return STRICT JSON {{"label": "<label>", "reason": "<brief>"}}.\n'
              f"Text: {text}")
    print(_json_result(_gen(prompt, model=a.model, temp=0.1, jformat="json")))


def cmd_sentiment(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    if a.batch:
        _run_batch(
            text,
            lambda l: f'Analyze sentiment. Return STRICT JSON {{"sentiment": "positive|neutral|negative", '
                      f'"confidence": <0-1>, "reason": "<brief>"}}.\nText: {l}',
            a.model,
        )
        return
    prompt = (f'Analyze sentiment. Return STRICT JSON {{"sentiment": "positive|neutral|negative", '
              f'"confidence": <0-1>, "reason": "<brief>"}}.\nText: {text}')
    print(_json_result(_gen(prompt, model=a.model, temp=0.1, jformat="json")))


def cmd_tags(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    def b(l):
        return f'Extract 3-8 concise tags from the text. Return STRICT JSON {{"tags": ["tag", ...]}}.\nText: {l}'
    if a.batch:
        _run_batch(text, b, a.model)
        return
    print(_json_result(_gen(b(text), model=a.model, temp=0.1, jformat="json")))


def cmd_extract(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    prompt = (f'Extract keywords and named entities from the text.\n'
              f'Return STRICT JSON {{"keywords": ["..."], '
              f'"entities": [{{"type": "person|org|place|date|product|other", "name": "..."}}]}}.\n'
              f"Text: {text}")
    print(_json_result(_gen(prompt, model=a.model, temp=0.1, jformat="json")))


def cmd_summarize(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    prompt = (f"Summarize the text in about {a.words} words or fewer. "
              f"Keep the key points and facts.\nText:\n{text}")
    print(_gen(prompt, model=a.model, temp=0.2))


def cmd_rewrite(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    prompt = (f"Rewrite the text below with {a.tone} style. "
              f"Keep the meaning, improve clarity. Output only the rewritten text.\n"
              f"Text:\n{text}")
    print(_gen(prompt, model=a.model, temp=0.6))


def cmd_translate(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    prompt = (f"Translate the text into {a.to}. "
              f"Output only the translation, no explanation.\nText:\n{text}")
    print(_gen(prompt, model=a.model, temp=0.1).strip())


def cmd_code(a):
    text = read_text(a.text, a.file, "Describe what the code should do (or paste partial code)> ")
    if not text:
        sys.exit("error: no input")
    lang = a.language or "python"
    prompt = (f"Write {lang} code for the following request. "
              f"Output only the code in a code block.\nRequest:\n{text}")
    print(_gen(prompt, model=a.model, temp=0.1))


def cmd_convert(a):
    text = read_text(a.text, a.file, "Paste code to convert> ")
    if not text:
        sys.exit("error: no input")
    prompt = (f"Convert the following code from {a.frm} to {a.to}. "
              f"Output only the converted code in a code block.\n"
              f"Source ({a.frm}):\n{text}")
    print(_gen(prompt, model=a.model, temp=0.1))


def cmd_json(a):
    text = read_text(a.text, a.file, "Describe the data or paste content> ")
    if not text:
        sys.exit("error: no input")
    prompt = (f"Produce a JSON object from the content below, following this schema:\n"
              f"{a.schema}\n"
              f"Return STRICT JSON only, no explanation.\nContent:\n{text}")
    print(_json_result(_gen(prompt, model=a.model, temp=0.1, jformat="json",
                            max_tokens=a.max_tokens)))


def cmd_clean(a):
    text = read_text(a.text, a.file)
    if not text:
        sys.exit("error: no input")
    prompt = (f"Normalize and clean the following JSON data: trim whitespace, "
              f"fix obvious typos in keys, coerce numbers/booleans, drop empty values, "
              f"keep the same structure. Return STRICT JSON only.\n{a.schema}\n"
              f"Data:\n{text}")
    print(_json_result(_gen(prompt, model=a.model, temp=0.1, jformat="json")))


def cmd_run(a):
    text = read_text(a.text, a.file, "Prompt> ")
    if not text:
        sys.exit("error: no input")
    print(_gen(text, model=a.model, temp=a.temp))


def cmd_chat(a):
    print(f"Chat with {a.model} (type exit to leave)")
    messages = [{"role": "system", "content": LANG_SYSTEM}]
    while True:
        try:
            user = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in ("exit", "quit"):
            break
        messages.append({"role": "user", "content": user})
        resp = _chat(messages, model=a.model, temp=a.temp)
        reply = resp["message"].get("content", "")
        messages.append({"role": "assistant", "content": reply})
        print(f"AI> {reply}")


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current local date and time",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Perform arithmetic calculations. Expression may contain numbers and + - * / ( ) . ,",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string",
                                   "description": "Arithmetic expression, e.g. (1+2)*3"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path, default current directory"},
                },
                "required": [],
            },
        },
    },
]


def _call_tool(name, args):
    if name == "get_current_time":
        return {"now": datetime.now().isoformat()}
    if name == "calculator":
        expr = args.get("expression", "")
        if not re.fullmatch(r"[0-9+\-*/().,eE\s]+", expr):
            return {"error": "invalid expression"}
        try:
            return {"result": eval(expr)}
        except Exception as e:
            return {"error": str(e)}
    if name == "list_files":
        path = args.get("path") or "."
        try:
            return {"files": os.listdir(path)}
        except Exception as e:
            return {"error": str(e)}
    return {"error": f"unknown tool {name}"}


def _agent_loop(messages, model, temp):
    while True:
        resp = _chat(messages, model=model, temp=temp, tools=TOOLS)
        msg = resp["message"]
        if not msg.get("tool_calls"):
            return msg.get("content", "")
        messages.append(msg)
        for tc in msg["tool_calls"]:
            name = tc["function"]["name"]
            fargs = tc["function"].get("arguments", {})
            if isinstance(fargs, str):
                try:
                    fargs = json.loads(fargs)
                except Exception:
                    fargs = {}
            result = _call_tool(name, fargs)
            messages.append({"role": "tool", "tool_name": name,
                             "content": json.dumps(result, ensure_ascii=False)})


def cmd_agent(a):
    print(f"Agent with {a.model}, tools: "
          + ", ".join(t["function"]["name"] for t in TOOLS))
    print("Type exit to leave.")
    messages = [{"role": "system",
                 "content": LANG_SYSTEM
                 + " Use tools when they help. Reply concisely after using a tool."}]
    while True:
        try:
            user = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in ("exit", "quit"):
            break
        messages.append({"role": "user", "content": user})
        reply = _agent_loop(messages, a.model, a.temp)
        messages.append({"role": "assistant", "content": reply})
        print(f"AI> {reply}")


def build_parser():
    p = argparse.ArgumentParser(
        prog="ollx",
        description="Local AI toolbox backed by Ollama.")
    p.add_argument("-m", "--model", default=DEFAULT_MODEL,
                   help=f"Ollama model (default: {DEFAULT_MODEL})")
    p.add_argument("-t", "--temp", type=float, default=0.3,
                   help="temperature (default: 0.3)")
    p.add_argument("-f", "--file", help="read input text from a UTF-8 file")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="classify text into given labels")
    c.add_argument("--labels", nargs="+", required=True,
                   help="candidate labels")
    c.add_argument("text", nargs="?", help="text (or piped via stdin)")
    c.add_argument("--batch", action="store_true",
                   help="treat each line of stdin as one item, output JSON lines")
    c.set_defaults(fn=cmd_classify)

    c = sub.add_parser("sentiment", help="sentiment analysis")
    c.add_argument("text", nargs="?", help="text (or piped via stdin)")
    c.add_argument("--batch", action="store_true")
    c.set_defaults(fn=cmd_sentiment)

    c = sub.add_parser("tags", help="extract tags/keywords")
    c.add_argument("text", nargs="?", help="text (or piped via stdin)")
    c.add_argument("--batch", action="store_true")
    c.set_defaults(fn=cmd_tags)

    c = sub.add_parser("extract", help="extract keywords and named entities")
    c.add_argument("text", nargs="?", help="text (or piped via stdin)")
    c.set_defaults(fn=cmd_extract)

    c = sub.add_parser("summarize", help="summarize text")
    c.add_argument("--words", type=int, default=100, help="target length")
    c.add_argument("text", nargs="?", help="text (or piped via stdin)")
    c.set_defaults(fn=cmd_summarize)

    c = sub.add_parser("rewrite", help="rewrite text")
    c.add_argument("--tone", default="clear and natural",
                   help="target tone/style")
    c.add_argument("text", nargs="?", help="text (or piped via stdin)")
    c.set_defaults(fn=cmd_rewrite)

    c = sub.add_parser("translate", help="translate text")
    c.add_argument("--to", default="繁體中文", help="target language")
    c.add_argument("text", nargs="?", help="text (or piped via stdin)")
    c.set_defaults(fn=cmd_translate)

    c = sub.add_parser("code", help="code generation/completion")
    c.add_argument("-l", "--language", default="python")
    c.add_argument("text", nargs="?", help="description or partial code")
    c.set_defaults(fn=cmd_code)

    c = sub.add_parser("convert", help="convert code between languages")
    c.add_argument("--from", dest="frm", default="python")
    c.add_argument("--to", default="javascript")
    c.add_argument("text", nargs="?", help="source code")
    c.set_defaults(fn=cmd_convert)

    c = sub.add_parser("json", help="force structured JSON output from content")
    c.add_argument("--schema", default="",
                   help="describe the target JSON schema")
    c.add_argument("--max-tokens", type=int, default=2000)
    c.add_argument("text", nargs="?", help="content (or piped via stdin)")
    c.set_defaults(fn=cmd_json)

    c = sub.add_parser("clean", help="clean/normalize JSON data")
    c.add_argument("--schema", default="", help="optional hints")
    c.add_argument("text", nargs="?", help="JSON data (or piped via stdin)")
    c.set_defaults(fn=cmd_clean)

    c = sub.add_parser("run", help="one-off prompt")
    c.add_argument("text", nargs="?", help="prompt")
    c.set_defaults(fn=cmd_run)

    c = sub.add_parser("chat", help="interactive chat")
    c.set_defaults(fn=cmd_chat)

    c = sub.add_parser("agent", help="interactive agent with tool calling")
    c.set_defaults(fn=cmd_agent)

    return p


def main():
    _utf8()
    args = build_parser().parse_args()
    try:
        args.fn(args)
    except requests.exceptions.ConnectionError:
        sys.exit("error: cannot reach Ollama. Start it with: ollama serve")


if __name__ == "__main__":
    main()