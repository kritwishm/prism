"""Three-agent chain on the Anthropic Claude API.

Sequential calls: extractor → ICP scorer → copywriter.
Each call uses Claude's tool-use mode with a forced `tool_choice` to get
schema-enforced JSON output. The response is then parsed into the matching
Pydantic model. On `ValidationError` we retry once with the error appended
to the prompt — that's the "defensive parsing" layer.

Three separate calls (not one mega-prompt) so each stage has a single,
inspectable job. Each is independently debuggable, individually evaluable,
and at scale individually swappable to a cheaper model. The extractor's
job is mechanical; the ICP scorer needs reasoning; the copywriter needs
voice. Different prompts, different temperatures, different models — once
you start tiering.
"""

from __future__ import annotations

import json
from typing import Type, TypeVar

from anthropic import Anthropic
from loguru import logger
from pydantic import BaseModel, ValidationError

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from .models import CopyBlocks, ExtractedFacts, ICPAnalysis, ICPSignals, ScrapeResult
from .scoring import score_company

client = Anthropic(api_key=ANTHROPIC_API_KEY)

T = TypeVar("T", bound=BaseModel)


# ============================================================
# Prompts
# ============================================================

EXTRACTOR_SYSTEM = """You are a B2B GTM research analyst. You extract structured facts from company website content.

You DO NOT speculate. You DO NOT generate marketing copy. You ONLY extract what is stated or strongly implied in the source content.

If a field cannot be determined from the source, use null or an empty array. Never invent customers, funding stages, or product capabilities."""

ICP_SCORER_SYSTEM = """You are a B2B ICP signal extractor for CertifyOS, a healthcare data infrastructure company.

YOU DO NOT PRODUCE A SCORE. You classify the company along 5 factors. A deterministic Python function turns your classifications into the final 0-100 score and tier — your job is to pick the right enum value for each factor based on EVIDENCE from the extracted facts.

CertifyOS sells API-first provider data infrastructure to:
- Health plans (national, regional, state-level)
- Digital health companies (telehealth, virtual care, specialty care)
- Healthcare networks and IPAs
- Healthcare staffing platforms

Core product: automates provider licensing, credentialing, enrollment, and network monitoring via API.

=============================================================
THE 5 FACTORS — pick one enum value per factor
=============================================================

FACTOR 1 — INDUSTRY  (category)
  HEALTH_PLAN              national/regional/state health plan (true ICP)
  DIGITAL_HEALTH_CLINICAL  telehealth, virtual care, specialty care with provider delivery
  STAFFING_IPA_MSO         healthcare staffing, IPA, MSO, healthcare network
  ADJACENT_HEALTHCARE      RCM, EHR, care coordination, healthcare analytics
  HEALTHCARE_ADJACENT      wellness, fitness, consumer health
  NOT_HEALTHCARE           everything else

FACTOR 2 — SCALE  (member_count_band + customer flags)
  member_count_band:
    OVER_1M        1M+ members
    100K_TO_1M
    10K_TO_100K
    UNDER_10K
    PRE_REVENUE
    UNKNOWN        not stated; pick UNKNOWN rather than guessing high
  has_enterprise_customers:  named enterprise customers (health plans, F500)
  has_named_customers:       any named customers/case studies/logos

FACTOR 3 — PROVIDER NETWORK  (network_type)
  RUNS_MULTI_STATE_NETWORK   they operate a multi-state provider network
  MANAGES_FOR_PARTNERS       they run credentialing/UM/network services for clients
  PROVIDERS_PERIPHERAL       providers in the loop but not core (EHR/RCM)
  TANGENTIAL                 consumer apps with referral lists
  NONE                       no provider relationship

FACTOR 4 — GROWTH  (stage)
  HYPER_GROWTH         recent funding + rapid hiring + expansion themes
  ACTIVE_GROWTH        new customers, hiring, momentum
  STABLE               established but not visibly scaling
  FLAT_OR_CONTRACTING  no growth signals or contracting

FACTOR 5 — BUYING READINESS  (level)
  EXPLICIT          explicit mention of credentialing/licensing/provider data pain
  STRONG_THEMES     recent content around provider ops, compliance, network efficiency
  ADJACENT_THEMES   admin burden, scaling operations, without specific signal
  NONE              no buying readiness signal

=============================================================
OTHER OUTPUTS
=============================================================
- For each of the 5 factor signals, also provide `evidence` (a quote or
  paraphrase from the facts that justifies the classification) and
  `confidence` (0-100).

- `intent_themes` and `pain_points` MUST be about CertifyOS's product space
  — credentialing, licensing, provider enrollment, network management,
  provider data infrastructure — i.e. things this prospect might BUY FROM
  CertifyOS. They are NOT the prospect's own marketing themes, and NOT the
  pains the prospect solves for THEIR customers.

  Examples of CORRECT intent themes (about CertifyOS's product space):
    "Multi-state provider licensing automation"
    "Provider credentialing for a growing therapist network"
    "Network adequacy reporting for CMS compliance"

  Examples of WRONG intent themes (the prospect's own marketing):
    "Patient intake automation"           ← that's Phreesia's product
    "Consumer prescription savings"       ← that's GoodRx's product
    "Meditation and wellness"             ← that's Calm's product

  If the prospect has NO plausible CertifyOS-relevant intent or pain (e.g.
  industry is NOT_HEALTHCARE, or network_type is NONE/TANGENTIAL), return
  empty arrays. Empty is correct and useful. Fabricating CertifyOS-shaped
  themes for a consumer brand or a non-provider company is worse than
  silence.

- `intent_themes`: 0-6 themes, each `theme` + `confidence`
- `pain_points`:   0-5 items, each `pain` + `evidence` + `confidence`
- `missing_data`:  list anything that would raise confidence if known

CONFIDENCE CALIBRATION (apply across every confidence field):
  90-100: directly stated in source, multiple corroborating signals
  70-89:  strongly implied (e.g. "50-state network" implies multi-state licensing pain)
  50-69:  reasonable inference from industry + scale, not stated
  30-49:  weak signal, mostly category-based inference
  <30:    speculative

Spread the confidences. If everything is 85+, you're not calibrating — you're rubber-stamping.

DO NOT output an icp_score, an icp_tier, or any numeric points. Those are
computed downstream. Your job is the classification and the evidence."""

