# BANKING77 external validation

- Train/test queries: 10,003/3,080
- Intents: 77
- Multinomial Naive Bayes accuracy: 0.8620
- Macro F1: 0.8614
- TF-IDF LinearSVC accuracy: 0.9094
- TF-IDF LinearSVC macro F1: 0.9094
- ResolveAI input-guardrail false-positive rate on benign queries: 0.0000 (0/3080)

These results add a real-query external-validation track. They do not replace the synthetic end-to-end benchmark because BANKING77 lacks action, policy, retrieval, approval, and outcome labels.
