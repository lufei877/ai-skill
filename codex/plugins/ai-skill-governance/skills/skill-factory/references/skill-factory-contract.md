# Skill Factory Contract

## Required source fields

`SKILL.md` uses YAML frontmatter with:

- `name`: lowercase letters, digits, and hyphens; maximum 64 characters;
- `description`: one sentence describing the capability and the requests that should activate it;
- `metadata.short-description`: optional UI label.

The body should state the purpose, operating rules, output contract, and exclusions. `validate --level structure` checks required fields and a nonempty body; the default `contract` level also requires a nonempty output section and an exclusion boundary, and rejects known scaffold placeholders. Supported output headings include `Output Contract`, `输出契约`, `输出合同`, `输出格式`, and `输出要求`. Exclusion markers are `exclude`, `排除`, and `不适用`. There is no language-dependent minimum description length; describe the job and boundary, up to 1024 characters. Keep frontmatter fields on single lines; the standard-library reader is not a general YAML parser.

These checks validate explicit structure, not correctness or completeness of the business contract. `validate-library <root>` checks every central skill from the same source set as compilation; independently installed third-party skills are not silently held to this library's authoring contract. Long procedures belong in `references/`; deterministic repeated logic belongs in `scripts/`.

## Trigger cases

The optional `evals/trigger_cases.json` file contains an object with a `cases` array. Each case has:

```json
{
  "id": "positive-1",
  "text": "Create a reusable skill for our release checklist",
  "expected": "trigger"
}
```

`expected` is either `trigger` or `no-trigger`. Add near-neighbor prompts as `no-trigger` cases when a request could be confused with ordinary coding, documentation, or a different skill.

The built-in evaluator is a deterministic smoke check based on English words and short Chinese character n-grams in the description. It is evidence for obvious routing mistakes, not a substitute for model evaluation or human review; add Chinese and mixed-language cases when the skill is used by Chinese-speaking agents.

Use `evals/model-task-cases.json` at the framework root for representative model tasks and `docs/skill-model-evaluation.md` for the comparison protocol. Negation and cross-language understanding belong to model evaluation, not a progressively more complicated keyword classifier. Keep unexecuted runs unverified.

## Maturity guidance

- `scaffold`: source file plus a clear boundary;
- `production`: trigger cases, focused tests, and a documented output contract;
- `library`: production evidence plus packaging, portability, and an owner/review cadence;
- `governed`: use only when the skill affects release, compliance, security, or other high-impact operations.
