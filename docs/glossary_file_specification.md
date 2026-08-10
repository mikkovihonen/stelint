# Glossary File Specification

Stelint uses JSONL (JSON Lines) files to store glossary data. Each line in the file is a single JSON object. Stelint ships with `asd-ste100_base.jsonl` containing the full ASD-STE100 specification, and you create override files for company or project-specific adjustments.

## File format

Each line is one JSON object. Empty lines are ignored. The object has these fields:

| Field | Required | Description |
|---|---|---|
| `namespace` | yes | Category name (e.g. `words`, `verbs`, `general`). Must match a namespace in the base file. |
| `name` | yes | Constant name (e.g. `NON_APPROVED_WORDS`, `BE_VERBS`). Must match a name in the base file. |
| `rules` | yes | List of rule references this entry relates to (e.g. `["Rule 1.10"]`). |
| `type` | yes | Data structure type: `mapping`, `collection`, or `mapping_tuple_keys`. Must match the base file type. |
| `data` | yes | The actual data value. |

## Adding entries

To add a new approved replacement word:

```json
{"namespace": "words", "name": "NON_APPROVED_WORDS", "rules": ["Company Policy"], "type": "mapping", "data": {"bollocks": "nonsense", "bugger": "dammit"}}
```

To add new false friends:

```json
{"namespace": "general", "name": "FALSE_FRIENDS", "rules": ["Company Policy"], "type": "mapping", "data": {"actually": "currently", "current": "present"}}
```

To add new conjunction-that patterns:

```json
{"namespace": "general", "name": "CONJUNCTION_THAT_PATTERNS", "rules": ["Company Policy"], "type": "collection", "data": [{"pattern": "make sure", "replacement": "make sure that"}]}
```

## Removing entries

To remove a key from a mapping in the base file, set its value to `"__REMOVE__"`:

```json
{"namespace": "words", "name": "NON_APPROVED_WORDS", "rules": ["Company Policy"], "type": "mapping", "data": {"privilege": "__REMOVE__", "deliberate": "__REMOVE__"}}
```

The key is deleted from the loaded constant. This is useful when your company vocabulary allows a word that the base ASD-STE100 specification marks as forbidden.

## Data types

### `mapping` — word replacement dictionary

A JSON object with string keys and string values:

```json
{"namespace": "words", "name": "NON_APPROVED_WORDS", "rules": ["Rule 1.10"], "type": "mapping", "data": {"acceptable": "permitted", "abundant": "many"}}
```

When overriding, you can add new keys, update existing values, or remove keys with `"__REMOVE__"`.

### `collection` — list of items

A JSON array of unique items:

```json
{"namespace": "verbs", "name": "BE_VERBS", "rules": ["Rule 3.5"], "type": "collection", "data": ["am", "are", "be", "been", "being", "is", "was", "were"]}
```

When overriding, the entire collection is replaced. New entries are added, old entries are removed.

### `mapping_tuple_keys` — multi-word pattern dictionary

A JSON array of `[key_array, value]` pairs. Each key is a tuple converted to an array:

```json
{"namespace": "writing", "name": "PHRASAL_VERBS", "rules": ["Rule 9.3"], "type": "mapping_tuple_keys", "data": [[["add", "up"], "add"], [["break", "down"], "stop working"]]}
```

Use this for patterns that match multiple consecutive words (e.g. phrasal verbs, multi-word noun patterns).

## Complete example

A company glossary file might look like this:

```json
{"namespace":"words","name":"NON_APPROVED_WORDS","rules":["Company Policy"],"type":"mapping","data":{"bollocks":"nonsense","bugger":"dammit"}}
{"namespace":"words","name":"NON_APPROVED_WORDS","rules":["Company Policy"],"type":"mapping","data":{"privilege":"__REMOVE__","deliberate":"__REMOVE__"}}
{"namespace":"general","name":"FALSE_FRIENDS","rules":["Company Policy"],"type":"mapping","data":{"actually":"currently","current":"present"}}
{"namespace":"general","name":"CONJUNCTION_THAT_PATTERNS","rules":["Company Policy"],"type":"collection","data":[{"pattern":"make sure","replacement":"make sure that"},{"pattern":"show","replacement":"show that"}]}
```

When loaded on top of the base file:
- `NON_APPROVED_WORDS` gains 2 new entries and loses 2 keys
- `FALSE_FRIENDS` gains 1 new entry and overrides 1 existing value
- `CONJUNCTION_THAT_PATTERNS` is replaced entirely with the new collection

## Referencing the file

Create `glossaries.yaml` (typically alongside other project config files):

```yaml
glossaries:
  - path: company_glossary.jsonl
    cardinality: 100
  - path: project_glossary.jsonl
    cardinality: 200
```

The `path` is relative to the directory containing `glossaries.yaml`. The `cardinality` is an integer — higher values override lower ones. The base file (`asd-ste100_base.jsonl`) is always loaded first and cannot be overridden.

## Namespaces

These are the namespace values you can use in the `namespace` field:

| Namespace | STE100 Section | Typical use |
|---|---|---|
| `words` | Rule 1.x | Non-approved words, technical nouns, false friends, slang |
| `multiword` | Rule 2.x | Multi-word noun patterns, technical noun clarity |
| `verbs` | Rule 3.x | Verb forms, tenses, passive voice exceptions |
| `sentences` | Rule 4.x | Contractions, connecting words |
| `procedural` | Rule 5.x | Conditional words, imperative verb lemmas |
| `descriptive` | Rule 6.x | Common determiners |
| `safety` | Rule 7.x | Safety keywords, risk indicators |
| `punctuation` | Rule 8.x | Parentheses contexts, hyphenated terms, common units |
| `writing` | Rule 9.x | Phrasal verbs, consistent style patterns, restricted words |
| `general` | GR-1 to GR-8 | False friends, gender pronouns, conjunction patterns |

Use the same namespace and name as the base file entry you want to modify.

## Tips

- One JSON object per line. Do not use pretty-printed JSON.
- Use `"__REMOVE__"` as a value to delete a key from a mapping.
- Collections are replaced entirely, not merged. Include all entries you want.
- Keep rule references honest — they help with traceability and debugging.
- Test your overrides by running stelint on a sample file and checking the constant count.
