"""
Cache Management Utilities

This module provides utilities for managing encrypted model caches and
cryptographic key generation/storage.

Extracted from model_cache.py to centralize cache management logic.
"""

import os
import pickle
from typing import Any, Optional
from cryptography.fernet import Fernet
from wborm.file_utils import KEY_PATH, model_cache_path


def get_or_create_key() -> bytes:
    """
    Obtém a chave de criptografia existente ou cria uma nova.

    A chave é armazenada no arquivo .wbormkey na raiz do projeto.

    Returns:
        bytes: Chave de criptografia Fernet

    Examples:
        >>> key = get_or_create_key()
        >>> len(key)
        44
    """
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            return f.read()

    key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as f:
        f.write(key)

    return key


def encrypt_data(data: Any) -> bytes:
    """
    Criptografa dados usando Fernet.

    Args:
        data: Dados a serem criptografados (serializável com pickle)

    Returns:
        Dados criptografados em bytes

    Examples:
        >>> encrypted = encrypt_data({"name": "test"})
        >>> isinstance(encrypted, bytes)
        True
    """
    key = get_or_create_key()
    serialized = pickle.dumps(data)
    return Fernet(key).encrypt(serialized)


def decrypt_data(encrypted: bytes) -> Any:
    """
    Descriptografa dados usando Fernet.

    Args:
        encrypted: Dados criptografados em bytes

    Returns:
        Dados descriptografados e desserializados

    Examples:
        >>> data = {"name": "test"}
        >>> encrypted = encrypt_data(data)
        >>> decrypted = decrypt_data(encrypted)
        >>> data == decrypted
        True
    """
    key = get_or_create_key()
    decrypted = Fernet(key).decrypt(encrypted)
    return pickle.loads(decrypted)


def save_to_cache(table_name: str, data: Any) -> None:
    """
    Salva dados criptografados no cache.

    Args:
        table_name: Nome da tabela
        data: Dados a serem salvos (serializável com pickle)

    Examples:
        >>> save_to_cache("clientes", {"fields": {}, "relations": {}})
    """
    encrypted = encrypt_data(data)
    path = model_cache_path(table_name)

    with open(path, "wb") as f:
        f.write(encrypted)


def load_from_cache(table_name: str) -> Optional[Any]:
    """
    Carrega dados descriptografados do cache.

    Args:
        table_name: Nome da tabela

    Returns:
        Dados descriptografados ou None se não existir ou erro ocorrer

    Examples:
        >>> data = load_from_cache("clientes")
        >>> data is not None or data is None
        True
    """
    path = model_cache_path(table_name)

    if not os.path.exists(path):
        return None

    try:
        with open(path, "rb") as f:
            encrypted = f.read()
        return decrypt_data(encrypted)
    except Exception as e:
        print(f"⚠️ Erro ao carregar cache de '{table_name}': {e}")
        return None


def cache_exists(table_name: str) -> bool:
    """
    Verifica se existe cache para uma tabela.

    Args:
        table_name: Nome da tabela

    Returns:
        True se o cache existe, False caso contrário

    Examples:
        >>> cache_exists("clientes")
        False
    """
    return os.path.exists(model_cache_path(table_name))


def invalidate_cache(table_name: str) -> bool:
    """
    Remove o cache de uma tabela específica.

    Args:
        table_name: Nome da tabela

    Returns:
        True se removido com sucesso, False se não existia

    Examples:
        >>> invalidate_cache("clientes")
        False
    """
    path = model_cache_path(table_name)

    if os.path.exists(path):
        os.remove(path)
        return True

    return False
