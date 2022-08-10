"""
Tests for LivingAPI.

This tests the Python and Java implementations of the LivingAPI as well as
direct access via the gateway.

To run the tests, :mod:`pytest` is required. For rerunning flaky tests the
package ``pytest-rerunfailures`` is used.
"""

import textwrap, re, json

from conftest import *


def lines(text):
	return [line.strip() for line in text.splitlines(False) if line.strip()]


###
### Tests
###

def test_user(handler):
	"""
	Check attributes of the logged in user (i.e. ``globals.user``).
	"""
	u = user()

	# Check that the logged in user is the user we've used to log in
	vt = handler.make_viewtemplate(
		identifier="livingapi_user_email",
		source="<?print globals.user.email?>",
	)

	assert u == handler.renders(person_app_id(), template=vt.identifier)

	# Check that the account name is part of the user ``repr`` output
	vt = handler.make_viewtemplate(
		identifier="livingapi_user_repr",
		source="<?print repr(globals.user)?>",
	)

	assert f" email='{u}'" in handler.renders(person_app_id(), template=vt.identifier)


def test_global_hostname(handler):
	"""
	Check that ``globals.hostname`` is the host we're talking to.
	"""

	vt = handler.make_viewtemplate(
		identifier="test_livingapi_global_hostname",
		source="""
			<?print repr(globals.hostname)?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = repr(hostname())
	assert lines(output) == lines(expected)


def test_global_mode(handler, config_persons):
	"""
	Check that ``globals.mode`` behaves correctly.
	"""

	source = "<?print globals.mode?>"

	vt_list = handler.make_viewtemplate(
		identifier="test_livingapi_global_mode_list",
		source=source,
		type=la.ViewTemplateConfig.Type.LIST,
	)

	output = handler.renders(person_app_id(), template=vt_list.identifier)
	assert output == "view/list"

	vt_detail = handler.make_viewtemplate(
		identifier="test_livingapi_global_mode_detail",
		source=source,
		type=la.ViewTemplateConfig.Type.DETAIL,
	)

	output = handler.renders(person_app_id(), config_persons.persons.ae.id, template=vt_detail.identifier)
	assert output == "view/detail"

	vt_support = handler.make_viewtemplate(
		identifier="test_livingapi_global_mode_support",
		source=source,
		type=la.ViewTemplateConfig.Type.SUPPORT,
	)

	output = handler.renders(person_app_id(), template=vt_support.identifier)
	assert output == "view/support"


def test_global_datasources(handler, config_apps):
	"""
	Check that ``globals.datasources`` works.
	"""
	c = config_apps

	# Check that the logged in user is the user we've used to log in
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
		),
		la.DataSourceConfig(
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="test_livingapi_global_datasources",
		source="""
			<?print len(globals.datasources)?>
			<?print "persons" in globals.datasources?>
			<?print "fieldsofactivity" in globals.datasources?>
			<?print globals.d_persons.app.id?>
			<?print globals.d_fieldsofactivity.app.id?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = f"""
		2
		True
		True
		{person_app_id()}
		{fields_app_id()}
	"""
	assert lines(output) == lines(expected)


def test_app_attributes(handler):
	"""
	Check that the variable ``app`` points to the correct app.
	"""
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_app_attributes",
		source="""
			<?print app.id?>
			<?print app.name?>
		""",
	)
	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = f"""
		{person_app_id()}
		LA-Demo: Persons (ORI)
	"""
	assert lines(output) == lines(expected)


def test_file_attributes(handler):
	"""
	Check various attributes of ``File`` objects.
	"""

	vt = handler.make_viewtemplate(
		identifier="test_livingapi_file_attributes",
		source="""
			<?code icon = app.iconlarge or app.iconsmall?>
			id=<?print isinstance(icon.id, str)?>
			internalid=<?print isinstance(icon.internalid, str)?>
			url=<?print icon.url.startswith("/gateway/files/")?>
			filename=<?print icon.filename.endswith([".gif", ".png", ".jpg", ".jpeg"])?>
			mimetype=<?print icon.mimetype in {"image/gif", "image/png", "image/jpeg"}?>
			width=<?print icon.width > 0?>
			height=<?print icon.height > 0?>
			duration=<?print icon.duration is None?>
			geo=<?print icon.geo is None?>
			size=<?print icon.size > 0?>
			archive=<?print icon.archive is None?>
			archive_url=<?print icon.url == icon.archive_url?>
			createdat=<?print isinstance(icon.createdat, datetime)?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		id=True
		internalid=True
		url=True
		filename=True
		mimetype=True
		width=True
		height=True
		duration=True
		geo=True
		size=True
		archive=True
		archive_url=True
		createdat=True
	"""

	assert lines(output) == lines(expected)


def test_datasources(handler, config_apps):
	"""
	Check that the datasources have the identifiers we expect.
	"""

	c = config_apps

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
		),
		la.DataSourceConfig(
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="test_livingapi_datasources",
		source="""
			<?for identifier in sorted(datasources)?>
				<?print identifier?>
			<?end for?>
		""",
	)
	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		fieldsofactivity
		persons
	"""
	assert lines(output) == lines(expected)


def test_output_all_records(handler, config_persons):
	"""
	Output all records from all datasources.

	This checks that we don't get any exceptions.
	"""

	c = config_persons

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
		),
		la.DataSourceConfig(
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="test_livingapi_output_all_records",
		source="""
			<?for ds in datasources.values()?>
				Datasource/ID: <?print ds.identifier?>
				<?if ds.app is not None and ds.app.records is not None?>
					Datasource/App: <?print ds.app?>
					<?for r in ds.app.records.values()?>
						Record/ID: <?print r.id?>
						Record/Created at: <?print r.createdat?>
						Record/Created by: <?print r.createdby?>
						Record/Updated at: <?print r.updatedat?>
						Record/Updated by: <?print r.updatedby?>
						Record/Update count: <?print r.updatecount?>
						<?for f in r.fields.values()?>
							Record/<?print f.control.identifier?>: <?print repr(f.value)?>
						<?end for?>
					<?end for?>
				<?end if?>
			<?end for?>
		"""
	)
	handler.renders(person_app_id(), template=vt.identifier)


def test_output_all_controls(handler):
	"""
	Output all controls from all apps.

	This checks that we don't get any exceptions.
	"""

	vt = handler.make_viewtemplate(
		identifier="test_livingapi_output_all_controls",
		source="""
			<?for ds in datasources.values()?>
				<?if ds.app is not None and ds.app.controls is not None?>
					<?for c in ds.app.controls.values()?>
						<?print repr(c)?>
					<?end for?>
				<?end if?>
			<?end for?>
		"""
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_detail(handler, config_persons):
	"""
	Test that detail templates work.
	"""

	vt = handler.make_viewtemplate(
		identifier="test_livingapi_detail",
		source="""
			<?print record.id?>
			<?print record.v_firstname?>
			<?print record.v_lastname?>
		"""
	)

	output = handler.renders(
		person_app_id(),
		config_persons.persons.ae.id,
		template=vt.identifier,
	)
	expected = f"""
		{config_persons.persons.ae.id}
		Albert
		Einstein
	"""
	assert lines(output) == lines(expected)


def test_sort_default_order_is_newest_first(handler, config_persons):
	"""
	Check that the default sort order for records is descending by creation date.
	"""

	c = config_persons

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includecontrols=0,
		),
		identifier="test_livingapi_sort_default_order_is_newest_first",
		source="""
			<?code lastcreatedat = None?>
			<?for p in datasources.persons.app.records.values()?>
				<?if lastcreatedat is not None and lastcreatedat > p.createdat?>
					Bad: <?print lastcreatedat?> > <?print p.createdat?>
				<?end if?>
			<?end for?>
		""",
	)

	assert not lines(handler.renders(person_app_id(), template=vt.identifier))


def test_record_extended_attributes(handler, config_persons):
	"""
	Check that extended attributes (i.e. ``x_foo``) for ``Record`` objects work.
	"""

	c = config_persons

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
		),
		identifier="test_livingapi_record_extended_attributes",
		source="""
			<?code r = first(app.records.values())?>
			<?code r.x_foo = 42?>
			<?print hasattr(r, "x_foo")?>
			<?print r.x_foo?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		True
		42
	"""
	assert lines(output) == lines(expected)


def test_record_shortcuts(handler, config_persons):
	"""
	Check that shortcut attributes for ``Record`` objects work.
	"""

	c = config_persons

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
		),
		identifier="test_livingapi_record_shortcuts",
		source="""
			<?code papp = datasources.persons.app?>
			<?code ae = first(r for r in papp.records.values() if r.v_lastname == "Einstein")?>
			<?print repr(ae.fields.firstname.value)?>
			<?print repr(ae.f_firstname.value)?>
			<?print repr(ae.values.firstname)?>
			<?print repr(ae.v_firstname)?>
		""",
	)
	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		'Albert'
		'Albert'
		'Albert'
		'Albert'
	"""
	assert lines(output) == lines(expected)


