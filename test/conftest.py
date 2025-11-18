import sys, os, datetime, subprocess, textwrap, pathlib, filelock

import pytest

from ll import ul4c, url as url_, ul4on, misc
from ll.xist import xsc, parse, xfind
from ll.xist.ns import html

from ll import la

dir = pathlib.Path(__file__).absolute().parent


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


def connect_postgres():
	return os.environ["LA_LIVINGAPI_TEST_CONNECT_POSTGRES"]


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


def check_vsql(config_data, code, result=None):
	c = config_data

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
		self.dbhandler = la.DBHandler(
			connectstring=connect(),
			connectstring_postgres=connect_postgres(),
			uploaddir=uploaddir(),
			ide_account=user(),
		)

	def make_viewtemplate(self, *args, **kwargs):
		viewtemplate = la.ViewTemplateConfig(*args, **{**{"mimetype": "text/plain"}, **kwargs})
		with self.dbhandler:
			app = la.App()
			app.handler = self.dbhandler
			app.id = person_app_id()
			app.addtemplate(viewtemplate)
			self.dbhandler.save_app_config(app)
		return viewtemplate

	def make_internaltemplate(self, *args, **kwargs):
		internaltemplate = la.InternalTemplate(*args, **kwargs)
		with self.dbhandler:
			app = la.App()
			app.handler = self.dbhandler
			app.id = person_app_id()
			app.addtemplate(internaltemplate)
			self.dbhandler.save_app_config(app)
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
			# loading data incrementally anyway. But this means that tests might fail
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
		(dbuserpassword_oracle, self.connectdescriptor_oracle) = connect().split("@", 1)
		(self.dbuser_oracle, self.dbpassword_oracle) = dbuserpassword_oracle.split("/")

		self.connectionparams_postgres = dict(item.split("=", 1) for item in connect_postgres().split())

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
			oracle_jdbcurl=f"jdbc:oracle:thin:@{self.connectdescriptor_oracle}",
			oracle_jdbcuser=self.dbuser_oracle,
			oracle_jdbcpassword=self.dbpassword_oracle,
			postgres_jdbcurl=f"jdbc:postgresql://{self.connectionparams_postgres['host']}/{self.connectionparams_postgres['dbname']}",
			postgres_jdbcuser=self.connectionparams_postgres['user'],
			postgres_jdbcpassword=self.connectionparams_postgres['password'],
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
	pytest.param("python_db", marks=[pytest.mark.python, pytest.mark.db]),
	pytest.param("python_http", marks=[pytest.mark.python, pytest.mark.http, pytest.mark.flaky(reruns=3, reruns_delay=2)]),
	pytest.param("java_db", marks=[pytest.mark.java, pytest.mark.db]),
	pytest.param("gateway_http", marks=[pytest.mark.java, pytest.mark.http, pytest.mark.flaky(reruns=0, reruns_delay=2)]),
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


