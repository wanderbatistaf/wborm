class Field:
    def __init__(self, field_type, primary_key=False, nullable=True):
        self.field_type = field_type
        self.primary_key = primary_key
        self.nullable = nullable

    def __repr__(self):
        return f"Field({self.field_type.__name__})"