# Learning Log — Invoice AI Assistant

A running log of how this project was built, kept as both a personal learning path and a
walkthrough that others can follow. Each session gets its own dated section.

**Stack**: Python, FastAPI, Strands Agents SDK, Amazon Bedrock, DynamoDB, S3.

**Author background**: experienced software engineer, learning Python, AWS, and the Strands
Agents SDK for the first time on this project.

---

## Session 1 — 2026-08-16: Project foundations, local AWS environment

### Goal for the day

Go from an empty repo to a working local development loop: a running FastAPI service, and a
local (cost-free) DynamoDB + S3 environment that Python code can talk to. No AI model calls yet —
that's deliberately deferred until the plumbing underneath it is proven to work.

### Business context

This is one module of a larger group project. The overall system does invoice processing with
**three-way matching** (PO vs goods-receipt vs invoice, reconciling quantities and amounts) — but
that matching logic is being built by a teammate, not this module.

This module's scope:
1. Upload an invoice file (PDF or photo).
2. Parse it into structured fields and store them in DynamoDB; store the raw file in S3.
3. An AI assistant (Strands Agent + Bedrock) answers natural-language questions over that stored
   data — summarization, lookups, eventually reports/BI.

The `Invoices` table still carries the quantity/amount/line-item fields that three-way matching
needs downstream, even though this module doesn't compute the match itself.

### Key concepts learned

**Python**
- `@app.get("/health")` is a *decorator* — not a "tag" or annotation. It's a real function call
  executed at import time that wraps the function below it. `@app.get("/health")` is shorthand for
  `health_check = app.get("/health")(health_check)`. Contrast with Java annotations, which are
  metadata read by reflection, not executed code.
- `FastAPI` is a *class*; you must instantiate it — `app = FastAPI()`, not `app = FastAPI`.
  Forgetting the `()` gives cryptic errors deep inside the library (e.g. `missing 1 required
  positional argument: 'path'`), because `app.get(...)` ends up calling an unbound method on the
  class instead of a method on an instance.
- Same bug pattern, different call: `load_dotenv` vs `load_dotenv()`. Without `()` the function
  never runs, so `.env` is silently never loaded — this manifested as a confusing
  `NoCredentialsError` from boto3 that had nothing to do with credentials being wrong; they were
  just never read in the first place.
- `os` (standard library) reads environment variables; `python-dotenv`'s `load_dotenv()` loads a
  `.env` file's contents *into* those environment variables so `os.getenv(...)` can see them.
  Keeping config in `.env` (gitignored) instead of hardcoded in source is what lets the same code
  point at local LocalStack today and real AWS later, by changing only the `.env` file.

**Tooling**
- `requirements.txt` is a dependency manifest for `pip` (equivalent to `package.json`), not
  something read by an AI. `pip freeze > requirements.txt` locks exact versions for reproducible
  installs.
- Gotcha: PowerShell's `>` redirection writes UTF-16LE by default, which produced a
  mojibake-looking `requirements.txt`. Regenerating it through a UTF-8-safe path (bash heredoc /
  explicit encoding) fixed it. Worth checking file encoding whenever a text file "looks broken" —
  errors like `pip: Invalid requirement` with null bytes between every character are the tell.
- CLI = "Command Line Interface" — typing commands instead of clicking a GUI. `aws dynamodb
  list-tables ...` is a single CLI invocation: tool name + service + action + flags. Same
  operations are possible by clicking through the AWS Console; CLI just makes them scriptable and
  repeatable.
- A venv's `Scripts/` folder (Windows) / `bin/` folder (Linux/Mac) holds the project-local copies
  of `python`, `pip`, and any installed package's CLI tools (like `uvicorn`). Once the venv is
  *activated* (prompt shows `(.venv)`), that folder is already on `PATH`, so the short command name
  is enough — no need to type the full path.

**FastAPI**
- `/docs` (Swagger UI) and `/redoc` are auto-generated from whatever routes you define — free, but
  not magic; they don't create endpoints for you. `/health` itself had to be written by hand.
- A 404 on `/` and `/favicon.ico` is expected and harmless if no route is defined for those paths.

