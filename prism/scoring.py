"""Deterministic ICP scoring.

The LLM (Agent 2) extracts structured `ICPSignals` — categorical classifications
plus per-signal confidence + evidence. This module turns those signals into a
0-100 score, a tier, and the full `ICPAnalysis` payload.

Why mechanical scoring (and not LLM-emitted points):

  - **Auditable.** The formula lives in code. Read this file and you know
    exactly how every score is computed.
  - **Reproducible.** Same signals → same score. Zero LLM variance on the math.
  - **Tunable.** Re-weight a factor by editing a constant. No prompt change,
    no re-eval of every prior account.
  - **Testable.** `score_company(synthetic_signals) == expected_total` is a
    real unit test. LLM-emitted scoring isn't.
  - **A/B-able.** Ship multiple `SCORING_VERSION`s, route different cohorts,
    measure which scoring predicts win rate better.

The LLM still does the *hard* part — reading scraped content and classifying
each factor. It just doesn't do arithmetic.
"""

from __future__ import annotations

from .models import (
    ICPAnalysis,
    ICPSignals,
    ScoreBreakdown,
    ScoreFactor,
)

# Bump when the scoring formula changes. Stored on records so old scores
# remain comparable to today's, and downstream eval can hold version constant.
SCORING_VERSION = "v1.0"


# Below this score we skip BOTH the copywriter and the Sanity write.
# Rationale:
#   - Auto-generated copy on a misfit pollutes the marketer queue.
#   - A Sanity doc with empty copy fields looks broken in Studio.
#   - The ICP analysis is still valuable for "don't pursue" decisions — but
#     that data lives on HubSpot, where AEs can see it directly.
# Sub-floor accounts therefore land in HubSpot only (with ICP score, tier,
# reasoning, breakdown in custom properties). No Sanity doc. No public page.
COPY_SCORE_FLOOR = 50


# ============================================================
# Factor 1: Industry Fit  (max 30)
# ============================================================
INDUSTRY_POINTS = {
    "HEALTH_PLAN":              29,   # true ICP — national/regional/state plan
    "DIGITAL_HEALTH_CLINICAL":  25,   # telehealth, virtual care, specialty care
    "STAFFING_IPA_MSO":         19,   # healthcare staffing, IPA, MSO, network
    "ADJACENT_HEALTHCARE":      13,   # RCM, EHR, care coordination, analytics
    "HEALTHCARE_ADJACENT":       7,   # wellness, fitness, consumer health
    "NOT_HEALTHCARE":            2,   # everything else
}
INDUSTRY_MAX = 30


# ============================================================
# Factor 2: Scale Signals  (max 25)
# ============================================================
# Base band → points. Bonuses below stack on top, capped at SCALE_MAX.
SCALE_BAND_POINTS = {
    "OVER_1M":      22,
    "100K_TO_1M":   17,
    "10K_TO_100K":  11,
    "UNDER_10K":     6,
    "PRE_REVENUE":   2,
    "UNKNOWN":      10,    # conservative midpoint when scale isn't stated
}
SCALE_ENTERPRISE_BONUS = 3   # has named enterprise customer(s)
SCALE_NAMED_CUSTOMER_BONUS = 1   # has any named customers
SCALE_MAX = 25


# ============================================================
# Factor 3: Provider Network  (max 25)
# ============================================================
NETWORK_POINTS = {
    "RUNS_MULTI_STATE_NETWORK":  24,
    "MANAGES_FOR_PARTNERS":      19,
    "PROVIDERS_PERIPHERAL":      13,
    "TANGENTIAL":                 7,
    "NONE":                       2,
}
NETWORK_MAX = 25


# ============================================================
# Factor 4: Growth & Maturity  (max 10)
# ============================================================
GROWTH_POINTS = {
    "HYPER_GROWTH":          10,
    "ACTIVE_GROWTH":          7,
    "STABLE":                 4,
    "FLAT_OR_CONTRACTING":    1,
}
GROWTH_MAX = 10


# ============================================================
# Factor 5: Buying Readiness  (max 10)
# ============================================================
READINESS_POINTS = {
    "EXPLICIT":          10,
    "STRONG_THEMES":      7,
    "ADJACENT_THEMES":    4,
    "NONE":               1,
}
READINESS_MAX = 10


# ============================================================
# Tier thresholds (inclusive lower bound)
# ============================================================
TIER_THRESHOLDS = [
    ("A", 90),
    ("B", 70),
    ("C", 40),
    ("D",  0),
]


