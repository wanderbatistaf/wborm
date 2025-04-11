## 📝 **Changelog – New Modules and Features**

---
### 📚 `registry.py` – **Global Model and Cache Registry**

#### 🗂️ Global Structure
- `_model_registry`: stores all generated `Model` classes available for autocomplete and reuse.
- `_model_cache`: maps models by `(table_name, conn_id)` to avoid redundant recreation.
- `_query_result_cache`: in-memory cache for query results with TTL, used in `QuerySet`.

> This module provides the foundation for features like:
> - Query result caching (with `live()` to bypass).
> - Automatic model reloads.
> - Stub generation based on dynamically loaded models.

---

### 📦 `model_cache.py` – **Persistent Model Caching on Disk**

#### 🔐 Encryption and Storage
- Implements encrypted model caching in `.wbmodels/` using a Fernet key saved in `.wbormkey`.
- Models are serialized with `pickle`, encrypted, and saved with `.wbm` extension.

#### 📤 Key Functions

- `save_model_to_disk(table_name, model_cls)`
  - Saves a model class as a dictionary of serializable attributes (fields and relations).
- `try_load_model_from_disk(table_name, conn)`
  - Attempts to load a previously saved model, rebuilds the class using `ModelMeta`, and registers it.
- `generate_model_stub(output_path)`
  - Automatically generates a `.pyi` stub file for autocomplete support in editors.

#### 🔑 Security
- Uses `cryptography.fernet.Fernet` to ensure secure caching, even if files are exposed.

---

### 🧠 `expressions.py` – **Custom SQL Expressions**

#### 📐 Declarative Expressions
- **`Expression` class** allows for clean, safe SQL expressions:
  - Supported operators: `==`, `!=`, `>`, `<`, `>=`, `<=`.
  - Integrates with `datetime` values using automatic conversion.

#### 🔧 Utility Functions for Queries

- `col(name)` – builds a column-based expression.
- `date(field)` – wraps a field with Informix's `DATE(...)`.
- `now()` – returns the `CURRENT` SQL keyword.
- `raw(expr)` – inserts raw SQL directly.
- `format_informix_datetime(value)` – converts `datetime` or `str` to `DATETIME(...) YEAR TO SECOND`, supporting ISO8601 or fallback to raw strings.

> These functions are available directly via the main package `__init__.py`:
```python
from wborm import col, now, raw
```

---

## 📝 **`utils.py`**

### 🚀 **New Features**

- **Local model caching**
  - Automatically checks for cached models using `try_load_model_from_disk()` before regenerating.
  - Generated models are saved using `save_model_to_disk()` for future reuse.

- **Global scope injection**
  - Adds `inject_globals=True` to assign models to global variables by table name.

- **Autocomplete stub**
  - Introduces `generate_model_stub()` to generate `.pyi` files post-generation for editor autocomplete.

- **Model listing**
  - Adds `list_models()` to:
    - List all models loaded from the database (if connected).
    - List cached models from `.wbmodels/` if not connected, with decryption via `cryptography.fernet`.

- **Batch model generation**
  - Adds `generate_all_models(conn)` to introspect all tables (and optionally views) with verbosity control and global injection.

- **Secure model access by name**
  - Adds `get_model_by_name(name)` for direct access from `_model_registry`.

- **Create temp tables from queryset**
  - Adds `create_temp_table_from_queryset(...)` to generate `TEMP TABLE`s from ORM queries.

---

### 🔧 **Improvements**

- **FK exception handling**
  - Uses `try/except` to gracefully handle foreign key reading errors with warnings.

- **Explicit model module**
  - Sets `__module__` of models to `"wborm.core"` for accurate tracking and autocomplete support.

- **Global model registry**
  - Adds `_model_registry` usage in addition to `_model_cache` for name-based lookups.

- **Improved name mapping**
  - Ensures field and variable names are treated as `str(col["name"])` to avoid inconsistencies.

- **Import separation**
  - Clearer organization of external vs. internal imports.

---

### 🗑️ **Removals**

- Nothing was removed. The update maintains **full backward compatibility** while expanding capabilities.

---

### ⚠️ **Technical Notes**

- Local caching requires:
  - Access to the encryption key (`get_or_create_key()`).
  - Proper permissions for `.wbmodels/`.
- FK introspection may silently fail for robustness, but can hide subtle bugs if not logged.

---

## 📝 **`introspect.py`**

### 🚀 **Robust Improvements to `get_foreign_keys()`**

#### 🔍 **Index-Based FK Analysis**
- Now uses `sysindexes` to correctly identify FK and PK columns.
- Supports up to **16 index columns** (`part1` to `part16`), allowing composite key detection.

#### 🧠 **Semantic Accuracy Fixes**
- Replaces `r.tabid = fk.tabid` join with `c.tabid = fk.tabid` for precision.
- Adds `idx_fk.part1 IS NOT NULL AND idx_pk.part1 IS NOT NULL` filter to exclude corrupted/incomplete entries.

#### 🧹 **`COALESCE` usage**
- Applies `COALESCE(..., '')` to avoid null comparison failures.

---

### 🛠️ **Other Technical Adjustments**

- Improved SQL indentation.
- Retains aliases `fk`, `pk`, `fc`, `pc` with improved index-based joins.
- Query structure refactored for long-term maintainability and Informix-style consistency.

---

### ✅ **No Changes to `introspect_table()`**
- The `introspect_table(...)` function remains unchanged.
  - No impact on existing usage.
  - Same introspection logic.

