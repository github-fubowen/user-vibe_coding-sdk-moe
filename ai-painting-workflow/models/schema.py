"""8-Block extraction schema (JSON Schema dict) for model backends.

Maps a Danbooru-style prompt line onto the workflow's 8-Block layout
(SKILL.md §8-Block 全维度设计纪律). All fields are arrays of tags; the
identity/quality blocks are optional in extraction (engine injects them).

This schema is passed to needle.extract() verbatim — the engine compiles
a byte-level grammar from it, so every response is structurally valid JSON.
"""

BLOCK_DESCRIPTIONS = {
    "identity": "character tags and series name: 1girl/2girls/multiple_girls, solo, series like equestria_girls, character names like fluttershy",
    "style": "style anchors and art style: innocent, vaporwave, synthwave, art_deco, glitch, grid, solo is identity not style",
    "composition": "camera/composition: close-up, wide_shot, from_behind, pov, knee_up, cowboy_shot, profile, perspective (low_angle is invalid)",
    "attire": "clothing and accessories: main outfit, choker, hair_ribbon, mary_janes, socks/shoes, see-through_legwear",
    "body": "body features: hairstyle, eye color, figure (long_legs, midriff, navel, collarbone), skin (pale_skin, slender)",
    "action": "named poses and body details: contrapposto, kneeling, crossed_legs, hand on chin, foot details (spread_toes, soles, foot_focus)",
    "expression": "expression tags: shy, neutral, teasing, seductive_smile, closed_eyes, looking_away (avoid plain blush/smile)",
    "scene": "environment and atmosphere: arcade, jukebox, neon, reflection, puddle, static, street",
    "quality": "quality anchors: masterpiece, best_quality, highres, absurdres, year_2026",
}

SCHEMA = {
    "name": "PromptBreakdown",
    "description": "Split a Danbooru-style prompt line into the 8-Block tag groups.",
    "parameters": {
        "type": "object",
        "properties": {
            name: {
                "type": "array",
                "items": {"type": "string"},
                "description": desc,
            }
            for name, desc in BLOCK_DESCRIPTIONS.items()
        },
        "required": ["style", "composition", "attire", "body", "action", "expression"],
    },
}

# Blocks in workflow order (for stable reporting).
BLOCK_ORDER = [
    "identity", "style", "composition", "attire",
    "body", "action", "expression", "scene", "quality",
]
