"""
Tests for LivingAPI.

This tests the Python and Java implementations of the LivingAPI as well as
direct access via the gateway.

To run the tests, :mod:`pytest` is required. For rerunning flaky tests the
package ``pytest-rerunfailures`` is used.
"""

import textwrap, re, json

from conftest import *


###
### Tests
###

def test_user(handler):
	"""
	Check the logged in user.
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
	Check that ``globals.hostname`` works.
	"""

	# Check that ``globals.hostname`` is the host we're talking to.
	vt = handler.make_viewtemplate(
		identifier="livingapi_global_hostname",
		source="""
			<?whitespace strip?>
			<?print repr(globals.hostname)?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert repr(hostname()) == output


def test_global_mode(handler, config_persons):
	"""
	Check that ``globals.mode`` behaves correctly.
	"""

	source = "<?print globals.mode?>"

	vt_list = handler.make_viewtemplate(
		identifier="livingapi_global_mode_list",
		source=source,
		type=la.ViewTemplate.Type.LIST,
	)

	output = handler.renders(person_app_id(), template=vt_list.identifier)
	assert output == "view/list"

	vt_detail = handler.make_viewtemplate(
		identifier="livingapi_global_mode_detail",
		source=source,
		type=la.ViewTemplate.Type.DETAIL,
	)

	output = handler.renders(person_app_id(), config_persons.persons.ae.id, template=vt_detail.identifier)
	assert output == "view/detail"

	vt_support = handler.make_viewtemplate(
		identifier="livingapi_global_mode_support",
		source=source,
		type=la.ViewTemplate.Type.SUPPORT,
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
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
		),
		la.DataSource(
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="livingapi_global_datasources",
		source="""
			<?whitespace strip?>
			<?print len(globals.datasources)?>
			;
			<?print "persons" in globals.datasources?>
			;
			<?print "fieldsofactivity" in globals.datasources?>
			;
			<?print globals.d_persons.app.id?>
			;
			<?print globals.d_fieldsofactivity.app.id?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert f"2;True;True;{person_app_id()};{fields_app_id()}" == output


def test_app_attributes(handler):
	"""
	Check that ``app`` is the correct one.
	"""
	vt = handler.make_viewtemplate(
		identifier="livingapi_app_attributes",
		source="<?print app.id?>;<?print app.name?>",
	)
	assert f"{person_app_id()};LA-Demo: Persons (ORI)" == handler.renders(person_app_id(), template=vt.identifier)


def test_datasources(handler, config_apps):
	"""
	Check that the datasources have the identifiers we expect.
	"""

	c = config_apps

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
		),
		la.DataSource(
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="livingapi_datasources",
		source="<?print ';'.join(sorted(datasources))?>",
	)
	assert "fieldsofactivity;persons" == handler.renders(person_app_id(), template=vt.identifier)


def test_output_all_records(handler, config_persons):
	"""
	Simply output all records from all datasources.

	This checks that we don't get any exceptions.
	"""

	c = config_persons

	source = """
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

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
		),
		la.DataSource(
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="livingapi_output_all_records",
		source=source,
	)
	handler.renders(person_app_id(), template=vt.identifier)


def test_output_all_controls(handler):
	"""
	Simply output all controls from all apps.

	This checks that we don't get any exceptions.
	"""

	source = """
		<?for ds in datasources.values()?>
			<?if ds.app is not None and ds.app.controls is not None?>
				<?for c in ds.app.controls.values()?>
					<?print repr(c)?>
				<?end for?>
			<?end if?>
		<?end for?>
	"""

	handler.make_viewtemplate(
		identifier="livingapi_output_all_controls",
		source=source,
	)

	handler.renders(person_app_id(), template="livingapi_output_all_controls")


def test_detail(handler, config_persons):
	"""
	Simply test that detail templates work.
	"""

	source = """
		<?whitespace strip?>
		<?print record.id?> <?print record.v_firstname?> <?print record.v_lastname?>
	"""

	vt = handler.make_viewtemplate(
		identifier="livingapi_detail",
		source=source,
	)

	assert f"{config_persons.persons.ae.id} Albert Einstein" == handler.renders(
		person_app_id(),
		config_persons.persons.ae.id,
		template=vt.identifier,
	)


def test_sort_default_order_is_newest_first(handler, config_persons):
	"""
	Check the the default sort order is descending by creation date.
	"""

	c = config_persons

	source = """
		<?whitespace strip?>
		<?code lastcreatedat = None?>
		<?for p in datasources.persons.app.records.values()?>
			<?if lastcreatedat is not None and lastcreatedat > p.createdat?>
				Bad: <?print lastcreatedat?> > <?print p.createdat?>
			<?end if?>
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includecontrols=0,
		),
		identifier="livingapi_sort_default_order_is_newest_first",
		source=source,
	)

	assert not handler.renders(person_app_id(), template=vt.identifier)


def test_record_shortcutattributes(handler, config_persons):
	"""
	Find. "Albert Einstein" and output one of his fields in multiple ways
	"""
	c = config_persons

	source = """
		<?whitespace strip?>
		<?code papp = datasources.persons.app?>
		<?code ae = first(r for r in papp.records.values() if r.v_lastname == "Einstein")?>
		<?print repr(ae.fields.firstname.value)?>;
		<?print repr(ae.f_firstname.value)?>;
		<?print repr(ae.values.firstname)?>;
		<?print repr(ae.v_firstname)?>
	"""

	handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
		),
		identifier="livingapi_record_shortcutattributes",
		source=source,
	)
	assert "'Albert';'Albert';'Albert';'Albert'" == handler.renders(person_app_id(), template="livingapi_record_shortcutattributes")


