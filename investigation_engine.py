import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
import re
import json
import math
import requests
import xml.etree.ElementTree as ET

from groq import Groq
from urllib.parse import quote
from bs4 import BeautifulSoup


# ==========================================
# TRACKBACK - INVESTIGATION ENGINE
# ==========================================

GROQ_MODEL = "openai/gpt-oss-20b"

HEADERS = {
    "User-Agent": "TRACKBACK-FactChecker/1.0 (educational project)"
}

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


# ==========================================
# 1. GROQ CLIENT
# ==========================================

def get_groq_client():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise Exception("GROQ_API_KEY is missing.")

    return Groq(api_key=api_key)


# ==========================================
# 2. EXTRACT KEYWORDS
# ==========================================

def extract_keywords(claim):

    stop_words = {
        "the", "is", "are", "was", "were", "a", "an",
        "and", "or", "to", "of", "in", "on", "for",
        "with", "that", "this", "it", "as", "by",
        "from", "at", "be", "has", "have", "had",
        "does", "do", "did", "will", "would", "could",
        "should", "can", "not", "there", "their",
        "ಭಾರತವು", "ಎಂದು", "ಮತ್ತು", "ಇದೆ"
    }

    words = re.findall(
        r"[\u0C80-\u0CFF]+|[a-zA-Z0-9]+",
        claim.lower()
    )

    keywords = []

    for word in words:
        if word not in stop_words and len(word) > 1:
            if word not in keywords:
                keywords.append(word)

    return keywords


# ==========================================
# 3. TRANSLATE KANNADA CLAIM
# ==========================================

def translate_kannada_claim(claim):

    kannada_pattern = re.compile(r"[\u0C80-\u0CFF]")

    if not kannada_pattern.search(claim):
        return claim

    try:

        client = get_groq_client()

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the given Kannada factual claim "
                        "into clear English. Return only the translation."
                    )
                },
                {
                    "role": "user",
                    "content": claim
                }
            ],
            temperature=0,
            max_tokens=150
        )

        translated = (
            response.choices[0].message.content or ""
        ).strip()

        if translated:
            print("Kannada translation:", translated, flush=True)
            return translated

    except Exception as error:

        print(
            "Kannada translation error:",
            repr(error),
            flush=True
        )

    return claim


# ==========================================
# 4. GOOGLE NEWS SEARCH
# ==========================================

def search_google_news(claim, english_claim=None):

    search_claim = english_claim or claim

    results = []
    seen_urls = set()

    queries = [search_claim]

    if claim != search_claim:
        queries.append(claim)

    for query in queries:

        try:

            print("Google News query:", query, flush=True)

            rss_url = (
                "https://news.google.com/rss/search?q="
                + quote(query)
                + "&hl=en-IN&gl=IN&ceid=IN:en"
            )

            response = requests.get(
                rss_url,
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):

                title = item.findtext("title", "").strip()
                url = item.findtext("link", "").strip()
                description = item.findtext(
                    "description", ""
                ).strip()

                snippet = BeautifulSoup(
                    description,
                    "html.parser"
                ).get_text(" ", strip=True)

                if not title or not url:
                    continue

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "content": "",
                    "source_type": "News"
                })

                if len(results) >= 10:
                    break

            if len(results) >= 10:
                break

        except Exception as error:

            print(
                "Google News search error:",
                repr(error),
                flush=True
            )

    print(
        "Google News results found:",
        len(results),
        flush=True
    )

    return results


# ==========================================
# 5. WIKIPEDIA SEARCH AND CONTENT
# ==========================================

