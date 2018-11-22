import os, datetime

import pytest

from ll import ul4c, url as url_

import livapps


###
### Data and helper functions
###

testappid = "5bf3f8b2b7d9a84b7a9a4476"


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
	Return the account name of the user that should be used for connecting
	to LivingApps.
	"""
	return os.environ["LA_LIVINGAPI_TEST_USER"]


def passwd():
	return os.environ["LA_LIVINGAPI_TEST_PASSWD"]


###
### Testing classes
###

class PythonDBHandler:
	def __init__(self, **params):
		self.handler = livapps.DBHandler(
			connect(),
			uploaddir(),
			user(),
		)
		self.vars = self.handler.get(testappid, **params)

	def render(self, template):
		template = ul4c.Template(template)
		result = template.renders(**self.vars)
		self.handler.commit()
		return result



class PythonHTTPHandler:
	def __init__(self, **params):
		self.handler = livapps.HTTPHandler(
			url(),
			user(),
			passwd(),
		)
		self.vars = self.handler.get(testappid, **params)

	def render(self, template):
		template = ul4c.Template(template)
		result = template.renders(**self.vars)
		return result


all_handlers = dict(
	python_db=PythonDBHandler,
	python_http=PythonHTTPHandler,
)


###
### Test fixtures
###

@pytest.fixture(scope="module", params=all_handlers.keys())
def H(request):
	"""
	A parameterized fixture that returns each of the testing classes
	:class:`PythonDBHandler` and :class:`PythonHTTPHandler`.
	"""
	return all_handlers[request.param]


@pytest.fixture(scope="function")
def norecords():
	"""
	A test fixture that ensures that both test apps contain no records.
	"""
	handler = livapps.DBHandler(connect(), uploaddir(), user())
	vars = handler.get(testappid, template="export")

	personen_app = vars.datasources.personen.app
	taetigkeitsfelder_app = vars.datasources.taetigkeitsfelder.app

	# Remove all person records
	for r in personen_app.records.values():
		r.delete()


	# Recursively remove areas of activity
	def removeaa(r):
		for r2 in r.c_kinder.values():
			removeaa(r2)
		r.delete()

	for r in taetigkeitsfelder_app.records.values():
		if r.v_uebergeordnetes_taetigkeitsfeld is None:
			removeaa(r)

	handler.commit()
	return attrdict(handler=handler)


@pytest.fixture(scope="function")
def arearecords(norecords):
	"""
	A fixture that creates the records in the "area of activity" app.
	"""
	attrs = norecords
	attrs.vars = attrs.handler.get(testappid, template="export")

	taetigkeitsfelder_app = attrs.vars.datasources.taetigkeitsfelder.app

	attrs.areas = attrdict()

	def aa(**values):
		aa = taetigkeitsfelder_app(**values)
		aa.save()
		print(f"Created and saved area of activity: {aa.v_name}")
		return aa

	attrs.areas.wissenschaft = aa(name="Wissenschaft")
	attrs.areas.mathematik = aa(name="Mathematik", uebergeordnetes_taetigkeitsfeld=attrs.areas.wissenschaft)
	attrs.areas.physik = aa(name="Physik", uebergeordnetes_taetigkeitsfeld=attrs.areas.wissenschaft)
	attrs.areas.kunst = aa(name="Kunst")
	attrs.areas.film = aa(name="Film", uebergeordnetes_taetigkeitsfeld=attrs.areas.kunst)
	attrs.areas.musik = aa(name="Musik", uebergeordnetes_taetigkeitsfeld=attrs.areas.kunst)
	attrs.areas.literatur = aa(name="Literatur", uebergeordnetes_taetigkeitsfeld=attrs.areas.kunst)
	attrs.areas.politik = aa(name="Politik")
	attrs.areas.wirtschaft = aa(name="Wirtschaft")
	attrs.areas.sport = aa(name="Sport")

	attrs.handler.commit()

	return attrs


@pytest.fixture(scope="function")
def personrecords(arearecords):
	"""
	A fixture that creates the records in the "persons" app (after making sure
	we have records in the "area of activity" app).
	"""
	attrs = arearecords
	ps = []

	personen_app = attrs.vars.datasources.personen.app

	def p(**values):
		p = personen_app(**values)
		if p.v_portrait is not None and p.v_portrait.id is None:
			p.v_portrait.save()
		p.save()
		print(f"Created and saved person: {p.v_vorname} {p.v_nachname}")
		return p

	def u(u):
		return attrs.handler.file(url_.URL(u))

	ae = p(
		vorname="Albert",
		nachname="Einstein",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.physik],
		geburtstag=datetime.date(1879, 3, 14),
		todestag=datetime.date(1955, 4, 15),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Einstein_1921_portrait2.jpg/330px-Einstein_1921_portrait2.jpg"),
	)

	mc = p(
		vorname="Marie",
		nachname="Curie",
		geschlecht=personen_app.c_geschlecht.lookupdata.weiblich,
		taetigkeitsfeld=[attrs.areas.physik],
		geburtstag=datetime.date(1867, 11, 7),
		todestag=datetime.date(1934, 7, 4),
	)

	ma = p(
		vorname="Muhammad",
		nachname="Ali",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.sport],
		geburtstag=datetime.date(1942, 1, 17),
		todestag=datetime.date(2016, 6, 3),
	)

	mm = p(
		vorname="Marilyn",
		nachname="Monroe",
		geschlecht=personen_app.c_geschlecht.lookupdata.weiblich,
		taetigkeitsfeld=[attrs.areas.film],
		geburtstag=datetime.date(1926, 6, 1),
		todestag=datetime.date(1962, 8, 4),
	)

	ep = p(
		vorname="Elvis",
		nachname="Presley",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.musik],
		geburtstag=datetime.date(1935, 1, 8),
		todestag=datetime.date(1977, 8, 16),
	)

	br = p(
		vorname="Bernhard",
		nachname="Riemann",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.mathematik],
		geburtstag=datetime.date(1826, 6, 17),
		todestag=datetime.date(1866, 6, 20),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/BernhardRiemannAWeger.jpg/330px-BernhardRiemannAWeger.jpg"),
	)

	cfg = p(
		vorname="Carl Friedrich",
		nachname="Gauß",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.mathematik],
		geburtstag=datetime.date(1777, 4, 30),
		todestag=datetime.date(1855, 2, 23),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Carl_Friedrich_Gauss.jpg/255px-Carl_Friedrich_Gauss.jpg"),
	)

	rr = p(
		vorname="Ronald",
		nachname="Reagan",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.film, attrs.areas.politik],
		geburtstag=datetime.date(1911, 2, 6),
		todestag=datetime.date(2004, 6, 5),
	)

	attrs.handler.commit()
	return attrs


###
### Tests
###

def test_user(H):
	h = H(template="export")

	u = user()

	# Check that the logged in user is the user we"ve used to log in
	assert u == h.render("<?print globals.user.email?>")

	# Check that the account name is part of the user ``repr`` output
	assert f" email='{u}'" in h.render("<?print repr(globals.user)?>")


def test_app(H):
	h = H(template="export")

	# Check that ``app`` is the correct one
	testappid == h.render("<?print app.id?>")
	"LA-Demo: Personen" == h.render("<?print app.name?>")


def test_datasources(H):
	h = H(template="export")

	# Check that the datasources have the identifiers we expect
	"personen;taetigkeitsfelder" == h.render("<?print ';'.join(sorted(datasources))?>")


def test_output_all_records(H, personrecords):
	h = H(template="export")

	# Simply output all records from all datasources
	# to see that we don"t get any exceptions
	h.render("""
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
	""")


def test_output_all_controls(H):
	h = H(template="export")

	# Simply output all controls from all apps
	# to see that we don"t get any exceptions
	h.render("""
		<?for ds in datasources.values()?>
			<?if ds.app is not None and ds.app.controls is not None?>
				<?for c in ds.app.controls.values()?>
					<?print repr(c)?>
				<?end for?>
			<?end if?>
		<?end for?>
	""")


def test_record_shortcutattributes(H, personrecords):
	h = H(template="export")

	# Find "Albert Einstein" and output his fields in multiple ways
	4 * "Albert" == h.render("""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code ae = first(r for r in papp.records.values() if r.v_nachname == "Einstein")?>
		<?print ae.fields.vorname.value?>
		<?print ae.f_vorname.value?>
		<?print ae.values.vorname?>
		<?print ae.v_vorname?>
	""")


def test_app_shortcutattributes(H):
	h = H(template="export")

	# Access a control and output its fields with in two ways
	2 * "vorname" == h.render("""
		<?whitespace strip?>
		<?print app.controls.vorname.identifier?>
		<?print app.c_vorname.identifier?>
	""")


def test_insert_record(H):
	h = H(template="export")

	h.render("""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code r = papp.insert(vorname="John", nachname="Doe")?>
	""")

	"John Doe" == h.render("""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code jd = first(r for r in papp.records.values() if r.v_vorname == "John" and r.v_nachname == "Doe")?>
		<?print r.v_vorname?> <?print r.v_nachname?>
	""")
