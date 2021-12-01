"""
Tests for LivingAPI.

This tests the Python and Java implementations of the LivingAPI as well as
direct access via the gateway.

To run the tests, :mod:`pytest` is required. For rerunning flaky tests the
package ``pytest-rerunfailures`` is used.
"""

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
	expected = "lang=None;label='Firstname';placeholder=None;required=False;minlength=0;maxlength=4000;labelpos='left'"
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
Richtige Zuordnung Control <-> ViewControl testen (Java view_controls())
Globals.dist() testen (Java geo_dist())
Geo-Attribute testen (Java geo_constructor()).
isinstance()-Tests (Java isinstance_la())
FileSignature-Feldwerte testen (Java signature)
'''