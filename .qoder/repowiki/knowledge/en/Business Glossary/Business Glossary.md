---
kind: business_term
name: Business Glossary
category: business_term
scope:
    - '**'
---

### RAT
- Definition：Repo Analysis Tool — the name of this multi-repository web dashboard that turns git history into filterable file/directory/repo/commit-set/author metrics.
- Aliases：Repo Analysis Tool

### commit set H
- Definition：The time window or manually selected commit list that defines which commits contribute to every metric; supplied via URL filters `start`/`end` (inclusive start, exclusive end) or a `commits` SHA list, with the latter overriding the range.
- Aliases：H

### modification frequency η
- Definition：Metric n_H,o / |H| — proportion of commits in H that modify object o; equals 0 when |H| = 0.
- Aliases：frequency、eta

### churn rate ρ
- Definition：Metric λ_H,o / |H| — total added+removed lines in H for object o divided by the size of H; equals 0 when |H| = 0.
- Aliases：rho

### ownership ω
- Definition：Per-author share of churn: λ_H,o,a / λ_H,o — fraction of object o's churn attributable to author a over the filtered commit set H; equals 0 when λ_H,o = 0.

### author merging
- Definition：Process of collapsing multiple raw identities (name/email pairs) into one canonical identity; applied automatically at ingest via `.mailmap`, and manually through the UI where merges are resolved at query time without re-indexing.
- Aliases：identity merging、merge groups
