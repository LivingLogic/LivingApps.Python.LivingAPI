import sys, os, datetime, subprocess, operator, textwrap

import pytest

from ll import ul4c, url as url_, ul4on, misc

from ll import la


###
### Data and helper functions
###

person_app_id = "5bffc841c26a4b5902b2278c"
fields_app_id = "5bffc44c5be111d74ed79972"


class attrdict(dict):
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(key)

	def __setattr__(self, key, value):
		self[key] = value


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

class Handler:
	def __init__(self):
		self.dbhandler = la.DBHandler(connect(), uploaddir(), user())

	def make_viewtemplate(self, *args, **kwargs):
		viewtemplate = la.ViewTemplate(*args, **kwargs)
		app = la.App()
		app.id = person_app_id
		app.addtemplate(viewtemplate)
		app.save(self.dbhandler)
		self.dbhandler.commit()
		return viewtemplate


class LocalTemplateHandler(Handler):
	def __init__(self):
		super().__init__()
		self.viewtemplates = {}

	def make_viewtemplate(self, *args, **kwargs):
		source = textwrap.dedent(kwargs["source"]).lstrip()
		kwargs = {**kwargs, "source": source}
		viewtemplate = super().make_viewtemplate(*args, **kwargs)
		self.viewtemplates[viewtemplate.identifier] = viewtemplate
		return viewtemplate

	def make_ul4template(self, **params):
		if "template" in params:
			template = self.viewtemplates[params["template"]]
		else:
			template = misc.first(t for t in self.viewtemplates.values() if t.type is la.ViewTemplate.Type.LISTDEFAULT)
		template = ul4c.Template(name=template.identifier, source=template.source)
		return template


class PythonDB(LocalTemplateHandler):
	def renders(self, *path, **params):
		template = self.make_ul4template(**params)
		vars = self.dbhandler.viewtemplate_data(*path, **params)
		result = template.renders(**vars)
		self.dbhandler.commit()
		return result


class PythonHTTP(LocalTemplateHandler):
	def __init__(self):
		super().__init__()
		self.testhandler = la.HTTPHandler(url(), user(), passwd())

	def renders(self, *path, **params):
		template = self.make_ul4template(**params)
		vars = self.testhandler.viewtemplate_data(*path, **params)
		result = template.renders(**vars)
		return result


class GatewayHTTP(Handler):
	def __init__(self):
		super().__init__()
		self.testhandler = la.HTTPHandler(url(), user(), passwd())

	def renders(self, *path, **params):
		gatewayurl = url() + "gateway/apps/" + "/".join(path)
		kwargs = dict(params=params)
		self.testhandler._add_auth_token(kwargs)
		response = self.testhandler.session.get(gatewayurl, **kwargs)
		result = response.text
		return result