def test_app_shortcutattributes(handler):
	"""
	Access a control and output its fields with in two ways.
	"""
	source = """
		<?whitespace strip?>
		<?print repr(app.controls.firstname.identifier)?>;
		<?print repr(app.c_firstname.identifier)?>
	"""

	vt = handler.make_viewtemplate(
		identifier="livingapi_app_shortcutattributes",
		source=source,
	)
	assert "'firstname';'firstname'" == handler.renders(person_app_id(), template=vt.identifier)


def test_insert_record(handler, config_apps):
	"""
	Insert a record into the person app.
	"""
	c = config_apps

	source = """
		<?whitespace strip?>
		<?code r = app.insert(firstname="Isaac", lastname="Newton")?>
		<?print repr(r.v_firstname)?> <?print repr(r.v_lastname)?>;
		<?print r.id?>
	"""

	vt = handler.make_viewtemplate(
		identifier="livingapi_insert_record",
		source=source,
	)
	(output, id) = handler.renders(person_app_id(), template=vt.identifier).split(";")

	assert "'Isaac' 'Newton'" == output

	source = f"""
		<?whitespace strip?>
		<?code r = app.records['{id}']?>
		<?print repr(r.v_firstname)?> <?print repr(r.v_lastname)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
		),
		identifier="livingapi_insert_record_check_result",
		source=source,
	)
	assert "'Isaac' 'Newton'" == handler.renders(person_app_id(), template=vt.identifier)


def test_attributes_unsaved_record(handler):
	# Check that ``id``, ``createdat`` and ``createdby`` will be set when the
	# new record is saved
	source = """
		<?whitespace strip?>
		<?code r = app(firstname="Isaac", lastname="Newton")?>
		<?print r.id is None?> <?print r.createdat is None?> <?print r.createdby is None?>
		<?code r.save()?>;
		<?print r.id is None?> <?print r.createdat is None?> <?print r.createdby.email?>
	"""

	vt = handler.make_viewtemplate(
		identifier="livingapi_attributes_unsaved_record_create",
		source=source,
	)
	assert f"True True True;False False {user()}" == handler.renders(person_app_id(), template=vt.identifier)

	# Check that ``updatedat`` and ``updatedby`` will be set when the
	# record is saved (this even happens when the record hasn't been changed
	# however in this case no value fields will be changed)
	source = """
		<?whitespace strip?>
		<?code r = app(firstname="Isaac", lastname="Newton")?>
		<?print r.updatedat is None?> <?print r.updatedby is None?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby is None?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby.email?>
		<?code r.v_date_of_birth = @(1642-12-25)?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby.email?>
	"""

	vt = handler.make_viewtemplate(
		identifier="livingapi_attributes_unsaved_record_update",
		source=source,
	)

	assert f"True True;True True;False {user()};False {user()}" == handler.renders(person_app_id(), template=vt.identifier)


def test_no_appparams(handler):
	source = "<?print repr(app.params)?>"

	vt = handler.make_viewtemplate(
		identifier="livingapi_no_appparams",
		source=source,
	)

	assert "None" == handler.renders(person_app_id(), template=vt.identifier)


def test_appparam_bool(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.bool_none.value)?>
		;<?print app.params.bool_none.description?>
		;<?print repr(app.params.bool_false.value)?>
		;<?print app.params.bool_false.description?>
		;<?print repr(app.params.bool_true.value)?>
		;<?print app.params.bool_true.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_bool",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert "None;desc bool_none;False;desc bool_false;True;desc bool_true" == output


def test_appparam_int(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.int_none.value)?>
		;<?print app.params.int_none.description?>
		;<?print repr(app.params.int_value.value)?>
		;<?print app.params.int_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_int",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert "None;desc int_none;1777;desc int_value" == output


def tcest_livingapi_appparam_number(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.number_none.value)?>
		;<?print app.params.number_none.description?>
		;<?print repr(app.params.number_value.value)?>
		;<?print app.params.number_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_number",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert "None;desc number_none;42.5;desc number_value" == output


def test_appparam_str(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.str_none.value)?>
		;<?print app.params.str_none.description?>
		;<?print repr(app.params.str_value.value)?>
		;<?print app.params.str_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_str",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "None;desc str_none;'gurk';desc str_value" == output


def test_appparam_color(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.color_none.value)?>
		;<?print app.params.color_none.description?>
		;<?print repr(app.params.color_value.value)?>
		;<?print app.params.color_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_color",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "None;desc color_none;#369c;desc color_value" == output


def test_appparam_datedelta(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.datedelta_none.value)?>
		;<?print app.params.datedelta_none.description?>
		;<?print repr(app.params.datedelta_value.value)?>
		;<?print app.params.datedelta_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_datedelta",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert "None;desc datedelta_none;timedelta(days=12);desc datedelta_value" == output


def test_appparam_datetimedelta(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.datetimedelta_none.value)?>
		;<?print app.params.datetimedelta_none.description?>
		;<?print repr(app.params.datetimedelta_value.value)?>
		;<?print app.params.datetimedelta_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_datetimedelta",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert "None;desc datetimedelta_none;timedelta(days=1, seconds=45296);desc datetimedelta_value" == output


def test_appparam_monthdelta(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.monthdelta_none.value)?>
		;<?print app.params.monthdelta_none.description?>
		;<?print repr(app.params.monthdelta_value.value)?>
		;<?print app.params.monthdelta_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_monthdelta",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert "None;desc monthdelta_none;monthdelta(3);desc monthdelta_value" == output


def test_appparam_upload(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.upload_none.value)?>
		;<?print app.params.upload_none.description?>
		;<?print repr(app.params.upload_value.value.mimetype)?>
		;<?print app.params.upload_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_upload",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "None;desc upload_none;'image/jpeg';desc upload_value" == output


def test_appparam_app(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?print repr(app.params.app_none.value)?>
		;<?print app.params.app_none.description?>
		;<?print repr(app.params.app_value.value.id)?>
		;<?print app.params.app_value.description?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_app",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert f"None;desc app_none;'{person_app_id()}';desc app_value" == output


def test_appparam_otherattributes(handler, config_apps):
	c = config_apps

	source = """
		<?whitespace strip?>
		<?note Use shortcut attribute in all expressions?>
		<?print app.p_str_value.identifier?>
		;<?print app.p_str_value.description?>
		;<?print isdatetime(app.p_str_value.createdat)?>
		;<?print isdefined(app.p_str_value.createdby)?>
		;<?print isdefined(app.p_str_value.updatedat)?>
		;<?print isdefined(app.p_str_value.updatedby)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_otherattributes",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	assert "str_value;desc str_value;True;True;True;True" == output


