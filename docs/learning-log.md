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

# Insert a test item (via a JSON file — avoids shell-escaping pain)
aws dynamodb put-item --table-name Invoices --item file://seed-invoice.json \
  --endpoint-url http://localhost:4566 --region us-east-1 --profile localstack

# Inspect
aws dynamodb scan --table-name Invoices --endpoint-url http://localhost:4566 --region us-east-1 --profile localstack
aws s3 ls --endpoint-url http://localhost:4566 --region us-east-1 --profile localstack
```

> Note: LocalStack's data doesn't persist across container restarts/removal by default. Everything
> above needs re-running after `docker rm localstack` + a fresh `docker run`. A future session
> should turn this block into a small setup script instead of retyping it by hand each time.

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

## Roadmap (living)

1. ~~Data model definition~~ ✅
2. ~~Local DynamoDB + S3 environment (LocalStack), seeded test data~~ ✅
3. Agent tools (DynamoDB query functions wired into Strands) — **next**
4. `POST /ask` conversational endpoint (Strands Agent + Bedrock)
5. File upload endpoint: PDF/photo → parse → write to DynamoDB + S3
6. Reports / BI-style structured aggregation output
7. Later: swap hand-rolled parsing for Bedrock Data Automation; move parsing to an
   S3-event-triggered Lambda instead of running synchronously in FastAPI
