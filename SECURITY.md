# Security Policy

## Scope and context

`territorio-engine` is a research and civic-tech project. It serves **public
open data** through a **read-only** API and stores no personal data, no user
accounts, and no credentials beyond the API keys an operator supplies for third
party data providers (for example `AEMET_API_KEY`).

There is no hosted deployment. The threat model is therefore limited to people
running the stack themselves.

## Reporting a vulnerability

Please report security issues **privately**, not as a public issue:

- Use GitHub's [private vulnerability
  reporting](https://github.com/igoikofanega/territorio-engine/security/advisories/new)
  on this repository.

Please include what you found, how to reproduce it, and what an attacker could
achieve. I will acknowledge within a few days. As a solo, unfunded project I
cannot promise a formal SLA, but genuine issues will be prioritised over
features.

## Things worth reporting

- SQL injection in the API. Query construction uses `sqlalchemy.text()` with
  bound parameters; any path where user input reaches SQL unparameterised is a
  real bug.
- Secrets committed to the repository or leaked in logs or Docker images.
- Path traversal or arbitrary write in the ingestion pipelines, which write to
  the `raw/` landing zone.
- Prompt injection in the LLM layer that escalates beyond producing wrong
  labels — for example causing SQL execution or arbitrary network calls.

## Things that are known and out of scope

These are deliberate properties of a local-only development stack, not
vulnerabilities:

- The default database credentials in `.env.example` (`territorio`/
  `territorio`). Anyone exposing this stack to a network must change them.
- The absence of authentication on the API, Dagster UI and MLflow UI. All of
  them are meant to be bound to localhost.
- `verify=False` on the AEMET client, which works around that provider's
  certificate chain. It is scoped to that one host.
- Inaccurate model predictions or wrong data. Those are correctness bugs —
  please open a normal public issue for them.