def test_view_control_overwrite_string(handler, config_apps):
	c = config_apps

	source_print = """
	lang=<?print repr(app.active_view.lang if app.active_view else None)?>
	;label=<?print repr(app.c_firstname.label)?>
	;placeholder=<?print repr(app.c_firstname.placeholder)?>
	;required=<?print repr(app.c_firstname.required)?>
	;minlength=<?print repr(app.c_firstname.minlength)?>
	;maxlength=<?print repr(app.c_firstname.maxlength)?>
	;labelpos=<?print repr(app.c_firstname.labelpos)?>
	"""

	def source_switch(lang):
		return f"<?code app.active_view = first(v for v in app.views.values() if v.lang == {lang!r})?>"

	vt_no_view = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includerecords=la.DataSource.IncludeRecords.RECORDS,
		),
		identifier="test_view_control_overwrite_string_noview",
		source=f"""
		<?whitespace strip?>
		{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_no_view.identifier)
	expected = "lang=None;label='Firstname';placeholder=None;required=False;minlength=None;maxlength=4000;labelpos='left'"
	assert output == expected

	vt_view_en = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSource.IncludeControls.ALL,
			includerecords=la.DataSource.IncludeRecords.RECORDS,
		),
		identifier="test_view_control_overwrite_string_view_en",
		source=f"""
		<?whitespace strip?>
		{source_switch('en')}
		{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_en.identifier)
	expected = "lang='en';label='Firstname (en)';placeholder='Full first name (en)';required=True;minlength=3;maxlength=30;labelpos='bottom'"
	assert output == expected

	vt_view_de = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSource.IncludeControls.ALL,
			includerecords=la.DataSource.IncludeRecords.RECORDS,
		),
		identifier="test_view_control_overwrite_string_view_de",
		source=f"""
		<?whitespace strip?>
		{source_switch('de')}
		{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_de.identifier)
	expected = "lang='de';label='Vorname (de)';placeholder='Vollständiger Vorname (de)';required=True;minlength=3;maxlength=30;labelpos='top'"
	assert output == expected


def test_view_control_overwrite_lookup_noneoption(handler, config_apps):
	c = config_apps

	source_print = """
	lang=<?print repr(app.active_view.lang if app.active_view else None)?>
	;isstr(none_key)=<?print isstr(app.c_country_of_birth.none_key)?>
	;none_label=<?print app.c_country_of_birth.none_label?>
	"""

	source_sep = "<?print '\\n'?>"

	def source_switch(lang):
		return f"<?code app.active_view = first(v for v in app.views.values() if v.lang == {lang!r})?>"

	vt_no_view = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includerecords=la.DataSource.IncludeRecords.RECORDS,
		),
		identifier="test_view_control_overwrite_lookup_noview",
		source=f"""
		<?whitespace strip?>
		{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_no_view.identifier)
	expected = "lang=None;isstr(none_key)=False;none_label="
	assert output == expected

	vt_view_en = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSource.IncludeControls.ALL,
			includerecords=la.DataSource.IncludeRecords.RECORDS,
		),
		identifier="test_view_control_overwrite_lookup_view_en",
		source=f"""
		<?whitespace strip?>
		{source_switch('en')}
		{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_en.identifier)
	expected = "lang='en';isstr(none_key)=True;none_label=Nothing found!"
	assert output == expected

	vt_view_de = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includeviews=True,
			includecontrols=la.DataSource.IncludeControls.ALL,
			includerecords=la.DataSource.IncludeRecords.RECORDS,
		),
		identifier="test_view_control_overwrite_lookup_view_de",
		source=f"""
		<?whitespace strip?>
		{source_switch('de')}
		{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt_view_de.identifier)
	expected = "lang='de';isstr(none_key)=True;none_label=Nichts gefunden!"
	assert output == expected


