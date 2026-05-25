"""
VISION — Knowledge Agent for JARVIS

Primary source  : Offline Kiwix Server (Local Wikipedia @ http://127.0.0.1:8080)
Secondary source: Local SQLite knowledge DB (vision_knowledge.db)
Fallback        : Internal response with "uncertain" confidence

VISION is standalone — it does not depend on any other JARVIS module.
JARVIS calls vision_agent.ask(question) and receives a VisionResponse.

OFFLINE MODE: VISION queries local Wikipedia without internet connection.
Languages: English, Tamil, Malayalam
"""

import asyncio
import logging
import re
import sqlite3
import time
import unicodedata
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List

import httpx

log = logging.getLogger("jarvis.vision")

# ---------------------------------------------------------------------------
# Kiwix Offline Server Configuration
# ---------------------------------------------------------------------------

KIWIX_SERVER_URL = "http://127.0.0.1:8080"

# NOTE: Kiwix /search endpoint rejects multi-language setups with "confusion of tongues".
# VISION uses direct article lookup: /content/{book_path}/A/{title}
# Book paths are auto-discovered from /catalog/v2/entries on startup.

# Language config — maps short lang code to human name and ZIM language tag
LANGUAGE_CONFIG = {
    "en":    {"name": "English Wikipedia",  "zim_lang": "eng"},
    "en-US": {"name": "English Wikipedia",  "zim_lang": "eng"},
    "ta":    {"name": "Tamil Wikipedia",    "zim_lang": "tam"},
    "ta-IN": {"name": "Tamil Wikipedia",    "zim_lang": "tam"},
    "ml":    {"name": "Malayalam Wikipedia","zim_lang": "mal"},
    "ml-IN": {"name": "Malayalam Wikipedia","zim_lang": "mal"},
}

# Fallback to live Wikipedia if Kiwix is unavailable (disabled by default)
USE_LIVE_WIKIPEDIA_FALLBACK = False

# Live Wikipedia endpoints (used only if Kiwix unavailable)
WIKI_API_LIVE  = "https://en.wikipedia.org/w/api.php"
WIKI_REST_LIVE = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"

# Cache TTLs (seconds)
CACHE_TTL_STABLE = 30 * 24 * 3600
CACHE_TTL_EVENTS = 3600

RATE_LIMIT_DELAY = 0.3  # local server — no internet rate limiting needed


# ---------------------------------------------------------------------------
# Response dataclass
# ---------------------------------------------------------------------------

