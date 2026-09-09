# Contributing

Create an isolated Python 3.11+ environment and install `pip install -e ".[dev]"`. Run `ruff check .`, `mypy src/llm_analyzer`, `pytest` and `python scripts/validate_catalog.py` before proposing a change. Core tests use synthetic Windows profiles on any OS; live scanner tests require Windows x64.

Keep platform APIs inside hardware providers and runtime discovery. Recommendation logic must remain deterministic and independent of IO, CLI and presentation. New capabilities need explicit evidence and unknown handling. Preserve the distinction between installed/currently available RAM, dedicated/shared graphics memory and driver/Toolkit support.

Catalog changes need authoritative publisher/config/artifact sources, revision or date evidence, complete shard accounting, supported quantizations, and a fixture case that exercises the changed behavior. Do not turn marketing claims into compatibility facts. See docs/sources.md and docs/methodology.md.

When changing schemas, review backward compatibility and regenerate JSON schemas using `python scripts/validate_catalog.py --write-schemas`. Use a new schema version for breaking changes. Regenerate synthetic fixtures with `python scripts/generate_fixtures.py`; never commit a personal machine scan as a fixture.

Report writes must not overwrite without explicit `--force`, input files must not execute code, and normal analysis must remain offline. Tests should verify meaningful boundary behavior rather than duplicate implementation details. See SECURITY.md for confidential vulnerability reporting.

Contributions are licensed under Apache-2.0. Keep model and dependency licensing separate from project licensing.
