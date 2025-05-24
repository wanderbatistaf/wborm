__version__ = "0.3.1"

from .core import Model
from .fields import Field
from .utils import generate_model, get_model
from .model_cache import generate_model_stub, try_load_model_from_disk
from .query import QuerySet
from .expressions import col, date, now, raw, format_informix_datetime
from .bootstrap import auto_load_cached_models
from wborm.registry import _model_cache, _model_registry, _connection
from wborm.bootstrap import auto_load_cached_models
import inspect
from typing import TYPE_CHECKING
import sys, os


__all__ = [
    "Model",
    "Field",
    "generate_model",
    "get_model",
    "generate_model_stub",
    "QuerySet",
    "col",
    "date",
    "now",
    "raw",
    "format_informix_datetime",
    "register_global_connection",
]

# Este bloco é mágico
import builtins

_conn_holder = {}


def register_global_connection(conn):
    import wborm.registry
    wborm.registry._connection = conn
    _conn_holder["conn"] = conn  #  <- ESSENCIAL para o __getattr__ funcionar

    # injeta os modelos no escopo do caller (principal)
    globals_ref = inspect.stack()[1].frame.f_globals
    auto_load_cached_models(conn, target_globals=globals_ref)



def __getattr__(name):
    conn = _conn_holder.get("conn")
    if not conn:
        raise RuntimeError("Conexão global não registrada. Use `register_global_connection(conn)` primeiro.")

    from .utils import generate_model
    model = generate_model(name, conn, inject_globals=True)
    return model

if _connection:
    caller_globals = inspect.stack()[1].frame.f_globals
    auto_load_cached_models(_connection, target_globals=caller_globals)


wbmodels_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".wbmodels"))
if wbmodels_path not in sys.path:
    sys.path.insert(0, wbmodels_path)

if TYPE_CHECKING:
    from models import *
