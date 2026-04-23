"""
File and Path Utilities

This module provides utilities for managing file paths and directories
used by WBORM for caching models and storing encryption keys.

Extracted from model_cache.py to centralize path management.
"""

import os
from typing import List


# Directory and file path constants
ROOT_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR: str = ".wbmodels"
KEY_PATH: str = ".wbormkey"
STUB_FILE: str = os.path.join(ROOT_DIR, "models.pyi")


def ensure_cache_dir() -> None:
    """
    Garante que o diretório de cache existe.

    Cria o diretório .wbmodels se ele não existir.

    Examples:
        >>> ensure_cache_dir()
        >>> os.path.isdir(CACHE_DIR)
        True
    """
    os.makedirs(CACHE_DIR, exist_ok=True)


def model_cache_path(table_name: str) -> str:
    """
    Retorna o caminho completo para o arquivo de cache de um modelo.

    Args:
        table_name: Nome da tabela

    Returns:
        Caminho completo para o arquivo .wbm

    Examples:
        >>> model_cache_path("clientes")
        '.wbmodels/clientes.wbm'
    """
    return os.path.join(CACHE_DIR, f"{table_name}.wbm")


def list_cached_models() -> List[str]:
    """
    Lista todos os modelos em cache no diretório .wbmodels.

    Returns:
        Lista ordenada de nomes de tabelas em cache

    Examples:
        >>> list_cached_models()
        ['clientes', 'pedidos', 'produtos']
    """
    if not os.path.isdir(CACHE_DIR):
        return []

    models: List[str] = []
    for file in os.listdir(CACHE_DIR):
        if file.endswith(".wbm"):
            models.append(file.replace(".wbm", ""))

    return sorted(models)


def clear_cache() -> int:
    """
    Remove todos os arquivos de cache (.wbm) do diretório .wbmodels.

    Returns:
        Número de arquivos removidos

    Examples:
        >>> count = clear_cache()
        >>> count >= 0
        True
    """
    if not os.path.isdir(CACHE_DIR):
        return 0

    count: int = 0
    for file in os.listdir(CACHE_DIR):
        if file.endswith(".wbm"):
            path = os.path.join(CACHE_DIR, file)
            os.remove(path)
            count += 1

    return count


def ensure_stub_dir() -> None:
    """
    Garante que o diretório para o arquivo de stubs existe.

    Cria o diretório pai do arquivo de stubs se necessário.

    Examples:
        >>> ensure_stub_dir()
        >>> os.path.isdir(os.path.dirname(STUB_FILE))
        True
    """
    os.makedirs(os.path.dirname(STUB_FILE), exist_ok=True)


# Initialize cache directory on import
ensure_cache_dir()
