import sys
import os
from wborm.fields import Field
from wborm.core import Model
from wborm.introspect import introspect_table, get_foreign_keys
from wborm.model_cache import try_load_model_from_disk, save_model_to_disk
from wborm.stub_generator import generate_model_stub
from wborm.type_mapper import map_coltype_to_python
from wborm.file_utils import CACHE_DIR, list_cached_models
from wborm.registry import _model_registry, _model_cache
from wborm.connection_utils import execute_sql


def get_global_connection():
    """
    Retorna a conexão global registrada.

    Forma de uso:
    -------------
    conn = get_global_connection()

    Retorna:
    --------
    Connection : Conexão registrada com register_global_connection()

    Exceções:
    ---------
    RuntimeError: Se nenhuma conexão global foi registrada

    Exemplo:
    --------
    from wborm import register_global_connection, get_global_connection

    # Registrar uma vez
    register_global_connection(conn)

    # Acessar em qualquer lugar
    conn = get_global_connection()
    """
    from wborm.registry import _connection
    if _connection is None:
        raise RuntimeError(
            "Nenhuma conexão global registrada.\n"
            "Use: register_global_connection(conn) primeiro."
        )
    return _connection


def generate_model(table_name, conn=None, refresh=False, inject_globals=True, target_globals=None):
    """
        Gera dinamicamente uma classe de modelo Python com base na estrutura de uma tabela do banco de dados.

        Forma de uso:
        -------------
        # Com conexão explícita
        generate_model("clientes", conn)

        # Com conexão global (mais conveniente)
        register_global_connection(conn)  # fazer uma vez
        generate_model("clientes")  # usar em qualquer lugar

        Parâmetros:
        ------------
        table_name : str
            Nome da tabela a ser introspectada e transformada em modelo.
        conn : object, opcional
            Conexão ativa com o banco de dados. Se não fornecida, usa a conexão global
            registrada com `register_global_connection()`.
            (padrão: None - usa conexão global)
        refresh : bool, opcional
            Se True, força a introspecção da tabela mesmo se existir cache ou modelo salvo em disco.
            (padrão: False)
        inject_globals : bool, opcional
            Se True, injeta a classe gerada no escopo global para uso imediato.
            (padrão: True)
        target_globals : dict, opcional
            Escopo alternativo para injeção, se não quiser injetar no `globals()` padrão.

        Comportamento:
        --------------
        - Se `conn` não for fornecido, busca a conexão global do registry.
        - Se o modelo já existir no cache, apenas reutiliza.
        - Se houver modelo salvo no disco, carrega para evitar reintrospecção.
        - Se não existir, introspecta a estrutura da tabela e gera dinamicamente:
            - Campos normais (`Field`) para cada coluna.
            - Relações automáticas baseadas nas Foreign Keys.
        - Injeta a classe e aliases t1–t10 no escopo se `inject_globals=True`.
        - Gera também o arquivo de stubs (.pyi) para suporte a autocomplete.

        Exemplo de uso rápido:
        ----------------------
        # Método 1: Conexão explícita (tradicional)
        Cliente = generate_model("clientes", conn)

        # Método 2: Conexão global (recomendado)
        from wborm import register_global_connection, generate_model
        register_global_connection(conn)
        Cliente = generate_model("clientes")
        Pedido = generate_model("pedidos")

        clientes = Cliente.filter(status="ATIVO").all()

        Observações:
        ------------
        - Cria propriedades automáticas para relações de Foreign Keys (FKs e reversas).
        - Se ocorrer erro ao ler FKs, prossegue apenas com os campos normais.
        - Chama `save_model_to_disk()` para persistir o modelo localmente.
        - Atualiza o registro `_model_registry` para permitir joins automáticos.

        Exceções:
        ---------
        RuntimeError: Se `conn` não for fornecido e não houver conexão global registrada.
        """
    import sys
    import inspect

    # Se conn não foi fornecido, usa a conexão global
    if conn is None:
        from wborm.registry import _connection
        if _connection is None:
            raise RuntimeError(
                "Nenhuma conexão fornecida e nenhuma conexão global registrada.\n"
                "Use: register_global_connection(conn) ou passe conn explicitamente."
            )
        conn = _connection

    key = (table_name, id(conn))

    if not refresh and key in _model_cache:
        model = _model_cache[key]
        if inject_globals:
            var_name = table_name
            (target_globals or inspect.stack()[1].frame.f_globals)[var_name] = model
        return model

    if not refresh:
        model = try_load_model_from_disk(table_name, conn)
        if model:
            _model_cache[key] = model
            if inject_globals:
                var_name = table_name
                (target_globals or inspect.stack()[1].frame.f_globals)[var_name] = model
            return model

    metadata = introspect_table(table_name, conn)
    class_attrs = {"__tablename__": table_name, "_relation_configs": {}}

    for col in metadata:
        py_type = map_coltype_to_python(col["type"])
        is_pk = str(col["name"]).lower() == "id" or bool(col.get("primary_key"))
        raw_length = col.get("length")
        max_length = None
        if py_type is str and raw_length:
            try:
                max_length = int(raw_length)
            except (TypeError, ValueError):
                max_length = None
        class_attrs[str(col["name"])] = Field(
            py_type,
            primary_key=is_pk,
            column_name=str(col["name"]),
            max_length=max_length,
        )

    class_name = table_name.capitalize()
    class_attrs["__module__"] = "wborm.core"
    model_class = type(class_name, (Model,), class_attrs)
    model_class._connection = conn

    # Detect and set database dialect
    from wborm.dialects import detect_dialect
    model_class._dialect = detect_dialect(conn)

    sys.modules["wborm.core"].__dict__[class_name] = model_class

    try:
        fks = get_foreign_keys(table_name, conn)
        for fk in fks:
            from_tbl = fk["from_table"]
            to_tbl = fk["to_table"]
            from_col = fk["from_column"]
            to_col = fk["to_column"]

            if from_tbl == table_name:
                rel_name = from_col.replace("_id", "")
                def relation_getter(self, t=to_tbl, fk_col=from_col, pk_col=to_col, relation_name=rel_name):
                    if relation_name in self.__dict__:
                        return self.__dict__[relation_name]
                    Target = generate_model(t, conn, target_globals=target_globals)
                    return Target.filter(**{pk_col: getattr(self, fk_col)}).first()
                setattr(model_class, rel_name, property(relation_getter))
                model_class._relations[rel_name] = to_tbl
                model_class._relation_configs[rel_name] = {
                    "kind": "belongs_to",
                    "model": to_tbl,
                    "local_key": from_col,
                    "remote_key": to_col,
                }

            if to_tbl == table_name:
                reverse_name = from_tbl.lower() + "s"
                def reverse_getter(self, t=from_tbl, fk_col=from_col, pk_col=to_col, relation_name=reverse_name):
                    if relation_name in self.__dict__:
                        return self.__dict__[relation_name]
                    Source = generate_model(t, conn, target_globals=target_globals)
                    return Source.filter(**{fk_col: getattr(self, pk_col)}).all()
                setattr(model_class, reverse_name, property(reverse_getter))
                model_class._relations[reverse_name] = from_tbl
                model_class._relation_configs[reverse_name] = {
                    "kind": "has_many",
                    "model": from_tbl,
                    "local_key": to_col,
                    "remote_key": from_col,
                }
    except Exception as e:
        print(f"     ⚠️ Ignorando FKs para '{table_name}': {e}")

    _model_cache[key] = model_class
    save_model_to_disk(table_name, model_class)

    model_class._from_cache = False

    if inject_globals:
        target = target_globals or inspect.stack()[1].frame.f_globals
        var_name = table_name
        target[var_name] = model_class

        # injeta aliases t1-t10 também
        for i in range(1, 11):
            alias_name = f"t{i}"
            if alias_name not in target:
                from wborm.query import _Alias
                target[alias_name] = _Alias(alias_name)

    _model_registry[table_name] = model_class
    generate_model_stub()

    @classmethod
    def objects(cls, conn):
        from wborm.query import QuerySet
        return QuerySet(cls, conn)

    model_class.objects = objects

    if not getattr(model_class, "_fields", None):
        model_class._fields = [col["name"] for col in metadata] if metadata else []

    return model_class