class JavaDB(LocalTemplateHandler):
	def __init__(self):
		super().__init__()
		(dbuserpassword, self.connectdescriptor) = connect().split("@", 1)
		(self.dbuser, self.dbpassword) = dbuserpassword.split("/")

	def renders(self, *path, **params):
		template = self.make_ul4template(**params)
		if "template" in params:
			templateidentifier = params["template"]
			del params["template"]
		else:
			templateidentifier = None
		data = dict(
			jdbcurl=f"jdbc:oracle:thin:@{self.connectdescriptor}",
			jdbcuser=self.dbuser,
			jdbcpassword=self.dbpassword,
			user=user(),
			appid=path[0],
			datid=path[1] if len(path) > 1 else None,
			command="render",
			template=template.source,
			templateidentifier=templateidentifier,
			params=params,
		)
		dump = ul4on.dumps(data).encode("utf-8")
		result = subprocess.run("java com.livinglogic.livingapi.Tester", input=dump, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
		# Check if we have an exception
		self._find_exception(result.stderr.decode("utf-8", "passbytes"))
		return result.stdout.decode("utf-8", "passbytes")

	def _find_exception(self, output):
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


###
### Test fixtures
###

params = [
	"python_db",
	"python_http",
	pytest.param("java_db", marks=pytest.mark.java),
	"gateway_http",
]


all_handlers = dict(
	python_db=PythonDB,
	python_http=PythonHTTP,
	java_db=JavaDB,
	gateway_http=GatewayHTTP,
)


@pytest.fixture(params=params)
def handler(request):
	"""
	A parameterized fixture that returns each of the testing classes
	:class:`PythonDBHandler` and :class:`PythonHTTPHandler`.
	"""
	return all_handlers[request.param]()


@pytest.fixture(scope="module")
def apps():
	"""
	A test fixture gives us a dictionary with a :class:`la.DBHandler` and the
	two :class:`la.App` objects.
	"""
	handler = la.DBHandler(connect(), uploaddir(), user())

	apps = handler.meta_data(person_app_id, fields_app_id)

	persons_app = apps[person_app_id]
	fields_app = apps[fields_app_id]

	return attrdict(
		handler=handler,
		apps=attrdict(
			persons=persons_app,
			fields=fields_app,
		),
	)


@pytest.fixture(scope="module")
def norecords(apps):
	"""
	A test fixture that ensures that both test apps contain no records.
	"""
	attrs = apps

	handler = attrs.handler

	identifier = "makerecords"

	attrs.apps.persons.addtemplate(
		la.ViewTemplate(
			la.DataSource(
				identifier="persons",
				app=attrs.apps.persons,
			),
			la.DataSource(
				la.DataSourceChildren(
					control=attrs.apps.fields.c_parent,
					identifier="children",
				),
				identifier="fields",
				app=attrs.apps.fields,
			),
			identifier=identifier,
		)
	)
	attrs.apps.persons.save(handler)

	handler.commit()

	vars = attrs.handler.viewtemplate_data(person_app_id, template=identifier)

	persons_app = vars.datasources.persons.app
	fields_app = vars.datasources.fields.app

	# Remove all persons
	for r in persons_app.records.values():
		r.delete(handler)

	# Recursively remove areas of activity
	def removeaa(r):
		for r2 in r.c_children.values():
			removeaa(r2)
		r.delete(handler)

	for r in fields_app.records.values():
		if r.v_parent is None:
			removeaa(r)

	handler.commit()

	# Replace both :class:`la.App` objects with ones that have records.
	attrs.apps.persons = persons_app
	attrs.apps.fields = fields_app

	return attrs


@pytest.fixture(scope="module")
def arearecords(norecords):
	"""
	A fixture that creates the records in the "area of activity" app (after
	removing all existing records).
	"""
	attrs = norecords

	handler = attrs.handler

	fields_app = attrs.apps.fields

	attrs.areas = attrdict()

	def aa(**values):
		aa = fields_app(**values)
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

	personen_app = attrs.apps.persons

	handler = attrs.handler

	attrs.persons = attrdict()

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


def test_livingapi_app_attributes(handler):
	"""
	Check that ``app`` is the correct one.
	"""
	vt = handler.make_viewtemplate(
		identifier="livingapi_app_attributes",
		source="<?print app.id?>;<?print app.name?>",
	)
	assert f"{person_app_id};LA-Demo: Persons" == handler.renders(person_app_id, template=vt.identifier)


def test_livingapi_datasources(handler, apps):
	"""
	Check that the datasources have the identifiers we expect.
	"""

	attrs = apps

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
		),
		la.DataSource(
			identifier="fieldsofactivity",
			app=attrs.apps.fields,
		),
		identifier="livingapi_datasources",
		source="<?print ';'.join(sorted(datasources))?>",
	)
	assert "fieldsofactivity;persons" == handler.renders(person_app_id, template=vt.identifier)


def test_livingapi_output_all_records(handler, personrecords):
	"""
	Simply output all records from all datasources.

	This checks that we don't get any exceptions.
	"""

	attrs = personrecords

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
			app=attrs.apps.persons,
		),
		la.DataSource(
			identifier="fieldsofactivity",
			app=attrs.apps.fields,
		),
		identifier="livingapi_output_all_records",
		source=source,
	)
	handler.renders(person_app_id, template=vt.identifier)


def test_livingapi_output_all_controls(handler):
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


def test_livingapi_detail(handler, personrecords):
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

	assert "Albert Einstein" == handler.renders(person_app_id, personrecords.persons.ae.id, template=vt.identifier)


def test_livingapi_sort_default_order_is_newest_first(handler, personrecords):
	"""
	Check the the default sort order is descending by creation date.
	"""

	attrs = personrecords

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
			app=attrs.apps.persons,
			includecontrols=0,
		),
		identifier="livingapi_sort_default_order_is_newest_first",
		source=source,
	)

	assert not handler.renders(person_app_id, template=vt.identifier)