def test_app_extended_attributes(handler, config_apps):
	"""
	Check that extended attributes (i.e. ``x_foo``) for ``App`` objects work.
	"""

	c = config_apps

	vt = handler.make_viewtemplate(
		identifier="test_livingapi_app_extended_attributes",
		source="""
			<?code app.x_foo = 42?>
			<?print hasattr(app, "x_foo")?>
			<?print app.x_foo?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		True
		42
	"""
	assert lines(output) == lines(expected)


def test_app_shortcuts(handler, config_persons):
	"""
	Check that shortcut attributes for ``App`` objects work.
	"""

	c = config_persons

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includecontrols=la.DataSourceConfig.IncludeControls.ALL_LAYOUT,
			includeviews=True,
			includeparams=True,
		),
		identifier="test_livingapi_app_shortcuts",
		source="""
			<?print repr(app.controls.firstname.identifier)?>
			<?print repr(app.c_firstname.identifier)?>
			<?print repr(app.params.bool_true.value)?>
			<?print repr(app.p_bool_true.value)?>
			<?print repr(app.pv_bool_true)?>
			<?code app.active_view = first(app.views)?>
			<?print repr(app.layout_controls.save.identifier)?>
			<?print repr(app.lc_save.identifier)?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		'firstname'
		'firstname'
		True
		True
		True
		'save'
		'save'
	"""
	assert lines(output) == lines(expected)


def test_insert_record(handler, config_apps):
	"""
	Insert a record into the person app via the method ``App.insert()``.
	"""

	c = config_apps

	vt = handler.make_viewtemplate(
		identifier="test_livingapi_insert_record",
		source="""
			<?code r = app.insert(firstname="Isaac", lastname="Newton")?>
			<?print repr(r.v_firstname)?>
			<?print repr(r.v_lastname)?>
			<?print r.id?>
		"""
	)
	output1 = handler.renders(person_app_id(), template=vt.identifier)
	expected1 = """
		'Isaac'
		'Newton'
	"""

	output1 = lines(output1)
	id = output1[-1]
	assert output1[:-1] == lines(expected1)

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
		),
		identifier="test_livingapi_insert_record_check_result",
		source=f"""
			<?code r = app.records['{id}']?>
			<?print repr(r.v_firstname)?>
			<?print repr(r.v_lastname)?>
		"""
	)
	output2 = handler.renders(person_app_id(), template=vt.identifier)
	expected2 = """
		'Isaac'
		'Newton'
	"""
	assert lines(output2) == lines(expected2)


def test_attributes_unsaved_record(handler):
	"""
	Check that various ``Record`` attributes will be set when a ``Record`` is saved.
	"""

	# Check that ``id``, ``createdat`` and ``createdby`` will be set when the
	# new record is saved
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_attributes_unsaved_record_create",
		source="""
			<?code r = app(firstname="Isaac", lastname="Newton")?>
			r.id=<?print r.id is not None?>
			r.createdat=<?print r.createdat is not None?>
			r.createdby=<?print r.createdby is not None?>
			r.save()=<?print r.save()?>
			r.id=<?print r.id is not None?>
			r.createdat=<?print r.createdat is not None?>
			r.createdby=<?print r.createdby.email?>
		"""
	)
	output1 = handler.renders(person_app_id(), template=vt.identifier)
	expected1 = f"""
		r.id=False
		r.createdat=False
		r.createdby=False
		r.save()=True
		r.id=True
		r.createdat=True
		r.createdby={user()}
	"""

	assert lines(output1) == lines(expected1)

	# Check that ``updatedat`` and ``updatedby`` will be set when the
	# record is saved (this even happens when the record hasn't been changed
	# however in this case no value fields will be changed)
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_attributes_unsaved_record_update",
		source="""
			<?code r = app(firstname="Isaac", lastname="Newton")?>
			r.id=<?print r.id is not None?>
			r.updatedat=<?print r.updatedat is not None?>
			r.updatedby=<?print r.updatedby is not None?>
			r.save()=<?print r.save()?>
			r.id=<?print r.id is not None?>
			r.updatedat=<?print r.updatedat is not None?>
			r.updatedby=<?print r.updatedby is not None?>
			r.save()=<?print r.save()?>
			r.id=<?print r.id is not None?>
			r.updatedat=<?print r.updatedat is not None?>
			r.updatedby=<?print r.updatedby.email?>
			r.v_date_of_birth=<?code r.v_date_of_birth = @(1642-12-25)?>
			r.save()=<?print r.save()?>
			r.id=<?print r.id is not None?>
			r.updatedat=<?print r.updatedat is not None?>
			r.updatedby=<?print r.updatedby.email?>
		"""
	)

	output2 = handler.renders(person_app_id(), template=vt.identifier)
	expected2 = f"""
		r.id=False
		r.updatedat=False
		r.updatedby=False
		r.save()=True
		r.id=True
		r.updatedat=False
		r.updatedby=False
		r.save()=True
		r.id=True
		r.updatedat=True
		r.updatedby={user()}
		r.v_date_of_birth=
		r.save()=True
		r.id=True
		r.updatedat=True
		r.updatedby={user()}
	"""

	assert lines(output2) == lines(expected2)