def test_globals_d_shortcuts(handler, config_apps):
	c = config_apps

	source_print = "<?print globals.d_persons.app.c_firstname.identifier?>"

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
			includerecords=la.DataSource.IncludeRecords.RECORDS,
		),
		identifier="test_globals_d_shortcuts",
		source=f"""
		<?whitespace strip?>
		{source_print}
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "firstname"
	assert output == expected


def test_globals_t_shortcuts(handler, config_apps):
	# TODO: implement App::fetchTemplates in the java living api and remove the second isinstance condition
	if not isinstance(handler, PythonHTTP) and not isinstance(handler, JavaDB):
		source_print = "<?print globals.t_test_globals_t_shortcuts_internal.name?>;<?print app.t_test_globals_t_shortcuts_internal.name?>"

		handler.make_internaltemplate(identifier="test_globals_t_shortcuts_internal", source="")

		vt = handler.make_viewtemplate(
			identifier="test_globals_t_shortcuts",
			source=f"""
			<?whitespace strip?>
			{source_print}
			""",
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = "test_globals_t_shortcuts_internal;test_globals_t_shortcuts_internal"
		assert output == expected


def test_view_defaultedfields_default(handler, config_apps):
	testoptions = {'withview': {
			'activateview': "<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>",
			'expected': f"'Walter'|'Dörwald'|@({datetime.date.today()})|germany||||",
		},
		'withoutview': {
			'activateview': '',
			'expected': f"None|None|None|||||",
		}}
	
	for name, param in testoptions.items():
		source_print = f"""{param['activateview']}
			<?code r = app()?>
			<?print repr(r.v_firstname)?>|
			<?print repr(r.v_lastname)?>|
			<?print repr(r.v_date_of_birth)?>|
			<?print r.v_country_of_birth.key?>|
			<?print ':'.join(r.f_firstname.errors)?>|
			<?print ':'.join(r.f_lastname.errors)?>|
			<?print ':'.join(r.f_date_of_birth.errors)?>|
			<?print ':'.join(r.f_country_of_birth.errors)?>"""

		vt = handler.make_viewtemplate(
			la.DataSource(
				identifier="persons",
				app=config_apps.apps.persons,
				includeviews=True
			),
			identifier=f"test_view_defaultedfields_default_{name}",
			source=f"""
			<?whitespace strip?>
			{source_print}
			""",
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		assert output == param['expected']


def test_changeapi_dirty(handler, config_apps):
	source = """
		<?whitespace strip?>
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

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_changeapi_dirty",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "FalseFalseFalseFalseTrueTrueTrueTrue"
	assert output == expected