@dataclass
class VisionResponse:
    confidence: str           # "high" | "medium" | "low" | "uncertain"
    answer: str
    source: str               # "kiwix" | "wikipedia_live" | "knowledge_db" | "internal"
    wikipedia_url: Optional[str] = None
    source_language: Optional[str] = None  # "English" | "Tamil" | "Malayalam"
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
    # Kiwix Offline Server Helpers
    # ------------------------------------------------------------------

    async def _is_kiwix_available(self, client: httpx.AsyncClient) -> bool:
        """Check if Kiwix server is running by fetching root (returns 200 or 302)."""
        try:
            resp = await client.get(KIWIX_SERVER_URL, timeout=httpx.Timeout(2.0),
                                    follow_redirects=False)
            return resp.status_code in (200, 302)
        except Exception:
            return False

    async def _discover_book_paths(self, client: httpx.AsyncClient) -> Dict[str, str]:
        """
        Discover available ZIM book content paths from Kiwix catalog.
        Returns dict like {"eng": "/content/wikipedia_en_all_maxi_2026-02", ...}
        """
        try:
            resp = await client.get(
                f"{KIWIX_SERVER_URL}/catalog/v2/entries?count=50",
                timeout=httpx.Timeout(3.0),
            )
            if resp.status_code != 200:
                return {}

            xml = resp.text
            # Parse <language> and <link type="text/html" href="/content/..."/>
            entries: Dict[str, str] = {}
            # Split into entry blocks
            for block in re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL):
                lang_match = re.search(r'<language>([^<]+)</language>', block)
                href_match = re.search(r'<link type="text/html" href="([^"]+)"', block)
                if lang_match and href_match:
                    lang = lang_match.group(1).strip()   # e.g. "eng", "tam", "mal"
                    href = href_match.group(1).strip()   # e.g. "/content/wikipedia_en_all_maxi_2026-02"
                    entries[lang] = href
                    log.info(f"Kiwix book discovered: {lang} → {href}")
            return entries
        except Exception as e:
            log.warning(f"Kiwix catalog discovery failed: {e}")
            return {}

    async def _try_start_kiwix(self) -> bool:
        """Attempt to start Kiwix server automatically."""
        kiwix_paths = [
            r"C:\Program Files\Kiwix\kiwix-serve.exe",
            r"C:\Program Files (x86)\Kiwix\kiwix-serve.exe",
            "kiwix-serve",
        ]
        zim_dir = r"D:\JARVIS_WIKI\Kiwix"
        for kiwix_bin in kiwix_paths:
            try:
                subprocess.Popen(
                    [kiwix_bin, "--port", "8080", f"{zim_dir}\\*.zim"],
                    stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                )
                log.info(f"Started Kiwix server: {kiwix_bin}")
                await asyncio.sleep(2.5)
                return True
            except FileNotFoundError:
                continue
            except Exception as e:
                log.warning(f"Kiwix start failed ({kiwix_bin}): {e}")
        return False

    def _question_to_titles(self, question: str, lang_code: str = "en") -> List[str]:
        """
        Generate Wikipedia article title candidates from a natural language question.
        Returns a list of titles to try, in order of likelihood.
        """
        # Strip question words to get topic
        q = question.strip().rstrip("?!.")
        patterns = [
            r"^(who is|who was|who are|who were)\s+",
            r"^(what is|what are|what was|what were)\s+(a |an |the )?",
            r"^(when (did|was|were|is|are))\s+",
            r"^(where (is|was|are|were|did))\s+",
            r"^(how (does|do|did|is|are|was|were))\s+",
            r"^(why (does|do|did|is|are|was|were))\s+",
            r"^(tell me about|explain|describe|define)\s+",
            r"^(what('s| is) the (capital|population|history|meaning) of)\s+",
        ]
        for pat in patterns:
            q = re.sub(pat, "", q, flags=re.IGNORECASE).strip()

        candidates = []

        # As-is (preserves original query words)
        if q:
            candidates.append(q)

        # Title Case
        titled = q.title()
        if titled != q:
            candidates.append(titled)

        # Underscored (Wikipedia URL format)
        underscored = q.replace(" ", "_")
        candidates.append(underscored)

        # Title-cased + underscored
        candidates.append(titled.replace(" ", "_"))

        # Capitalise first letter only
        cap = q[0].upper() + q[1:] if q else q
        candidates.append(cap)

        # Deduplicate preserving order
        seen: set = set()
        result = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                result.append(c)
        return result

    async def _kiwix_fetch_article(
        self,
        client: httpx.AsyncClient,
        book_path: str,
        title: str,
    ) -> Optional[Dict]:
        """
        Fetch an article from offline Kiwix by title.
        Tries /A/{title} first (Wikipedia ZIM convention) then /{title}.
        Returns {"title", "summary", "url", "type":"kiwix"} or None.
        """
        encoded = title.replace(" ", "_")
        urls_to_try = [
            f"{KIWIX_SERVER_URL}{book_path}/A/{encoded}",
            f"{KIWIX_SERVER_URL}{book_path}/{encoded}",
        ]

        for url in urls_to_try:
            try:
                resp = await client.get(url, timeout=httpx.Timeout(5.0),
                                        follow_redirects=True)
                if resp.status_code != 200:
                    continue

                html = resp.text

                # Skip disambiguation/error pages
                page_title_match = re.search(r'<title>([^<]+)</title>', html)
                page_title = page_title_match.group(1) if page_title_match else title
                if any(w in page_title.lower() for w in
                       ("not found", "invalid request", "error", "disambiguation")):
                    continue

                # Strip scripts, styles, tables (infoboxes), nav boxes
                html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
                html = re.sub(r'<style[^>]*>.*?</style>',  '', html, flags=re.DOTALL)
                html = re.sub(r'<table[^>]*>.*?</table>',  '', html, flags=re.DOTALL)
                html = re.sub(r'<nav[^>]*>.*?</nav>',      '', html, flags=re.DOTALL)

                # Collect substantive <p> paragraphs
                raw_paras = re.findall(r'<p[^>]*>(.*?)</p>', html, flags=re.DOTALL)
                clean_paras = []
                for p in raw_paras:
                    text = re.sub(r'<[^>]+>', '', p)        # strip HTML tags
                    text = re.sub(r'\[\d+\]', '', text)     # strip [1], [2] citations
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 60:                       # skip stub/nav lines
                        clean_paras.append(text)

                if not clean_paras:
                    continue

                # Join first 3 paragraphs, cap at 600 chars
                summary = " ".join(clean_paras[:3])
                if len(summary) > 600:
                    summary = summary[:597] + "..."

                return {
                    "title":   page_title.strip(),
                    "summary": summary,
                    "url":     str(resp.url),
                    "type":    "kiwix",
                }
            except Exception as e:
                log.debug(f"Kiwix fetch error ({url}): {e}")
                continue

        return None

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
    # Wikipedia helpers (Live fallback - for when Kiwix is unavailable)
    # ------------------------------------------------------------------

    async def _wiki_search_live(self, client: httpx.AsyncClient, query: str) -> list[str]:
        """Search live Wikipedia (fallback only)."""
        try:
            resp = await self._rate_request(
                client, WIKI_API_LIVE,
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
            log.warning(f"VISION live Wikipedia search failed: {exc}")
            return []

    async def _wiki_summary_live(self, client: httpx.AsyncClient,
                            title: str) -> Optional[dict]:
        """Fetch REST summary for a title from live Wikipedia; checks cache first."""
        cached = self._cache_lookup(title)
        if cached:
            log.debug(f"VISION cache hit: '{title}'")
            return {**cached, "type": "cached"}

        try:
            url  = WIKI_REST_LIVE.format(title.replace(" ", "_"))
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

    def _is_system_question(self, question: str) -> bool:
        """Check if this is a system/PC/hardware/diagnostics question."""
        q = question.lower()
        system_keywords = [
            "cpu", "memory", "ram", "disk", "hard drive", "ssd",
            "temperature", "temp", "cpu temp", "overheating", "overheat",
            "slow", "laggy", "lag", "crash", "crash", "freeze", "frozen",
            "performance", "bottleneck", "bottlenecking",
            "process", "service", "application", "app",
            "driver", "drivers", "bios", "firmware",
            "resource", "resources", "usage", "utilization",
            "windows", "system", "pc", "computer", "machine",
            "fix", "repair", "issue", "problem", "error", "trouble",
            "diagnose", "diagnosis", "health", "health check",
            "optimize", "optimization", "speed up", "cleanup",
            "storage", "cache", "temp files", "garbage",
        ]
        return any(keyword in q for keyword in system_keywords)

    async def _get_system_context(self) -> str:
        """Get current system diagnostics context."""
        try:
            from agents.diagnostics import get_system_diagnostician
            from agents.system_info import get_system_info_gatherer

            loop = asyncio.get_event_loop()
            diagnostician = get_system_diagnostician()
            gatherer = get_system_info_gatherer()

            # Run diagnostics in executor to avoid blocking
            diag_summary = await loop.run_in_executor(None, diagnostician.get_summary_for_vision)
            sys_summary = await loop.run_in_executor(None, gatherer.get_system_summary)

            return f"{diag_summary}\n\n{sys_summary}"
        except Exception as e:
            log.warning(f"Failed to get system context: {e}")
            return ""

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

    async def ask(self, question: str, include_system_context: bool = False) -> VisionResponse:
        """Answer a knowledge question. Main entry point.

        If include_system_context=True, enriches response with current system diagnostics
        for PC/hardware/issue-related questions.
        """
        self._active        = True
        self._total_queries += 1
        log.info(f"VISION ← {question!r}")

        try:
            # Check if this is a system/diagnostics question
            is_system_question = self._is_system_question(question)

            # 1. Check local knowledge DB (fastest path)
            loop = asyncio.get_event_loop()
            norm = self._normalize(question)
            stored = await loop.run_in_executor(None, self._db_lookup, norm)
            if stored and stored.get("confidence") in ("high", "medium"):
                log.info("VISION: knowledge DB hit")
                answer = stored["answer"]

                # Enrich with system context if this is a system question
                if is_system_question and include_system_context:
                    system_context = await self._get_system_context()
                    if system_context:
                        answer = f"{answer}\n\n[CURRENT SYSTEM STATE]\n{system_context}"

                return VisionResponse(
                    confidence=stored["confidence"],
                    answer=answer,
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

            # 2. Offline Kiwix lookup (primary) — direct article access
            # Kiwix /search API rejects multi-language setups; VISION uses
            # title-based direct lookup: /content/{book_path}/A/{title}
            lang_code = self.lang.split("-")[0] if "-" in self.lang else self.lang
            zim_lang  = LANGUAGE_CONFIG.get(self.lang, LANGUAGE_CONFIG.get(lang_code, {})).get("zim_lang", "eng")
            source_language = LANGUAGE_CONFIG.get(self.lang, LANGUAGE_CONFIG.get(lang_code, {})).get("name", "English Wikipedia")

            async with httpx.AsyncClient(
                headers={"User-Agent": "JARVIS-VISION/1.0 (jarvis-assistant)"},
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
            ) as client:
                # 2a. Check Kiwix availability
                kiwix_available = await self._is_kiwix_available(client)

                if not kiwix_available:
                    log.warning("Kiwix server not reachable — attempting auto-start...")
                    started = await self._try_start_kiwix()
                    if started:
                        kiwix_available = await self._is_kiwix_available(client)

                if kiwix_available:
                    # 2b. Discover which book path to use for this language
                    book_paths = await self._discover_book_paths(client)
                    book_path  = book_paths.get(zim_lang)

                    if not book_path:
                        # Fallback: try known naming pattern
                        for zl, path in book_paths.items():
                            if zl == zim_lang:
                                book_path = path
                                break
                        if not book_path and book_paths:
                            # Use English Wikipedia if no exact match
                            book_path = book_paths.get("eng", next(iter(book_paths.values())))

                    if book_path:
                        # 2c. Generate article title candidates and try each
                        search_query = self._extract_search_query(question)
                        title_candidates = self._question_to_titles(search_query, lang_code)

                        # Also try the raw question stripped of question words
                        if question != search_query:
                            title_candidates += self._question_to_titles(question, lang_code)

                        wiki = None
                        for candidate in title_candidates:
                            wiki = await self._kiwix_fetch_article(client, book_path, candidate)
                            if wiki and wiki.get("summary"):
                                break

                        if wiki and wiki.get("summary"):
                            summary     = wiki["summary"]
                            source_url  = wiki.get("url", "")
                            article_ttl = wiki.get("title", search_query)

                            q_words     = set(norm.split())
                            title_words = set(self._normalize(article_ttl).split())
                            overlap     = q_words & title_words
                            confidence  = "high" if len(overlap) >= 2 else "medium"
                            follow_up   = self._follow_up(question, article_ttl)

                            answer = summary
                            if is_system_question and include_system_context:
                                system_context = await self._get_system_context()
                                if system_context:
                                    answer = f"{answer}\n\n[CURRENT SYSTEM STATE]\n{system_context}"

                            response = VisionResponse(
                                confidence=confidence,
                                answer=answer,
                                source="kiwix",
                                source_language=source_language,
                                wikipedia_url=source_url,
                                follow_up=follow_up,
                            )

                            await loop.run_in_executor(
                                None, self._store_knowledge,
                                question, summary, "kiwix", source_url, confidence, follow_up,
                            )

                            log.info(f"VISION → {confidence} from offline {source_language} ({article_ttl!r})")
                            return response

                        # Book found but article not matched — return no-result
                        log.info("VISION: Kiwix article not found for this query")
                        return VisionResponse(
                            confidence="uncertain",
                            answer="I could not find information on that topic in my offline Wikipedia collection.",
                            source="internal",
                        )

                # Kiwix unavailable and fallback disabled
                if not kiwix_available and not USE_LIVE_WIKIPEDIA_FALLBACK:
                    return VisionResponse(
                        confidence="uncertain",
                        answer="Offline Wikipedia server is not running. Please start Kiwix and try again.",
                        source="internal",
                    )

                if USE_LIVE_WIKIPEDIA_FALLBACK:
                    log.info("Falling back to live Wikipedia")
                    titles = await self._wiki_search_live(client, search_query)

                    # Retry with raw question if extracted query yields nothing
                    if not titles and search_query != question:
                        titles = await self._wiki_search_live(client, question)

                    if not titles:
                        return VisionResponse(
                            confidence="uncertain",
                            answer="Wikipedia appears to be unavailable, sir. I'm unable to verify that right now.",
                            source="internal",
                        )

                    # Try each candidate until we get a usable summary
                    wiki = None
                    for title in titles:
                        result = await self._wiki_summary_live(client, title)
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

                    summary = wiki["summary"]
                    source_url = wiki.get("url", "")
                    article_ttl = wiki.get("title", titles[0])

                    q_words = set(norm.split())
                    title_words = set(self._normalize(titles[0]).split())
                    overlap = q_words & title_words
                    confidence = "high" if len(overlap) >= 2 else "medium"

                    follow_up = self._follow_up(question, article_ttl)

                    answer = summary
                    # Enrich with system context if this is a system question
                    if is_system_question and include_system_context:
                        system_context = await self._get_system_context()
                        if system_context:
                            answer = f"{answer}\n\n[CURRENT SYSTEM STATE]\n{system_context}"

                    response = VisionResponse(
                        confidence=confidence,
                        answer=answer,
                        source="wikipedia_live",
                        wikipedia_url=source_url,
                        follow_up=follow_up,
                    )

                    # Persist to knowledge DB
                    await loop.run_in_executor(
                        None, self._store_knowledge,
                        question, summary, "wikipedia_live", source_url, confidence, follow_up,
                    )

                    log.info(f"VISION → {confidence} confidence from live Wikipedia")
                    return response

            return VisionResponse(
                confidence="uncertain",
                answer="I could not find information on that topic in my offline Wikipedia collection.",
                source="internal",
            )

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