def test_app_views_on_demand(handler):
	"""
	Check that ``App.views`` will be loaded incrementally when it isn't activated
	in the ``DataSource``.

	Note that this will not work via ``PythonHTTP``.
	"""

	if not isinstance(handler, PythonHTTP):
		vt = handler.make_viewtemplate(
			identifier="test_livingapi_app_views_on_demand",
			source="""
				<?print isdict(app.views)?>
			""",
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = "True"
		assert lines(output) == lines(expected)


def test_app_parameters_on_demand(handler):
	"""
	Check that ``App.params`` will be loaded incrementally when it isn't activated
	in the ``DataSource``.

	Note that this will not work via ``PythonHTTP``.
	"""

	if not isinstance(handler, PythonHTTP):
		vt = handler.make_viewtemplate(
			identifier="test_livingapi_app_parameters_on_demand",
			source="""
				<?print app.params is not None?>
				<?print app.p_bool_true.value?>
				<?print app.pv_bool_true?>
			""",
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = """
			True
			True
			True
		"""
		assert lines(output) == lines(expected)


def test_appparams(handler, config_apps):
	"""
	Check all app parameter types.

	We don'd load the app parameters on demand (this is done by another test).
	"""

	c = config_apps

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="test_livingapi_appparam_bool",
		source="""
			bool_none.value=<?print repr(app.params.bool_none.value)?>
			bool_none.description=<?print app.params.bool_none.description?>
			bool_false.value=<?print repr(app.params.bool_false.value)?>
			bool_false.description=<?print app.params.bool_false.description?>
			bool_true.value=<?print repr(app.params.bool_true.value)?>
			bool_true.description=<?print app.params.bool_true.description?>

			int_none.value=<?print repr(app.params.int_none.value)?>
			int_none.description=<?print app.params.int_none.description?>
			int_value.value=<?print repr(app.params.int_value.value)?>
			int_value.description=<?print app.params.int_value.description?>

			number_none.value=<?print repr(app.params.number_none.value)?>
			number_none.description=<?print app.params.number_none.description?>
			number_value.value=<?print repr(app.params.number_value.value)?>
			number_value.description=<?print app.params.number_value.description?>

			str_none.value=<?print repr(app.params.str_none.value)?>
			str_none.description=<?print app.params.str_none.description?>
			str_value.value=<?print repr(app.params.str_value.value)?>
			str_value.description=<?print app.params.str_value.description?>

			color_none.value=<?print repr(app.params.color_none.value)?>
			color_none.description=<?print app.params.color_none.description?>
			color_value.value=<?print repr(app.params.color_value.value)?>
			color_value.description=<?print app.params.color_value.description?>

			datedelta_none.value=<?print repr(app.params.datedelta_none.value)?>
			datedelta_none.description=<?print app.params.datedelta_none.description?>
			datedelta_value.value=<?print repr(app.params.datedelta_value.value)?>
			datedelta_value.description=<?print app.params.datedelta_value.description?>

			datetimedelta_none.value=<?print repr(app.params.datetimedelta_none.value)?>
			datetimedelta_none.description=<?print app.params.datetimedelta_none.description?>
			datetimedelta_value.value=<?print repr(app.params.datetimedelta_value.value)?>
			datetimedelta_value.description=<?print app.params.datetimedelta_value.description?>

			monthdelta_none.value=<?print repr(app.params.monthdelta_none.value)?>
			monthdelta_none.description=<?print app.params.monthdelta_none.description?>
			monthdelta_value.value=<?print repr(app.params.monthdelta_value.value)?>
			monthdelta_value.description=<?print app.params.monthdelta_value.description?>

			upload_none.value=<?print repr(app.params.upload_none.value)?>
			upload_none.description=<?print app.params.upload_none.description?>
			upload_value.value=<?print repr(app.params.upload_value.value.mimetype)?>
			upload_value.description=<?print app.params.upload_value.description?>

			app_none.value=<?print repr(app.params.app_none.value)?>
			app_none.description=<?print app.params.app_none.description?>
			app_value.value=<?print repr(app.params.app_value.value.id)?>
			app_value.description=<?print app.params.app_value.description?>

			str_value.identifier=<?print app.p_str_value.identifier?>
			str_value.description=<?print app.p_str_value.description?>
			str_value.createdat=<?print isdatetime(app.p_str_value.createdat)?>
			str_value.createdby=<?print isdefined(app.p_str_value.createdby)?>
			str_value.updatedat=<?print isdefined(app.p_str_value.updatedat)?>
			str_value.updatedby=<?print isdefined(app.p_str_value.updatedby)?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = f"""
		bool_none.value=None
		bool_none.description=desc bool_none
		bool_false.value=False
		bool_false.description=desc bool_false
		bool_true.value=True
		bool_true.description=desc bool_true

		int_none.value=None
		int_none.description=desc int_none
		int_value.value=1777
		int_value.description=desc int_value

		number_none.value=None
		number_none.description=desc number_none
		number_value.value=42.5
		number_value.description=desc number_value

		str_none.value=None
		str_none.description=desc str_none
		str_value.value='gurk'
		str_value.description=desc str_value

		color_none.value=None
		color_none.description=desc color_none
		color_value.value=#369c
		color_value.description=desc color_value

		datedelta_none.value=None
		datedelta_none.description=desc datedelta_none
		datedelta_value.value=timedelta(days=12)
		datedelta_value.description=desc datedelta_value

		datetimedelta_none.value=None
		datetimedelta_none.description=desc datetimedelta_none
		datetimedelta_value.value=timedelta(days=1, seconds=45296)
		datetimedelta_value.description=desc datetimedelta_value

		monthdelta_none.value=None
		monthdelta_none.description=desc monthdelta_none
		monthdelta_value.value=monthdelta(3)
		monthdelta_value.description=desc monthdelta_value

		upload_none.value=None
		upload_none.description=desc upload_none
		upload_value.value='image/jpeg'
		upload_value.description=desc upload_value

		app_none.value=None
		app_none.description=desc app_none
		app_value.value='{person_app_id()}'
		app_value.description=desc app_value

		str_value.identifier=str_value
		str_value.description=desc str_value
		str_value.createdat=True
		str_value.createdby=True
		str_value.updatedat=True
		str_value.updatedby=True
	"""
	assert lines(output) == lines(expected)


def test_view_control_overwrite_string(handler, config_apps):
	c = config_apps

	source_print = """
	lang=<?print repr(app.active_view.lang if app.active_view else None)?>
	label=<?print repr(app.c_firstname.label)?>
	placeholder=<?print repr(app.c_firstname.placeholder)?>
	required=<?print repr(app.c_firstname.required)?>
	minlength=<?print repr(app.c_firstname.minlength)?>
	maxlength=<?print repr(app.c_firstname.maxlength)?>
	labelpos=<?print repr(app.c_firstname.labelpos)?>
	"""

	def source_switch(lang):
		return f"<?code app.active_view = first(v for v in app.views.values() if v.lang == {lang!r})?>"

	vt_no_view = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includerecords=la.DataSourceConfig.IncludeRecords.CONTROLS,
		),
		identifier="test_livingapi_view_control_overwrite_string_noview",
		source=f"""
			{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_no_view.identifier)
	expected = """
		lang=None
		label='Firstname'
		placeholder=None
		required=False
		minlength=None
		maxlength=4000
		labelpos='left'
	"""
	assert lines(output) == lines(expected)

	vt_view_en = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSourceConfig.IncludeControls.ALL,
			includerecords=la.DataSourceConfig.IncludeRecords.CONTROLS,
		),
		identifier="test_livingapi_view_control_overwrite_string_view_en",
		source=f"""
			{source_switch('en')}
			{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_en.identifier)
	expected = """
		lang='en'
		label='Firstname (en)'
		placeholder='Full first name (en)'
		required=True
		minlength=3
		maxlength=30
		labelpos='bottom'
	"""
	assert lines(output) == lines(expected)

	vt_view_de = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSourceConfig.IncludeControls.ALL,
			includerecords=la.DataSourceConfig.IncludeRecords.CONTROLS,
		),
		identifier="test_livingapi_view_control_overwrite_string_view_de",
		source=f"""
			{source_switch('de')}
			{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_de.identifier)
	expected = """
		lang='de'
		label='Vorname (de)'
		placeholder='Vollständiger Vorname (de)'
		required=True
		minlength=3
		maxlength=30
		labelpos='top'
	"""
	assert lines(output) == lines(expected)


def test_view_control_overwrite_lookup_noneoption(handler, config_apps):
	c = config_apps

	source_print = """
	lang=<?print repr(app.active_view.lang if app.active_view else None)?>
	isstr(none_key)=<?print isstr(app.c_country_of_birth.none_key)?>
	none_label=<?print app.c_country_of_birth.none_label?>
	"""

	def source_switch(lang):
		return f"<?code app.active_view = first(v for v in app.views.values() if v.lang == {lang!r})?>"

	vt_no_view = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includerecords=la.DataSourceConfig.IncludeRecords.RECORDS,
		),
		identifier="test_livingapi_view_control_overwrite_lookup_noview",
		source=f"""
			{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_no_view.identifier)
	expected = """
		lang=None
		isstr(none_key)=False
		none_label=
	"""
	assert lines(output) == lines(expected)

	vt_view_en = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSourceConfig.IncludeControls.ALL,
			includerecords=la.DataSourceConfig.IncludeRecords.RECORDS,
		),
		identifier="test_livingapi_view_control_overwrite_lookup_view_en",
		source=f"""
			{source_switch('en')}
			{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_en.identifier)
	expected = """
		lang='en'
		isstr(none_key)=True
		none_label=Nothing found!
	"""
	assert lines(output) == lines(expected)

	vt_view_de = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSourceConfig.IncludeControls.ALL,
			includerecords=la.DataSourceConfig.IncludeRecords.RECORDS,
		),
		identifier="test_livingapi_view_control_overwrite_lookup_view_de",
		source=f"""
			{source_switch('de')}
			{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_de.identifier)
	expected = """
		lang='de'
		isstr(none_key)=True
		none_label=Nichts gefunden!
	"""
	assert lines(output) == lines(expected)


def test_globals_extended_attributes(handler, config_apps):
	c = config_apps

	vt = handler.make_viewtemplate(
		identifier="test_livingapi_globals_extended_attributes",
		source=f"""
			<?code globals.x_foo = 42?>
			<?print hasattr(globals, "x_foo")?>
			<?print globals.x_foo?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		True
		42
	"""
	assert lines(output) == lines(expected)


def test_globals_shortcuts(handler, config_apps):
	c = config_apps

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			includerecords=la.DataSourceConfig.IncludeRecords.RECORDS,
			includeparams=True, # Do this so that ``PythonHTTP`` works too.
		),
		identifier="test_livingapi_globals_shortcuts",
		source="""
			<?print repr(globals.datasources.persons.app.controls.firstname.identifier)?>
			<?print repr(globals.d_persons.app.c_firstname.identifier)?>
			<?print repr(globals.app.params.bool_true.value)?>
			<?print repr(globals.p_bool_true.value)?>
			<?print repr(globals.pv_bool_true)?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		'firstname'
		'firstname'
		True
		True
		True
	"""
	assert lines(output) == lines(expected)


def test_globals_template_shortcuts(handler, config_apps):
	if not isinstance(handler, PythonHTTP):
		handler.make_internaltemplate(identifier="test_livingapi_globals_template_shortcuts_internal", source="")

		vt = handler.make_viewtemplate(
			identifier="test_livingapi_globals_template_shortcuts",
			source="""
				<?print globals.t_test_livingapi_globals_template_shortcuts_internal.name?>
				<?print app.t_test_livingapi_globals_template_shortcuts_internal.name?>
			""",
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = """
			test_livingapi_globals_template_shortcuts_internal
			test_livingapi_globals_template_shortcuts_internal
		"""
		assert lines(output) == lines(expected)


def test_view_defaultedfields_default(handler, config_apps):
	testoptions = dict(
		withview=dict(
			activateview="<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>",
			expected=f"""
				'Walter'
				'Dörwald'
				@({datetime.date.today()})
				germany
				[]
				[]
				[]
				[]
			"""
		),
		withoutview=dict(
			activateview='',
			expected="""
				None
				None
				None
				[]
				[]
				[]
				[]
			""",
		),
	)

	for name, param in testoptions.items():
		vt = handler.make_viewtemplate(
			la.DataSourceConfig(
				identifier="persons",
				app=config_apps.apps.persons,
				includeviews=True
			),
			identifier=f"test_view_defaultedfields_default_{name}",
			source=f"""
				{param['activateview']}
				<?code r = app()?>
				<?print repr(r.v_firstname)?>
				<?print repr(r.v_lastname)?>
				<?print repr(r.v_date_of_birth)?>
				<?print r.v_country_of_birth.key?>
				<?print r.f_firstname.errors?>
				<?print r.f_lastname.errors?>
				<?print r.f_date_of_birth.errors?>
				<?print r.f_country_of_birth.errors?>
			""",
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = param['expected']
		assert lines(output) == lines(expected)


def test_numbercontrol_attributes(handler, config_apps):
	vt = handler.make_viewtemplate(
		identifier=f"test_numbercontrol_attributes",
		source="""
			<?code c = app.c_number?>
			precision1=<?print repr(c.precision)?>
			minimum1=<?print repr(c.minimum)?>
			maximum1=<?print repr(c.maximum)?>
			<?code c.precision = 2?>
			<?code c.minimum = -100?>
			<?code c.maximum = 100?>
			precision2=<?print int(c.precision)?>
			minimum2=<?print int(c.minimum)?>
			maximum2=<?print int(c.maximum)?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		precision1=None
		minimum1=None
		maximum1=None
		precision2=2
		minimum2=-100
		maximum2=100
	"""
	assert lines(output) == lines(expected)


def test_changeapi_dirty(handler, config_persons):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_persons.apps.persons,
			includeviews=True
		),
		identifier=f"test_changeapi_dirty",
		source="""
			<?for r in app.records.values()?>
				<?print r.f_date_of_birth.is_dirty()?>
				<?print r.is_dirty()?>
				<?code r.v_date_of_birth = r.v_date_of_birth?>
				<?print r.f_date_of_birth.is_dirty()?>
				<?print r.is_dirty()?>
				<?code r.v_date_of_birth = (r.v_date_of_birth or today()) + timedelta(1)?>
				<?print r.f_date_of_birth.is_dirty()?>
				<?print r.is_dirty()?>
				<?code r.v_date_of_birth += timedelta(1)?>
				<?print r.f_date_of_birth.is_dirty()?>
				<?print r.is_dirty()?>
				<?break?>
			<?end for?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		False
		False
		False
		False
		True
		True
		True
		True
	"""
	assert lines(output) == lines(expected)


def test_changeapi_has_errors(handler, config_apps):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_changeapi_has_errors",
		source="""
			<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>
			<?code r = app(firstname='01')?>
			<?print r.f_firstname.has_errors()?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "True"
	assert lines(output) == lines(expected)


