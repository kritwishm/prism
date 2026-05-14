import Link from "next/link";
import { listAnalyses, slugFromDomain } from "@/lib/sanity";

export const revalidate = 60;

export default async function HomePage() {
  const items = await listAnalyses();

  return (
    <main>
      <header className="topbar">
        <div className="shell topbar-inner">
          <div className="brand"><em>P</em>rism</div>
          <div className="nav-actions">
            <a href="https://github.com">Repo</a>
            <a href="/" className="btn-mini">Book a demo</a>
          </div>
        </div>
      </header>

      <section style={{ padding: "120px 0 60px", borderBottom: "1px solid var(--rule)" }}>
        <div className="shell">
          <div className="eyebrow"><span className="eyebrow-dot" /> Personalized landing pages</div>
          <h1 style={{ fontFamily: "var(--serif)", fontSize: "clamp(48px,7vw,80px)", lineHeight: 1.04, margin: "0 0 24px", fontWeight: 400, letterSpacing: "-.022em", maxWidth: "20ch" }}>
            One URL in. <em style={{ fontStyle: "italic", color: "var(--accent)" }}>One landing page out.</em>
          </h1>
          <p style={{ fontSize: 20, color: "var(--text-dim)", maxWidth: "60ch", margin: 0 }}>
            Every page below was generated from public company content, scored against the CertifyOS ICP rubric, and is now editable in Sanity Studio. Click any to see the rendered page.
          </p>
        </div>
      </section>

      <section style={{ padding: "60px 0 100px" }}>
        <div className="shell">
          <div className="section-eyebrow">{items.length} analyzed companies · sorted by ICP score</div>
          <div className="index-grid">
            <div className="index-row head">
              <div>Tier</div>
              <div>Company</div>
              <div style={{ textAlign: "right" }}>Score</div>
              <div style={{ textAlign: "right" }}>Conf</div>
              <div></div>
            </div>
            {items.map((co) => {
              const slug = slugFromDomain(co.domain);
              return (
                <Link key={co._id} href={`/p/${slug}`} className="index-row" prefetch={false}>
                  <div className={`index-tier ${co.icpTier || ""}`}>{co.icpTier || "—"}</div>
                  <div className="index-co">
                    {co.companyName || co.domain}
                    <em>{co.domain}</em>
                  </div>
                  <div className="index-num">{co.icpScore ?? "—"}</div>
                  <div className="index-conf">{co.scoreConfidence != null ? `${co.scoreConfidence}%` : "—"}</div>
                  <div className="index-arrow">→</div>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      <footer>
        <div className="shell footer-inner">
          <div className="footer-mark">Prism</div>
          <div className="personalized-tag">Powered by Sanity · ISR · Claude</div>
        </div>
      </footer>
    </main>
  );
}
