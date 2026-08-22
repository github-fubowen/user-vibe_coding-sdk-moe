#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
privacy-scan.py — 公开推送前隐私扫描 (v1.0, 2026-08-22)

Purpose: scan a directory tree (typically a git repo before a public push)
for machine-specific / personal-content leaks that should never reach a public
repo: Windows usernames, home-dir paths, drive-letter paths, localhost
endpoints, API keys/tokens, and personal emails. Mirrors the manual grep scan
that caught 5 path leaks in v1.15.1 — now scripted (P3).

Design rules (SDK §3/G-gates, §5.2 grounding, §10.9 risk tier):
  * Python 3.9+ stdlib only. Read-only (never modifies anything).
  * Binary-aware: skips non-text files by size + NUL-byte sniff.
  * Bounded output: per-pattern group, file:line + snippet, capped per group.
  * Exit: 0 = clean / 2 = findings (blocker for push).

Usage:
  python privacy-scan.py [path]                 # scan a dir (default: cwd)
  python privacy-scan.py --json                 # machine-readable JSON
  python privacy-scan.py --user fu268           # extra username to flag
  python privacy-scan.py --allow-user alice     # allow a username (docs/examples)
  python privacy-scan.py --group paths --group keys   # subset of groups
Exit codes: 0 = clean / 2 = findings found (blocker for public push).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# --- pattern groups ---------------------------------------------------------
# Each group: list of (label, compiled regex, context-hint).
GROUPS: dict[str, list[tuple[str, re.Pattern, str]]] = {
    "users": [],   # filled at runtime with --user / --allow-user
    "paths": [
        ("win-user-home", re.compile(r"(?:C:\\\\Users\\|C:/Users/|/c/Users/)([^\\/\\\\]+)", re.I),
         "Windows username + home dir"),
        ("drive-letter", re.compile(r"\b[A-Za-z]:[\\\\/](?![A-Za-z0-9_]*(?:example|sample|test|mock)\b)", re.I),
         "drive-letter path (D:/...)"),
        ("unix-home", re.compile(r"\b(?:/home/|~\\/)", re.I), "unix home path"),
        ("softlink-real", re.compile(r"/d/softlink\b|/softlink\b", re.I),
         "symlink real path (this machine)"),
    ],
    "endpoints": [
        ("localhost", re.compile(r"localhost:[0-9]{4,5}|127\.0\.0\.1:[0-9]{4,5}", re.I),
         "local service endpoint"),
    ],
    "keys": [
        ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), "OpenAI-style API key"),
        ("ghp-token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "GitHub PAT (ghp_)"),
        ("gho-token", re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"), "GitHub OAuth token"),
        ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "GitHub fine-grained PAT"),
        ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{12,}\b"), "AWS access key id"),
        ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
        ("bearer", re.compile(r"(?i)\bBearer\\s+[A-Za-z0-9._-]{20,}\b"), "Bearer token"),
        ("password-assign", re.compile(r"(?i)\bpassword\\s*[=:]\\s*['\"][^'\"]{4,}['\"]"),
         "password assignment"),
        ("api-key-assign", re.compile(r"(?i)\bapi[_-]?key\\s*[=:]\\s*['\"][^'\"]{8,}['\"]"),
         "api key assignment"),
    ],
    "emails": [
        ("personal-email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
         "email address"),
    ],
}

# Values that are clearly documentation/test examples — never flag these.
ALLOWED_EMAIL_SUFFIXES = ("example.com", "example.org", "test.com", "test.org",
                          "localhost", "@test", "example.net", "corp.local", "example.io")
ALLOWED_EMAIL_ADDRESSES = set()
ALLOWED_KEY_VALUES = {
    "AKIAIOSFODNN7EXAMPLE", "AKIAI44QH8DHBEXAMPLE", "AKIAXXXXXXXXXXXXXXXX",
    "AKIAEXPOSEDKEY123456", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY",
}
# Substrings that mark a line as documentation (AWS docs etc.) — skip.
ALLOWED_KEY_CONTEXT = ("example", "EXAMPLE", "your_", "<", "changeme", "passwd-placeholder",
                       "TEST", "test-", "-test")
# Generic Windows paths that exist on every machine — not personal fingerprint.
ALLOWED_PATH_CONTEXT = ("Program Files", "Windows", "System32", "/usr/", "/bin/", "/etc/",
                        "AppData", "\\...\\", "/.../", "TEST")

# Files/dirs to skip entirely.
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
             ".idea", ".vscode", ".next", "dist", "build"}
SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".woff",
             ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".gz", ".7z", ".exe", ".dll",
             ".pack", ".idx", ".bin", ".pyc", ".lock", ".dll"}


