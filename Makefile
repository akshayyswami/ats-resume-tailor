.PHONY: setup fmt check evals evals-check

setup:
	uv sync
	uv run pre-commit install

fmt:
	uv run ruff format .
	uv run ruff check --fix .

# Runs exactly what CI runs.
check:
	uv run pre-commit run --all-files
	uv run mypy
	uv run pytest --cov
	$(MAKE) evals-check

# Re-measure and overwrite evals/results/latest.json. Commit the result.
evals:
	uv run python evals/measure.py > evals/results/latest.json.tmp
	mv evals/results/latest.json.tmp evals/results/latest.json

# Fail if measure.py disagrees with the committed latest.json, or a README figure disagrees with it.
evals-check:
	@tmp="$$(mktemp)"; \
	uv run python evals/measure.py > "$$tmp"; rc=$$?; \
	if [ $$rc -eq 0 ]; then diff -u evals/results/latest.json "$$tmp"; rc=$$?; fi; \
	rm -f "$$tmp"; \
	if [ $$rc -ne 0 ]; then echo "evals-check: measure.py output differs from evals/results/latest.json (run make evals)"; exit $$rc; fi
	uv run python scripts/check-readme-numbers.py
