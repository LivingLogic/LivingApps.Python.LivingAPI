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

	assert u == handler.renders(person_app_id, template=vt.identifier)

	# Check that the account name is part of the user ``repr`` output
	vt = handler.make_viewtemplate(
		identifier="livingapi_user_repr",
		source="<?print repr(globals.user)?>",
	)

	assert f" email='{u}'" in handler.renders(person_app_id, template=vt.identifier)


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

	output = handler.renders(person_app_id, template=vt.identifier)
	assert repr(hostname()) == output


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

	output = handler.renders(person_app_id, template=vt.identifier)
	assert f"2;True;True;{person_app_id};{fields_app_id}" == output


def test_app_attributes(handler):
	"""
	Check that ``app`` is the correct one.
	"""
	vt = handler.make_viewtemplate(
		identifier="livingapi_app_attributes",
		source="<?print app.id?>;<?print app.name?>",
	)
	assert f"{person_app_id};LA-Demo: Persons" == handler.renders(person_app_id, template=vt.identifier)


def test_datasources(handler, config_apps):
	"""
	Check that the datasources have the identifiers we expect.
	"""

	c = config_apps

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=c.apps.persons,
		),
		la.DataSource(
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="livingapi_datasources",
		source="<?print ';'.join(sorted(datasources))?>",
	)
	assert "fieldsofactivity;persons" == handler.renders(person_app_id, template=vt.identifier)


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
	handler.renders(person_app_id, template=vt.identifier)


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

	handler.renders(person_app_id, template="livingapi_output_all_controls")


def test_detail(handler, config_persons):
	"""
	Simply test that detail templates work.
	"""

	source = """
		<?whitespace strip?>
		<?print record.v_firstname?> <?print record.v_lastname?>
	"""

	vt = handler.make_viewtemplate(
		identifier="livingapi_detail",
		source=source,
	)

	assert "Albert Einstein" == handler.renders(
		person_app_id,
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

	assert not handler.renders(person_app_id, template=vt.identifier)


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
	assert "'Albert';'Albert';'Albert';'Albert'" == handler.renders(person_app_id, template="livingapi_record_shortcutattributes")


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
	assert "'firstname';'firstname'" == handler.renders(person_app_id, template=vt.identifier)


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
	(output, id) = handler.renders(person_app_id, template=vt.identifier).split(";")

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
	assert "'Isaac' 'Newton'" == handler.renders(person_app_id, template=vt.identifier)


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
	assert f"True True True;False False {user()}" == handler.renders(person_app_id, template=vt.identifier)

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

	assert f"True True;True True;False {user()};False {user()}" == handler.renders(person_app_id, template=vt.identifier)


def test_no_appparams(handler):
	source = "<?print repr(app.params)?>"

	vt = handler.make_viewtemplate(
		identifier="livingapi_no_appparams",
		source=source,
	)

	assert "None" == handler.renders(person_app_id, template=vt.identifier)


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

	output = handler.renders(person_app_id, template=vt.identifier)
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

	output = handler.renders(person_app_id, template=vt.identifier)
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

	output = handler.renders(person_app_id, template=vt.identifier)
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

	output = handler.renders(person_app_id, template=vt.identifier)

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

	output = handler.renders(person_app_id, template=vt.identifier)

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

	output = handler.renders(person_app_id, template=vt.identifier)
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

	output = handler.renders(person_app_id, template=vt.identifier)
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

	output = handler.renders(person_app_id, template=vt.identifier)
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

	output = handler.renders(person_app_id, template=vt.identifier)

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

	output = handler.renders(person_app_id, template=vt.identifier)

	assert f"None;desc app_none;'{person_app_id}';desc app_value" == output


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

	output = handler.renders(person_app_id, template=vt.identifier)
	assert "str_value;desc str_value;True;True;True;True" == output
