"""Backend abstraction for the model-testing harness.

Two backends implement the same `extract(prompt) -> dict | None` contract:
  - RuleBackend   : deterministic keyword splitter embodying the workflow's
                    8-Block conventions (the baseline / ground truth for agreement)
  - NeedleBackend : cactus-compute/needle 2.0.8 (45M, on-device, 0 LLM tokens)

New models (local Qwen, MoE API, ...) plug in by implementing the protocol.
"""

from __future__ import annotations

import ctypes
import os
import re
import sys
from typing import Optional

from .schema import BLOCK_ORDER, SCHEMA


# ---------------------------------------------------------------------------
# Windows private working-set probe (process RSS in MB)
# ---------------------------------------------------------------------------

def _rss_mb() -> Optional[float]:
    if sys.platform != "win32":
        return None
    try:
        psapi = ctypes.windll.psapi
        kern = ctypes.windll.kernel32
        PROCESS_MEMORY_COUNTERS = (
            ctypes.c_ulong * 4
            + (ctypes.c_size_t * 9)  # noqa: E226
        )
        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        handle = kern.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / (1024.0 * 1024.0)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Rule baseline
# ---------------------------------------------------------------------------

def _norm(tag: str) -> str:
    """Lowercase, strip emphasis parens and weight suffixes, collapse spaces."""
    t = tag.lower().strip()
    t = re.sub(r"\(+|\)+", "", t)               # emphasis (( )) and ( ) parens
    t = re.sub(r":\d+(\.\d+)?\)?$", "", t)      # (tag:1.2) weight suffix
    t = re.sub(r"\s+", " ", t).strip()
    return t


_KEYWORDS = {
    "quality": {
        "masterpiece", "best quality", "highres", "absurdres",
        "year 2026", "year_2026", "newest", "official art",
    },
    "identity": {
        "1girl", "2girls", "3girls", "multiple girls", "solo",
        "equestria girls", "mlp", "fluttershy", "rarity", "twilight sparkle",
        "rainbow dash", "applejack", "pinkie pie", "apple bloom",
        "sweetie belle", "sunset shimmer", "starlight glimmer", "coco pommel",
        "human", "anthro",
    },
    "style": {
        "innocent", "vaporwave", "synthwave", "art deco", "glitch", "grid",
        "dark fantasy", "cyberpunk", "retro", "minimalist", "chibi",
    },
    "composition": {
        "close-up", "wide shot", "from behind", "pov", "knee up",
        "cowboy shot", "profile", "perspective", "full body", "upper body",
        "face focus", "looking at viewer",
    },
    "attire": {
        "see-through legwear", "mary janes", "choker", "hair ribbon",
        "dress", "skirt", "thighhighs", "socks", "school uniform",
        "torn clothes", "jacket", "blazer", "crop top", "miniskirt",
    },
    "body": {
        "long hair", "short hair", "pale skin", "slender", "long legs",
        "midriff", "navel", "collarbone", "aqua eyes", "green eyes",
        "blue eyes", "pink hair", "blonde hair", "black hair", "twintails",
        "ponytail", "cream skin", "fair skin",
    },
    "action": {
        "contrapposto", "kneeling", "crossed legs", "hand on chin",
        "spread toes", "soles", "foot focus", "feet on table",
        "one side up", "standing on one foot", "arms behind back",
    },
    "expression": {
        "shy", "neutral", "teasing", "seductive smile", "closed eyes",
        "looking away", "embarrassed", "smirk", "wink",
    },
    "scene": {
        "arcade", "jukebox", "neon", "reflection", "puddle", "static",
        "street", "classroom", "beach", "bedroom", "night", "rain",
        "neon lights", "city", "window", "mirror", "stage",
    },
}

_BLOCK_PRIORITY = ["quality", "identity", "style", "composition", "attire",
                   "body", "action", "expression", "scene"]


class RuleBackend:
    name = "rule-baseline"

    def __init__(self):
        self._kw = {block: {_norm(k) for k in keys}
                    for block, keys in _KEYWORDS.items()}
        self.last_confidence = None

    def extract(self, prompt: str) -> Optional[dict]:
        fields = {block: [] for block in BLOCK_ORDER}
        for chunk in prompt.split(","):
            tag = _norm(chunk)
            if not tag:
                continue
            for block in _BLOCK_PRIORITY:
                if tag in self._kw[block]:
                    fields[block].append(tag)
                    break
            # unmatched chunks are silently dropped (rule baseline limits)
        return fields

    def close(self):
        pass