def search_wikipedia(claim):

    print("Searching Wikipedia for:", claim, flush=True)

    results = []

    try:

        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": claim,
            "format": "json",
            "srlimit": 10
        }

        response = requests.get(
            WIKIPEDIA_API,
            params=search_params,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        search_data = response.json()

        search_results = (
            search_data.get("query", {}).get("search", [])
        )

        if not search_results:
            return []

        page_ids = []

        for item in search_results:

            title = item.get("title", "")
            page_id = item.get("pageid")

            if not title or not page_id:
                continue

            snippet = BeautifulSoup(
                item.get("snippet", ""),
                "html.parser"
            ).get_text(" ", strip=True)

            page_url = (
                "https://en.wikipedia.org/wiki/"
                + quote(title.replace(" ", "_"))
            )

            results.append({
                "title": title,
                "url": page_url,
                "snippet": snippet,
                "content": "",
                "source_type": "Wikipedia"
            })

            page_ids.append(str(page_id))

        if not page_ids:
            return results

        try:

            content_params = {
                "action": "query",
                "pageids": "|".join(page_ids),
                "prop": "extracts",
                "explaintext": 1,
                "exchars": 5000,
                "format": "json"
            }

            content_response = requests.get(
                WIKIPEDIA_API,
                params=content_params,
                headers=HEADERS,
                timeout=30
            )

            content_response.raise_for_status()

            pages = (
                content_response.json()
                .get("query", {})
                .get("pages", {})
            )

            for item, page_id in zip(results, page_ids):

                page = pages.get(page_id, {})

                item["content"] = page.get("extract", "")

        except Exception as error:

            print(
                "Wikipedia content retrieval error:",
                repr(error),
                flush=True
            )

        print(
            "Wikipedia pages collected:",
            len(results),
            flush=True
        )

        return results

    except Exception as error:

        print(
            "Wikipedia search error:",
            repr(error),
            flush=True
        )

        return results


# ==========================================
# 6. EXTRACT WEBPAGE CONTENT
# ==========================================

def extract_source_content(url):

    try:

        if not url:
            return ""

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        for element in soup([
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "noscript",
            "iframe"
        ]):
            element.decompose()

        content = soup.get_text(
            separator=" ",
            strip=True
        )

        return content[:5000]

    except Exception as error:

        print(
            "Source extraction error:",
            url,
            repr(error),
            flush=True
        )

        return ""


# ==========================================
# 7. SOURCE RELEVANCE CHECK
# ==========================================

def check_source_relevance(claim, title, snippet, content):

    source_text = (
        f"{title} {snippet} {content}"
    ).lower()

    stop_words = {
        "the", "is", "are", "was", "were", "a", "an",
        "and", "or", "to", "of", "in", "on", "for",
        "with", "that", "this", "it", "as", "by",
        "from", "at", "be", "has", "have", "had",
        "does", "do", "did", "will", "would", "could",
        "should", "can"
    }

    claim_words = [
        word.lower()
        for word in re.findall(r"[a-zA-Z]+", claim)
        if len(word) > 2 and word.lower() not in stop_words
    ]

    if not claim_words:
        return False

    matched_words = [
        word for word in claim_words
        if word in source_text
    ]

    # A source must have a reasonable keyword overlap.
    # This is only a retrieval filter, NOT proof of relevance.
    match_ratio = len(matched_words) / len(claim_words)

    is_relevant = (
        len(matched_words) >= 1
        and match_ratio >= 0.25
    )

    print(
        "Source relevance:",
        title,
        "| Matches:",
        matched_words,
        "| Accepted:",
        is_relevant,
        flush=True
    )

    return is_relevant


# ==========================================
# 8. IDENTIFY SOURCE
# ==========================================

def identify_source(url):

    url = (url or "").lower()

    if "wikipedia.org" in url:
        return "Wikipedia"

    if "news.google.com" in url:
        return "Google News"

    if "pib.gov.in" in url:
        return "Press Information Bureau"

    if "gov.in" in url:
        return "Government Source"

    return "Web Source"


# ==========================================
# 9. SAFE JSON EXTRACTION
# ==========================================

def extract_json_response(response_text):

    response_text = (response_text or "").strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Handle JSON wrapped inside Markdown code fences.
    match = re.search(
        r"\{[\s\S]*\}",
        response_text
    )

    if match:

        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ==========================================
# 10. EVIDENCE COMPARISON USING AI
# ==========================================

def compare_evidence_with_ai(claim, evidence):

    comparison = {
        "supporting": [],
        "contradicting": [],
        "inconclusive": [],
        "summary": "",
        "verdict": "Insufficient Evidence"
    }

    if not evidence:

        comparison["summary"] = (
            "No relevant source evidence was collected. "
            "A reliable comparison cannot be performed."
        )

        return comparison

    try:

        client = get_groq_client()

        source_list = []

        for index, item in enumerate(evidence[:10], start=1):

            source_list.append({
                "id": index,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "content": item.get("content", "")[:2500]
            })

        prompt = f"""
You are the evidence comparison component of TRACKBACK.

Your task is to compare sources against the claim.

CLAIM:
{claim}

SOURCES:
{json.dumps(source_list, ensure_ascii=False)}

For EVERY source, assign exactly one category:

1. supporting:
The source provides information that directly supports the claim.

2. contradicting:
The source provides information that directly challenges the claim.

3. inconclusive:
The source is related but does not establish whether the claim is true or false,
or the available information is insufficient.

IMPORTANT RULES:

- Evaluate the actual information in each source.
- Do not classify a source using its title or keywords alone.
- Do not invent facts or source details.
- Do not assume that missing information means the claim is false.
- Do not treat Wikipedia as an official government source.
- If a source does not contain enough information, classify it as inconclusive.
- A source can be classified only once.
- Include every supplied source ID exactly once.
- The final verdict must reflect the evidence as a whole.
- If evidence is weak or mixed, prefer Insufficient Evidence.
- Use Partially Supported when the evidence supports only some important parts.
- Do not invent statistics or confidence percentages.

Return ONLY valid JSON in this format:

{{
  "summary": "Short explanation of the comparison",
  "verdict": "Supported, Contradicted, Partially Supported, or Insufficient Evidence",
  "results": [
    {{
      "id": 1,
      "category": "supporting",
      "reason": "Explain what this source says and how it relates to the claim"
    }}
  ]
}}
"""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful evidence comparison assistant. "
                        "Use only the supplied sources. Never fabricate evidence. "
                        "Return valid JSON only."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            max_tokens=1800
        )

        ai_text = (
            response.choices[0].message.content or ""
        ).strip()

        data = extract_json_response(ai_text)

        if not data:
            raise Exception(
                "The AI returned an invalid JSON comparison."
            )

        comparison["summary"] = str(
            data.get("summary", "")
        )

        allowed_verdicts = {
            "Supported",
            "Contradicted",
            "Partially Supported",
            "Insufficient Evidence"
        }

        ai_verdict = str(
            data.get("verdict", "")
        ).strip()

        if ai_verdict in allowed_verdicts:
            comparison["verdict"] = ai_verdict

        # Map source IDs back to the original collected evidence.
        source_map = {
            index: item
            for index, item in enumerate(evidence[:10], start=1)
        }

        assigned_ids = set()

        for result in data.get("results", []):

            try:
                source_id = int(result.get("id"))
            except (ValueError, TypeError):
                continue

            if source_id not in source_map:
                continue

            if source_id in assigned_ids:
                continue

            category = str(
                result.get("category", "")
            ).lower().strip()

            if category not in {
                "supporting",
                "contradicting",
                "inconclusive"
            }:
                category = "inconclusive"

            original = source_map[source_id]

            classified_item = {
                "title": original.get("title", ""),
                "url": original.get("url", ""),
                "snippet": original.get("snippet", ""),
                "source_type": original.get("source_type", ""),
                "reason": str(result.get("reason", "")).strip()
            }

            comparison[category].append(classified_item)

            assigned_ids.add(source_id)

        # Any source not classified by the AI remains inconclusive.
        for source_id, original in source_map.items():

            if source_id in assigned_ids:
                continue

            comparison["inconclusive"].append({
                "title": original.get("title", ""),
                "url": original.get("url", ""),
                "snippet": original.get("snippet", ""),
                "source_type": original.get("source_type", ""),
                "reason": (
                    "This source was not conclusively classified "
                    "by the AI and requires manual review."
                )
            })

        print(
            "Evidence comparison completed:",
            "Supporting =", len(comparison["supporting"]),
            "| Contradicting =", len(comparison["contradicting"]),
            "| Inconclusive =", len(comparison["inconclusive"]),
            flush=True
        )

        return comparison

    except Exception as error:

        print(
            "Evidence comparison error:",
            repr(error),
            flush=True
        )

        # Never discard collected evidence when AI comparison fails.
        for item in evidence[:10]:

            comparison["inconclusive"].append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", ""),
                "source_type": item.get("source_type", ""),
                "reason": (
                    "AI comparison could not be completed. "
                    "Please review this source manually."
                )
            })

        comparison["summary"] = (
            "The sources were collected, but AI could not "
            "complete their comparison. The sources are "
            "provided for manual review."
        )

        return comparison


