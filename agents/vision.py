"""
VISION — Knowledge Agent for JARVIS

Primary source  : Wikipedia REST API (rate-limited, cached)
Secondary source: Local SQLite knowledge DB (vision_knowledge.db)
Fallback        : Internal response with "uncertain" confidence

VISION is standalone — it does not depend on any other JARVIS module.
JARVIS calls vision_agent.ask(question) and receives a VisionResponse.
"""

import asyncio
import logging
import re
import sqlite3
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger("jarvis.vision")

# ---------------------------------------------------------------------------
# Wikipedia endpoints
# ---------------------------------------------------------------------------

WIKI_API  = "https://en.wikipedia.org/w/api.php"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"

# Cache TTLs (seconds)
CACHE_TTL_STABLE = 30 * 24 * 3600   # 30 days — encyclopedic facts
CACHE_TTL_EVENTS = 3600              # 1 hour  — current-events articles

RATE_LIMIT_DELAY = 1.1               # minimum seconds between Wikipedia requests


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

@dataclass
class VisionResponse:
    confidence: str           # "high" | "medium" | "low" | "uncertain"
    answer: str
    source: str               # "wikipedia" | "knowledge_db" | "internal"
    wikipedia_url: Optional[str] = None
    follow_up: Optional[str]  = None


# ---------------------------------------------------------------------------
# VisionAgent
# ---------------------------------------------------------------------------