# ---------------------------------------------------------------------------
# cactus-needle backend
# ---------------------------------------------------------------------------

class NeedleBackend:
    name = "needle-2.0.8"

    def __init__(self, max_new_tokens: int = 384):
        try:
            import needle
        except ImportError:
            # `python path/to/bench.py` does not put the shell cwd on
            # sys.path — retry with cwd added (needle checkout dir).
            sys.path.insert(0, os.getcwd())
            try:
                import needle
            except ImportError as err:
                raise RuntimeError(
                    "needle package not importable. Run the bench from the "
                    "needle checkout dir or install cactus-needle.") from err
        self._needle = needle
        self._max_new_tokens = max_new_tokens
        # One agent bound to the 8-Block schema; the engine compiles the
        # byte-level grammar once and re-inits per complete() call.
        self._agent = needle.Needle(tools=[SCHEMA])
        self._rss_before = _rss_mb()
        self.last_confidence = None

    def extract(self, prompt: str) -> Optional[dict]:
        # Engine quirk (tested 2026-08-21): consecutive complete() calls on the
        # same agent can abort the process (exit 1, no traceback) once a prior
        # call returned a non-call response. reset() rewinds the conversation
        # (tools/schema stay loaded) and makes repeated calls stable.
        self._agent.reset()
        resp = self._agent.complete(prompt, self._max_new_tokens)
        self.last_confidence = resp.get("confidence")
        calls = resp.get("function_calls") or []
        if not calls:
            return None
        return calls[0].get("arguments") or {}

    def rss_mb(self) -> Optional[float]:
        now = _rss_mb()
        if now is None or self._rss_before is None:
            return None
        return round(now - self._rss_before, 1)

    def close(self):
        pass


# ---------------------------------------------------------------------------
# MiniCPM5-1B backend (Ollama HTTP API)
# ---------------------------------------------------------------------------

import json as _json
import urllib.request as _urlreq


def _schema_spec():
    """Compact prompt spec of the 8-Block schema (keys + types + hint)."""
    parts = []
    for name, desc in SCHEMA["parameters"]["properties"].items():
        parts.append(f"- {name}: array of strings ({desc})")
    req = ", ".join(SCHEMA["parameters"]["required"])
    return "Schema keys (output EXACTLY these keys, each a list of strings):\n" \
        + "\n".join(parts) + f"\nRequired keys: {req}"


_SYSTEM_8BLOCK = (
    "You are a Danbooru tag classifier for an AI-painting pipeline. "
    "Given a comma-separated prompt line, put each tag into exactly ONE of "
    "the schema groups. Do not duplicate tags across groups. "
    "Output ONLY a JSON object with the schema keys. No prose, no markdown."
)


class MiniCPMBackend:
    name = "minicpm5-1b"

    def __init__(self, model: str = "openbmb/minicpm5",
                 base_url: str = "http://127.0.0.1:11434",
                 temperature: float = 0.0, num_ctx: int = 4096,
                 max_new_tokens: int = 1024):
        self._model = model
        self._url = base_url + "/api/chat"
        self._temperature = temperature
        self._num_ctx = num_ctx
        self._max_new_tokens = max_new_tokens
        self._spec = _schema_spec()
        self.last_confidence = None  # Ollama API exposes no calibrated score

    def extract(self, prompt: str) -> Optional[dict]:
        messages = [
            {"role": "system", "content": _SYSTEM_8BLOCK + "\n" + self._spec},
            {"role": "user", "content": f"Prompt: {prompt}\nReturn the JSON breakdown."},
        ]
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": self._temperature, "num_ctx": self._num_ctx,
                        "num_predict": self._max_new_tokens},
        }
        req = _urlreq.Request(self._url, data=_json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json"})
        with _urlreq.urlopen(req, timeout=300) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        content = data.get("message", {}).get("content", "")
        return _parse_json_object(content)

    def close(self):
        pass


def _parse_json_object(content: str) -> Optional[dict]:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
        content = content.strip()
    try:
        obj = _json.loads(content)
    except (ValueError, TypeError):
        # fallback: extract the first {...} block
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            obj = _json.loads(content[start:end + 1])
        except ValueError:
            return None
    return obj if isinstance(obj, dict) else None


def load_backend(name: str, **kw):
    if name == "rule":
        return RuleBackend()
    if name == "needle":
        return NeedleBackend(**kw)
    if name in ("minicpm", "minicpm5"):
        return MiniCPMBackend(**kw)
    raise ValueError(f"unknown backend: {name} (use rule|needle|minicpm)")
