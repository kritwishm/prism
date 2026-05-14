import { createClient } from "@sanity/client";

export type CTA = { text?: string; intent?: string };

export type IntentTheme = { theme: string; confidence: number };
export type PainPoint = { pain: string; evidence?: string; confidence: number };

export type ScoreFactor = {
  score: number;
  rationale: string;
  confidence: number;
};

export type ScoreBreakdown = {
  industry_fit: ScoreFactor;
  scale_signals: ScoreFactor;
  provider_network_signal: ScoreFactor;
  growth_maturity: ScoreFactor;
  buying_readiness: ScoreFactor;
};

export type CompanyAnalysis = {
  _id: string;
  domain: string;
  companyName?: string;
  oneLine?: string;
  industry?: string;
  buyerPersonas?: string[];

  icpScore?: number;
  icpTier?: "A" | "B" | "C" | "D";
  scoreConfidence?: number;
  icpReasoning?: string;
  scoreBreakdown?: ScoreBreakdown;
  dataConfidence?: "high" | "medium" | "low";

  intentThemes?: IntentTheme[];
  painPoints?: PainPoint[];

  heroHeadline?: string;
  subheadline?: string;
  valueProp?: string;
  painParagraph?: string;
  ctaPrimary?: CTA;
  ctaSecondary?: CTA;

  generatedAt?: string;
  scoringVersion?: string;
};

export const sanity = createClient({
  projectId: process.env.NEXT_PUBLIC_SANITY_PROJECT_ID!,
  dataset: process.env.NEXT_PUBLIC_SANITY_DATASET || "production",
  apiVersion: process.env.NEXT_PUBLIC_SANITY_API_VERSION || "2024-01-01",
  token: process.env.SANITY_READ_TOKEN || undefined,
  useCdn: true, // edge cache — fast reads; ISR + webhook handles freshness
});

// Slug ↔ domain mapping.
// We slugify by replacing `.` with `-`. So `oncohealth.us` → `oncohealth-us`,
// `www.devoted.com` → `www-devoted-com`. The reverse is lossy on real-domain
// dashes (rare); we therefore query with a fallback match.
export function domainFromSlug(slug: string): string {
  return slug.replace(/-/g, ".");
}

export function slugFromDomain(domain: string): string {
  return domain.replace(/\./g, "-");
}

const FIELDS = /* groq */ `
  _id, domain, companyName, oneLine, industry, buyerPersonas,
  icpScore, icpTier, scoreConfidence, icpReasoning, dataConfidence,
  intentThemes, painPoints,
  heroHeadline, subheadline, valueProp, painParagraph,
  ctaPrimary, ctaSecondary,
  generatedAt, scoringVersion,
  scoreBreakdown
`;

// Score floor below which a doc exists in Sanity but isn't rendered as a page.
// Keep in sync with prism/scoring.py:COPY_SCORE_FLOOR.
export const RENDER_SCORE_FLOOR = 50;

export async function getAnalysisBySlug(
  slug: string
): Promise<CompanyAnalysis | null> {
  const domain = domainFromSlug(slug);
  // Try exact-domain match first; fall back to a `match` pattern for
  // domains that legitimately contain dashes.
  const groq = `*[_type=="companyAnalysis" && (domain==$domain || domain match $pattern)][0]{${FIELDS}}`;
  return sanity.fetch(
    groq,
    { domain, pattern: slug.replace(/-/g, "*") },
    { next: { revalidate: 60, tags: [`analysis:${slug}`] } }
  );
}

// Public-facing list: only renders accounts above the score floor.
// The full analysis (including sub-floor) lives in Sanity Studio.
export async function listAnalyses(): Promise<CompanyAnalysis[]> {
  return sanity.fetch(
    `*[_type=="companyAnalysis" && icpScore >= ${RENDER_SCORE_FLOOR}] | order(icpScore desc){${FIELDS}}`,
    {},
    { next: { revalidate: 60, tags: ["analysis:list"] } }
  );
}
