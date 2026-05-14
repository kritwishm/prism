from pydantic import BaseModel, Field
from typing import Literal, Optional


class PainPoint(BaseModel):
    pain: str
    evidence: str
    confidence: int = Field(
        ..., ge=0, le=100,
        description="0-100. How strongly the source evidence supports this being a real pain.",
    )


class IntentTheme(BaseModel):
    theme: str
    confidence: int = Field(
        ..., ge=0, le=100,
        description="0-100. How strongly the facts support buyer intent in this theme.",
    )


# ============================================================
# ICPSignals — what the LLM extracts (structured classifications, no points)
# ============================================================

class IndustrySignal(BaseModel):
    category: Literal[
        "HEALTH_PLAN",                 # national/regional/state health plan
        "DIGITAL_HEALTH_CLINICAL",     # telehealth, virtual care, specialty care w/ providers
        "STAFFING_IPA_MSO",            # healthcare staffing, IPA, MSO, network
        "ADJACENT_HEALTHCARE",         # RCM, EHR, care coordination, analytics
        "HEALTHCARE_ADJACENT",         # wellness, fitness, consumer health
        "NOT_HEALTHCARE",
    ]
    confidence: int = Field(..., ge=0, le=100)
    evidence: str


class ScaleSignal(BaseModel):
    member_count_band: Literal[
        "OVER_1M",          # 1M+ members
        "100K_TO_1M",
        "10K_TO_100K",
        "UNDER_10K",
        "PRE_REVENUE",
        "UNKNOWN",          # not stated; scoring uses midpoint
    ]
    has_enterprise_customers: bool = Field(
        ..., description="Named enterprise customers (health plans, F500, etc) in source"
    )
    has_named_customers: bool = Field(
        ..., description="Any named customers at all (case studies, logos)"
    )
    confidence: int = Field(..., ge=0, le=100)
    evidence: str


class ProviderNetworkSignal(BaseModel):
    network_type: Literal[
        "RUNS_MULTI_STATE_NETWORK",    # operates own network across states
        "MANAGES_FOR_PARTNERS",        # credentialing/UM services for others
        "PROVIDERS_PERIPHERAL",        # EHR/RCM — providers in the loop but not core
        "TANGENTIAL",                  # consumer-facing apps with referral lists
        "NONE",                        # no provider relationship
    ]
    confidence: int = Field(..., ge=0, le=100)
    evidence: str


class GrowthSignal(BaseModel):
    stage: Literal[
        "HYPER_GROWTH",                # recent funding + rapid hiring + expansion
        "ACTIVE_GROWTH",               # new customers, hiring
        "STABLE",                      # established, not visibly scaling
        "FLAT_OR_CONTRACTING",
    ]
    confidence: int = Field(..., ge=0, le=100)
    evidence: str


class BuyingReadinessSignal(BaseModel):
    level: Literal[
        "EXPLICIT",                    # mentions credentialing/licensing/provider data
        "STRONG_THEMES",               # provider ops, compliance, network efficiency
        "ADJACENT_THEMES",             # admin burden, scaling ops
        "NONE",
    ]
    confidence: int = Field(..., ge=0, le=100)
    evidence: str


class ICPSignals(BaseModel):
    """Structured signals extracted from facts by Agent 2.
    Contains NO scores or points — those are computed mechanically in scoring.py.
    """
    industry: IndustrySignal
    scale: ScaleSignal
    provider_network: ProviderNetworkSignal
    growth: GrowthSignal
    buying_readiness: BuyingReadinessSignal
    intent_themes: list[IntentTheme]
    pain_points: list[PainPoint]
    missing_data: list[str] = []


class ScoreFactor(BaseModel):
    """One component of the ICP score. The sum of all factor.score values
    should equal ICPAnalysis.icp_score (the prompt enforces this; not
    validated programmatically because LLMs are unreliable at arithmetic).
    """
    score: int = Field(..., description="Points awarded, capped at the factor's max weight.")
    rationale: str = Field(..., description="One-sentence justification grounded in the extracted facts.")
    confidence: int = Field(..., ge=0, le=100, description="0-100. How sure the model is of this sub-score.")


class ScoreBreakdown(BaseModel):
    """5-factor weighted ICP rubric (total max = 100).

    Weights reflect what actually predicts CertifyOS fit:
      - industry_fit (30): is the company in a target vertical at all
      - scale_signals (25): customer/member/provider counts, revenue indicators
      - provider_network_signal (25): do they actually run/manage providers (the literal use case)
      - growth_maturity (10): funding, hiring, expansion themes — affects urgency
      - buying_readiness (10): stated pains, recent themes, role-relevant content
    """
    industry_fit: ScoreFactor             # max 30
    scale_signals: ScoreFactor            # max 25
    provider_network_signal: ScoreFactor  # max 25
    growth_maturity: ScoreFactor          # max 10
    buying_readiness: ScoreFactor         # max 10


class CTA(BaseModel):
    text: str
    intent: Literal["demo", "content", "email", "trial", "contact"]


class ExtractedFacts(BaseModel):
    company_name: str
    one_line_description: str = Field(..., description="What they do, <=140 chars, plain language")
    industry: str
    sub_vertical: Optional[str] = None
    products_services: list[str] = []
    buyer_personas: list[str] = []
    stated_value_props: list[str] = []
    customer_segments: list[str] = []
    recent_themes: list[str] = []
    tone_signals: Optional[str] = None
    social_proof: list[str] = []


class ICPAnalysis(BaseModel):
    icp_score: int = Field(..., ge=0, le=100)
    icp_tier: Literal["A", "B", "C", "D"]
    icp_reasoning: str = Field(..., description="Specific reasoning referencing extracted facts, <=400 chars")
    score_breakdown: ScoreBreakdown = Field(
        ...,
        description="5-factor weighted decomposition of the score. The sum of factor scores should equal icp_score.",
    )
    score_confidence: int = Field(
        ..., ge=0, le=100,
        description="0-100. Confidence in the icp_score itself. Distinct from data_confidence (scrape completeness): "
                    "this is the model's certainty given the facts it has.",
    )
    intent_themes: list[IntentTheme]
    pain_points: list[PainPoint]
    missing_data: list[str] = []


class CopyBlocks(BaseModel):
    hero_headline: str = Field(..., description="<=80 chars, specific to prospect's world")
    subheadline: str = Field(..., description="<=160 chars")
    value_prop_one_liner: str = Field(..., description="<=140 chars")
    pain_paragraph: str = Field(..., description="<=400 chars")
    cta_primary: CTA
    cta_secondary: Optional[CTA] = None


class ScrapeResult(BaseModel):
    domain: str
    pages_attempted: int
    pages_succeeded: int
    pages: list[dict]
    confidence: Literal["high", "medium", "low"]
