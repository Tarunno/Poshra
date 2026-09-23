"""Refuse a declarative config with a repeated top-level key.

A repeated key is valid YAML: the last one wins and the earlier ones vanish
without a word. `kong config parse` then reports success on whatever survived,
so an entire block of plugins can disappear and every check still passes —
which is exactly how the tracing plugin was silently dropped.
"""

import sys

import yaml


def main(path: str) -> None:
    node = yaml.compose(open(path))
    keys = [key.value for key, _ in node.value]
    repeated = sorted({key for key in keys if keys.count(key) > 1})
    if repeated:
        sys.exit(f"duplicate top-level keys in {path}: {repeated}")
    print(f"{path}: no duplicate top-level keys")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "gateway/kong/kong.yaml")
