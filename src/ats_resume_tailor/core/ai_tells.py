"""Words that read as machine-written on a resume. A bank can add its own under `banned_words`.

Lower case, whole words. Inflections are listed out, because matching is on word boundaries.
"""

from __future__ import annotations

AI_TELLS: tuple[str, ...] = (
    "leverage",
    "leveraged",
    "leverages",
    "leveraging",
    "spearhead",
    "spearheaded",
    "spearheading",
    "synergy",
    "synergies",
    "passionate",
    "cutting-edge",
    "robust",
    "seamless",
    "seamlessly",
    "delve",
    "delved",
    "tapestry",
    "innovative",
    "results-driven",
    "proven track record",
    "game-changer",
    "utilize",
    "utilized",
    "utilizes",
    "utilizing",
    "best-in-class",
    "world-class",
    "holistic",
)
