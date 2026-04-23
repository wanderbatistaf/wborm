"""
Stub Generation Utilities

This module provides utilities for generating Python type stub files (.pyi)
to enable IDE autocompletion and type checking for dynamically generated models.

Extracted from model_cache.py to isolate stub generation logic.
"""

import os
import re
from typing import Dict, Any, Optional
from wborm.file_utils import STUB_FILE, ensure_stub_dir
from wborm.type_mapper import get_python_type_name


def generate_field_stub(field_name: str, field: Any) -> str:
    """
    Gera uma linha de stub para um campo.

    Args:
        field_name: str - Nome do campo
        field: Field - Objeto Field com metadados

    Returns:
        str: Linha de stub formatada

    Examples:
        >>> field = Field(int, nullable=True)
        >>> generate_field_stub("id", field)
        '    id: Optional[int]'
    """
    py_type = get_python_type_name(field.field_type)
    nullable = getattr(field, "nullable", True)

    if nullable:
        return f"    {field_name}: Optional[{py_type}]"
    else:
        return f"    {field_name}: {py_type}"


def generate_class_stub(model_name: str, fields: Dict[str, Any]) -> str:
    """
    Gera o stub completo de uma classe de modelo.

    Args:
        model_name: Nome da classe
        fields: Dicionário de campos {nome: Field}

    Returns:
        Stub completo da classe como string

    Examples:
        >>> fields = {"id": Field(int), "name": Field(str)}
        >>> stub = generate_class_stub("Cliente", fields)
        >>> "class Cliente(Model):" in stub
        True
    """
    lines = [f"class {model_name}(Model):"]

    if not fields:
        lines.append("    pass")
    else:
        for fname, field in fields.items():
            lines.append(generate_field_stub(fname, field))

    lines.append("")
    return "\n".join(lines)


def update_model_stub_file(path: str, model_name: str, fields: Dict[str, Any]) -> None:
    """
    Atualiza ou adiciona um modelo no arquivo de stubs de forma incremental.

    Args:
        path: str - Caminho do arquivo .pyi
        model_name: str - Nome da classe
        fields: dict - Dicionário de campos {nome: Field}

    Examples:
        >>> update_model_stub_file("models.pyi", "Cliente", {"id": Field(int)})
    """
    header = [
        "from wborm.core import Model",
        "from typing import Optional",
        "",
    ]

    new_block = generate_class_stub(model_name, fields)

    # Cria arquivo se não existir
    if not os.path.exists(path):
        ensure_stub_dir()
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(header + [new_block]))
        print(f"✅ Stub criado com {model_name}: {path}")
        return

    # Lê conteúdo existente
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Atualiza ou adiciona a classe
    class_pattern = rf"(class {model_name}\(Model\):\n(?:    .*\n)*?)\n"
    if re.search(class_pattern, content):
        updated = re.sub(class_pattern, f"{new_block}\n", content, flags=re.MULTILINE)
    else:
        updated = content.rstrip() + "\n\n" + new_block + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"✅ Stub atualizado: {model_name} → {path}")


def generate_model_stub(output_path: Optional[str] = None) -> None:
    """
    Gera arquivo de stubs completo para todos os modelos no registry.

    Args:
        output_path: Caminho customizado para o arquivo .pyi (opcional)

    Examples:
        >>> generate_model_stub()
        >>> # Gera models.pyi com todos os modelos
        >>> generate_model_stub("custom_models.pyi")
        >>> # Gera custom_models.pyi com todos os modelos
    """
    from wborm.core import Model
    from wborm.registry import _model_registry

    if output_path is None:
        output_path = STUB_FILE

    if not _model_registry:
        print("⚠ Nenhum modelo carregado.")
        return

    lines = [
        "from wborm.core import Model",
        "from typing import Optional",
        "",
    ]

    for name, model_cls in sorted(_model_registry.items()):
        if not issubclass(model_cls, Model):
            continue

        fields = getattr(model_cls, "_fields", {})
        lines.append(generate_class_stub(model_cls.__name__, fields))

    ensure_stub_dir()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # print(f"✅ Stub completo gerado: {output_path}")


def generate_type_aliases_stub(path: str = "globals.pyi") -> None:
    """
    Gera arquivo de stubs com aliases de tipos para variáveis globais.

    Args:
        path: Caminho para o arquivo de aliases (padrão: "globals.pyi")

    Examples:
        >>> generate_type_aliases_stub()
        >>> # Gera globals.pyi com aliases de modelos
        >>> generate_type_aliases_stub("my_aliases.pyi")
        >>> # Gera my_aliases.pyi com aliases
    """
    from wborm.registry import _model_registry

    lines = [
        "from models import *",
        "",
    ]

    for name, model_cls in sorted(_model_registry.items()):
        class_name = model_cls.__name__
        lines.append(f"{name}: {class_name}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # print(f"✅ Aliases gerados para type-checking: {path}")
