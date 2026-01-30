HEAD (2026-??-??)
-------------------

*	Update internal version number of the LivingAPI to 139.

*	Made the attribute ``Stringcontrol.placeholder`` settable and mirror the
	attribute in ``StringField`` (where	the attribute is settable too and
	inherits the controls value).


0.54.0 (2026-01-14)
-------------------

*	Update internal version number of the LivingAPI to 138.

*	Added the ``Control`` attributes ``in_structured_search``, ``in_fulltext_search``
	and ``in_expert_search``.


0.53.1 (2025-12-15)
-------------------

*	Update version number of the LivingAPI to 137.


0.53.0 (2025-12-08)
-------------------

*	Update to XIST 5.82.1 and use the vSQL defined there (instead of our own).

*	Add the method ``App.aggregate_records``.


0.52.2 (2025-11-26)
-------------------

*	Fixed member templates for ``Geo`` objects.


0.52.1 (2025-11-18)
-------------------

*	Fixed logic for determining whether a template is a bound member templates
	for templates that are bound to a specific ``Field`` or ``Control`` instance.


0.52.0 (2025-11-18)
-------------------

*	Added methods ``AppGroup.count_records``, ``AppGroup.fetch_records`` and
	``AppGroup.fetch_recordpage``.

*	Added support for ``AppGroup`` member templates.

*	Changed the way internal and library templates are fetched and cached:
	Now they will be fetched and cached for each supported LivingAPI type
	independently instead of all in one dictionary.


0.51.2 (2025-10-28)
-------------------

*	Update version number in ``setup.py``.


0.51.1 (2025-10-28)
-------------------

*	``DatasourceChildren.filter`` is a ``list`` now.


0.51.0 (2025-10-21)
-------------------

*	Python 3.14 is required now, since we're using type hints that only work
	with deferred annotations.
*	Added class ``Permissions`` and attribute ``App.permissions``.
*	Added attribute ``App.recordpage``.
*	Added attribute ``Globals.user_record``.
*	Added attributes ``App.filter_default``, ``App.sort_default`` and
	``App.filter_owndata``.
*	Added methods ``Record.fetch_child_records``, ``Record.count_child_records``
	and ``Record.fetch_child_recordpage``.


0.50.2 (2025-09-16)
-------------------

*	Fixed attribute name in ``AppLookupControl.vsqlfield``
*	Remove debug ``print``\s.


0.50.1 (2025-09-10)
-------------------

*	Fixed join condition in ``App.vsqlfield_app`` and ``App.vsqlfield_records``
	to use an inner join instead of an outer join.


0.50.0 (2025-08-21)
-------------------

*	Added a vSQL method ``vsql.Query.register_vsql`` to force the table referenced
	by a vSQL variable to be included in the "from" list.
*	Added UL4 attribute ``App.internal_id``, ``Globals.free``,
	``DataSource.filter``, ``DataSource.sort``, ``DataSourceChildren.filter`` and
	``DataSourceChildren.sort``.
*	Added methods ``App.count_records()``, ``App.delete_records()`` and
	``App.fetch_records()`` that use dynamic vSQL queries to count, delete and
	fetch records of an app.
*	Added support for "offset" and "limit" clauses to vSQL queries.


0.49.0 (2025-08-04)
-------------------

*	Add additional vSQL methods for request parameters and other global
	information.
*	Fix :meth:`ll.la.Record.send_mail`.
*	Always use the ``{a}`` table alias in vSQL expressions for fields.
*	Java source code for vSQL expressions now also knows the Oracle source code.
*	Add the attributes ``App.ai_generated``, ``AppGroup.description`` and
	``AppGroup.image``.


0.48.0 (2025-06-24)
-------------------

*	Parameters of an app group now inherit the library parameters too.
	However for parameters of an app the library parameters will be ignored
	during traversal of the app group. The library parameters will only be used
	as the ultimate fallback.

*	``AppParameter`` objects now support member templates.

*	``Control.mode`` is now settable.

*	Add support for custom attributes to ``AppParameter``.

*	Update name of ``AppParameter`` type ``str`` to ``string``.

*	The attribute ``App.recordcount`` has been renamed to ``record_total``.
	Attributes ``record_start`` and ``record_count`` have been added that
	contain paging information (when paging parameters are in use or vSQL
	expressions for paging have been configured).

