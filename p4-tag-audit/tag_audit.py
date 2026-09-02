#!/usr/bin/env python3
"""
P4 Tag Audit v2 — 强制标签合规审计（严格模式）
==============================================
v6.3+ 的 P4 终检。核心变更（v2）：
- **所有 token 必须能表示为合法 Danbooru 标签**（单 token 或下划线多词）
- 多词叙事短语（如 "remembering childhood game find same color"）转下划线后
  不是合法标签 → 判违规，并给出"拆解为合法标签"的建议
- 输出必须是 tags 组成的提示词组合；叙事内容只能进 MD 的 nltags_block

用法:
    python tag_audit.py <input.txt> [--output audit.md] [--cli path] [--strict]

退出码: 0 = 全部合规 | 1 = 存在违规 | 2 = 环境错误
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------
# 白名单：跳过校验
# ---------------------------------------------------------------
STYLE_PREFIX = {
    "masterpiece", "best_quality", "highres", "absurdres", "newest",
    "year_2025", "year_2026", "ultra_detailed", "8k", "official_art",
}

SERIES_TAGS = {"equestria_girls", "my_little_pony", "1girl", "solo", "animal"}

CHARACTER_TAGS = {
    "fluttershy", "twilight_sparkle", "rainbow_dash", "rarity", "applejack",
    "pinkie_pie", "sunset_shimmer", "starlight_glimmer", "spike", "trixie",
    # 仙剑/西游 cos 角色（非 Danbooru 体系，走 nltags，白名单跳过）
    "zhao_ling_er", "lin_yueru", "liu_mengli", "zixuan", "tang_xuejian",
    "white_bone_spirit", "princess_iron_fan", "jade_rabbit_spirit",
}

APPEARANCE_TAGS = {
    "pink_hair", "purple_hair", "multicolored_hair", "blonde_hair", "red_hair",
    "long_hair", "short_hair", "curly_hair", "teal_hair_tips", "silver_hair",
    "green_eyes", "blue_eyes", "purple_eyes", "amber_eyes", "glasses",
    "freckles", "ponytail", "twin_tails", "hair_ornament", "hair_flower",
    "bangs", "ahoge", "eyebrows",
}

KNOWN_VALID = {
    # 场景
    "brick_wall", "graffiti", "spray_paint", "spray_can", "tunnel", "alley",
    "overpass", "bridge", "storefront", "barn", "laundromat", "rooftop",
    "water_tower", "theater", "abandoned", "night", "city_lights",
    "neon_lights", "vhs_artifacts", "track_and_field", "fitting_room",
    "gas_station", "photocopier", "karaoke", "crosswalk", "shibuya",
    "escalator", "subway_station", "convenience_store", "pedestrian_bridge",
    "courtyard", "mansion", "pavilion", "paper_lantern", "calligraphy",
    "ink", "sumi_e", "silk", "folding_fan", "tatami", "temple_gate", "torii",
    "rock_garden", "bamboo_forest", "bookstore", "lantern", "fire_escape",
    "playground", "van", "manhole_cover", "stone_path", "dark_room",
    "security_camera", "crt", "static", "sunrise", "vending_machine",
    "disco_ball", "library", "mirror", "office", "microphone", "low_angle",
    "china_dress", "cheongsam", "police_car", "bedroom", "kitchen",
    "bathroom", "shower", "pool", "beach", "snow", "rain", "umbrella",
    "autumn_leaves", "cherry_blossoms", "moon", "starry_sky", "clouds",
    "sunset", "dawn", "day", "evening", "morning", "indoors", "outdoors",
    "city", "street", "park", "forest", "mountain", "river", "ocean",
    # 服装
    "pencil_skirt", "crop_top", "latex_skirt", "hanfu", "qipao",
    "pantyhose", "thighhighs", "garter", "fishnet_stockings",
    "sheer_stockings", "ankle_socks", "nude_stockings", "white_stockings",
    "knee_socks", "sailor_suit", "school_uniform", "sweater", "cardigan",
    "hoodie", "oversized_clothes", "coat", "jacket", "blazer", "trenchcoat",
    "skirt", "dress", "shirt", "blouse", "t_shirt", "pajamas", "nightgown",
    "bra", "panties", "lace_trim", "bow", "ribbon", "hairband",
    "mary_janes", "platform_boots", "high_heels", "sneakers", "loafers",
    "slippers", "sandals", "stockings", "socks", "leg_warmers", "toe_socks",
    "kneehighs", "overknee_socks", "sports_uniform", "swimsuit", "bikini",
    "school_swimsuit", "apron", "maid_outfit", "santa_costume", "kimono",
    "yukata", "witch_hat", "crown", "armor", "military_uniform", "suit",
    # 姿势/动作
    "kneeling", "all_fours", "contrapposto", "squatting", "straddling",
    "lying", "leaning", "sitting", "standing", "running", "jumping",
    "dancing", "sleeping", "crouching", "prone", "supine", "sideways",
    "cross_legged", "seiza", "hand_on_hip", "hands_up", "arms_up",
    "arms_crossed", "hand_in_pocket", "holding_object", "looking_away",
    "looking_at_viewer", "looking_back", "closed_eyes", "winking",
    "blushing", "smiling", "laughing", "surprised", "sleepy", "exhausted",
    "thinking", "concentrating", "tears", "crying", "pout", "tongue_out",
    # 足部
    "barefoot", "toes", "feet", "legs", "foot_focus", "sole", "arches",
    "footprint", "toenails", "pedicure", "ankle", "calf", "thigh",
    "sitting_on_floor", "feet_up", "feet_on_table", "crossed_legs",
    # 其他常用
    "monochrome", "colorful", "pastel_colors", "dress", "hairclip",
    "jewelry", "necklace", "earrings", "gloves", "hat", "scarf", "belt",
    "backpack", "purse", "cellphone", "laptop", "headphones", "book",
    "writing", "reading", "eating", "drinking", "smoking", "holding_phone",
    "selfie", "photo", "music", "guitar", "piano", "violin", "microphone",
    "chibi", "super_deformed", "kawaii", "cute", "soft_shading",
    "flat_color", "simple_background", "sticker", "lineart",
    "winter_clothes", "scarf", "gloves", "muffler", "earmuffs",
    "christmas", "halloween", "new_year", "fireworks", "lantern_festival",
}

# 多词短语中常见的停用词（拆解建议时忽略）
STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "of", "to", "for", "with", "and",
    "or", "but", "is", "are", "was", "were", "has", "have", "had", "my",
    "her", "his", "its", "their", "your", "this", "that", "like", "just",
    "very", "really", "about", "from", "into", "over", "under", "through",
    "while", "when", "during", "after", "before", "being", "been", "get",
    "got", "having", "doing", "going", "one", "two", "three", "first",
    "last", "same", "own", "so", "as", "if", "then", "than", "too",
}


# ---------------------------------------------------------------
# Token 规范化：多词短语 → 下划线标签形式
# ---------------------------------------------------------------
def normalize_token(raw):
    """'remembering childhood game' → 'remembering_childhood_game'
    'purple_hair' → 'purple_hair'（保留已有下划线）
    'see-through_legwear' → 'see-through_legwear'（保留连字符，Danbooru 有连字符标签）
    去除其余标点，转小写，空格转下划线"""
    t = re.sub(r"[^a-z0-9\s_\-]", "", raw.lower())
    t = re.sub(r"\s+", "_", t.strip())
    return t


def split_phrase(phrase):
    """把下划线短语拆回单词列表"""
    return [w for w in phrase.split("_") if w and w not in STOPWORDS]


# ---------------------------------------------------------------
# CLI
# ---------------------------------------------------------------
def find_cli():
    candidates = [
        os.environ.get("DANBOORU_TAGS_CLI", ""),
        os.path.expanduser("~/.workbuddy/skills/danbooru-tags/bin/danbooru-tags.exe"),
        r"C:\Users\fu268\.workbuddy\skills\danbooru-tags\bin\danbooru-tags.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    env_dir = os.environ.get("COMFYUI_GOOD_ANIMA_SKILLS_DIR", "")
    if env_dir:
        p = Path(env_dir) / "danbooru-tags/bin/danbooru-tags.exe"
        if p.exists():
            return str(p)
    return None


def batch_check(cli, tokens):
    """批量校验。返回 {token: (status, matched, layer)}
    批查请求不带 group；返回 results 是 dict 按 id 索引。"""
    if not tokens:
        return {}
    payload = {
        "queries": [
            {"id": f"t{i}", "keyword": tok, "limit": 3}
            for i, tok in enumerate(tokens)
        ]
    }
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "tag_audit_batch.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    try:
        result = subprocess.run(
            [cli, "--batch-file", tmp, "--batch-workers", "8",
             "--for-prompt", "--json", "--compact"],
            capture_output=True, text=True, timeout=180,
        )
        if result.returncode != 0:
            return {t: ("cli_error", "", "") for t in tokens}
        data = json.loads(result.stdout)
    except Exception as e:
        return {t: (f"error:{e}", "", "") for t in tokens}
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    results_map = data.get("results", {})
    out = {}
    for i, tok in enumerate(tokens):
        q = results_map.get(f"t{i}", {})
        confirmed = q.get("confirmed_tags", {})
        candidate = q.get("candidate_tags", {})
        found = False
        matched = ""
        layer = ""
        # v2: 只有 exact_tag / exact_alias 算合规
        # fuzzy/prefix/contains = 该短语不是标准标签 → 违规（需拆解或换标准标签）
        for grp, tags in confirmed.items():
            for t in tags:
                ml = t.get("match_layer", "")
                if ml in ("exact_tag", "exact_alias"):
                    found, matched, layer = True, t.get("tag", tok), ml
                    break
            if found:
                break
        if found:
            out[tok] = ("ok", matched, layer)
        else:
            # 记录 fuzzy 命中作为参考建议
            fuzzy_hint = ""
            for grp, tags in candidate.items():
                for t in tags:
                    if t.get("match_layer") in ("fuzzy", "prefix", "contains"):
                        fuzzy_hint = t.get("tag", "")
                        break
                if fuzzy_hint:
                    break
            out[tok] = ("missing", fuzzy_hint, "")
    return out


# ---------------------------------------------------------------
# TXT 解析
# ---------------------------------------------------------------
def parse_txt(path):
    scenes = []
    current_title = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("# "):
                current_title = line[2:].strip()
            elif line.startswith("masterpiece") or line.startswith("best quality"):
                tokens = [t.strip() for t in line.split(",") if t.strip()]
                if current_title:
                    scenes.append((current_title, tokens))
    return scenes


# ---------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="P4 Tag Audit v2 (strict)")
    ap.add_argument("input", help="输入 TXT 文件路径")
    ap.add_argument("--output", default=None)
    ap.add_argument("--cli", default=None)
    ap.add_argument("--no-strict", action="store_true",
                    help="关闭严格模式：多词短语不转下划线校验（默认开启严格模式）")
    args = ap.parse_args()

    cli = args.cli or find_cli()
    if not cli:
        print("❌ 未找到 danbooru-tags CLI", file=sys.stderr)
        sys.exit(2)

    scenes = parse_txt(args.input)
    if not scenes:
        print("❌ 未在 TXT 中找到 prompt 行", file=sys.stderr)
        sys.exit(2)

    # 收集待校验 token（全部转下划线形式）
    all_tokens = set()
    for _, tokens in scenes:
        for tok in tokens:
            norm = normalize_token(tok)
            if not norm:
                continue
            if norm in STYLE_PREFIX or norm in SERIES_TAGS or norm in CHARACTER_TAGS:
                continue
            if norm in APPEARANCE_TAGS or norm in KNOWN_VALID:
                continue
            all_tokens.add(norm)

    print(f"场景数: {len(scenes)} | 待校验 token(下划线化后): {len(all_tokens)}")
    results = batch_check(cli, sorted(all_tokens))

    report_lines = [f"# P4 Tag Audit v2 (strict) — {Path(args.input).name}", ""]
    violations = []          # [(token, 建议)]
    for tok in sorted(results):
        status, matched, layer = results[tok]
        if status == "ok":
            report_lines.append(f"| {tok} | ✅ {layer} → {matched} |")
        else:
            # 拆解建议：把短语拆成单词，逐个查已知合法标签
            words = split_phrase(tok)
            known_parts = [w for w in words if w in KNOWN_VALID]
            if known_parts:
                suggestion = "拆解为: " + ", ".join(known_parts)
            elif matched:
                suggestion = f"非标准标签(fuzzy→{matched})，改用: {matched}"
            else:
                suggestion = "移入 nltags_block (仅MD)"
            report_lines.append(f"| {tok} | ❌ → {suggestion} |")
            violations.append((tok, suggestion))

    report_lines.append("")
    report_lines.append("## 场景级违规")
    for title, tokens in scenes:
        bad = []
        for tok in tokens:
            norm = normalize_token(tok)
            if norm in results and results[norm][0] == "missing":
                bad.append(tok)
        if bad:
            report_lines.append(f"- **{title}**: ❌ {', '.join(bad)}")
        else:
            report_lines.append(f"- {title}: ✅ 全部合规")

    report_lines.append(f"\n## 结论\n- 违规 token: {len(violations)} 个 (v2严格模式)")
    report = "\n".join(report_lines)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"报告已写入: {args.output}")

    if violations:
        print(f"\n❌ 存在 {len(violations)} 个不合规 token (必须为合法 Danbooru 标签):")
        for v, sug in violations:
            print(f"   - {v}  →  {sug}")
        sys.exit(1)
    else:
        print("\n✅ 全部 token 通过 — 输出完全由合法 Danbooru 标签组成")
        sys.exit(0)


if __name__ == "__main__":
    main()
