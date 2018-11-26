import sys, os, datetime, subprocess

import pytest

from ll import ul4c, url as url_, ul4on

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


class JavaDBHandler:
	def __init__(self, **params):
		self.params = params

	def findexception(self, output):
		lines = output.splitlines()
		msg = None
		exc = None
		lastexc = None
		for line in lines:
			prefix1 = 'Exception in thread "main"'
			prefix2 = "Caused by:"
			if line.startswith(prefix1):
				msg = line[len(prefix1):].strip()
			elif line.startswith(prefix2):
				msg = line[len(prefix2):].strip()
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

	def run(self, data):
		dump = ul4on.dumps(data).encode("utf-8")
		result = subprocess.run("java com.livinglogic.livingapi.Tester", input=dump, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
		# Check if we have an exception
		self.findexception(result.stderr.decode("utf-8", "passbytes"))
		return result.stdout.decode("utf-8", "passbytes")

	def render(self, template):
		template = ul4c.Template(template) # Just a syntax check
		(dbuserpassword, connectdescriptor) = connect().split("@", 1)
		(dbuser, dbpassword) = dbuserpassword.split("/")
		params = self.params
		if "template" in params:
			params = dict(params)
			del params["template"]
		data = dict(
			jdbcurl=f"jdbc:oracle:thin:@{connectdescriptor}",
			jdbcuser=dbuser,
			jdbcpassword=dbpassword,
			user=user(),
			appid=testappid,
			command="render",
			template=template.source,
			templateidentifier=self.params.get("template", None),
			params=params,
		)
		return self.run(data)


all_handlers = dict(
	python_db=PythonDBHandler,
	python_http=PythonHTTPHandler,
	java_db=JavaDBHandler,
)


###
### Test fixtures
###

@pytest.fixture(scope="module", params=all_handlers.keys())
def Handler(request):
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
	handler = livapps.DBHandler(connect(), uploaddir(), user())
	vars = handler.get(testappid, template="export")

	personen_app = vars.datasources.personen.app
	taetigkeitsfelder_app = vars.datasources.taetigkeitsfelder.app

	# Remove all persons
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


@pytest.fixture(scope="module")
def arearecords(norecords):
	"""
	A fixture that creates the records in the "area of activity" app (after
	removing all existing records).
	"""
	attrs = norecords
	attrs.vars = attrs.handler.get(testappid, template="export")

	taetigkeitsfelder_app = attrs.vars.datasources.taetigkeitsfelder.app

	attrs.areas = attrdict()

	def aa(**values):
		aa = taetigkeitsfelder_app(**values)
		aa.save()
		return aa

	attrs.areas.wissenschaft = aa(name="Wissenschaft")
	attrs.areas.mathematik = aa(name="Mathematik", uebergeordnetes_taetigkeitsfeld=attrs.areas.wissenschaft)
	attrs.areas.physik = aa(name="Physik", uebergeordnetes_taetigkeitsfeld=attrs.areas.wissenschaft)
	attrs.areas.informatik = aa(name="Informatik", uebergeordnetes_taetigkeitsfeld=attrs.areas.wissenschaft)
	attrs.areas.kunst = aa(name="Kunst")
	attrs.areas.film = aa(name="Film", uebergeordnetes_taetigkeitsfeld=attrs.areas.kunst)
	attrs.areas.musik = aa(name="Musik", uebergeordnetes_taetigkeitsfeld=attrs.areas.kunst)
	attrs.areas.literatur = aa(name="Literatur", uebergeordnetes_taetigkeitsfeld=attrs.areas.kunst)
	attrs.areas.politik = aa(name="Politik")
	attrs.areas.wirtschaft = aa(name="Wirtschaft")
	attrs.areas.sport = aa(name="Sport")

	attrs.handler.commit()

	return attrs


@pytest.fixture(scope="module")
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
		return p

	def u(u):
		return attrs.handler.file(url_.URL(u))

	def g(lat=None, long=None, info=None):
		return attrs.handler.geo(lat, long, info)

	ae = p(
		vorname="Albert",
		nachname="Einstein",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.physik],
		geburtstag=datetime.date(1879, 3, 14),
		todestag=datetime.date(1955, 4, 15),
		#grab=g(lat, long),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Einstein_1921_portrait2.jpg/330px-Einstein_1921_portrait2.jpg"),
	)

	mc = p(
		vorname="Marie",
		nachname="Curie",
		geschlecht=personen_app.c_geschlecht.lookupdata.weiblich,
		taetigkeitsfeld=[attrs.areas.physik],
		geburtstag=datetime.date(1867, 11, 7),
		todestag=datetime.date(1934, 7, 4),
		grab=g("Patheon Paris"),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Marie_Curie_%28Nobel-Chem%29.jpg/170px-Marie_Curie_%28Nobel-Chem%29.jpg"),
	)

	ma = p(
		vorname="Muhammad",
		nachname="Ali",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.sport],
		geburtstag=datetime.date(1942, 1, 17),
		todestag=datetime.date(2016, 6, 3),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Muhammad_Ali_NYWTS.jpg/200px-Muhammad_Ali_NYWTS.jpg"),
	)

	mm = p(
		vorname="Marilyn",
		nachname="Monroe",
		geschlecht=personen_app.c_geschlecht.lookupdata.weiblich,
		taetigkeitsfeld=[attrs.areas.film],
		geburtstag=datetime.date(1926, 6, 1),
		todestag=datetime.date(1962, 8, 4),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Marilyn_Monroe%2C_Korea%2C_1954_cropped.jpg/220px-Marilyn_Monroe%2C_Korea%2C_1954_cropped.jpg"),
	)

	ep = p(
		vorname="Elvis",
		nachname="Presley",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.musik],
		geburtstag=datetime.date(1935, 1, 8),
		todestag=datetime.date(1977, 8, 16),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Elvis_Presley_1970.jpg/170px-Elvis_Presley_1970.jpg"),
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

	dk = p(
		vorname="Donald",
		nachname="Knuth",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.informatik],
		geburtstag=datetime.date(1938, 1, 10),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/KnuthAtOpenContentAlliance.jpg/255px-KnuthAtOpenContentAlliance.jpg"),
	)

	rr = p(
		vorname="Ronald",
		nachname="Reagan",
		geschlecht=personen_app.c_geschlecht.lookupdata.maennlich,
		taetigkeitsfeld=[attrs.areas.film, attrs.areas.politik],
		geburtstag=datetime.date(1911, 2, 6),
		todestag=datetime.date(2004, 6, 5),
		portrait=u("https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Official_Portrait_of_President_Reagan_1981.jpg/220px-Official_Portrait_of_President_Reagan_1981.jpg"),
	)

	attrs.handler.commit()

	return attrs