class VisionAgent:
    """Standalone knowledge agent with Wikipedia integration and persistent learning."""

    def __init__(self, db_path: str, lang: str = "en"):
        self.db_path  = db_path
        self.lang     = lang
        self._rate_lock        = asyncio.Lock()
        self._last_request     = 0.0
        self._active           = False
        self._total_queries    = 0   # session counter for usage %
        self._init_db()
        log.info(f"VISION online — db: {db_path}")

    # ------------------------------------------------------------------
    # DB bootstrap
    # ------------------------------------------------------------------

    def _init_db(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    question            TEXT    NOT NULL,
                    normalized_question TEXT    NOT NULL,
                    answer              TEXT    NOT NULL,
                    source              TEXT    DEFAULT 'wikipedia',
                    wikipedia_url       TEXT,
                    confidence          TEXT    DEFAULT 'medium',
                    follow_up           TEXT,
                    created_at          REAL    NOT NULL,
                    last_accessed       REAL    NOT NULL,
                    access_count        INTEGER DEFAULT 1,
                    user_feedback       INTEGER DEFAULT 0
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    normalized_question, answer,
                    content='knowledge', content_rowid='id'
                );

                -- Keep FTS in sync with the base table
                CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                    INSERT INTO knowledge_fts(rowid, normalized_question, answer)
                    VALUES (new.id, new.normalized_question, new.answer);
                END;

                CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, normalized_question, answer)
                    VALUES ('delete', old.id, old.normalized_question, old.answer);
                    INSERT INTO knowledge_fts(rowid, normalized_question, answer)
                    VALUES (new.id, new.normalized_question, new.answer);
                END;

                CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, normalized_question, answer)
                    VALUES ('delete', old.id, old.normalized_question, old.answer);
                END;

                CREATE TABLE IF NOT EXISTS wiki_cache (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    query      TEXT    UNIQUE NOT NULL,
                    title      TEXT,
                    summary    TEXT,
                    url        TEXT,
                    cached_at  REAL    NOT NULL,
                    expires_at REAL    NOT NULL
                );
            """)
            conn.commit()

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def _normalize(self, text: str) -> str:
        """Lowercase, strip punctuation, collapse whitespace."""
        text = text.lower().strip()
        text = unicodedata.normalize("NFKD", text)
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _trim_to_sentences(self, text: str, n: int = 3) -> str:
        """Return the first n sentences of text."""
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return " ".join(parts[:n])

    # ------------------------------------------------------------------
    # SQLite helpers (sync — called via run_in_executor)
    # ------------------------------------------------------------------

    def _db_lookup(self, normalized_q: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT k.* FROM knowledge k "
                "JOIN knowledge_fts f ON k.id = f.rowid "
                "WHERE knowledge_fts MATCH ? ORDER BY rank LIMIT 3",
                (normalized_q,),
            ).fetchall()
            if not rows:
                return None
            best = rows[0]
            if best["user_feedback"] < 0:
                return None
            conn.execute(
                "UPDATE knowledge SET last_accessed=?, access_count=access_count+1 WHERE id=?",
                (time.time(), best["id"]),
            )
            conn.commit()
            return dict(best)

    def _cache_lookup(self, query: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM wiki_cache WHERE query=? AND expires_at > ?",
                (query.lower(), time.time()),
            ).fetchone()
            return dict(row) if row else None

    def _cache_store(self, query: str, title: str, summary: str, url: str,
                     ttl: float = CACHE_TTL_STABLE):
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO wiki_cache"
                "(query, title, summary, url, cached_at, expires_at) VALUES (?,?,?,?,?,?)",
                (query.lower(), title, summary, url, now, now + ttl),
            )
            conn.commit()

    def _store_knowledge(self, question: str, answer: str, source: str,
                         wikipedia_url: Optional[str], confidence: str,
                         follow_up: Optional[str]):
        now = time.time()
        normalized = self._normalize(question)
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM knowledge WHERE normalized_question=?", (normalized,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE knowledge SET answer=?, source=?, wikipedia_url=?, "
                    "confidence=?, follow_up=?, last_accessed=?, "
                    "access_count=access_count+1 WHERE id=?",
                    (answer, source, wikipedia_url, confidence, follow_up, now, existing[0]),
                )
            else:
                conn.execute(
                    "INSERT INTO knowledge(question, normalized_question, answer, source, "
                    "wikipedia_url, confidence, follow_up, created_at, last_accessed) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (question, normalized, answer, source,
                     wikipedia_url, confidence, follow_up, now, now),
                )
            conn.commit()

    def _update_feedback(self, normalized_q: str, feedback_val: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE knowledge SET user_feedback=? WHERE normalized_question=?",
                (feedback_val, normalized_q),
            )
            conn.commit()

    def _count_knowledge(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]

    # ------------------------------------------------------------------
    # Rate-limited HTTP
    # ------------------------------------------------------------------

    async def _rate_request(self, client: httpx.AsyncClient,
                            url: str, **kwargs) -> httpx.Response:
        async with self._rate_lock:
            wait = RATE_LIMIT_DELAY - (time.time() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            resp = await client.get(url, **kwargs)
            self._last_request = time.time()
            return resp

    # ------------------------------------------------------------------
    # Wikipedia helpers
    # ------------------------------------------------------------------

    async def _wiki_search(self, client: httpx.AsyncClient, query: str) -> list[str]:
        try:
            resp = await self._rate_request(
                client, WIKI_API,
                params={
                    "action": "query", "list": "search",
                    "srsearch": query, "format": "json",
                    "srlimit": 3, "utf8": 1,
                },
                timeout=6.0,
            )
            data = resp.json()
            return [r["title"] for r in data.get("query", {}).get("search", [])]
        except Exception as exc:
            log.warning(f"VISION search failed: {exc}")
            return []

    async def _wiki_summary(self, client: httpx.AsyncClient,
                            title: str) -> Optional[dict]:
        """Fetch REST summary for a title; checks cache first."""
        cached = self._cache_lookup(title)
        if cached:
            log.debug(f"VISION cache hit: '{title}'")
            return {**cached, "type": "cached"}

        try:
            url  = WIKI_REST.format(title.replace(" ", "_"))
            resp = await self._rate_request(client, url, timeout=8.0)
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                log.warning(f"VISION Wikipedia HTTP {resp.status_code} for '{title}'")
                return None
            data = resp.json()

            if data.get("type") == "disambiguation":
                return {"title": title, "summary": None,
                        "url": "", "type": "disambiguation"}

            raw     = data.get("extract", "").strip()
            summary = self._trim_to_sentences(raw, 3) if raw else None
            if not summary:
                return None

            article_url = (data.get("content_urls", {})
                           .get("desktop", {}).get("page", ""))
            result = {
                "title":   data.get("title", title),
                "summary": summary,
                "url":     article_url,
                "type":    "standard",
            }
            self._cache_store(title, result["title"], summary, article_url)
            return result

        except Exception as exc:
            log.warning(f"VISION summary failed for '{title}': {exc}")
            return None

    # ------------------------------------------------------------------
    # Question classification
    # ------------------------------------------------------------------

    def _extract_search_query(self, question: str) -> str:
        """Strip question words to get a clean Wikipedia search term."""
        q = question.strip().rstrip("?")
        # Remove leading question patterns
        patterns = [
            r"^(who is|who was|who are|who were)\s+",
            r"^(what is|what are|what was|what were)\s+(a|an|the)?\s*",
            r"^(when (did|was|were|is|are))\s+",
            r"^(where (is|was|are|were|did))\s+",
            r"^(how (does|do|did|is|are|was|were))\s+",
            r"^(why (does|do|did|is|are|was|were))\s+",
            r"^(tell me about|explain|describe|define)\s+",
            r"^(can you explain|can you tell me about)\s+",
        ]
        for pat in patterns:
            q = re.sub(pat, "", q, flags=re.IGNORECASE).strip()
        return q if q else question

    def _classify(self, question: str) -> str:
        q = question.lower()
        if any(w in q for w in ["difference between", "compare", "vs ", "versus"]):
            return "comparative"
        if any(w in q for w in ["how does", "how do", "why does", "why do",
                                 "explain", "what causes", "how is"]):
            return "explanatory"
        if any(w in q for w in ["weather", "today", "current", "right now",
                                 "latest news", "happening now"]):
            return "current_events"
        if any(w in q for w in ["should i", "is it better", "recommend",
                                 "best way", "which is better"]):
            return "opinion"
        return "factual"

    def _follow_up(self, question: str, article_title: str) -> Optional[str]:
        q = question.lower()
        if "who" in q:
            return f"Would you like to know more about {article_title}?"
        if "what is" in q or "what are" in q:
            return f"Shall I elaborate on {article_title}?"
        if "when" in q:
            return f"Would you like the full history of {article_title}?"
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ask(self, question: str) -> VisionResponse:
        """Answer a knowledge question. Main entry point."""
        self._active        = True
        self._total_queries += 1
        log.info(f"VISION ← {question!r}")

        try:
            # 1. Check local knowledge DB (fastest path)
            loop = asyncio.get_event_loop()
            norm = self._normalize(question)
            stored = await loop.run_in_executor(None, self._db_lookup, norm)
            if stored and stored.get("confidence") in ("high", "medium"):
                log.info("VISION: knowledge DB hit")
                return VisionResponse(
                    confidence=stored["confidence"],
                    answer=stored["answer"],
                    source="knowledge_db",
                    wikipedia_url=stored.get("wikipedia_url"),
                    follow_up=stored.get("follow_up"),
                )

            # Opinion questions — no Wikipedia lookup needed
            q_type = self._classify(question)
            if q_type == "opinion":
                return VisionResponse(
                    confidence="low",
                    answer="That's somewhat subjective, sir — I can offer facts on both sides if you'd like.",
                    source="internal",
                )

            # 2. Wikipedia lookup
            search_query = self._extract_search_query(question)
            async with httpx.AsyncClient(
                headers={"User-Agent": "JARVIS-VISION/1.0 (jarvis-assistant)"},
                timeout=httpx.Timeout(10.0),
            ) as client:
                titles = await self._wiki_search(client, search_query)

                # Retry with raw question if extracted query yields nothing
                if not titles and search_query != question:
                    titles = await self._wiki_search(client, question)

                if not titles:
                    return VisionResponse(
                        confidence="uncertain",
                        answer="Wikipedia appears to be unavailable, sir. I'm unable to verify that right now.",
                        source="internal",
                    )

                # Try each candidate until we get a usable summary
                wiki = None
                for title in titles:
                    result = await self._wiki_summary(client, title)
                    if result and result.get("type") in ("standard", "cached") \
                            and result.get("summary"):
                        wiki = result
                        break

                if not wiki:
                    return VisionResponse(
                        confidence="uncertain",
                        answer="I found related articles but couldn't extract a clear answer, sir. Could you clarify the topic?",
                        source="internal",
                    )

            summary     = wiki["summary"]
            source_url  = wiki.get("url", "")
            article_ttl = wiki.get("title", titles[0])

            # Confidence: high if first search result matches the question closely
            q_words     = set(norm.split())
            title_words = set(self._normalize(titles[0]).split())
            overlap     = q_words & title_words
            confidence  = "high" if len(overlap) >= 2 else "medium"

            follow_up = self._follow_up(question, article_ttl)

            response = VisionResponse(
                confidence=confidence,
                answer=summary,
                source="wikipedia",
                wikipedia_url=source_url,
                follow_up=follow_up,
            )

            # Persist — fire and forget in executor so we don't block
            await loop.run_in_executor(
                None, self._store_knowledge,
                question, summary, "wikipedia", source_url, confidence, follow_up,
            )

            log.info(f"VISION → {confidence} confidence from Wikipedia")
            return response

        except Exception as exc:
            log.error(f"VISION error: {exc}", exc_info=True)
            return VisionResponse(
                confidence="uncertain",
                answer="I encountered an error retrieving that, sir. Please try again shortly.",
                source="internal",
            )
        finally:
            self._active = False

    async def feedback(self, question: str, is_correct: bool):
        """Record explicit user feedback on a stored answer."""
        normalized   = self._normalize(question)
        feedback_val = 1 if is_correct else -1
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._update_feedback, normalized, feedback_val)
        verdict = "correct" if is_correct else "incorrect"
        log.info(f"VISION feedback: {verdict} for {question!r}")

    def get_status(self) -> dict:
        """Return agent status for /api/agents/status."""
        if self._active:
            # Processing — show high activity (60-100%)
            usage = min(100, 60 + min(40, self._total_queries * 5))
        else:
            # Standby — show 40% so the reactor ring has a visible fill
            usage = 40
        return {"online": True, "usage": usage}

    def get_knowledge_count(self) -> int:
        """Return the number of stored knowledge entries."""
        return self._count_knowledge()