---

## 📝 **`query.py`**

### 🚀 **New Features**

#### 🧠 **Query Result Caching**
- Adds in-memory query result cache (`_query_result_cache`) with TTL (default `60s`).
- Introduces `live()` to disable cache per-query.
- Reuses cached results in `all()` if valid.

#### 🧾 **Advanced `ResultSet` Class**
- New `ResultSet` inherits from `list` and adds:
  - `show(tablefmt="grid")`: tabulated result display with green (live) or blue (cache) borders.
  - Dynamic column detection or from `select(...)`.
  - Auto-removal of fully empty columns.

#### 📊 **`pivot(...)` Function**
- Transforms results into a **pivot table** with indexes, columns, and values.
- Uses `tabulate`, colored output, and optimized layout.

#### 🧪 **`show(...)` in `QuerySet`**
- Shortcut to `all().show(...)`, allowing customizable table format.

#### 🧩 **Subquery Join Support**
- `join()` now accepts `QuerySet` instances named with `.as_temp_table(alias)` for subquery joins.

#### 🧪 **Chained Temp Table Creation**
- `create_temp_table(...)` creates a temporary table from the current query and returns its model.

---

### 🔧 **Enhancements**

- **More flexible `filter(...)`**
  - Accepts string expressions (`filter("age > 30")`) and `ColumnExpr`, plus safe `key=value` filtering.

- **Flexible `join(...)` ON clause**
  - Supports:
    - Lists/tuples of columns → `a.col = b.col`
    - Single column (assumes equality)
    - Full custom SQL conditions

- **Explicit instance creation**
  - `_create_instance_from_row(...)` uses fallback to `__dict__` if not in `_fields`.

- **`select(...)` now influences `ResultSet` rendering**
  - Column order and names reflect select fields.

- **Safe escaping in `count()`**
  - Escapes filter values to prevent SQL injection.

---

### 🗑️ **Removals / Deprecated Items**

- `preload(...)` has been **removed** – needs reimplementation if required.
- Heuristic FK logic in `preload(...)` is deprecated.
- `all()` now returns `ResultSet`, not a simple list.

---

### 🎨 **UX and Visual Enhancements**

- Uses `colorama` for terminal border coloring (green: live, blue: cached).
- `tabulate` formatting for CLI clarity.

---

### ⚙️ **Internals and Techniques**

- Adds `sha256`-based query hash keying for caching.
- Subquery joins require `.as_temp_table_alias` set.
- Fully compatible with updated `generate_model()` for temp tables.

---

## 📝 **`core.py`**

### 🚀 **New Features**

#### 🧬 Dynamic `QuerySet` Method Access
- **Via `__getattr__` in `ModelMeta` metaclass**:
  - Allows direct model access to `QuerySet` methods (e.g. `User.limit(10).show()`).
  - Examples: `Model.join(...)`, `Model.pivot(...)` without manual binding.

#### 📦 Temporary Table Creation
- New `create_temp_table()` method (both instance and class level):
  - Builds SQL from model fields.
  - Executes `CREATE TEMP TABLE ...` with visual logging.
  - Supports intermediate joins or data snapshots.

#### 📊 Enhanced Visualization: `Model.show(...)`
- Uses `tabulate` to show up to 50 records (default).
- Colors borders based on model source:
  - 🔵 Blue: cached
  - 🟢 Green: live/dynamic

#### 🔁 Pivot via `Model.pivot(...)`
- Supports pivoting at model level with filters and `aggfunc="count"` by default.

#### 🔍 Relationship Overview: `Model.describe_relations()`
- Displays mapped relations with destination table names.

---

### 🔧 Major Improvements

- **Field introspection in `ModelMeta`**
  - Uses `str(k)` for key safety and compatibility.

- **Better `to_dict()` handling**
  - Skips private/method attributes.

- **Improved SQL generation for tables**
  - Cleaner `NOT NULL` / `PRIMARY KEY` clause generation with `.strip()`.

---

### 🗑️ Removals / Deprecated

- 📤 Removed instance-level `show()`
  - Replaced with more versatile class-level version.

- 📦 `preload()` still referenced but likely obsolete (depends on removed QuerySet method).
  - May be removed in future releases.

---

### 🎨 UI/UX Enhancements

- More readable output using `colorama` for relation mapping and table generation.
- Informative messages on creation/deletion/updates.

---

### 🛠️ Structural Notes

- `lazy_property` remains unchanged.
- `validate()` is still required before persisting with `add`, `bulk_add`, etc.

---

## 📝 **`__init__.py`**

### 🚀 **New Public Exports**

New helpers have been added to the public API for expressive, direct SQL construction:

#### 📐 SQL Expression Utilities
- **`col`** – Column-based expression builder (e.g., `col("age") > 18`).
- **`date`** – Converts or wraps a value as a date.
- **`now`** – SQL `CURRENT` timestamp.
- **`raw`** – Direct SQL insertion.
- **`format_informix_datetime`** – Formats values for Informix's `DATETIME ... YEAR TO SECOND`.

> Provided by the `expressions.py` module, now part of the main package.

---

### 🧭 **Explicit `__all__` Export**

- Adds `__all__ = [...]` to define what gets imported via `from wborm import *`.
  - Improves code clarity.
  - Controls public API surface.
  - Aids IDEs and documentation tools.

---

### ✅ **Backward Compatibility Maintained**

- All previously available elements (`Model`, `Field`, `generate_model`, `get_model`, `QuerySet`) are still fully supported.
