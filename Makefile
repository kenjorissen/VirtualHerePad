.DEFAULT_GOAL := check

UVX ?= uvx
PYTHON ?= python3
SHELLCHECK ?= shellcheck

# Keep local formatting and CI consistent. These are development-only tools.
RUFF_VERSION := 0.16.9
SHFMT_PY_VERSION := 4.2.0
RUFF = $(UVX) --from ruff==$(RUFF_VERSION) ruff
SHFMT = $(UVX) --from shfmt-py==$(SHFMT_PY_VERSION) shfmt
SHELL_FILES := $(wildcard *.sh) vhp-root

.PHONY: fmt lint test check

fmt:
	$(RUFF) check --fix .
	$(RUFF) format .
	$(SHFMT) -i 2 -ci -w $(SHELL_FILES)

lint:
	$(RUFF) check .
	$(RUFF) format --check .
	$(SHFMT) -i 2 -ci -d $(SHELL_FILES)
	$(SHELLCHECK) $(SHELL_FILES)
	@for script in $(SHELL_FILES); do bash -n "$$script" || exit; done

test:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest discover -s tests -v -b

check: lint test
