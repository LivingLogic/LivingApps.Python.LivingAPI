.PHONY: install develop test build upload livinglogic


install:
	python$(PYVERSION) setup.py install


develop:
	python$(PYVERSION) setup.py develop


test: install
	python$(PYVERSION) -mpytest


build:
	# remove a stale SOURCES.txt, otherwise its old file list gets merged into the new package
	rm -rf dist/* src/ll_la.egg-info
	# setuptools-scm is installed, which would add all GIT controlled files to the package
	# we dont want that, so set `SETUPTOOLS_SCM_IGNORE_VCS_ROOTS`
	SETUPTOOLS_SCM_IGNORE_VCS_ROOTS=$(CURDIR) python$(PYVERSION) setup.py sdist --formats=gztar bdist_wheel


upload: build
	twine upload dist/*


livinglogic: build
	rm -rf dist/*
	SETUPTOOLS_SCM_IGNORE_VCS_ROOTS=$(CURDIR) python$(PYVERSION) setup.py sdist --formats=gztar
	SETUPTOOLS_SCM_IGNORE_VCS_ROOTS=$(CURDIR) python$(PYVERSION) setup.py bdist_wheel
	python$(PYVERSION) -mll.scripts.ucp -vyes dist/*.tar.gz dist/*.whl ssh://intranet@intranet.livinglogic.de/~/documentroot/intranet.livinglogic.de/python-downloads/