def check_field(handler, config_apps, identifier, field, value, expected, isre=False):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True,
		),
		la.DataSourceConfig(
			identifier="fields",
			app=config_apps.apps.fields,
			includeviews=True,
		),
		identifier=identifier,
		source=f"""
			<?for lang in ["en", "fr", "it", "de"]?>
				<?code app.active_view = first(v for v in app.views.values() if v.lang == lang)?>
				<?if app.active_view is None?>
					<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>
				<?end if?>
				<?code globals.lang = lang?>
				<?code r = app()?>
				<?code r.v_{field} = {value}?>
				<?print lang?>.value=<?print repr(r.v_{field})?>
				<?for (i, e) in enumerate(r.f_{field}.errors)?>
					<?print lang?>.errors<?print i?>=<?print e?>
				<?end for?>
			<?end for?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	output = lines(output)
	expected = lines(expected)

	if isre:
		assert len(output) == len(expected)
		for (o, e) in zip(output, expected):
			assert re.match(e, o)
	else:
		assert output == expected


def test_changeapi_fieldvalue_bool_string(handler, config_apps):
	type = "<java.lang.String>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "str"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_bool_string",
		"nobel_prize",
		"'Gurk'",
		f"""
			en.value=None
			en.errors0="Nobel prize (en)" doesn't support the type {type}.
			fr.value=None
			fr.errors0=«Nobel prize (en)» ne prend pas en charge le type {type}.
			it.value=None
			it.errors0="Nobel prize (en)" non supporta il tipo {type}.
			de.value=None
			de.errors0="Nobelpreis (de)" unterstützt den Typ {type} nicht.
		""",
	)


def test_changeapi_fieldvalue_bool_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_bool_none",
		"nobel_prize",
		"None",
		"""
			en.value=None
			fr.value=None
			it.value=None
			de.value=None
		""",
	)


def test_changeapi_fieldvalue_bool_true(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_bool_true",
		"nobel_prize",
		"True",
		"""
			en.value=True
			fr.value=True
			it.value=True
			de.value=True
		""",
	)


def test_changeapi_fieldvalue_str_required(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_required",
		"firstname",
		"None",
		"""
			en.value=None
			en.errors0="Firstname (en)" is required.
			fr.value=None
			fr.errors0=«Firstname (en)» est obligatoire.
			it.value=None
			it.errors0=È necessario "Firstname (en)".
			de.value=None
			de.errors0="Vorname (de)" wird benötigt.
		""",
	)


def test_changeapi_fieldvalue_str_limited_tooshort(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_limited_tooshort",
		"firstname",
		"'?'",
		"""
			en.value='?'
			en.errors0="Firstname (en)" is too short. You must use at least 3 characters.
			fr.value='?'
			fr.errors0=«Firstname (en)» est trop court. Vous devez utiliser au moins 3 caractères.
			it.value='?'
			it.errors0="Firstname (en)" è troppo breve. È necessario utilizzare almeno 3 caratteri.
			de.value='?'
			de.errors0="Vorname (de)" ist zu kurz. Sie müssen mindestens 3 Zeichen verwenden.
		""",
	)


def test_changeapi_fieldvalue_str_limited_toolong(handler, config_apps):
	result = "?" * 31
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_limited_toolong",
		"firstname",
		"'?' * 31",
		f"""
			en.value='{result}'
			en.errors0="Firstname (en)" is too long. You may use up to 30 characters.
			fr.value='{result}'
			fr.errors0=«Firstname (en)» est trop long. Vous pouvez utiliser un maximum de 30 caractères.
			it.value='{result}'
			it.errors0="Firstname (en)" è troppo lungo. È possibile utilizzare un massimo di 30 caratteri.
			de.value='{result}'
			de.errors0="Vorname (de)" ist zu lang. Sie dürfen höchstens 30 Zeichen verwenden.
		""",
	)


def test_changeapi_fieldvalue_str_ok(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_ok",
		"firstname",
		"'Gurk'",
		"""
			en.value='Gurk'
			fr.value='Gurk'
			it.value='Gurk'
			de.value='Gurk'
		""",
	)


def test_changeapi_fieldvalue_str_unlimited_toolong(handler, config_apps):
	result = "?"*4001
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_unlimited_toolong",
		"lastname",
		"'?'*4001",
		f"""
			en.value='{result}'
			en.errors0="Lastname (en)" is too long. You may use up to 4000 characters.
			fr.value='{result}'
			fr.errors0=«Lastname (en)» est trop long. Vous pouvez utiliser un maximum de 4000 caractères.
			it.value='{result}'
			it.errors0="Lastname (en)" è troppo lungo. È possibile utilizzare un massimo di 4000 caratteri.
			de.value='{result}'
			de.errors0="Nachname (de)" ist zu lang. Sie dürfen höchstens 4000 Zeichen verwenden.
		""",
	)


def test_changeapi_fieldvalue_geo_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_geo_color",
		"grave",
		"#000",
		f"""
			en.value=None
			en.errors0="Grave (en)" doesn't support the type {type}.
			fr.value=None
			fr.errors0=«Grave (en)» ne prend pas en charge le type {type}.
			it.value=None
			it.errors0="Grave (en)" non supporta il tipo {type}.
			de.value=None
			de.errors0="Grab (de)" unterstützt den Typ {type} nicht.
		""",
	)


def test_changeapi_fieldvalue_geo_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_geo_none",
		"grave",
		"None",
		"""
			en.value=None
			fr.value=None
			it.value=None
			de.value=None
		""",
	)


def test_changeapi_fieldvalue_date_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_color",
		"date_of_birth",
		"#000",
		f"""
			en.value=None
			en.errors0="Date of birth (en)" doesn't support the type {type}.
			fr.value=None
			fr.errors0=«Date of birth (en)» ne prend pas en charge le type {type}.
			it.value=None
			it.errors0="Date of birth (en)" non supporta il tipo {type}.
			de.value=None
			de.errors0="Geburtstag (de)" unterstützt den Typ {type} nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_wrongformat(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_wrongformat",
		"date_of_birth",
		"'Gurk'",
		"""
			en.value='Gurk'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value='Gurk'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='Gurk'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='Gurk'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_ok_datestring(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datestring",
		"date_of_birth",
		"'2000-02-29'",
		"""
			en.value=@(2000-02-29)
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datestring_de(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datestring_de",
		"date_of_birth",
		"'29.02.2000'",
		"""
			en.value='29.02.2000'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datestring_en(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datestring_en",
		"date_of_birth",
		"'02/29/2000'",
		"""
			en.value=@(2000-02-29)
			fr.value='02/29/2000'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='02/29/2000'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='02/29/2000'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes",
		"date_of_birth",
		"'2000-02-29T12:34'",
		"""
			en.value=@(2000-02-29)
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_de(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_de",
		"date_of_birth",
		"'29.02.2000 12:34'",
		"""
			en.value='29.02.2000 12:34'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_en(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_en",
		"date_of_birth",
		"'02/29/2000 12:34'",
		"""
			en.value=@(2000-02-29)
			fr.value='02/29/2000 12:34'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='02/29/2000 12:34'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='02/29/2000 12:34'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds",
		"date_of_birth",
		"'2000-02-29T12:34:56'",
		"""
			en.value=@(2000-02-29)
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_de(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_de",
		"date_of_birth",
		"'29.02.2000 12:34:56'",
		"""
			en.value='29.02.2000 12:34:56'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_en(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_en",
		"date_of_birth",
		"'02/29/2000 12:34:56'",
		"""
			en.value=@(2000-02-29)
			fr.value='02/29/2000 12:34:56'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='02/29/2000 12:34:56'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='02/29/2000 12:34:56'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds",
		"date_of_birth",
		"'2000-02-29T12:34:56.987654'",
		"""
			en.value=@(2000-02-29)
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_de(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_de",
		"date_of_birth",
		"'29.02.2000 12:34:56.987654'",
		"""
			en.value='29.02.2000 12:34:56.987654'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_en(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_en",
		"date_of_birth",
		"'02/29/2000 12:34:56.987654'",
		"""
			en.value=@(2000-02-29)
			fr.value='02/29/2000 12:34:56.987654'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='02/29/2000 12:34:56.987654'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='02/29/2000 12:34:56.987654'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes_with_tz(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes_with_tz",
		"date_of_birth",
		"'2000-02-29T12:34+01:00'",
		"""
			en.value=@(2000-02-29)
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_with_tz_de(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_with_tz_de",
		"date_of_birth",
		"'29.02.2000 12:34+01:00'",
		"""
			en.value='29.02.2000 12:34+01:00'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_with_tz_en(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_minutes_with_tz_en",
		"date_of_birth",
		"'02/29/2000 12:34+01:00'",
		"""
			en.value=@(2000-02-29)
			fr.value='02/29/2000 12:34+01:00'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='02/29/2000 12:34+01:00'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='02/29/2000 12:34+01:00'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds_with_tz(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds_with_tz",
		"date_of_birth",
		"'2000-02-29T12:34:56+01:00'",
		"""
			en.value=@(2000-02-29)
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_with_tz_de(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_with_tz_de",
		"date_of_birth",
		"'29.02.2000 12:34:56+01:00'",
		"""
			en.value='29.02.2000 12:34:56+01:00'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_with_tz_en(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_seconds_with_tz_en",
		"date_of_birth",
		"'02/29/2000 12:34:56+01:00'",
		"""
			en.value=@(2000-02-29)
			fr.value='02/29/2000 12:34:56+01:00'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='02/29/2000 12:34:56+01:00'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='02/29/2000 12:34:56+01:00'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds_with_tz(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds_with_tz",
		"date_of_birth",
		"'2000-02-29T12:34:56.987654+01:00'",
		"""
			en.value=@(2000-02-29)
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_with_tz_de(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_with_tz_de",
		"date_of_birth",
		"'29.02.2000 12:34:56.987654+01:00'",
		"""
			en.value='29.02.2000 12:34:56.987654+01:00'
			en.errors0="Date of birth (en)" doesn't support this date format.
			fr.value=@(2000-02-29)
			it.value=@(2000-02-29)
			de.value=@(2000-02-29)
		""",
	)


def test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_with_tz_en(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_semiok_datetimestring_milliseconds_with_tz_en",
		"date_of_birth",
		"'02/29/2000 12:34:56.987654+01:00'",
		"""
			en.value=@(2000-02-29)
			fr.value='02/29/2000 12:34:56.987654+01:00'
			fr.errors0=«Date of birth (en)» doit comporter une date valide.
			it.value='02/29/2000 12:34:56.987654+01:00'
			it.errors0="Date of birth (en)" deve essere una data.
			de.value='02/29/2000 12:34:56.987654+01:00'
			de.errors0="Geburtstag (de)" unterstützt dieses Datumsformat nicht.
		""",
	)


def test_changeapi_fieldvalue_date_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_none",
		"date_of_birth",
		"None",
		"""
			en.value=None
			en.errors0="Date of birth (en)" is required.
			fr.value=None
			fr.errors0=«Date of birth (en)» est obligatoire.
			it.value=None
			it.errors0=È necessario "Date of birth (en)".
			de.value=None
			de.errors0="Geburtstag (de)" wird benötigt.
		""",
	)


def test_changeapi_fieldvalue_lookup_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_color",
		"sex",
		"#000",
		f"""
			en.value=None
			en.errors0="Sex (en)" doesn't support the type {type}.
			fr.value=None
			fr.errors0=«Sex (en)» ne prend pas en charge le type {type}.
			it.value=None
			it.errors0="Sex (en)" non supporta il tipo {type}.
			de.value=None
			de.errors0="Geschlecht (de)" unterstützt den Typ {type} nicht.
		""",
	)


def test_changeapi_fieldvalue_lookup_unknown(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_unknown",
		"sex",
		"'nix'",
		"""
			en.value=None
			en.errors0=The option 'nix' for "Sex (en)" is unknown.
			fr.value=None
			fr.errors0=L'option 'nix' pour «Sex (en)» est inconnue.
			it.value=None
			it.errors0=L'opzione 'nix' per "Sex (en)" è sconosciuta.
			de.value=None
			de.errors0=Die Option 'nix' für "Geschlecht (de)" ist unbekannt.
		"""
	)


def test_changeapi_fieldvalue_lookup_foreign(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_foreign",
		"sex",
		"app.c_country_of_birth.lookupdata.usa",
		"""
			en.value=None
			en.errors0=The option <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> in "Sex \\(en\\)" doesn't belong to this lookup.
			fr.value=None
			fr.errors0=L'option <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> dans «Sex \\(en\\)» n'appartient pas à cette sélection.
			it.value=None
			it.errors0=L'opzione <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> in "Sex \\(en\\)" non appartiene a questa selezione.
			de.value=None
			de.errors0=Die Option <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> in "Geschlecht \\(de\\)" gehört nicht zu dieser Auswahl.
		""",
		isre=True,
	)


def test_changeapi_fieldvalue_lookup_str(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_str",
		"sex",
		"'male'",
		"""
			en.value=.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>
			fr.value=.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>
			it.value=.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>
			de.value=.*.LookupItem id='.*.male' key='male' label='Männlich \\(de\\)'.*>
		""",
		isre=True,
	)


def test_changeapi_fieldvalue_lookup_lookupitem(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_lookupitem",
		"sex",
		"app.c_sex.lookupdata.male",
		"""
			en.value=<.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>
			fr.value=<.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>
			it.value=<.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>
			de.value=<.*.LookupItem id='.*.male' key='male' label='Männlich \\(de\\)'.*>
		""",
		isre=True,
	)


def test_changeapi_fieldvalue_lookup_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_none",
		"sex",
		"None",
		"""
			en.value=None
			fr.value=None
			it.value=None
			de.value=None
		""",
	)


def test_changeapi_fieldvalue_multipleapplookup_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_multipleapplookup_color",
		"field_of_activity",
		"#000",
		f"""
			en.value=[]
			en.errors0="Field of activity (en)" doesn't support the type {type}.
			fr.value=[]
			fr.errors0=«Field of activity (en)» ne prend pas en charge le type {type}.
			it.value=[]
			it.errors0="Field of activity (en)" non supporta il tipo {type}.
			de.value=[]
			de.errors0="Tätigkeitsfeld (de)" unterstützt den Typ {type} nicht.
		"""
	)


def test_changeapi_fieldvalue_multipleapplookup_type_foreign_ok(handler, config_fields):
	type_color = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	find_physics = "first(r2 for r2 in globals.d_fields.app.records.values() if r2.v_name == 'Physics')";

	record = "<.*.Record id='.*' v_name='Physics' v_parent=<.*.Record id='.*' v_name='Science' state=SAVED.*> state=SAVED.*>"

	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_multipleapplookup_type_foreign_ok",
		"field_of_activity",
		f"[#000, None, '', r.f_field_of_activity.control.none_key, r, {find_physics}]",
		f"""
			en.value=\\[{record}\\]
			en.errors0="Field of activity \\(en\\)" doesn't support the type {type_color}.
			en.errors1=The referenced record in "Field of activity \\(en\\)" is from the wrong app.
			fr.value=\\[{record}\\]
			fr.errors0=«Field of activity \\(en\\)» ne prend pas en charge le type {type_color}.
			fr.errors1=L'enregistrement référencé dans «Field of activity \\(en\\)» appartient à la mauvaise application.
			it.value=\\[{record}\\]
			it.errors0="Field of activity \\(en\\)" non supporta il tipo {type_color}.
			it.errors1=Il record di riferimento in "Field of activity \\(en\\)" appartiene all'app sbagliata.
			de.value=\\[{record}\\]
			de.errors0="Tätigkeitsfeld \\(de\\)" unterstützt den Typ {type_color} nicht.
			de.errors1=Der referenzierte Datensatz in "Tätigkeitsfeld \\(de\\)" gehört zur falscher App.
		""",
		isre=True
	)


def test_changeapi_fieldvalue_multipleapplookup_record_ok(handler, config_fields):
	find_physics = "first(r2 for r2 in globals.d_fields.app.records.values() if r2.v_name == 'Physics')";

	record = "<.*.Record id='.*' v_name='Physics' v_parent=<.*.Record id='.*' v_name='Science' state=SAVED.*> state=SAVED.*>"

	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_multipleapplookup_record_ok",
		"field_of_activity",
		f"[{find_physics}]",
		f"""
			en.value=\\[{record}\\]
			fr.value=\\[{record}\\]
			it.value=\\[{record}\\]
			de.value=\\[{record}\\]
		""",
		isre=True,
	)


def test_changeapi_fieldvalue_multipleapplookup_emptylist_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_multipleapplookup_emptylist_ok",
		"field_of_activity",
		"[None, '', r.f_field_of_activity.control.none_key]",
		"""
			en.value=[]
			fr.value=[]
			it.value=[]
			de.value=[]
		""",
	)


def test_changeapi_fieldvalue_multipleapplookup_none_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_multipleapplookup_none_ok",
		"field_of_activity",
		"None",
		"""
			en.value=[]
			fr.value=[]
			it.value=[]
			de.value=[]
		""",
	)


