"""
Shared JSON extraction utility.
Handles markdown code fences, preamble text, and truncated responses.
"""

import json
import re


def extract_json(raw: str, default=None):
    """
    Robustly extract JSON (dict or list) from Claude's response.

    Handles:
    - Markdown code fences: ```json ... ``` or ``` ... ```
    - Preamble/postamble text
    - Returns `default` (empty dict or list) if all attempts fail
    """
    if default is None:
        default = {}

    if not raw:
        return default

    # 1. Try markdown code fence first: ```json { ... } ```
    fence_match = re.search(r'```(?:json)?\s*([\[\{][\s\S]*?[\]\}])\s*```', raw)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except Exception:
            pass

    # 2. Try extracting dict {}
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        pass

    # 3. Try extracting list []
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        return json.loads(raw[start:end])
    except Exception:
        pass

    return default
