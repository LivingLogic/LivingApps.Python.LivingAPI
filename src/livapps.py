#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016/2017 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

import datetime, json, collections, ast

import requests, requests.exceptions # This requires :mod:`request`, which you can install with ``pip install requests``

from ll import misc, ul4on # This requires :mod:`ll-xist`, which you can install with ``pip install ll-xist==5.27``


__docformat__ = "reStructuredText"


###
### Helper functions and classes
###

def register(name):
	"""
	Shortcut for registering a LivingAPI class with the UL4ON machinery.
	"""
	def registration(cls):
		ul4on.register("de.livingapps.appdd." + name)(cls)
		return cls
	return registration


class attrdict(dict):
	"""
	A subclass of :class:`dict` that makes keys accessible as attributes.
	"""
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(key)

	def __dir__(self):
		"""
		This makes keys completeable in IPython.
		"""
		return set(dir(dict)) | set(self)


class attrodict(collections.OrderedDict):
	"""
	A subclass of :class:`collections.OrderedDict` that makes keys accessible
	as attributes.
	"""
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(key)

	def __dir__(self):
		"""
		This makes keys completeable in IPython.
		"""
		return set(dir(dict)) | set(self)


def makeattrs(value):
	"""
	Convert a :class:`dict` or a :class:`collections.OrderedDict` for convenient
	access to the attributes in code and interactive shell (lik IPython).

	If :obj:`value` is neither a :class:`dict` nor a
	:class:`collections.OrderedDict` it will be returned unchanged.
	"""

	if isinstance(value, collections.OrderedDict):
		value = attrodict(value)
	elif isinstance(value, dict):
		value = attrdict(value)
	return value


def raise_403(response):
	http_error_msg = "403 Client Error: Forbidden for url: {}".format(response.url)
	raise requests.exceptions.HTTPError(http_error_msg, response=response)


# Monkey patch :class:`ll.ul4on.Decoder` to fix a string deserialization bug

def _load(self, typecode):
	from ll import misc
	if typecode is None:
		typecode = self._nextchar()
	if typecode == "^":
		position = self._readint()
		return self._objects[position]
	elif typecode in "nN":
		if typecode == "N":
			self._loading(None)
		return None
	elif typecode in "bB":
		value = self.stream.read(1)
		if value == "T":
			value = True
		elif value == "F":
			value = False
		else:
			raise ValueError("broken UL4ON stream at position {self.stream.tell():,}: expected 'T' or 'F' for bool; got {!r}".format(value))
		if typecode == "B":
			self._loading(value)
		return value
	elif typecode in "iI":
		value = self._readint()
		if typecode == "I":
			self._loading(value)
		return value
	elif typecode in "fF":
		chars = []
		while True:
			c = self.stream.read(1)
			if c and not c.isspace():
				chars.append(c)
			else:
				value = float("".join(chars))
				break
		if typecode == "F":
			self._loading(value)
		return value
	elif typecode in "sS":
		delimiter = self.stream.read(1)
		if not delimiter:
			raise EOFError()
		buffer = [delimiter]
		while True:
			c = self.stream.read(1)
			if not c:
				raise EOFError()
			buffer.append(c)
			if c == delimiter:
				# Create a triple quoted string literal so that linefeeds in the string work
				value = ast.literal_eval("{0}{0}{1}{0}{0}".format(delimiter, ''.join(buffer)))
				break
			elif c == "\\":
				c2 = self.stream.read(1)
				if not c2:
					raise EOFError()
				buffer.append(c2)
		if typecode == "S":
			self._loading(value)
		return value
	elif typecode in "cC":
		from ll import color
		if typecode == "C":
			oldpos = self._beginfakeloading()
		r = self._load(None)
		g = self._load(None)
		b = self._load(None)
		a = self._load(None)
		value = color.Color(r, g, b, a)
		if typecode == "C":
			self._endfakeloading(oldpos, value)
		return value
	elif typecode in "zZ":
		if typecode == "Z":
			oldpos = self._beginfakeloading()
		year = self._load(None)
		month = self._load(None)
		day = self._load(None)
		hour = self._load(None)
		minute = self._load(None)
		second = self._load(None)
		microsecond = self._load(None)
		value = datetime.datetime(year, month, day, hour, minute, second, microsecond)
		if typecode == "Z":
			self._endfakeloading(oldpos, value)
		return value
	elif typecode in "rR":
		if typecode == "R":
			oldpos = self._beginfakeloading()
		start = self._load(None)
		stop = self._load(None)
		value = slice(start, stop)
		if typecode == "R":
			self._endfakeloading(oldpos, value)
		return value
	elif typecode in "tT":
		if typecode == "T":
			oldpos = self._beginfakeloading()
		days = self._load(None)
		seconds = self._load(None)
		microseconds = self._load(None)
		value = datetime.timedelta(days, seconds, microseconds)
		if typecode == "T":
			self._endfakeloading(oldpos, value)
		return value
	elif typecode in "mM":
		from ll import misc
		if typecode == "M":
			oldpos = self._beginfakeloading()
		months = self._load(None)
		value = misc.monthdelta(months)
		if typecode == "M":
			self._endfakeloading(oldpos, value)
		return value
	elif typecode in "lL":
		value = []
		if typecode == "L":
			self._loading(value)
		while True:
			typecode = self._nextchar()
			if typecode == "]":
				return value
			else:
				item = self._load(typecode)
				value.append(item)
	elif typecode in "dDeE":
		value = {} if typecode in "dD" else ul4on.ordereddict()
		if typecode in "DE":
			self._loading(value)
		while True:
			typecode = self._nextchar()
			if typecode == "}":
				return value
			else:
				key = self._load(typecode)
				if isinstance(key, str):
					if key in self._keycache:
						key = self._keycache[key]
					else:
						self._keycache[key] = key
				item = self._load(None)
				value[key] = item
	elif typecode in "yY":
		value = set()
		if typecode == "Y":
			self._loading(value)
		while True:
			typecode = self._nextchar()
			if typecode == "}":
				return value
			else:
				item = self._load(typecode)
				value.add(item)
	elif typecode in "oO":
		if typecode == "O":
			oldpos = self._beginfakeloading()
		name = self._load(None)
		cls = None
		if self.registry is not None:
			cls = self.registry.get(name)
		if cls is None:
			cls = ul4on._registry.get(name)
		if cls is None:
			raise TypeError("can't decode object of type {!r}".format(name))
		value = cls()
		if typecode == "O":
			self._endfakeloading(oldpos, value)
		value.ul4onload(self)
		typecode = self._nextchar()
		if typecode != ")":
			raise ValueError("broken UL4ON stream at position {:,}: object terminator ')' expected, got {!r}".format(self.stream.tell(), typecode))
		return value
	else:
		raise ValueError("broken UL4ON stream at position {:,}: unknown typecode {!r}".format(self.stream.tell(), typecode))

