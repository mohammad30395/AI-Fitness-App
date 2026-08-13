#!/usr/bin/env python
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local environment configuration.")
    parser.add_argument(
        "--mode",
        choices=("base", "astra", "langflow", "all"),
        default="base",
        help="Configuration group to validate. 'base' requires no service credentials.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = config.validate_config(args.mode)
    required = set(config.REQUIRED_BY_MODE[args.mode])

    print(f"Configuration mode: {args.mode}")
    print("Values are redacted; only set/missing status is shown.")
    for name, is_set in config.variable_status().items():
        requirement = "required" if name in required else "optional"
        status = "set" if is_set else "missing"
        print(f"{name}: {status} ({requirement}, value redacted)")

    if result.ok:
        print(result.messages[0])
        return 0

    print("Missing required variables:")
    for name in result.missing:
        print(f"- {name}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
