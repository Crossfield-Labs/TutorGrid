from __future__ import annotations

import json
import math
import os
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from backend.config import load_config
from backend.knowledge.service import KnowledgeBaseService
from backend.observability import get_langsmith_tracer
from backend.providers.base import LLMProvider
from backend.providers.registry import ProviderRegistry
from backend.vector import VectorRanker


_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [item.group(0).lower() for item in _TOKEN_PATTERN.finditer(text or "")]


class _Bm25Scorer:
    def __init__(self, corpus_tokens: list[list[str]], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.corpus_tokens = corpus_tokens
        self.k1 = float(k1)
        self.b = float(b)
        self.doc_count = max(1, len(corpus_tokens))
        lengths = [len(item) for item in corpus_tokens]
        self.avg_doc_len = sum(lengths) / self.doc_count if lengths else 1.0
        self.doc_freq: dict[str, int] = {}
        for tokens in corpus_tokens:
            for token in set(tokens):
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
        self.term_freq_by_doc: list[dict[str, int]] = []
        for tokens in corpus_tokens:
            freq: dict[str, int] = {}
            for token in tokens:
                freq[token] = freq.get(token, 0) + 1
            self.term_freq_by_doc.append(freq)

    def score(self, query_tokens: list[str]) -> list[float]:
        if not query_tokens:
            return [0.0 for _ in self.corpus_tokens]
        scores = [0.0 for _ in self.corpus_tokens]
        for token in query_tokens:
            df = self.doc_freq.get(token, 0)
            if df <= 0:
                continue
            idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
            for doc_index, term_freq in enumerate(self.term_freq_by_doc):
                tf = term_freq.get(token, 0)
                if tf <= 0:
                    continue
                doc_len = max(1, len(self.corpus_tokens[doc_index]))
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * doc_len / max(1.0, self.avg_doc_len))
                scores[doc_index] += idf * numerator / max(1e-9, denominator)
        return scores