###
### Tests
###

def test_user(Handler):
	h = Handler(template="export")

	u = user()

	# Check that the logged in user is the user we"ve used to log in
	assert u == h.render("<?print globals.user.email?>")

	# Check that the account name is part of the user ``repr`` output
	assert f" email='{u}'" in h.render("<?print repr(globals.user)?>")


def test_app(Handler):
	h = Handler(template="export")

	# Check that ``app`` is the correct one
	assert testappid == h.render("<?print app.id?>")
	assert "LA-Demo: Personen" == h.render("<?print app.name?>")


def test_datasources(Handler):
	h = Handler(template="export")

	# Check that the datasources have the identifiers we expect
	assert "personen;taetigkeitsfelder" == h.render("<?print ';'.join(sorted(datasources))?>")


def test_output_all_records(Handler, personrecords):
	h = Handler(template="export")

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


def test_output_all_controls(Handler):
	h = Handler(template="export")

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


def test_sort_default_order_is_newest_first(Handler, personrecords):
	h = Handler(template="export")

	# Check the the default sort order is descending by creation date
	assert not h.render("""
		<?whitespace strip?>
		<?code lastcreatedat = None?>
		<?for p in datasources.personen.app.records.values()?>
			<?if lastcreatedat is not None and lastcreatedat > p.createdat?>
				Bad: <?print lastcreatedat?> > <?print p.createdat?>
			<?end if?>
		<?end for?>
	""")