def get_model(table_name, conn=None):
    """
    Retorna a classe de modelo associada à tabela especificada.

    Forma de uso:
    -------------
    # Com conexão explícita
    Cliente = get_model("clientes", conn)

    # Com conexão global
    register_global_connection(conn)
    Cliente = get_model("clientes")

    Parâmetros:
    -----------
    table_name : str
        Nome da tabela
    conn : object, opcional
        Conexão com o banco. Se não fornecida, usa a conexão global.

    Comportamento:
    --------------
    - Se o modelo já existir no cache ou salvo em disco, reutiliza.
    - Caso contrário, gera dinamicamente usando `generate_model`.

    Observações:
    ------------
    - É um atalho para `generate_model(table_name, conn)`.
    """
    return generate_model(table_name, conn)

def generate_all_models(conn=None, include_views=False, inject_globals=True, target_globals=None, verbose=True):
    """
    Gera modelos para todas as tabelas do banco de dados.

    Forma de uso:
    -------------
    # Com conexão explícita
    models = generate_all_models(conn)

    # Com conexão global
    register_global_connection(conn)
    models = generate_all_models()

    Parâmetros:
    -----------
    conn : object, opcional
        Conexão com o banco. Se não fornecida, usa a conexão global.
    include_views : bool, opcional
        Se True, inclui views além de tabelas (padrão: False)
    inject_globals : bool, opcional
        Se True, injeta modelos no escopo global (padrão: True)
    target_globals : dict, opcional
        Escopo alternativo para injeção
    verbose : bool, opcional
        Se True, exibe barra de progresso (padrão: True)

    Retorna:
    --------
    dict : Dicionário {table_name: ModelClass}

    Comportamento:
    --------------
    - Lista todas as tabelas do banco (systables para Informix)
    - Gera modelo para cada tabela encontrada
    - Exibe barra de progresso se verbose=True
    - Registra modelos no _model_registry
    - Gera arquivo de stubs para autocomplete

    Observações:
    ------------
    - Pula tabelas do sistema (tabid <= 99 no Informix)
    - Continua mesmo se falhar em alguma tabela
    - Útil para carregar todo o esquema do banco de uma vez
    """
    from wborm.utils import generate_model
    from wborm.stub_generator import generate_model_stub
    from wborm.registry import _model_registry
    import traceback

    try:
        from tqdm import tqdm  # barra de progresso
    except ImportError:
        tqdm = None

    # Se conn não foi fornecido, usa a conexão global
    if conn is None:
        from wborm.registry import _connection
        if _connection is None:
            raise RuntimeError(
                "Nenhuma conexão fornecida e nenhuma conexão global registrada.\n"
                "Use: register_global_connection(conn) ou passe conn explicitamente."
            )
        conn = _connection

    if target_globals is None:
        target_globals = globals()

    tipo = "'T'" if not include_views else "'T','V'"
    query = f"SELECT TRIM(tabname) AS tabname FROM systables WHERE tabtype IN ({tipo}) AND tabid > 99"
    results = conn.execute_query(query)

    total = len(results)
    if verbose:
        print(f"\n🔄 Gerando modelos para {total} tabelas...\n")

    models = {}
    progress_bar = tqdm(results, desc="📦 Gerando modelos", unit="tabela", ncols=100) if (verbose and tqdm) else results

    for row in progress_bar:
        table = str(row["tabname"])
        if verbose and tqdm:
            progress_bar.set_postfix_str(table)

        try:
            model = generate_model(
                table,
                conn,
                inject_globals=inject_globals,
                target_globals=target_globals,
            )
            models[table] = model
        except Exception as e:
            if verbose and tqdm:
                progress_bar.write(f"  ⚠️ Erro ao gerar modelo para '{table}': {e}")
            else:
                print(f"  ⚠️ Erro ao gerar modelo para '{table}': {e}")

    _model_registry.update(models)
    generate_model_stub()

    if verbose:
        print(f"\n✅ Modelos gerados com sucesso: {len(models)} de {total} possíveis.\n")

    return models


