from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Sequence


class KnowledgeVectorIndex:
    """Per-course persistent vector index with optional FAISS/Chroma backends."""

    def __init__(self, *, root: Path, backend: str = "auto") -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        normalized = (backend or "auto").strip().lower()
        self.backend = normalized or "auto"

    def rebuild_course(self, *, course_id: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
        normalized_course = course_id.strip()
        normalized_chunks = self._normalize_chunks(chunks)
        index_dir = self._course_index_dir(normalized_course)
        if not normalized_chunks:
            self.delete_course(course_id=normalized_course)
            return {
                "courseId": normalized_course,
                "backend": "none",
                "chunkCount": 0,
                "dimension": 0,
            }

        dimension = len(normalized_chunks[0]["embedding"])
        for backend_name in self._backend_order():
            try:
                shutil.rmtree(index_dir, ignore_errors=True)
                index_dir.mkdir(parents=True, exist_ok=True)
                if backend_name == "faiss":
                    if not self._rebuild_with_faiss(index_dir=index_dir, chunks=normalized_chunks, dimension=dimension):
                        continue
                elif backend_name == "chroma":
                    if not self._rebuild_with_chroma(index_dir=index_dir, chunks=normalized_chunks):
                        continue
                else:
                    self._rebuild_with_json(index_dir=index_dir, chunks=normalized_chunks, dimension=dimension)
                self._write_manifest(
                    index_dir=index_dir,
                    payload={
                        "backend": backend_name,
                        "chunkCount": len(normalized_chunks),
                        "dimension": dimension,
                    },
                )
                return {
                    "courseId": normalized_course,
                    "backend": backend_name,
                    "chunkCount": len(normalized_chunks),
                    "dimension": dimension,
                }
            except Exception:
                continue
        self.delete_course(course_id=normalized_course)
        return {
            "courseId": normalized_course,
            "backend": "none",
            "chunkCount": 0,
            "dimension": 0,
        }

    def search(
        self,
        *,
        course_id: str,
        query_vectors: Sequence[Sequence[float]],
        limit: int = 128,
    ) -> dict[str, float]:
        if not query_vectors:
            return {}
        normalized_course = course_id.strip()
        index_dir = self._course_index_dir(normalized_course)
        manifest = self._read_manifest(index_dir=index_dir)
        if not manifest:
            return {}
        backend_name = str(manifest.get("backend") or "").strip().lower()
        safe_limit = max(1, int(limit))
        if backend_name == "faiss":
            scores = self._search_with_faiss(index_dir=index_dir, query_vectors=query_vectors, limit=safe_limit)
            if scores:
                return self._trim_scores(scores, safe_limit)
        if backend_name == "chroma":
            scores = self._search_with_chroma(index_dir=index_dir, query_vectors=query_vectors, limit=safe_limit)
            if scores:
                return self._trim_scores(scores, safe_limit)
        if backend_name == "json":
            scores = self._search_with_json(index_dir=index_dir, query_vectors=query_vectors, limit=safe_limit)
            if scores:
                return self._trim_scores(scores, safe_limit)
        return {}

    def delete_course(self, *, course_id: str) -> None:
        normalized_course = course_id.strip()
        index_dir = self._course_index_dir(normalized_course)
        shutil.rmtree(index_dir, ignore_errors=True)

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

    def _course_index_dir(self, course_id: str) -> Path:
        return self.root / course_id / "index"

    @staticmethod
    def _normalize_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        dimension = 0
        for item in chunks:
            chunk_id = str(item.get("chunkId") or "").strip()
            embedding = item.get("embedding")
            if not chunk_id or not isinstance(embedding, list) or not embedding:
                continue
            vector = [float(value) for value in embedding]
            if not vector:
                continue
            if dimension <= 0:
                dimension = len(vector)
            if len(vector) != dimension:
                continue
            normalized.append({"chunkId": chunk_id, "embedding": vector})
        return normalized

    @staticmethod
    def _write_manifest(*, index_dir: Path, payload: dict[str, Any]) -> None:
        manifest_path = index_dir / "manifest.json"
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _read_manifest(*, index_dir: Path) -> dict[str, Any]:
        manifest_path = index_dir / "manifest.json"
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
        return {chunk_id: max(0.0, float(score)) for chunk_id, score in ranked}

    def _rebuild_with_faiss(self, *, index_dir: Path, chunks: list[dict[str, Any]], dimension: int) -> bool:
        try:
            import faiss  # type: ignore[import-not-found]
            import numpy as np
        except Exception:
            return False

        vectors = np.asarray([item["embedding"] for item in chunks], dtype="float32")
        index = faiss.IndexFlatIP(dimension)
        index.add(vectors)
        faiss.write_index(index, str(index_dir / "faiss.index"))
        (index_dir / "faiss_ids.json").write_text(
            json.dumps([item["chunkId"] for item in chunks], ensure_ascii=False),
            encoding="utf-8",
        )
        return True

    def _search_with_faiss(
        self,
        *,
        index_dir: Path,
        query_vectors: Sequence[Sequence[float]],
        limit: int,
    ) -> dict[str, float]:
        index_path = index_dir / "faiss.index"
        ids_path = index_dir / "faiss_ids.json"
        if not index_path.exists() or not ids_path.exists():
            return {}
        try:
            import faiss  # type: ignore[import-not-found]
            import numpy as np
        except Exception:
            return {}
        try:
            chunk_ids = json.loads(ids_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(chunk_ids, list) or not chunk_ids:
            return {}
        try:
            index = faiss.read_index(str(index_path))
        except Exception:
            return {}
        dimension = int(getattr(index, "d", 0) or 0)
        if dimension <= 0:
            return {}
        normalized_queries = [[float(item) for item in vector] for vector in query_vectors if len(vector) == dimension]
        if not normalized_queries:
            return {}
        query_matrix = np.asarray(normalized_queries, dtype="float32")
        k = min(max(1, int(limit)), len(chunk_ids))
        try:
            distances, neighbors = index.search(query_matrix, k)
        except Exception:
            return {}
        scores: dict[str, float] = {}
        for query_idx in range(len(normalized_queries)):
            for rank_idx in range(k):
                local_index = int(neighbors[query_idx][rank_idx])
                if local_index < 0 or local_index >= len(chunk_ids):
                    continue
                chunk_id = str(chunk_ids[local_index]).strip()
                if not chunk_id:
                    continue
                score = float(distances[query_idx][rank_idx])
                previous = scores.get(chunk_id, float("-inf"))
                if score > previous:
                    scores[chunk_id] = score
        return scores

    def _rebuild_with_chroma(self, *, index_dir: Path, chunks: list[dict[str, Any]]) -> bool:
        try:
            import chromadb  # type: ignore[import-not-found]
        except Exception:
            return False
        chroma_dir = index_dir / "chroma"
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection_name = "knowledge_chunks"
        try:
            client.delete_collection(name=collection_name)
        except Exception:
            pass
        try:
            collection = client.create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        except Exception:
            return False
        batch_size = 256
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            collection.add(
                ids=[item["chunkId"] for item in batch],
                embeddings=[[float(value) for value in item["embedding"]] for item in batch],
            )
        return True

    def _search_with_chroma(
        self,
        *,
        index_dir: Path,
        query_vectors: Sequence[Sequence[float]],
        limit: int,
    ) -> dict[str, float]:
        try:
            import chromadb  # type: ignore[import-not-found]
        except Exception:
            return {}
        chroma_dir = index_dir / "chroma"
        if not chroma_dir.exists():
            return {}
        client = chromadb.PersistentClient(path=str(chroma_dir))
        try:
            collection = client.get_collection(name="knowledge_chunks")
        except Exception:
            return {}
        normalized_queries = [[float(item) for item in vector] for vector in query_vectors if vector]
        if not normalized_queries:
            return {}
        try:
            result = collection.query(query_embeddings=normalized_queries, n_results=max(1, int(limit)), include=["ids", "distances"])
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
            for chunk_id, distance in zip(ids_row, distances_row, strict=False):
                normalized_chunk_id = str(chunk_id or "").strip()
                if not normalized_chunk_id:
                    continue
                similarity = 1.0 - float(distance)
                previous = scores.get(normalized_chunk_id, float("-inf"))
                if similarity > previous:
                    scores[normalized_chunk_id] = similarity
        return scores

    @staticmethod
    def _rebuild_with_json(*, index_dir: Path, chunks: list[dict[str, Any]], dimension: int) -> None:
        payload = {
            "dimension": int(dimension),
            "items": [{"chunkId": item["chunkId"], "embedding": item["embedding"]} for item in chunks],
        }
        (index_dir / "json_index.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _search_with_json(
        self,
        *,
        index_dir: Path,
        query_vectors: Sequence[Sequence[float]],
        limit: int,
    ) -> dict[str, float]:
        index_path = index_dir / "json_index.json"
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
        items: list[tuple[str, list[float]]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            chunk_id = str(item.get("chunkId") or "").strip()
            embedding = item.get("embedding")
            if not chunk_id or not isinstance(embedding, list) or len(embedding) != dimension:
                continue
            items.append((chunk_id, [float(value) for value in embedding]))
        if not items:
            return {}
        normalized_queries = [[float(value) for value in vector] for vector in query_vectors if len(vector) == dimension]
        if not normalized_queries:
            return {}
        scores: dict[str, float] = {}
        for query_vector in normalized_queries:
            for chunk_id, embedding in items:
                score = _dot_similarity(query_vector, embedding)
                previous = scores.get(chunk_id, float("-inf"))
                if score > previous:
                    scores[chunk_id] = score
        return self._trim_scores(scores, limit)


def _dot_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=False))