ul4on.Decoder._load = _load


###
### Core classes
###


class Base:
	pass


@register("globals")
class Globals(Base):
	ul4attrs = {"version", "platform", "user", "flashes"}

	def __init__(self, version=None, platform=None, user=None):
		self.version = version
		self.platform = platform
		self.user = user
		self.maxdbactions = None
		self.maxtemplateruntime = None
		self.flashes = []
		self.login = None # The login from which we've got the data (required for insert/update/delete methods)

	def __repr__(self):
		return "<{} version={!r} platform={!r} at {:#x}>".format(self.__class__.__qualname__, self.version, self.platform, id(self))

	def geo(self, lat=None, long=None, info=None):
		import geocoder # This requires the :mod:`geocoder` module, install with ``pip install geocoder`
		# Get coordinates from description (passed via keyword ``info``)
		if info is not None and lat is None and long is None:
			result = geocoder.google(info, language="de")
		# Get coordinates from description (passed positionally as ``lat``)
		elif lat is not None and long is None and info is None:
			result = geocoder.google(lat, language="de")
		# Get description from coordinates
		elif lat is not None and long is not None and info is None:
			result = geocoder.google([lat, long], method="reverse", language="de")
		else:
			raise TypeError("geo() requires either (lat, long) arguments or a (info) argument")
		return Geo(result.lat, result.lng, result.address)

	def ul4ondump2(self, encoder):
		encoder.dumpattr("version", self.version)
		encoder.dumpattr("platform", self.platform)
		encoder.dumpattr("user", self.user)
		encoder.dumpattr("maxdbactions", self.maxdbactions)
		encoder.dumpattr("maxtemplateruntime", self.maxtemplateruntime)
		encoder.dumpattr("flashes", self.flashes)

	def ul4ondump(self, encoder):
		encoder.dump(self.version)
		encoder.dump(self.platform)
		encoder.dump(self.user)
		encoder.dump(self.maxdbactions)
		encoder.dump(self.maxtemplateruntime)
		encoder.dump(self.flashes)

	def ul4onload2(self, decoder):
		attrs = {"version", "platform", "user", "maxdbactions", "maxtemplateruntime", "flashes"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.version = decoder.load()
		self.platform = decoder.load()
		self.user = decoder.load()
		self.maxdbactions = decoder.load()
		self.maxtemplateruntime = decoder.load()
		self.flashes = decoder.load()


@register("app")
class App(Base):
	ul4attrs = {"id", "globals", "name", "description", "language", "startlink", "iconlarge", "iconsmall", "owner", "controls", "records", "recordcount", "installation", "categories", "params", "views"}

	def __init__(self, id=None, globals=None, name=None, description=None, language=None, startlink=None, iconlarge=None, iconsmall=None, owner=None, controls=None, records=None, recordcount=None, installation=None, categories=None, params=None, views=None):
		self.id = id
		self.globals = globals
		self.name = name
		self.description = description
		self.language = language
		self.startlink = startlink
		self.iconlarge = iconlarge
		self.iconsmall = iconsmall
		self.owner = owner
		self.controls = controls
		self.records = records
		self.recordcount = recordcount
		self.installation = installation
		self.categories = categories
		self.params = params
		self.views = views

	def __repr__(self):
		return "<{} id={!r} name={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.name, id(self))

	def insert(self, **kwargs):
		return self.globals.login._insert(self, **kwargs)

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("globals", self.globals)
		encoder.dumpattr("name", self.name)
		encoder.dumpattr("description", self.description)
		encoder.dumpattr("language", self.language)
		encoder.dumpattr("startlink", self.startlink)
		encoder.dumpattr("iconlarge", self.iconlarge)
		encoder.dumpattr("iconsmall", self.iconsmall)
		encoder.dumpattr("owner", self.owner)
		encoder.dumpattr("controls", self.controls)
		encoder.dumpattr("records", self.records)
		encoder.dumpattr("recordcount", self.recordcount)
		encoder.dumpattr("installation", self.installation)
		encoder.dumpattr("categories", self.categories)
		encoder.dumpattr("params", self.params)
		encoder.dumpattr("views", self.views)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.globals)
		encoder.dump(self.name)
		encoder.dump(self.description)
		encoder.dump(self.language)
		encoder.dump(self.startlink)
		encoder.dump(self.iconlarge)
		encoder.dump(self.iconsmall)
		encoder.dump(self.owner)
		encoder.dump(self.controls)
		encoder.dump(self.records)
		encoder.dump(self.recordcount)
		encoder.dump(self.installation)
		encoder.dump(self.categories)
		encoder.dump(self.params)
		encoder.dump(self.views)

	def ul4onload2(self, decoder):
		attrs = {"id", "globals", "name", "description", "language", "startlink", "iconlarge", "iconsmall", "owner", "controls", "records", "recordcount", "installation", "categories", "params", "views"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				if key == "controls":
					value = makeattrs(value)
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.globals = decoder.load()
		self.name = decoder.load()
		self.description = decoder.load()
		self.language = decoder.load()
		self.startlink = decoder.load()
		self.iconlarge = decoder.load()
		self.iconsmall = decoder.load()
		self.owner = decoder.load()
		self.controls = makeattrs(decoder.load())
		self.records = decoder.load()
		self.recordcount = decoder.load()
		self.installation = decoder.load()
		self.categories = decoder.load()
		self.params = makeattrs(decoder.load())
		self.views = decoder.load()


@register("view")
class View(Base):
	ul4attrs = {"id", "name", "app", "order", "width", "height", "start", "end"}

	def __init__(self, id=None, name=None, app=None, order=None, width=None, height=None, start=None, end=None):
		self.id = id
		self.name = name
		self.app = app
		self.order = order
		self.width = width
		self.height = height
		self.start = start
		self.end = end

	def __repr__(self):
		return "<{} id={!r} name={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.name, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("name", self.name)
		encoder.dumpattr("app", self.app)
		encoder.dumpattr("order", self.order)
		encoder.dumpattr("width", self.width)
		encoder.dumpattr("height", self.height)
		encoder.dumpattr("start", self.start)
		encoder.dumpattr("end", self.end)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.name)
		encoder.dump(self.app)
		encoder.dump(self.order)
		encoder.dump(self.width)
		encoder.dump(self.height)
		encoder.dump(self.start)
		encoder.dump(self.end)

	def ul4onload2(self, decoder):
		attrs = {"id", "name", "app", "order", "width", "height", "start", "end"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.name = decoder.load()
		self.app = decoder.load()
		self.order = decoder.load()
		self.width = decoder.load()
		self.height = decoder.load()
		self.start = decoder.load()
		self.end = decoder.load()


@register("datasource")
class DataSource(Base):
	ul4attrs = {"id", "identifier", "app", "apps"}

	def __init__(self, id=None, identifier=None, app=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.app = app
		self.apps = apps

	def __repr__(self):
		return "<{} id={!r} identifier={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.identifier, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("identifier", self.identifier)
		encoder.dumpattr("app", self.app)
		encoder.dumpattr("apps", self.apps)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.identifier)
		encoder.dump(self.app)
		encoder.dump(self.apps)

	def ul4onload2(self, decoder):
		attrs = {"id", "identifier", "app", "apps"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.identifier = decoder.load()
		self.app = decoder.load()
		self.apps = decoder.load()


@register("lookupitem")
class LookupItem(Base):
	ul4attrs = {"key", "label"}

	def __init__(self, key=None, label=None):
		self.key = key
		self.label = label

	def __repr__(self):
		return "<{} key={!r} label={!r} at {:#x}>".format(self.__class__.__qualname__, self.key, self.label, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("key", self.key)
		encoder.dumpattr("label", self.label)

	def ul4ondump(self, encoder):
		encoder.dump(self.key)
		encoder.dump(self.label)

	def ul4onload2(self, decoder):
		attrs = {"key", "value"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.key = decoder.load()
		self.label = decoder.load()


class Control(Base):
	type = None
	subtype = None
	ul4attrs = {"id", "identifier", "app", "label", "type", "subtype", "priority", "order", "default"}

	def __init__(self, id=None, identifier=None, field=None, app=None, label=None, priority=None, order=None, default=None):
		self.id = id
		self.identifier = identifier
		self.field = field
		self.app = app
		self.label = label
		self.priority = priority
		self.order = order
		self.default = default

	def __repr__(self):
		return "<{} id={!r} identifier={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.identifier, id(self))

	def asjson(self, value):
		return value

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("identifier", self.identifier)
		encoder.dumpattr("field", self.field)
		encoder.dumpattr("app", self.app)
		encoder.dumpattr("label", self.label)
		encoder.dumpattr("priority", self.priority)
		encoder.dumpattr("order", self.order)
		encoder.dumpattr("default", self.default)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.identifier)
		encoder.dump(self.field)
		encoder.dump(self.app)
		encoder.dump(self.label)
		encoder.dump(self.priority)
		encoder.dump(self.order)
		encoder.dump(self.default)

	def ul4onload2(self, decoder):
		attrs = {"id", "identifier", "field", "app", "label", "priority", "order", "default"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.identifier = decoder.load()
		self.field = decoder.load()
		self.app = decoder.load()
		self.label = decoder.load()
		self.priority = decoder.load()
		self.order = decoder.load()
		self.default = decoder.load()


class StringControl(Control):
	type = "string"


@register("textcontrol")
class TextControl(StringControl):
	subtype = "text"


@register("urlcontrol")
class URLControl(StringControl):
	subtype = "url"


@register("emailcontrol")
class EmailControl(StringControl):
	subtype = "email"


@register("passwordcontrol")
class PasswordControl(StringControl):
	subtype = "password"


@register("telcontrol")
class TelControl(StringControl):
	subtype = "tel"


@register("textareacontrol")
class TextAreaControl(StringControl):
	subtype = "textarea"


@register("intcontrol")
class IntControl(Control):
	type = "int"


@register("numbercontrol")
class NumberControl(Control):
	type = "number"


@register("datecontrol")
class DateControl(Control):
	type = "date"
	subtype = "date"

	def asjson(self, value):
		if isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d")
		elif isinstance(value, datetime.datetime):
			value = value.strftime("%Y-%m-%d %H:%M:%S")
		return value


@register("datetimeminutecontrol")
class DatetimeMinuteControl(DateControl):
	subtype = "datetimeminute"

	def asjson(self, value):
		if isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d 00:00")
		elif isinstance(value, datetime.datetime):
			value = value.strftime("%Y-%m-%d %H:%M")
		return value


@register("datetimesecondcontrol")
class DatetimeSecondControl(DateControl):
	subtype = "datetimesecond"

	def asjson(self, value):
		if isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d 00:00:00")
		elif isinstance(value, datetime.datetime):
			value = value.strftime("%Y-%m-%d %H:%M:%S")
		return value


@register("boolcontrol")
class BoolControl(Control):
	type = "bool"


class LookupControl(Control):
	type = "lookup"

	ul4attrs = Control.ul4attrs.union({"lookupdata", "lookupapp", "lookupcontrols"})

	def __init__(self, id=None, identifier=None, app=None, label=None, order=None, default=None, lookupdata=None, lookupapp=None, lookupcontrols=None):
		super().__init__(id=id, identifier=identifier, app=app, label=label, order=order, default=default)
		self.lookupdata = lookupdata
		self.lookupapp = lookupapp
		self.lookupcontrols = lookupcontrols

	def asjson(self, value):
		if isinstance(value, LookupItem):
			value = value.key
		elif isinstance(value, Record):
			value = value.id
		return value

	def ul4ondump2(self, encoder):
		super().ul4ondump2(encoder)
		encoder.dumpattr("lookupdata", self.lookupdata)
		encoder.dumpattr("lookupapp", self.lookupapp)
		encoder.dumpattr("lookupcontrols", self.lookupcontrols)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.lookupdata)
		encoder.dump(self.lookupapp)
		encoder.dump(self.lookupcontrols)

	def ul4onload2(self, decoder):
		attrs = {"id", "identifier", "field", "app", "label", "priority", "order", "default", "lookupdata", "lookupapp", "Lookupcontrols"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		lookupdata = decoder.load()
		self.lookupdata = attrdict(lookupdata) if lookupdata is not None else None
		self.lookupapp = decoder.load()
		self.lookupcontrols = decoder.load()


@register("lookupselectcontrol")
class LookupSelectControl(LookupControl):
	subtype = "select"


@register("lookupradiocontrol")
class LookupRadioControl(LookupControl):
	subtype = "radio"


@register("lookupchoicecontrol")
class LookupChoiceControl(LookupControl):
	subtype = "choice"


class MultipleLookupControl(LookupControl):
	type = "multiplelookup"

	def asjson(self, value):
		if isinstance(value, LookupItem):
			value = [value.key]
		elif isinstance(value, Record):
			value = [value.id]
		elif isinstance(value, collections.Sequence):
			value = [self.asjson(item) for item in value]
		return value


@register("multiplelookupselectcontrol")
class MultipleLookupSelectControl(MultipleLookupControl):
	subtype = "select"


@register("multiplelookupcheckboxcontrol")
class MultipleLookupCheckboxControl(MultipleLookupControl):
	subtype = "checkbox"


@register("filecontrol")
class FileControl(Control):
	type = "file"

	def asjson(self, value):
		if value is not None:
			raise NotImplementedError
		return value


@register("geocontrol")
class GeoControl(Control):
	type = "geo"

	def asjson(self, value):
		if isinstance(value, Geo):
			value = "{!r}, {!r}, {}".format(value.lat, value.long, value.info)
		return value


@register("record")
class Record(Base):
	ul4attrs = {"id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "fields", "attachments"}

	def __init__(self, id=None, app=None, createdat=None, createdby=None, updatedat=None, updatedby=None, updatecount=None, values=None, fields=None, attachments=None):
		self.id = id
		self.app = app
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.updatecount = updatecount
		self.values = values
		self.fields = fields
		self.attachments = attachments

	def __repr__(self):
		attrs = " ".join("values.{}={!r}".format(identifier, value) for (identifier, value) in self.values.items() if self.app.controls[identifier].priority)
		return "<{} id={!r} {} at {:#x}>".format(self.__class__.__qualname__, self.id, attrs, id(self))

	def _repr_pretty_(self, p, cycle):
		prefix = "<{}.{}".format(self.__class__.__module__, self.__class__.__qualname__)
		suffix = "at {:#x}".format(id(self))

		if cycle:
			p.text("{} ... {}>".format(prefix, suffix))
		else:
			with p.group(4, prefix, ">"):
				p.breakable()
				p.text("id=")
				p.pretty(self.id)
				for (identifier, value) in self.values.items():
					if self.app.controls[identifier].priority:
						p.breakable()
						p.text("values.{}=".format(identifier))
						p.pretty(value)
				p.breakable()
				p.text(suffix)

	def update(self, **kwargs):
		self.app.globals.login._update(self, **kwargs)

	def delete(self):
		self.app.globals.login._delete(self)

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("app", self.app)
		encoder.dumpattr("createdat", self.createdat)
		encoder.dumpattr("createdby", self.createdby)
		encoder.dumpattr("updatedat", self.updatedat)
		encoder.dumpattr("updatedby", self.updatedby)
		encoder.dumpattr("updatecount", self.updatecount)
		fieldvalues = {identifier: value for (identifier, value) in self.values.items() if value is not None}
		encoder.dumpattr("fields", fieldvalues)
		encoder.dumpattr("attachments", self.attachments)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.app)
		encoder.dump(self.createdat)
		encoder.dump(self.createdby)
		encoder.dump(self.updatedat)
		encoder.dump(self.updatedby)
		encoder.dump(self.updatecount)
		fieldvalues = {identifier: value for (identifier, value) in self.values.items() if value is not None}
		encoder.dump(fieldvalues)
		encoder.dump(attachments)

	def ul4onload2(self, decoder):
		attrs = {"id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "fields", "attachments"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				if key == "fields":
					value = attrdict({identifier: Field(control, self, value.get(identifier, None)) for (identifier, control) in self.app.controls.items()})
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.app = decoder.load()
		self.createdat = decoder.load()
		self.createdby = decoder.load()
		self.updatedat = decoder.load()
		self.updatedby = decoder.load()
		self.updatecount = decoder.load()
		fieldvalues = decoder.load()
		self.values = ul4on.ordereddict()
		self.fields = ul4on.ordereddict()
		for (identifier, control) in self.app.controls.items():
			value = fieldvalues.get(identifier, None)
			self.values[identifier] = value
			self.fields[identifier] = Field(control, self, value)
		self.attachments = decoder.load()


class Field:
	ul4attrs = {"control", "record", "value", "errors", "enabled", "writable", "visible"}

	def __init__(self, control, record, value):
		self.control = control
		self.record = record
		self.orgvalue = value
		self.errors = []
		self.enabled = True
		self.writable = True
		self.visible = True

	@property
	def value(self):
		return self.record.values[self.control.identifier]

	def __repr__(self):
		return "<{} identifier={!r} value={!r} at {:#x}>".format(self.__class__.__qualname__, self.control.identifier, self.value, id(self))


@register("attachment")
class Attachment:
	ul4attrs = {"id", "type", "record", "label", "active"}

	def __init__(self, id=None, record=None, label=None, active=None):
		self.id = id
		self.record = record
		self.label = label
		self.active = active

	def __repr__(self):
		return "<{} id={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("record", self.record)
		encoder.dumpattr("label", self.label)
		encoder.dumpattr("active", self.active)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.record)
		encoder.dump(self.label)
		encoder.dump(self.active)

	def ul4onload2(self, decoder):
		attrs = {"id", "record", "label", "active"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.record = decoder.load()
		self.label = decoder.load()
		self.active = decoder.load()


@register("file")
class File(Base):
	ul4attrs = {"id", "url", "filename", "mimetype", "width", "height"}

	def __init__(self, id=None, url=None, filename=None, mimetype=None, width=None, height=None):
		self.id = id
		self.url = url
		self.filename = filename
		self.mimetype = mimetype
		self.width = width
		self.height = height

	def __repr__(self):
		return "<{} id={!r} url={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.url, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("url", self.url)
		encoder.dumpattr("filename", self.filename)
		encoder.dumpattr("mimetype", self.mimetype)
		encoder.dumpattr("width", self.width)
		encoder.dumpattr("height", self.height)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.url)
		encoder.dump(self.filename)
		encoder.dump(self.mimetype)
		encoder.dump(self.width)
		encoder.dump(self.height)

	def ul4onload2(self, decoder):
		attrs = {"id", "url", "filename", "mimetype", "width", "height"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.url = decoder.load()
		self.filename = decoder.load()
		self.mimetype = decoder.load()
		self.width = decoder.load()
		self.height = decoder.load()


@register("geo")
class Geo(Base):
	ul4attrs = {"lat", "long", "info"}

	def __init__(self, lat=None, long=None, info=None):
		self.lat = lat
		self.long = long
		self.info = info

	def __repr__(self):
		return "<{} lat={!r} long={!r} info={!r} at {:#x}>".format(self.__class__.__qualname__, self.lat, self.long, self.info, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("lat", self.lat)
		encoder.dumpattr("long", self.long)
		encoder.dumpattr("info", self.info)

	def ul4ondump(self, encoder):
		encoder.dump(self.lat)
		encoder.dump(self.long)
		encoder.dump(self.info)

	def ul4onload2(self, decoder):
		attrs = {"lat", "long", "info"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.lat = decoder.load()
		self.long = decoder.load()
		self.info = decoder.load()


@register("user")
class User(Base):
	ul4attrs = {"id", "gender", "firstname", "surname", "initials", "email", "language", "avatar_small", "avatar_large", "keyviews"}

	def __init__(self, _id=None, id=None, gender=None, firstname=None, surname=None, initials=None, email=None, language=None, avatar_small=None, avatar_large=None, keyviews=None):
		self._id = _id
		self.id = id
		self.gender = gender
		self.firstname = firstname
		self.surname = surname
		self.initials = initials
		self.email = email
		self.language = language
		self.avatar_small = avatar_small
		self.avatar_large = avatar_large
		self.keyviews = keyviews

	def __repr__(self):
		return "<{} id={!r} firstname={!r} surname={!r} email={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.firstname, self.surname, self.email, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self._id)
		encoder.dumpattr("public_id", self.id)
		encoder.dumpattr("gender", self.gender)
		encoder.dumpattr("firstname", self.firstname)
		encoder.dumpattr("surname", self.surname)
		encoder.dumpattr("initials", self.initials)
		encoder.dumpattr("email", self.email)
		encoder.dumpattr("language", self.language)
		encoder.dumpattr("avatar_small", self.avatar_small)
		encoder.dumpattr("avatar_large", self.avatar_large)
		encoder.dumpattr("keyviews", self.keyviews)

	def ul4ondump(self, encoder):
		encoder.dump(self._id)
		encoder.dump(self.id)
		encoder.dump(self.gender)
		encoder.dump(self.firstname)
		encoder.dump(self.surname)
		encoder.dump(self.initials)
		encoder.dump(self.email)
		encoder.dump(self.language)
		encoder.dump(self.avatar_small)
		encoder.dump(self.avatar_large)
		encoder.dump(self.keyviews)

	def ul4onload2(self, decoder):
		attrs = {"id", "public_id", "gender", "firstname", "surname", "initials", "email", "language", "avatar_small", "avatar_large", "keyviews"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				if key == "id":
					key = "_id"
				elif key == "public_id":
					key = "id"
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self._id = decoder.load()
		self.id = decoder.load()
		self.gender = decoder.load()
		self.firstname = decoder.load()
		self.surname = decoder.load()
		self.initials = decoder.load()
		self.email = decoder.load()
		self.language = decoder.load()
		self.avatar_small = decoder.load()
		self.avatar_large = decoder.load()
		self.keyviews = decoder.load()


@register("category")
class Category(Base):
	ul4attrs = {"id", "identifier", "name", "order", "parent", "children", "apps"}

	def __init__(self, id=None, identifier=None, name=None, order=None, parent=None, children=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.order = order
		self.parent = parent
		self.children = children
		self.apps = apps

	def __repr__(self):
		return "<{} id={!r} identifier={!r} name={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.identifier, self.name, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("identifier", self.identifier)
		encoder.dumpattr("name", self.name)
		encoder.dumpattr("order", self.order)
		encoder.dumpattr("parent", self.parent)
		encoder.dumpattr("children", self.children)
		encoder.dumpattr("apps", self.apps)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.identifier)
		encoder.dump(self.name)
		encoder.dump(self.order)
		encoder.dump(self.parent)
		encoder.dump(self.children)
		encoder.dump(self.apps)

	def ul4onload2(self, decoder):
		attrs = {"id", "identifier", "name", "order", "parent", "children", "apps"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.identifier = decoder.load()
		self.name = decoder.load()
		self.order = decoder.load()
		self.parent = decoder.load()
		self.children = decoder.load()
		self.apps = decoder.load()


@register("keyview")
class KeyView(Base):
	ul4attrs = {"id", "identifier", "name", "key", "user"}

	def __init__(self, id=None, identifier=None, name=None, key=None, user=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.key = key
		self.user = user

	def __repr__(self):
		return "<{} id={!r} identifier={!r} name={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.identifier, self.name, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("identifier", self.identifier)
		encoder.dumpattr("name", self.name)
		encoder.dumpattr("key", self.key)
		encoder.dumpattr("user", self.user)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.identifier)
		encoder.dump(self.name)
		encoder.dump(self.key)
		encoder.dump(self.user)

	def ul4onload2(self, decoder):
		attrs = {"id", "identifier", "name", "key", "user"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.identifier = decoder.load()
		self.name = decoder.load()
		self.key = decoder.load()
		self.user = decoder.load()


@register("appparameter")
class AppParameter(Base):
	ul4attrs = {"id", "app", "identifier", "description", "value"}

	def __init__(self, id=None, app=None, identifier=None, description=None, value=None):
		self.id = id
		self.app = app
		self.identifier = identifier
		self.description = description
		self.value = value

	def __repr__(self):
		return "<{} id={!r} identifier={!r} at {:#x}>".format(self.__class__.__qualname__, self.id, self.identifier, id(self))

	def ul4ondump2(self, encoder):
		encoder.dumpattr("id", self.id)
		encoder.dumpattr("app", self.app)
		encoder.dumpattr("identifier", self.identifier)
		encoder.dumpattr("description", self.description)
		encoder.dumpattr("value", self.value)

	def ul4ondump(self, encoder):
		encoder.dump(self.id)
		encoder.dump(self.app)
		encoder.dump(self.identifier)
		encoder.dump(self.description)
		encoder.dump(self.value)

	def ul4onload2(self, decoder):
		attrs = {"id", "app", "identifier", "description", "value"}
		for attr in attrs:
			setattr(self, attr, None)
		for (key, value) in decoder.loadattrs():
			if key in attrs:
				setattr(self, key, value)

	def ul4onload(self, decoder):
		self.id = decoder.load()
		self.app = decoder.load()
		self.identifier = decoder.load()
		self.description = decoder.load()
		self.value = decoder.load()


class Login:
	def __init__(self, url, username=None, password=None):
		if not url.endswith("/"):
			url += "/"
		self.url = url
		self.username = username
		self.password = password

		self.session = requests.Session()

		self.cookies = {}
		# If :obj:`username` or :obj:`password` are not given, we don't log in
		# This means we can only fetch data for public templates, i.e. those that are marked as "for all users"
		if username is not None and password is not None:
			# Login to the LivingApps installation and store the cookie we get
			r = self.session.post(
				self.url + "login.htm",
				data={
					"cugUsername": username,
					"cugPassword": password,
					"com.livinglogic.cms.apps.cug.model.ClosedUserGroupLoginDisplayPreparer.loginFormSubmit": "true"
				},
			)

			# If we're still on the login page, raise a "Forbidden" error
			if "formError" in r.text:
				raise_403(r)

			for h in r.history:
				if "XIST4CSESSIONID" in h.cookies:
					self.cookies = h.cookies
					break

	def __repr__(self):
		return "<{} url={!r} username={!r} at {:#x}>".format(self.__class__.__qualname__, self.url, self.username, id(self))

	def get(self, appid, templatename=None):
		kwargs = {
			"cookies": self.cookies,
			"headers": {"Accept": "application/la-ul4on"},
		}
		if templatename is not None:
			kwargs["params"] = {"template": templatename}
		r = self.session.get("{}gateway/apps/{}".format(self.url, appid), **kwargs)
		r.raise_for_status()
		# Workaround: If we're not logged in, but request a protected template, we get redirected to the login page instead -> raise a 403 error instead
		if not self.cookies and r.history:
			raise_403(r)
		dump = ul4on.loads(r.text)
		globals = dump["globals"]
		globals.login = self
		datasources = attrdict(misc.first(dump["viewtemplates"].values())["datasources"])
		return attrdict(
			globals=globals,
			datasources=datasources,
		)

	def _insert(self, app, **kwargs):
		fields = {}
		for (identifier, value) in kwargs.items():
			if identifier not in app.controls:
				raise TypeError("insert() got an unexpected keyword argument {!r}".format(identifier))
			control = app.controls[identifier]
			fields[identifier] = control.asjson(value)
		data = dict(id=app.id, data=[{"fields": fields}])
		r = self.session.post(
			"{}gateway/v1/appdd/{}.json".format(self.url, app.id),
			data={"appdd": json.dumps(data)},
			cookies=self.cookies,
		)
		# Workaround: The Content-Type should be ``application/json``, but isn't
		# if r.headers["Content-Type"] != "application/json":
		# 	raise TypeError("bad Content-Type")
		# result = r.json()
		result = json.loads(r.text)
		if result["status"] != "ok":
			raise TypeError("Response status {!r}".format(result['status']))
		record = Record(
			id=result["id"],
			app=app,
			createdat=datetime.datetime.now(),
			createdby=app.globals.user,
			updatedat=None,
			updatedby=None,
			updatecount=0
		)
		record.values = attrdict()
		record.fields = attrdict()
		for (identifier, control) in app.controls.items():
			value = kwargs.get(identifier, None)
			if value is None and isinstance(control, MultipleLookupControl):
				value = []
			record.values[identifier] = value
			record.fields[identifier] = Field(control, record, value)
		return record

	def _update(self, record, **kwargs):
		fields = {}
		app = record.app
		for (identifier, value) in kwargs.items():
			if identifier not in app.controls:
				raise TypeError("update() got an unexpected keyword argument {!r}".format(identifier))
			control = app.controls[identifier]
			fields[identifier] = control.asjson(value)
		data = dict(id=app.id, data=[{"id": record.id, "fields": fields}])
		r = self.session.post(
			"{}gateway/v1/appdd/{}.json".format(self.url, app.id),
			data={"appdd": json.dumps(data)},
			cookies=self.cookies,
		)
		# Workaround: The Content-Type should be ``application/json``, but isn't
		# if r.headers["Content-Type"] != "application/json":
		# 	raise TypeError("bad Content-Type")
		# result = r.json()
		result = json.loads(r.text)
		if result["status"] != "ok":
			raise TypeError("Response status {!r}".format(result['status']))
		record.updatedat = datetime.datetime.now()
		record.updatedby = app.globals.user
		record.updatecount += 1
		for (identifier, control) in kwargs.items():
			record.values[identifier] = value

	def _delete(self, record):
		r = self.session.delete(
			"{}gateway/v1/appdd/{}/{}.json".format(self.url, record.app.id, record.id),
			cookies=self.cookies,
		)
		if r.text != '"Successfully deleted dataset"':
			raise TypeError("Unexpectedd response {!r}".format(r.text))