def build_groups(args: argparse.Namespace) -> dict[str, list[tuple[str, re.Pattern, str]]]:
    """Assemble active groups; inject user-specific patterns."""
    active = {g: GROUPS[g] for g in args.group if g in GROUPS}
    # users group is runtime-built
    if "users" in args.group:
        users: list[tuple[str, re.Pattern, str]] = []
        for u in args.user:
            users.append((f"username-{u}", re.compile(rf"\b{re.escape(u)}\b"), "configured username"))
        allowed = set(args.allow_user)
        # keep usernames NOT in the allowlist
        active["users"] = [e for e in users if e[0].replace("username-", "") not in allowed]
    return active


def is_binary(path: Path, head: bytes) -> bool:
    if path.stat().st_size > 2_000_000:  # >2MB text unlikely; skip
        return True
    return b"\x00" in head[:4096]


def scan_file(path: Path, active: dict, caps: dict) -> list[dict]:
    """Scan one text file. Returns list of {file, group, label, line, snippet}."""
    found: list[dict] = []
    try:
        raw = path.read_bytes()
    except OSError:
        return found
    if is_binary(path, raw[:4096]):
        return found
    try:
        text = raw.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        return found

    for lineno, line in enumerate(text.splitlines(), 1):
        if len(line) > 2000:   # minified/one-liner blobs — skip (huge noise)
            continue
        for gname, entries in active.items():
            if caps.get(gname, 0) <= 0:
                continue
            for label, pat, hint in entries:
                for m in pat.finditer(line):
                    val = m.group(0)
                    if gname == "keys" and _key_benign(val, line):
                        continue
                    if gname == "emails":
                        em = m.group(0).strip()
                        if em.lower() in ALLOWED_EMAIL_ADDRESSES or em.lower().endswith(ALLOWED_EMAIL_SUFFIXES):
                            continue
                    if gname == "paths" and _path_benign(line):
                        continue
                    found.append({
                        "file": str(path), "line": lineno, "group": gname,
                        "label": label, "match": val[:120], "hint": hint,
                        "snippet": line.strip()[:160],
                    })
                    caps[gname] -= 1
                    if caps.get(gname, 0) <= 0:
                        break
                if caps.get(gname, 0) <= 0:
                    break
    return found


def _key_benign(val: str, line: str) -> bool:
    if val in ALLOWED_KEY_VALUES:
        return True
    # AWS docs example keys / placeholder patterns on the same line
    for marker in ALLOWED_KEY_CONTEXT:
        if marker in line:
            return True
    return False


def _path_benign(line: str) -> bool:
    """Drive-letter path on a line containing generic Windows paths = not personal."""
    for marker in ALLOWED_PATH_CONTEXT:
        if marker in line:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Public-push privacy scanner (P3)")
    ap.add_argument("path", nargs="?", default=".", help="dir to scan (default: cwd)")
    ap.add_argument("--user", action="append", default=[],
                    help="username(s) to flag (repeatable); default empty")
    ap.add_argument("--allow-user", action="append", default=[],
                    help="username(s) to allow (docs/examples); repeatable")
    ap.add_argument("--group", action="append", default=list(GROUPS.keys()),
                    choices=list(GROUPS.keys()),
                    help="pattern groups to run (default: all)")
    ap.add_argument("--cap", type=int, default=50,
                    help="max findings per group (default 50)")
    ap.add_argument("--json", action="store_true", help="machine-readable JSON")
    args = ap.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"[fatal] not a directory: {root}", file=sys.stderr)
        return 2

    active = build_groups(args)
    caps = {g: args.cap for g in active}
    findings: list[dict] = []
    scanned = 0
    skipped = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if any(part in SKIP_DIRS for part in Path(dirpath).relative_to(root).parts):
            skipped += len(filenames)
            continue
        for fn in filenames:
            if Path(fn).suffix.lower() in SKIP_EXTS:
                skipped += 1
                continue
            fp = Path(dirpath) / fn
            if fp.is_symlink():
                skipped += 1
                continue
            if fp.name == "privacy-scan.py":
                skipped += 1   # self-skip: its own regex literals are false positives
                continue
            scanned += 1
            findings.extend(scan_file(fp, active, caps))

    findings.sort(key=lambda f: (f["group"], f["file"], f["line"]))
    clean = len(findings) == 0
    report = {
        "time": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "root": str(root), "scanned": scanned, "skipped": skipped,
        "groups": sorted(active.keys()), "clean": clean,
        "findings": findings[: args.cap * 10],
        "total": len(findings),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"== privacy scan: {root} ({scanned} files, {skipped} skipped) ==")
        if clean:
            print("  CLEAN — 0 findings")
        else:
            by_group: dict[str, int] = {}
            for f in findings:
                by_group[f["group"]] = by_group.get(f["group"], 0) + 1
            for g, n in by_group.items():
                print(f"  {g}: {n} finding(s)")
            for f in findings[: args.cap * 3]:
                print(f"  !! [{f['group']}/{f['label']}] {f['file']}:{f['line']} "
                      f"match={f['match']!r} ({f['hint']})")
        print(f"Total findings: {len(findings)} — exit {'0 (clean)' if clean else '2 (blocker)'}")
    return 0 if clean else 2


if __name__ == "__main__":
    sys.exit(main())
