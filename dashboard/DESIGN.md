# Dashboard design direction

**One line:** the interface is a district register, not a SaaS dashboard — warm paper,
hairline rules, one ink-navy accent, dense tabular figures, reference numbers in mono.

## Why this direction

The product is a government grievance register: officers read rows, check deadlines,
and record decisions. Paper and ink fit that work; gradients, glows and pastel cards
belong to marketing. The chrome stays quiet so the register itself (and the map) is
the only thing with weight.

## Tokens

- **Surfaces:** paper `#faf9f7` / `#f4f2ed`, white cards, hairline borders `#e7e3da`.
- **Ink:** warm near-black text ramp (`slate`), secondary `#5f5951`, muted `#7e776f`.
- **Accent:** one ink navy (`blue` ramp, 700 = `#27425f`) for actions, links, focus.
- **Semantic colour:** moss (resolved), ochre (in progress), brick (overdue), slate-blue
  (escalated) — all muted so they read as stamps on paper, not as paint.
- **Radii:** 3–6 px. No pill shapes.
- **Shadows:** one hairline shadow. No coloured or blurred shadows.
- **Type:** serif (`Palatino/Georgia` stack) for the wordmark and page titles; system sans
  for UI; mono for ticket references and IDs. Figures are tabular.
- **Labels:** sentence case, 11–12 px. No uppercase tracking, no italics, no emoji.
- **Motion:** none beyond hover states and the existing modal fade.

## Signature detail

Every complaint is referred to by its reference in mono (`GRV-2026-000011`) with a
leading hairline rule on the row — the register's own notation, used consistently in
tables, the drawer and the escalation centre.