def test_livingapi_record_shortcutattributes(handler, personrecords):
	"""
	Find. "Albert Einstein" and output one of his fields in multiple ways
	"""
	attrs = personrecords

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
			app=attrs.apps.persons,
		),
		identifier="livingapi_record_shortcutattributes",
		source=source,
	)
	assert "'Albert';'Albert';'Albert';'Albert'" == handler.renders(person_app_id, template="livingapi_record_shortcutattributes")


def test_livingapi_app_shortcutattributes(handler):
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


def test_livingapi_insert_record(handler, apps):
	"""
	Insert a record into the person app.
	"""
	attrs = apps

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
			app=attrs.apps.persons,
		),
		identifier="livingapi_insert_record_check_result",
		source=source,
	)
	assert "'Isaac' 'Newton'" == handler.renders(person_app_id, template=vt.identifier)


def test_livingapi_attributes_unsaved_record(handler):
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


def test_livingapi_no_appparams(handler):
	source = "<?print repr(app.params)?>"

	vt = handler.make_viewtemplate(
		identifier="livingapi_no_appparams",
		source=source,
	)

	assert "None" == handler.renders(person_app_id, template=vt.identifier)


def test_livingapi_appparam_bool(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_bool",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)
	assert "None;desc bool_none;False;desc bool_false;True;desc bool_true" == output


def test_livingapi_appparam_int(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_int",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)
	assert "None;desc int_none;1777;desc int_value" == output


def test_livingapi_appparam_number(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_number",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)
	assert "None;desc number_none;42.5;desc number_value" == output


def test_livingapi_appparam_str(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_str",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "None;desc str_none;'gurk';desc str_value" == output


def test_livingapi_appparam_color(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_color",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "None;desc color_none;#369c;desc color_value" == output


def test_livingapi_appparam_upload(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_upload",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "None;desc upload_none;'image/jpeg';desc upload_value" == output


def test_livingapi_appparam_app(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_app",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert f"None;desc app_none;'{person_app_id}';desc app_value" == output


def test_livingapi_appparam_otherattributes(handler, apps):
	attrs = apps

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
			app=attrs.apps.persons,
			includeparams=True,
		),
		identifier="livingapi_appparam_otherattributes",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)
	assert "str_value;desc str_value;True;True;True;True" == output


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
	handler = PythonDB()

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

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataOrder(expression="r.v_name"),
			la.DataOrder(expression="app.p_str_value.value"),
			la.DataOrder(expression="user.email"),
			la.DataOrder(expression="record.id"),
			la.DataOrder(expression="params.str.nix"),
			la.DataOrder(expression="len(params.strlist.nix)"),
			la.DataSourceChildren(
				la.DataOrder(expression="r.v_name"),
				la.DataOrder(expression="app.p_str_value.value"),
				la.DataOrder(expression="user.email"),
				la.DataOrder(expression="record.id"),
				la.DataOrder(expression="params.str.nix"),
				la.DataOrder(expression="len(params.strlist.nix)"),
				identifier="children",
				control=attrs.apps.fields.c_parent,
				filter="r.app.id != app.p_app_value.id and user.email is not None and record.id is None and params.str.nix is None and len(params.strlist.nix) == 0",
			),
			identifier="fieldsofactivity",
			app=attrs.apps.fields,
			recordfilter="r.app.id != app.p_app_value.id and user.email is not None and record.id is None and params.str.nix is None and len(params.strlist.nix) == 0",
			includeparams=True,
		),
		identifier="vsql_global_variables",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	expected = []
	key = operator.attrgetter("v_name")
	for a in sorted(areas.values(), key=key):
		expected.append(a.v_name)
		for a2 in sorted((a2 for a2 in areas.values() if a2.v_parent is a), key=key):
			expected.append(a2.v_name)
	expected = ";" + ";".join(expected)

	assert expected == output


def test_vsql_datasource_appfilter(personrecords):
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
		la.DataSource(
			identifier="all",
			appfilter=f"a.id == '{person_app_id}'"
		),
		identifier="vsql_datasource_appfilter",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert f"None;{person_app_id}" == output


def test_vsql_datasource_recordfilter(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_lastname == 'Einstein'",
		),
		identifier="vsql_datasource_recordfilter",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier)

	assert "Albert Einstein" == output


def test_vsql_datasource_recordfilter_param_str(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_lastname == params.str.lastname",
		),
		identifier="vsql_datasource_recordfilter_param_str",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, lastname="Curie")

	assert "Marie Curie" == output


def test_vsql_datasource_recordfilter_param_int(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_date_of_birth.year == params.int.year",
		),
		identifier="vsql_datasource_recordfilter_param_int",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, year="1935")

	assert "Elvis Presley" == output


def test_vsql_datasource_recordfilter_param_date(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_date_of_birth == params.date.date_of_birth",
		),
		identifier="vsql_datasource_recordfilter_param_date",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, date_of_birth="1926-06-01")

	assert "Marilyn Monroe" == output


