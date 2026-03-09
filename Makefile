# Run tests with coverage (same as GitHub Actions)
.PHONY: test
test:
	pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html --tb=short

# Run tests only, no coverage
.PHONY: test-fast
test-fast:
	pytest tests/ -v --tb=short
