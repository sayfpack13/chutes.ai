"""Classify chute configs for CLI / dashboard behavior."""

from typing import FrozenSet

# Chutes SDK templates that use a standard platform image (no ``chutes build``).
PLATFORM_IMAGE_CHUTE_TYPES: FrozenSet[str] = frozenset(
    {"vllm", "sglang", "diffusion", "embedding"}
)


def uses_chutes_platform_image(chute_type: str) -> bool:
    return chute_type in PLATFORM_IMAGE_CHUTE_TYPES