def list_models(conn=None):
    """
        Lista os modelos disponíveis, tanto do banco quanto do cache local.

        Forma de uso:
        -------------
        # Para listar modelos diretamente do banco:
        list_models(conn)

        # Para listar modelos salvos no cache (.wbmodels):
        list_models()

        Comportamento:
        --------------
        - Se `conn` for informado, chama `generate_all_models` e carrega do banco de dados.
        - Se `conn` não for informado, lê o diretório `.wbmodels` para listar os modelos em cache.

        Observações:
        ------------
        - Exibe mensagens de aviso se não encontrar modelos.
        - Mostra o número total de modelos encontrados.
        - Em caso de erro ao ler o cache criptografado, o erro é exibido mas a execução continua.
        """
    if conn:
        models = generate_all_models(conn, inject_globals=True, verbose=True)
        if not models:
            print("⚠ Nenhum modelo encontrado no banco.")
            return

        print(f"\n📡 Modelos carregados do servidor ({len(models)}):\n")
        for name in sorted(models):
            print(f" - {name}")
    else:
        if not os.path.isdir(CACHE_DIR):
            print("⚠ Diretório de modelos não encontrado.")
            return

        models = list_cached_models()

        if not models:
            print("⚠ Nenhum modelo válido no cache.")
        else:
            print(f"\n📦 Modelos encontrados em cache ({len(models)}):\n")
            for name in models:
                print(f" - {name}")