# ============================================================
# Confidence weights (must sum to 1.0)
# Used to roll signal-level confidences up to an overall score_confidence.
# Weights mirror the factor caps so confidence on big factors counts more.
# ============================================================
CONFIDENCE_WEIGHTS = {
    "industry":         0.30,
    "scale":            0.25,
    "provider_network": 0.25,
    "growth":           0.10,
    "buying_readiness": 0.10,
}


# ============================================================
# Pure functions — each factor is independently testable
# ============================================================

def _score_industry(signal) -> ScoreFactor:
    return ScoreFactor(
        score=INDUSTRY_POINTS[signal.category],
        rationale=f"[{signal.category}] {signal.evidence}",
        confidence=signal.confidence,
    )


def _score_scale(signal) -> ScoreFactor:
    pts = SCALE_BAND_POINTS[signal.member_count_band]
    if signal.has_enterprise_customers:
        pts += SCALE_ENTERPRISE_BONUS
    elif signal.has_named_customers:
        pts += SCALE_NAMED_CUSTOMER_BONUS
    pts = min(pts, SCALE_MAX)
    return ScoreFactor(
        score=pts,
        rationale=f"[{signal.member_count_band}"
                  + (", enterprise customers" if signal.has_enterprise_customers else "")
                  + (", named customers" if signal.has_named_customers and not signal.has_enterprise_customers else "")
                  + f"] {signal.evidence}",
        confidence=signal.confidence,
    )


def _score_network(signal) -> ScoreFactor:
    return ScoreFactor(
        score=NETWORK_POINTS[signal.network_type],
        rationale=f"[{signal.network_type}] {signal.evidence}",
        confidence=signal.confidence,
    )


def _score_growth(signal) -> ScoreFactor:
    return ScoreFactor(
        score=GROWTH_POINTS[signal.stage],
        rationale=f"[{signal.stage}] {signal.evidence}",
        confidence=signal.confidence,
    )


def _score_readiness(signal) -> ScoreFactor:
    return ScoreFactor(
        score=READINESS_POINTS[signal.level],
        rationale=f"[{signal.level}] {signal.evidence}",
        confidence=signal.confidence,
    )


def _tier_for(total: int) -> str:
    for tier, threshold in TIER_THRESHOLDS:
        if total >= threshold:
            return tier
    return "D"


def _aggregate_confidence(signals: ICPSignals) -> int:
    return round(
        signals.industry.confidence         * CONFIDENCE_WEIGHTS["industry"]
        + signals.scale.confidence          * CONFIDENCE_WEIGHTS["scale"]
        + signals.provider_network.confidence * CONFIDENCE_WEIGHTS["provider_network"]
        + signals.growth.confidence         * CONFIDENCE_WEIGHTS["growth"]
        + signals.buying_readiness.confidence * CONFIDENCE_WEIGHTS["buying_readiness"]
    )


def _compose_reasoning(breakdown: ScoreBreakdown, total: int, tier: str) -> str:
    parts = [
        f"Total {total} → Tier {tier}.",
        f"Industry {breakdown.industry_fit.score}/{INDUSTRY_MAX}.",
        f"Scale {breakdown.scale_signals.score}/{SCALE_MAX}.",
        f"Network {breakdown.provider_network_signal.score}/{NETWORK_MAX}.",
        f"Growth {breakdown.growth_maturity.score}/{GROWTH_MAX}.",
        f"Readiness {breakdown.buying_readiness.score}/{READINESS_MAX}.",
    ]
    out = " ".join(parts)
    return out[:400]


# ============================================================
# Public entry point
# ============================================================

def score_company(signals: ICPSignals) -> ICPAnalysis:
    """Turn LLM-extracted signals into the full ICPAnalysis. Deterministic."""
    breakdown = ScoreBreakdown(
        industry_fit            = _score_industry(signals.industry),
        scale_signals           = _score_scale(signals.scale),
        provider_network_signal = _score_network(signals.provider_network),
        growth_maturity         = _score_growth(signals.growth),
        buying_readiness        = _score_readiness(signals.buying_readiness),
    )

    total = (
        breakdown.industry_fit.score
        + breakdown.scale_signals.score
        + breakdown.provider_network_signal.score
        + breakdown.growth_maturity.score
        + breakdown.buying_readiness.score
    )
    tier = _tier_for(total)

    return ICPAnalysis(
        icp_score=total,
        icp_tier=tier,
        icp_reasoning=_compose_reasoning(breakdown, total, tier),
        score_breakdown=breakdown,
        score_confidence=_aggregate_confidence(signals),
        intent_themes=signals.intent_themes,
        pain_points=signals.pain_points,
        missing_data=signals.missing_data,
    )
