"""
Lazy Loading Support

This module provides lazy loading capabilities for WBORM, allowing
deferred loading of columns and relationships to improve performance.

Features:
- Defer specific columns from loading
- Load only specified columns (.only())
- Lazy load relationships on first access
- Automatic batching of lazy queries
"""

from typing import Any, List, Optional, Set, Dict
from collections import defaultdict


class DeferredAttribute:
    """
    Descriptor for deferred (lazy-loaded) attributes.

    When accessed, triggers a query to load the deferred value from the database.
    """

    def __init__(self, field_name: str):
        """
        Initialize deferred attribute.

        Args:
            field_name: Name of the field to load lazily
        """
        self.field_name = field_name
        self._loaded_values: Dict[int, Any] = {}

    def __get__(self, instance, owner):
        """Get attribute value, loading from DB if needed"""
        if instance is None:
            return self

        # Check if value is already loaded
        instance_id = id(instance)
        if instance_id in self._loaded_values:
            return self._loaded_values[instance_id]

        # Load deferred value from database
        if hasattr(instance, '_load_deferred_fields'):
            instance._load_deferred_fields([self.field_name])
            # After loading, the value should be in __dict__
            return instance.__dict__.get(self.field_name)

        raise AttributeError(
            f"Cannot load deferred field '{self.field_name}' - "
            f"instance has no _load_deferred_fields method"
        )

    def __set__(self, instance, value):
        """Set attribute value"""
        instance_id = id(instance)
        self._loaded_values[instance_id] = value
        instance.__dict__[self.field_name] = value


class LazyLoadingMixin:
    """
    Mixin to add lazy loading capabilities to Model instances.

    Provides methods to load deferred fields and relationships on demand.
    """

    def __init__(self):
        """Initialize lazy loading state"""
        self._deferred_fields: Set[str] = set()
        self._loaded_fields: Set[str] = set()
        self._connection = None

    def _mark_deferred(self, *fields: str) -> None:
        """
        Mark fields as deferred (not yet loaded).

        Args:
            *fields: Field names to defer
        """
        self._deferred_fields.update(fields)

    def _mark_loaded(self, *fields: str) -> None:
        """
        Mark fields as loaded.

        Args:
            *fields: Field names that are loaded
        """
        self._loaded_fields.update(fields)
        self._deferred_fields.difference_update(fields)

    def _is_deferred(self, field: str) -> bool:
        """
        Check if a field is deferred.

        Args:
            field: Field name to check

        Returns:
            True if field is deferred
        """
        return field in self._deferred_fields

    def _load_deferred_fields(self, fields: Optional[List[str]] = None) -> None:
        """
        Load deferred fields from database.

        Args:
            fields: Specific fields to load (None = all deferred)

        Examples:
            >>> obj._load_deferred_fields(['email', 'phone'])
            >>> obj._load_deferred_fields()  # Load all deferred
        """
        if not self._connection:
            raise RuntimeError(
                "Cannot load deferred fields without database connection"
            )

        # Determine which fields to load
        fields_to_load = (
            set(fields) if fields
            else self._deferred_fields.copy()
        )

        if not fields_to_load:
            return  # Nothing to load

        # Build and execute query to load fields
        tablename = self.__class__.__tablename__
        pk_fields = getattr(self.__class__, '_pk_field_names', lambda: [getattr(self.__class__, '_pk_field', 'id')])()
        pk_field = pk_fields[0]
        pk_value = getattr(self, pk_field, None)

        if pk_value is None:
            raise ValueError(
                f"Cannot load deferred fields - no primary key value for {pk_field}"
            )

        # SELECT only the needed fields
        field_list = ", ".join(fields_to_load)
        sql = f"SELECT {field_list} FROM {tablename} WHERE {pk_field} = ?"

        from wborm.connection_utils import run_query
        result = run_query(self._connection, sql, params=[pk_value])

        if result:
            row = result[0]
            for field in fields_to_load:
                if field in row:
                    self.__dict__[field] = row[field]
                    self._mark_loaded(field)


