#!/usr/bin/env python3
"""
Quick test for schema-enforcing retry wrapper using Granite.
This will send a trivial classification prompt and validate the forced schema.
"""
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PKG_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PKG_ROOT not in sys.path:
    sys.path.append(PKG_ROOT)

from utils.model_calling import call_with_schema_retry


def main() -> None:
    system = "You are a classification model."
    user = (
        "Classify this object as a ball or a brick and output as json like {\"class\": [array of strings]} "
        "where class can be one or more of [ball, brick, none]. The object is ambiguous."
    )
    allowed = ["ball", "brick", "none"]

    try:
        result = call_with_schema_retry(system, user, allowed_classes=allowed, max_attempts=3)
        print("Result:", result)
    except Exception as e:
        print("Failed:", e)


if __name__ == "__main__":
    main()


