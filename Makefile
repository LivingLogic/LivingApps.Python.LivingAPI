.PHONY: install develop test build upload livinglogic


install:
	python$(PYVERSION) setup.py install


develop:
	python$(PYVERSION) setup.py develop


test: install
	python$(PYVERSION) -mpytest


build:
	rm -rf dist/*
	python$(PYVERSION) setup.py sdist --formats=gztar bdist_wheel


upload: build
	twine upload dist/*


livinglogic:
	rm -rf dist/*
	python$(PYVERSION) setup.py sdist --formats=bztar,gztar,zip
	python$(PYVERSION) setup.py bdist_wheel
	python$(PYVERSION) -mll.scripts.ucp -vyes dist/*.tar.gz dist/*.tar.bz2 dist/*.zip dist/*.whl ssh://intranet@intranet.livinglogic.de/~/documentroot/intranet.livinglogic.de/python-downloads/