def test_record_shortcutattributes(Handler, personrecords):
	h = Handler(template="export")

	# Find "Albert Einstein" and output one of his fields in multiple ways
	assert "'Albert';'Albert';'Albert';'Albert'" == h.render("""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code ae = first(r for r in papp.records.values() if r.v_nachname == "Einstein")?>
		<?print repr(ae.fields.vorname.value)?>;
		<?print repr(ae.f_vorname.value)?>;
		<?print repr(ae.values.vorname)?>;
		<?print repr(ae.v_vorname)?>
	""")


def test_app_shortcutattributes(Handler):
	h = Handler(template="export")

	# Access a control and output its fields with in two ways
	assert "'vorname';'vorname'" == h.render("""
		<?whitespace strip?>
		<?print repr(app.controls.vorname.identifier)?>;
		<?print repr(app.c_vorname.identifier)?>
	""")


def test_insert_record(Handler, norecords):
	h = Handler(template="export")

	(output, id) = h.render("""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code r = papp.insert(vorname="Isaac", nachname="Newton")?>
		<?print repr(r.v_vorname)?> <?print repr(r.v_nachname)?>;
		<?print r.id?>
	""").split(";")

	assert "'Isaac' 'Newton'" == output

	h = Handler(template="export") # Refetch data
	assert "'Isaac' 'Newton'" == h.render(f"""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code r = papp.records['{id}']?>
		<?print repr(r.v_vorname)?> <?print repr(r.v_nachname)?>
	""")


def test_attributes_unsaved_record(Handler):
	h = Handler(template="export")

	# Check that ``id``, ``createdat`` and ``createdby`` will be set when the
	# new record is saved
	assert f"True True True;False False {user()}" == h.render("""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code r = papp(vorname="Isaac", nachname="Newton")?>
		<?print r.id is None?> <?print r.createdat is None?> <?print r.createdby is None?>
		<?code r.save()?>;
		<?print r.id is None?> <?print r.createdat is None?> <?print r.createdby.email?>
	""")

	h = Handler(template="export") # Refetch data

	# Check that ``updatedat`` and ``updatedby`` will be set when the
	# record is saved (this even happens when the record hasn't been changed
	# however in this case no value fields will be changed)
	assert f"True True;False {user()};False {user()}" == h.render("""
		<?whitespace strip?>
		<?code papp = datasources.personen.app?>
		<?code r = first(r for r in papp.records.values() if r.v_nachname == 'Newton')?>
		<?print r.updatedat is None?> <?print r.updatedby is None?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby.email?>
		<?code r.v_geburtstag = @(1642-12-25)?>
		<?code r.save()?>;
		<?print r.updatedat is None?> <?print r.updatedby.email?>
	""")


def template_unsorted_records(records, content):
	return f"""
		<?whitespace strip?>
		<?for (f, r) in isfirst({records})?>
			<?if not f?>;<?end if?>
			{content}
		<?end for?>
	"""


def template_sorted_records(records, content, sort):
	return f"""
		<?whitespace strip?>
		<?def key(r)?>
			<?return {sort}?>
		<?end def?>
		<?for (f, r) in isfirst(sorted({records}, key))?>
			<?if not f?>;<?end if?>
			{content}
		<?end for?>
	"""


template_unsorted_persons = template_unsorted_records(
	"datasources.personen.app.records.values()",
	"<?print r.v_vorname?> <?print r.v_nachname?>"
)

template_sorted_persons = template_sorted_records(
	"datasources.personen.app.records.values()",
	"<?print r.v_vorname?> <?print r.v_nachname?>",
	"r.v_nachname",
)

template_unsorted_children = template_unsorted_records(
	"datasources.taetigkeitsfelder.app.records[id].c_kinder.values()",
	"<?print r.v_name?>",
)

template_sorted_children = template_sorted_records(
	"datasources.taetigkeitsfelder.app.records[id].c_kinder.values()",
	"<?print r.v_name?>",
	"r.v_name",
)


def test_datasource_recordfilter(personrecords):
	h = PythonDBHandler(template="export_recordfilter")

	assert "Albert Einstein" == h.render(template_unsorted_persons)