**AWS fundamentals**
- Use an IAM user with a scoped policy for programmatic access, never long-lived root credentials.
- `aws configure --profile <name>` supports multiple named profiles side by side — kept a
  `localstack` profile (dummy `test`/`test` keys) separate from whatever real-AWS profile gets set
  up later for Bedrock, so the two never get mixed up.
- Even against a local mock endpoint, the AWS CLI/SDK still requires *some* credentials to be
  present locally, because request signing happens client-side regardless of where the request is
  actually going.

**Oracle → DynamoDB, conceptually** (full comparison table lives in the conversation this log
summarizes; the essentials):
- No schema beyond the declared key(s). `CREATE TABLE` (or `create-table`) only defines the
  partition key (and optional sort key) — every other attribute is decided per-item, at write
  time, and different items can carry different attributes.
- No `JOIN`. Related data is either denormalized into one item or fetched with a second query in
  application code.
- No `GROUP BY` / `SUM` / `COUNT`. Aggregation happens in application code (or via
  DynamoDB Streams + Lambda maintaining a summary table) — not explored yet.
- Only two read patterns: **Query** (efficient, requires the partition key) and **Scan** (reads
  the whole table — acceptable for a small dev dataset, avoid at scale).
- Design order is inverted from relational habits: in Oracle you normalize the schema first and
  write whatever query you need later; in DynamoDB you decide the access patterns first, and the
  table (and any secondary indexes) is designed around them.
- **PartiQL** is DynamoDB's SQL-*flavored* query language (`SELECT`/`INSERT`/`UPDATE`/`DELETE`),
  handy for ad-hoc exploration in the console, but it doesn't lift any of the underlying
  limitations above (still no joins/aggregates, still a Scan under the hood without a key
  condition). Decision: don't let the LLM generate PartiQL/text2sql-style queries at runtime —
  DynamoDB's lack of joins/aggregates and Scan-vs-Query cost cliff make dynamically generated
  queries both fragile and a potential injection surface. Instead, the Agent gets a small set of
  hand-written, parameterized query functions ("tools") to call — flexible enough for varied
  phrasing, fully controlled on the query-safety side.

**S3**
- Not a database — an object store. A *bucket* is a namespace; an *object* is a file identified by
  a *key* (a path-like string; S3 has no real nested folders, `/` in a key just looks like one).
  No content-based querying. Conceptually similar to moving a BLOB/CLOB out of the database into
  cheap, durable, dedicated storage, linked back via a stored key/path (`s3_key` in `Invoices`).

**Where parsing will eventually run** (decided direction, not yet built)
- **Amazon Bedrock Data Automation (BDA)**: a managed AWS service purpose-built for extracting
  structured fields from documents/images — an alternative to hand-rolling extraction prompts.
- **Lambda**: unrelated axis — it's *when/where* code runs (event-driven, e.g. triggered by an S3
  upload), not *what* the code does.
- Decision for the MVP: do our own extraction via a Strands Agent + Bedrock model call
  (reinforces the core skill this project is meant to teach), triggered synchronously from the
  FastAPI upload endpoint (not Lambda). BDA and an event-driven Lambda pipeline are both explicitly
  deferred as later upgrades, once the simple synchronous path works end-to-end.

**boto3**
- The high-level `resource` API (`boto3.resource("dynamodb")`) auto-converts DynamoDB numbers to
  Python `Decimal` (not `float`) — correct for money, but `Decimal` isn't JSON-serializable by
  default, so returning DB rows straight from a FastAPI endpoint will need a conversion step later.
- The low-level API (what the AWS CLI uses under the hood) requires explicit type tags per value,
  e.g. `{"S": "Acme Corp"}`, `{"N": "1250.00"}` — verbose on purpose, to show what boto3's
  high-level `resource` interface is hiding/simplifying.

### What got built today

- `requirements.txt` fixed to plain UTF-8; added and pinned `strands-agents==1.52.0`,
  `boto3==1.43.72`.
- `.gitignore` added (`.venv/`, `__pycache__/`, `*.pyc`, `.env`) — written *before* any secrets
  could land in git history.
- `app/main.py` — minimal FastAPI app with a `GET /health` endpoint, verified via `uvicorn
  app.main:app --reload`.
