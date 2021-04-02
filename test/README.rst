For configuring which LivingApps installation to test, the following
three environment variables are used:

.. envvar:: LA_LIVINGAPI_TEST_CONNECT
	The connectstring for the database.

.. envvar:: LA_LIVINGAPI_TEST_UPLOADDIR
	The upload directory for files, as an ``ssh:`` URL.

.. envvar:: LA_LIVINGAPI_TEST_HOSTNAME
	The hostname of the installation, which is use for making HTTP requests

For configuring which LivingApps user account is used for executing the tests,
the following two environment variables are used:

.. envvar:: LA_LIVINGAPI_TEST_USER
	The account name (i.e. the email address) of the account to use.

.. envvar:: LA_LIVINGAPI_TEST_PASSWD
	The password of the account to use.

The tests work with two apps that are supposed to store information about
famous persons and their fields of activity. Their IDs are fetched from the
following two environment variables:

.. envvar:: LA_LIVINGAPI_TEST_FIELDAPP
	The id of the app containing fields of activity.

.. envvar:: LA_LIVINGAPI_TEST_PERSONAPP
	The id of the app containing famous persons.

The first app stores the fields of activity (like science, art, etc). This
app must have the following fields:

+------------+----------------------+------------------------------+
+ Identifier | Type                 | Comment                      |
+============+======================+==============================+
| ``name``   | ``string/text``      |                              |
+------------+----------------------+------------------------------+
| ``parent`` | ``applookup/select`` | Target app is the app itself |
+------------+----------------------+------------------------------+

The second app stores information about the persons and must have the following
fields:

+--------------------------+------------------------------+--------------------------+
+ Identifier               | Type                         | Comment                  |
+==========================+==============================+==========================+
| ``firstname``            | ``string/text``              |                          |
+------------------------------------------------------------------------------------+
| ``lastname``             | ``string/text``              |                          |
+------------------------------------------------------------------------------------+
| ``sex``                  | ``lookup/radio``             | Options are:             |
|                          |                              | * ``male``               |
|                          |                              | * ``female``             |
+------------------------------------------------------------------------------------+
| ``field_of_activity``    | ``multipleapplookup/select`` | Target is the fields app |
+------------------------------------------------------------------------------------+
| ``country_of_birth``     | ``lookup/select``            | Options are:             |
|                          |                              | * ``germany``            |
|                          |                              | * ``poland``             |
|                          |                              | * ``usa``                |
+------------------------------------------------------------------------------------+
| ``date_of_birth``        | ``date/date``                |                          |
+------------------------------------------------------------------------------------+
| ``date_of_death``        | ``date/date``                |                          |
+------------------------------------------------------------------------------------+
| ``grave``                | ``geo``                      |                          |
+------------------------------------------------------------------------------------+
| ``portrait``             | ``file``                     |                          |
+------------------------------------------------------------------------------------+
| ``url``                  | ``string/url``               |                          |
+------------------------------------------------------------------------------------+
| ``notes``                | ``string/textarea```         |                          |
+------------------------------------------------------------------------------------+
| ``nobel_prize``          | ``bool``                     |                          |
+------------------------------------------------------------------------------------+
| ``email2``               | ``string/email``             |                          |
+------------------------------------------------------------------------------------+
| ``phone``                | ``string/tel``               |                          |
+------------------------------------------------------------------------------------+
| ``country_of_residence`` | ``multiplelookup/select``    | Options are:             |
|                          |                              | * ``germany``            |
|                          |                              | * ``poland``             |
|                          |                              | * ``usa``                |
+------------------------------------------------------------------------------------+
| ``consent``              | ``bool``                     |                          |
+------------------------------------------------------------------------------------+
