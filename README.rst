``livapps`` provides a Python API for the LivingApps system
(see http://www.living-apps.de/ or http://www.living-apps.com/ for more info).

``livapps`` allows you to fetch the configured data sources from a template,
create new records, and update and delete existing records all from Python
prompt (or script).


Installation
------------

``livapps`` requires at least Python 3.5. You will also need ``venv`` and the
Python dev package, which might not be part of the standard Python installation
on your system. Both can be installed with::

	apt-get install python3.5-venv python3.5-dev

(or the equivalent for your system).

To install ``livapps`` itself do the following::

	pip install git+https://github.com/LivingLogic/LivingApps.Python.LivingAPI.git

This should also install the required packages ``ll-xist``, ``requests`` and
``geocoder``.

To simplify interactive work it might be useful to install IPython with::

	pip install ipython


Preparing your apps
-------------------

To be able to access your apps, you have to configure export templates for them.
For this refer to LivingApps' expert documentation.

The short version: Add a list template under ``Konfiguration`` ➝ ``Erweitert``
➝ ``Anzeige-Templates``. Give it the ``Identifizierer`` ``export``, set it's
``Typ`` to ``Liste`` and select ``Standard?``. Add the data sources you need
under ``Datenquellen``.


Examples
--------

All the following examples will assume we're using IPython and we have an app
for storing information about persons with the following fields:

Firstname : identifier ``firstname``, type ``string``
	First name of the person

Lastname : identifier ``lastname``, type ``string``
	Last name of the person


Author
------

Walter Dörwald <walter@livinglogic.de>
