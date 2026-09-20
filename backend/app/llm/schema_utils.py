from copy import deepcopy
from typing import Any

# JSON Schema の注釈のうち、Tool 定義に不要なキー。
# ただし "properties" の中では **プロパティ名** なので落としてはいけない
# （例: create_task の title を消すと LLM から引数が見えなくなる）。
_DROPPED_ANNOTATIONS = ("$defs", "definitions", "title")


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic が生成した JSON Schema の $ref を実体に展開する。

    Pydantic は Enum などを $defs + $ref で表現するが、LLM プロバイダの
    Tool スキーマは $ref を解釈しないことがあるため、実体に埋め込む。
    """
    definitions = schema.get("$defs", {})

    def resolve(node: Any, *, keys_are_names: bool = False) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            name = str(node["$ref"]).rsplit("/", 1)[-1]
            target = deepcopy(definitions.get(name, {}))
            # $ref と併記された description などは展開後も残す
            extras = {key: value for key, value in node.items() if key != "$ref"}
            return resolve({**target, **extras})

        resolved: dict[str, Any] = {}
        for key, value in node.items():
            if keys_are_names:
                # ここでのキーはプロパティ名なので、名前で捨ててはいけない
                resolved[key] = resolve(value)
                continue
            if key in _DROPPED_ANNOTATIONS:
                continue
            resolved[key] = resolve(value, keys_are_names=(key == "properties"))

        return resolved

    result = resolve(schema)
    assert isinstance(result, dict)
    return result