*	Similar attributes (``record_total``, ``record_start`` and ``record_count``)
	have been added to ``RecordChildren``.


0.47.0 (2025-05-20)
-------------------

*	Added support for :class:`ll.la.AppParameter`\s attached to
	:class:`ll.la.AppGroup`\s.

*	Added method :meth:`ll.la.AppGroup.add_param`.

*	The signature of :meth:`ll.la.App.add_param` has changed to
	``(self, identifier, *, type=None, description=None, value=None)``.

*	Removed unused class :class:`ll.la.TemplateLibrary`.

*	The methods :meth:`ll.la.Record.save` and  :meth:`ll.la.AppParameter.save`
	will do nothing when the record or parameter have been deleted before.


0.46.2 (2025-04-24)
-------------------

*	Fixed wrong variable name in :meth:`ll.la.vsql.VSQLUnknownFieldError.detail`.


0.46.1 (2025-04-23)
-------------------

*	Fixed wrong variable name in :meth:`ll.la.vsql.VSQLUnknownNameError.detail`.


0.46.0 (2025-04-23)
-------------------

*	Methods of :meth:`ll.la.vsql.Query` that take vSQL expressions as an argument,
	now have the suffix ``_vsql`` in their name. Versions that take "raw" SQL
	have been added with the name suffix ``_sql``.

*	It is no longer possible to pass multiple expressions to
	:meth:`ll.la.vsql.Query.select` or :meth:`ll.la.vsql.Query.where`.

*	It is now possible to add field aliases for the selected fields in
	:meth:`ll.la.vsql.Query.select`.

*	It is now possible to pass additional expressions to
	:meth:`ll.la.vsql.Query.sqlsource` for the list of tables to select from.

*	The ``fieldsql`` attribute of :class:`ll.la.vsql.Field` objects now should
	contain the placeholder ``{a}`` for the table alias.

*	:meth:`ll.la.Globals.scaled_url` now complains if the ``image`` argument isn't
	of type :class:`~ll.la.File` or :class:`str`.

*	A method :meth:`ll.la.vsql.AST.walknodes` has been added that recursively
	iterates through all children.

*	A method :meth:`ll.la.vsql.AST.check_valid` has been added. It does nothing
	if the AST node is valid, and raises an appropriate exception otherwise.

*	Modernize type hints (This means that Python 3.10 is required now).


0.45.0 (2025-03-24)
-------------------

*	Updated internal LivingAPI version number to 133.


0.44.0 (2025-03-13)
-------------------

*	Added method ``Control.save()`` that saves the user settable attributes to
	the database.

*	Made the ``App`` attributes ``name``, ``description``, ``image``, ``favorite``,
	``gramgen``, ``typename_nom_sin``, ``typename_gen_sin``, ``typename_dat_sin``,
	``typename_acc_sin``, ``typename_nom_plu``, ``typename_gen_plu``,
	``typename_dat_plu`` and ``typename_acc_plu`` settable and add a method
	``App.save()`` that saves those attributes to the database.

*	Added attribute ``Globals.groups``, ``AppGroup.main_app`` and ``App.main``.

*	Added class ``ViewTemplateInfo`` and attribute ``App.viewtemplates``. Renamed
	the old attribute ``viewtemplates`` to ``viewtemplatesconfig``.


0.43.4 (2025-02-03)
-------------------

*	Remove debug logging statement.
*	Reverted dependencies.


0.43.3 (2025-02-03)
-------------------

*	Use fixed version numbers.


0.43.2 (2025-02-03)
-------------------

*	Don't depend on XIST 5.77 since this requires Python 3.10.


0.42.1 (2025-01-30)
-------------------

*	Fixed handling of the "required" info. Before the following could happen:

	There is a first view A that has a field F that is required in view A and a
	second view B that doesn't include field F. The configuration of the
	``Control`` C for this field is the default value of "the first view decides"
	which in this case means ``C.required`` is ``Trrue``. Now if view B is the
	active view calling ``Control.required`` returned ``True``, which is wrong,
	since a field that is not in a view shouldn't be required. The reason for the
	wrong result was, that the return value of ``Control._get_viewcontrol()``
	couldn't distinguish between "there is no active view" (in which case
	"the first view decides" is the correct approach) an "there is an active view,
	but it doesn't contain the control in question" (in which case the control
	should never be required).

	This has been fixed now by using a new method that can distinguish those
	two cases.