def test_changeapi_has_errors(handler, config_apps):
	source = """
		<?whitespace strip?>
		<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>
		<?code r = app(firstname='01')?>
		<?print r.f_firstname.has_errors()?>
		"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_changeapi_has_errors",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "True"
	assert output == expected


def check_field(handler, config_apps, identifier, field, value, isre=False, **expected):
	source = textwrap.dedent(f"""
		<?whitespace strip?>
		{{
		<?for (f, lang) in isfirst(["en", "fr", "it", "de"])?>
			<?if not f?>
				,
			<?end if?>
			<?print asjson(lang)?>:
			<?code app.active_view = first(v for v in app.views.values() if v.lang == lang)?>
			<?if app.active_view is None?>
				<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>
			<?end if?>
			<?code globals.lang = lang?>
			<?code r = app()?>
			<?code r.v_{field} = {value}?>
			[
				<?print asjson(repr(r.v_{field}))?>
				<?for e in r.f_{field}.errors?>
					,<?print asjson(e)?>
				<?end for?>
			]
		<?end for?>
		}}
	""")

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True,
		),
		la.DataSource(
			identifier="fields",
			app=config_apps.apps.fields,
			includeviews=True,
		),
		identifier=identifier,
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	output = json.loads(output)

	if isre:
		assert output.keys() == expected.keys()
		for lang in output:
			output_lang = output[lang]
			expected_lang = expected[lang]
			for (o, e) in zip(output_lang, expected_lang):
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
		en=["None", f'''"Nobel prize (en)" doesn't support the type {type}.'''],
		fr=["None", f'''«Nobel prize (en)» ne prend pas en charge le type {type}.'''],
		it=["None", f'''"Nobel prize (en)" non supporta il tipo {type}.'''],
		de=["None", f'''"Nobelpreis (de)" unterstützt den Typ {type} nicht.'''],
	)


def test_changeapi_fieldvalue_bool_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_bool_none",
		"nobel_prize",
		"None",
		en=["None"],
		fr=["None"],
		it=["None"],
		de=["None"],
	)


def test_changeapi_fieldvalue_bool_true(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_bool_true",
		"nobel_prize",
		"True",
		en=["True"],
		fr=["True"],
		it=["True"],
		de=["True"],
	)


def test_changeapi_fieldvalue_str_required(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_required",
		"firstname",
		"None",
		en=["None", '''"Firstname (en)" is required.'''],
		fr=["None", '''«Firstname (en)» est obligatoire.'''],
		it=["None", '''È necessario "Firstname (en)".'''],
		de=["None", '''"Vorname (de)" wird benötigt.'''],
	)


def test_changeapi_fieldvalue_str_limited_tooshort(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_limited_tooshort",
		"firstname",
		"'?'",
		en=["'?'", '''"Firstname (en)" is too short. You must use at least 3 characters.'''],
		fr=["'?'", '''«Firstname (en)» est trop court. Vous devez utiliser au moins 3 caractères.'''],
		it=["'?'", '''"Firstname (en)" è troppo breve. È necessario utilizzare almeno 3 caratteri.'''],
		de=["'?'", '''"Vorname (de)" ist zu kurz. Sie müssen mindestens 3 Zeichen verwenden.'''],
	)


def test_changeapi_fieldvalue_str_limited_toolong(handler, config_apps):
	result = "?" * 31
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_limited_toolong",
		"firstname",
		"'?' * 31",
		en=[f"'{result}'", '''"Firstname (en)" is too long. You may use up to 30 characters.'''],
		fr=[f"'{result}'", '''«Firstname (en)» est trop long. Vous pouvez utiliser un maximum de 30 caractères.'''],
		it=[f"'{result}'", '''"Firstname (en)" è troppo lungo. È possibile utilizzare un massimo di 30 caratteri.'''],
		de=[f"'{result}'", '''"Vorname (de)" ist zu lang. Sie dürfen höchstens 30 Zeichen verwenden.'''],
	)


def test_changeapi_fieldvalue_str_ok(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_ok",
		"firstname",
		"'Gurk'",
		en=["'Gurk'"],
		fr=["'Gurk'"],
		it=["'Gurk'"],
		de=["'Gurk'"],
	)


def test_changeapi_fieldvalue_str_unlimited_toolong(handler, config_apps):
	result = "?"*4001
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_str_unlimited_toolong",
		"lastname",
		"'?'*4001",
		en=[f"'{result}'", '''"Lastname (en)" is too long. You may use up to 4000 characters.'''],
		fr=[f"'{result}'", '''«Lastname (en)» est trop long. Vous pouvez utiliser un maximum de 4000 caractères.'''],
		it=[f"'{result}'", '''"Lastname (en)" è troppo lungo. È possibile utilizzare un massimo di 4000 caratteri.'''],
		de=[f"'{result}'", '''"Nachname (de)" ist zu lang. Sie dürfen höchstens 4000 Zeichen verwenden.'''],
	)


def test_changeapi_fieldvalue_geo_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_geo_color",
		"grave",
		"#000",
		en=["None", f'''"Grave (en)" doesn't support the type {type}.'''],
		fr=["None", f'''«Grave (en)» ne prend pas en charge le type {type}.'''],
		it=["None", f'''"Grave (en)" non supporta il tipo {type}.'''],
		de=["None", f'''"Grab (de)" unterstützt den Typ {type} nicht.'''],
	)


def test_changeapi_fieldvalue_geo_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_geo_none",
		"grave",
		"None",
		en=["None"],
		fr=["None"],
		it=["None"],
		de=["None"],
	)


def test_changeapi_fieldvalue_date_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_color",
		"date_of_birth",
		"#000",
		en=["None", f'''"Date of birth (en)" doesn't support the type {type}.'''],
		fr=["None", f'''«Date of birth (en)» ne prend pas en charge le type {type}.'''],
		it=["None", f'''"Date of birth (en)" non supporta il tipo {type}.'''],
		de=["None", f'''"Geburtstag (de)" unterstützt den Typ {type} nicht.'''],
	)


def test_changeapi_fieldvalue_date_str_wrongformat(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_wrongformat",
		"date_of_birth",
		"'Gurk'",
		en=["'Gurk'", '''"Date of birth (en)" doesn't support this date format.'''],
		fr=["'Gurk'", '''«Date of birth (en)» doit comporter une date valide.'''],
		it=["'Gurk'", '''"Date of birth (en)" deve essere una data.'''],
		de=["'Gurk'", '''"Geburtstag (de)" unterstützt dieses Datumsformat nicht.'''],
	)


def test_changeapi_fieldvalue_date_str_ok_datestring(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datestring",
		"date_of_birth",
		"'2000-02-29'",
		en=["@(2000-02-29)"],
		fr=["@(2000-02-29)"],
		it=["@(2000-02-29)"],
		de=["@(2000-02-29)"],
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes",
		"date_of_birth",
		"'2000-02-29T12:34'",
		en=["@(2000-02-29)"],
		fr=["@(2000-02-29)"],
		it=["@(2000-02-29)"],
		de=["@(2000-02-29)"],
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds",
		"date_of_birth",
		"'2000-02-29T12:34:56'",
		en=["@(2000-02-29)"],
		fr=["@(2000-02-29)"],
		it=["@(2000-02-29)"],
		de=["@(2000-02-29)"],
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds",
		"date_of_birth",
		"'2000-02-29T12:34:56.987654'",
		en=["@(2000-02-29)"],
		fr=["@(2000-02-29)"],
		it=["@(2000-02-29)"],
		de=["@(2000-02-29)"],
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes_with_tz(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_minutes_with_tz",
		"date_of_birth",
		"'2000-02-29T12:34+01:00'",
		en=["@(2000-02-29)"],
		fr=["@(2000-02-29)"],
		it=["@(2000-02-29)"],
		de=["@(2000-02-29)"],
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds_with_tz(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_seconds_with_tz",
		"date_of_birth",
		"'2000-02-29T12:34:56+01:00'",
		en=["@(2000-02-29)"],
		fr=["@(2000-02-29)"],
		it=["@(2000-02-29)"],
		de=["@(2000-02-29)"],
	)


def test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds_with_tz(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_str_ok_datetimestring_milliseconds_with_tz",
		"date_of_birth",
		"'2000-02-29T12:34:56.987654+01:00'",
		en=["@(2000-02-29)"],
		fr=["@(2000-02-29)"],
		it=["@(2000-02-29)"],
		de=["@(2000-02-29)"],
	)


def test_changeapi_fieldvalue_date_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_date_none",
		"date_of_birth",
		"None",
		en=["None", '''"Date of birth (en)" is required.'''],
		fr=["None", '''«Date of birth (en)» est obligatoire.'''],
		it=["None", '''È necessario "Date of birth (en)".'''],
		de=["None", '''"Geburtstag (de)" wird benötigt.'''],
	)


def test_changeapi_fieldvalue_lookup_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_color",
		"sex",
		"#000",
		en=["None", f'''"Sex (en)" doesn't support the type {type}.'''],
		fr=["None", f'''«Sex (en)» ne prend pas en charge le type {type}.'''],
		it=["None", f'''"Sex (en)" non supporta il tipo {type}.'''],
		de=["None", f'''"Geschlecht (de)" unterstützt den Typ {type} nicht.'''],
	)


def test_changeapi_fieldvalue_lookup_unknown(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_unknown",
		"sex",
		"'nix'",
		en=["None", '''The option 'nix' for "Sex (en)" is unknown.'''],
		fr=["None", '''L'option 'nix' pour «Sex (en)» est inconnue.'''],
		it=["None", '''L'opzione 'nix' per "Sex (en)" è sconosciuta.'''],
		de=["None", '''Die Option 'nix' für "Geschlecht (de)" ist unbekannt.'''],
	)


def test_changeapi_fieldvalue_lookup_foreign(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_foreign",
		"sex",
		"app.c_country_of_birth.lookupdata.usa",
		en=["None", '''The option <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> in "Sex \\(en\\)" doesn't belong to this lookup.'''],
		fr=["None", '''L'option <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> dans «Sex \\(en\\)» n'appartient pas à cette sélection.'''],
		it=["None", '''L'opzione <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> in "Sex \\(en\\)" non appartiene a questa selezione.'''],
		de=["None", '''Die Option <.*.LookupItem id='.*.usa' key='usa' label='USA'.*> in "Geschlecht \\(de\\)" gehört nicht zu dieser Auswahl.'''],
		isre=True,
	)


def test_changeapi_fieldvalue_lookup_str(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_str",
		"sex",
		"'male'",
		en=[".*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>"],
		fr=[".*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>"],
		it=[".*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>"],
		de=[".*.LookupItem id='.*.male' key='male' label='Männlich \\(de\\)'.*>"],
		isre=True,
	)


def test_changeapi_fieldvalue_lookup_lookupitem(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_lookupitem",
		"sex",
		"app.c_sex.lookupdata.male",
		en=["<.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>"],
		fr=["<.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>"],
		it=["<.*.LookupItem id='.*.male' key='male' label='Male \\(en\\)'.*>"],
		de=["<.*.LookupItem id='.*.male' key='male' label='Männlich \\(de\\)'.*>"],
		isre=True,
	)


def test_changeapi_fieldvalue_lookup_none(handler, config_apps):
	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_lookup_none",
		"sex",
		"None",
		en=["None"],
		fr=["None"],
		it=["None"],
		de=["None"],
	)


def test_changeapi_fieldvalue_multipleapplookup_color(handler, config_apps):
	type = "<com.livinglogic.ul4.Color>" if isinstance(handler, (JavaDB, GatewayHTTP)) else "ll.color.Color"

	check_field(
		handler,
		config_apps,
		"test_changeapi_fieldvalue_multipleapplookup_color",
		"field_of_activity",
		"#000",
		en=["[]", f'''"Field of activity (en)" doesn't support the type {type}.'''],
		fr=["[]", f'''«Field of activity (en)» ne prend pas en charge le type {type}.'''],
		it=["[]", f'''"Field of activity (en)" non supporta il tipo {type}.'''],
		de=["[]", f'''"Tätigkeitsfeld (de)" unterstützt den Typ {type} nicht.'''],
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
		en=[
			f"\\[{record}\\]",
			f'''"Field of activity \\(en\\)" doesn't support the type {type_color}.''',
			f'''The referenced record in "Field of activity \\(en\\)" is from the wrong app.''',
		],
		fr=[
			f"\\[{record}\\]",
			f'''«Field of activity \\(en\\)» ne prend pas en charge le type {type_color}.''',
			f'''L'enregistrement référencé dans «Field of activity \\(en\\)» appartient à la mauvaise application.''',
		],
		it=[
			f"\\[{record}\\]",
			f'''"Field of activity \\(en\\)" non supporta il tipo {type_color}.''',
			f'''Il record di riferimento in "Field of activity \\(en\\)" appartiene all'app sbagliata.''',
		],
		de=[
			f"\\[{record}\\]",
			f'''"Tätigkeitsfeld \\(de\\)" unterstützt den Typ {type_color} nicht.''',
			f'''Der referenzierte Datensatz in "Tätigkeitsfeld \\(de\\)" gehört zur falscher App.''',
		],
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
		en=[f"\\[{record}\\]"],
		fr=[f"\\[{record}\\]"],
		it=[f"\\[{record}\\]"],
		de=[f"\\[{record}\\]"],
		isre=True,
	)


def test_changeapi_fieldvalue_multipleapplookup_emptylist_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_multipleapplookup_emptylist_ok",
		"field_of_activity",
		f"[None, '', r.f_field_of_activity.control.none_key]",
		en=["[]"],
		fr=["[]"],
		it=["[]"],
		de=["[]"],
	)


def test_changeapi_fieldvalue_multipleapplookup_none_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_multipleapplookup_none_ok",
		"field_of_activity",
		f"None",
		en=["[]"],
		fr=["[]"],
		it=["[]"],
		de=["[]"],
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
		en=[f"\\[{record_physics}, {record_mathematics}]"],
		fr=[f"\\[{record_physics}, {record_mathematics}]"],
		it=[f"\\[{record_physics}, {record_mathematics}]"],
		de=[f"\\[{record_physics}, {record_mathematics}]"],
		isre=True,
	)


def test_changeapi_fieldvalue_email_format(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_email_format",
		"email2",
		f"'foo'",
		en=["'foo'", '''"Email (en)" must be a valid email address.'''],
		fr=["'foo'", '''«Email (en)» doit comporter une adresse e-mail valide.'''],
		it=["'foo'", '''"Email (en)" deve essere un indirizzo email valido.'''],
		de=["'foo'", '''"E-Mail (de)" muss eine gültige E-Mail-Adresse sein.'''],
	)


def test_changeapi_fieldvalue_email_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_email_ok",
		"email2",
		f"'livingapps@example.org'",
		en=["'livingapps@example.org'"],
		fr=["'livingapps@example.org'"],
		it=["'livingapps@example.org'"],
		de=["'livingapps@example.org'"],
	)


def test_changeapi_fieldvalue_phone_format(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_phone_format",
		"phone",
		f"'foo'",
		en=["'foo'", '''"Phone (en)" must be a valid phone number.'''],
		fr=["'foo'", '''«Phone (en)» doit comporter un numéro de téléphone valide.'''],
		it=["'foo'", '''"Phone (en)" deve essere un numero di telefono valido.'''],
		de=["'foo'", '''"Telefon (de)" muss eine gültige Telefonnummer sein.'''],
	)


def test_changeapi_fieldvalue_phone_ok(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_phone_ok",
		"phone",
		f"'+49 (0) 9876/54321'",
		en=["'+49 (0) 9876/54321'"],
		fr=["'+49 (0) 9876/54321'"],
		it=["'+49 (0) 9876/54321'"],
		de=["'+49 (0) 9876/54321'"],
	)


def test_changeapi_fieldvalue_url_format(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_url_format",
		"url",
		f"'foo://bar'",
		en=["'foo://bar'", '''"URL (en)" must be a valid URL in the form "http://www.xyz.com".'''],
		fr=["'foo://bar'", '''«URL (en)» doit être au format «http://www.xyz.com».'''],
		it=["'foo://bar'", '''"URL (en)" deve essere formato "http://www.xyz.com".'''],
		de=["'foo://bar'", '''"URL (de)" muss eine gültige URL im Format "http://www.xyz.de" sein.'''],
	)


def test_changeapi_fieldvalue_url_ok(handler, config_fields):
	url = "https://www.example.org:80/foo/bar/baz.html?x=y&z=w#frag"

	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_url_ok",
		"url",
		f"'{url}'",
		en=[f"'{url}'"],
		fr=[f"'{url}'"],
		it=[f"'{url}'"],
		de=[f"'{url}'"],
	)


def test_changeapi_fieldvalue_bool_required_none(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_bool_required_none",
		"consent",
		"None",
		en=["None", '''"Consent (en)" is required.'''],
		fr=["None", '''«Consent (en)» est obligatoire.'''],
		it=["None", '''È necessario "Consent (en)".'''],
		de=["None", '''"Zustimmung (de)" wird benötigt.'''],
	)


def test_changeapi_fieldvalue_bool_required_false(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_bool_required_false",
		"consent",
		"False",
		en=["False", '''"Consent (en)" only accepts "Yes".'''],
		fr=["False", '''«Consent (en)» n'accepte que «oui».'''],
		it=["False", '''"Consent (en)" accetta solo "sì".'''],
		de=["False", '''"Zustimmung (de)" akzeptiert nur "Ja".'''],
	)


def test_changeapi_fieldvalue_bool_required_true(handler, config_fields):
	check_field(
		handler,
		config_fields,
		"test_changeapi_fieldvalue_bool_required_true",
		"consent",
		"True",
		en=["True"],
		fr=["True"],
		it=["True"],
		de=["True"],
	)


def test_view_specific_lookups(handler, config_apps):
	source = """
		<?code m = app.c_sex.lookupdata.male?><?code f = app.c_sex.lookupdata.female?>
		<?code app.active_view = first(v for v in app.views.values() if v.lang == 'en')?>
		<?print app.active_view.lang?>,<?print m.label?>,<?print f.label?>|
		<?code app.active_view = first(v for v in app.views.values() if v.lang == 'de')?>
		<?print app.active_view.lang?>,<?print m.label?>,<?print f.label?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_view_specific_lookups",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expexted = "en,Male (en),Female (en)|de,Männlich (de),Weiblich (de)"


