import Link from "next/link";

export default function NotFound() {
  return (
    <main>
      <header className="topbar">
        <div className="shell topbar-inner">
          <Link href="/" className="brand"><em>C</em>ertifyOS</Link>
        </div>
      </header>
      <div className="empty">
        <div className="shell">
          <div className="eyebrow"><span className="eyebrow-dot" /> 404</div>
          <h1>This page hasn't been generated yet.</h1>
          <p style={{ maxWidth: "44ch", margin: "0 auto" }}>
            Run <code style={{ fontFamily: "var(--mono)", background: "var(--surface)", padding: "2px 8px", borderRadius: 4 }}>python run.py analyze &lt;url&gt;</code> on the company URL, and this page will exist within seconds of the Sanity write.
          </p>
          <p style={{ marginTop: 36 }}>
            <Link href="/" className="btn btn-primary">See all pages →</Link>
          </p>
        </div>
      </div>
    </main>
  );
}
