"""
Content Machine — Main Orchestrator
=====================================
21-Agent Automated Content System
Python + Claude API
Run: python main.py
"""

import os
import sys
import traceback
from datetime import datetime

# Fix Windows console encoding (terminal only, skip if stdout lacks reconfigure)
if hasattr(sys.stdout, "reconfigure") and getattr(sys.stdout, "encoding", "utf-8") != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from shared_memory.memory import init_article, get_state, save_published, get_pipeline_summary

# ── All 21 Agents ─────────────────────────────────────────────────
from agents import (
    ag00_fanout,
    ag01_researcher,
    ag02_strategist,
    ag03_writer,
    ag04_info_gain,
    ag05_voice_guard,
    ag06_geo,
    ag07_schema,
    ag08_engagement,
    ag09_multimodal,
    ag10_technical,
    ag11_entity,
    ag12_dedup,
    ag13_links,
    ag14_freshness,
    ag15_quality_gate,
    ag16_indexing,
    ag17_repurpose,
    ag18_feedback,
    ag19_gap_detector,
    ag20_experience,
)


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _banner():
    print("\n" + "═" * 64)
    print("  CONTENT MACHINE — 21 Agent System")
    print("  Python + Claude API  |  output → output/articles/")
    print("═" * 64)


def _phase(num: str, title: str):
    print(f"\n{'─' * 64}")
    print(f"  PHASE {num}  —  {title}")
    print(f"{'─' * 64}")