def test_datasource_recordfilter_param_str(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_str", nachname="Curie")

	assert "Marie Curie" == h.render(template_unsorted_persons)


def test_datasource_recordfilter_param_int(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_int", jahr="1935")

	assert "Elvis Presley" == h.render(template_unsorted_persons)


def test_datasource_recordfilter_param_date(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_date", geburtstag="1926-06-01")

	assert "Marilyn Monroe" == h.render(template_unsorted_persons)


def test_datasource_recordfilter_param_datetime(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_datetime", geburtstag="1926-06-01T12:34:56")

	assert "Marilyn Monroe" == h.render(template_unsorted_persons)


def test_datasource_recordfilter_param_strlist(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_strlist", nachname=["Gauß", "Riemann"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == h.render(template_sorted_persons)


def test_datasource_recordfilter_param_intlist(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_intlist", jahr=["1826", "1777"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == h.render(template_sorted_persons)


def test_datasource_recordfilter_param_datelist(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_datelist", geburtstag=["1826-06-17", "1777-04-30"])

	assert "Carl Friedrich Gauß;Bernhard Riemann" == h.render(template_sorted_persons)


def test_datasource_recordfilter_param_datetimelist(personrecords):
	h = PythonDBHandler(template="export_recordfilter_param_datetimelist", geburtstag=["1777-04-30T12:34:56"])

	assert "Carl Friedrich Gauß" == h.render(template_sorted_persons)


def test_datasource_sort_asc_nullsfirst(personrecords):
	h = PythonDBHandler(template="export_sort_asc_nullsfirst")

	assert "Donald Knuth;Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein" == h.render(template_unsorted_persons)


def test_datasource_sort_asc_nullslast(personrecords):
	h = PythonDBHandler(template="export_sort_asc_nullslast")

	assert "Carl Friedrich Gauß;Bernhard Riemann;Albert Einstein;Donald Knuth" == h.render(template_unsorted_persons)


def test_datasource_sort_desc_nullsfirst(personrecords):
	h = PythonDBHandler(template="export_sort_desc_nullsfirst")

	assert "Donald Knuth;Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß" == h.render(template_unsorted_persons)


def test_datasource_sort_desc_nullslast(personrecords):
	h = PythonDBHandler(template="export_sort_desc_nullslast")

	assert "Albert Einstein;Bernhard Riemann;Carl Friedrich Gauß;Donald Knuth" == h.render(template_unsorted_persons)


def test_datasource_masterdetail_recordfilter(personrecords):
	h = PythonDBHandler(template="export_masterdetail_recordfilter")

	attrs = personrecords

	assert "True;Informatik;Mathematik;Physik;Literatur" == h.render(f"""
		<?whitespace strip?>
		<?print all(r.v_uebergeordnetes_taetigkeitsfeld is None for r in datasources.taetigkeitsfelder.app.records.values())?>
		<?for id in ['{attrs.areas.wissenschaft.id}', '{attrs.areas.kunst.id}']?>
			;{template_sorted_children}
		<?end for?>
	""")


def test_datasource_masterdetail_sort_asc(personrecords):
	h = PythonDBHandler(template="export_masterdetail_sort_asc")

	attrs = personrecords

	assert "True;Informatik;Mathematik;Physik;Film;Literatur;Musik" == h.render(f"""
		<?whitespace strip?>
		<?print all(r.v_uebergeordnetes_taetigkeitsfeld is None for r in datasources.taetigkeitsfelder.app.records.values())?>
		<?for id in ['{attrs.areas.wissenschaft.id}', '{attrs.areas.kunst.id}']?>
			;{template_unsorted_children}
		<?end for?>
	""")


def test_datasource_masterdetail_sort_desc(personrecords):
	h = PythonDBHandler(template="export_masterdetail_sort_desc")

	attrs = personrecords

	assert "True;Physik;Mathematik;Informatik;Musik;Literatur;Film" == h.render(f"""
		<?whitespace strip?>
		<?print all(r.v_uebergeordnetes_taetigkeitsfeld is None for r in datasources.taetigkeitsfelder.app.records.values())?>
		<?for id in ['{attrs.areas.wissenschaft.id}', '{attrs.areas.kunst.id}']?>
			;{template_unsorted_children}
		<?end for?>
	""")
