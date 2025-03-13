"""
Tests for vSQL.

The test are done via the Python DB interface.

To run the tests, :mod:`pytest` is required.
"""

import operator

from conftest import *


def lines(text):
	return [line.strip() for line in text.splitlines(False) if line.strip()]


template_unsorted_persons = """
	<?whitespace strip?>
	<?for (f, r) in isfirst(datasources.persons.app.records.values())?>
		<?if not f?>;<?end if?>
		<?print r.v_firstname?> <?print r.v_lastname?>
	<?end for?>
"""

template_sorted_persons = """
	<?whitespace strip?>
	<?def key(r)?>
		<?return r.v_lastname?>
	<?end def?>
	<?for (f, r) in isfirst(sorted(datasources.persons.app.records.values(), key))?>
		<?if not f?>;<?end if?>
		<?print r.v_firstname?> <?print r.v_lastname?>
	<?end for?>
"""

template_unsorted_children = """
	<?whitespace strip?>
	<?for (f, r) in isfirst(datasources.fieldsofactivity.app.records[id].c_children.values())?>
		<?if not f?>;<?end if?>
		<?print r.v_name?>
	<?end for?>
"""

template_sorted_children = """
	<?whitespace strip?>
	<?def key(r)?>
		<?return r.v_name?>
	<?end def?>
	<?for (f, r) in isfirst(sorted(datasources.fieldsofactivity.app.records[id].c_children.values(), key))?>
		<?if not f?>;<?end if?>
		<?print r.v_name?>
	<?end for?>
"""


###
### Tests
###

def test_global_variables(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?for r in datasources.fieldsofactivity.app.records.values()?>
			<?print r.v_name?>
			<?for r2 in r.c_children.values()?>
				<?print r2.v_name?>
			<?end for?>
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_name"),
			la.DataOrder(expression="app.p_str_value.value"),
			la.DataOrder(expression="user.email"),
			la.DataOrder(expression="record.id"),
			la.DataOrder(expression="params.str.nix"),
			la.DataOrder(expression="len(params.strlist.nix)"),
			la.DataSourceChildrenConfig(
				la.DataOrder(expression="r.v_name"),
				la.DataOrder(expression="app.p_str_value.value"),
				la.DataOrder(expression="user.email"),
				la.DataOrder(expression="record.id"),
				la.DataOrder(expression="params.str.nix"),
				la.DataOrder(expression="len(params.strlist.nix)"),
				identifier="children",
				control=c.apps.fields.c_parent,
				filter="r.app.id != app.p_app_value.id and user.email is not None and record.id is None and params.str.nix is None and len(params.strlist.nix) == 0",
			),
			identifier="fieldsofactivity",
			app=c.apps.fields,
			recordfilter="r.app.id != app.p_app_value.id and user.email is not None and record.id is None and params.str.nix is None and len(params.strlist.nix) == 0",
			includeparams=True,
		),
		identifier="vsql_global_variables",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	expected = []
	key = operator.attrgetter("v_name")
	for a in sorted(c.areas.values(), key=key):
		expected.append(a.v_name)
		for a2 in sorted((a2 for a2 in c.areas.values() if a2.v_parent is a), key=key):
			expected.append(a2.v_name)

	assert expected == lines(output)