class RagService:
    def __init__(
        self,
        *,
        knowledge_service: KnowledgeBaseService | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.knowledge_service = knowledge_service or KnowledgeBaseService()
        self.config = load_config()
        self.llm_provider = llm_provider or self._build_llm_provider()
        self.enable_multi_query = self._bool_env("ORCHESTRATOR_RAG_MULTI_QUERY", False)
        self.enable_hyde = self._bool_env("ORCHESTRATOR_RAG_HYDE", False)
        self.enable_rerank = self._bool_env("ORCHESTRATOR_RAG_RERANK", True)
        self.enable_answer = self._bool_env("ORCHESTRATOR_RAG_ANSWER_ENABLED", False)
        self.multi_query_count = max(1, int(os.environ.get("ORCHESTRATOR_RAG_MULTI_QUERY_COUNT", "3")))
        self.hyde_attempts = max(1, int(os.environ.get("ORCHESTRATOR_RAG_HYDE_ATTEMPTS", "2")))
        self.answer_attempts = max(1, int(os.environ.get("ORCHESTRATOR_RAG_ANSWER_ATTEMPTS", "2")))
        self.hyde_query_fallback = self._bool_env("ORCHESTRATOR_RAG_HYDE_QUERY_FALLBACK", True)
        self.answer_max_chars = max(300, int(os.environ.get("ORCHESTRATOR_RAG_ANSWER_MAX_CHARS", "1200")))
        self.max_candidates = max(10, int(os.environ.get("ORCHESTRATOR_RAG_MAX_CANDIDATES", "60")))
        self.rrf_k = max(10, int(os.environ.get("ORCHESTRATOR_RAG_RRF_K", "60")))
        self.tracer = get_langsmith_tracer()
        self.vector_backend = os.environ.get("ORCHESTRATOR_VECTOR_STORE_BACKEND", "auto").strip().lower()
        self.vector_ranker = VectorRanker(backend=self.vector_backend)
        self.last_hyde_error = ""
        self.last_hyde_source = "disabled"
        self.last_answer_error = ""
        self.last_answer_source = "disabled"

        self.rerank_api_base = os.environ.get("ORCHESTRATOR_RERANK_API_BASE", "").strip().rstrip("/")
        self.rerank_api_key = os.environ.get("ORCHESTRATOR_RERANK_API_KEY", "").strip()
        self.rerank_model = os.environ.get("ORCHESTRATOR_RERANK_MODEL", "").strip()

    async def query(self, *, course_id: str, question: str, limit: int = 8) -> dict[str, Any]:
        normalized_course = course_id.strip()
        normalized_question = question.strip()
        if not normalized_course:
            raise ValueError("courseId cannot be empty.")
        if not normalized_question:
            raise ValueError("question cannot be empty.")
        run_id = self.tracer.start_run(
            name="rag.query",
            run_type="chain",
            inputs={"courseId": normalized_course, "question": normalized_question, "limit": max(1, int(limit))},
            metadata={"module": "rag"},
            tags=["rag", "query"],
        )
        try:
            raw_chunks = self.knowledge_service.list_chunks_for_retrieval(course_id=normalized_course, limit=5000)
            chunks, dropped_chunk_count = self._filter_retrievable_chunks(raw_chunks)
            if not chunks:
                response = {
                    "courseId": normalized_course,
                    "query": normalized_question,
                    "items": [],
                    "debug": {"reason": "no_chunks", "droppedChunkCount": dropped_chunk_count},
                }
                self.tracer.end_run(
                    run_id,
                    outputs={
                        "courseId": normalized_course,
                        "itemCount": 0,
                        "candidateCount": 0,
                        "reason": "no_chunks",
                    },
                    metadata={"module": "rag"},
                )
                return response

            multi_query_run_id = self.tracer.start_run(
                name="rag.multi_query",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"question": normalized_question, "enabled": self.enable_multi_query},
                metadata={"stage": "multi_query"},
                tags=["rag", "multi-query"],
            )
            try:
                multi_queries = await self._build_multi_queries(normalized_question)
                self.tracer.end_run(
                    multi_query_run_id,
                    outputs={"count": len(multi_queries), "queries": multi_queries[: self.multi_query_count]},
                    metadata={"stage": "multi_query"},
                )
            except Exception as exc:
                self.tracer.end_run(
                    multi_query_run_id,
                    error=(str(exc).strip() or "multi-query stage failed")[:1200],
                    metadata={"stage": "multi_query"},
                    tags=["error"],
                )
                raise

            hyde_run_id = self.tracer.start_run(
                name="rag.hyde",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"question": normalized_question, "enabled": self.enable_hyde},
                metadata={"stage": "hyde"},
                tags=["rag", "hyde"],
            )
            try:
                hyde_text = await self._build_hyde_answer(normalized_question)
                self.tracer.end_run(
                    hyde_run_id,
                    outputs={"charCount": len(hyde_text), "enabled": self.enable_hyde},
                    metadata={"stage": "hyde"},
                )
            except Exception as exc:
                self.tracer.end_run(
                    hyde_run_id,
                    error=(str(exc).strip() or "HyDE stage failed")[:1200],
                    metadata={"stage": "hyde"},
                    tags=["error"],
                )
                raise

            dense_queries = list(multi_queries)
            if hyde_text:
                dense_queries.append(hyde_text)

            retrieve_run_id = self.tracer.start_run(
                name="rag.retrieve",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"queryCount": len(dense_queries), "chunkCount": len(chunks)},
                metadata={"stage": "retrieve"},
                tags=["rag", "retrieve"],
            )
            try:
                indexed_scores = self.knowledge_service.search_chunk_scores(
                    course_id=normalized_course,
                    queries=dense_queries,
                    limit=max(self.max_candidates * 4, max(32, limit * 8)),
                )
                dense_scores = self._dense_scores(chunks, dense_queries, indexed_scores=indexed_scores)
                lexical_scores = self._lexical_scores(chunks, multi_queries)
                fused = self._fuse_scores(dense_scores=dense_scores, lexical_scores=lexical_scores)
                top_candidates = sorted(
                    fused,
                    key=lambda item: float(item["score"]),
                    reverse=True,
                )[: self.max_candidates]
                self.tracer.end_run(
                    retrieve_run_id,
                    outputs={
                        "denseCount": len(dense_scores),
                        "lexicalCount": len(lexical_scores),
                        "candidateCount": len(top_candidates),
                        "indexedCount": len(indexed_scores),
                    },
                    metadata={"stage": "retrieve"},
                )
            except Exception as exc:
                self.tracer.end_run(
                    retrieve_run_id,
                    error=(str(exc).strip() or "retrieve stage failed")[:1200],
                    metadata={"stage": "retrieve"},
                    tags=["error"],
                )
                raise

            rerank_mode = "api" if self._can_use_rerank_api() else "local"
            rerank_run_id = self.tracer.start_run(
                name="rag.rerank",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"candidateCount": len(top_candidates), "mode": rerank_mode, "enabled": self.enable_rerank},
                metadata={"stage": "rerank"},
                tags=["rag", "rerank"],
            )
            try:
                reranked = self._rerank_candidates(question=normalized_question, candidates=top_candidates, chunks=chunks)
                final_items = sorted(reranked, key=lambda item: float(item["finalScore"]), reverse=True)[: max(1, limit)]
                self.tracer.end_run(
                    rerank_run_id,
                    outputs={"rerankedCount": len(reranked), "finalCount": len(final_items), "mode": rerank_mode},
                    metadata={"stage": "rerank"},
                )
            except Exception as exc:
                self.tracer.end_run(
                    rerank_run_id,
                    error=(str(exc).strip() or "rerank stage failed")[:1200],
                    metadata={"stage": "rerank"},
                    tags=["error"],
                )
                raise

            answer_run_id = self.tracer.start_run(
                name="rag.answer",
                run_type="tool",
                parent_run_id=run_id,
                inputs={"enabled": self.enable_answer, "finalCount": len(final_items)},
                metadata={"stage": "answer"},
                tags=["rag", "answer"],
            )
            try:
                answer_text = await self._build_answer(question=normalized_question, items=final_items)
                self.tracer.end_run(
                    answer_run_id,
                    outputs={
                        "enabled": self.enable_answer,
                        "charCount": len(answer_text),
                        "source": self.last_answer_source,
                    },
                    metadata={"stage": "answer"},
                )
            except Exception as exc:
                self.tracer.end_run(
                    answer_run_id,
                    error=(str(exc).strip() or "answer stage failed")[:1200],
                    metadata={"stage": "answer"},
                    tags=["error"],
                )
                raise

            response = {
                "courseId": normalized_course,
                "query": normalized_question,
                "answer": answer_text,
                "items": [
                    {
                        "chunkId": item["chunkId"],
                        "fileId": item["fileId"],
                        "content": item["content"],
                        "sourcePage": item["sourcePage"],
                        "sourceSection": item["sourceSection"],
                        "sourceName": item["sourceName"],
                        "score": item["finalScore"],
                        "denseScore": item["denseScore"],
                        "lexicalScore": item["lexicalScore"],
                        "rerankScore": item["rerankScore"],
                        "metadata": item["metadata"],
                    }
                    for item in final_items
                ],
                "debug": {
                    "multiQueries": multi_queries,
                    "hyde": hyde_text,
                    "hydeSource": self.last_hyde_source,
                    "hydeError": self.last_hyde_error[:240],
                    "answerSource": self.last_answer_source,
                    "answerError": self.last_answer_error[:240],
                    "droppedChunkCount": dropped_chunk_count,
                    "candidateCount": len(top_candidates),
                    "rerankMode": rerank_mode,
                },
            }
            self.tracer.end_run(
                run_id,
                outputs={
                    "courseId": normalized_course,
                    "itemCount": len(response["items"]),
                    "candidateCount": len(top_candidates),
                    "rerankMode": rerank_mode,
                },
                metadata={"module": "rag"},
            )
            return response
        except Exception as exc:
            self.tracer.end_run(
                run_id,
                outputs={"courseId": normalized_course},
                error=(str(exc).strip() or "RAG query failed")[:1200],
                metadata={"module": "rag"},
                tags=["error"],
            )
            raise

    def _dense_scores(
        self,
        chunks: list[dict[str, Any]],
        queries: list[str],
        *,
        indexed_scores: dict[str, float] | None = None,
    ) -> list[float]:
        if not queries:
            return [0.0 for _ in chunks]
        if indexed_scores:
            scores = [float(indexed_scores.get(str(chunk.get("chunkId") or ""), 0.0)) for chunk in chunks]
            if any(score > 0.0 for score in scores):
                return self._normalize(scores)
        query_vectors = self.knowledge_service.embed_texts(queries)
        if not query_vectors:
            return [0.0 for _ in chunks]

        chunk_vectors: list[list[float]] = []
        for chunk in chunks:
            chunk_embedding = chunk.get("embedding")
            if not isinstance(chunk_embedding, list) or not chunk_embedding:
                text = str(chunk.get("content") or "")
                chunk_embedding = self.knowledge_service.embed_text(text)
                chunk["embedding"] = chunk_embedding
            chunk_vectors.append(chunk_embedding if isinstance(chunk_embedding, list) else [])
        scores = self.vector_ranker.rank_max_similarity(query_vectors=query_vectors, document_vectors=chunk_vectors)
        if len(scores) != len(chunks):
            return [0.0 for _ in chunks]
        return self._normalize(scores)

    def _lexical_scores(self, chunks: list[dict[str, Any]], queries: list[str]) -> list[float]:
        if not queries:
            return [0.0 for _ in chunks]
        corpus_tokens = [_tokenize(str(chunk.get("content") or "")) for chunk in chunks]
        scorer = _Bm25Scorer(corpus_tokens)
        merged = [0.0 for _ in chunks]
        for query in queries:
            tokens = _tokenize(query)
            partial = scorer.score(tokens)
            for idx, score in enumerate(partial):
                merged[idx] = max(merged[idx], float(score))
        return self._normalize(merged)

    def _fuse_scores(self, *, dense_scores: list[float], lexical_scores: list[float]) -> list[dict[str, Any]]:
        dense_ranks = self._ranks(dense_scores)
        lexical_ranks = self._ranks(lexical_scores)
        fused: list[dict[str, Any]] = []
        for idx in range(max(len(dense_scores), len(lexical_scores))):
            dense = float(dense_scores[idx] if idx < len(dense_scores) else 0.0)
            lexical = float(lexical_scores[idx] if idx < len(lexical_scores) else 0.0)
            dense_rank = dense_ranks.get(idx, len(dense_scores) + 1)
            lexical_rank = lexical_ranks.get(idx, len(lexical_scores) + 1)
            rrf = 1.0 / (self.rrf_k + dense_rank) + 1.0 / (self.rrf_k + lexical_rank)
            score = 0.55 * dense + 0.45 * lexical + 0.25 * rrf
            fused.append(
                {
                    "index": idx,
                    "denseScore": dense,
                    "lexicalScore": lexical,
                    "rrfScore": rrf,
                    "score": score,
                }
            )
        return fused

    def _rerank_candidates(
        self,
        *,
        question: str,
        candidates: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        if self.enable_rerank and self._can_use_rerank_api():
            api_scores = self._rerank_with_api(question=question, candidates=candidates, chunks=chunks)
        else:
            api_scores = {}

        query_tokens = set(_tokenize(question))
        reranked: list[dict[str, Any]] = []
        for item in candidates:
            index = int(item["index"])
            chunk = chunks[index]
            chunk_text = str(chunk.get("content") or "")
            local_rerank = self._local_rerank_score(query_tokens=query_tokens, chunk_text=chunk_text)
            rerank_score = float(api_scores.get(index, local_rerank))
            final_score = 0.65 * float(item["score"]) + 0.35 * rerank_score
            reranked.append(
                {
                    "chunkId": str(chunk.get("chunkId") or ""),
                    "fileId": str(chunk.get("fileId") or ""),
                    "sourceName": self._source_name_for_chunk(chunk),
                    "content": chunk_text,
                    "sourcePage": int(chunk.get("sourcePage") or 0),
                    "sourceSection": str(chunk.get("sourceSection") or ""),
                    "metadata": dict(chunk.get("metadata") or {}),
                    "denseScore": float(item["denseScore"]),
                    "lexicalScore": float(item["lexicalScore"]),
                    "rerankScore": rerank_score,
                    "finalScore": final_score,
                }
            )
        return reranked

    @staticmethod
    def _source_name_for_chunk(chunk: dict[str, Any]) -> str:
        metadata = chunk.get("metadata")
        if isinstance(metadata, dict):
            original_name = str(metadata.get("originalName") or "").strip()
            if original_name:
                return original_name
            source_path = str(metadata.get("sourcePath") or metadata.get("storedPath") or "").strip()
            if source_path:
                return Path(source_path).name
        return str(chunk.get("fileId") or "")

    def _local_rerank_score(self, *, query_tokens: set[str], chunk_text: str) -> float:
        if not query_tokens:
            return 0.0
        chunk_tokens = set(_tokenize(chunk_text))
        if not chunk_tokens:
            return 0.0
        overlap = len(query_tokens & chunk_tokens)
        return overlap / max(1, len(query_tokens))

    async def _build_multi_queries(self, question: str) -> list[str]:
        normalized = question.strip()
        queries = [normalized]
        if not self.enable_multi_query:
            return queries
        llm_queries = await self._multi_queries_by_llm(normalized)
        if not llm_queries:
            llm_queries = [f"{normalized} key concepts", f"{normalized} definition and examples"]
        for query in llm_queries:
            candidate = query.strip()
            if not candidate:
                continue
            if candidate not in queries:
                queries.append(candidate)
            if len(queries) >= self.multi_query_count:
                break
        return queries

    async def _build_hyde_answer(self, question: str) -> str:
        self.last_hyde_error = ""
        normalized_question = question.strip()
        if not self.enable_hyde:
            self.last_hyde_source = "disabled"
            return ""
        if not normalized_question:
            self.last_hyde_source = "empty_question"
            return ""
        if self.llm_provider is None:
            self.last_hyde_source = "llm_unavailable"
            if self.hyde_query_fallback:
                self.last_hyde_error = "LLM provider is unavailable."
                self.last_hyde_source = "question_fallback"
                return normalized_question
            return ""

        prompts = [
            (
                "Write one concise, high-quality hypothetical answer for retrieval augmentation.\n"
                "Return only the answer text and no extra explanation.\n\n"
                f"Question: {normalized_question}"
            ),
            (
                "Generate a direct answer in 2-4 sentences.\n"
                "Only output the answer body.\n\n"
                f"Question: {normalized_question}"
            ),
        ]
        errors: list[str] = []
        for attempt in range(self.hyde_attempts):
            prompt = prompts[min(attempt, len(prompts) - 1)]
            try:
                response = await self._chat(messages=[{"role": "user", "content": prompt}], tools=None)
            except Exception as exc:
                message = str(exc).strip() or "HyDE request failed."
                errors.append(message)
                continue
            candidate = str(response or "").strip()
            if candidate:
                self.last_hyde_source = "llm"
                return candidate[:1200]
            errors.append("LLM returned empty HyDE output.")

        self.last_hyde_error = " | ".join(errors)[:1200]
        if self.hyde_query_fallback:
            self.last_hyde_source = "question_fallback"
            return normalized_question
        self.last_hyde_source = "empty"
        return ""

    async def _multi_queries_by_llm(self, question: str) -> list[str]:
        if self.llm_provider is None:
            return []
        prompt = (
            "Rewrite the question into 3 diverse search queries.\n"
            "Output exactly one query per line and do not add numbering.\n\n"
            f"Question: {question.strip()}"
        )
        try:
            raw = await self._chat(messages=[{"role": "user", "content": prompt}], tools=None)
        except Exception:
            return []
        lines = [line.strip(" -0123456789.\t") for line in str(raw or "").splitlines()]
        return [line for line in lines if line]

    async def _chat(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> str:
        if self.llm_provider is None:
            return ""
        response = await self.llm_provider.chat(messages=messages, tools=tools)
        return str(response.content or "")

    async def _build_answer(self, *, question: str, items: list[dict[str, Any]]) -> str:
        self.last_answer_error = ""
        normalized_question = question.strip()
        if not normalized_question:
            self.last_answer_source = "empty_question"
            return ""
        if not items:
            self.last_answer_source = "no_items"
            return ""
        if not self.enable_answer:
            self.last_answer_source = "disabled"
            return self._extractive_answer(items)

        if self.llm_provider is None:
            self.last_answer_source = "extractive_fallback"
            self.last_answer_error = "LLM provider is unavailable."
            return self._extractive_answer(items)

        context_parts: list[str] = []
        for index, item in enumerate(items[:5], start=1):
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            context_parts.append(f"[{index}] {content[:500]}")
        context = "\n\n".join(context_parts).strip()
        if not context:
            self.last_answer_source = "extractive_fallback"
            self.last_answer_error = "No usable context text found."
            return self._extractive_answer(items)

        prompt = (
            "You are a retrieval QA assistant.\n"
            "Answer the user question based only on the provided context.\n"
            "If context is insufficient, say that information is limited.\n"
            "Keep the answer concise.\n\n"
            f"Question:\n{normalized_question}\n\n"
            f"Context:\n{context}\n\n"
            "Answer:"
        )
        errors: list[str] = []
        for _ in range(self.answer_attempts):
            try:
                raw = await self._chat(messages=[{"role": "user", "content": prompt}], tools=None)
            except Exception as exc:
                errors.append(str(exc).strip() or "answer request failed")
                continue
            candidate = str(raw or "").strip()
            if candidate:
                self.last_answer_source = "llm"
                return candidate[: self.answer_max_chars]
            errors.append("LLM returned empty answer.")

        self.last_answer_error = " | ".join(errors)[:1200]
        self.last_answer_source = "extractive_fallback"
        return self._extractive_answer(items)

    def _extractive_answer(self, items: list[dict[str, Any]]) -> str:
        for item in items:
            content = str(item.get("content") or "").strip()
            if content:
                return content[: self.answer_max_chars]
        return ""

    def _filter_retrievable_chunks(self, chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        filtered: list[dict[str, Any]] = []
        dropped = 0
        for chunk in chunks:
            if not self._is_chunk_source_compatible(chunk):
                dropped += 1
                continue
            content = str(chunk.get("content") or "")
            if self._is_retrievable_text(content):
                filtered.append(chunk)
                continue
            dropped += 1
        return filtered, dropped

    @staticmethod
    def _is_chunk_source_compatible(chunk: dict[str, Any]) -> bool:
        metadata = chunk.get("metadata")
        if not isinstance(metadata, dict):
            return True
        parser_name = str(metadata.get("parser") or "").strip().lower()
        if parser_name != "plaintext":
            return True
        source_path = str(metadata.get("sourcePath") or "").strip()
        if not source_path:
            return True
        suffix = Path(source_path).suffix.lower()
        # Plaintext parser should only be trusted for text-like formats.
        if suffix in {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".log"}:
            return True
        return False

    @staticmethod
    def _is_retrievable_text(text: str) -> bool:
        normalized = str(text or "").strip()
        if not normalized:
            return False
        printable = sum(1 for ch in normalized if ch.isprintable() or ch in "\n\r\t")
        ratio = printable / max(1, len(normalized))
        if ratio < 0.85:
            return False
        if normalized.count("\ufffd") > max(8, len(normalized) // 8):
            return False
        token_count = len(_tokenize(normalized))
        return token_count >= 3 and len(normalized) >= 20

    def _normalize(self, values: list[float]) -> list[float]:
        if not values:
            return []
        minimum = min(values)
        maximum = max(values)
        if maximum - minimum <= 1e-9:
            return [1.0 if value > 0 else 0.0 for value in values]
        return [(value - minimum) / (maximum - minimum) for value in values]

    def _ranks(self, values: list[float]) -> dict[int, int]:
        ranking = sorted(enumerate(values), key=lambda item: float(item[1]), reverse=True)
        return {index: rank + 1 for rank, (index, _) in enumerate(ranking)}

    def _build_llm_provider(self) -> LLMProvider | None:
        if not self._bool_env("ORCHESTRATOR_RAG_LLM_ENABLED", True):
            return None
        planner = self.config.planner
        if not planner.api_key.strip() or not planner.api_base.strip() or not planner.model.strip():
            return None
        try:
            return ProviderRegistry.create(planner)
        except Exception:
            return None

    def _can_use_rerank_api(self) -> bool:
        return bool(self.rerank_api_base and self.rerank_api_key and self.rerank_model)

    def _rerank_with_api(
        self,
        *,
        question: str,
        candidates: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> dict[int, float]:
        payload = {
            "model": self.rerank_model,
            "query": question,
            "documents": [str(chunks[int(item["index"])].get("content") or "") for item in candidates],
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.rerank_api_base}/rerank",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.rerank_api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                parsed = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ssl.SSLError, OSError):
            return {}
        data = parsed.get("data")
        if not isinstance(data, list):
            return {}
        scores: dict[int, float] = {}
        for item_idx, result in enumerate(data):
            if not isinstance(result, dict):
                continue
            source_idx = int(result.get("index", item_idx))
            if source_idx < 0 or source_idx >= len(candidates):
                continue
            chunk_index = int(candidates[source_idx]["index"])
            scores[chunk_index] = float(result.get("score", 0.0))
        if not scores:
            return {}
        max_score = max(scores.values())
        min_score = min(scores.values())
        if max_score - min_score <= 1e-9:
            return {key: 1.0 if value > 0 else 0.0 for key, value in scores.items()}
        return {key: (value - min_score) / (max_score - min_score) for key, value in scores.items()}

    @staticmethod
    def _bool_env(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() not in {"0", "false", "no", ""}

