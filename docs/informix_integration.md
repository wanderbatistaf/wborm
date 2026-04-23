# Informix Integration Check

Este projeto ja tem um script de verificacao ponta a ponta em `examples/informix_integration_check.py`.

## Container atual

Os parâmetros detectados no container `fgl-informix` foram:

- host: `localhost`
- port: `9088`
- database: `stores_demo`
- user: `informix`
- password: `in4mix`
- server: `informix`

## Como executar

Use Python `3.12` ou `3.13` com `wbjdbc` instalado:

```bash
python examples/informix_integration_check.py
```

Se quiser sobrescrever os parâmetros:

```bash
set WBORM_IFX_HOST=localhost
set WBORM_IFX_PORT=9088
set WBORM_IFX_DB=stores_demo
set WBORM_IFX_USER=informix
set WBORM_IFX_PASS=in4mix
set WBORM_IFX_SERVER=informix
python examples/informix_integration_check.py
```

## O que o script valida

- conexão via `connect_optimized(...)`
- migração por abstração do ORM com `CreateTableMigration.from_model(...)`
- introspecção com `generate_model(...)`
- `bulk_add()` / `bulk_delete()`
- query builder com operadores
- locking pessimista com `lock_for_update()`
