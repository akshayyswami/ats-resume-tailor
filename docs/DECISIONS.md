# Decisions

One entry per decision that changes architecture or scope. Newest first.

## 2026-11-20: the Skills section is closed-world

- **Decision:** every item in the Skills section must resolve to a claimable term in the ledger or a skill tag on a verified fact. An unknown item fails as `unsupported-skill`. An adjacent-only term fails there too, because a bare list cannot carry the sanctioned wording.
- **Why:** a skills list is exactly the claim "I have these", and it is where an added skill hides. Treating an unknown skill as NOT CHECKED would let it through.
- **Alternatives:** report unknown skills as NOT CHECKED. Rejected: it fails open on the place that matters most.

## 2026-11-20: short terms match case-sensitively

- **Decision:** a term of one or two characters (`go`, `r`) matches only as written. Longer terms match case-insensitively on word boundaries.
- **Why:** `go` and `r` are ordinary words, and a case-insensitive match would force evidence for "go live".
- **Alternatives:** case-insensitive everywhere. Rejected for the false positives. Case-sensitive everywhere. Rejected: `postgresql` written in lower case would slip past.

## 2026-11-20: verify checks terms against the cited facts

- **Decision:** the lexicon is the bank's skill tags plus the ledger terms and aliases. Every lexicon term found in a bullet must be supported by that bullet's cited facts. Not-claimable terms fail anywhere. Adjacent terms pass only when the bullet contains the sanctioned wording and cites one of the ledger entry's `supported_by` facts. Terms outside the lexicon are NOT CHECKED.
- **Why:** an existing ID proves nothing about what the bullet claims. A term check is the part of "does the bullet say what the fact says" that code can do without guessing.
- **Alternatives:** structure checks only (ID exists, number exists). Rejected as too weak. A bundled list of skill names for the whole industry. Rejected: a large curated list that would still miss terms, and a maintenance burden.

## 2026-11-20: numbers are checked against the cited facts, not the whole bank

- **Decision:** a number in a bullet must appear in the facts that bullet cites. If it appears only in another fact, the rule is `number-from-other-fact`, distinct from `number-not-in-cited-evidence`.
- **Why:** a global check lets a real 40% from one fact be reused on a bullet about something else.
- **Alternatives:** whole-bank check, as in the first draft of the spec.

## 2026-11-20: an export step strips the evidence IDs

- **Decision:** `export` writes the clean resume and refuses to run when `verify` fails.
- **Why:** the `[E###]` tags must not reach an employer or the PDF that `pdf-check` reads, and the fabrication detector needs the clean text.
- **Alternatives:** have the skill strip tags itself. Rejected: that step could silently skip `verify`.

## 2026-11-20: the fabrication number is recomputed from saved model outputs

- **Decision:** raw outputs from both arms are saved with the model id and date, and `make evals` recomputes the counts offline from them.
- **Why:** CI never calls a live model, and a number that is only recorded cannot be re-measured. Saved outputs can.
- **Alternatives:** record only the final number under `evals/baseline/`. Rejected: nothing to re-derive it from.

## 2026-11-20: no PDF template in v0.1

- **Decision:** `pdf-check` checks any PDF you supply. There is no renderer or template in this repo.
- **Why:** a template adds a rendering dependency and a design job, and it is the part furthest from the thesis.
- **Alternatives:** ship a one-column template. Deferred.