def test_changeapi_fieldvalue_multipleapplookup_multiple_records(handler, config_fields):
	find_physics = "first(r2 for r2 in globals.d_fields.app.records.values() if r2.v_name == 'Physics')";
	find_mathematics = "first(r2 for r2 in globals.d_fields.app.records.values() if r2.v_name == 'Mathematics')";

	record_physics = "<.*.Record id='.*' v_name='Physics' v_parent=<.*.Record id='.*' v_name='Science' state=SAVED.*> state=SAVED.*>"
	record_mathematics = "<.*.Record id='.*' v_name='Mathematics' v_parent=<.*.Record id='.*' v_name='Science' state=SAVED.*> state=SAVED.*>"

	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_multipleapplookup_multiple_records",
		"field_of_activity",
		f"[{find_physics}, {find_mathematics}]",
		f"""
			en.value=\\[{record_physics}, {record_mathematics}\\]
			fr.value=\\[{record_physics}, {record_mathematics}\\]
			it.value=\\[{record_physics}, {record_mathematics}\\]
			de.value=\\[{record_physics}, {record_mathematics}\\]
		""",
		isre=True,
	)


def test_changeapi_fieldvalue_email_format(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_email_format",
		"email2",
		f"'foo'",
		"""
			en.value='foo'
			en.errors0="Email (en)" must be a valid email address.
			fr.value='foo'
			fr.errors0=«Email (en)» doit comporter une adresse e-mail valide.
			it.value='foo'
			it.errors0="Email (en)" deve essere un indirizzo email valido.
			de.value='foo'
			de.errors0="E-Mail (de)" muss eine gültige E-Mail-Adresse sein.
		""",
	)