0.42.0 (2025-01-29)
-------------------

*	If a ``Record`` hasn't been saved yet calling ``delete`` just
	records the fact that the record has been deleted without calling
	any database procedures. The ``Record``\s ``id`` attribute will
	be set to ``None``.

*	Calling ``save`` after a record has been deleted now doesn nothing.


0.41.0 (2025-01-17)
-------------------

*	Added the class ``AppGroup`` and the ``App`` attribute ``group``.

*	Member templates now work for ``MenuItem`` and ``Panel``.

*	This version requires the API version 132.


0.40.0 (2025-01-13)
-------------------

*	Added ``Control`` attributes ``description``, ``in_mobile_list`` and
	``in_text``.

*	Added ``Control.in_list`` as an alias for ``Control.priority``.

*	``Control.required`` now works independent of an active view. However when
	a view is active it mirrors the view fields "required" status.

*	Added ``Field`` attributes ``description``, ``in_mobile_list``, ``in_text``
	that mirror the ``Control``\s attributes.


0.39.1 (2024-12-16)
-------------------

*	Fixed the value of ``Field.mode`` when accessed via UL4.


0.39.0 (2024-12-11)
-------------------

*	Fixed the implementation of the attribute ``App.templates``
	(and ``Globals.templates``).


0.38.0 (2024-11-26)
-------------------

*	Setting a ``BoolField`` to ``"false"``, ``"no"``, ``"0"`` or ``"off"`` now sets the value
	to ``False``. This is checked in a case insensitive way.

*	Setting a ``BoolField`` to an empty string now sets the value to ``None``.

*	``template_url()`` and related methods now support sets as keyword argument values.
	They will be handled like lists producing multiple parameters.

*	:class:`Control.Mode` gained three new values: ``READONLY``, ``HIDDEN`` and ``ABSENT``.

*	``Field.mode`` inherits ``Control.mode`` but can be overwritten.

*	:class:`App` has gained new attributes:

	- ``gramgen``: The grammatical gender of the label of things in this app.
	- ``typename_nom_sin``: A label for things in this app (nominative singular).
	- ``typename_gen_sin``: A label for things in this app (genitive singular).
	- ``typename_dat_sin``: A label for things in this app (dative singular).
	- ``typename_acc_sin``: A label for things in this app (accusative singular).
	- ``typename_nom_plu``: A label for things in this app (nominative plural).
	- ``typename_gen_plu``: A label for things in this app (genitive plural).
	- ``typename_dat_plu``: A label for things in this app (dative plural).
	- ``typename_acc_plu``: A label for things in this app (accusative plural).

*	Added ``Globals.form``.

*	Detail records for a master record are now stored in a new
	:class:`RecordChildren` object. Creating a new empty :class:`Record`
	automatically attaches the appropriate :class:`RecordChildren` objects to it.

*	Added ``MenuItem.on_view_template``.


0.37.0 (2024-11-07)
-------------------

*	Setting a ``BoolField`` to an empty string now sets the value to ``False``.


0.36.0 (2024-10-08)
-------------------

*	Add new UL4 attribute ``recordedat`` in class ``File`` which holds the point in time when
	the file was recorded.


0.35.0 (2024-09-10)
-------------------

*	Add new UL4 attributes ``search_url``, ``search_param_name`` and ``target_param_name`` in
	``AppLookupChoiceControl`` and ``AppLookupChoiceField``.


0.34.1 (2024-08-06)
-------------------

* Fix version number.


0.34.0 (2024-08-06)
-------------------

*	Fixed type of ``AppParameter.owner``.

*	Bump API version to 131.


0.33.0 (2024-07-16)
-------------------

*	Now each vSQL rule stores the specification it was generated from. A string
	version of that can be retrieved via the method :meth:`str_vsqlsource`.

*	Added the methods :meth:`App.send_mail` and :meth:`Record.send_mail`.


0.32.0 (2024-06-14)
-------------------

*	Add field ``required`` in class ``Field``.

*	Move ``_set_value`` method into ``Field`` subclasses.