- Docker Desktop + LocalStack running locally (LocalStack's free tier now requires a free account
  and an `LOCALSTACK_AUTH_TOKEN`, unlike older versions).
- DynamoDB table `Invoices` created in LocalStack (partition key `invoice_id`, `PAY_PER_REQUEST`
  billing), seeded with one test item.
- S3 bucket `invoices-bucket` created in LocalStack (empty so far — nothing uploaded yet).
- `.env` (gitignored) holding local dev config: `DYNAMODB_ENDPOINT_URL`, `AWS_DEFAULT_REGION`,
  `AWS_PROFILE=localstack`.
- `app/db.py` — `get_invoices_table()` helper using boto3, endpoint/profile driven entirely by
  `.env` so the same code will point at real AWS later just by changing config, not code. Verified
  end-to-end: Python can read the seeded item back out of local DynamoDB.

### `Invoices` table schema (current)

| Field | Type | Notes |
|---|---|---|
| `invoice_id` | String (PK) | |
| `vendor` | String | |
| `invoice_date` | String (ISO date) | |
| `currency` | String | |
| `total_amount` | Number | |
| `po_number` | String | for the teammate's three-way-matching module to join on |
| `line_items` | List of maps | `{item_name, quantity, unit_price, amount}` — not yet exercised with real data |
| `s3_key` | String | path to the raw file in S3 — not yet exercised |
| `status` | String | e.g. `extracted`, `pending` |

### Command reference (LocalStack dev loop)

```bash
# Start LocalStack (first time / after removing the container)
docker run -d --name localstack -p 4566:4566 -e LOCALSTACK_AUTH_TOKEN=<token> localstack/localstack

# One-time local AWS CLI profile for LocalStack (dummy credentials — LocalStack doesn't validate them)
aws configure --profile localstack   # test / test / us-east-1 / json

# Create the table
aws dynamodb create-table --table-name Invoices \
  --attribute-definitions AttributeName=invoice_id,AttributeType=S \
  --key-schema AttributeName=invoice_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url http://localhost:4566 --region us-east-1 --profile localstack

# Create the bucket
aws s3 mb s3://invoices-bucket --endpoint-url http://localhost:4566 --region us-east-1 --profile localstack

# Insert sample data (Python/boto3 script — see below; superseded the original
# `aws dynamodb put-item --item file://seed-invoice.json` one-off used in this session
# to learn DynamoDB's low-level typed item format)
python -m scripts.seed_data

