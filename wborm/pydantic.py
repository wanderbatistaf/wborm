"""Pydantic helpers for WBORM models."""

from typing import Iterable, Optional


def _python_type_for_field(field):
    return field.field_type or str


def create_read_schema(model_cls, name: Optional[str] = None, include: Optional[Iterable[str]] = None, exclude: Optional[Iterable[str]] = None):
    """Create a Pydantic read schema from a WBORM model class."""
    from pydantic import ConfigDict, Field as PydanticField, create_model

    include_set = set(include or model_cls._fields.keys())
    exclude_set = set(exclude or [])
    field_definitions = {}

    for field_name, field in model_cls._fields.items():
        if field_name not in include_set or field_name in exclude_set:
            continue
        annotation = _python_type_for_field(field) | None if field.nullable else _python_type_for_field(field)
        default = None if field.nullable else ...
        pydantic_meta = PydanticField(default=default, max_length=field.max_length) if field.max_length else default
        field_definitions[field_name] = (annotation, pydantic_meta)

    schema_name = name or f"{model_cls.__name__}Read"
    schema = create_model(schema_name, **field_definitions)
    schema.model_config = ConfigDict(from_attributes=True)
    return schema


def create_write_schema(
    model_cls,
    name: Optional[str] = None,
    include: Optional[Iterable[str]] = None,
    exclude: Optional[Iterable[str]] = None,
    partial: bool = False,
):
    """Create a Pydantic write schema from a WBORM model class."""
    from pydantic import Field as PydanticField, create_model

    include_set = set(include or model_cls._fields.keys())
    exclude_set = set(exclude or [])
    field_definitions = {}

    for field_name, field in model_cls._fields.items():
        if field_name not in include_set or field_name in exclude_set:
            continue
        field_type = _python_type_for_field(field)
        annotation = field_type | None if (field.nullable or partial) else field_type
        default = None if (field.nullable or field.primary_key or partial) else ...
        pydantic_meta = PydanticField(default=default, max_length=field.max_length) if field.max_length else default
        field_definitions[field_name] = (annotation, pydantic_meta)

    schema_name = name or f"{model_cls.__name__}{'Patch' if partial else 'Write'}"
    return create_model(schema_name, **field_definitions)


def dump_entity(entity, schema_cls=None):
    """Dump an entity as dict, optionally validating with a Pydantic schema."""
    payload = entity.to_dict()
    if schema_cls is None:
        return payload
    return schema_cls.model_validate(payload).model_dump()
