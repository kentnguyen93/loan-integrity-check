# Application Integrity Check

A dependency-free Python prototype that checks business-loan applications before disbursement. It reads four financial figures from supporting documents, validates them, compares the applicant's story with observed account activity, and gives an investigator an explainable evidence pack.

The system advises; a person decides. It never automatically declines a loan.

Built for the Techcombank AI Transformation Division Expert Challenge 2026, Problem 4 (early warning signals). **All applications, documents, labels, and outcomes are synthetic. No customer or confidential bank data is used.**

## Does the workflow use AI?

**The core workflow does not call an AI model.** Document labelling, field extraction, validation, integrity checks, scoring, routing, and monitoring use deterministic rules and arithmetic.

| Component | AI model called? | Status |
| --- | --- | --- |
| Document ingestion and validation | No | Runs locally with Python parsers |
| Seven integrity checks and risk score | No | Runs locally with weighted rules |
| Investigator dashboard | No | Static HTML and JavaScript |
| `src/llm_extract.py` | Yes, when explicitly run | Optional Anthropic experiment; not part of the core pipeline |
| Manual trial in `trial/` | Yes | A separate 10-application Claude chat experiment supplied with the project |

The optional model script has **not been run or validated in this environment**. It requires an Anthropic API key, a valid model name, and current pricing. It compares model answers with known truth, but it does not yet pass those answers through the full ingestion validation layer. Its output must not be treated as production-validated data.

## Requirements

- Python 3.9 or newer.
- No third-party Python packages, package installation, API key, web font, or external service is needed for the core workflow.
- Verified on Windows with Python 3.13.4. Text files are read and written as UTF-8 explicitly.

## Build and run

From the project root, run the commands in this order:

```bash
python src/pipeline.py              # Generate 4,000 applications; check, score, route, and evaluate
python src/ingest_eval.py           # Evaluate 1,000 applications / 4,000 synthetic documents
python src/build_demo.py            # Generate demo/index.html from the two evaluation outputs
python -m unittest discover tests -v # Run 15 unit, regression, and security tests
python src/monitor.py               # Check the latest scoring run and write out/alerts.json
```

Open `demo/index.html` in a browser. It is self-contained and does not require a web server.

With the supplied configuration, `monitor.py` intentionally exits with status `1` because the held-out flag rate is **5.9%**, above the **5%** target. This is a documented calibration warning, not a crashed build. The monitor also exits `1` for any other active alert.

If `python` is not available on your PATH, use `python3` on macOS/Linux or `py` on Windows.

## Workflow

1. **Generate or collect.** Each synthetic application contains declared revenue and invoices, observed inflows, related-party flows, account tenure, and shared director, phone, and address fields.
2. **Read documents.** The ingestion slice labels four document types, extracts Vietnamese-formatted figures and units, and records source lines and confidence.
3. **Validate.** Arithmetic checks compare components with totals. A cross-document check compares e-invoice revenue with VAT-declared revenue. Untrusted or missing values go to document review.
4. **Cross-check and score.** Seven checks return a strength from 0 to 1, a plain-language reason, and supporting evidence. `src/score.py` combines them as `score = 1 - product(1 - weight × strength)`.
5. **Route and review.** Files below the calibrated threshold are `CLEAR`. Others are `REVIEW` or `REVIEW_PRIORITY`. An investigator can escalate, clear, or request documents, but must select a reason.
6. **Log and monitor.** The pipeline writes one audit record per application. The dashboard records session decisions and monitoring checks flag-rate drift, an empty queue, the kill switch, and scoring time.

### Integrity checks

| Check | Comparison | Intended signal |
| --- | --- | --- |
| `revenue_gap` | Declared revenue vs account inflows | Inflated revenue |
| `invoice_gap` | Invoices issued vs money received | Invoices without corresponding trade |
| `round_trip` | Inflows vs money returned to related accounts | Turnover inflated by cycling funds |
| `spike` | Last 3 months vs previous 9 months | Account dressing before application |
| `links` | Shared directors, phones, and addresses | Connected applicants or shell rings |
| `suspect_list` | Applicant details vs known cases | Repeat actors |
| `tenure` | Account age | New-account risk; deliberately a weak signal |

## Verified synthetic results

### Integrity scoring

