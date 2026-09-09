.PHONY: docs test dist

docs:
	# pandoc --from=markdown --to=rst --output=README.rst README.md
	cp README.rst ./docs/index.rst

test:
	python -m unittest discover -s test -v

dist:
	python -m build
	# `setup.py upload` 은 PyPI 에서 폐기되었습니다. twine 을 쓰세요.
	python -m twine upload dist/*
