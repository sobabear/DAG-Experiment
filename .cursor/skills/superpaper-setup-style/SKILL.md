---
name: superpaper-setup-style
description: Use when the user provides sample papers, chapters, or paragraphs and wants to extract their writing style — creates a concrete style guide at meta/style/style-guide.md for use by draft and review skills
---

# Setup Style

## When to Use

- User provides 2–3 sample papers, chapters, or paragraphs they like (their own writing or papers they admire)
- No `meta/style/style-guide.md` exists yet, or the user wants to replace it
- User says "learn my writing style", "analyze this paper's style", "I want to write like this"

## Procedure

### 1. Collect sample writings

Ask the user to paste 2–3 samples. These can be:
- Paragraphs or sections from their own previous writing
- Excerpts from papers they admire
- A mix of both

If samples are already provided in the conversation, proceed without asking.

### 2. Analyze style dimensions

For each sample, examine the following dimensions:

#### Tone
- **Formal vs. conversational**: Does the author maintain academic distance or engage directly with the reader?
- **Hedging level**: Frequent use of "may", "might", "suggests", "appears to" vs. direct assertion?
- **Stance**: Does the author foreground their own argument ("I argue") or use impersonal constructions ("This paper argues")?

#### Sentence Structure
- **Average sentence length**: Short and punchy (< 20 words), medium (20–35 words), or long and complex (> 35 words)?
- **Sentence complexity**: Simple declarative sentences vs. embedded clauses and subordination?
- **Variation**: Does the author vary sentence length for rhythm, or maintain consistent length?

#### Paragraph Patterns
- **Topic sentences**: Does every paragraph open with a clear claim?
- **Evidence integration**: How is evidence introduced — "As X argues", "X finds that", "According to X"?
- **Transition style**: Explicit connectors ("However", "Moreover", "In contrast") vs. implicit flow?
- **Paragraph length**: Short focused paragraphs (3–5 sentences) vs. long developed paragraphs?

#### Vocabulary Level
- **Technical density**: How many field-specific terms per paragraph?
- **Preferred abstractions**: Does the author favor latinate abstractions ("utilization") or plain words ("use")?
- **Register consistency**: Does vocabulary stay in one register or shift?

#### Paragraph Template

**Paragraph template** means a fill-in-the-blank model paragraph, not just a structural description. Example:
```
本文认为___[核心立场]___。既有研究表明___[证据1]___（[citekey]）；___[证据2]___（[citekey]）。然而，___[复杂化/限制]___。因此，___[推论或研究问题]___。
```
Provide at least one such template in the style guide, derived from an actual sample paragraph.

#### Argumentation Style
- **Directness**: Does the author state claims directly before evidence, or build up to a conclusion?
- **Hedging phrases**: Specific phrases used (e.g., "suggests", "indicates", "it is possible that")
- **Counterargument handling**: Does the author preemptively address objections?
- **Evidence sourcing**: Heavy citation vs. selective citation of key works?

#### Formality Level
- Overall register: academic-formal, academic-accessible, or journalistic?

### 3. Handle bilingual projects

If the project language is Chinese (`zh`) or the samples include Chinese text:

- Capture **Chinese-specific patterns** separately:
  - Hedging phrases: e.g., "可能", "或许", "在一定程度上", "值得注意的是"
  - Typical sentence endings and connectives: "然而", "因此", "此外", "综上所述"
  - Whether the author uses "本文" vs. "笔者" vs. "我们"
  - Paragraph structure conventions in Chinese academic writing
- Capture **English-specific patterns** for any English sections
- Note where the author switches register between languages

### 4. Synthesize patterns into concrete guidelines

Extract **concrete, actionable patterns** — not abstract advice.

Good: `Use hedging phrases like "suggests" or "indicates" before empirical claims`
Bad: `Be appropriately cautious`

Good: `Open each paragraph with a direct claim sentence of 15–20 words, then support with 2–3 sentences of evidence`
Bad: `Write clear paragraphs`

Good (Chinese): `Hedge claims with "可能" or "在一定程度上" before stating findings`
Bad (Chinese): `Write in an appropriately academic tone`

For each dimension, extract 2–4 concrete patterns with examples from the samples.

### 5. Write meta/style/style-guide.md

Create or overwrite `meta/style/style-guide.md` with the following structure:

```markdown
# Style Guide

Extracted from: [list of sample sources]
Date: [today]

## Tone
- [Concrete pattern 1 with example]
- [Concrete pattern 2 with example]

## Sentence Structure
- [Concrete pattern 1 with example]
- [Concrete pattern 2 with example]

## Paragraph Patterns
- [Concrete pattern 1 with example]
- [Concrete pattern 2 with example]

## Paragraph Template
[Fill-in-the-blank model paragraph derived from sample text. E.g.: "___[立场声明]___，既有研究表明___[证据]___（[citekey]），然而，___[转折/限制]___，因此___[推论]___。"]

## Vocabulary
- [Concrete pattern 1 with example]
- [Concrete pattern 2 with example]

## Argumentation Style
- [Concrete pattern 1 with example]
- [Concrete pattern 2 with example]

## Hedging Phrases
[List of specific phrases extracted from samples, ready to copy]

## Transition Phrases
[List of specific transitions extracted from samples, ready to copy]

## Chinese Style (if bilingual)
- [Concrete Chinese-specific pattern 1 with example]
- [Concrete Chinese-specific pattern 2 with example]
### Chinese Hedging Phrases
[List: 可能, 或许, 在一定程度上, ...]
### Chinese Transitions
[List: 然而, 因此, 此外, ...]

## Formality Level
[One-line description: e.g., "Academic-formal; no contractions; impersonal constructions preferred"]
```

Fill every section from the actual samples — never invent patterns.

### 6. Confirm and suggest next steps

After writing the guide, tell the user:

> `meta/style/style-guide.md` has been created with patterns extracted from your samples.
>
> This guide will be read by `draft` (to match your style when writing) and `review` (to flag deviations). If you'd like to refine any patterns, edit the file directly — it's yours.
>
> Suggested next step: run `outline` on the chapter you're working on, then `draft`.

## Inputs

- 2–3 sample papers, chapters, or paragraphs (pasted inline or referenced as file paths)
- Project language setting from `CLAUDE.md` (to determine whether to include Chinese style section)

## Outputs

- `meta/style/style-guide.md` — concrete writing style patterns with examples, organized by dimension
  - Tone (formal/conversational, hedging level, stance)
  - Sentence structure (length, complexity, variation)
  - Paragraph patterns (topic sentences, evidence integration, transitions)
  - Vocabulary level and register
  - Argumentation style (directness, hedging phrases, counterargument handling)
  - Chinese style section (if bilingual project): hedging phrases, transitions, structural conventions

## Notes

- Style guide entries must be **concrete**: include example phrases or sentence templates extracted from the actual samples
- Never generate fictional examples — every pattern in the guide must be traceable to a provided sample
- For bilingual projects, maintain separate sections for Chinese and English patterns; do not conflate them
- The style guide is consumed by `draft` and `review` — keep it structured and machine-readable
- If the user provides samples from multiple authors with different styles, note the tension and ask which to prioritize, or create a "blended" profile with explicit trade-offs noted
- Recommend re-running `setup-style` after the user has written 2–3 chapters of their own — their style will evolve
