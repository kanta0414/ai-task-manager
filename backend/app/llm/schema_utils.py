from copy import deepcopy
from typing import Any

# JSON Schema の注釈のうち、Tool 定義に不要なキー。
# ただし "properties" の中では **プロパティ名** なので落としてはいけない
# （例: create_task の title を消すと LLM から引数が見えなくなる）。
_DROPPED_ANNOTATIONS = (
    "$defs",
    "definitions",
    "title",
    # 文字数制限は Backend の Pydantic が検証する。LLM に渡しても
    # トークンを消費するだけなので落とす（数値の範囲は意味があるので残す）
    "minLength",
    "maxLength",
)


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


def simplify_nullable(schema: dict[str, Any]) -> dict[str, Any]:
    """任意項目の冗長な表現を削り、プロンプトのトークン数を減らす。

    Pydantic は ``str | None`` を ``anyOf: [{type: string}, {type: null}]`` と
    ``default: null`` で表現するが、LLM に渡すうえでは型が1つ見えていれば足りる。
    ローカルLLMでは入力トークン数が応答時間に直結するため、ここを削る。
    必須かどうかは ``required`` が持っているので、省略可能性は失われない。
    """

    def walk(node: Any, *, keys_are_names: bool = False) -> Any:
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node

        simplified = dict(node)

        variants = simplified.get("anyOf")
        if isinstance(variants, list):
            concrete = [v for v in variants if v.get("type") != "null"]
            if len(concrete) == 1:
                simplified.pop("anyOf")
                # description などの注釈は残したまま型定義を取り込む
                simplified = {**concrete[0], **simplified}

        if simplified.get("default", "keep") is None:
            simplified.pop("default")

        return {
            key: walk(value, keys_are_names=(key == "properties" and not keys_are_names))
            if not keys_are_names
            else walk(value)
            for key, value in simplified.items()
        }

    result = walk(schema)
    assert isinstance(result, dict)
    return result
