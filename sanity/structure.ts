import type {StructureBuilder} from 'sanity/structure'

const tier = (S: StructureBuilder, label: string, value: string, title: string) =>
  S.listItem()
    .title(label)
    .child(
      S.documentList()
        .title(title)
        .filter('_type == "companyAnalysis" && icpTier == $tier')
        .params({tier: value})
        .defaultOrdering([{field: 'icpScore', direction: 'desc'}]),
    )

export const structure = (S: StructureBuilder) =>
  S.list()
    .title('Prism')
    .items([
      // The primary marketer surface: only accounts that render as public pages.
      S.listItem()
        .title('🟢  Public pages (score ≥ 50)')
        .child(
          S.documentList()
            .title('Renders as /p/{slug} - score ≥ 50')
            .filter('_type == "companyAnalysis" && icpScore >= 50')
            .defaultOrdering([{field: 'icpScore', direction: 'desc'}]),
        ),
      // The audit/reference surface: every analysis, including misfits.
      S.listItem()
        .title('🔴  Below threshold (no page rendered)')
        .child(
          S.documentList()
            .title('Analyzed but not rendered - score < 50')
            .filter('_type == "companyAnalysis" && icpScore < 50')
            .defaultOrdering([{field: 'icpScore', direction: 'desc'}]),
        ),
      S.divider(),
      S.listItem()
        .title('By ICP Tier')
        .child(
          S.list()
            .title('Companies by ICP Tier')
            .items([
              tier(S, '🟢  Tier A - Elite Fit',     'A', 'Tier A · Elite Fit (90-100)'),
              tier(S, '🟡  Tier B - Strong Fit',    'B', 'Tier B · Strong Fit (70-89)'),
              tier(S, '🟣  Tier C - Adjacent',      'C', 'Tier C · Adjacent (40-69)'),
              tier(S, '🔴  Tier D - Misfit',        'D', 'Tier D · Misfit (0-39)'),
            ]),
        ),
      S.divider(),
      S.listItem()
        .title('All Companies (ranked)')
        .child(
          S.documentList()
            .title('All Companies - ranked by ICP score')
            .filter('_type == "companyAnalysis"')
            .defaultOrdering([{field: 'icpScore', direction: 'desc'}]),
        ),
      S.listItem()
        .title('Needs review (low data confidence)')
        .child(
          S.documentList()
            .title('Low data confidence')
            .filter('_type == "companyAnalysis" && dataConfidence == "low"'),
        ),
    ])