def test_vsql_datasource_recordfilter_param_datetime(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="datetime(r.v_date_of_birth) + hours(12) + minutes(34) + seconds(56) == params.datetime.date_of_birth",
		),
		identifier="vsql_datasource_recordfilter_param_datetime",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, date_of_birth="1926-06-01T12:34:56")

	assert "Marilyn Monroe" == output


def test_vsql_datasource_recordfilter_param_strlist(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_lastname in params.strlist.lastname",
		),
		identifier="vsql_datasource_recordfilter_param_strlist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, lastname=["Gauß", "Riemann"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_vsql_datasource_recordfilter_param_intlist(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_date_of_birth.year in params.intlist.year",
		),
		identifier="vsql_datasource_recordfilter_param_intlist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, year=["1826", "1777"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_vsql_datasource_recordfilter_param_datelist(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_date_of_birth in params.datelist.date_of_birth",
		),
		identifier="vsql_datasource_recordfilter_param_datelist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, date_of_birth=["1826-06-17", "1777-04-30"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == output


def test_vsql_datasource_recordfilter_param_datetimelist(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="datetime(r.v_date_of_birth) + hours(12) + minutes(34) + seconds(56) == params.datetimelist.date_of_birth[0]",
		),
		identifier="vsql_datasource_recordfilter_param_datelist",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier, date_of_birth=["1777-04-30T12:34:56"])

	assert "Carl Friedrich Gauß" == output


def test_vsql_datasource_recordfilter_appparam_int(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_date_of_birth.year == app.p_int_value.value",
		),
		identifier="vsql_datasource_recordfilter_appparam_int",
		source=template_sorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier)

	assert "Carl Friedrich Gauß" == output


def test_vsql_datasource_sort_asc_nullsfirst(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataOrder(expression="r.v_date_of_death", direction="asc", nulls="first"),
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_asc_nullsfirst",
		source=template_unsorted_persons,
	)
	output = handler.renders(person_app_id, template=vt.identifier)

	assert "Donald Knuth;Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein" == output


def test_vsql_datasource_sort_asc_nullslast(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataOrder(expression="r.v_date_of_death", direction="asc", nulls="last"),
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_asc_nullslast",
		source=template_unsorted_persons,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein;Donald Knuth" == output


def test_vsql_datasource_sort_desc_nullsfirst(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataOrder(expression="r.v_date_of_death", direction="desc", nulls="first"),
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_desc_nullsfirst",
		source=template_unsorted_persons,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "Donald Knuth;Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß" == output


def test_vsql_datasource_sort_desc_nullslast(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataOrder(expression="r.v_date_of_death", direction="desc", nulls="last"),
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="r.v_lastname in ['Knuth', 'Gauß', 'Einstein', 'Riemann']",
		),
		identifier="vsql_datasource_sort_desc_nullslast",
		source=template_unsorted_persons,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß;Donald Knuth" == output


def test_vsql_datasource_masterdetail_recordfilter(personrecords):
	attrs = personrecords

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{attrs.areas.science.id}', '{attrs.areas.art.id}']?>
			;{template_sorted_children}
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataSourceChildren(
				identifier="children",
				control=attrs.apps.fields.c_parent,
				filter="len(r.v_name) >= 6",
			),
			identifier="fieldsofactivity",
			app=attrs.apps.fields,
			recordfilter="r.v_parent.id is None",
		),
		identifier="vsql_datasource_masterdetail_recordfilter",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "True;Computer science;Mathematics;Physics;Literature" == output


def test_vsql_datasource_masterdetail_sort_asc(personrecords):
	attrs = personrecords

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{attrs.areas.science.id}', '{attrs.areas.art.id}']?>
			;{template_unsorted_children}
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataSourceChildren(
				la.DataOrder(expression="r.v_name", direction="asc", nulls="first"),
				identifier="children",
				control=attrs.apps.fields.c_parent,
			),
			identifier="fieldsofactivity",
			app=attrs.apps.fields,
			recordfilter="r.v_parent.id is None",
		),
		identifier="vsql_datasource_masterdetail_sort_asc",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "True;Computer science;Mathematics;Physics;Film;Literature;Music" == output


