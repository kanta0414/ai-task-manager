from copy import deepcopy
from typing import Any

# Tool の引数スキーマで使わないキー（LLM に渡しても意味がなく、
# プロバイダによっては受け付けないため落とす）
_DROPPED_KEYS = ("$defs", "definitions", "title")


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic が生成した JSON Schema の $ref を実体に展開する。

    Pydantic は Enum などを $defs + $ref で表現するが、LLM プロバイダの
    Tool スキーマは $ref を解釈しないことがあるため、実体に埋め込む。
    """
    definitions = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            ref: str = node["$ref"]
            name = ref.rsplit("/", 1)[-1]
            target = deepcopy(definitions.get(name, {}))
            # $ref と併記された description などは展開後も残す
            extras = {k: v for k, v in node.items() if k != "$ref"}
            return resolve({**target, **extras})

        return {
            key: resolve(value)
            for key, value in node.items()
            if key not in _DROPPED_KEYS
        }

    resolved = resolve(schema)
    assert isinstance(resolved, dict)
    return resolved