def test_changeapi_fieldvalue_email_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_email_ok",
		"email2",
		f"'livingapps@example.org'",
		"""
			en.value='livingapps@example.org'
			fr.value='livingapps@example.org'
			it.value='livingapps@example.org'
			de.value='livingapps@example.org'
		""",
	)


def test_changeapi_fieldvalue_phone_format(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_phone_format",
		"phone",
		f"'foo'",
		"""
			en.value='foo'
			en.errors0="Phone (en)" must be a valid phone number.
			fr.value='foo'
			fr.errors0=«Phone (en)» doit comporter un numéro de téléphone valide.
			it.value='foo'
			it.errors0="Phone (en)" deve essere un numero di telefono valido.
			de.value='foo'
			de.errors0="Telefon (de)" muss eine gültige Telefonnummer sein.
		""",
	)


def test_changeapi_fieldvalue_phone_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_phone_ok",
		"phone",
		f"'+49 (0) 9876/54321'",
		"""
			en.value='+49 (0) 9876/54321'
			fr.value='+49 (0) 9876/54321'
			it.value='+49 (0) 9876/54321'
			de.value='+49 (0) 9876/54321'
		""",
	)


def test_changeapi_fieldvalue_url_format(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_url_format",
		"url",
		f"'foo://bar'",
		"""
			en.value='foo://bar'
			en.errors0="URL (en)" must be a valid URL in the form "http://www.xyz.com".
			fr.value='foo://bar'
			fr.errors0=«URL (en)» doit être au format «http://www.xyz.com».
			it.value='foo://bar'
			it.errors0="URL (en)" deve essere formato "http://www.xyz.com".
			de.value='foo://bar'
			de.errors0="URL (de)" muss eine gültige URL im Format "http://www.xyz.de" sein.
		""",
	)


