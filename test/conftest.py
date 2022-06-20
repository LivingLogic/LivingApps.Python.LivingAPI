import sys, os, datetime, subprocess, textwrap, pathlib

import pytest

from ll import ul4c, url as url_, ul4on, misc

from ll import la


###
### Data and helper functions
###

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


def hostname():
	return os.environ["LA_LIVINGAPI_TEST_HOSTNAME"]


def url():
	return f"https://{hostname()}/"


def user():
	"""
	Return the account name of the user that should be used for connecting to LivingApps.
	"""
	return os.environ["LA_LIVINGAPI_TEST_USER"]


def passwd():
	return os.environ["LA_LIVINGAPI_TEST_PASSWD"]


def person_app_id():
	return os.environ["LA_LIVINGAPI_TEST_PERSONAPP"]


def fields_app_id():
	return os.environ["LA_LIVINGAPI_TEST_FIELDAPP"]


def check_vsql(config_persons, code, result=None):
	c = config_persons

	# Use the name of the calling function (without "test_")
	# as the name of the view template.
	filename = pathlib.Path(sys._getframe(1).f_code.co_filename).with_suffix("").name
	functionname = sys._getframe(1).f_code.co_name[5:]
	identifier = f"{filename}_{functionname}"
	handler = PythonDB()

	vt = handler.make_viewtemplate(
		la.DataSourceConfig(
			recordfilter=code,
			identifier="persons",
			app=c.apps.persons,
			includeparams=True,
		),
		identifier=identifier,
		source="""
			<?whitespace strip?>
			<?print len(datasources.persons.app.records)?>
		""",
	)

	output = handler.renders(person_app_id(), template=vt.identifier)

	if result is None:
		assert "0" != output
	else:
		assert result == output


###
### Testing handlers
###

class Handler:
	def __init__(self):
		self.dbhandler = la.DBHandler(connectstring=connect(), uploaddir=uploaddir(), ide_account=user())

	def make_viewtemplate(self, *args, **kwargs):
		viewtemplate = la.ViewTemplateConfig(*args, **{**{"mimetype": "text/plain"}, **kwargs})
		app = la.App()
		app.id = person_app_id()
		app.addtemplate(viewtemplate)
		with self.dbhandler:
			app.save(self.dbhandler)
		return viewtemplate

	def make_internaltemplate(self, *args, **kwargs):
		internaltemplate = la.InternalTemplate(*args, **kwargs)
		app = la.App()
		app.id = person_app_id()
		app.addtemplate(internaltemplate)
		with self.dbhandler:
			app.save(self.dbhandler)
		return internaltemplate


class LocalTemplateHandler(Handler):
	def __init__(self):
		super().__init__()
		self.viewtemplates = {}

	def make_viewtemplate(self, *args, **kwargs):
		kwargs["source"] = textwrap.dedent(kwargs["source"]).lstrip()
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
		with self.dbhandler:
			template = self.make_ul4template(**params)
		with self.dbhandler:
			vars = self.dbhandler.viewtemplate_data(*path, **params)
			globals = vars["globals"]
			globals.request = la.HTTPRequest()
			globals.request.params.update(**params)
			# Make sure that we render the template with the same handler and db state
			# as we had when we fetched the UL4ON, as rendering the template might
			# load data incrementally
			result = template.renders_with_globals([], vars, dict(globals=globals, la=la.module))
		return result



class PythonHTTP(LocalTemplateHandler):
	def __init__(self):
		super().__init__()
		self.testhandler = la.HTTPHandler(url(), user(), passwd())

	def renders(self, *path, **params):
		template = self.make_ul4template(**params)
		with self.testhandler:
			vars = self.testhandler.viewtemplate_data(*path, **params)
			# We don't have to call the following code inside the ``with`` block
			# since the data was fetched by the ``HTTPHandler`` which doesn't support
			# loading data incrementally anyway. But this means that test might fail
			# for these dynamic attributes (or have to be skipped).
			# But note that we *do* have to call it inside a separate ``with`` block
			# so that the backref registry gets reset afterwards.
			globals = vars["globals"]
			globals.request = la.HTTPRequest()
			globals.request.params.update(**params)
			result = template.renders_with_globals([], vars, dict(globals=globals, la=la.module))
		return result