# ==========================================
# 11. AI ANALYSIS TEXT
# ==========================================

def analyze_evidence_with_ai(claim, evidence):

    comparison = compare_evidence_with_ai(
        claim,
        evidence
    )

    lines = [
        "CLAIM SUMMARY",
        claim,
        "",
        "SUPPORTING EVIDENCE"
    ]

    if comparison["supporting"]:

        for item in comparison["supporting"]:
            lines.append(
                "- " + item["title"] + ": " + item["reason"]
            )

    else:
        lines.append("No supporting evidence established.")

    lines.extend([
        "",
        "CONTRADICTING EVIDENCE"
    ])

    if comparison["contradicting"]:

        for item in comparison["contradicting"]:
            lines.append(
                "- " + item["title"] + ": " + item["reason"]
            )

    else:
        lines.append("No contradicting evidence established.")

    lines.extend([
        "",
        "INCONCLUSIVE EVIDENCE"
    ])

    if comparison["inconclusive"]:

        for item in comparison["inconclusive"]:
            lines.append(
                "- " + item["title"] + ": " + item["reason"]
            )

    else:
        lines.append("No inconclusive sources.")

    lines.extend([
        "",
        "COMPARISON SUMMARY",
        comparison["summary"],
        "",
        "FINAL VERDICT",
        comparison["verdict"]
    ])

    return "\n".join(lines)


