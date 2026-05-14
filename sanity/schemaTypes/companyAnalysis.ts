import {defineField, defineType} from 'sanity'

const tierOptions = {
  list: [
    {title: 'A — Elite Fit (90–100)', value: 'A'},
    {title: 'B — Strong Fit (70–89)', value: 'B'},
    {title: 'C — Adjacent (40–69)', value: 'C'},
    {title: 'D — Misfit (0–39)', value: 'D'},
  ],
  layout: 'radio' as const,
}

const ctaIntentOptions = {
  list: [
    {title: 'Demo', value: 'demo'},
    {title: 'Content', value: 'content'},
    {title: 'Email', value: 'email'},
    {title: 'Trial', value: 'trial'},
    {title: 'Contact', value: 'contact'},
  ],
}

const scoreFactor = (name: string, title: string, max: number) =>
  defineField({
    name,
    title,
    type: 'object',
    options: {columns: 3},
    readOnly: true,
    fields: [
      {name: 'score',      title: `Score (0–${max})`, type: 'number'},
      {name: 'confidence', title: 'Confidence (0–100)', type: 'number'},
      {name: 'rationale',  title: 'Rationale',         type: 'text', rows: 2},
    ],
  })

export const companyAnalysis = defineType({
  name: 'companyAnalysis',
  title: 'Company Analysis',
  type: 'document',

  groups: [
    {name: 'identity',  title: 'Identity',     default: true},
    {name: 'scoring',   title: 'ICP Scoring'},
    {name: 'signals',   title: 'Intent & Pain'},
    {name: 'content',   title: 'Page Content'},
    {name: 'meta',      title: 'Metadata'},
  ],

  fields: [
    // ─── Identity ─────────────────────────────────────────────
    defineField({name: 'domain', type: 'string', group: 'identity', readOnly: true, validation: r => r.required()}),
    defineField({name: 'companyName', title: 'Company name', type: 'string', group: 'identity', readOnly: true}),
    defineField({name: 'oneLine', title: 'One-line description', type: 'string', group: 'identity', readOnly: true}),
    defineField({name: 'industry', type: 'string', group: 'identity', readOnly: true}),
    defineField({name: 'buyerPersonas', title: 'Buyer personas', type: 'array', of: [{type: 'string'}], group: 'identity', readOnly: true, options: {layout: 'tags'}}),

    // ─── Scoring ──────────────────────────────────────────────
    defineField({name: 'icpScore', title: 'ICP Score (0–100)', type: 'number', group: 'scoring', readOnly: true,
      validation: r => r.min(0).max(100)}),
    defineField({name: 'icpTier', title: 'ICP Tier', type: 'string', group: 'scoring', readOnly: true, options: tierOptions}),
    defineField({name: 'scoreConfidence', title: 'Score confidence (0–100)', type: 'number', group: 'scoring', readOnly: true}),
    defineField({name: 'dataConfidence', title: 'Data confidence (scrape)', type: 'string', group: 'scoring', readOnly: true,
      options: {list: ['high', 'medium', 'low']}}),
    defineField({name: 'icpReasoning', title: 'ICP reasoning', type: 'text', rows: 3, group: 'scoring', readOnly: true}),
    defineField({
      name: 'scoreBreakdown',
      title: 'Score breakdown — 5 factor rubric',
      type: 'object',
      group: 'scoring',
      readOnly: true,
      options: {collapsible: true, collapsed: false},
      fields: [
        scoreFactor('industry_fit',            'Industry Fit (max 30)',         30),
        scoreFactor('scale_signals',           'Scale Signals (max 25)',        25),
        scoreFactor('provider_network_signal', 'Provider Network (max 25)',     25),
        scoreFactor('growth_maturity',         'Growth & Maturity (max 10)',    10),
        scoreFactor('buying_readiness',        'Buying Readiness (max 10)',     10),
      ],
    }),
    defineField({name: 'missingData', title: 'Missing data (would raise confidence)', type: 'array', of: [{type: 'string'}], group: 'scoring', readOnly: true}),

    // ─── Signals: Intent + Pain ───────────────────────────────
    defineField({
      name: 'intentThemes',
      title: 'Intent themes',
      type: 'array',
      group: 'signals',
      readOnly: true,
      of: [{
        type: 'object',
        fields: [
          {name: 'theme',      type: 'string', title: 'Theme'},
          {name: 'confidence', type: 'number', title: 'Confidence (0–100)'},
        ],
        preview: {
          select: {theme: 'theme', confidence: 'confidence'},
          prepare: ({theme, confidence}) => ({
            title: theme || '(theme)',
            subtitle: confidence != null ? `${confidence}% confidence` : '',
          }),
        },
      }],
    }),
    defineField({
      name: 'painPoints',
      title: 'Pain points',
      type: 'array',
      group: 'signals',
      readOnly: true,
      of: [{
        type: 'object',
        fields: [
          {name: 'pain',       type: 'string', title: 'Pain'},
          {name: 'evidence',   type: 'text', rows: 2, title: 'Evidence from scraped content'},
          {name: 'confidence', type: 'number', title: 'Confidence (0–100)'},
        ],
        preview: {
          select: {pain: 'pain', confidence: 'confidence'},
          prepare: ({pain, confidence}) => ({
            title: pain || '(pain)',
            subtitle: confidence != null ? `${confidence}% confidence` : '',
          }),
        },
      }],
    }),

    // ─── Page Content (editable by marketers) ─────────────────
    defineField({
      name: 'heroHeadline', title: 'Hero headline', type: 'string', group: 'content',
      description: 'Recommended: ≤80 characters. Edit to refine before publishing.',
      validation: r => r.max(120),
    }),
    defineField({
      name: 'subheadline', type: 'string', group: 'content',
      description: 'Recommended: ≤160 characters.',
      validation: r => r.max(220),
    }),
    defineField({
      name: 'valueProp', title: 'Value prop (one-liner)', type: 'string', group: 'content',
      description: 'Recommended: ≤140 characters.',
      validation: r => r.max(200),
    }),
    defineField({
      name: 'painParagraph', title: 'Pain paragraph', type: 'text', rows: 4, group: 'content',
      description: 'Recommended: ≤400 characters.',
      validation: r => r.max(600),
    }),
    defineField({
      name: 'ctaPrimary', title: 'Primary CTA', type: 'object', group: 'content', options: {columns: 2},
      fields: [
        {name: 'text', type: 'string', title: 'Button text'},
        {name: 'intent', type: 'string', title: 'Intent', options: ctaIntentOptions},
      ],
    }),
    defineField({
      name: 'ctaSecondary', title: 'Secondary CTA', type: 'object', group: 'content', options: {columns: 2},
      fields: [
        {name: 'text', type: 'string', title: 'Button text'},
        {name: 'intent', type: 'string', title: 'Intent', options: ctaIntentOptions},
      ],
    }),

    // ─── Metadata ─────────────────────────────────────────────
    defineField({name: 'sourceUrl', title: 'Source URL', type: 'url', group: 'meta', readOnly: true}),
    defineField({name: 'pagesScraped', title: 'Pages scraped', type: 'number', group: 'meta', readOnly: true}),
    defineField({name: 'hubspotCompanyId', title: 'HubSpot company ID', type: 'string', group: 'meta', readOnly: true}),
    defineField({name: 'scoringVersion', title: 'Scoring version', type: 'string', group: 'meta', readOnly: true}),
    defineField({name: 'generatedAt', title: 'Generated at', type: 'datetime', group: 'meta', readOnly: true}),
  ],

  preview: {
    select: {
      title: 'companyName',
      tier: 'icpTier',
      score: 'icpScore',
      conf: 'scoreConfidence',
      domain: 'domain',
      data: 'dataConfidence',
    },
    prepare({title, tier, score, conf, domain, data}) {
      const dot = ({A: '🟢', B: '🟡', C: '🟣', D: '🔴'} as Record<string, string>)[tier as string] || '⚪'
      const scoreStr = score != null ? `${score}/100` : '—'
      const confStr = conf != null ? `${conf}% conf` : ''
      const dataStr = data ? `· ${data} data` : ''
      return {
        title: title || domain || '(unnamed)',
        subtitle: `${dot}  Tier ${tier || '?'}  ·  ${scoreStr}  ·  ${confStr}  ${dataStr}  ·  ${domain || ''}`,
      }
    },
  },

  orderings: [
    {title: 'ICP Score (high → low)', name: 'scoreDesc', by: [{field: 'icpScore', direction: 'desc'}]},
    {title: 'ICP Score (low → high)', name: 'scoreAsc',  by: [{field: 'icpScore', direction: 'asc'}]},
    {title: 'Most recent',            name: 'newest',    by: [{field: 'generatedAt', direction: 'desc'}]},
    {title: 'Domain (A→Z)',           name: 'domainAsc', by: [{field: 'domain', direction: 'asc'}]},
  ],
})