def test_datasource_appfilter(config_data):
	handler = PythonDB()

	source = """
		<?whitespace strip?>
		<?print repr(datasources.all.app)?>
		;
		<?for a in datasources.all.apps.values()?>
			<?print a.id?>
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="all",
			appfilter=f"a.uuid == '{person_app_id()}'"
		),
		identifier="vsql_datasource_appfilter",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert f"None;{person_app_id()}" == output


def test_datasource_recordfilter(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_lastname == 'Einstein'",
		),
		identifier="vsql_datasource_recordfilter",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "Albert Einstein" == output


def test_datasource_recordfilter_param_str(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_lastname == params.str.lastname",
		),
		identifier="vsql_datasource_recordfilter_param_str",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, lastname="Curie")

	assert "Marie Curie" == output


def test_datasource_recordfilter_param_int(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_date_of_birth.year == params.int.year",
		),
		identifier="vsql_datasource_recordfilter_param_int",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, year="1935")

	assert "Elvis Presley" == output


def test_datasource_recordfilter_param_date(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_date_of_birth == params.date.date_of_birth",
		),
		identifier="vsql_datasource_recordfilter_param_date",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, date_of_birth="1926-06-01")

	assert "Marilyn Monroe" == output


def test_datasource_recordfilter_param_datetime(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="datetime(r.v_date_of_birth) + hours(12) + minutes(34) + seconds(56) == params.datetime.date_of_birth",
		),
		identifier="vsql_datasource_recordfilter_param_datetime",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, date_of_birth="1926-06-01T12:34:56")

	assert "Marilyn Monroe" == output


def test_datasource_recordfilter_param_strlist(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_lastname in params.strlist.lastname",
		),
		identifier="vsql_datasource_recordfilter_param_strlist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, lastname=["Gauß", "Riemann"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_datasource_recordfilter_param_intlist(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_date_of_birth.year in params.intlist.year",
		),
		identifier="vsql_datasource_recordfilter_param_intlist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, year=["1826", "1777"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_datasource_recordfilter_param_datelist(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_date_of_birth in params.datelist.date_of_birth",
		),
		identifier="vsql_datasource_recordfilter_param_datelist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, date_of_birth=["1826-06-17", "1777-04-30"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_datasource_recordfilter_param_datetimelist(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="datetime(r.v_date_of_birth) + hours(12) + minutes(34) + seconds(56) == params.datetimelist.date_of_birth[0]",
		),
		identifier="vsql_datasource_recordfilter_param_datelist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier, date_of_birth=["1777-04-30T12:34:56"])

	assert "Carl Friedrich Gauß" == output


def test_datasource_recordfilter_appparam_int(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_date_of_birth.year == app.p_int_value.value",
		),
		identifier="vsql_datasource_recordfilter_appparam_int",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "Carl Friedrich Gauß" == output


def test_datasource_recordfilter_geo(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_grave is not None", direction="desc", nulls="first"),
			la.DataOrder(expression="dist(r.v_grave, geo(49.955267, 11.591212, 'LivingLogic AG'))", direction="asc", nulls="first"),
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_grave is not None and dist(r.v_grave, geo(49.955267, 11.591212, 'LivingLogic AG')) < params.int.maxdist",
		),
		identifier="vsql_datasource_recordfilter_geo",
		source=template_unsorted_persons,
	)

	output = handler.renders(person_app_id(), template=vt.identifier, maxdist="50")
	assert "" == output

	output = handler.renders(person_app_id(), template=vt.identifier, maxdist="500")
	assert "Carl Friedrich Gauß;Bernhard Riemann" == output

	output = handler.renders(person_app_id(), template=vt.identifier, maxdist="5000")
	assert "Carl Friedrich Gauß;Bernhard Riemann;Marie Curie" == output


def test_datasource_sort_asc_nullsfirst(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_date_of_death", direction="asc", nulls="first"),
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_asc_nullsfirst",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "Donald Knuth;Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein" == output


def test_datasource_sort_asc_nullslast(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_date_of_death", direction="asc", nulls="last"),
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_asc_nullslast",
		source=template_unsorted_persons,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein;Donald Knuth" == output


def test_datasource_sort_desc_nullsfirst(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_date_of_death", direction="desc", nulls="first"),
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_desc_nullsfirst",
		source=template_unsorted_persons,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "Donald Knuth;Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß" == output


def test_datasource_sort_desc_nullslast(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_date_of_death", direction="desc", nulls="last"),
			identifier="persons",
			app=c.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_desc_nullslast",
		source=template_unsorted_persons,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß;Donald Knuth" == output


def test_datasource_masterdetail_recordfilter(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{c.areas.science.id}', '{c.areas.art.id}']?>
			;{template_sorted_children}
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataSourceChildrenConfig(
				identifier="children",
				control=c.apps.fields.c_parent,
				filter="len(r.v_name) >= 6",
			),
			identifier="fieldsofactivity",
			app=c.apps.fields,
			recordfilter="r.v_parent.id is None",
		),
		identifier="vsql_datasource_masterdetail_recordfilter",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "True;Computer science;Mathematics;Physics;Literature" == output


def test_datasource_masterdetail_sort_asc(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{c.areas.science.id}', '{c.areas.art.id}']?>
			;{template_unsorted_children}
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataSourceChildrenConfig(
				la.DataOrder(expression="r.v_name", direction="asc", nulls="first"),
				identifier="children",
				control=c.apps.fields.c_parent,
			),
			identifier="fieldsofactivity",
			app=c.apps.fields,
			recordfilter="r.v_parent.id is None",
		),
		identifier="vsql_datasource_masterdetail_sort_asc",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "True;Computer science;Mathematics;Physics;Film;Literature;Music" == output


def test_datasource_masterdetail_sort_desc(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{c.areas.science.id}', '{c.areas.art.id}']?>
			;{template_unsorted_children}
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataSourceChildrenConfig(
				la.DataOrder(expression="r.v_name", direction="desc", nulls="first"),
				identifier="children",
				control=c.apps.fields.c_parent,
			),
			identifier="fieldsofactivity",
			app=c.apps.fields,
			recordfilter="r.v_parent.id is None",
		),
		identifier="vsql_datasource_masterdetail_sort_desc",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "True;Physics;Mathematics;Computer science;Music;Literature;Film" == output


def test_color_attributes(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="app.p_color_value.value.r == 0x33 and app.p_color_value.value.g == 0x66 and app.p_color_value.value.b == 0x99 and app.p_color_value.value.a == 0xcc",
		),
		identifier="vsql_color_attributes",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "0" != output


def test_color_methods(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="app.p_color_value.value.lum() == 0.4",
		),
		identifier="vsql_color_methods",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "0" != output


def test_repr_color(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter='repr(#369) == "#369" and repr(#369c) == "#369c" and repr(#123456) == "#123456" and repr(#12345678) == "#12345678"',
		),
		identifier="vsql_repr_color",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "0" != output


def test_geo_attributes(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			identifier="persons",
			app=c.apps.persons,
			recordfilter="int(geo(49.955267, 11.591212, 'LivingLogic AG').lat) == 49 and int(geo(49.955267, 11.591212, 'LivingLogic AG').long) == 11 and geo(49.955267, 11.591212, 'LivingLogic AG').info == 'LivingLogic AG'",
		),
		identifier="vsql_geo_attributes",
		source=source,
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	assert "0" != output


def test_datasource_paging(config_data):
	c = config_data

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_lastname"),
			la.DataOrder(expression="r.v_firstname"),
			identifier="persons",
			app=c.apps.persons,
		),
		identifier="vsql_datasource_paging",
		source=template_unsorted_persons,
	)

	output = handler.renders(
		person_app_id(),
		template=vt.identifier,
		**{"la-ds-persons-paging": "0_2"},
	)

	assert "Muhammad Ali;Marie Curie" == output


def test_datasourcechildren_paging(config_data):
	c = config_data

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?for (f, r) in isfirst(datasources.fieldsofactivity.app.records['{c.areas.film.id}'].c_persons.values())?>
			<?if not f?>;<?end if?><?print r.v_firstname?> <?print r.v_lastname?>
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			la.DataOrder(expression="r.v_name"),
			la.DataSourceChildrenConfig(
				la.DataOrder(expression="r.v_lastname"),
				la.DataOrder(expression="r.v_firstname"),
				identifier="persons",
				control=c.apps.persons.c_field_of_activity,
			),
			identifier="fieldsofactivity",
			app=c.apps.fields,
		),
		identifier="vsql_datasourcechildren_paging",
		source=source,
	)

	output = handler.renders(
		person_app_id(),
		template=vt.identifier,
		**{f"la-dsc-fieldsofactivity-{c.areas.film.id}-persons-paging": "1_1"},
	)

	assert "Ronald Reagan" == output