The supplied configuration generates 4,000 applications with a 2.5% injected fraud rate across five schemes. The threshold is calibrated on the first 2,000 applications and measured on the other 2,000.

| Held-out measure | Result |
| --- | ---: |
| Files flagged | 118 of 2,000 (5.9%) |
| Fraud caught, by count | 38 of 51 (74.5%) |
| Fraud caught, by value of requested limits | 82.2% |
| Precision: flagged files that are fraud | 32.2% |
| Fraud cases missed | 13 |
| Model cost per file | VND 0; no model is called |

| Injected scheme | Fraud cases | Caught |
| --- | ---: | ---: |
| Fake invoices | 13 | 13 |
| Round-tripping | 11 | 10 |
| Inflated revenue | 13 | 10 |
| Shell ring | 8 | 5 |
| Straw borrower | 6 | 0 |

These figures describe only the patterns simulated by `src/generate.py`. The fraud generator and checks were designed together, so these are not estimates of real bank performance. Timing in the JSON reports is machine-dependent.

### Document ingestion

The ingestion evaluation renders four Vietnamese source documents per application—income statement extract, VAT declaration, e-invoice listing, and bank statement summary—then simulates lost diacritics, look-alike letters, misread digits, and dropped lines.

| Measure | Result |
| --- | ---: |
| Documents labelled correctly | 4,000 of 4,000 |
| Fields validated | 3,713 of 4,000 (92.8%) |
| Validated fields that are correct | 100% |
| Wrong but validated | 0 |
| Fields sent to review / missing | 262 / 25 |
| Applications straight through to integrity checks | 743 of 1,000 |
| Applications sent to document review | 257 |
| Routing agreement on straight-through files | 100% |
| Model cost per application | VND 0; no model is called |

This tests parsing and validation logic on generated text, **not OCR quality on real scans**. Real layouts, stamps, handwriting, and poor image quality are outside this prototype. Strict validation avoids wrong-but-trusted values in this synthetic run, at the cost of sending 25.7% of applications to a person.

## Investigator dashboard

The generated English-language dashboard includes:

- Separate document-intake and integrity-review stages.
- A review queue ordered by score, with application-ID search.
- Source-linked master data and expandable source documents.
- Explainable flags, numeric evidence, and signal-contribution bars.
- Mandatory decision reasons and a session audit log.
- An evaluation mode showing known answers and simulated damage.
- A session-only kill switch.

The dashboard initially uses the **actual pipeline threshold**, so its metrics match the 118-file held-out result above. Moving the **Interactive review share** slider deliberately creates a what-if threshold on the displayed 2,000 files. At exactly 5%, it selects 100 files; this is not the calibrated pipeline result. Select **Use calibrated threshold** to restore the initial view.

The interface and this README are English. The synthetic source documents remain Vietnamese because Vietnamese labels, number formatting, diacritics, and units are part of the extraction test.

Dashboard decisions are held in memory only and disappear on reload. They are not written back to `out/audit_log.jsonl` or any bank system.

## Configuration and controls

All scoring configuration is in `config.json`:

- `enabled`: set to `false` for the pipeline kill switch. Every application is routed `CLEAR_CHECK_OFF` to the normal manual process.
- `flag_cap`: target review share used to calibrate the threshold on the first half of the applications.
- `priority_score`: score at which a flagged file becomes `REVIEW_PRIORITY`.
- `weights`: contribution of each integrity check.
- `tolerance`: segment-specific revenue and invoice gap thresholds for SMEs and household businesses.
- `seed`, `n_applications`, and `fraud_rate`: synthetic data generation controls.

The same seed and configuration produce the same application data, scores, routes, and run ID. Measured execution time can vary. The pipeline rewrites its JSON and audit outputs on each run, so a rerun does not append duplicate audit records.

The dashboard kill switch demonstrates session behavior only; it does not edit `config.json`.

## Optional AI experiment

`src/llm_extract.py` sends the supplied 10-application trial documents to Anthropic and evaluates four figures per application against `trial/truth.json`. It is not executed by any quick-start command. Before using it, review the model name, endpoint, price constants, data-sharing implications, and validation gaps in the script.

The separate manual Claude trial recorded in `trial/` reported 39 of 40 figures correct. Its important failure was an inappropriate correction: on `APP-00615`, the model changed a printed net-revenue figure to satisfy arithmetic even though the net figure was correct and the gross line contained the damaged digit. This illustrates why model output needs independent validation and must preserve figures as printed. Ten applications are a small trial, not a production evaluation.

