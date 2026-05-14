import { notFound } from "next/navigation";
import Link from "next/link";
import type { Metadata } from "next";
import { getAnalysisBySlug, RENDER_SCORE_FLOOR, type CompanyAnalysis } from "@/lib/sanity";

export const revalidate = 60;

type Props = { params: { slug: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const co = await getAnalysisBySlug(params.slug);
  if (!co) return { title: "Not found" };
  return {
    title: co.heroHeadline
      ? `${co.heroHeadline} · CertifyOS`
      : `CertifyOS for ${co.companyName || co.domain}`,
    description: co.subheadline || co.valueProp,
  };
}

export default async function PersonalizedPage({ params }: Props) {
  const co = await getAnalysisBySlug(params.slug);
  if (!co) notFound();
  // Doc exists but the score is below the render floor — the analysis is
  // kept in Sanity for AE/marketer reference, but no public page is rendered.
  if ((co.icpScore ?? 0) < RENDER_SCORE_FLOOR) notFound();

  const primary = co.ctaPrimary || { text: "Book a demo", intent: "demo" };
  const secondary = co.ctaSecondary || { text: "Talk to our team", intent: "contact" };

  // Top intent themes become "we automate this" proof cards
  const topThemes = (co.intentThemes || [])
    .slice()
    .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))
    .slice(0, 3);

  return (
    <main>
      {/* Top bar */}
      <header className="topbar">
        <div className="shell topbar-inner">
          <Link href="/" className="brand"><em>C</em>ertifyOS</Link>
          <div className="nav-actions">
            <Link href="/">All pages</Link>
            <a href="#cta-bottom" className="btn-mini">{primary.text}</a>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="hero">
        <div className="shell">
          <div className="eyebrow">
            <span className="eyebrow-dot" />
            Personalized for {co.companyName || co.domain}
          </div>
          <h1>{co.heroHeadline || `Provider data infrastructure for ${co.companyName || co.domain}`}</h1>
          {co.subheadline && <p className="hero-sub">{co.subheadline}</p>}
          <div className="cta-row">
            <a href="#cta-bottom" className="btn btn-primary">
              {primary.text}
              <span className="arrow">→</span>
            </a>
            {secondary && (
              <a href="#cta-bottom" className="btn btn-secondary">{secondary.text}</a>
            )}
          </div>
        </div>
      </section>

      {/* Pain — only render if we have one */}
      {co.painParagraph && (
        <section>
          <div className="shell">
            <div className="section-eyebrow">The problem you're solving today</div>
            <p className="pain-block">{co.painParagraph}</p>
          </div>
        </section>
      )}

      {/* Value prop */}
      {co.valueProp && (
        <section>
          <div className="shell">
            <div className="section-eyebrow">What CertifyOS does for you</div>
            <p className="value-block">{co.valueProp}</p>
          </div>
        </section>
      )}

      {/* Proof — the top intent themes, framed as "we automate this" */}
      {topThemes.length > 0 && (
        <section>
          <div className="shell">
            <div className="section-eyebrow">Tailored to what we saw on your site</div>
            <h2 className="section-title">
              We automate <em>exactly</em><br />what your team is doing manually
            </h2>
            <div className="proof-grid">
              {topThemes.map((t, i) => (
                <div className="proof-cell" key={i}>
                  <div className="proof-num">{String(i + 1).padStart(2, "0")}</div>
                  <p className="proof-title">{t.theme}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* CTA strip */}
      <section className="cta-strip" id="cta-bottom">
        <div className="shell-narrow">
          <h2>
            Ready to see it on <em style={{ fontStyle: "italic", color: "var(--accent)" }}>your</em> network?
          </h2>
          <p>30-minute walkthrough. We'll show you the API, the credentialing dashboard, and how it'd plug into {co.companyName || "your"} operations.</p>
          <div className="cta-row" style={{ justifyContent: "center" }}>
            <a href="#" className="btn btn-primary">
              {primary.text}
              <span className="arrow">→</span>
            </a>
            <a href="#" className="btn btn-secondary">{secondary.text}</a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer>
        <div className="shell footer-inner">
          <div className="footer-mark">CertifyOS</div>
          <div className="personalized-tag" title={`ICP ${co.icpScore ?? "—"} · Tier ${co.icpTier ?? "—"} · ${co.scoreConfidence ?? "—"}% confidence`}>
            Personalized via Prism · {co.domain}
          </div>
        </div>
      </footer>
    </main>
  );
}
