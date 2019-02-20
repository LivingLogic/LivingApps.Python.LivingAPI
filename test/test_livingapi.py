import sys, os, datetime, subprocess, operator

import pytest

from ll import ul4c, url as url_, ul4on

from ll import la


###
### Data and helper functions
###

testappid = "5bffc841c26a4b5902b2278c"


def connect():
	return os.environ["LA_LIVINGAPI_TEST_CONNECT"]


def uploaddir():
	return os.environ["LA_LIVINGAPI_TEST_UPLOADDIR"]


def url():
	return os.environ["LA_LIVINGAPI_TEST_URL"]


def user():
	"""
	Return the account name of the user that should be used for connecting to LivingApps.
	"""
	return os.environ["LA_LIVINGAPI_TEST_USER"]


def passwd():
	return os.environ["LA_LIVINGAPI_TEST_PASSWD"]


###
### Testing handlers
###

def python_db(source, *path, **params):
	template = ul4c.Template(source)

	handler = la.DBHandler(connect(), uploaddir(), user())

	vars = handler.viewtemplate_data(*path, **params)
	result = template.renders(**vars)
	handler.commit()
	return result


def python_http(source, *path, **params):
	template = ul4c.Template(source)

	handler = la.HTTPHandler(url(), user(), passwd())

	vars = handler.viewtemplate_data(*path, **params)
	result = template.renders(**vars)
	return result


def java_find_exception(output):
	lines = output.splitlines()
	msg = None
	exc = None
	lastexc = None
	for line in lines:
		prefix1 = 'Exception in thread "main"'
		prefix2 = "Caused by:"
		prefix3 = "Suppressed:"
		if line.startswith(prefix1):
			msg = line[len(prefix1):].strip()
		elif line.startswith(prefix2):
			msg = line[len(prefix2):].strip()
		elif line.lstrip().startswith(prefix3):
			msg = line.lstrip()[len(prefix3):].strip()
		else:
			continue
		newexc = RuntimeError(msg)
		newexc.__cause__ = lastexc
		lastexc = newexc
		if exc is None:
			exc = newexc
	if exc is not None:
		print(output, file=sys.stderr)
		raise exc


