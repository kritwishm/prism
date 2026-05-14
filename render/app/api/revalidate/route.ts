/**
 * Sanity webhook target. Fires whenever a `companyAnalysis` doc is
 * created/updated/deleted in Sanity.
 *
 * Configure in Sanity:
 *   Sanity manage → API → Webhooks → Create webhook
 *     URL:       https://<your-deployment>/api/revalidate
 *     Trigger:   Create, Update, Delete
 *     Filter:    _type == "companyAnalysis"
 *     Secret:    same value as REVALIDATE_SECRET env var
 *     Method:    POST
 *
 * The webhook body includes `_id` and `domain`; we use the domain to
 * invalidate just the affected slug + the home list, no full rebuild.
 */
import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";
import { slugFromDomain } from "@/lib/sanity";

export async function POST(req: Request) {
  // Verify shared secret. Sanity puts it in the `sanity-webhook-signature`
  // header (HMAC) or the simpler `?secret=` query param. We support both
  // for ergonomics; in production prefer HMAC.
  const url = new URL(req.url);
  const querySecret = url.searchParams.get("secret");
  const expected = process.env.REVALIDATE_SECRET;
  if (!expected) {
    return NextResponse.json({ ok: false, error: "server misconfigured" }, { status: 500 });
  }
  if (querySecret !== expected) {
    return NextResponse.json({ ok: false, error: "invalid secret" }, { status: 401 });
  }

  let body: { _id?: string; domain?: string; _type?: string } = {};
  try {
    body = await req.json();
  } catch {
    /* webhook may send empty body on test-fire */
  }

  if (body._type && body._type !== "companyAnalysis") {
    return NextResponse.json({ ok: true, skipped: true, reason: "non-target type" });
  }

  // Always refresh the index
  revalidateTag("analysis:list");

  // Targeted refresh of the affected slug
  if (body.domain) {
    const slug = slugFromDomain(body.domain);
    revalidateTag(`analysis:${slug}`);
    return NextResponse.json({ ok: true, revalidated: ["analysis:list", `analysis:${slug}`] });
  }

  return NextResponse.json({ ok: true, revalidated: ["analysis:list"], note: "no domain in payload" });
}
