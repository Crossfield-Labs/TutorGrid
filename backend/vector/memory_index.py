from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Sequence


class MemoryVectorIndex:
    """Persistent vector index for memory documents."""

    def __init__(self, *, root: Path, backend: str = "auto") -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        normalized = (backend or "auto").strip().lower()
        self.backend = normalized or "auto"

    def rebuild(self, *, documents: list[dict[str, Any]]) -> dict[str, Any]:
        normalized_docs = self._normalize_documents(documents)
        if not normalized_docs:
            shutil.rmtree(self.root, ignore_errors=True)
            self.root.mkdir(parents=True, exist_ok=True)
            return {"backend": "none", "documentCount": 0, "dimension": 0}

        dimension = len(normalized_docs[0]["embedding"])
        for backend_name in self._backend_order():
            try:
                shutil.rmtree(self.root, ignore_errors=True)
                self.root.mkdir(parents=True, exist_ok=True)
                if backend_name == "faiss":
                    if not self._rebuild_with_faiss(documents=normalized_docs, dimension=dimension):
                        continue
                elif backend_name == "chroma":
                    if not self._rebuild_with_chroma(documents=normalized_docs):
                        continue
                else:
                    self._rebuild_with_json(documents=normalized_docs, dimension=dimension)
                self._write_manifest(
                    payload={
                        "backend": backend_name,
                        "documentCount": len(normalized_docs),
                        "dimension": dimension,
                    }
                )
                return {"backend": backend_name, "documentCount": len(normalized_docs), "dimension": dimension}
            except Exception:
                continue
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)
        return {"backend": "none", "documentCount": 0, "dimension": 0}

    def search(
        self,
        *,
        query_vectors: Sequence[Sequence[float]],
        limit: int = 5,
        session_id: str | None = None,
    ) -> dict[str, float]:
        if not query_vectors:
            return {}
        manifest = self._read_manifest()
        if not manifest:
            return {}
        backend_name = str(manifest.get("backend") or "").strip().lower()
        safe_limit = max(1, int(limit))
        if backend_name == "faiss":
            scores = self._search_with_faiss(query_vectors=query_vectors, limit=safe_limit, session_id=session_id)
            if scores:
                return self._trim_scores(scores, safe_limit)
        if backend_name == "chroma":
            scores = self._search_with_chroma(query_vectors=query_vectors, limit=safe_limit, session_id=session_id)
            if scores:
                return self._trim_scores(scores, safe_limit)
        if backend_name == "json":
            scores = self._search_with_json(query_vectors=query_vectors, limit=safe_limit, session_id=session_id)
            if scores:
                return self._trim_scores(scores, safe_limit)
        return {}

    def _backend_order(self) -> list[str]:
        if self.backend in {"none", "off", "disabled"}:
            return []
        if self.backend in {"json", "python", "sqlite"}:
            return ["json"]
        if self.backend == "faiss":
            return ["faiss", "json"]
        if self.backend == "chroma":
            return ["chroma", "json"]
        return ["faiss", "chroma", "json"]

    @staticmethod
    def _normalize_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        dimension = 0
        for item in documents:
            document_id = str(item.get("documentId") or "").strip()
            session_id = str(item.get("sessionId") or "").strip()
            embedding = item.get("embedding")
            if not document_id or not session_id or not isinstance(embedding, list) or not embedding:
                continue
            vector = [float(value) for value in embedding]
            if not vector:
                continue
            if dimension <= 0:
                dimension = len(vector)
            if len(vector) != dimension:
                continue
            normalized.append({"documentId": document_id, "sessionId": session_id, "embedding": vector})
        return normalized

    def _write_manifest(self, *, payload: dict[str, Any]) -> None:
        (self.root / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _read_manifest(self) -> dict[str, Any]:
        manifest_path = self.root / "manifest.json"
        if not manifest_path.exists():
            return {}
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _trim_scores(scores: dict[str, float], limit: int) -> dict[str, float]:
        ranked = sorted(scores.items(), key=lambda item: float(item[1]), reverse=True)[: max(1, int(limit))]
        return {document_id: float(score) for document_id, score in ranked}

    def _rebuild_with_faiss(self, *, documents: list[dict[str, Any]], dimension: int) -> bool:
        try:
            import faiss  # type: ignore[import-not-found]
            import numpy as np
        except Exception:
            return False
        vectors = np.asarray([item["embedding"] for item in documents], dtype="float32")
        index = faiss.IndexFlatIP(dimension)
        index.add(vectors)
        faiss.write_index(index, str(self.root / "faiss.index"))
        (self.root / "faiss_docs.json").write_text(
            json.dumps(
                [{"documentId": item["documentId"], "sessionId": item["sessionId"]} for item in documents],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return True

    def _search_with_faiss(
        self,
        *,
        query_vectors: Sequence[Sequence[float]],
        limit: int,
        session_id: str | None = None,
    ) -> dict[str, float]:
        index_path = self.root / "faiss.index"
        docs_path = self.root / "faiss_docs.json"
        if not index_path.exists() or not docs_path.exists():
            return {}
        try:
            import faiss  # type: ignore[import-not-found]
            import numpy as np
        except Exception:
            return {}
        try:
            meta_items = json.loads(docs_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(meta_items, list) or not meta_items:
            return {}
        metadata: list[tuple[str, str]] = []
        for item in meta_items:
            if not isinstance(item, dict):
                continue
            document_id = str(item.get("documentId") or "").strip()
            doc_session_id = str(item.get("sessionId") or "").strip()
            if not document_id or not doc_session_id:
                continue
            metadata.append((document_id, doc_session_id))
        if not metadata:
            return {}
        try:
            index = faiss.read_index(str(index_path))
        except Exception:
            return {}
        dimension = int(getattr(index, "d", 0) or 0)
        normalized_queries = [[float(item) for item in vector] for vector in query_vectors if len(vector) == dimension]
        if dimension <= 0 or not normalized_queries:
            return {}
        candidate_limit = min(max(1, int(limit)) * 8, len(metadata))
        query_matrix = np.asarray(normalized_queries, dtype="float32")
        try:
            distances, neighbors = index.search(query_matrix, max(1, candidate_limit))
        except Exception:
            return {}
        scores: dict[str, float] = {}
        for query_idx in range(len(normalized_queries)):
            for rank_idx in range(max(1, candidate_limit)):
                local_index = int(neighbors[query_idx][rank_idx])
                if local_index < 0 or local_index >= len(metadata):
                    continue
                document_id, doc_session_id = metadata[local_index]
                if session_id and doc_session_id != session_id:
                    continue
                score = float(distances[query_idx][rank_idx])
                previous = scores.get(document_id, float("-inf"))
                if score > previous:
                    scores[document_id] = score
        return scores

    def _rebuild_with_chroma(self, *, documents: list[dict[str, Any]]) -> bool:
        try:
            import chromadb  # type: ignore[import-not-found]
        except Exception:
            return False
        chroma_dir = self.root / "chroma"
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection_name = "memory_documents"
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        try:
            collection = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        except Exception:
            return False
        batch_size = 256
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            collection.add(
                ids=[item["documentId"] for item in batch],
                embeddings=[[float(value) for value in item["embedding"]] for item in batch],
                metadatas=[{"sessionId": item["sessionId"]} for item in batch],
            )
        return True

    def _search_with_chroma(
        self,
        *,
        query_vectors: Sequence[Sequence[float]],
        limit: int,
        session_id: str | None = None,
    ) -> dict[str, float]:
        try:
            import chromadb  # type: ignore[import-not-found]
        except Exception:
            return {}
        chroma_dir = self.root / "chroma"
        if not chroma_dir.exists():
            return {}
        client = chromadb.PersistentClient(path=str(chroma_dir))
        try:
            collection = client.get_collection(name="memory_documents")
        except Exception:
            return {}
        normalized_queries = [[float(item) for item in vector] for vector in query_vectors if vector]
        if not normalized_queries:
            return {}
        kwargs: dict[str, Any] = {
            "query_embeddings": normalized_queries,
            "n_results": max(1, int(limit)),
            "include": ["ids", "distances"],
        }
        if session_id:
            kwargs["where"] = {"sessionId": str(session_id)}
        try:
            result = collection.query(**kwargs)
        except Exception:
            return {}
        ids_rows = result.get("ids") if isinstance(result, dict) else None
        distances_rows = result.get("distances") if isinstance(result, dict) else None
        if not isinstance(ids_rows, list) or not isinstance(distances_rows, list):
            return {}
        scores: dict[str, float] = {}
        for ids_row, distances_row in zip(ids_rows, distances_rows, strict=False):
            if not isinstance(ids_row, list) or not isinstance(distances_row, list):
                continue
            for document_id, distance in zip(ids_row, distances_row, strict=False):
                normalized_id = str(document_id or "").strip()
                if not normalized_id:
                    continue
                similarity = 1.0 - float(distance)
                previous = scores.get(normalized_id, float("-inf"))
                if similarity > previous:
                    scores[normalized_id] = similarity
        return scores

    def _rebuild_with_json(self, *, documents: list[dict[str, Any]], dimension: int) -> None:
        payload = {
            "dimension": int(dimension),
            "items": [
                {
                    "documentId": item["documentId"],
                    "sessionId": item["sessionId"],
                    "embedding": item["embedding"],
                }
                for item in documents
            ],
        }
        (self.root / "json_index.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _search_with_json(
        self,
        *,
        query_vectors: Sequence[Sequence[float]],
        limit: int,
        session_id: str | None = None,
    ) -> dict[str, float]:
        index_path = self.root / "json_index.json"
        if not index_path.exists():
            return {}
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        dimension = int(payload.get("dimension") or 0)
        raw_items = payload.get("items")
        if dimension <= 0 or not isinstance(raw_items, list):
            return {}
        items: list[tuple[str, str, list[float]]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            document_id = str(item.get("documentId") or "").strip()
            doc_session_id = str(item.get("sessionId") or "").strip()
            embedding = item.get("embedding")
            if not document_id or not doc_session_id or not isinstance(embedding, list) or len(embedding) != dimension:
                continue
            items.append((document_id, doc_session_id, [float(value) for value in embedding]))
        if not items:
            return {}
        normalized_queries = [[float(value) for value in vector] for vector in query_vectors if len(vector) == dimension]
        if not normalized_queries:
            return {}
        scores: dict[str, float] = {}
        for query_vector in normalized_queries:
            for document_id, doc_session_id, embedding in items:
                if session_id and doc_session_id != session_id:
                    continue
                score = _dot_similarity(query_vector, embedding)
                previous = scores.get(document_id, float("-inf"))
                if score > previous:
                    scores[document_id] = score
        return self._trim_scores(scores, limit)


def _dot_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=False))

