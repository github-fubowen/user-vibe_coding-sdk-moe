"""括号感知校验 — 校验含 (a:1.2) / (a, b:1.2) 权重的模型方言文件。

用法:
    python bracket_check.py <你的文件.txt>

从 ai-painting-workflow/SKILL.md 内嵌脚本迁移（v2.16），内容不变。
依赖: 在 workspace 根目录执行（.workbuddy/promptos 相对路径）。
"""
import os, sys, re
os.environ.pop("PYTHONUSERBASE", None); os.environ.pop("PYTHONPATH", None)
sys.path.insert(0, ".workbuddy/promptos")
from core.json_engine import get_json_engine
from commands.validate import (normalize, STYLE_PREFIX, SERIES_TAGS, CHARACTER_TAGS,
                               APPEARANCE_TAGS, KNOWN_VALID, KNOWN_VALID_EXTRA, ALIAS_MAP)
eng = get_json_engine()

def is_ok(tok):
    n = normalize(tok)
    if not n: return False
    if n in STYLE_PREFIX or n in SERIES_TAGS or n in CHARACTER_TAGS or n in APPEARANCE_TAGS or n in KNOWN_VALID or n in KNOWN_VALID_EXTRA: return True
    r = ALIAS_MAP.get(n, n)
    return bool(eng.lookup(n)) or (r != n and eng.lookup(r))

def split_top(ln):  # 括号感知: 顶层逗号切分
    out=[]; buf=''; depth=0
    for ch in ln:
        if ch=='(': depth+=1
        elif ch==')': depth-=1
        if ch==',' and depth==0: out.append(buf.strip()); buf=''
        else: buf+=ch
    if buf.strip(): out.append(buf.strip())
    return out

def expand(tok):  # (a, b:1.2)->[a,b]; (a:1.2)->[a]; 普通->[tok]
    m = re.fullmatch(r'\(([^()]*?):([0-9.]+)\)', tok)
    if m:
        inner = m.group(1)
        return [s.strip() for s in inner.split(',')] if ',' in inner else [inner.strip()]
    return [tok]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python bracket_check.py <文件.txt>"); sys.exit(1)
    seen=set(); miss=[]
    for i, ln in enumerate(open(sys.argv[1], encoding="utf-8"), 1):
        if not ln.strip(): continue
        for t in split_top(ln.strip()):
            for base in expand(t):
                n = normalize(base)
                if not n or n in seen: continue
                seen.add(n)
                if not is_ok(base): miss.append((i, n))
    print("缺失:", miss if miss else "无 — 全部合法")
