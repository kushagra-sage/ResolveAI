# Real customer-support dataset assessment

## Selected: BANKING77

BANKING77 is the safest first external-validation dataset for ResolveAI. The official PolyAI
repository contains 10,003 training and 3,080 test online-banking support queries across 77
intents under CC BY 4.0. The repository is pinned to commit
`57ec275d8078af65b7731c2a98be812d844a6d6b`, and both CSV files are SHA-256 verified before
use. The source paper is Casanueva et al. (2020), DOI
[`10.18653/v1/2020.nlp4convai-1.5`](https://doi.org/10.18653/v1/2020.nlp4convai-1.5).

Use it for intent classification, domain-shift checks, and benign guardrail calibration. Do not
claim it validates refunds, approvals, tool execution, retrieval, or business outcomes because
those labels are absent.

## Deferred: TweetSumm

TweetSumm contains 1,100 reconstructed Twitter customer-care dialogs and approximately 6,500
human summaries. It is highly relevant for conversation summarization, but the readable dialogs
depend on the separate Kaggle Customer Support on Twitter corpus and Twitter-derived content.
ResolveAI therefore does not automatically redistribute or render it until a separate data-use,
privacy, and license review is complete. Primary paper: Feigenblat et al. (2021), DOI
[`10.18653/v1/2021.findings-emnlp.24`](https://doi.org/10.18653/v1/2021.findings-emnlp.24).

## Selected for safety: deepset/prompt-injections

The public corpus provides 546 training and 116 test examples with binary injection labels. The
acquisition script pins revision `4f61ecb038e9c3fb77e21034b22511b523772cdd`, records response
checksums, and preserves the source card's two license notices rather than choosing one silently.
The corpus is used as an independent detector test; its examples are not treated as customer
traffic or evidence of production attack prevalence. Source:
[`deepset/prompt-injections`](https://huggingface.co/datasets/deepset/prompt-injections).

## Privacy controls

- Raw public text remains research data, not assumed anonymous.
- The acquisition script scans email-like strings and 10–19 digit numbers and records counts.
- No BANKING77 query is inserted into product customer records, screenshots, or telemetry.
- Any future social-media dataset requires license, retention, and display review first.
