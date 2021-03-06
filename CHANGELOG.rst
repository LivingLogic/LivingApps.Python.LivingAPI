0.13.0 (2020-09-17)
-------------------

*	Add support for "deferred" types in :class:`Attr`. This makes it possible
	to have cyclic references in attribute "declarations".

*	Add the attributes ``app`` and ``record`` to :class:`Globals`.

*	Accessing ``globals.templates`` or ``app.templates`` now fetches the
	templates via the handlers :meth:`fetch_templates` method (which only does
	something in :class:`DBHandler`).

*	:class:`DBHandler` now accepts either the ``account`` or the ``ide_id``
	argument.

*	Added :class:`FileSignatureControl` and :class:`HTMLControl`.


0.12.3 (2020-04-24)
-------------------

*	Remove debug prints.


0.12.2 (2020-04-24)
-------------------

*	Pass the handler to the fields when creating JSON for the
	:class:`HTTPHandler` or procedure arguments for the :class:`DBHandler`.
	This is used so that the correct ``VARCHARS`` type from the target database
	can be used when saving a record via a :class:`DBHandler`.

*	Fixed procedure argument handling for :class:`MultipleLookupControl` (the
	list value has to be wrapped in a ``VARCHARS`` object).


0.12.1 (2020-02-18)
-------------------

*	Fixed field validation for multiple lookup fields.


0.12 (2020-01-16)
-----------------

*	Removed debug code from ``DBHandler.meta_data``.

*	Add support for sets in vSQL.

*	When creating vSQL constants :class:`datetime` objects are no longer
	converted to vSQL date objects when the time portion of the :class:`datetime`
	object is zero.

*	Properly mark a record as deleted when it gets deleted via the
	:class:`DBHandler`.

*	View templates and internal templates can now be deleted via the
	:class:`DBHandler`.

*	Fixed handling of vSQL slices with missing start or stop indexes.

*	Add dependency on :mod:`Pillow`.

*	Allow communication with the :class:`HTTPHandler` with an existing
	authentication token.

*	Add proper handling of database exceptions to :meth:`DBHandler.save_record`.

*	Add more tests.

*	Handle recursion in :meth:`Record.__repr__`.

*	Its now possible to pass more than one error to :meth:`Record.add_error` and
	:meth:`Field.add_error`.

*	When uploading files via the :class:`HTTPHandler` pass along the MIME type.


0.11 (2019-08-15)
-----------------

*	The ``HTTPHandler`` now delays logging into LivingApps until the first real
	request. Furthermore it automatically appends ``gateway/`` to the base URL
	and omits that part when constructing request URLs. The result of that it
	that it's possible to replace the base URL with something else after the
	``HTTPHandler`` has been created and before the first request is made.
	(This makes it possible to talk to the gateway host directly on custom
	LivingApps installations.)

*	Added a ``force`` argument to the method ``Record.save()``. With
	``force=False`` (the default) any errors on the record or any of the fields
	will raise an exception. The ``force=True`` the record will be saved anyway.
	The return value indicated whether the record was really saved or the database
	or gateway returned an error. Referencing unsaved records or files are now
	handled in a similar way: ``force=False`` will raise an exception and
	``force=True`` will replace those references with ``None`` and add an error
	messsage to the field.

*	It is now possible to create a ``File`` object and pass the content to the
	constructor. This is useful when a file has to be uploaded but none of the
	supported methods for creating one via ``Handler.file()`` do the right thing.
	If content is passed, the mime type is ``image`` and the arguments
	``width`` and ``height`` are ``None`` the image size will be calculated
	automatically from the data (using :mod:`Pillow`).


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

*	Expose the method ``Field.is_empty()`` to UL4.
