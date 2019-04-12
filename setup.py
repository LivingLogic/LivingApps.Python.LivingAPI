# -*- coding: utf-8 -*-

# Setup script for LivingApps SDK

import re

import setuptools


DESCRIPTION = """
:mod:`ll.la` is a Python module for accessing data from LivingApps
(http://www.living-apps.de/)
"""

CLASSIFIERS = """
Development Status :: 3 - Alpha
Intended Audience :: Developers
License :: OSI Approved :: MIT License
Operating System :: OS Independent
Programming Language :: Python
Programming Language :: Python :: 3 :: Only
Programming Language :: Python :: 3
Programming Language :: Python :: 3.6
Topic :: Software Development :: Libraries :: Python Modules
Topic :: Internet :: WWW/HTTP
"""

KEYWORDS = """
LivingApps
"""

try:
	news = list(open("docs/NEWS.rst", "r", encoding="utf-8"))
except IOError:
	description = DESCRIPTION.strip()
else:
	# Extract the first section (which are the changes for the current version)
	underlines = [i for (i, line) in enumerate(news) if line.startswith("---")]
	news = news[underlines[0]-1:underlines[1]-1]
	description = "{DESCRIPTION.strip()}\n\n\n{}".format("".join(news))

# Get rid of text roles PyPI doesn't know about
description = re.subn(":[a-z]+:`~?([-a-zA-Z0-9_./]+)`", "``\\1``", description)[0]

# Expand tabs (so they won't show up as 8 spaces in the Windows installer)
description = description.expandtabs(2)

args = dict(
	name="ll.la",
	version="0.8.1",
	description="Python API for LivingApps",
	long_description=description,
	author="Walter Doerwald",
	author_email="walter@livinglogic.de",
	url="http://github.com/LivingLogic/LivingApps.Python.LivingAPI",
	license="MIT",
	python_requires=">=3.6",
	classifiers=sorted({c for c in CLASSIFIERS.strip().splitlines() if c.strip() and not c.strip().startswith("#")}),
	keywords=", ".join(sorted({k.strip() for k in KEYWORDS.strip().splitlines() if k.strip() and not k.strip().startswith("#")})),
	package_dir={"": "src"},
	packages=["ll.la"],
	install_requires=[
		"ll-xist >= 5.31",
		"requests >= 2.18.4",
		"geocoder >= 1.30.1"
	],
	zip_safe=False,
)

if __name__ == "__main__":
	setuptools.setup(**args)