def test_vsql_datasource_masterdetail_sort_desc(personrecords):
	attrs = personrecords

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print all(r.v_parent is None for r in datasources.fieldsofactivity.app.records.values())?>
		<?for id in ['{attrs.areas.science.id}', '{attrs.areas.art.id}']?>
			;{template_unsorted_children}
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataSourceChildren(
				la.DataOrder(expression="r.v_name", direction="desc", nulls="first"),
				identifier="children",
				control=attrs.apps.fields.c_parent,
			),
			identifier="fieldsofactivity",
			app=attrs.apps.fields,
			recordfilter="r.v_parent.id is None",
		),
		identifier="vsql_datasource_masterdetail_sort_desc",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "True;Physics;Mathematics;Computer science;Music;Literature;Film" == output


def test_vsql_color_attributes(personrecords):
	attrs = personrecords

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="app.p_color_value.value.r == 0x33 and app.p_color_value.value.g == 0x66 and app.p_color_value.value.b == 0x99 and app.p_color_value.value.a == 0xcc",
		),
		identifier="vsql_color_attributes",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "0" != output


def test_vsql_color_methods(personrecords):
	attrs = personrecords

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter="app.p_color_value.value.lum() == 0.4",
		),
		identifier="vsql_color_methods",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "0" != output


def test_vsql_repr_color(personrecords):
	attrs = personrecords

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?print len(datasources.persons.app.records)?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			identifier="persons",
			app=attrs.apps.persons,
			recordfilter='repr(#369) == "#369" and repr(#369c) == "#369c" and repr(#123456) == "#123456" and repr(#12345678) == "#12345678"',
		),
		identifier="vsql_repr_color",
		source=source,
	)

	output = handler.renders(person_app_id, template=vt.identifier)

	assert "0" != output


def test_vsql_datasource_paging(personrecords):
	attrs = personrecords

	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataOrder("r.v_lastname"),
			la.DataOrder("r.v_firstname"),
			identifier="persons",
			app=attrs.apps.persons,
		),
		identifier="vsql_datasource_paging",
		source=template_unsorted_persons,
	)

	output = handler.renders(
		person_app_id,
		template=vt.identifier,
		**{"la-ds-persons-paging": "0_2"},
	)

	assert "Muhammad Ali;Marie Curie" == output


def test_vsql_datasourcechildren_paging(personrecords):
	attrs = personrecords

	handler = PythonDB()

	source = f"""
		<?whitespace strip?>
		<?for (f, r) in isfirst(datasources.fieldsofactivity.app.records['{attrs.areas.film.id}'].c_persons.values())?>
			<?if not f?>;<?end if?><?print r.v_firstname?> <?print r.v_lastname?>
		<?end for?>
	"""

	vt = handler.make_viewtemplate(
		la.DataSource(
			la.DataOrder("r.v_name"),
			la.DataSourceChildren(
				la.DataOrder("r.v_lastname"),
				la.DataOrder("r.v_firstname"),
				identifier="persons",
				control=attrs.apps.persons.c_field_of_activity,
			),
			identifier="fieldsofactivity",
			app=attrs.apps.fields,
		),
		identifier="vsql_datasourcechildren_paging",
		source=source,
	)

	output = handler.renders(
		person_app_id,
		template=vt.identifier,
		**{f"la-dsc-fieldsofactivity-{attrs.areas.film.id}-persons-paging": "1_1"},
	)

	assert "Ronald Reagan" == output