class GatewayHTTP(Handler):
	def __init__(self):
		super().__init__()
		self.testhandler = la.HTTPHandler(url(), user(), passwd())

	def renders(self, *path, **params):
		self.testhandler._login()
		gatewayurl = url() + "gateway/apps/" + "/".join(path)
		kwargs = dict(params={f"{k}[]" if isinstance(v, list) else k: v for (k, v) in params.items()})
		with self.testhandler:
			self.testhandler._add_auth_token(kwargs)
			response = self.testhandler.session.get(gatewayurl, **kwargs)
			result = response.text
		return result


class JavaDB(LocalTemplateHandler):
	def __init__(self):
		super().__init__()
		(dbuserpassword, self.connectdescriptor) = connect().split("@", 1)
		(self.dbuser, self.dbpassword) = dbuserpassword.split("/")

	def _indent(self, text):
		return textwrap.indent(text, "\t\t")

	def renders(self, *path, **params):
		url = "/".join(path)
		if params:
			url += "?" + "&".join(f"{k}={v}" for (k, v) in params.items())
		print(f"Running {url}")
		with self.dbhandler:
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
		dump = ul4on.dumps(data)
		print(f"\tInput data as UL4ON dump is:\n{self._indent(dump)}")
		dump = dump.encode("utf-8")
		currentdir = pathlib.Path.cwd()
		try:
			os.chdir(pathlib.Path.home() / "checkouts/LivingApps.Java.LivingAPI")
			result = subprocess.run("gradle -q --console=plain execute", input=dump, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
		finally:
			os.chdir(currentdir)
		print(f"\tReturn code is {result.returncode}")
		# Check if we have an exception
		stderr = result.stderr.decode("utf-8", "passbytes")
		print(f"\tOutput on stderr is:\n{self._indent(stderr)}")
		if result.returncode != 0:
			self._find_exception(stderr)
			if stderr:
				# No exception found, but we still have error output,
				# so complain anyway with the original output
				raise ValueError(stderr)
		stdout = result.stdout.decode("utf-8", "passbytes")
		print(f"\tOutput on stdout is:\n{self._indent(stdout)}")
		return stdout

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
			raise exc


###
### Test fixtures
###

params = [
	"python_db",
	pytest.param("python_http", marks=pytest.mark.flaky(reruns=3, reruns_delay=2)),
	pytest.param("java_db", marks=pytest.mark.java),
	pytest.param("gateway_http", marks=pytest.mark.flaky(reruns=0, reruns_delay=2)),
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
def config_apps():
	"""
	A test fixture that gives us a dictionary with a :class:`la.DBHandler` and
	the two :class:`la.App` objects.
	"""
	handler = la.DBHandler(connectstring=connect(), uploaddir=uploaddir(), ide_account=user())

	vars = handler.meta_data(person_app_id(), fields_app_id())

	persons_app = vars["apps"][person_app_id()]
	fields_app = vars["apps"][fields_app_id()]

	return attrdict(
		handler=handler,
		apps=attrdict(
			persons=persons_app,
			fields=fields_app,
		),
	)


@pytest.fixture(scope="module")
def config_norecords(config_apps):
	"""
	A test fixture that ensures that both test apps contain no records.
	"""
	c = config_apps

	identifier = "makerecords"

	c.apps.persons.addtemplate(
		la.ViewTemplateConfig(
			la.DataSourceConfig(
				identifier="persons",
				app=c.apps.persons,
			),
			la.DataSourceConfig(
				la.DataSourceChildren(
					control=c.apps.fields.c_parent,
					identifier="children",
				),
				identifier="fields",
				app=c.apps.fields,
			),
			identifier=identifier,
		)
	)
	c.apps.persons.viewtemplates.makerecords.save(c.handler)

	c.handler.reset()
	c.handler.commit()

	vars = c.handler.viewtemplate_data(person_app_id(), template=identifier)

	persons_app = vars.datasources.persons.app
	fields_app = vars.datasources.fields.app

	# Remove all persons
	for r in persons_app.records.values():
		r.delete(c.handler)

	# Recursively remove areas of activity
	def removeaa(r):
		for r2 in r.c_children.values():
			removeaa(r2)
		r.delete(c.handler)

	for r in fields_app.records.values():
		if r.v_parent is None:
			removeaa(r)

	c.handler.reset()
	c.handler.commit()

	# Replace both :class:`la.App` objects with ones that have records.
	c.apps.persons = persons_app
	c.apps.fields = fields_app

	return c


@pytest.fixture(scope="module")
def config_fields(config_norecords):
	"""
	A fixture that creates the records in the "area of activity" app (after
	removing all existing records).
	"""
	c = config_norecords

	fields_app = c.apps.fields

	c.areas = attrdict()

	def aa(**values):
		aa = fields_app(**values)
		aa.save(c.handler)
		return aa

	c.areas.science = aa(name="Science")
	c.areas.mathematics = aa(name="Mathematics", parent=c.areas.science)
	c.areas.physics = aa(name="Physics", parent=c.areas.science)
	c.areas.computerscience = aa(name="Computer science", parent=c.areas.science)
	c.areas.art = aa(name="Art")
	c.areas.film = aa(name="Film", parent=c.areas.art)
	c.areas.music = aa(name="Music", parent=c.areas.art)
	c.areas.literature = aa(name="Literature", parent=c.areas.art)
	c.areas.politics = aa(name="Politics")
	c.areas.industry = aa(name="Industry")
	c.areas.sport = aa(name="Sport")

	c.handler.reset()
	c.handler.commit()

	return c


@pytest.fixture(scope="module")
def config_persons(config_fields):
	"""
	A fixture that creates the records in the "persons" app (after making sure
	we have records in the "area of activity" app).
	"""
	c = config_fields

	personen_app = c.apps.persons

	c.persons = attrdict()

	def p(**values):
		p = personen_app(**values)
		if p.v_portrait is not None and p.v_portrait.id is None:
			p.v_portrait.save(c.handler)
		p.save(c.handler)
		return p

	def u(u):
		return c.handler.file(url_.URL(u))

	def g(lat=None, long=None, info=None):
		return c.handler.geo(lat, long, info)

	c.persons.ae = p(
		firstname="Albert",
		lastname="Einstein",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[c.areas.physics],
		country_of_birth="germany",
		date_of_birth=datetime.date(1879, 3, 14),
		date_of_death=datetime.date(1955, 4, 15),
		grave=g(40.216085, -74.7917151),
		nobel_prize=False,
		url="https://de.wikipedia.org/wiki/Albert_Einstein",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Einstein_1921_portrait2.jpg/330px-Einstein_1921_portrait2.jpg"),
	)

	c.persons.mc = p(
		firstname="Marie",
		lastname="Curie",
		sex=personen_app.c_sex.lookupdata.female,
		field_of_activity=[c.areas.physics],
		country_of_birth="poland",
		date_of_birth=datetime.date(1867, 11, 7),
		date_of_death=datetime.date(1934, 7, 4),
		grave=g(48.84672, 2.34631),
		nobel_prize=True,
		url="https://de.wikipedia.org/wiki/Marie_Curie",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Marie_Curie_%28Nobel-Chem%29.jpg/170px-Marie_Curie_%28Nobel-Chem%29.jpg"),
	)

	c.persons.ma = p(
		firstname="Muhammad",
		lastname="Ali",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[c.areas.sport],
		country_of_birth="usa",
		date_of_birth=datetime.date(1942, 1, 17),
		date_of_death=datetime.date(2016, 6, 3),
		grave=g(38.2454051, -85.7170115),
		nobel_prize=False,
		url="https://de.wikipedia.org/wiki/Muhammad_Ali",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Muhammad_Ali_NYWTS.jpg/200px-Muhammad_Ali_NYWTS.jpg"),
	)

	c.persons.mm = p(
		firstname="Marilyn",
		lastname="Monroe",
		sex=personen_app.c_sex.lookupdata.female,
		field_of_activity=[c.areas.film],
		country_of_birth="usa",
		date_of_birth=datetime.date(1926, 6, 1),
		date_of_death=datetime.date(1962, 8, 4),
		grave=g(34.05827, -118.44096),
		nobel_prize=False,
		url="https://de.wikipedia.org/wiki/Marilyn_Monroe",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Marilyn_Monroe%2C_Korea%2C_1954_cropped.jpg/220px-Marilyn_Monroe%2C_Korea%2C_1954_cropped.jpg"),
	)

	c.persons.ep = p(
		firstname="Elvis",
		lastname="Presley",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[c.areas.music],
		country_of_birth="usa",
		date_of_birth=datetime.date(1935, 1, 8),
		date_of_death=datetime.date(1977, 8, 16),
		grave=g(35.04522870295311, -90.02283096313477),
		nobel_prize=False,
		url="https://de.wikipedia.org/wiki/Elvis_Presley",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Elvis_Presley_1970.jpg/170px-Elvis_Presley_1970.jpg"),
	)

	c.persons.br = p(
		firstname="Bernhard",
		lastname="Riemann",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[c.areas.mathematics],
		country_of_birth="germany",
		date_of_birth=datetime.date(1826, 6, 17),
		date_of_death=datetime.date(1866, 6, 20),
		grave=g(45.942127, 8.5870263),
		nobel_prize=False,
		url="https://de.wikipedia.org/wiki/Bernhard_Riemann",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/BernhardRiemannAWeger.jpg/330px-BernhardRiemannAWeger.jpg"),
	)

	c.persons.cfg = p(
		firstname="Carl Friedrich",
		lastname="Gauß",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[c.areas.mathematics],
		country_of_birth="germany",
		date_of_birth=datetime.date(1777, 4, 30),
		date_of_death=datetime.date(1855, 2, 23),
		grave=g(51.53157404627684, 9.94189739227295),
		nobel_prize=False,
		url="https://de.wikipedia.org/wiki/Carl_Friedrich_Gau%C3%9F",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Carl_Friedrich_Gauss.jpg/255px-Carl_Friedrich_Gauss.jpg"),
	)

	c.persons.dk = p(
		firstname="Donald",
		lastname="Knuth",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[c.areas.computerscience],
		country_of_birth="usa",
		date_of_birth=datetime.date(1938, 1, 10),
		url="https://de.wikipedia.org/wiki/Donald_E._Knuth",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/KnuthAtOpenContentAlliance.jpg/255px-KnuthAtOpenContentAlliance.jpg"),
	)

	c.persons.rr = p(
		firstname="Ronald",
		lastname="Reagan",
		sex=personen_app.c_sex.lookupdata.male,
		field_of_activity=[c.areas.film, c.areas.politics],
		country_of_birth="usa",
		date_of_birth=datetime.date(1911, 2, 6),
		date_of_death=datetime.date(2004, 6, 5),
		grave=g(34.2590025, -118.8226249),
		nobel_prize=False,
		url="https://de.wikipedia.org/wiki/Ronald_Reagan",
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Official_Portrait_of_President_Reagan_1981.jpg/220px-Official_Portrait_of_President_Reagan_1981.jpg"),
	)

	c.persons.am = p(
		firstname="Angela",
		lastname="Merkel",
		sex=personen_app.c_sex.lookupdata.female,
		field_of_activity=[c.areas.politics],
		country_of_birth="germany",
		date_of_birth=datetime.date(1954, 6, 17),
		date_of_death=None,
		grave=None,
		nobel_prize=False,
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/2018-03-12_Unterzeichnung_des_Koalitionsvertrages_der_19._Wahlperiode_des_Bundestages_by_Sandro_Halank%E2%80%93026_%28cropped%29.jpg/220px-2018-03-12_Unterzeichnung_des_Koalitionsvertrages_der_19._Wahlperiode_des_Bundestages_by_Sandro_Halank%E2%80%93026_%28cropped%29.jpg"),
	)

	c.handler.reset()
	c.handler.commit()

	return c