def java_db(source, *path, **params):
	template = ul4c.Template(source) # Just a syntax check
	(dbuserpassword, connectdescriptor) = connect().split("@", 1)
	(dbuser, dbpassword) = dbuserpassword.split("/")
	if "template" in params:
		templateidentifier = params["template"]
		del params["template"]
	else:
		templateidentifier = None
	data = dict(
		jdbcurl=f"jdbc:oracle:thin:@{connectdescriptor}",
		jdbcuser=dbuser,
		jdbcpassword=dbpassword,
		user=user(),
		appid=path[0],
		datid=path[1] if len(path) > 1 else None,
		command="render",
		template=source,
		templateidentifier=templateidentifier,
		params=params,
	)
	dump = ul4on.dumps(data).encode("utf-8")
	result = subprocess.run("java com.livinglogic.livingapi.Tester", input=dump, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
	# Check if we have an exception
	java_find_exception(result.stderr.decode("utf-8", "passbytes"))
	return result.stdout.decode("utf-8", "passbytes")


###
### Test fixtures
###

params = [
	"python_db",
	"python_http",
	pytest.param("java_db", marks=pytest.mark.java)
]


all_handlers = dict(
	python_db=python_db,
	python_http=python_http,
	java_db=java_db,
)


@pytest.fixture(scope="module", params=params)
def handler(request):
	"""
	A parameterized fixture that returns each of the testing classes
	:class:`PythonDBHandler` and :class:`PythonHTTPHandler`.
	"""
	return all_handlers[request.param]


@pytest.fixture(scope="module")
def norecords():
	"""
	A test fixture that ensures that both test apps contain no records.
	"""
	handler = la.DBHandler(connect(), uploaddir(), user())
	vars = handler.viewtemplate_data(testappid, template="export")

	personen_app = vars.datasources.persons.app
	taetigkeitsfelder_app = vars.datasources.fieldsofactivity.app

	# Remove all persons
	for r in personen_app.records.values():
		r.delete(handler)

	# Recursively remove areas of activity
	def removeaa(r):
		for r2 in r.c_children.values():
			removeaa(r2)
		r.delete(handler)

	for r in taetigkeitsfelder_app.records.values():
		if r.v_parent is None:
			removeaa(r)

	handler.commit()
	return la.attrdict(handler=handler)


@pytest.fixture(scope="module")
def arearecords(norecords):
	"""
	A fixture that creates the records in the "area of activity" app (after
	removing all existing records).
	"""
	attrs = norecords

	handler = attrs.handler

	attrs.vars = attrs.handler.viewtemplate_data(testappid, template="export")

	taetigkeitsfelder_app = attrs.vars.datasources.fieldsofactivity.app

	attrs.areas = la.attrdict()

	def aa(**values):
		aa = taetigkeitsfelder_app(**values)
		aa.save(handler)
		return aa

	attrs.areas.science = aa(name="Science")
	attrs.areas.mathematics = aa(name="Mathematics", parent=attrs.areas.science)
	attrs.areas.physics = aa(name="Physics", parent=attrs.areas.science)
	attrs.areas.computerscience = aa(name="Computer science", parent=attrs.areas.science)
	attrs.areas.art = aa(name="Art")
	attrs.areas.film = aa(name="Film", parent=attrs.areas.art)
	attrs.areas.music = aa(name="Music", parent=attrs.areas.art)
	attrs.areas.literature = aa(name="Literature", parent=attrs.areas.art)
	attrs.areas.politics = aa(name="Politics")
	attrs.areas.industry = aa(name="Industry")
	attrs.areas.sport = aa(name="Sport")

	handler.commit()

	return attrs


@pytest.fixture(scope="module")
def personrecords(arearecords):
	"""
	A fixture that creates the records in the "persons" app (after making sure
	we have records in the "area of activity" app).
	"""
	attrs = arearecords
	ps = []

	personen_app = attrs.vars.datasources.persons.app

	handler = attrs.handler

	attrs.persons = la.attrdict()

	def p(**values):
		p = personen_app(**values)
		if p.v_portrait is not None and p.v_portrait.id is None:
			p.v_portrait.save(handler)
		p.save(handler)
		return p

	def u(u):
		return handler.file(url_.URL(u))

	def g(lat=None, long=None, info=None):
		return handler.geo(lat, long, info)

	attrs.persons.ae = p(
		firstname="Albert",
		lastname="Einstein",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[attrs.areas.physics],
		date_of_birth=datetime.date(1879, 3, 14),
		date_of_death=datetime.date(1955, 4, 15),
		grave=g(40.216085, -74.7917151),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Einstein_1921_portrait2.jpg/330px-Einstein_1921_portrait2.jpg"),
	)

	attrs.persons.mc = p(
		firstname="Marie",
		lastname="Curie",
		sex=personen_app.c_sex.lookupdata.female,
		field_of_activity=[attrs.areas.physics],
		date_of_birth=datetime.date(1867, 11, 7),
		date_of_death=datetime.date(1934, 7, 4),
		grave=g(48.84672, 2.34631),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Marie_Curie_%28Nobel-Chem%29.jpg/170px-Marie_Curie_%28Nobel-Chem%29.jpg"),
	)

	attrs.persons.ma = p(
		firstname="Muhammad",
		lastname="Ali",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[attrs.areas.sport],
		date_of_birth=datetime.date(1942, 1, 17),
		date_of_death=datetime.date(2016, 6, 3),
		grave=g(38.2454051, -85.7170115),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Muhammad_Ali_NYWTS.jpg/200px-Muhammad_Ali_NYWTS.jpg"),
	)

	attrs.persons.mm = p(
		firstname="Marilyn",
		lastname="Monroe",
		sex=personen_app.c_sex.lookupdata.female,
		field_of_activity=[attrs.areas.film],
		date_of_birth=datetime.date(1926, 6, 1),
		date_of_death=datetime.date(1962, 8, 4),
		grave=g(34.05827, -118.44096),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Marilyn_Monroe%2C_Korea%2C_1954_cropped.jpg/220px-Marilyn_Monroe%2C_Korea%2C_1954_cropped.jpg"),
	)

	attrs.persons.ep = p(
		firstname="Elvis",
		lastname="Presley",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[attrs.areas.music],
		date_of_birth=datetime.date(1935, 1, 8),
		date_of_death=datetime.date(1977, 8, 16),
		grave=g(35.04522870295311, -90.02283096313477),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Elvis_Presley_1970.jpg/170px-Elvis_Presley_1970.jpg"),
	)

	attrs.persons.br = p(
		firstname="Bernhard",
		lastname="Riemann",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[attrs.areas.mathematics],
		date_of_birth=datetime.date(1826, 6, 17),
		date_of_death=datetime.date(1866, 6, 20),
		grave=g(45.942127, 8.5870263),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/BernhardRiemannAWeger.jpg/330px-BernhardRiemannAWeger.jpg"),
	)

	attrs.persons.cfg = p(
		firstname="Carl Friedrich",
		lastname="Gauß",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[attrs.areas.mathematics],
		date_of_birth=datetime.date(1777, 4, 30),
		date_of_death=datetime.date(1855, 2, 23),
		grave=g(51.53157404627684, 9.94189739227295),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Carl_Friedrich_Gauss.jpg/255px-Carl_Friedrich_Gauss.jpg"),
	)

	attrs.persons.dk = p(
		firstname="Donald",
		lastname="Knuth",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[attrs.areas.computerscience],
		date_of_birth=datetime.date(1938, 1, 10),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/KnuthAtOpenContentAlliance.jpg/255px-KnuthAtOpenContentAlliance.jpg"),
	)

	attrs.persons.rr = p(
		firstname="Ronald",
		lastname="Reagan",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[attrs.areas.film, attrs.areas.politics],
		date_of_birth=datetime.date(1911, 2, 6),
		date_of_death=datetime.date(2004, 6, 5),
		grave=g(34.2590025, -118.8226249),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Official_Portrait_of_President_Reagan_1981.jpg/220px-Official_Portrait_of_President_Reagan_1981.jpg"),
	)

	attrs.persons.am = p(
		firstname="Angela",
		lastname="Merkel",
		sex=personen_app.c_sex.lookupdata.female,
		field_of_activity=[attrs.areas.politics],
		date_of_birth=datetime.date(1954, 6, 17),
		date_of_death=None,
		grave=None,
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/2018-03-12_Unterzeichnung_des_Koalitionsvertrages_der_19._Wahlperiode_des_Bundestages_by_Sandro_Halank%E2%80%93026_%28cropped%29.jpg/220px-2018-03-12_Unterzeichnung_des_Koalitionsvertrages_der_19._Wahlperiode_des_Bundestages_by_Sandro_Halank%E2%80%93026_%28cropped%29.jpg"),
	)

	handler.commit()

	return attrs


###
### Tests
###

def test_livingapi_user(handler):
	u = user()

	# Check that the logged in user is the user we"ve used to log in
	assert u == handler("<?print globals.user.email?>", testappid, template="export")

	# Check that the account name is part of the user ``repr`` output
	assert f" email='{u}'" in handler("<?print repr(globals.user)?>", testappid, template="export")


def test_livingapi_app(handler):
	# Check that ``app`` is the correct one
	assert testappid == handler("<?print app.id?>", testappid, template="export")
	assert "LA-Demo: Persons" == handler("<?print app.name?>", testappid, template="export")


def test_livingapi_datasources(handler):
	# Check that the datasources have the identifiers we expect
	source = "<?print ';'.join(sorted(datasources))?>"
	assert "fieldsofactivity;persons" == handler(source, testappid, template="export")


def test_livingapi_output_all_records(handler, personrecords):
	# Simply output all records from all datasources
	# to see that we don"t get any exceptions
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

	handler(source, testappid, template="export")


def test_livingapi_output_all_controls(handler):
	# Simply output all controls from all apps
	# to see that we don"t get any exceptions
	source = """
		<?for ds in datasources.values()?>
			<?if ds.app is not None and ds.app.controls is not None?>
				<?for c in ds.app.controls.values()?>
					<?print repr(c)?>
				<?end for?>
			<?end if?>
		<?end for?>
	"""

	handler(source, testappid, template="export")


def test_livingapi_detail(handler, personrecords):
	# Simply test that detail templates work
	source = """
		<?whitespace strip?>
		<?print record.v_firstname?> <?print record.v_lastname?>
	"""

	assert "Albert Einstein" == handler(source, testappid, personrecords.persons.ae.id, template="export_detail")


def test_livingapi_sort_default_order_is_newest_first(handler, personrecords):
	# Check the the default sort order is descending by creation date
	source = """
		<?whitespace strip?>
		<?code lastcreatedat = None?>
		<?for p in datasources.persons.app.records.values()?>
			<?if lastcreatedat is not None and lastcreatedat > p.createdat?>
				Bad: <?print lastcreatedat?> > <?print p.createdat?>
			<?end if?>
		<?end for?>
	"""

	assert not handler(source, testappid, template="export")


def test_livingapi_record_shortcutattributes(handler, personrecords):
	# Find "Albert Einstein" and output one of his fields in multiple ways
	source = """
		<?whitespace strip?>
		<?code papp = datasources.persons.app?>
		<?code ae = first(r for r in papp.records.values() if r.v_lastname == "Einstein")?>
		<?print repr(ae.fields.firstname.value)?>;
		<?print repr(ae.f_firstname.value)?>;
		<?print repr(ae.values.firstname)?>;
		<?print repr(ae.v_firstname)?>
	"""
	assert "'Albert';'Albert';'Albert';'Albert'" == handler(source, testappid, template="export")


def test_livingapi_app_shortcutattributes(handler):
	# Access a control and output its fields with in two ways
	source = """
		<?whitespace strip?>
		<?print repr(app.controls.firstname.identifier)?>;
		<?print repr(app.c_firstname.identifier)?>
	"""
	assert "'firstname';'firstname'" == handler(source, testappid, template="export")


def test_livingapi_insert_record(handler, norecords):
	source = """
		<?whitespace strip?>
		<?code papp = datasources.persons.app?>
		<?code r = papp.insert(firstname="Isaac", lastname="Newton")?>
		<?print repr(r.v_firstname)?> <?print repr(r.v_lastname)?>;
		<?print r.id?>
	"""
	(output, id) = handler(source, testappid, template="export").split(";")

	assert "'Isaac' 'Newton'" == output

	source = f"""
		<?whitespace strip?>
		<?code papp = datasources.persons.app?>
		<?code r = papp.records['{id}']?>
		<?print repr(r.v_firstname)?> <?print repr(r.v_lastname)?>
	"""
	assert "'Isaac' 'Newton'" == handler(source, testappid, template="export")


def test_livingapi_attributes_unsaved_record(handler):
	# Check that ``id``, ``createdat`` and ``createdby`` will be set when the
	# new record is saved
	source = """
		<?whitespace strip?>
		<?code papp = datasources.persons.app?>
		<?code r = papp(firstname="Isaac", lastname="Newton")?>
		<?print r.id is None?> <?print r.createdat is None?> <?print r.createdby is None?>
		<?code r.save()?>;
		<?print r.id is None?> <?print r.createdat is None?> <?print r.createdby.email?>
	"""
	assert f"True True True;False False {user()}" == handler(source, testappid, template="export")

	# Check that ``updatedat`` and ``updatedby`` will be set when the
	# record is saved (this even happens when the record hasn't been changed
	# however in this case no value fields will be changed)
	source = """
		<?whitespace strip?>
		<?code papp = datasources.persons.app?>
		<?code r = papp(firstname="Isaac", lastname="Newton")?>
		<?print r.updatedat is None?> <?print r.updatedby is None?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby is None?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby.email?>
		<?code r.v_date_of_birth = @(1642-12-25)?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby.email?>
	"""
	assert f"True True;True True;False {user()};False {user()}" == handler(source, testappid, template="export")


def test_livingapi_no_appparams(handler):
	source = "<?print repr(app.params)?>"
	assert "None" == python_db(source, testappid, template="export")


def test_livingapi_appparam_bool(handler):
	source = """
		<?whitespace strip?>
		<?print repr(app.params.bool_none.value)?>;
		<?print app.params.bool_none.description?>;
		<?print repr(app.params.bool_false.value)?>;
		<?print app.params.bool_false.description?>;
		<?print repr(app.params.bool_true.value)?>;
		<?print app.params.bool_true.description?>
	"""
	output = python_db(source, testappid, template="export_appparams")
	assert "None;desc bool_none;False;desc bool_false;True;desc bool_true" == output


def test_livingapi_appparam_int(handler):
	source = """
		<?whitespace strip?>
		<?print repr(app.params.int_none.value)?>;
		<?print app.params.int_none.description?>;
		<?print repr(app.params.int_value.value)?>;
		<?print app.params.int_value.description?>
	"""
	output = python_db(source, testappid, template="export_appparams")
	assert "None;desc int_none;1777;desc int_value" == output


def test_livingapi_appparam_number(handler):
	source = """
		<?whitespace strip?>
		<?print repr(app.params.number_none.value)?>;
		<?print app.params.number_none.description?>;
		<?print repr(app.params.number_value.value)?>;
		<?print app.params.number_value.description?>
	"""
	output = python_db(source, testappid, template="export_appparams")
	assert "None;desc number_none;42.5;desc number_value" == output


def test_livingapi_appparam_str(handler):
	source = """
		<?whitespace strip?>
		<?print repr(app.params.str_none.value)?>;
		<?print app.params.str_none.description?>;
		<?print repr(app.params.str_value.value)?>;
		<?print app.params.str_value.description?>
	"""
	output = python_db(source, testappid, template="export_appparams")
	assert "None;desc str_none;'gurk';desc str_value" == output


def test_livingapi_appparam_color(handler):
	source = """
		<?whitespace strip?>
		<?print repr(app.params.color_none.value)?>;
		<?print app.params.color_none.description?>;
		<?print repr(app.params.color_value.value)?>;
		<?print app.params.color_value.description?>
	"""
	output = python_db(source, testappid, template="export_appparams")
	assert "None;desc color_none;#369c;desc color_value" == output


def test_livingapi_appparam_upload(handler):
	source = """
		<?whitespace strip?>
		<?print repr(app.params.upload_none.value)?>;
		<?print app.params.upload_none.description?>;
		<?print repr(app.params.upload_value.value.mimetype)?>;
		<?print app.params.upload_value.description?>
	"""
	output = python_db(source, testappid, template="export_appparams")
	assert "None;desc upload_none;'image/jpeg';desc upload_value" == output


def test_livingapi_appparam_app(handler):
	source = """
		<?whitespace strip?>
		<?print repr(app.params.app_none.value)?>;
		<?print app.params.app_none.description?>;
		<?print repr(app.params.app_value.value.id)?>;
		<?print app.params.app_value.description?>
	"""
	output = python_db(source, testappid, template="export_appparams")
	assert f"None;desc app_none;'{testappid}';desc app_value" == output


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


def test_vsql_global_variables(personrecords):
	attrs = personrecords
	areas = attrs.areas
	source = f"""
		<?whitespace strip?>
		<?for r in datasources.fieldsofactivity.app.records.values()?>
			;<?print r.v_name?>
			<?for r2 in r.c_children.values()?>
				;<?print r2.v_name?>
			<?end for?>
		<?end for?>
	"""

	output = python_db(source, testappid, template="export_vsql_global_variables")

	expected = []
	key = operator.attrgetter("v_name")
	for a in sorted(areas.values(), key=key):
		expected.append(a.v_name)
		for a2 in sorted((a2 for a2 in areas.values() if a2.v_parent is a), key=key):
			expected.append(a2.v_name)
	expected = ";" + ";".join(expected)

	assert expected == output


def test_vsql_datasource_appfilter(personrecords):
	source = """
		<?whitespace strip?>
		<?print repr(datasources.all.app)?>
		;
		<?for a in datasources.all.apps.values()?>
			<?print a.id?>
		<?end for?>
	"""

	output = python_db(
		source,
		testappid,
		template="export_appfilter",
	)
	assert f"None;{testappid}" == output


def test_vsql_datasource_recordfilter(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_recordfilter",
	)
	assert "Albert Einstein" == output


def test_vsql_datasource_recordfilter_param_str(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_recordfilter_param_str",
		lastname="Curie",
	)

	assert "Marie Curie" == output


def test_vsql_datasource_recordfilter_param_int(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_recordfilter_param_int",
		year="1935",
	)

	assert "Elvis Presley" == output


def test_vsql_datasource_recordfilter_param_date(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_recordfilter_param_date",
		date_of_birth="1926-06-01",
	)

	assert "Marilyn Monroe" == output


def test_vsql_datasource_recordfilter_param_datetime(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_recordfilter_param_datetime",
		date_of_birth="1926-06-01T12:34:56",
	)

	assert "Marilyn Monroe" == output


def test_vsql_datasource_recordfilter_param_strlist(personrecords):
	output = python_db(
		template_sorted_persons,
		testappid,
		template="export_recordfilter_param_strlist",
		lastname=["Gauß", "Riemann"],
	)

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_vsql_datasource_recordfilter_param_intlist(personrecords):
	output = python_db(
		template_sorted_persons,
		testappid,
		template="export_recordfilter_param_intlist",
		year=["1826", "1777"],
	)

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_vsql_datasource_recordfilter_param_datelist(personrecords):
	output = python_db(
		template_sorted_persons,
		testappid,
		template="export_recordfilter_param_datelist",
		date_of_birth=["1826-06-17", "1777-04-30"],
	)

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_vsql_datasource_recordfilter_param_datetimelist(personrecords):
	output = python_db(
		template_sorted_persons,
		testappid,
		template="export_recordfilter_param_datetimelist",
		date_of_birth=["1777-04-30T12:34:56"],
	)

	assert "Carl Friedrich Gauß" == output


def test_vsql_datasource_recordfilter_appparam_int(personrecords):
	output = python_db(
		template_sorted_persons,
		testappid,
		template="export_recordfilter_appparam_int",
	)

	assert "Carl Friedrich Gauß" == output


def test_vsql_datasource_sort_asc_nullsfirst(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_sort_asc_nullsfirst",
	)

	assert "Donald Knuth;Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein" == output


def test_vsql_datasource_sort_asc_nullslast(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_sort_asc_nullslast",
	)

	assert "Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein;Donald Knuth" == output


def test_vsql_datasource_sort_desc_nullsfirst(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_sort_desc_nullsfirst",
	)

	assert "Donald Knuth;Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß" == output


def test_vsql_datasource_sort_desc_nullslast(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_sort_desc_nullslast",
	)

	assert "Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß;Donald Knuth" == output


def test_vsql_datasource_masterdetail_recordfilter(personrecords):
	attrs = personrecords
	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{attrs.areas.science.id}', '{attrs.areas.art.id}']?>
			;{template_sorted_children}
		<?end for?>
	"""

	output = python_db(source, testappid, template="export_masterdetail_recordfilter")

	assert "True;Computer science;Mathematics;Physics;Literature" == output


def test_vsql_datasource_masterdetail_sort_asc(personrecords):
	attrs = personrecords
	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{attrs.areas.science.id}', '{attrs.areas.art.id}']?>
			;{template_unsorted_children}
		<?end for?>
	"""

	output = python_db(source, testappid, template="export_masterdetail_sort_asc")

	assert "True;Computer science;Mathematics;Physics;Film;Literature;Music" == output


def test_vsql_datasource_masterdetail_sort_desc(personrecords):
	attrs = personrecords
	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{attrs.areas.science.id}', '{attrs.areas.art.id}']?>
			;{template_unsorted_children}
		<?end for?>
	"""

	output = python_db(source, testappid, template="export_masterdetail_sort_desc")

	assert "True;Physics;Mathematics;Computer science;Music;Literature;Film" == output


def test_vsql_color_attributes(personrecords):
	attrs = personrecords
	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	output = python_db(source, testappid, template="export_vsql_color_attributes")

	assert "0" != output


def test_vsql_color_methods(personrecords):
	attrs = personrecords
	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	output = python_db(source, testappid, template="export_vsql_color_methods")

	assert "0" != output


def test_vsql_repr_color(personrecords):
	attrs = personrecords
	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	output = python_db(source, testappid, template="export_vsql_repr_color")

	assert "0" != output


def test_vsql_datasource_paging(personrecords):
	output = python_db(
		template_unsorted_persons,
		testappid,
		template="export_datasource_paging",
		**{"la-ds-persons-paging": "0_2"},
	)

	assert "Muhammad Ali;Marie Curie" == output


def test_vsql_datasourcechildren_paging(personrecords):
	attrs = personrecords
	source = f"""
		<?whitespace strip?>
		<?for (f, r) in isfirst(datasources.fieldsofactivity.app.records['{attrs.areas.film.id}'].c_persons.values())?>
			<?if not f?>;<?end if?><?print r.v_firstname?> <?print r.v_lastname?>
		<?end for?>
	"""

	output = python_db(
		source,
		testappid,
		template="export_datasourcechildren_paging",
		**{f"la-dsc-fieldsofactivity-{attrs.areas.film.id}-persons-paging": "1_1"},
	)

	assert "Ronald Reagan" == output
