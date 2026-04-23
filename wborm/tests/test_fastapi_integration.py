from wborm.fastapi import create_session_dependency, session_scope


class DummyConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))


def test_session_dependency_commits():
    conn = DummyConnection()
    dep = create_session_dependency(conn, auto_commit=True)
    gen = dep()
    session = next(gen)
    assert session.connection is conn
    session.begin()
    try:
        next(gen)
    except StopIteration:
        pass
    assert ("COMMIT WORK", None) in conn.calls


def test_session_dependency_default_does_not_commit():
    conn = DummyConnection()
    dep = create_session_dependency(conn)
    gen = dep()
    next(gen)
    try:
        next(gen)
    except StopIteration:
        pass
    assert ("COMMIT WORK", None) not in conn.calls


def test_session_scope_rolls_back_on_error():
    conn = DummyConnection()
    try:
        with session_scope(conn):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert ("ROLLBACK WORK", None) in conn.calls
