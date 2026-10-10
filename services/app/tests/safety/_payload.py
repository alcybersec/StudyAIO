"""Request builders for the floor-1 sweep: type-valid inputs with foreign ids planted.

The first sweep sent ``json={}`` to every write route and the same string to
every path parameter. Any handler whose foreign id arrives in the request body,
or whose path parameter is typed (``week: int``), failed validation with a 422
before it ran, so the sweep captured no SQL for it and called that "clean"
(M31 gate, ``docs/gates/M31/floors.md`` floor 1, "Why the floor-1 sweep missed
them"). This module builds, from each route's own declared types, a request
that *passes* validation and carries a recognisable foreign value in every
slot a caller controls:

* every ``str`` slot (ids, codes, free text alike) holds :data:`FOREIGN_ID`;
* every ``int`` slot holds :data:`FOREIGN_INT` when its bounds allow it, else
  the nearest legal value;
* ``UUID`` slots hold :data:`FOREIGN_UUID`;
* optional fields are filled too, because the optional ``course_code`` /
  ``exam_id`` is exactly where body-borne ids hide.

``_tenant.is_planted`` recognises those values in a bound parameter, so the
sweep can tell a lookup keyed on caller input from FK traversal of a row it
already resolved.
"""

from __future__ import annotations

import copy
import datetime as dt
import enum
import types
import typing
import uuid
from typing import Any

from annotated_types import Ge, Gt, Le, Lt, MaxLen, MinLen
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

FOREIGN_ID = "id-owned-by-someone-else"
#: Rare enough that a bind carrying it is almost surely the planted value, and
#: inside the usual week bounds (1..52) so ``week`` validates.
FOREIGN_INT = 47
FOREIGN_UUID = uuid.UUID("0f0f0f0f-0000-4000-8000-0000000000aa")

#: Fallbacks tried, in order, for a ``str`` slot that rejects FOREIGN_ID
#: (a pattern, an email, a date string). The first that validates wins.
STR_FALLBACKS = (
    FOREIGN_ID,
    "someone-else@example.com",
    "2026-01-01",
    "2026-01-01T00:00:00Z",
    "#ffffff",
    "en",
    "a",
)


def _int_for(metadata: list[Any]) -> int:
    low, high = None, None
    for m in metadata:
        if isinstance(m, Ge):
            low = m.ge
        elif isinstance(m, Gt):
            low = m.gt + 1
        elif isinstance(m, Le):
            high = m.le
        elif isinstance(m, Lt):
            high = m.lt - 1
    value = FOREIGN_INT
    if high is not None and value > high:
        value = high
    if low is not None and value < low:
        value = low
    return value


def _float_for(metadata: list[Any]) -> float:
    return float(_int_for(metadata))


def _str_for(annotation: Any, metadata: list[Any]) -> str:
    min_len = next((m.min_length for m in metadata if isinstance(m, MinLen)), 0)
    max_len = next((m.max_length for m in metadata if isinstance(m, MaxLen)), None)
    for candidate in STR_FALLBACKS:
        value = candidate
        if len(value) < min_len:
            value = (value + "-") * (min_len // len(value) + 1)
        if max_len is not None and len(value) > max_len:
            value = value[:max_len]
        try:
            target = typing.Annotated[annotation, *metadata] if metadata else annotation
            TypeAdapter(target).validate_python(value)
            return value
        except (ValidationError, TypeError):
            continue
    return FOREIGN_ID


def value_for(annotation: Any, metadata: list[Any] | None = None, depth: int = 0) -> Any:
    """A JSON-ready value of ``annotation`` with foreign ids planted."""
    metadata = list(metadata or [])
    if depth > 6:
        return None
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is typing.Annotated:
        # ``Annotated[int, Field(lt=5)]`` carries a FieldInfo, whose own
        # metadata holds the constraints.
        extra = [m for a in args[1:] for m in (a.metadata if isinstance(a, FieldInfo) else [a])]
        return value_for(args[0], [*metadata, *extra], depth)
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in args if a is not type(None)]
        return value_for(non_none[0], metadata, depth) if non_none else None
    if origin is typing.Literal:
        return args[0]
    if origin in (list, set, frozenset, tuple, typing.Sequence) or annotation in (list, set):
        inner = args[0] if args else str
        return [value_for(inner, [], depth + 1)]
    if origin is dict or annotation is dict:
        return {}
    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            return model_payload(annotation, depth + 1)
        if issubclass(annotation, enum.Enum):
            return next(iter(annotation)).value
        if issubclass(annotation, bool):
            return True
        if issubclass(annotation, int):
            return _int_for(metadata)
        if issubclass(annotation, float):
            return _float_for(metadata)
        if issubclass(annotation, uuid.UUID):
            return str(FOREIGN_UUID)
        if issubclass(annotation, dt.datetime):
            return "2026-01-01T00:00:00Z"
        if issubclass(annotation, dt.date):
            return "2026-01-01"
        if issubclass(annotation, dt.time):
            return "08:00:00"
        if issubclass(annotation, str):
            return _str_for(annotation, metadata)
    return FOREIGN_ID


def model_payload(model: type[BaseModel], depth: int = 0) -> dict[str, Any]:
    """Every field of ``model`` filled, validated; fields that refuse are dropped.

    A required field that still refuses is kept, so the 422 shows up in the
    sweep's statuses instead of silently shrinking the body. Cached per model:
    the sweep runs three times over ~150 routes, and building a validator per
    ``str`` slot is the slow part.
    """
    if model not in _PAYLOADS:
        _PAYLOADS[model] = _build_payload(model, depth)
    return copy.deepcopy(_PAYLOADS[model])


_PAYLOADS: dict[type[BaseModel], dict[str, Any]] = {}


def _build_payload(model: type[BaseModel], depth: int) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        key = field.alias or name
        body[key] = value_for(field.annotation, list(field.metadata), depth)
    for _ in range(len(body) + 1):
        try:
            model.model_validate(body)
            return body
        except ValidationError as exc:
            dropped = False
            for err in exc.errors():
                if not err["loc"]:
                    continue
                key = err["loc"][0]
                field = next(
                    (f for n, f in model.model_fields.items() if (f.alias or n) == key), None
                )
                if field is not None and not field.is_required() and key in body:
                    del body[key]
                    dropped = True
            if not dropped:
                return _satisfy_model_validator(model, body)
    return body


def _validates(model: type[BaseModel], body: dict[str, Any]) -> bool:
    try:
        model.model_validate(body)
    except ValidationError:
        return False
    return True


def _satisfy_model_validator(model: type[BaseModel], body: dict[str, Any]) -> dict[str, Any]:
    """A model-level rule ("text or url, not both") has no field to blame.

    Try dropping one optional field at a time, latest-declared first; the first
    body that validates wins. If none does, return it unchanged and let the 422
    show in the sweep.
    """
    optional = [(f.alias or n) for n, f in model.model_fields.items() if not f.is_required()]
    for key in reversed(optional):
        if key not in body:
            continue
        trial = {k: v for k, v in body.items() if k != key}
        if _validates(model, trial):
            return trial
    return body