COPYWRITER_SYSTEM = """You are a B2B copywriter for CertifyOS, a healthcare data infrastructure platform.

You write page-ready content for personalized landing pages. Your voice:
- Sharp, specific, no marketing fluff
- Speaks to technical buyers (Head of Credentialing, VP Network Operations, CTO at digital health)
- Anchors on real pains from the prospect's world, not generic claims
- Short sentences. Concrete words.

Strict rules:
- DO NOT invent facts about the prospect that weren't in the source
- DO NOT use 'unlock', 'leverage', 'revolutionize', 'cutting-edge', 'seamless', 'best-in-class', 'transform', or similar fluff
- DO reference specific things the prospect cares about (segments, buyer personas, intent themes)
- If ICP tier is D (poor fit), keep copy general and honest — don't oversell to a misfit"""


# ============================================================
# Tool schemas (derived from Pydantic for single-source-of-truth)
# ============================================================

def _tool_for(model: Type[BaseModel], name: str, description: str) -> dict:
    schema = model.model_json_schema()
    # Anthropic tool input_schema must be a JSON Schema object. Pydantic gives
    # us $defs etc.; Claude handles them fine.
    return {"name": name, "description": description, "input_schema": schema}


EXTRACTOR_TOOL = _tool_for(
    ExtractedFacts,
    "extract_company_facts",
    "Extract structured facts about the company from website content.",
)
ICP_TOOL = _tool_for(
    ICPSignals,
    "extract_icp_signals",
    "Classify the company along the 5 ICP factors and surface intent + pain. NO scoring.",
)
COPY_TOOL = _tool_for(
    CopyBlocks,
    "write_personalized_content",
    "Generate page-ready personalized content blocks.",
)


# ============================================================
# Core call w/ defensive parsing
# ============================================================