def get_model_by_name(name):
    """
        Recupera um modelo previamente carregado pelo nome.

        Forma de uso:
        -------------
        Cliente = get_model_by_name("clientes")

        Comportamento:
        --------------
        - Busca o modelo no `_model_registry` interno.
        - Se o modelo não estiver registrado, gera erro sugerindo usar `generate_all_models(conn)`.

        Observações:
        ------------
        - O nome informado deve ser igual ao nome da tabela (sensível a maiúsculas/minúsculas).
        - É necessário ter executado `generate_model` ou `generate_all_models` antes para popular o registro.
        """
    model = _model_registry.get(name)
    if not model:
        raise ValueError(f"Modelo '{name}' não encontrado. Use generate_all_models(conn) primeiro.")
    return model

def create_temp_table_from_queryset(queryset, temp_name, with_log=False):
    """
        Cria uma tabela temporária a partir de um queryset existente.

        Forma de uso:
        -------------
        pedidos_filtrados = Pedido.filter(status="ABERTO")
        temp_pedidos = create_temp_table_from_queryset(pedidos_filtrados, "temp_pedidos")

        Parâmetros:
        ------------
        queryset : QuerySet
            O queryset que define a consulta base para criar a tabela temporária.
        temp_name : str
            Nome da tabela temporária a ser criada.
        with_log : bool, opcional
            Define se a tabela será criada `WITH LOG` ou `WITH NO LOG`. (padrão: False)

        Gera comandos como:
        -------------------
        CREATE TEMP TABLE temp_pedidos AS (SELECT * FROM pedidos WHERE status = 'ABERTO') WITH NO LOG

        Observações:
        ------------
        - Após criar a tabela, gera dinamicamente o modelo associado usando `generate_model`.
        - Retorna o modelo pronto para consultas usando o novo temp table.
        - Útil para otimizar consultas complexas ou paginar grandes volumes de dados.
        """
    sql = queryset._build_query()
    log_clause = "WITH LOG" if with_log else "WITH NO LOG"
    create_sql = f"CREATE TEMP TABLE {temp_name} AS ({sql}) {log_clause}"

    # print(f"📦 Criando temp table: {create_sql}")
    execute_sql(queryset.conn, create_sql)

    from wborm.utils import generate_model
    return generate_model(temp_name, queryset.conn, inject_globals=True)
