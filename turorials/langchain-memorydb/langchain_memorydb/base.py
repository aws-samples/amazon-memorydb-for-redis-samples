"""Wrapper around Redis vector database."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional, Union

from langchain.schema.embeddings import Embeddings
from langchain.utilities.redis import get_client
from langchain.utils import get_from_dict_or_env
from langchain.vectorstores.redis.base import (
    Redis,
    RedisVectorStoreRetriever,
    check_index_exists,
)

logger = logging.getLogger(__name__)


class MemoryDB(Redis):
    """Amazon MemoryDB vector store"""

    def __init__(
        self,
        redis_url: str,
        index_name: str,
        embedding: Embeddings,
        index_schema: Optional[Union[Dict[str, str], str, os.PathLike]] = None,
        vector_schema: Optional[Dict[str, Union[str, int]]] = None,
        relevance_score_fn: Optional[Callable[[float], float]] = None,
        key_prefix: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize with necessary components."""
        self._check_deprecated_kwargs(kwargs)
        try:
            # TODO use importlib to check if redis is installed
            import redis  # noqa: F401

        except ImportError as e:
            raise ImportError(
                "Could not import redis python package. "
                "Please install it with `pip install redis`."
            ) from e

        self.index_name = index_name
        self._embeddings = embedding
        try:
            redis_client = get_client(redis_url=redis_url, **kwargs)
        except ValueError as e:
            raise ValueError(f"Redis failed to connect: {e}")

        self.client = redis_client
        self.relevance_score_fn = relevance_score_fn
        self._schema = self._get_schema_with_defaults(index_schema, vector_schema)
        self.key_prefix = key_prefix if key_prefix is not None else f"doc:{index_name}"

    @classmethod
    def from_existing_index(
        cls,
        embedding: Embeddings,
        index_name: str,
        schema: Union[Dict[str, str], str, os.PathLike],
        **kwargs: Any,
    ) -> Redis:
        """Connect to an existing MemoryDB index"""
        redis_url = get_from_dict_or_env(kwargs, "redis_url", "REDIS_URL")
        try:
            # We need to first remove redis_url from kwargs,
            # otherwise passing it to Redis will result in an error.
            if "redis_url" in kwargs:
                kwargs.pop("redis_url")
            client = get_client(redis_url=redis_url, **kwargs)
            # ensure that the index already exists
            assert check_index_exists(
                client, index_name
            ), f"Index {index_name} does not exist"
        except Exception as e:
            raise ValueError(f"Redis failed to connect: {e}")

        return cls(
            redis_url,
            index_name,
            embedding,
            index_schema=schema,
            **kwargs,
        )

    def as_retriever(self, **kwargs: Any) -> MemoryDBVectorStoreRetriever:
        tags = kwargs.pop("tags", None) or []
        tags.extend(self._get_retriever_tags())
        return MemoryDBVectorStoreRetriever(vectorstore=self, **kwargs, tags=tags)

    def _create_index_if_not_exist(self, dim: int = 1536) -> None:
        try:
            from redis.commands.search.indexDefinition import (  # type: ignore
                IndexDefinition,
                IndexType,
            )

        except ImportError:
            raise ImportError(
                "Could not import redis python package. "
                "Please install it with `pip install redis`."
            )

        class MemoryDBIndexDefinition(IndexDefinition):
            """A custom IndexDefinition that ignores index creation options not yet supported in MemoryDB"""

            def _append_score(self, score_field, score):
                return

            def _append_payload(self, payload_field):
                return

        # Set vector dimension
        # can't obtain beforehand because we don't
        # know which embedding model is being used.
        self._schema.content_vector.dims = dim

        # Check if index exists
        if not check_index_exists(self.client, self.index_name):
            # Create Redis Index
            fields = MemoryDBFieldOptionFilter.ignore_unsupported_field_options(
                self._schema.get_fields()
            )
            self.client.ft(self.index_name).create_index(
                fields=fields,
                definition=MemoryDBIndexDefinition(
                    prefix=[self.key_prefix], index_type=IndexType.HASH
                ),
            )


class MemoryDBVectorStoreRetriever(RedisVectorStoreRetriever):
    """Retriever for MemoryDB VectorStore"""

    vectorstore: Redis


class MemoryDBFieldOptionFilter:
    """A helper class to ignore field options not yet supported in MemoryDB"""

    def ignore_unsupported_field_options(fields):
        for f in fields:
            if "WEIGHT" in f.args:
                f.args = MemoryDBFieldOptionFilter._ignore_weight_in_field_args(f)
        return fields

    def _ignore_weight_in_field_args(field):
        result = []
        skip_weight_val = False
        for arg in field.args:
            if arg == "WEIGHT":
                skip_weight_val = True
                continue
            elif skip_weight_val:
                skip_weight_val = False
                continue
            else:
                result.append(arg)
        return result
