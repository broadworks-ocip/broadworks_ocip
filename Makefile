.PHONY: clean clean-test clean-pyc clean-build docs help code

help: ## Show this help
	@egrep -h '\s##\s' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: clean
clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

.PHONY: clean-build
clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	rm -fr site/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: clean-test
clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

.PHONY: lint
lint: ## check style with flake8
	poetry run flake8 ssh2_parse_key tests

.PHONY: test
test: ## run tests quickly with the default Python
	poetry run pytest

.PHONY: servdocs
servdocs: ## serve out the mkdocs documentation
	poetry run mkdocs serve

.PHONY: docs-serve
docs-serve: ## serve out the mkdocs documentation
	poetry run mkdocs serve

.PHONY: docs
docs: ## generate Sphinx HTML documentation, including API docs
	poetry run mkdocs build
	@echo docs generated into site directory

.PHONY: dist
dist: clean ## builds source and wheel package
	poetry build
	ls -l dist

schema.pkl: ocip_schema/*.xsd ocip_schema/Services/*.xsd ## Create the pickled schema
	poetry run python utilities/process_schema.py --schema ocip_schema/OCISchemaAS.xsd --pickle

.PHONY: code
code: schema.pkl ## Create requests,responses and types code from the schema
	poetry run python utilities/process_schema.py --unpickle

# end