# ==========================================
# 12. EXTRACT FINAL VERDICT
# ==========================================

def extract_verdict(ai_analysis):

    text = (ai_analysis or "").lower()

    if "partially supported" in text:
        return "Partially Supported"

    if "insufficient evidence" in text:
        return "Insufficient Evidence"

    if re.search(r"\bcontradicted\b", text):
        return "Contradicted"

    if re.search(r"\bnot supported\b", text):
        return "Contradicted"

    if re.search(r"\bsupported\b", text):
        return "Supported"

    return "Insufficient Evidence"


# ==========================================
# 13. MAIN INVESTIGATION FUNCTION
# ==========================================

def investigate_claim(claim):

    print(
        "\n========== TRACKBACK INVESTIGATION ==========",
        flush=True
    )

    print("Original claim:", claim, flush=True)

    keywords = extract_keywords(claim)

    english_claim = translate_kannada_claim(claim)

    print(
        "Investigation search claim:",
        english_claim,
        flush=True
    )

    # Search Google News
    print("Searching Google News...", flush=True)

    news_evidence = search_google_news(
        claim,
        english_claim
    )

    # Search Wikipedia
    wikipedia_evidence = search_wikipedia(
        english_claim
    )

    # Combine and remove duplicate URLs
    candidates = []
    seen_urls = set()

    for item in news_evidence + wikipedia_evidence:

        source_url = item.get("url", "")

        if source_url and source_url not in seen_urls:

            seen_urls.add(source_url)
            candidates.append(item)

    print(
        "Total candidate sources:",
        len(candidates),
        flush=True
    )

    # Collect relevant candidate sources
    analyzed_evidence = []

    for item in candidates:

        source_url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")

        if not source_url:
            continue

        source_content = item.get("content", "")

        if (
            not source_content
            and "wikipedia.org" not in source_url
        ):
            source_content = extract_source_content(
                source_url
            )

        print(
            "\nChecking source:",
            title,
            flush=True
        )

        is_relevant = check_source_relevance(
            english_claim,
            title,
            snippet,
            source_content
        )

        if not is_relevant:
            continue

        analyzed_evidence.append({
            "title": title,
            "url": source_url,
            "snippet": snippet,
            "source_type": item.get(
                "source_type",
                identify_source(source_url)
            ),
            "content": source_content
        })

    print(
        "\nRelevant candidate sources:",
        len(analyzed_evidence),
        flush=True
    )

    # Perform evidence comparison.
    evidence_comparison = compare_evidence_with_ai(
        english_claim,
        analyzed_evidence
    )

    # Generate readable analysis from the comparison.
    ai_analysis = analyze_comparison_text(
        claim,
        evidence_comparison
    )

    status = evidence_comparison["verdict"]

    # Short dashboard analysis.
    analysis = evidence_comparison["summary"]

    if not analysis:
        analysis = (
            "TRACKBACK collected "
            + str(len(analyzed_evidence))
            + " candidate sources for investigation. "
            "Please review the evidence and original sources."
        )

    print(
        "\nFINAL TRACKBACK STATUS:",
        status,
        flush=True
    )

    print(
        "============================================\n",
        flush=True
    )

    return {
        "status": status,
        "analysis": analysis,
        "keywords": keywords,
        "evidence": analyzed_evidence,
        "ai_analysis": ai_analysis,
        "evidence_comparison": evidence_comparison
    }