# Inspect
aws dynamodb scan --table-name Invoices --endpoint-url http://localhost:4566 --region us-east-1 --profile localstack
aws s3 ls --endpoint-url http://localhost:4566 --region us-east-1 --profile localstack
```

> Note: LocalStack's data doesn't persist across container restarts/removal by default. Everything
> above needs re-running after `docker rm localstack` + a fresh `docker run`, including
> `python -m scripts.seed_data` to repopulate sample data.

### Open items / not yet done

- Real AWS account: created, but no IAM user, no access keys configured locally, and Bedrock model
  access not yet requested in any region.
- `app/_init_.py` should be renamed to `app/__init__.py` (currently has no effect either way,
  since Python 3.3+ implicit namespace packages make it optional, but the name is wrong).

### Next session

**Milestone 3 — give the Agent tools.** Wrap `app/db.py`'s DynamoDB access in a small set of
purpose-built query functions (e.g. search by vendor, get by ID, sum by vendor/date range),
register them as Strands Agent tools, and wire a `POST /ask` FastAPI endpoint on top. Real Bedrock
access (IAM user + model access request) needs to happen before that endpoint can actually be
exercised end-to-end, even though the tool functions themselves can be written and unit-tested
against LocalStack first.

---

## Session 2 — 2026-08-17: Agent tools, real Bedrock access, FastAPI + Streamlit wired end-to-end

### Goal for the day

Finish milestone 3 (DynamoDB query functions as Strands tools), get real AWS Bedrock access
working (separate from the LocalStack setup), wire a `POST /ask` FastAPI endpoint on top of the
Agent, and stand up a minimal Streamlit frontend calling it — i.e. prove the whole front-to-back
loop end-to-end, even if the very last hop (an actual model reply) ends up blocked on account
approval rather than code.

### Key concepts learned

**Python, deeper dive**
- `dict` ≈ Java `Map<K,V>`; Python is dynamically typed, so no generic type declarations.
- `dict | None` (Python 3.10+ union syntax; `Optional[dict]` pre-3.10) ≈ Java's `@Nullable
  Map<K,V>` / `Optional<Map<K,V>>` — but critically, **Python's own interpreter does not enforce
  type hints at runtime**. They're documentation/tooling metadata (read by IDEs, `mypy`, etc.),
  not a compiler guarantee like Java's type system.
- Exception to the above: **Strands' `@tool` decorator actually reads type hints and docstrings
  at runtime** to build the tool's parameter schema for the LLM — so in this specific context,
  hints and docstrings are functionally load-bearing, not just decorative.
- PEP 8 is Python's de facto style guide (≈ a shared Checkstyle config) — 2 blank lines between
  top-level defs, 1 between methods; not enforced by the interpreter, but universally followed and
  usually auto-applied by formatters like `black`/`ruff`.
- Google-style docstrings (`Args:` section, one line per parameter) are a community convention,
  not special syntax — but `docstring_parser` (a Strands dependency) parses this exact structure
  to extract per-parameter descriptions for the tool schema.
- `boto3.Session` (capital S, a class) vs `boto3.session` (lowercase, the module containing that
  class) — easy one-character typo, produces `TypeError: 'module' object is not callable`.

**Running package code correctly (the recurring bug of the day)**
- `python app/tools.py` (running a file directly) sets `sys.path[0]` to the file's *own*
  directory (`app/`), so `app` itself isn't importable as a package from inside a file that does
  `from app.db import ...` → `ModuleNotFoundError: No module named 'app'`.
- Fix: run as a module from the project root instead — `python -m app.tools`, `python -m
  app.agent`. This puts the project root on `sys.path[0]` and lets `app.*` resolve correctly.
  `db.py` never hit this because it has no internal `app.*` import; `uvicorn app.main:app` never
  hits it either, because uvicorn already imports `app.main` as a module the same way.

**AWS / IAM**
- IAM (Identity and Access Management) ≈ the permission system behind every AWS account: **users**
  (an identity, roughly like a Linux user account) get **policies** (JSON documents describing
  allowed/denied actions) attached to them. Never use root account credentials for
  programmatic/CLI access — create a scoped IAM user instead, so a leaked key's blast radius is
  limited to what that policy allows.
- Kept a second named CLI profile (`bedrock`, real AWS) separate from the earlier `localstack`
  profile (fake creds, local only) — `boto3.Session(profile_name=...)` picks between them
  explicitly in code, so the two never collide.

**Bedrock inference types** — this was the main practical rabbit hole today:
- **On-Demand**: call the base `modelId` directly, pay per token. Many models support this; some
  newer ones don't.
- **Cross-Region inference (inference profiles)**: some models — Claude Haiku 4.5 among them —
  *only* support this. You call an inference-profile ID instead of the base model ID (e.g.
  `us.anthropic.claude-haiku-4-5-20251001-v1:0` or `global.anthropic.claude-haiku-4-5-20251001-v1:0`),
  found via `aws bedrock list-inference-profiles`. AWS routes the request across a region or the
  globe under that ID. Model access is granted once, at the base-model level — it's not a
  separate grant per inference-profile variant; whichever profile ID you call, it's still checking
  access against the same underlying model.
- **Provisioned Throughput**: paid reserved capacity, billed hourly regardless of usage — not
  relevant for a low-volume learning project.
- Confirmed via a real `aws bedrock-runtime invoke-model` call that error *type* tells you which
  layer failed: `AccessDeniedException` → permissions; `ValidationException` (ours: "on-demand
  throughput isn't supported... use an inference profile") → wrong call shape; `ThrottlingException`
  ("Too many tokens per day") → request was authenticated and routed correctly, just rate-limited.
  New Bedrock accounts get conservative default daily-token quotas; raising them means a Service
  Quotas increase request, which can take AWS support some time to approve (still pending at
  session end).

**Operational gotcha: orphaned `uvicorn --reload` workers**
- After a bad edit crashed uvicorn's auto-reload worker, killing the *reloader* process (the PID
  uvicorn prints at startup) did not kill the already-spawned *worker* child process — the old
  worker kept running independently, still bound to the port, still serving the stale
  pre-edit code. Symptom was confusing: `/health` kept responding (from the orphaned old worker),
  new routes 404'd (also from the same stale worker), and `netstat` briefly showed two PIDs both
  claiming to `LISTEN` on the same port. Fix: identify every `python.exe` process actually
  associated with the dev servers (cross-check against `netstat -ano` for the specific ports),
  kill all of them, then start one truly fresh process. Lesson: when a reload/restart produces
  behavior that doesn't match the current file on disk, don't trust that the running process
  reflects the code — verify independently (e.g. `python -c "from app.main import app; print(app.routes)"`)
  before spending time debugging the code itself.

### What got built today

- `app/tools.py`: `get_invoice_by_id` and `search_invoices_by_vendor`, both decorated `@tool`
  with Google-style docstrings, wrapping `app/db.py`'s table access.
- Real AWS Bedrock access: dedicated IAM user (`invoice-ai-bedrock`, `AmazonBedrockFullAccess`
  policy only — no Service Quotas or other permissions), local `bedrock` CLI profile, Claude
  Haiku 4.5 model access requested and granted in `us-east-1`.
- `app/agent.py`: `build_agent()` constructs a `BedrockModel` (via a `boto3.Session` scoped to the
  `bedrock` profile) and a Strands `Agent` wired to the two tools above. Model ID and profile name
  both come from `.env` (`BEDROCK_AWS_PROFILE`, `BEDROCK_MODEL_ID`), kept separate from the
  DynamoDB-focused `AWS_PROFILE`/`DYNAMODB_ENDPOINT_URL` vars so local-dev and real-AWS credentials
  never collide.
- `app/main.py`: `POST /ask` endpoint (Pydantic `AskRequest` body) that builds a fresh Agent per
  request (deliberately stateless — no cross-request conversation memory yet) and returns
  `str(result)`.
- `scripts/seed_data.py`: five sample invoices across three vendors and two statuses, via boto3's
  high-level `resource` API (plain Python dicts, no manual `{"S": ...}` type tags) — supersedes and
  replaces the one-off `seed-invoice.json` used in Session 1 to teach the low-level item format
  (that file has been deleted; the CLI command it supported is no longer part of the reproducible
  setup flow).
- `frontend/app.py`: minimal Streamlit chat UI (`st.chat_message`/`st.chat_input`), posts to the
  FastAPI `/ask` endpoint via `requests`, renders the answer or a caught request error.
- `.streamlit/credentials.toml` created locally (not project-specific — this is a one-time,
  per-machine Streamlit config) to pre-answer the interactive first-run "email?" onboarding prompt
  that otherwise blocks non-interactive/background startup.

### Verified end-to-end (up to the external blocker)

`python -m app.agent` successfully built the session, the Bedrock model, the Agent, registered
both tools, and made a real, correctly authenticated, correctly routed `ConverseStream` call to
Bedrock — confirmed by getting a `ThrottlingException` (not a permissions or validation error) as
the final result. Same confirmed through the FastAPI `/ask` route once the endpoint and its
imports were fixed. **The code path is proven correct end-to-end; the only remaining blocker is
the pending Bedrock daily-token quota increase**, which is an AWS approval queue, not something to
debug further on our side.

### Bugs hit and fixed today (for the pattern-recognition value, not the specifics)

- Parameter name typo (`invocice_id`) not matching the docstring's `invoice_id`.
- `table = get_invoices_table` missing `()` — same "forgot to call it" class of bug as
  `app = FastAPI` and `load_dotenv` from Session 1, now three-for-three. Worth internalizing:
  whenever something behaves like "has no such method," check whether it was ever actually
  *called*, not just referenced.
- `response.get("Item", [])` after a `scan()` — should be `"Items"` (plural); `get_item` returns
  singular `"Item"`, `scan`/`query` return plural `"Items"`. Silent bug (no crash, just always
  empty), the sneakiest kind.
- Test code calling the wrong function (`get_invoices_table("inv-001")` instead of
  `get_invoice_by_id("inv-001")`) — easy to do when a low-level helper and a business-level
  wrapper have similar names.
- `boto3.session(...)` vs `boto3.Session(...)` capitalization.
- `from app.agent import BaseModel` instead of `from app.agent import build_agent` — an
  autocomplete misfire (similar-looking suggestions).

### Open items / not yet done

- **Blocking**: Bedrock daily-token quota increase still pending AWS approval. Nothing else to do
  here except wait and re-test once approved.
- `app/_init_.py` still needs renaming to `app/__init__.py` (harmless typo, carried over from
  Session 1).
- No conversation memory across `/ask` requests yet (each call builds a stateless Agent).
- S3 is still empty — no file has been uploaded yet, and nothing reads from it. Deliberately
  deferred: everything the Agent currently answers comes from already-extracted DynamoDB fields;
  a tool that reads the raw file from S3 only becomes necessary for questions the structured data
  can't answer (e.g. "is there a signature/stamp on this invoice," or handing back a link to the
  original document) — see the roadmap below for when that becomes relevant.

### Next session

Once the Bedrock quota increase is approved: re-run `python -m app.agent` (or hit `/ask` through
Streamlit) to confirm a real model answer comes back, referencing the seeded sample data (e.g. "how
much did we spend with Acme Corp total?" should require the Agent to call
`search_invoices_by_vendor` and reason over multiple line items). Then move to milestone 5: a file
upload endpoint (PDF/photo → parse via a Strands Agent call → write structured fields to DynamoDB +
raw file to S3).

---

## Roadmap (living)

1. ~~Data model definition~~ ✅
2. ~~Local DynamoDB + S3 environment (LocalStack), seeded test data~~ ✅
3. ~~Agent tools (DynamoDB query functions wired into Strands)~~ ✅
4. ~~`POST /ask` conversational endpoint (Strands Agent + Bedrock) + minimal Streamlit frontend~~ ✅
   code-complete; blocked on pending Bedrock quota approval for a real end-to-end answer
5. File upload endpoint: PDF/photo → parse → write to DynamoDB + S3 — **next**
6. Reports / BI-style structured aggregation output
7. Later: swap hand-rolled parsing for Bedrock Data Automation; move parsing to an
   S3-event-triggered Lambda instead of running synchronously in FastAPI
8. Later: package this FastAPI app with Mangum for Lambda deployment, to match how the rest of
   the team's system runs (see Session 3 note below) — only needed once this module has to be
   reachable by the rest of the team's system, not for local development

---

## Session 3 — 2026-08-18: Team stack context (no code changes)

Learned the wider group project's stack from a teammate, for context — this repo stays
independent, nothing here changed as a result:

- **Frontend**: React 18.3.1 + TypeScript, React Router 6.26, Vite, Tailwind CSS, Vitest + React
  Testing Library. This is the *real* production frontend the team is building; the Streamlit app
  in this repo remains just a local dev/debug tool for exercising `/ask` — no conflict, since both
  are just HTTP clients against the same JSON API. Nothing here needs to change when the real
  frontend is React instead of Streamlit.
- **Backend**: FastAPI 0.115.0, Uvicorn 0.30.0, Pydantic 2.9.0, Boto3 — same core stack as this
  project, different pinned versions.
- **Mangum 0.17.0** in their dependency list is the signal worth remembering: Mangum is an adapter
  that wraps an ASGI app (like FastAPI) so it can run inside **AWS Lambda** instead of a
  long-running Uvicorn process — Lambda starts on-demand per request rather than staying always-on.
  This means the team's real backend deployment target is Lambda, not a persistent server.

**Decision**: this repo (and its module) stays a fully independent service — no code merge, no
need to match the team's exact dependency versions, since integration will happen over an API
boundary, not a shared codebase. If/when this module needs to be reachable from the team's system,
wrapping `app/main.py` with Mangum for Lambda deployment (roadmap item 8) is the way to match their
operational pattern — not required for continued local development.
28