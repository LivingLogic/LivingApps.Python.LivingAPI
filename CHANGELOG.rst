HEAD (2019-08-??)
-----------------

*	The ``HTTPHandler`` now delays logging into LivingApps until the first real
	request. Furthermore it automatically appends ``gateway/`` to the base URL
	and omits that part when constructing request URLs. The result of that it
	that it's possible to replace to base URL with something else after the
	``HTTPHandler`` has been created and before the first request is made.


0.10 (2019-07-24)
-----------------

*	Added support for saving uploads via the ``HTTPHandler``.

*	Added support for the attribute ``Globals.hostname``.


0.9 (2019-06-26)
----------------

*	Fixed shortcut attributes for the ``Globals`` object.

*	First Cheeseshop release.


0.8.2 (2019-06-13)
------------------

*	Expose the method ``Field.is_empty`` to UL4.
