"""Session, transaction and unit-of-work support for WBORM."""

from contextlib import contextmanager
from wborm.connection_utils import begin_transaction, commit_transaction, rollback_transaction


class Session:
    def __init__(self, connection):
        self.connection = connection
        self.identity_map = {}
        self.new = set()
        self.dirty = set()
        self.deleted = set()
        self._in_transaction = False

    def query(self, model):
        return model._get_queryset(session=self)

    def add(self, instance):
        instance._session = self
        self.new.add(instance)
        self.deleted.discard(instance)
        for _, target in instance._cascade_targets("save-update"):
            if target is not None:
                self.add(target)
        return instance

    def attach(self, instance):
        instance._session = self
        key = instance.identity_key()
        if key:
            self.identity_map[key] = instance
        instance._state = "clean"
        instance._take_snapshot()
        return instance

    def delete(self, instance):
        instance._session = self
        self.new.discard(instance)
        self.dirty.discard(instance)
        self.deleted.add(instance)
        for _, target in instance._cascade_targets("delete"):
            if target is not None:
                self.delete(target)
        return instance

    def mark_dirty(self, instance):
        if instance not in self.new and instance not in self.deleted:
            self.dirty.add(instance)

    def get(self, model, pk_value):
        pk_name = tuple(model._pk_field_names())
        return self.identity_map.get((model, pk_name, pk_value))

    def merge(self, instance):
        key = instance.identity_key()
        if key and key in self.identity_map:
            managed = self.identity_map[key]
            for field_name in managed._fields:
                setattr(managed, field_name, getattr(instance, field_name, None))
            self.mark_dirty(managed)
            return managed
        return self.attach(instance)

    def refresh(self, instance, fields=None):
        pk_name = instance._pk_field_name()
        pk_value = instance._pk_value()
        if pk_name is None or pk_value is None:
            return instance
        fresh = instance.__class__._get_queryset(session=None).live().filter(**{pk_name: pk_value}).first()
        if not fresh:
            return instance
        selected = set(fields or instance._fields.keys())
        for field_name in selected:
            if field_name in instance._fields:
                object.__setattr__(instance, field_name, getattr(fresh, field_name, None))
                instance._expired_fields.discard(field_name)
        instance._take_snapshot()
        object.__setattr__(instance, "_state", "clean")
        self.attach(instance)
        return instance

    def expire(self, instance, fields=None):
        selected = set(fields or instance._fields.keys())
        instance._expired_fields.update(selected)
        return instance

    def expunge(self, instance):
        self.new.discard(instance)
        self.dirty.discard(instance)
        self.deleted.discard(instance)
        key = instance.identity_key()
        if key:
            self.identity_map.pop(key, None)
        instance._session = None
        return instance

    def register_loaded(self, instance):
        key = instance.identity_key()
        if key:
            cached = self.identity_map.get(key)
            if cached:
                return cached
            self.identity_map[key] = instance
        instance._session = self
        instance._state = "clean"
        instance._take_snapshot()
        return instance

    @contextmanager
    def transaction(self):
        self.begin()
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise

    def begin(self):
        if not self._in_transaction:
            begin_transaction(self.connection)
            self._in_transaction = True
        return self

    def flush(self):
        for instance in list(self.new):
            instance._insert_via_session(self)
            self.new.discard(instance)
            self.register_loaded(instance)

        for instance in list(self.dirty):
            instance._update_via_session(self)
            self.dirty.discard(instance)
            self.register_loaded(instance)

        for instance in list(self.deleted):
            instance._delete_via_session(self)
            self.deleted.discard(instance)
            key = instance.identity_key()
            if key:
                self.identity_map.pop(key, None)
            instance._state = "deleted"

    def commit(self):
        self.flush()
        if self._in_transaction:
            commit_transaction(self.connection)
            self._in_transaction = False
        return self

    def rollback(self):
        if self._in_transaction:
            rollback_transaction(self.connection)
            self._in_transaction = False
        for instance in list(self.dirty):
            for field_name, value in instance._original_values.items():
                object.__setattr__(instance, field_name, value)
            object.__setattr__(instance, "_state", "clean")
        for instance in list(self.deleted):
            object.__setattr__(instance, "_state", "clean")
        for instance in list(self.new):
            object.__setattr__(instance, "_state", "new")
        self.new.clear()
        self.dirty.clear()
        self.deleted.clear()
        return self