def _run_agent(label: str, fn, *args, **kwargs):
    """Run one agent with error handling. Returns result or None on failure."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"\n  ⚠ [{label}] ERROR: {e}")
        print(f"  Continuing pipeline... (check logs for details)")
        return None


def _save_article(state: dict) -> str:
    """Write article markdown and schema to output/articles/."""
    os.makedirs("output/articles", exist_ok=True)
    slug = state["keyword"].replace(" ", "_").lower()
    date = datetime.now().strftime("%Y%m%d")

    md_path = f"output/articles/{slug}_{date}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        h1 = state.get("outline", {}).get("h1", state["keyword"])
        f.write(f"# {h1}\n\n")
        f.write(state.get("draft", ""))

    schema_html = state.get("schema_html", "")
    if schema_html:
        schema_path = f"output/articles/{slug}_{date}_schema.html"
        with open(schema_path, "w", encoding="utf-8") as f:
            f.write(schema_html)
        print(f"  Schema: {schema_path}")

    print(f"\n  ✅ Article saved: {md_path}")
    return md_path


def _get_experience_input() -> list[str]:
    """Collect 5 experience bullets from the user for AG·20."""
    print(f"\n{'─' * 64}")
    print("  AG·20 — EXPERIENCE FORMATTER")
    print("  Enter 5 experience bullets (press Enter to skip each).")
    print("  Type 'skip' to skip this entire step.")
    print(f"{'─' * 64}\n")

    prompts = [
        "1. What you did  (e.g. 'Used X tool for 3 months')",
        "2. Result you got (e.g. 'Traffic increased 47%')",
        "3. A mistake you made",
        "4. An unexpected discovery",
        "5. Your honest opinion",
    ]

    bullets = []
    for p in prompts:
        val = input(f"  {p}\n  → ").strip()
        if val.lower() == "skip":
            return []
        if val:
            bullets.append(val)

    return bullets


# ─────────────────────────────────────────────────────────────────
# GAP DETECTION (standalone, separate from article pipeline)
# ─────────────────────────────────────────────────────────────────

def run_gap_detection():
    """Run AG·19 to find content gaps and queue new keywords."""
    from shared_memory.memory import _load
    niche = input("  Niche to analyze: ").strip() or "general"

    existing = [v.get("keyword", "") for k, v in _load().items()
                if not k.startswith("_") and "keyword" in v]

    gaps = ag19_gap_detector.find_gaps(niche, existing)

    print(f"\n  High priority gaps ({len(gaps.get('high_priority_gaps', []))}):")
    for g in gaps.get("high_priority_gaps", []):
        print(f"  → [{g.get('estimated_difficulty')}] {g.get('keyword')}")

    print(f"\n  Quick wins ({len(gaps.get('quick_wins', []))}):")
    for w in gaps.get("quick_wins", []):
        print(f"  → {w.get('keyword')} ({w.get('action')})")

    print(f"\n  Total in queue: {gaps.get('queue_total', 0)}")

    use_next = input("\n  Use next queued keyword as input? (y/n): ").strip().lower()
    if use_next == "y":
        next_kw = ag19_gap_detector.get_next_keyword()
        if next_kw:
            return next_kw.get("keyword"), next_kw.get("niche", niche)
    return None, None


# ─────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────

def run_pipeline(
    keyword: str,
    niche: str = "general",
    skip_experience: bool = False,
    do_repurpose: bool = False,
    site_url: str = "",
):
    _banner()
    print(f"\n  Keyword : '{keyword}'")
    print(f"  Niche   : {niche}")

    article_id = init_article(keyword, niche)
    print(f"  ID      : {article_id}\n")

    max_retries = 2
    quality_pass = False
    output_path = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"\n  🔄 Retry attempt {attempt}/{max_retries}")

        # ── Phase 1: Input & Planning ─────────────────────────────
        if attempt == 0:
            _phase("1", "Input & Planning  [AG 00 → 02]")
            _run_agent("AG·00", ag00_fanout.run, article_id)
            _run_agent("AG·01", ag01_researcher.run, article_id)
            _run_agent("AG·02", ag02_strategist.run, article_id)

        # ── Phase 2: Content Creation ─────────────────────────────
        _phase("2", "Content Creation  [AG 03 → 08 + AG 20]")
        _run_agent("AG·03", ag03_writer.run, article_id)
        _run_agent("AG·04", ag04_info_gain.run, article_id)

        # AG·20 Experience — only collect bullets on first attempt
        # Bullets saved to memory, so retries reuse them automatically
        if not skip_experience and attempt == 0:
            bullets = _get_experience_input()
            if bullets:
                _run_agent("AG·20", ag20_experience.run, article_id, bullets)
            else:
                print("  [AG·20] Skipped.")
        elif not skip_experience and attempt > 0:
            # Retry — AG·20 reads bullets from memory automatically
            _run_agent("AG·20", ag20_experience.run, article_id)

        _run_agent("AG·05", ag05_voice_guard.run, article_id)
        _run_agent("AG·06", ag06_geo.run, article_id)
        _run_agent("AG·07", ag07_schema.run, article_id)
        _run_agent("AG·08", ag08_engagement.run, article_id)

        # ── Phase 3: Technical & Optimization ────────────────────
        _phase("3", "Technical & Optimization  [AG 09 → 14]")
        _run_agent("AG·09", ag09_multimodal.run, article_id)
        _run_agent("AG·10", ag10_technical.run, article_id, site_url=site_url)
        _run_agent("AG·11", ag11_entity.run, article_id)
        _run_agent("AG·12", ag12_dedup.run, article_id)
        _run_agent("AG·13", ag13_links.run, article_id)
        _run_agent("AG·14", ag14_freshness.run, article_id)

        # ── Phase 4: Quality Gate ─────────────────────────────────
        _phase("4", "Quality Gate  [AG 15]")
        result = ag15_quality_gate.run(article_id)
        verdict = result.get("verdict", "FAIL")
        total = result.get("total", 0)

        if verdict == "PASS":
            quality_pass = True
            break
        elif verdict == "FLAG":
            print(f"\n  ⚠️  Score {total}/110 — Flagged for review. Proceeding.")
            quality_pass = True
            break
        else:
            print(f"\n  ❌ Score {total}/110 — FAIL.")
            if attempt < max_retries:
                print("  Rewriting from GEO step (AG·06 → AG·08)...")
                _run_agent("AG·06", ag06_geo.run, article_id)
                _run_agent("AG·07", ag07_schema.run, article_id)
                _run_agent("AG·08", ag08_engagement.run, article_id)

    # ── Phase 5: Save & Distribute ────────────────────────────────
    _phase("5", "Save & Distribute  [AG 16 + AG 18]")
    state = get_state(article_id)
    output_path = _save_article(state)
    final_score = state.get("quality_result", {}).get("total", 0)

    _run_agent("AG·16", ag16_indexing.run, article_id,
               output_path=output_path, site_url=site_url)
    _run_agent("AG·18", ag18_feedback.run, article_id)

    save_published(article_id, output_path, final_score)

    # ── Optional: Repurpose ───────────────────────────────────────
    if do_repurpose:
        _phase("★", "Repurpose  [AG 17]")
        _run_agent("AG·17", ag17_repurpose.run, article_id)

    # ── Pipeline Summary ──────────────────────────────────────────
    pipeline_summary = get_pipeline_summary(article_id)
    agents_completed = len(pipeline_summary.get("agents_completed", []))
    all_warnings = pipeline_summary.get("warnings", [])

    print("\n" + "═" * 64)
    print("  PIPELINE COMPLETE")
    print("═" * 64)
    print(f"  Keyword         : {keyword}")
    print(f"  Article ID      : {article_id}")
    print(f"  Final Score     : {final_score}/110")
    print(f"  Agents Run      : {agents_completed}/21")
    print(f"  Status          : {'✅ PASS' if quality_pass else '⚠️  REVIEW NEEDED'}")
    print(f"  Output          : {output_path}")
    if all_warnings:
        print(f"\n  Warnings ({len(all_warnings)}):")
        for w in all_warnings[:5]:
            print(f"    ⚠ {w}")
    print("═" * 64 + "\n")

    return output_path


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main():
    _banner()
    print("\n  Welcome to Content Machine!")
    print()
    print("  [1] Write a new article")
    print("  [2] Run gap detection (AG·19)")
    print("  [3] View keyword queue")
    print()

    choice = input("  Choice (1/2/3, default: 1): ").strip() or "1"

    if choice == "3":
        ag19_gap_detector.view_queue()
        return

    if choice == "2":
        keyword, niche = run_gap_detection()
        if not keyword:
            print("  No keyword selected. Exit.")
            return
        skip_exp = input("  Skip AG·20 experience? (y/n, default: n): ").strip().lower()
        repurpose = input("  Repurpose to social? (y/n, default: n): ").strip().lower()
        site_url = input("  Site URL (optional): ").strip()
        run_pipeline(keyword, niche or "general", skip_exp == "y", repurpose == "y", site_url)
        return

    # Option 1: Manual keyword entry
    keyword = input("  Keyword: ").strip()
    if not keyword:
        print("  No keyword entered. Exit.")
        sys.exit(1)

    niche = input("  Niche (default: general): ").strip() or "general"
    skip_exp = input("  Skip AG·20 experience? (y/n, default: n): ").strip().lower()
    repurpose = input("  Repurpose to social? (y/n, default: n): ").strip().lower()
    site_url = input("  Site URL for indexing (optional): ").strip()

    run_pipeline(keyword, niche, skip_exp == "y", repurpose == "y", site_url)


if __name__ == "__main__":
    main()