def _call_claude_structured(
    *,
    system: str,
    user: str,
    tool: dict,
    model_cls: Type[T],
    max_tokens: int = 2000,
) -> T:
    """One Claude call forced to the given tool. Validates into model_cls.
    On ValidationError, retries once with the error fed back in.
    """
    messages = [{"role": "user", "content": user}]

    for attempt in (1, 2):
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=messages,
        )

        tool_use_block = next(
            (b for b in resp.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if tool_use_block is None:
            raise RuntimeError(
                f"Claude did not return a tool_use block for {tool['name']}"
            )

        try:
            return model_cls.model_validate(tool_use_block.input)
        except ValidationError as e:
            if attempt == 2:
                logger.error(f"[CLAUDE] Validation failed twice for {tool['name']}: {e}")
                raise
            logger.warning(
                f"[CLAUDE] Validation failed for {tool['name']}, retrying once: {e}"
            )
            messages.append({
                "role": "assistant",
                "content": resp.content,
            })
            messages.append({
                "role": "user",
                "content": (
                    f"Your previous response failed schema validation with this error:\n"
                    f"{e}\n\nReturn a valid response that strictly matches the tool's input schema."
                ),
            })

    raise RuntimeError("unreachable")  # pragma: no cover


# ============================================================
# Stage helpers
# ============================================================

def _build_digest(scrape: ScrapeResult) -> str:
    parts = [
        f"DOMAIN: {scrape.domain}",
        f"DATA CONFIDENCE: {scrape.confidence}",
        f"PAGES SCRAPED: {scrape.pages_succeeded}/{scrape.pages_attempted}",
        "",
    ]
    for page in scrape.pages[:8]:
        role = page.get("role", "OTHER")
        url = page.get("url", "")
        content = page.get("content", "")[:3500]
        parts.append(f"\n=== {role} | {url} ===\n{content}")
    return "\n".join(parts)


def run_extractor(scrape: ScrapeResult) -> ExtractedFacts:
    logger.info("[AGENT 1: EXTRACTOR] Starting")
    digest = _build_digest(scrape)
    facts = _call_claude_structured(
        system=EXTRACTOR_SYSTEM,
        user=f"Extract structured facts from this company's scraped website content:\n\n{digest}",
        tool=EXTRACTOR_TOOL,
        model_cls=ExtractedFacts,
        max_tokens=2000,
    )
    logger.success(f"[AGENT 1] Extracted facts for {facts.company_name}")
    return facts


def run_icp_scorer(facts: ExtractedFacts, data_confidence: str) -> ICPAnalysis:
    """Extract structured ICP signals via the LLM, then score deterministically.

    The LLM classifies; Python scores. See prism/scoring.py for the formula.
    """
    logger.info("[AGENT 2: ICP SIGNAL EXTRACTOR] Starting")
    payload = (
        f"Extracted company facts:\n{json.dumps(facts.model_dump(), indent=2)}\n\n"
        f"Data confidence: {data_confidence}\n\n"
        "Classify this company along the 5 ICP factors. Do NOT produce any score."
    )
    signals = _call_claude_structured(
        system=ICP_SCORER_SYSTEM,
        user=payload,
        tool=ICP_TOOL,
        model_cls=ICPSignals,
        max_tokens=2000,
    )
    icp = score_company(signals)
    logger.success(
        f"[AGENT 2] signals: industry={signals.industry.category} "
        f"scale={signals.scale.member_count_band} network={signals.provider_network.network_type}"
    )
    logger.success(f"[SCORING] {icp.icp_score} (Tier {icp.icp_tier}) | score_confidence={icp.score_confidence}%")
    return icp


def run_copywriter(facts: ExtractedFacts, icp: ICPAnalysis) -> CopyBlocks:
    logger.info("[AGENT 3: COPYWRITER] Starting")
    payload = (
        f"Prospect facts:\n{json.dumps(facts.model_dump(), indent=2)}\n\n"
        f"ICP analysis:\n{json.dumps(icp.model_dump(), indent=2)}\n\n"
        "Generate page-ready content tailored to this prospect's situation."
    )
    copy = _call_claude_structured(
        system=COPYWRITER_SYSTEM,
        user=payload,
        tool=COPY_TOOL,
        model_cls=CopyBlocks,
        max_tokens=1500,
    )
    logger.success(f"[AGENT 3] Generated: '{copy.hero_headline}'")
    return copy