## Project layout

```text
config.json               Weights, tolerances, review target, kill switch, and seed
src/generate.py           Synthetic applications and five fraud schemes
src/checks.py             Seven integrity cross-checks
src/score.py              Scoring, threshold calibration, and routing
src/pipeline.py           End-to-end scoring evaluation and audit output
src/documents.py          Synthetic Vietnamese documents and simulated scan damage
src/ingest.py             Labelling, extraction, validation, and master data
src/ingest_eval.py        Document-ingestion evaluation
src/build_demo.py         Self-contained dashboard generator
src/monitor.py            Run-health checks and alerts
src/llm_extract.py        Optional, unexecuted Anthropic extraction experiment
demo/template.html        English investigator interface
demo/index.html           Generated dashboard with embedded results
tests/test_checks.py      Unit tests and Windows UTF-8 regression test
tests/test_security.py    Embedded-data, CSP, external-resource, and storage checks
trial/                    Supplied 10-application manual AI trial artifacts
out/                      Generated results, examples, audit log, and alerts
```

### Generated outputs

- `out/results.json`: held-out application rows plus the run report.
- `out/evaluation.json`: calibration and held-out scoring metrics.
- `out/ingest_evaluation.json`: document-ingestion metrics.
- `out/master_data_examples.json`: source-linked extraction examples.
- `out/audit_log.jsonl`: one pipeline audit record per generated application.
- `out/alerts.json`: latest monitoring alerts.
- `demo/index.html`: standalone investigator dashboard.

## Security review

The generated demo is a static file, not a web application backend. Its current security controls are:

- No external scripts, fonts, images, stylesheets, analytics, network requests, cookies, browser storage, service workers, or third-party JavaScript dependencies.
- HTML-safe JSON embedding that escapes `<`, `>`, `&`, and JavaScript line separators so document content cannot close the embedding `<script>` element.
- Escaping of dynamic identifiers, reasons, evidence, source metadata, decisions, and document text before HTML rendering. Audit-log output uses `textContent`.
- A Content Security Policy that denies resources by default, blocks outbound connections and objects, and permits only the generated script with the matching SHA-256 hash. The demo has no inline-event-handler or external-script dependency.
- Synthetic data only in the supplied build. The optional Anthropic experiment is separate and is never called by the demo.
- Automated security regression checks in `tests/test_security.py` for script breakouts, CSP hash integrity, external resources, and persistent storage.

**Data confidentiality remains the user's responsibility.** Anyone who receives `demo/index.html` can read every value embedded in it. Do not put real customer, loan, identity, credit-bureau, tax, or banking data into this static demo. Repository privacy does not protect copies downloaded or shared by authorised users.

The meta CSP is appropriate for this standalone prototype but does not replace production HTTP security headers or server controls. A real deployment still needs authenticated and authorised access, TLS, secure server-side case and audit storage, encryption and retention controls, CSRF protection where applicable, rate limiting, dependency and infrastructure monitoring, and a framing policy such as the `frame-ancestors` HTTP CSP directive. Browser, extension, endpoint, and operating-system compromise are outside this demo's trust boundary.

## Known limitations

- **No real OCR or external verification.** There is no connection to a bank, CIC, tax authority, identity provider, enterprise registry, collateral registry, or open-banking service.
- **Straw borrowers are not detected.** The synthetic scheme leaves no trace in the available fields; identity and beneficial-owner controls would be needed.
- **Careful fraud can fall below the threshold.** Weak-signal cases are missed by design in the simulation.
- **Shared addresses cause false alarms.** Honest businesses can share a market or office address. Production use would require better entity resolution and graph analysis.
- **Cash-heavy businesses need separate calibration.** Household-business tolerances are assumptions, not empirically fitted bank policy.
- **The held-out flag rate drifts above target.** The current 5.9% result is why monitoring and recalibration are required.
- **The demo is not a case-management system.** Decisions are session-only, with no authentication, persistence, backend, or production audit integration.

This repository is an explainable prototype, not a production credit-decisioning system. Real deployment requires representative historical validation, legal and compliance review, security controls, authorised data access, model and rule governance, and human operating procedures.