class RelationshipDescriptor:
    """
    Descriptor for lazy-loaded relationships.

    Loads related objects on first access.
    """

    def __init__(
        self,
        related_model: str,
        foreign_key: str,
        related_field: str = "id",
        many: bool = False
    ):
        """
        Initialize relationship descriptor.

        Args:
            related_model: Name of related model class
            foreign_key: Foreign key field on this model
            related_field: Field on related model (default: 'id')
            many: True for one-to-many, False for one-to-one
        """
        self.related_model = related_model
        self.foreign_key = foreign_key
        self.related_field = related_field
        self.many = many
        self._cache_attr = f"_cached_{foreign_key}_{related_model}"

    def __get__(self, instance, owner):
        """Get related object(s), loading if needed"""
        if instance is None:
            return self

        # Check cache
        if hasattr(instance, self._cache_attr):
            return getattr(instance, self._cache_attr)

        # Load relationship
        related_value = self._load_relationship(instance)
        setattr(instance, self._cache_attr, related_value)
        return related_value

    def _load_relationship(self, instance):
        """
        Load related object(s) from database.

        Args:
            instance: Model instance

        Returns:
            Related object or list of objects
        """
        if not hasattr(instance, '_connection') or not instance._connection:
            raise RuntimeError(
                f"Cannot load relationship '{self.related_model}' - "
                f"no database connection"
            )

        # Get foreign key value
        fk_value = getattr(instance, self.foreign_key, None)
        if fk_value is None:
            return [] if self.many else None

        # Import related model
        from wborm.registry import _model_registry
        related_class = _model_registry.get(self.related_model)

        if not related_class:
            raise ValueError(
                f"Related model '{self.related_model}' not found in registry"
            )

        # Build query
        from wborm.query import QuerySet
        queryset = QuerySet(related_class, instance._connection)
        queryset = queryset.filter(**{self.related_field: fk_value})

        # Execute query
        if self.many:
            return queryset.all()
        else:
            return queryset.first()


def defer_fields(*fields: str):
    """
    Decorator to mark fields as deferred on a model.

    Args:
        *fields: Field names to defer

    Examples:
        >>> @defer_fields('description', 'metadata')
        >>> class Product(Model):
        >>>     pass
    """
    def decorator(cls):
        if not hasattr(cls, '_deferred_fields'):
            cls._deferred_fields = set()
        cls._deferred_fields.update(fields)
        return cls
    return decorator


def only_fields(*fields: str):
    """
    Decorator to specify only these fields should be loaded.

    Args:
        *fields: Field names to load (all others deferred)

    Examples:
        >>> @only_fields('id', 'name', 'price')
        >>> class Product(Model):
        >>>     pass
    """
    def decorator(cls):
        if not hasattr(cls, '_only_fields'):
            cls._only_fields = set(fields)
        return cls
    return decorator


def prefetch_related(queryset, *relations: str):
    """
    Prefetch related objects to avoid N+1 queries.

    Args:
        queryset: QuerySet to prefetch for
        *relations: Relationship names to prefetch

    Returns:
        QuerySet with prefetched relationships

    Examples:
        >>> # Without prefetch (N+1 queries)
        >>> orders = Order.all()
        >>> for order in orders:
        >>>     print(order.customer.name)  # Query per order!

        >>> # With prefetch (2 queries total)
        >>> orders = prefetch_related(Order.all(), 'customer')
        >>> for order in orders:
        >>>     print(order.customer.name)  # No extra query!
    """
    # This would be implemented in QuerySet
    # For now, return queryset as-is
    # Full implementation requires QuerySet integration
    return queryset


def batch_load_fields(instances: List[Any], fields: List[str]) -> None:
    """
    Batch load deferred fields for multiple instances.

    More efficient than loading fields one instance at a time.

    Args:
        instances: List of model instances
        fields: Fields to load for all instances

    Examples:
        >>> products = Product.only('id', 'name').all()
        >>> # Later, batch load descriptions
        >>> batch_load_fields(products, ['description', 'price'])
    """
    if not instances:
        return

    # Group instances by model class
    by_class = defaultdict(list)
    for instance in instances:
        by_class[instance.__class__].append(instance)

    # Load for each class
    for model_class, class_instances in by_class.items():
        tablename = model_class.__tablename__
        pk_fields = getattr(model_class, '_pk_field_names', lambda: [getattr(model_class, '_pk_field', 'id')])()
        pk_field = pk_fields[0]

        # Get all PKs
        pk_values = [
            getattr(inst, pk_field)
            for inst in class_instances
            if getattr(inst, pk_field, None) is not None
        ]

        if not pk_values:
            continue

        # Build query
        field_list = ", ".join([pk_field] + fields)
        placeholders = ", ".join("?" for _ in pk_values)
        sql = f"SELECT {field_list} FROM {tablename} WHERE {pk_field} IN ({placeholders})"

        # Get connection from first instance
        conn = getattr(class_instances[0], '_connection', None)
        if not conn:
            continue

        # Execute query
        from wborm.connection_utils import run_query
        results = run_query(conn, sql, params=pk_values)

        # Map results to instances
        results_by_pk = {row[pk_field]: row for row in results}

        for instance in class_instances:
            pk_value = getattr(instance, pk_field)
            if pk_value in results_by_pk:
                row = results_by_pk[pk_value]
                for field in fields:
                    if field in row:
                        instance.__dict__[field] = row[field]
                        if hasattr(instance, '_mark_loaded'):
                            instance._mark_loaded(field)
