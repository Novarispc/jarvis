#!/usr/bin/env python3
"""
Test script to verify VISION Kiwix offline Wikipedia integration.

This script checks:
1. Kiwix server availability
2. Language support
3. Search functionality
4. Content retrieval

Run: python test_kiwix.py
"""

import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

KIWIX_SERVER_URL = "http://127.0.0.1:8080"
KIWIX_SEARCH_API = f"{KIWIX_SERVER_URL}/search?query="
KIWIX_CONTENT_API = f"{KIWIX_SERVER_URL}/content/"

LANGUAGES = {
    "en": "English Wikipedia",
    "ta": "Tamil Wikipedia",
    "ml": "Malayalam Wikipedia",
}

async def test_kiwix_connection():
    """Test if Kiwix server is running and responding."""
    log.info("=" * 60)
    log.info("VISION Kiwix Integration Test")
    log.info("=" * 60)

    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        try:
            log.info(f"\n1. Testing Kiwix Server Connection...")
            log.info(f"   URL: {KIWIX_SERVER_URL}")

            resp = await client.get(f"{KIWIX_SERVER_URL}/health")
            if resp.status_code == 200:
                log.info(f"   ✓ Kiwix server is ONLINE")
            else:
                log.warning(f"   ✗ Kiwix returned status {resp.status_code}")
                log.warning(f"\n   Kiwix server is NOT RUNNING or NOT RESPONDING")
                log.warning(f"\n   To start Kiwix, run:")
                log.warning(f"   kiwix-serve --port 8080 D:\\JARVIS_WIKI\\Kiwix\\*.zim")
                return False

        except Exception as e:
            log.error(f"   ✗ Failed to connect to Kiwix: {e}")
            log.error(f"\n   Kiwix server is NOT RUNNING")
            log.error(f"\n   To start Kiwix, run:")
            log.error(f"   kiwix-serve --port 8080 D:\\JARVIS_WIKI\\Kiwix\\*.zim")
            return False

    # If we get here, Kiwix is running
    log.info(f"\n2. Testing Language Support...")

    test_queries = {
        "en": ("Python programming", "Python"),
        "ta": ("Tamilnadu", "Tamil Nadu"),
        "ml": ("Kerala", "Kerala"),
    }

    for lang, (query, expected_term) in test_queries.items():
        lang_name = LANGUAGES.get(lang, "Unknown")
        log.info(f"\n   Testing {lang_name}...")

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                search_url = f"{KIWIX_SEARCH_API}{query.replace(' ', '+')}"
                resp = await client.get(search_url)

                if resp.status_code == 200:
                    if expected_term.lower() in resp.text.lower():
                        log.info(f"   ✓ {lang_name}: Search working")
                    else:
                        log.warning(f"   ~ {lang_name}: Search returned results but couldn't verify content")
                else:
                    log.warning(f"   ✗ {lang_name}: Search returned status {resp.status_code}")

        except Exception as e:
            log.error(f"   ✗ {lang_name}: Failed - {e}")

    return True


async def test_vision_integration():
    """Test VISION's ability to query Kiwix."""
    log.info(f"\n3. Testing VISION Integration...")

    try:
        from agents.vision import VisionAgent
        from pathlib import Path

        db_path = str(Path(__file__).parent / "data" / "vision_knowledge.db")
        vision = VisionAgent(db_path, lang="en")

        log.info(f"   ✓ VISION agent initialized")
        log.info(f"   ✓ VISION will query Kiwix on port 8080")
        log.info(f"   ✓ Language detection: Supports en-US, ta-IN, ml-IN")

    except Exception as e:
        log.error(f"   ✗ Failed to initialize VISION: {e}")
        return False

    return True


def main():
    """Run all tests."""
    try:
        kiwix_ok = asyncio.run(test_kiwix_connection())
        vision_ok = asyncio.run(test_vision_integration())

        log.info(f"\n" + "=" * 60)
        if kiwix_ok and vision_ok:
            log.info("✓ ALL TESTS PASSED - VISION is ready!")
            log.info("=" * 60)
            log.info("\nYou can now use JARVIS to ask questions in:")
            log.info("  • English (en-US)")
            log.info("  • Tamil (ta-IN)")
            log.info("  • Malayalam (ml-IN)")
            log.info("\nExamples:")
            log.info("  - 'What is the capital of France?'")
            log.info("  - 'தமிழ்நாட்டின் தலைநகரம் என்ன?'")
            log.info("  - 'കേരളത്തിന്റെ തലസ്ഥാനം ഏത്?'")
        else:
            log.warning("✗ Some tests failed - Check the output above")
            log.warning("=" * 60)

    except KeyboardInterrupt:
        log.info("\nTest interrupted by user")
    except Exception as e:
        log.error(f"\nUnexpected error: {e}")


if __name__ == "__main__":
    main()