def test_changeapi_fieldvalue_url_ok(handler, config_fields):
	url = "https://www.example.org:80/foo/bar/baz.html?x=y&z=w#frag"

	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_url_ok",
		"url",
		f"'{url}'",
		f"""
			en.value='{url}'
			fr.value='{url}'
			it.value='{url}'
			de.value='{url}'
		""",
	)


def test_changeapi_fieldvalue_bool_required_none(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_bool_required_none",
		"consent",
		"None",
		"""
			en.value=None
			en.errors0="Consent (en)" is required.
			fr.value=None
			fr.errors0=«Consent (en)» est obligatoire.
			it.value=None
			it.errors0=È necessario "Consent (en)".
			de.value=None
			de.errors0="Zustimmung (de)" wird benötigt.
		""",
	)


def test_changeapi_fieldvalue_bool_required_false(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_bool_required_false",
		"consent",
		"False",
		"""
			en.value=False
			en.errors0="Consent (en)" only accepts "Yes".
			fr.value=False
			fr.errors0=«Consent (en)» n'accepte que «oui».
			it.value=False
			it.errors0="Consent (en)" accetta solo "sì".
			de.value=False
			de.errors0="Zustimmung (de)" akzeptiert nur "Ja".
		""",
	)


def test_changeapi_fieldvalue_bool_required_true(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_bool_required_true",
		"consent",
		"True",
		"""
			en.value=True
			fr.value=True
			it.value=True
			de.value=True
		""",
	)


def test_view_attributes(handler, config_apps):
	"""
	Check the ``View`` attributes ``login_required``, ``result_page`` and ``use_geo``
	(which are new in version 124).
	"""
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_view_attributes",
		source="""
			<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>
			login_required=<?print app.active_view.login_required?>
			result_page=<?print app.active_view.result_page?>
			use_geo=<?print app.active_view.use_geo?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		login_required=False
		result_page=True
		use_geo=no
	"""
	assert lines(output) == lines(expected)


def test_view_specific_lookups(handler, config_apps):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_view_specific_lookups",
		source="""
			<?code m = app.c_sex.lookupdata.male?><?code f = app.c_sex.lookupdata.female?>
			<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>
			lang.en=<?print app.active_view.lang?>
			m.en=<?print m.label?>
			f.en=<?print f.label?>
			<?code app.active_view = first(v for v in app.views.values() if v.lang == 'de')?>
			lang.de=<?print app.active_view.lang?>
			m.de=<?print m.label?>
			f.de=<?print f.label?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		lang.en=en
		m.en=Male (en)
		f.en=Female (en)
		lang.de=de
		m.de=Männlich (de)
		f.de=Weiblich (de)
	"""
	assert lines(output) == lines(expected)


def test_app_with_wrong_fields(handler, config_apps):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_app_with_wrong_fields",
		source="""
			<?code r = app(gurk='hurz')?>
		"""
	)

	# TODO: common exception handling mechanism
	#output = handler.renders(person_app_id(), template=vt.identifier)


