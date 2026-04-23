class Field:
    def __init__(
        self,
        field_type,
        primary_key=False,
        nullable=True,
        default=None,
        column_name=None,
        validator=None,
        choices=None,
        max_length=None,
        version=False,
        precision=None,
        scale=None,
    ):
        self.field_type = field_type
        self.primary_key = primary_key
        self.nullable = nullable
        self.default = default
        self.column_name = column_name
        self.validator = validator
        self.choices = tuple(choices) if choices else None
        self.max_length = max_length
        self.version = version
        self.precision = precision
        self.scale = scale

    def __repr__(self):
        return f"Field({self.field_type.__name__})"