0.31.0 (2024-05-22)
-------------------

*	Bump required serverside LivingAPI version to 130.


0.30.0 (2024-05-21)
-------------------

*	Added ``Record`` methods ``display_embedded_url()``,
	``display_standalone_url()`` and ``display_url()``.

*	Renamed database procedure parameter ``p_requestid`` to ``p_reqid``.


0.29.0 (2024-04-17)
-------------------

*	Removed inheritance of internal templates from the base app.


0.28.0 (2024-04-16)
-------------------

*	Added method ``User.change()``.


0.27.0 (2024-04-04)
-------------------

*	Added method ``Globals.qrcode_url()``.

*	Updated documentation theme.

*	``Globals.version`` is now checked against the expected version when loading
	an UL4ON dump.


0.26.0 (2024-02-28)
-------------------

*	``User`` now has an attribute ``globals`` and supports "member templates"
	(i.e. bound templates that can be called and rendered like normal methods).


0.25.0 (2024-02-27)
-------------------

*	All URLs that the LivingAPI now uses are always absolute (i.e. the
	return values of ``Globals.scaled_url()``, ``App.template_url()``,
	``Record.edit_url()``, etc. and the attributes ``File.url`` and
	``File.archive_url``).


0.24.5 (2024-01-15)
-------------------

*	``AppLookupField.lookupdata`` now returns fake data with error hints
	in case of missing target app or target app records.


0.24.4 (2024-01-15)
-------------------

*	Fixed parameter inheritance via the parameter ``la``.


0.24.3 (2024-01-09)
-------------------

*	Fixed template inheritance via the parameter ``la``.


0.24.2 (2023-12-12)
-------------------

*	Fixed saving files via the :class:`HTTPHandler`.


0.24.1 (2023-12-12)
-------------------

*	Fixed invalid uses of ``File.internal_id``.


0.24.0 (2023-12-07)
-------------------

*	Merged attributes ``iconsmall`` and ``iconlarge`` of ``App`` objects
	into ``image``.

*	Merged attributes ``avatarsmall`` and ``avatarlarge`` of ``User``
	objects into ``image``.

*	Merged attributes ``original`` and ``scaled`` of ``ImageLayoutControl``
	objects into ``image``.

*	Added attribute ``z_index`` to ``Control``, ``ViewControl`` and
	``LayoutControl``.

*	Added attribute ``MenuItem.accessible``.

*	Update upload handling to support a world without ``uploadref``.

*	Add methods ``home_url()``, ``datamanagement_url()``, ``import_url()``,
	``tasks_url()``, ``datamanagement_config_url()``, ``permissions_url()`` and
	``datamanageview_url()`` to class :class:`App` which return the relative URLs
	for the respective menus.

*	Add methods ``my_apps_url()``, ``my_tasks_url()``, ``catalog_url()``,
	``chats_url()``, ``profile_url()``, ``account_url()`` and ``logout_url()``
	to class ``Globals`` which return the relative URLs for the respective
	menus.

*	Added attribute ``View.focus_control`` and method
	``View.focus_first_control()``.

*	Added method ``Control.is_focused()``.

*	Add field errors to the record if we have an active view and the field
	is not in the active view. This avoids problems with invisible errors in the
	form.

*	``Control.in_active_view()`` is a method now.

*	Added method ``App.seq()``.

*	Added ``Field`` subclasses (one for each control type).

*	Allow setting the attributes ``Globals.pv_*`` and ``App.pv_*``.


0.23.2 (2023-04-03)
-------------------

*	Removed shortcut attributes from :class:`DataSource`.

*	Added ``APPSTART`` to :class:`MenuItem.Type`.


0.23.1 (2023-03-17)
-------------------

*	Added the new :class:`Panel` attributes to ``Panel.ul4_attrs`` to make them
	accessible for UL4.


0.23 (2023-03-17)
-----------------

*	Added :class:`Panel` attributes :attr:`header_type`,
	:attr:`header_background`, :attr:`text_color`, :attr:`background_color1`
	and :attr:`background_color2`.

*	:class:`Link`\s have been split into :class:`MenuItem` and :class:`Panel`
	objects.


0.22.1 (2023-03-13)
-------------------

*	Fixed version number in ``setup.py``.


0.22 (2023-03-13)
-----------------