def create_data():
	with la.DBHandler(connectstring=connect(), connectstring_postgres=connect_postgres(), uploaddir=uploaddir(), ide_account=user()) as handler:
		vars = handler.viewtemplate_data(person_app_id(), template="livingapi_datasources")

		persons_app = vars.datasources.persons.app
		fields_app = vars.datasources.fieldsofactivity.app
		globals = vars["globals"]

		# Remove all persons
		for r in persons_app.records.values():
			r.delete()

		# Remove all areas of activity
		for r in fields_app.records.values():
			r.delete()

		handler.reset()
		handler.commit()

		# Create records in the "areas of activity" app

		areas = attrdict()

		def aa(**values):
			aa = fields_app(**values)
			aa.save()
			fields_app.records[aa.id] = aa
			return aa

		areas.science = aa(name="Science")
		areas.mathematics = aa(name="Mathematics", parent=areas.science)
		areas.physics = aa(name="Physics", parent=areas.science)
		areas.computerscience = aa(name="Computer science", parent=areas.science)
		areas.art = aa(name="Art")
		areas.film = aa(name="Film", parent=areas.art)
		areas.music = aa(name="Music", parent=areas.art)
		areas.literature = aa(name="Literature", parent=areas.art)
		areas.politics = aa(name="Politics")
		areas.industry = aa(name="Industry")
		areas.sport = aa(name="Sport")

		handler.reset()
		handler.commit()

		# Create records in the "persons" app

		persons = attrdict()

		def p(**values):
			p = persons_app(**values)
			if 0:
				if "url" in values:
					page_url = values["url"]
					e = parse.tree(
						parse.URL(page_url),
						parse.Tidy(),
						parse.NS(html),
						parse.Node(pool=xsc.Pool(html)),
					)
					selector = xfind.hasclass('mw-parser-output') / html.p
					notes = misc.first(e.walknodes(selector))
					notes = notes.mapped(lambda n, c: xsc.Null if isinstance(n, html.sup) else n)
					p.v_notes = notes.string()

			if p.v_portrait is not None and p.v_portrait.id is None:
				handler.save_file(p.v_portrait)
			# Ignore `required` state we might "inherit" from the first form
			p.save(force=True)
			persons_app.records[p.id] = p
			return p

		def u(u):
			return globals.file(dir / u)

		def g(lat=None, long=None, info=None):
			return globals.geo(lat, long, info)

		persons.ae = p(
			firstname="Albert",
			lastname="Einstein",
			sex=persons_app.c_sex.lookupdata.male,
			field_of_activity=[areas.physics],
			country_of_birth="germany",
			date_of_birth=datetime.date(1879, 3, 14),
			date_of_death=datetime.date(1955, 4, 15),
			grave=g(40.216085, -74.7917151, "Grave of Albery Einstein"),
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Albert_Einstein",
			portrait=u("images/Albert_Einstein.jpg"),
		)

		persons.mc = p(
			firstname="Marie",
			lastname="Curie",
			sex=persons_app.c_sex.lookupdata.female,
			field_of_activity=[areas.physics],
			country_of_birth="poland",
			date_of_birth=datetime.date(1867, 11, 7),
			date_of_death=datetime.date(1934, 7, 4),
			grave=g(48.84672, 2.34631, "Grave of Marie Curie"),
			nobel_prize=True,
			url="https://de.wikipedia.org/wiki/Marie_Curie",
			portrait=u("images/Marie_Curie.jpg"),
		)

		persons.ma = p(
			firstname="Muhammad",
			lastname="Ali",
			sex=persons_app.c_sex.lookupdata.male,
			field_of_activity=[areas.sport],
			country_of_birth="usa",
			date_of_birth=datetime.date(1942, 1, 17),
			date_of_death=datetime.date(2016, 6, 3),
			grave=g(38.2454051, -85.7170115, "Grave of Muhammad Ali"),
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Muhammad_Ali",
			portrait=u("images/Muhammad_Ali.jpg"),
		)

		persons.mm = p(
			firstname="Marilyn",
			lastname="Monroe",
			sex=persons_app.c_sex.lookupdata.female,
			field_of_activity=[areas.film],
			country_of_birth="usa",
			date_of_birth=datetime.date(1926, 6, 1),
			date_of_death=datetime.date(1962, 8, 4),
			grave=g(34.05827, -118.44096, "Grave of Marilyn Monroe"),
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Marilyn_Monroe",
			portrait=u("images/Marilyn_Monroe.jpg"),
		)

		persons.ep = p(
			firstname="Elvis",
			lastname="Presley",
			sex=persons_app.c_sex.lookupdata.male,
			field_of_activity=[areas.music],
			country_of_birth="usa",
			date_of_birth=datetime.date(1935, 1, 8),
			date_of_death=datetime.date(1977, 8, 16),
			grave=g(35.04522870295311, -90.02283096313477, "Grave of Elvis Presley"),
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Elvis_Presley",
			portrait=u("images/Elvis_Presley.jpg"),
		)

		persons.br = p(
			firstname="Bernhard",
			lastname="Riemann",
			sex=persons_app.c_sex.lookupdata.male,
			field_of_activity=[areas.mathematics],
			country_of_birth="germany",
			date_of_birth=datetime.date(1826, 6, 17),
			date_of_death=datetime.date(1866, 6, 20),
			grave=g(45.942127, 8.5870263, "Grave of Bernhard Riemann"),
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Bernhard_Riemann",
			portrait=u("images/Bernhard_Riemann.jpg"),
		)

		persons.cfg = p(
			firstname="Carl Friedrich",
			lastname="Gauß",
			sex=persons_app.c_sex.lookupdata.male,
			field_of_activity=[areas.mathematics],
			country_of_birth="germany",
			date_of_birth=datetime.date(1777, 4, 30),
			date_of_death=datetime.date(1855, 2, 23),
			grave=g(51.53157404627684, 9.94189739227295, "Grave of Carl Friedrich Gauß"),
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Carl_Friedrich_Gau%C3%9F",
			portrait=u("images/Carl_Friedrich_Gauss.jpg"),
		)

		persons.dk = p(
			firstname="Donald",
			lastname="Knuth",
			sex=persons_app.c_sex.lookupdata.male,
			field_of_activity=[areas.computerscience],
			country_of_birth="usa",
			date_of_birth=datetime.date(1938, 1, 10),
			url="https://de.wikipedia.org/wiki/Donald_E._Knuth",
			portrait=u("images/Donald_Knuth.jpg"),
		)

		persons.rr = p(
			firstname="Ronald",
			lastname="Reagan",
			sex=persons_app.c_sex.lookupdata.male,
			field_of_activity=[areas.film, areas.politics],
			country_of_birth="usa",
			date_of_birth=datetime.date(1911, 2, 6),
			date_of_death=datetime.date(2004, 6, 5),
			grave=g(34.2590025, -118.8226249, "Grave of Roland Reagan"),
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Ronald_Reagan",
			portrait=u("images/Ronald_Reagan.jpg"),
		)

		persons.am = p(
			firstname="Angela",
			lastname="Merkel",
			sex=persons_app.c_sex.lookupdata.female,
			field_of_activity=[areas.politics],
			country_of_birth="germany",
			date_of_birth=datetime.date(1954, 6, 17),
			date_of_death=None,
			grave=None,
			nobel_prize=False,
			url="https://de.wikipedia.org/wiki/Angela_Merkel",
			portrait=u("images/Angela_Merkel.jpg"),
		)

		handler.reset()
		handler.commit()

		return attrdict(
			globals=globals,
			apps=attrdict(
				persons=persons_app,
				fields=fields_app,
			),
			areas=areas,
			persons=persons
		)