def test_app_with_wrong_fields(handler, config_apps):
	source = """
		<?whitespace strip?>
		<?code r = app(gurk='hurz')?>
		"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier=f"test_app_with_wrong_fields",
		source=source
	)

	# TODO: common exception handling mechanism
	#output = handler.renders(person_app_id(), template=vt.identifier)


def test_record_save_with_sync(handler, config_apps):
	if not isinstance(handler, PythonHTTP):
		source = """
			<?whitespace strip?>
			<?code r = app(notes='notes')?>
			<?code r.save(True, True)?>
			<?print r.id is not None?>
			<?print r.createdat is not None?>
			<?print r.createdby is not None?>
			<?print r.v_notes?>
			"""

		vt = handler.make_viewtemplate(
			la.DataSource(
				identifier="persons",
				app=config_apps.apps.persons,
				includeviews=True
			),
			identifier=f"test_record_save_with_sync",
			source=source
		)

		output = handler.renders(person_app_id(), template=vt.identifier)
		expected = "TrueTrueTruenotes saved!"
		assert output == expected


def test_globals_seq(handler, config_apps):
	if not isinstance(handler, PythonHTTP):
		source = """
			<?print globals.seq()?>
			"""

		vt = handler.make_viewtemplate(
			identifier="test_globals_seq",
			source=source
		)

		handler.renders(person_app_id(), template=vt.identifier)
		# no tests here


def test_record_add_error(handler):
	source = """
		<?whitespace strip?>
		<?code r = app()?>
		<?print r.has_errors()?>
		<?code r.add_error('my error text')?>
		<?print r.has_errors()?>
		<?print r.errors?>
		<?code r.clear_errors()?>
		<?print r.has_errors()?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_record_add_error",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "FalseTrue['my error text']False"
	assert output == expected

	
