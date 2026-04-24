from __future__ import annotations

from typing import Sequence
from uuid import uuid4


class VectorRanker:
    """Compute max-similarity scores for document vectors across one or more queries.

    Backends:
    - auto: try faiss, then chroma, then python fallback.
    - faiss: use faiss if available, else fallback.
    - chroma: use chroma if available, else fallback.
    - python/bruteforce: pure Python fallback only.
    """

    def __init__(self, *, backend: str = "auto") -> None:
        normalized = (backend or "auto").strip().lower()
        self.backend = normalized or "auto"

    def rank_max_similarity(
        self,
        *,
        query_vectors: Sequence[Sequence[float]],
        document_vectors: Sequence[Sequence[float]],
    ) -> list[float]:
        if not document_vectors:
            return []
        if not query_vectors:
            return [0.0 for _ in document_vectors]

        for backend_name in self._backend_order():
            if backend_name == "faiss":
                scores = self._rank_with_faiss(query_vectors=query_vectors, document_vectors=document_vectors)
            elif backend_name == "chroma":
                scores = self._rank_with_chroma(query_vectors=query_vectors, document_vectors=document_vectors)
            else:
                scores = self._rank_with_python(query_vectors=query_vectors, document_vectors=document_vectors)
            if scores is not None:
                return scores
        return self._rank_with_python(query_vectors=query_vectors, document_vectors=document_vectors)

    def _backend_order(self) -> list[str]:
        if self.backend in {"python", "bruteforce", "fallback"}:
            return ["python"]
        if self.backend == "faiss":
            return ["faiss", "python"]
        if self.backend == "chroma":
            return ["chroma", "python"]
        return ["faiss", "chroma", "python"]

    @staticmethod
    def _rank_with_python(
        *,
        query_vectors: Sequence[Sequence[float]],
        document_vectors: Sequence[Sequence[float]],
    ) -> list[float]:
        scores = [0.0 for _ in document_vectors]
        for doc_index, document_vector in enumerate(document_vectors):
            best = 0.0
            for query_vector in query_vectors:
                similarity = _dot_similarity(query_vector, document_vector)
                if similarity > best:
                    best = similarity
            scores[doc_index] = best
        return scores

    @staticmethod
    def _rank_with_faiss(
        *,
        query_vectors: Sequence[Sequence[float]],
        document_vectors: Sequence[Sequence[float]],
    ) -> list[float] | None:
        try:
            import faiss  # type: ignore[import-not-found]
            import numpy as np
        except Exception:
            return None

        dimension = _first_dimension(query_vectors)
        if dimension <= 0:
            return [0.0 for _ in document_vectors]

        filtered_queries = [vector for vector in query_vectors if len(vector) == dimension]
        if not filtered_queries:
            return [0.0 for _ in document_vectors]

        filtered_docs: list[list[float]] = []
        filtered_doc_indices: list[int] = []
        for index, vector in enumerate(document_vectors):
            if len(vector) != dimension:
                continue
            filtered_docs.append([float(item) for item in vector])
            filtered_doc_indices.append(index)
        if not filtered_docs:
            return [0.0 for _ in document_vectors]

        try:
            doc_matrix = np.asarray(filtered_docs, dtype="float32")
            query_matrix = np.asarray(filtered_queries, dtype="float32")
            index = faiss.IndexFlatIP(dimension)
            index.add(doc_matrix)
            distances, neighbors = index.search(query_matrix, len(filtered_docs))
        except Exception:
            return None

        scores = [0.0 for _ in document_vectors]
        for query_idx in range(len(filtered_queries)):
            for rank_idx in range(len(filtered_docs)):
                local_doc_idx = int(neighbors[query_idx][rank_idx])
                if local_doc_idx < 0:
                    continue
                global_doc_idx = filtered_doc_indices[local_doc_idx]
                score = float(distances[query_idx][rank_idx])
                if score > scores[global_doc_idx]:
                    scores[global_doc_idx] = score
        return scores

    @staticmethod
    def _rank_with_chroma(
        *,
        query_vectors: Sequence[Sequence[float]],
        document_vectors: Sequence[Sequence[float]],
    ) -> list[float] | None:
        try:
            import chromadb  # type: ignore[import-not-found]
        except Exception:
            return None

        dimension = _first_dimension(query_vectors)
        if dimension <= 0:
            return [0.0 for _ in document_vectors]
        filtered_queries = [vector for vector in query_vectors if len(vector) == dimension]
        if not filtered_queries:
            return [0.0 for _ in document_vectors]

        doc_ids: list[str] = []
        doc_vectors: list[list[float]] = []
        for index, vector in enumerate(document_vectors):
            if len(vector) != dimension:
                continue
            doc_ids.append(str(index))
            doc_vectors.append([float(item) for item in vector])
        if not doc_ids:
            return [0.0 for _ in document_vectors]

        collection_name = f"ranker_{uuid4().hex}"
        client = None
        try:
            if hasattr(chromadb, "EphemeralClient"):
                client = chromadb.EphemeralClient()
            else:
                client = chromadb.Client()
            collection = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
            collection.add(ids=doc_ids, embeddings=doc_vectors)
            result = collection.query(
                query_embeddings=[[float(item) for item in vector] for vector in filtered_queries],
                n_results=len(doc_ids),
                include=["ids", "distances"],
            )
        except Exception:
            return None
        finally:
            if client is not None:
                try:
                    client.delete_collection(name=collection_name)
                except Exception:
                    pass

        result_ids = result.get("ids") if isinstance(result, dict) else None
        result_distances = result.get("distances") if isinstance(result, dict) else None
        if not isinstance(result_ids, list) or not isinstance(result_distances, list):
            return None

        scores = [0.0 for _ in document_vectors]
        for ids_row, distances_row in zip(result_ids, result_distances, strict=False):
            if not isinstance(ids_row, list) or not isinstance(distances_row, list):
                continue
            for doc_id, distance in zip(ids_row, distances_row, strict=False):
                try:
                    doc_index = int(doc_id)
                    similarity = 1.0 - float(distance)
                except (TypeError, ValueError):
                    continue
                if doc_index < 0 or doc_index >= len(scores):
                    continue
                if similarity > scores[doc_index]:
                    scores[doc_index] = similarity
        return scores


def _dot_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=False))


def _first_dimension(vectors: Sequence[Sequence[float]]) -> int:
    for vector in vectors:
        if vector:
            return len(vector)
    return 0
