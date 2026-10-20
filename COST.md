# Cost accounting

Provider usage is normalized into input, output, and cached tokens. Effective-dated `Price` records calculate integer USD micros with decimal arithmetic. Unknown pricing returns `null`, never zero. Cost events can be grouped by tenant, run, model, and feature without placing those high-cardinality dimensions in Prometheus labels.

The repository contains arithmetic and effective-date boundary tests. It makes no savings claim and ships no guessed provider price table; deployments must load reviewed price records from provider billing sources.