def test_field_add_error(handler):
	source = """
		<?whitespace strip?>
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

	vt = handler.make_viewtemplate(
		identifier="test_field_add_error",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "FalseTrueTrue['my error text']FalseFalse"
	assert output == expected


def test_flash_info(handler):
	source = """
		<?whitespace strip?>
		<?code globals.flash_info('Title', 'Message')?>
		<?for f in globals.flashes()?><?print f.type?>,<?print f.title?>,<?print f.message?><?end for?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_flash_info",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "info,Title,Message"
	assert output == expected


def test_flash_notice(handler):
	source = """
		<?whitespace strip?>
		<?code globals.flash_notice('Title', 'Message')?>
		<?for f in globals.flashes()?><?print f.type?>,<?print f.title?>,<?print f.message?><?end for?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_flash_notice",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "notice,Title,Message"
	assert output == expected


def test_flash_warning(handler):
	source = """
		<?whitespace strip?>
		<?code globals.flash_warning('Title', 'Message')?>
		<?for f in globals.flashes()?><?print f.type?>,<?print f.title?>,<?print f.message?><?end for?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_flash_warning",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "warning,Title,Message"
	assert output == expected


def test_flash_error(handler):
	source = """
		<?whitespace strip?>
		<?code globals.flash_error('Title', 'Message')?>
		<?for f in globals.flashes()?><?print f.type?>,<?print f.title?>,<?print f.message?><?end for?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_flash_error",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "error,Title,Message"
	assert output == expected


def test_log_debug(handler):
	source = """
		<?whitespace strip?>
		<?code globals.log_debug('foo', 'bar', 42)?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_log_debug",
		source=source
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_info(handler):
	source = """
		<?whitespace strip?>
		<?code globals.log_info('foo', 'bar', 42)?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_log_info",
		source=source
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_notice(handler):
	source = """
		<?whitespace strip?>
		<?code globals.log_notice('foo', 'bar', 42)?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_log_notice",
		source=source
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_warning(handler):
	source = """
		<?whitespace strip?>
		<?code globals.log_warning('foo', 'bar', 42)?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_log_warning",
		source=source
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_log_error(handler):
	source = """
		<?whitespace strip?>
		<?code globals.log_error('foo', 'bar', 42)?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_log_error",
		source=source
	)

	handler.renders(person_app_id(), template=vt.identifier)