# ==========================================
# 14. BUILD COMPARISON TEXT
# ==========================================

def analyze_comparison_text(claim, comparison):

    lines = [
        "CLAIM:",
        claim,
        "",
        "SUPPORTING EVIDENCE:"
    ]

    if comparison["supporting"]:

        for item in comparison["supporting"]:
            lines.append(
                "- "
                + item["title"]
                + ": "
                + item["reason"]
            )

    else:
        lines.append("No supporting evidence established.")

    lines.extend([
        "",
        "CONTRADICTING EVIDENCE:"
    ])

    if comparison["contradicting"]:

        for item in comparison["contradicting"]:
            lines.append(
                "- "
                + item["title"]
                + ": "
                + item["reason"]
            )

    else:
        lines.append("No contradicting evidence established.")

    lines.extend([
        "",
        "INCONCLUSIVE EVIDENCE:"
    ])

    if comparison["inconclusive"]:

        for item in comparison["inconclusive"]:
            lines.append(
                "- "
                + item["title"]
                + ": "
                + item["reason"]
            )

    else:
        lines.append("No inconclusive sources.")

    lines.extend([
        "",
        "COMPARISON SUMMARY:",
        comparison["summary"],
        "",
        "FINAL VERDICT:",
        comparison["verdict"]
    ])

    return "\n".join(lines)


# ==========================================
# 15. VOICE TRANSCRIPTION
# ==========================================

def transcribe_voice(audio_file, filename):

    """Convert recorded voice into text using Groq Whisper."""

    try:

        client = get_groq_client()

        audio_data = audio_file.read()

        if not audio_data:
            raise Exception("The recording is empty.")

        transcription = client.audio.transcriptions.create(
            file=(filename, audio_data),
            model="whisper-large-v3",
            response_format="json",
            temperature=0.0
        )

        return transcription.text.strip()

    except Exception as error:

        print(
            "Voice transcription error:",
            repr(error),
            flush=True
        )

        raise Exception(
            "Could not transcribe the voice message: "
            + str(error)
        )

