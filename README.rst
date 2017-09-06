``livapps`` provides a Python API for the LivingApps system
(see http://www.living-apps.de/ or http://www.living-apps.com/ for more info).

``livapps`` allows you to fetch the configured data sources from a template,
create new records, and update and delete existing records all from your Python
prompt (or script).


Installation
------------

``livapps`` requires at least Python 3.5. You will also need ``venv`` and the
Python dev package (as well as a C compiler), which might not be part of the
standard Python installation on your system. All this can be installed with::

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

==========  ==============  =========  ================================================
Label       Identifier      Type       Comment
==========  ==============  =========  ================================================
First name  ``firstname``  ``string``
Last name   ``lastname``   ``string``
Salutation  ``salutation`` ``lookup``  choices ``mr`` ➝ ``Mr.`` and ``mrs`` ➝ ``Mrs.``
Birth day   ``birthday``   ``date``
Location    ``location``   ``geo``
==========  ==============  =========  ================================================


To get into IPython type::

	$ ipython3
	Python 3.5.1 (default, Jan 22 2016, 11:57:23)
	Type 'copyright', 'credits' or 'license' for more information
	IPython 6.1.0 -- An enhanced Interactive Python. Type '?' for help.
	In [1] ▶

Import the ``livapps`` module::

	In [1] ▶ import libapps

Then login to LivingApps::

	In [2] ▶ login = livapps.Login("https://my.living-apps.de/", "username", "password")


Author
------

Walter Dörwald <walter@livinglogic.de>