def test_assign_to_children_shortcut_attribute(handler):
	source = """
		<?whitespace strip?>
		<?code r = app()?>
		<?code r.c_foo = {'bar': 'baz'}?>
		<?print r.c_foo?>
		<?code r.children = {}?>
		<?print r.children?>
		<?code r.children.foo = {}?>
		<?print r.children.foo?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_assign_to_children_shortcut_attribute",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "{'bar': 'baz'}{}{}"
	assert output == expected


def test_assign_to_children_shortcut_attribute_wrong_type(handler):
	if isinstance(handler, JavaDB):
		source = "<?code r = app()?><?code r.c_foo = 42?><?print r.c_foo?>"

		vt = handler.make_viewtemplate(
			identifier="test_assign_to_children_shortcut_attribute_wrong_type",
			source=source
		)

		try:
			handler.renders(person_app_id(), template=vt.identifier)
		except RuntimeError: # which exception is ok?
			pass
		else:
			assert "expected exception not raised" == ''


def test_view_controls(handler, config_apps):
	source_print = """
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

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier="test_view_controls",
		source=f"""
			<?whitespace strip?>
			{source_print}
		"""
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "True"
	assert output == expected


def test_geo_dist(handler):
	source = """
		<?whitespace strip?>
		<?code geo1 = globals.geo(49.955267, 11.591212)?>
		<?code geo2 = globals.geo(48.84672, 2.34631)?>
		<?code geo3 = globals.geo("Pantheon, Paris")?>
		<?code dist = globals.dist(geo1, geo2)?>
		<?print 680 < dist and dist < 690?>
		<?code dist = globals.dist(geo1, geo3)?>
		<?print 680 < dist and dist < 690?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_geo_dist",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "TrueTrue"
	assert output == expected


def test_isinstance_la(handler):
	"""
	TODO: implement me
	"""
	pass


def test_signature(handler):
	source = """
		<?whitespace strip?>
		<?code r = app()?>
		<?code r.v_signature_en2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII"?>
		<?print r.v_signature_en2.mimetype == "image/png"?>
		<?print r.v_signature_en2.size == 68?>
		<?print r.v_signature_en2.width == 1?>
		<?print r.v_signature_en2.height == 1?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_signature",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "TrueTrueTrueTrue"
	assert output == expected


def test_app_datasource(handler, config_apps):
	source = """
		<?whitespace strip?>
		<?print app.datasource.app is app?>
		<?print app.c_field_of_activity.lookup_app.datasource is None?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=config_apps.apps.persons,
			includeviews=True
		),
		identifier="test_app_datasource",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "TrueTrue"
	assert output == expected


def test_has_custom_lookupdata(handler):
	source = """
		<?whitespace strip?>
		<?code r = app()?>
		<?print r.f_field_of_activity.has_custom_lookupdata()?>
		<?code r.f_field_of_activity.lookupdata = r.f_field_of_activity.lookupdata?>
		<?print r.f_field_of_activity.has_custom_lookupdata()?>
	"""

	vt = handler.make_viewtemplate(
		identifier="test_has_custom_lookupdata",
		source=source
	)

	output = handler.renders(person_app_id(), template=vt.identifier)
	expected = "FalseTrue"
	assert output == expected




tests = '''
test_view_control_overwrite_lookup -> test_view_control_overwrite_lookup_noneoption  done
Neue: test_view_control_overwrite_lookup_label ???  view_specific_lookups  done


Test für Shortcut-Attbut globals.d_*    done
Test für Template-Shortcutattribute globals.t_* und app.t_*. done
App.fetchTemplates() implementieren.  spaeter

Feld-Defaultwerte bei aktivem und inaktivem View. done

Field-Methode is_dirty() und has_errors() testen.   done
App-Konstruktur mit falschen Argumenten aufrufen.   Exception  
Record.save()-Argument sync testen. (id, cname und cdate(not None)) done

Globals.seq() testen.  done
Record.add_error() und Field.add_error() testen. done
Globals.flash_info() und Kollegen testen. done
Globals.log_info() und Kollegen testen. done
Record.c_*-Shortcut-Attribute testen. done
Richtige Zuordnung Control <-> ViewControl testen (Java view_controls()) done
Globals.dist() testen (Java geo_dist())  done
Geo-Attribute testen (Java geo_constructor()). not
isinstance()-Tests (Java isinstance_la())
FileSignature-Feldwerte testen (Java signature)
App.datasource
Field.has_custom_lookupdata()
'''