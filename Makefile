.PHONY: clean-pyc clean-build docs clean test lint
SHELL := /bin/bash

help:
	@echo "clean - remove all build, test, coverage and Python artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "clean-test - remove test and coverage artifacts"
	@echo "lint - check style with ruff and mypy"
	@echo "test - run pytest with coverage"
	@echo "coverage - check code coverage quickly with the default Python"
	@echo "release - package and upload a release"
	@echo "dist - package"

clean: clean-build clean-pyc clean-test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

lint:
	ruff check filerepack test
	mypy filerepack test --ignore-missing-imports

test:
	pytest --cov=filerepack --cov-report=term-missing

coverage:
	pytest --cov=filerepack --cov-report=html
	python -m webbrowser htmlcov/index.html

release: clean
	python -m build
	python -m twine upload dist/*

dist: clean
	python -m build
	ls -l dist