def fetch_data():
	with la.DBHandler(connectstring=connect(), connectstring_postgres=connect_postgres(), uploaddir=uploaddir(), ide_account=user()) as handler:
		vars = handler.viewtemplate_data(person_app_id(), template="livingapi_datasources")

		persons_app = vars.datasources.persons.app
		fields_app = vars.datasources.fieldsofactivity.app
		globals = vars["globals"]

		return attrdict(
			globals=globals,
			apps=attrdict(
				persons=persons_app,
				fields=fields_app,
			),
			areas=attrdict({a.v_name.replace(" ", "").lower() : a for a in fields_app.records.values()}),
			persons=attrdict({"".join(name[:1].lower() for name in f"{p.v_firstname} {p.v_lastname}".split()) : p for p in persons_app.records.values()}),
		)


@pytest.fixture(scope="session")
def config_data(tmp_path_factory, worker_id):
	"""
	A test fixture that gives us a dictionary with a :class:`la.DBHandler` and
	the two :class:`la.App` objects.

	A set of test records in the "area of activity" app will be created
	(after removing all existing records) and stored in the ``areas`` attribute.

	A set of test records in the "persons" app will be created
	(after removing all existing records) and stored in the ``persons`` attribute.

	"""

	# This uses the logic documented here:
	# https://pytest-xdist.readthedocs.io/en/latest/how-to.html#making-session-scoped-fixtures-execute-only-once
	# to support running under ``pytest-xdist``

	if worker_id == "master":
		return create_data()

	# get the temp directory shared by all workers
	root_tmp_dir = tmp_path_factory.getbasetemp().parent

	# File that signals that test data has been created in the database
	fn = root_tmp_dir / "init.dummy"

	# Lock file for prevention concurrent checks
	ln = root_tmp_dir / "init.lock"

	with filelock.FileLock(ln):
		if fn.is_file():
			# Test data has alread been created => simply fetch it
			data = fetch_data()
		else:
			# Create test data
			data = create_data()
			# Record that test data has been created
			fn.write_text("done")
	return data