*	Added incremental loading of layout controls.

*	Added ``App.child_controls`` (This contains all ``applookup`` and
	``multipleapplookup`` controls in other apps that point to this app).

*	Internal templates are now stored in the Postgres database.

*	Add shortcut attributes ``p_*``, ``pv_*``, ``cl_*`` and ``t_*`` to
	:class:`DataSource`. These atttributes forward to the app.

*	When a record gets saved it's state is now set to ``SAVED``.

*	Added the class :class:`Link` and added the attribute ``App.links``
	containing all currently active links in this app that are accessible to
	the current user.

*	Fixed transaction handling for postgres.

*	Skip transaction handling when no connections are given for :class:`DBHandler`.

*	Implemented deleting of parameters.

*	Fixed parameter save logic to use the WAF procedures.


0.21 (2022-11-29)
-----------------

*	Added :meth:`Field.set_error`.

*	Added ``LayoutControl.visible``.


0.20 (2022-11-15)
-----------------

*	Fixed :meth:`ul4_getattr` implementation to honor UL4 logic in descriptors.

*	The Postgres database connection is now optional.


0.19.1 (2022-11-11)
-------------------

*	Add missing ``ul4onid`` property to :class:`Installation`.


0.19 (2022-11-11)
-----------------

*	:meth:`DBHandler.reset` now calls ``LIVINGAPI_PKG.CLEAR_ALL()`` instead
	of ``LIVINGAPI_PKG.CLEAR_OUTPUTANDBACKREFS()`` to completely reset the
	server side state.


0.18.2 (2022-11-11)
-------------------

*	Fixed optional dependency on :mod:`psycopg`.


0.18.1 (2022-11-11)
-------------------

*	Updated required XIST version.

*	Added optional dependencies to :mod:`cx_Oracle` and :mod:`psycopg` (required
	when :class:`DBHandler` is used).


0.18 (2022-11-04)
-----------------

*	Add support for hierarchical parameters and parameters attached to
	view and email templates.

*	Add the following methods to :class:`App`:

	- :meth:`template_url`,
	- :meth:`new_embedded_url`,
	- :meth:`new_standalone_url`

	and the following methods to :class:`Record`:

	- :meth:`template_url`,
	- :meth:`edit_embedded_url`,
	- :meth:`edit_standalone_url`

*	Add support for automatic resynchronization of the UL4ON codec state between
	the database and the :class:`DBHandler`.


0.17 (2022-08-16)
-----------------

*	Add support for template library parameters.

*	Add support for external data sources.


0.16.1 (2022-07-08)
-------------------

*	Ensure that our internal Postgres queries use ``tuple_row`` as the
	``row_factory``. This makes us independent from the Postgres connection
	we might have been given in the call to the ``DBHandler`` constructor.


0.16 (2022-07-07)
-----------------

*	Add support for template libraries and template library chains.


0.15 (2022-06-15)
-----------------

*	Add support for custom attributes (whose name starts with ``x_``).

*	Added ``File`` attributes: ``duration``, ``geo``, ``storagefilename``,
	``archive`` and ``archive_url``.

*	Added new values for ``Globals.mode``: ``form/new/input``, ``form/new/geo``,
	``form/edit/input`` and ``form/edit/geo``.

*	Added shortcut attributes to ``Globals``: ``p_*`` for app parameters,
	``pv_*`` for app parameter values.

*	Added shortcut attributes to ``App``: ``lc_*`` for layout controls,
	and ``pv_*`` for app parameter values.

*	Added shortcut attributes to ``Veiw``: ``c_*`` for controls and ``lc_*``
	for layout controls.

*	The following attributes are now fetched from the database incrementally,
	if they haven't been part of the UL4ON dump: ``App.params``, ``App.views``
	and ``Record.attachments``.

*	Added attributes to ``NumberControl``: ``precision``, ``minimum`` and
	``maximum``.

*	When setting values of date fields, now the language specific format
	(from ``globals.lang``) will be considered.

*	Added new values to ``ViewTemplateConfig.Type``: ``LISTDATAMANAGEMENT`` and
	``DETAILDATAMANAGEMENT``.

*	Added ``ButtonLayoutControl``.

*	Added ``View`` attributes: ``login_required``, ``result_page`` and
	``use_geo``.