def test_record_save_with_sync(handler, config_apps):
	if not isinstance(handler, PythonHTTP):
		vt = handler.make_viewtemplate(
			la.DataSourceConfig(
				identifier="persons",
				app=config_apps.apps.persons,
				includeviews=True
			),
			identifier=f"test_record_save_with_sync",
			source="""
				<?code r = app(notes='notes')?>
				<?code r.save(True, True)?>
				<?print r.id is not None?>
				<?print r.createdat is not None?>
				<?print r.createdby is not None?>
				<?print r.v_notes?>
			"""
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = """
			True
			True
			True
			notes saved!
		"""
		assert lines(output) == lines(expected)


def test_globals_seq(handler, config_apps):
	if not isinstance(handler, PythonHTTP):
		vt = handler.make_viewtemplate(
			identifier="test_livingapi_globals_seq",
			source="""
				<?print globals.seq()?>
			"""
		)

		handler.renders(person_app_id(), template=vt.identifier)
		# no tests here


def test_record_add_error(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_record_add_error",
		source="""
			<?code r = app()?>
			<?print r.has_errors()?>
			<?code r.add_error('my error text')?>
			<?print r.has_errors()?>
			<?print r.errors?>
			<?code r.clear_errors()?>
			<?print r.has_errors()?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		False
		True
		['my error text']
		False
	"""
	assert lines(output) == lines(expected)


def test_field_add_error(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_field_add_error",
		source="""
			<?code r = app()?>
			<?print r.f_firstname.has_errors()?>
			<?code r.f_firstname.add_error('my error text')?>
			<?print r.f_firstname.has_errors()?>
			<?print r.has_errors()?>
			<?print r.f_firstname.errors?>
			<?code r.f_firstname.clear_errors()?>
			<?print r.f_firstname.has_errors()?>
			<?print r.has_errors()?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		False
		True
		True
		['my error text']
		False
		False
	"""
	assert lines(output) == lines(expected)


def test_flash_info(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_flash_info",
		source="""
			<?code globals.flash_info('Title', 'Message')?>
			<?for f in globals.flashes()?>
				<?print f.type?>
				<?print f.title?>
				<?print f.message?>
			<?end for?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		info
		Title
		Message
	"""
	assert lines(output) == lines(expected)


def test_flash_notice(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_flash_notice",
		source="""
			<?code globals.flash_notice('Title', 'Message')?>
			<?for f in globals.flashes()?>
				<?print f.type?>
				<?print f.title?>
				<?print f.message?>
			<?end for?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		notice
		Title
		Message
	"""
	assert lines(output) == lines(expected)


def test_flash_warning(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_flash_warning",
		source="""
			<?code globals.flash_warning('Title', 'Message')?>
			<?for f in globals.flashes()?>
				<?print f.type?>
				<?print f.title?>
				<?print f.message?>
			<?end for?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		warning
		Title
		Message
	"""
	assert lines(output) == lines(expected)


def test_flash_error(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_flash_error",
		source="""
			<?code globals.flash_error('Title', 'Message')?>
			<?for f in globals.flashes()?>
				<?print f.type?>
				<?print f.title?>
				<?print f.message?>
			<?end for?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		error
		Title
		Message
	"""
	assert lines(output) == lines(expected)


def test_log_debug(handler):
	vt = handler.make_viewtemplate(
		identifier="test_log_debug",
		source="""
			<?code globals.log_debug('foo', 'bar', 42)?>
		"""
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_info(handler):
	vt = handler.make_viewtemplate(
		identifier="test_log_info",
		source="""
			<?code globals.log_info('foo', 'bar', 42)?>
		"""
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_notice(handler):
	vt = handler.make_viewtemplate(
		identifier="test_log_notice",
		source="""
			<?code globals.log_notice('foo', 'bar', 42)?>
		"""
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_warning(handler):
	vt = handler.make_viewtemplate(
		identifier="test_log_warning",
		source="""
			<?code globals.log_warning('foo', 'bar', 42)?>
		"""
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_error(handler):
	vt = handler.make_viewtemplate(
		identifier="test_log_error",
		source="""
			<?code globals.log_error('foo', 'bar', 42)?>
		"""
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_assign_to_children_shortcut_attribute(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_assign_to_children_shortcut_attribute",
		source="""
			<?code r = app()?>
			<?code r.c_foo = {'bar': 'baz'}?>
			<?print r.c_foo?>
			<?code r.children = {}?>
			<?print r.children?>
			<?code r.children.foo = {}?>
			<?print r.children.foo?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		{'bar': 'baz'}
		{}
		{}
	"""
	assert lines(output) == lines(expected)


def test_assign_to_children_shortcut_attribute_wrong_type(handler):
	if isinstance(handler, JavaDB):

		vt = handler.make_viewtemplate(
			identifier="test_livingapi_assign_to_children_shortcut_attribute_wrong_type",
			source = """
				<?code r = app()?>
				<?code r.c_foo = 42?>
				<?print r.c_foo?>
			"""
		)

		try:
			handler.renders(person_app_id(), template=vt.identifier)
		except RuntimeError: # which exception is ok?
			pass
		else:
			assert "expected exception not raised" == ''


def test_view_controls(handler, config_apps):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier="test_livingapi_view_controls",
		source=f"""
			<?code papp = globals.d_persons.app?>
			<?code pview = first(app.views.values())?>
			<?code any_controls = False?>
			<?for (c, vc) in zip(app.controls.values(), pview.controls.values())?>
				<?if c is not vc.control?>
					Bad control: <?print repr(c)?><?print repr(vc)?>"
				<?end if?>
				<?if c.identifier != vc.identifier?>
					Bad control identifier: <?print repr(c)?><?print repr(vc)?>
				<?end if?>
				<?if c.type != vc.type?>
					Bad control type: <?print repr(c)?><?print repr(vc)?>
				<?end if?>
				<?if c.subtype != vc.subtype?>
					Bad control subtype: <?print repr(c)?><?print repr(vc)?>
				<?end if?>
				<?code any_controls = True?>
			<?end for?>
			<?print any_controls?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "True"
	assert lines(output) == lines(expected)


def test_view_layout_controls(handler, config_apps):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True,
			includecontrols=la.DataSourceConfig.IncludeControls.ALL_LAYOUT,
		),
		identifier="test_livingapi_view_layout_controls",
		source=f"""
			<?code papp = globals.d_persons.app?>
			<?code pview = first(app.views.values())?>
			<?print "save" in pview.layout_controls?>
			<?print isinstance(first(pview.layout_controls.values()), la.ButtonLayoutControl)?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		True
		True
	"""
	assert lines(output) == lines(expected)


def test_geo_dist(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_geo_dist",
		source="""
			<?code geo1 = globals.geo(49.955267, 11.591212)?>
			<?code geo2 = globals.geo(48.84672, 2.34631)?>
			<?code geo3 = globals.geo("Pantheon, Paris")?>
			<?code dist = globals.dist(geo1, geo2)?>
			<?print 680 < dist and dist < 690?>
			<?code dist = globals.dist(geo1, geo3)?>
			<?print 680 < dist and dist < 690?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		True
		True
	"""
	assert lines(output) == lines(expected)


def test_module_la(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_module_la",
		source="""
			<?print repr(la)?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected1 = """
		<module la>
	"""
	expected2 = """
		<module 'la'>
	"""
	assert lines(output) == lines(expected1) or lines(output) == lines(expected2)


def test_isinstance_la(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_isinstance_la",
		source="""
			<?print isinstance(globals, la.Globals)?>
			<?print isinstance(app, la.App)?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		True
		True
	"""
	assert lines(output) == lines(expected)


def test_file_signature(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_signature",
		source="""
			<?code r = app()?>
			<?code r.v_signature_en2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII"?>
			mimetype=<?print r.v_signature_en2.mimetype?>
			size=<?print r.v_signature_en2.size?>
			width=<?print r.v_signature_en2.width?>
			height=<?print r.v_signature_en2.height?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		mimetype=image/png
		size=68
		width=1
		height=1
	"""
	assert lines(output) == lines(expected)


def test_app_datasource(handler, config_apps):
	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier="test_livingapi_app_datasource",
		source="""
			<?print app.datasource.app is app?>
			<?print app.c_field_of_activity.lookup_app.datasource is None?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		True
		True
	"""
	assert lines(output) == lines(expected)


def test_has_custom_lookupdata(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_has_custom_lookupdata",
		source="""
			<?code r = app()?>
			<?print r.f_field_of_activity.has_custom_lookupdata()?>
			<?code r.f_field_of_activity.lookupdata = r.f_field_of_activity.lookupdata?>
			<?print r.f_field_of_activity.has_custom_lookupdata()?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = """
		False
		True
	"""
	assert lines(output) == lines(expected)


def test_parameter_array(handler):
	vt = handler.make_viewtemplate(
		identifier="test_livingapi_parameter_array",
		source="""
			<?print globals.request.params["gurk"]?>
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier, gurk=["hurz"])
	expected = """
		['hurz']
	"""
	assert lines(output) == lines(expected)


def test_record_attachments_on_demand(handler, config_apps):
	if isinstance(handler, (PythonDB, JavaDB, GatewayHTTP)):
		c = config_apps

		vt = handler.make_viewtemplate(
			la.DataSourceConfig(
				identifier="persons",
				app=c.apps.persons,
				includerecords=la.DataSourceConfig.IncludeRecords.RECORDS,
			),
			identifier="test_livingapi_record_attachments_on_demand",
			source="""
				<?code r1 = app()?>
				<?print repr(r1.attachments)?>
				<?code r2 = first(app.records.values())?>
				<?print repr(r2.attachments)?>
			"""
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = """
			None
			{}
		"""
		assert lines(output) == lines(expected)


def test_app_templates_on_demand(handler, config_persons):
	if not isinstance(handler, PythonHTTP):
		handler.make_internaltemplate(
			identifier="test_livingapi_app_template_on_demand_internal",
			source="<?print app.t_test_livingapi_app_template_on_demand_internal.name?>",
		)

		vt = handler.make_viewtemplate(
			identifier="test_livingapi_app_templates_on_demand",
			source="""
				<?render app.templates.test_livingapi_app_template_on_demand_internal(app=app)?>
				<?render app.t_test_livingapi_app_template_on_demand_internal(app=app)?>
			"""
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = """
			test_livingapi_app_template_on_demand_internal
			test_livingapi_app_template_on_demand_internal
		"""
		assert lines(output) == lines(expected)


def test_template_libraries(handler):
	if not isinstance(handler, PythonHTTP):
		vt = handler.make_viewtemplate(
			identifier="template_libraries",
			source="""
				<?render globals.libs.la_static.templates.la_static_ul4()?>
				<?render globals.libs.la_static.t_la_static_ul4()?>
				<?render globals.l_la_static.templates.la_static_ul4()?>
				<?render globals.l_la_static.t_la_static_ul4()?>
			"""
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = """
			<script src="/static/ul4/1.13.1/dist/umd/ul4.js"></script>
			<script src="/static/ul4/1.13.1/dist/umd/ul4.js"></script>
			<script src="/static/ul4/1.13.1/dist/umd/ul4.js"></script>
			<script src="/static/ul4/1.13.1/dist/umd/ul4.js"></script>
		"""
		assert lines(output) == lines(expected)


def test_chained_template_library(handler):
	if not isinstance(handler, PythonHTTP):
		vt = handler.make_viewtemplate(
			identifier="chained_template_library",
			source="""
				<?render globals.app.cl_la_static.templates.la_static_ul4()?>
				<?render globals.app.cl_la_static.t_la_static_ul4()?>
				<?render globals.cl_la_static.templates.la_static_ul4()?>
				<?render globals.cl_la_static.t_la_static_ul4()?>
				<?print globals.app.cl_foo.identifier?>
				<?print globals.cl_foo.identifier?>
				<?print globals.app.cl_foo.app is globals.app?>
				<?print globals.cl_foo.app is globals.app?>
			"""
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = """
			<script src="nosource"></script>
			<script src="nosource"></script>
			<script src="nosource"></script>
			<script src="nosource"></script>
			foo
			foo
			True
			True
		"""
		assert lines(output) == lines(expected)
