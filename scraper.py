#!/usr/bin/env python3
"""
apache-jira-scraper: Scrapes Apache Jira issues for chosen projects,
handles pagination, retries, rate limits, resume via checkpointing,
transforms to JSONL with derived tasks suitable for LLM training.

Usage:
    python scraper.py
"""

import requests
import json
import time
import logging
import os
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from tqdm import tqdm
from dateutil import parser as dateparser

# -------------------------
# Configuration
# -------------------------
PROJECTS = ["HADOOP", "SPARK", "KAFKA"]  # Change these 3 projects if you prefer
OUTPUT_DIR = "data"
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "checkpoints.json")
MAX_RESULTS = 50          # Jira maxResults per query page
REQUEST_TIMEOUT = 15      # seconds
SLEEP_BETWEEN_PAGES = 1.0 # seconds (politeness)
JIRA_SEARCH_API = "https://issues.apache.org/jira/rest/api/2/search"
USER_AGENT = "apache-jira-scraper/1.0 (email: you@example.com)"  # change email optionally

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------
# Checkpoint helpers
# -------------------------
def load_checkpoints(path=CHECKPOINT_PATH):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                logger.warning("Corrupt checkpoint file; starting fresh.")
                return {}
    return {}

def save_checkpoints(checkpoints, path=CHECKPOINT_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(checkpoints, f, indent=2)

# -------------------------
# Utility: safe field extraction
# -------------------------
def safe_get(d, *keys, default=None):
    """Safe nested get in dicts; returns default if any key missing or None."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur or cur[k] is None:
            return default
        cur = cur[k]
    return cur

# -------------------------
# Derived tasks (simple deterministic rules)
# -------------------------
def derive_summary(text, max_sentences=2):
    """Simple summarizer: first N sentences (rule-based)."""
    if not text:
        return ""
    # naive split on punctuation
    sentences = [s.strip() for s in text.replace("\r"," ").split(".") if s.strip()]
    return ". ".join(sentences[:max_sentences]) + ("." if len(sentences) >= 1 else "")

def derive_classification(title, description, labels):
    """Rule-based classification into categories using keywords and labels."""
    text = " ".join(filter(None, [title or "", description or ""])).lower()
    if labels:
        labels_text = " ".join(labels).lower()
    else:
        labels_text = ""
    # define categories and keywords
    categories = {
        "bug": ["bug", "error", "exception", "stacktrace", "crash", "fail"],
        "feature_request": ["feature", "enhance", "improve", "support", "add"],
        "documentation": ["doc", "documentation", "readme", "guide", "docs"],
        "performance": ["performance", "slow", "optimi", "latency"],
        "configuration": ["config", "configuration", "setting", "property"],
        "test": ["test", "unit test", "integration test", "flaky"],
    }
    # score categories
    scores = {k: 0 for k in categories}
    for k, keywords in categories.items():
        for kw in keywords:
            if kw in text or kw in labels_text:
                scores[k] += 1
    # choose best non-zero or 'other'
    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] > 0 else "other"

def derive_qna(title, description, comments):
    """
    Rule-based QnA generation:
    - make 1-2 Q/A pairs:
      * Q1: "What is the issue?" -> A1: title + short summary
      * Q2: "What is current status or resolution?" -> tries to extract from description/comments
    """
    qna = []
    if title or description:
        q = "What is the issue described?"
        a = (title or "") + (" - " + derive_summary(description) if description else "")
        qna.append({"q": q, "a": a.strip()})
    # Q2: status-ish info from comments or description
    if comments:
        # pick the last substantive comment as 'resolution' guess
        last_comment = ""
        for c in reversed(comments):
            if c and len(c.strip()) > 10:
                last_comment = c.strip()
                break
        if last_comment:
            q2 = "What updates or decisions were made in the discussion?"
            qna.append({"q": q2, "a": last_comment})
    return qna

# -------------------------
# Request handling with retries & backoff
# -------------------------
class HTTPError(Exception):
    pass

@retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5)
)
def safe_get_json(url, params=None, headers=None, timeout=REQUEST_TIMEOUT):
    """Perform GET and return JSON; retry on network errors or 5xx/429 handled explicitly."""
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    resp = requests.get(url, params=params, headers=h, timeout=timeout)
    status = resp.status_code
    if status == 429:
        # Respect Retry-After if present
        ra = resp.headers.get("Retry-After")
        wait_for = int(ra) if ra and ra.isdigit() else None
        if wait_for:
            logger.warning(f"Received 429. Respecting Retry-After: sleeping {wait_for}s.")
            time.sleep(wait_for)
        else:
            logger.warning("Received 429. Sleeping 10s (no Retry-After).")
            time.sleep(10)
        raise HTTPError("429 rate limited; retrying")
    if 500 <= status < 600:
        logger.warning(f"Server error {status}; will retry.")
        raise HTTPError(f"Server error {status}")
    if status != 200:
        # non-recoverable client error for many codes (but we raise so tenacity retries few times)
        logger.error(f"HTTP {status} for URL {resp.url}")
        raise HTTPError(f"HTTP {status}")
    try:
        return resp.json()
    except ValueError:
        logger.error("Invalid JSON response.")
        raise HTTPError("Invalid JSON")

# -------------------------
# Scrape single project
# -------------------------
def scrape_project(project, start_at=0, max_results=MAX_RESULTS, checkpoint=None):
    """
    Scrape up to 200 issues for a single project from start_at onward.
    Returns list of transformed issue dicts and final start_at value.
    """
    out_items = []
    total = None
    cur = start_at
    limit = 200  # limit to 200 issues per project

    pbar = None
    first_iteration = True

    while True:
        # stop if we already collected 200 issues
        if len(out_items) >= limit:
            logger.info(f"Reached 200 issue limit for project {project}. Stopping early.")
            break

        params = {
            "jql": f"project={project} ORDER BY created ASC",
            "startAt": cur,
            "maxResults": max_results,
            "fields": "summary,description,comment,labels,priority,status,reporter,assignee,created,updated"
        }

        try:
            data = safe_get_json(JIRA_SEARCH_API, params=params)
        except Exception as e:
            logger.exception(f"Failed to fetch issues for {project} at startAt={cur}: {e}")
            return out_items, cur  # return partial data

        if first_iteration:
            total = data.get("total")
            total_to_fetch = min(total or limit, limit)
            pbar = tqdm(total=total_to_fetch, desc=f"Scraping {project}", unit="issue")
            first_iteration = False

        issues = data.get("issues", [])
        if not issues:
            logger.info(f"No more issues returned for {project} (startAt {cur}).")
            break

        for issue in issues:
            if len(out_items) >= limit:
                break  # stop immediately after reaching 200

            try:
                key = issue.get("key")
                fields = issue.get("fields", {}) or {}
                title = safe_get(fields, "summary", default=None)
                description = safe_get(fields, "description", default=None)
                status = safe_get(fields, "status", "name", default=None)
                priority = safe_get(fields, "priority", "name", default=None)
                reporter = safe_get(fields, "reporter", "displayName", default=None)
                assignee = safe_get(fields, "assignee", "displayName", default=None)
                labels = fields.get("labels") or []
                created = safe_get(fields, "created", default=None)
                updated = safe_get(fields, "updated", default=None)
                comments_obj = safe_get(fields, "comment", default={})
                comments_list = []

                if comments_obj and isinstance(comments_obj, dict):
                    for c in comments_obj.get("comments", []) or []:
                        body = c.get("body")
                        if body:
                            comments_list.append(body)

                transformed = {
                    "project": project,
                    "issue_id": key,
                    "title": title,
                    "status": status,
                    "priority": priority,
                    "reporter": reporter,
                    "assignee": assignee,
                    "labels": labels,
                    "created": created,
                    "updated": updated,
                    "description": description,
                    "comments": comments_list,
                    "derived": {
                        "summary": derive_summary(description or ""),
                        "classification": derive_classification(title, description, labels),
                        "qna": derive_qna(title, description, comments_list)
                    }
                }

                out_items.append(transformed)
                pbar.update(1)
            except Exception:
                logger.exception(f"Failed to transform issue {issue.get('key')}. Skipping.")
                continue

        # advance cursor
        cur += len(issues)
        if checkpoint is not None:
            checkpoint[project] = cur
            save_checkpoints(checkpoint)

        time.sleep(SLEEP_BETWEEN_PAGES)

        if total is not None and cur >= total:
            break

    if pbar:
        pbar.close()
    return out_items, cur


# -------------------------
# Writing JSONL output
# -------------------------
def write_jsonl(items, path):
    count = 0
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
            count += 1
    logger.info(f"Wrote {count} items to {path}")

# -------------------------
# Main driver
# -------------------------
def main():
    checkpoints = load_checkpoints()
    for project in PROJECTS:
        logger.info(f"Starting scrape for project: {project}")
        start_at = checkpoints.get(project, 0)
        out_file = os.path.join(OUTPUT_DIR, f"{project.lower()}_issues.jsonl")
        items, final_pos = scrape_project(project, start_at=start_at, checkpoint=checkpoints)
        if items:
            write_jsonl(items, out_file)
        # update checkpoint to final position (meaning pages processed)
        checkpoints[project] = final_pos
        save_checkpoints(checkpoints)
        logger.info(f"Completed page processing for {project}. Next startAt: {final_pos}")

if __name__ == "__main__":
    main()