*	Make ``DBHandler`` usable as a context manager (leaving the context manager
	commits or rolls back the connection and reset the UL4ON decoder).

*	Rename classes: ``ViewTemplate`` to ``ViewTemplateConfig``, ``DataSource``
	to ``DataSourceConfig``, ``DataSourceData`` to ``DataSource``.


0.14.3 (2022-01-10)
-------------------

*	Use :meth:`object_named` in :class:`DBHandler._getproc` instead of the
	deprecated (and broken) :meth:`getobject`.


0.14.2 (2021-12-14)
-------------------

*	Make :class:`KeyView` objects persistent.


0.14.1 (2021-12-14)
-------------------

*	Fixed setting a value for ``Fields``\s of ``IntControl`` and
	``NumberControl`` objects.


0.14 (2021-12-08)
-----------------

*	Renamed ``AppLookupControl.lookupapp`` to ``lookup_app`` and
	``AppLookupControl.lookupcontrols`` to ``lookup_controls``.

*	Added the following attributes to ``AppLookupControl``:

	-	``local_master_control``,
	-	``local_detail_controls``,
	-	``remote_master_control``.

*	Added the attribute ``favorite`` to ``App`` and expose it to UL4. Expose
	``superid`` to UL4ON.

*	Renamed ``App.language`` to ``App.lang``.

*	Fixed ``DatetimeSecondControl._asjson()`` to treat ``datetime.datetime``
	values correctly.

*	Updated ``DatetimeControl``, ``DatetimeMinuteControl`` and
	``DatetimeSecondControl`` to support setting values to strings (when they
	have the correct format).

*	Added an UL4 attribute ``format`` to ``DatetimeControl``,
	``DatetimeMinuteControl`` and ``DatetimeSecondControl`` that gives the
	appropriate UL4 format string for formatting a value for this control
	(depending on ``globals.lang``).


*	Added ``Globals.mode`` which is the template mode we're running in. Valid
	values are ``"form/new/init"``, ``"form/new/search"``, ``"form/new/failed"``,
	``"form/new/presave"``, ``"form/new/postsave"``, ``"form/edit/init"``,
	``"form/edit/search"``, ``"form/edit/failed"``, ``"form/edit/presave``,
	``"form/edit/postsave"``, ``"view/list"``, ``"view/detail"``,
	``"view/support"``, ``"email/text`` and ``email/html"``.

*	Most LivingAPI objects are now persistent objects.

*	Implement ``Globals.scaled_url()``.

*	Added the classes ``ViewControl``, ``HTMLLayoutControl`` and
	``ImageLayoutControl`` and attributes ``View.controls`` and ``App.active_view``.

*	Setting ``App.active_view`` to a ``View`` objects makes ``Control``
	attributes honor the additional information defined in the ``View``.

*	Added ``View`` attributes ``lang``, ``controls`` and ``layout_controls``.

*	Added ``App`` attribute ``layout_controls``.

*	Added various ``Control`` attributes that are used in ``View``s: ``top``,
	``left``, ``width``, ``height``, ``default``, ``tabindex``, ``minlength``,
	``maxlength``, ``required``, ``placeholder``, ``mode``, ``labelpos``,
	``autoalign`` and ``labelwidth``.

*	Added attribute ``format`` to ``DateControl``.

*	Added attributes ``none_key`` and ``none_label`` to ``LookupControl``,
	``MultipleLookupControl``, ``AppLookupControl`` and
	``MultipleAppLookupControl``.

*	Implemented field value validation and support for field default values.


0.13 (2020-09-17)
-----------------

*	Add support for "deferred" types in :class:`Attr`. This makes it possible
	to have cyclic references in attribute "declarations".

*	Add the attributes ``app`` and ``record`` to :class:`Globals`.

*	Accessing ``globals.templates`` or ``app.templates`` now fetches the
	templates via the handlers :meth:`fetch_templates` method (which only does
	something in :class:`DBHandler`).

*	:class:`DBHandler` now accepts either the ``account`` or the ``ide_id``
	argument.

*	Added :class:`FileSignatureControl` and :class:`HTMLControl`.


0.12.4 (2021-02-15)
-------------------

*	Fixed order of type checks in :meth:`DatetimeSecondControl._asjson`.


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
