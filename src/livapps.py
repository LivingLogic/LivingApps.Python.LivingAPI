#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2018 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

import sys, datetime, json, collections, ast, enum

import requests, requests.exceptions # This requires :mod:`request`, which you can install with ``pip install requests``

from ll import misc, ul4on # This requires :mod:`ll-xist`, which you can install with ``pip install ll-xist``


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


def makeattrs(value):
	"""
	Convert a :class:`dict` for convenient access to the attributes in code and
	interactive shell (like IPython).

	If :obj:`value` is not a :class:`dict` it will be returned unchanged.
	"""

	if isinstance(value, dict):
		value = attrdict(value)
	return value


def raise_403(response):
	"""
	Raise an HTTP exception with the status code 403 (i.e. "Forbidden").

	(This is used if the HTTP interface would redirect us to a different page,
	which we don't want).
	"""
	http_error_msg = f"403 Client Error: Forbidden for url: {response.url}"
	raise requests.exceptions.HTTPError(http_error_msg, response=response)


def error_wrong_type(value):
	return f"{misc.format_class(value)} is not supported"


def error_lookupitem_unknown(value):
	return f"Lookup item {value!r} is unknown"


def error_lookupitem_foreign(value):
	return f"Wrong lookup item {value!r}"


def error_applookuprecord_unknown(value):
	return f"Unknown record {value!r}"


def error_applookuprecord_foreign(value):
	return f"{value!r} is from wrong app"


###
### Core classes
###


class Base:
	ul4onattrs = []

	def ul4ondump(self, encoder):
		for name in self.ul4onattrs:
			value = self.ul4ondump_getattr(name)
			encoder.dump(value)

	def ul4ondump_getattr(self, name):
		return getattr(self, name)

	def ul4onload(self, decoder):
		names = iter(self.ul4onattrs)
		dump = decoder.loadcontent()

		# Load all attributes that we get from the UL4ON dump
		# Stop when the dump is exhausted or we've loaded all known attributes.
		for (name, value) in zip(names, dump):
			self.ul4onload_setattr(name, value)

		# Exhaust the UL4ON dump
		for value in dump:
			pass

		# Initialize the rest of the attributes with default values
		for name in names:
			self.ul4onload_setdefaultattr(name)

	def ul4onload_setattr(self, name, value):
		setattr(self, name, value)

	def ul4onload_setdefaultattr(self, name):
		setattr(self, name, None)


@register("globals")
class Globals(Base):
	ul4attrs = {"version", "platform", "user", "flashes", "geo"}
	ul4onattrs = ["version", "platform", "user", "maxdbactions", "maxtemplateruntime", "flashes"]

	def __init__(self, version=None, platform=None, user=None):
		self.version = version
		self.platform = platform
		self.user = user
		self.maxdbactions = None
		self.maxtemplateruntime = None
		self.flashes = []
		self.login = None # The login from which we've got the data (required for insert/update/delete/executeaction methods)

	def __repr__(self):
		return f"<{self.__class__.__qualname__} version={self.version!r} platform={self.platform!r} at {id(self):#x}>"

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

	def ul4onload_setdefaultattr(self, name):
		if name == "flashes":
			self.flashes = []
		else:
			setattr(self, name, None)


@register("app")
class App(Base):
	ul4attrs = {"id", "globals", "name", "description", "language", "startlink", "iconlarge", "iconsmall", "owner", "controls", "records", "recordcount", "installation", "categories", "params", "views", "datamanagement_identifier", "basetable", "primarykey", "insertprocedure", "updateprocedure", "deleteprocedure", "templates"}
	ul4onattrs = ["id", "globals", "name", "description", "language", "startlink", "iconlarge", "iconsmall", "owner", "controls", "records", "recordcount", "installation", "categories", "params", "views", "datamanagement_identifier", "basetable", "primarykey", "insertprocedure", "updateprocedure", "deleteprocedure", "templates"]

	def __init__(self, id=None, globals=None, name=None, description=None, language=None, startlink=None, iconlarge=None, iconsmall=None, owner=None, controls=None, records=None, recordcount=None, installation=None, categories=None, params=None, views=None, datamanagement_identifier=None):
		self.id = id
		self.globals = globals
		self.name = name
		self.description = description
		self.language = language
		self.startlink = startlink
		self.iconlarge = iconlarge
		self.iconsmall = iconsmall
		self.owner = owner
		self.templates = None
		self.controls = controls
		self.records = records
		self.recordcount = recordcount
		self.installation = installation
		self.categories = categories
		self.params = params
		self.views = views
		self.datamanagement_identifier = datamanagement_identifier
		self.basetable = None
		self.primarykey = None
		self.insertprocedure = None
		self.updateprocedure = None
		self.deleteprocedure = None

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} name={self.name!r} at {id(self):#x}>"

	def __getattr__(self, name):
		try:
			if name.startswith("c_"):
				return self.controls[name[2:]]
		except KeyError:
			pass
		raise AttributeError(name) from None

	def insert(self, **kwargs):
		return self.globals.handler._insert(self, **kwargs)

	def __call__(self, **kwargs):
		record = Record(app=self)
		for (identifier, value) in kwargs.items():
			if identifier not in self.controls:
				raise TypeError(f"app_{self.id}() got an unexpected keyword argument {identifier!r}")
			field = record.fields[identifier]
			field.value = value
			field.is_dirty = False # The record is dirty anyway
		return record

	def ul4onload_setattr(self, name, value):
		if name in {"controls", "params"}:
			value = makeattrs(value)
		setattr(self, name, value)

	def ul4onload_setdefaultattr(self, name):
		value = attrdict() if name in {"controls"} else None
		setattr(self, name, value)


@register("installation")
class Installation(Base):
	ul4attrs = {"id", "name"}
	ul4onattrs = ["id", "name"]

	def __init__(self, id=None, name=None):
		self.id = id
		self.name = name

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} name={self.name!r} at {id(self):#x}>"


@register("view")
class View(Base):
	ul4attrs = {"id", "name", "app", "order", "width", "height", "start", "end"}
	ul4onattrs = ["id", "name", "app", "order", "width", "height", "start", "end"]

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
		return f"<{self.__class__.__qualname__} id={self.id!r} name={self.name!r} at {id(self):#x}>"


@register("datasource")
class DataSource(Base):
	ul4attrs = {"id", "identifier", "app", "apps"}
	ul4onattrs = ["id", "identifier", "app", "apps"]

	def __init__(self, id=None, identifier=None, app=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.app = app
		self.apps = apps

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} at {id(self):#x}>"

	def ul4onload_setdefaultattr(self, name):
		value = {} if name == "apps" else None
		setattr(self, name, value)


@register("lookupitem")
class LookupItem(Base):
	ul4attrs = {"key", "label"}
	ul4onattrs = ["key", "label"]

	def __init__(self, key=None, label=None):
		self.key = key
		self.label = label

	def __repr__(self):
		return f"<{self.__class__.__qualname__} key={self.key!r} label={self.label!r} at {id(self):#x}>"


class Control(Base):
	type = None
	subtype = None
	ul4attrs = {"id", "identifier", "app", "label", "type", "subtype", "priority", "order", "default", "ininsertprocedure", "inupdateprocedure"}
	ul4onattrs = ["id", "identifier", "field", "app", "label", "priority", "order", "default", "ininsertprocedure", "inupdateprocedure"]

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
		return f"<{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} at {id(self):#x}>"

	def _convertvalue(self, value):
		return (value, None)

	def _asjson(self, value):
		return value


class StringControl(Control):
	type = "string"

	def _convertvalue(self, value):
		error = None
		if value is not None and not isinstance(value, str):
			error = error_wrong_type(value)
			value = None
		return (value, error)


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


class EncryptionType(enum.IntEnum):
	NONE = 0
	FORCE = 1
	OPTIONAL = 2


@register("textareacontrol")
class TextAreaControl(StringControl):
	subtype = "textarea"
	ul4attrs = StringControl.ul4attrs.union({"encrypted"})
	ul4onattrs = StringControl.ul4onattrs + ["encrypted"]

	def ul4onload_setattr(self, name, value):
		if name == "encrypted":
			try:
				value = EncryptionType(value)
			except ValueError:
				pass
			self.encrypted = value
		else:
			super().ul4onload_setattr(name, value)

	def ul4onload_setdefaultattr(self, name):
		if name == "encrypted":
			self.encrypted = EncryptionType.NONE
		else:
			return super().ul4onload_defaultattr(name)


@register("intcontrol")
class IntControl(Control):
	type = "int"

	def _convertvalue(self, value):
		error = None
		if value is not None and not isinstance(value, int):
			error = error_wrong_type(value)
			value = None
		return (value, error)


@register("numbercontrol")
class NumberControl(Control):
	type = "number"

	def _convertvalue(self, value):
		error = None
		if value is not None and not isinstance(value, (int, float)):
			error = error_wrong_type(value)
			value = None
		return (value, error)


@register("datecontrol")
class DateControl(Control):
	type = "date"
	subtype = "date"

	def _convertvalue(self, value):
		error = None
		if isinstance(value, datetime.datetime):
			value = value.date()
		elif value is None or isinstance(value, datetime.date):
			pass
		else:
			error = error_wrong_type(value)
			value = None
		return (value, error)

	def _asjson(self, value):
		if isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d")
		return value


@register("datetimeminutecontrol")
class DatetimeMinuteControl(DateControl):
	subtype = "datetimeminute"

	def _convertvalue(self, value):
		error = None
		if value is None:
			pass
		elif isinstance(value, datetime.datetime):
			value = value.replace(second=0, microsecond=0)
		elif isinstance(value, datetime.date):
			value = datetime.datetime.combine(value, datetime.time())
		else:
			error = error_wrong_type(value)
			value = None
		return (value, error)

	def _asjson(self, value):
		if isinstance(value, datetime.datetime):
			value = value.strftime("%Y-%m-%d %H:%M")
		return value


@register("datetimesecondcontrol")
class DatetimeSecondControl(DateControl):
	subtype = "datetimesecond"

	def _convertvalue(self, value):
		error = None
		if value is None:
			pass
		elif isinstance(value, datetime.datetime):
			value = value.replace(microsecond=0)
		elif isinstance(value, datetime.date):
			value = datetime.datetime.combine(value, datetime.time())
		else:
			error = error_wrong_type(value)
			value = None
		return (value, error)

	def _asjson(self, value):
		if isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d 00:00:00")
		elif isinstance(value, datetime.datetime):
			value = value.strftime("%Y-%m-%d %H:%M:%S")
		return value


@register("boolcontrol")
class BoolControl(Control):
	type = "bool"

	def _convertvalue(self, value):
		error = None
		if value is not None and not isinstance(value, bool):
			error = error_wrong_type(value)
			value = None
		return (value, error)


class LookupControl(Control):
	type = "lookup"

	ul4attrs = Control.ul4attrs.union({"lookupdata"})
	ul4onattrs = Control.ul4onattrs + ["lookupdata"]

	def __init__(self, id=None, identifier=None, app=None, label=None, order=None, default=None, lookupdata=None):
		super().__init__(id=id, identifier=identifier, app=app, label=label, order=order, default=default)
		self.lookupdata = lookupdata

	def _convertvalue(self, value):
		error = None
		if value is None:
			pass
		elif isinstance(value, str):
			if value in self.lookupdata:
				value = self.lookupdata[value]
			else:
				error = error_lookupitem_unknown(value)
				value = None
		elif isinstance(value, LookupItem):
			if value.key not in self.lookupdata or self.lookupdata[value.key] is not value:
				error = error_lookupitem_foreign(value)
				value = None
		else:
			error = error_wrong_type(value)
			value = None
		return (value, error)

	def _asjson(self, value):
		if isinstance(value, LookupItem):
			value = value.key
		return value

	def ul4onload_setattr(self, name, value):
		if name == "lookupdata":
			self.lookupdata = makeattrs(value)
		else:
			super().ul4onload_setattr(name, value)

	def ul4onload_setdefaultattr(self, name):
		if name == "lookupdata":
			self.lookupdata = attrdict()
		else:
			return super().ul4onload_defaultattr(name)


@register("lookupselectcontrol")
class LookupSelectControl(LookupControl):
	subtype = "select"


@register("lookupradiocontrol")
class LookupRadioControl(LookupControl):
	subtype = "radio"


@register("lookupchoicecontrol")
class LookupChoiceControl(LookupControl):
	subtype = "choice"


class AppLookupControl(Control):
	type = "applookup"

	ul4attrs = Control.ul4attrs.union({"lookupapp", "lookupcontrols"})
	ul4onattrs = Control.ul4onattrs + ["lookupapp", "lookupcontrols"]

	def __init__(self, id=None, identifier=None, app=None, label=None, order=None, default=None, lookupapp=None, lookupcontrols=None):
		super().__init__(id=id, identifier=identifier, app=app, label=label, order=order, default=default)
		self.lookupapp = lookupapp
		self.lookupcontrols = lookupcontrols

	def _convertvalue(self, value):
		error = None
		if value is None:
			pass
		elif isinstance(value, str):
			if self.lookupapp.records and value in self.lookupapp.records:
				value = self.lookupapp.records[value]
			else:
				error = error_applookuprecord_unknown(value)
				value = None
		elif isinstance(value, Record):
			if value.app is not self.lookupapp:
				error = error_applookuprecord_foreign(value)
				value = None
		else:
			error = error_wrong_type(value)
			value = None
		return (value, error)

	def _asjson(self, value):
		if value is not None:
			if value.id is None:
				raise ValueError(f"Referenced record {value!r} hasn't been saved yet!")
			elif value.is_deleted:
				raise ValueError(f"Referenced record {value!r} has been deleted!")
			value = value.id
		return value

	def ul4onload_setattr(self, name, value):
		if name == "lookupcontrols":
			self.lookupcontrols = makeattrs(value)
		else:
			super().ul4onload_setattr(name, value)

	def ul4onload_setdefaultattr(self, name):
		if name == "lookupcontrols":
			self.lookupcontrols = attrdict()
		else:
			super().ul4onload_setdefaultattr(name)


@register("applookupselectcontrol")
class AppLookupSelectControl(AppLookupControl):
	subtype = "select"


@register("applookupradiocontrol")
class AppLookupRadioControl(AppLookupControl):
	subtype = "radio"


@register("applookupchoicecontrol")
class AppLookupChoiceControl(AppLookupControl):
	subtype = "choice"


class MultipleLookupControl(LookupControl):
	type = "multiplelookup"

	def _convertvalue(self, value):
		error = None
		if value is None:
			pass
		elif isinstance(value, (str, LookupItem)):
			(value, error) = super()._convertvalue(value)
			if error:
				value = []
			else:
				value = [value]
		elif isinstance(value, list):
			realvalue = []
			allerrors = []
			for v in value:
				(v, error) = super()._convertvalue(v)
				if error:
					allerrors.append(error)
				else:
					realvalue.append(v)
			error = allerrors
			value = realvalue
		else:
			error = error_wrong_type(value)
			value = []
		return (value, error)

	def _asjson(self, value):
		return [item.key for item in value]


@register("multiplelookupselectcontrol")
class MultipleLookupSelectControl(MultipleLookupControl):
	subtype = "select"


@register("multiplelookupcheckboxcontrol")
class MultipleLookupCheckboxControl(MultipleLookupControl):
	subtype = "checkbox"


@register("multiplelookupchoicecontrol")
class MultipleLookupChoiceControl(MultipleLookupControl):
	subtype = "choice"


class MultipleAppLookupControl(AppLookupControl):
	type = "multipleapplookup"

	def _convertvalue(self, value):
		error = None
		if value is None:
			pass
		elif isinstance(value, (str, Record)):
			(value, error) = super()._convertvalue(value)
			if error:
				value = []
			else:
				value = [value]
		elif isinstance(value, list):
			realvalue = []
			allerrors = []
			for v in value:
				(v, error) = super()._convertvalue(v)
				if error:
					allerrors.append(error)
				else:
					realvalue.append(v)
			error = allerrors
			value = realvalue
		else:
			error = error_wrong_type(value)
			value = []
		return (value, error)

	def _asjson(self, value):
		newvalue = []
		for item in value:
			if item.id is None:
				raise ValueError(f"Referenced record {item!r} hasn't been saved yet!")
			elif item.is_deleted:
				raise ValueError(f"Referenced record {item!r} has been deleted!")
			newvalue.append(item)
		return newvalue


@register("multipleapplookupselectcontrol")
class MultipleAppLookupSelectControl(MultipleAppLookupControl):
	subtype = "select"


@register("multipleapplookupcheckboxcontrol")
class MultipleAppLookupCheckboxControl(MultipleAppLookupControl):
	subtype = "checkbox"


@register("multipleapplookupchoicecontrol")
class MultipleAppLookupChoiceControl(MultipleAppLookupControl):
	subtype = "choice"


@register("filecontrol")
class FileControl(Control):
	type = "file"

	def _convertvalue(self, value):
		error = None
		if value is not None and not isinstance(value, File):
			error = error_wrong_type(value)
			value = None
		return (value, error)

	def _asjson(self, value):
		if value is not None:
			raise NotImplementedError
		return value


@register("geocontrol")
class GeoControl(Control):
	type = "geo"

	def _convertvalue(self, value):
		error = None
		if value is not None and not isinstance(value, Geo):
			error = error_wrong_type(value)
			value = None
		return (value, error)

	def _asjson(self, value):
		if isinstance(value, Geo):
			value = f"{value.lat!r}, {value.long!r}, {value.info}"
		return value


@register("record")
class Record(Base):
	ul4attrs = {"id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "fields", "children", "attachments", "errors", "has_errors"}
	ul4onattrs = ["id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "values", "attachments", "children"]

	def __init__(self, id=None, app=None, createdat=None, createdby=None, updatedat=None, updatedby=None, updatecount=None):
		self.id = id
		self.app = app
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.updatecount = updatecount
		self._sparsevalues = attrdict()
		self._values = None
		self._fields = None
		self.children = attrdict()
		self.attachments = None
		self.errors = []
		self.is_deleted = False

	def __repr__(self):
		attrs = " ".join(f"v_{identifier}={value!r}" for (identifier, value) in self.values.items() if self.app.controls[identifier].priority)
		return f"<{self.__class__.__qualname__} id={self.id!r} {attrs} at {id(self):#x}>"

	def _repr_pretty_(self, p, cycle):
		prefix = f"<{self.__class__.__module__}.{self.__class__.__qualname__}"
		suffix = f"at {id(self):#x}"

		if cycle:
			p.text(f"{prefix} ... {suffix}>")
		else:
			with p.group(4, prefix, ">"):
				p.breakable()
				p.text("id=")
				p.pretty(self.id)
				for (identifier, value) in self.values.items():
					if self.app.controls[identifier].priority:
						p.breakable()
						p.text(f"v_{identifier}=")
						p.pretty(value)
				p.breakable()
				p.text(suffix)

	def __getattr__(self, name):
		try:
			if name.startswith("c_"):
				return self.children[name[2:]]
			elif name.startswith("f_"):
				return self.fields[name[2:]]
			elif name.startswith("v_"):
				return self.values[name[2:]]
			elif name == "fields":
				return self.__class__.fields.__get__(self)
			elif name == "values":
				return self.__class__.values.__get__(self)
		except KeyError:
			pass
		raise AttributeError(name) from None

	def __setattr__(self, name, value):
		try:
			if name.startswith("v_"):
				self.fields[name[2:]].value = value
				return
		except KeyError:
			pass
		else:
			super().__setattr__(name, value)
			return
		raise TypeError(f"can't set attribute {name!r}")

	def __dir__(self):
		"""
		This makes keys completeable in IPython.
		"""
		return set(super().__dir__()) | {f"f_{identifier}" for identifier in self.app.controls} | {f"v_{identifier}" for identifier in self.app.controls} | {f"c_{identifier}" for identifier in self.children}

	@property
	def is_dirty(self):
		return self.id is None or any(field.is_dirty for field in self.fields.values())

	@property
	def values(self):
		if self._values is None:
			self._values = attrdict((identifier, self._sparsevalues.get(identifier)) for identifier in self.app.controls)
			self._sparsevalues = None
		return self._values

	@property
	def fields(self):
		if self._fields is None:
			values = self.values
			self._fields = attrdict((identifier, Field(self.app.controls[identifier], self, values[identifier])) for identifier in self.app.controls)
		return self._fields

	def save(self):
		self.app.globals.handler._save(self)

	def update(self, **kwargs):
		self.app.globals.handler._update(self, **kwargs)

	def delete(self):
		self.app.globals.handler._delete(self)

	def executeaction(self, actionidentifier):
		self.app.globals.handler._executeaction(self, actionidentifier)

	@property
	def has_errors(self):
		return bool(self.errors) or any(field.has_errors for field in self.fields.values())

	def ul4ondump_getattr(self, name):
		if name == "values":
			if self._sparsevalues is not None:
				return self._sparsevalues
			else:
				return {identifier: value for (identifier, value) in self.values.items() if value is not None}
		else:
			return getattr(self, name)

	def ul4onload_setattr(self, name, value):
		if name == "values":
			self._sparsevalues = value
			self._values = None
			self._fields = None
		elif name == "children":
			self.children = makeattrs(value)
		else:
			setattr(self, name, value)

	def ul4onload_setdefaultattr(self, name, value):
		if name == "values":
			self._sparsevalues = {}
			self._values = None
			self._fields = None
		elif name == "children":
			self.children = attrdict()
		else:
			setattr(self, name, value)


class Field:
	ul4attrs = {"control", "record", "value", "is_dirty", "errors", "has_errors", "enabled", "writable", "visible"}

	def __init__(self, control, record, value):
		self.control = control
		self.record = record
		self._value = value
		self.is_dirty = False
		self.errors = []
		self.enabled = True
		self.writable = True
		self.visible = True

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, value):
		oldvalue = self._value
		(value, error) = self.control._convertvalue(value)
		if error:
			self._value = self.record.values[self.control.identifier] = value
			self.is_dirty = True
			if not isinstance(error, list):
				error = [error]
			self.errors = error
		else:
			if value != oldvalue:
				self._value = self.record.values[self.control.identifier] = value
				self.is_dirty = True

	@property
	def is_empty(self):
		return self.value is None or (isinstance(self.value, list) and not value)

	@property
	def has_errors(self):
		return bool(self.errors)

	def __repr__(self):
		s = f"<{self.__class__.__qualname__} identifier={self.control.identifier!r} value={self.value!r}"
		if self.is_dirty:
			s += " is_dirty=True"
		if self.errors:
			s += " has_errors=True"
		s += f" at {id(self):#x}>"
		return s


class Attachment(Base):
	ul4attrs = {"id", "type", "record", "label", "active"}
	ul4onattrs = ["id", "record", "label", "active"]

	def __init__(self, id=None, record=None, label=None, active=None):
		self.id = id
		self.record = record
		self.label = label
		self.active = active

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} at {id(self):#x}>"


@register("imageattachment")
class ImageAttachment(Attachment):
	ul4attrs = Attachment.ul4attrs.union({"original", "thumb", "small", "medium", "large"})
	ul4onattrs = Attachment.ul4onattrs + ["original", "thumb", "small", "medium", "large"]
	type = "imageattachment"

	def __init__(self, id=None, record=None, label=None, active=None, original=None, thumb=None, small=None, medium=None, large=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.original = original
		self.thumb = thumb
		self.small = small
		self.medium = medium
		self.large = large


class SimpleAttachment(Attachment):
	ul4attrs = Attachment.ul4attrs.union({"value"})
	ul4onattrs = Attachment.ul4onattrs + ["value"]

	def __init__(self, id=None, record=None, label=None, active=None, value=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.value = value


@register("fileattachment")
class FileAttachment(SimpleAttachment):
	type = "fileattachment"


@register("urlattachment")
class URLAttachment(SimpleAttachment):
	type = "urlattachment"


@register("noteattachment")
class NoteAttachment(SimpleAttachment):
	type = "noteattachment"


@register("jsonattachment")
class JSONAttachment(SimpleAttachment):
	type = "jsonattachment"

	def ul4onload_setattr(self, name, value):
		if name == "value":
			value = json.parse(value)
		super().ul4onload_setattr(name, value)


@register("file")
class File(Base):
	ul4attrs = {"id", "url", "filename", "mimetype", "width", "height"}
	ul4onattrs = ["id", "url", "filename", "mimetype", "width", "height"]

	def __init__(self, id=None, url=None, filename=None, mimetype=None, width=None, height=None):
		self.id = id
		self.url = url
		self.filename = filename
		self.mimetype = mimetype
		self.width = width
		self.height = height

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} url={self.url!r} at {id(self):#x}>"


@register("geo")
class Geo(Base):
	ul4attrs = {"lat", "long", "info"}
	ul4onattrs = ["lat", "long", "info"]

	def __init__(self, lat=None, long=None, info=None):
		self.lat = lat
		self.long = long
		self.info = info

	def __repr__(self):
		return f"<{self.__class__.__qualname__} lat={self.lat!r} long={self.long!r} info={self.info!r} at {id(self):#x}>"


@register("user")
class User(Base):
	ul4attrs = {"id", "gender", "firstname", "surname", "initials", "email", "language", "avatar_small", "avatar_large", "keyviews"}
	ul4onattrs = ["_id", "id", "gender", "firstname", "surname", "initials", "email", "language", "avatar_small", "avatar_large", "keyviews"]

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
		return f"<{self.__class__.__qualname__} id={self.id!r} firstname={self.firstname!r} surname={self.surname!r} email={self.email!r} at {id(self):#x}>"


@register("category")
class Category(Base):
	ul4attrs = {"id", "identifier", "name", "order", "parent", "children", "apps"}
	ul4onattrs = ["id", "identifier", "name", "order", "parent", "children", "apps"]

	def __init__(self, id=None, identifier=None, name=None, order=None, parent=None, children=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.order = order
		self.parent = parent
		self.children = children
		self.apps = apps

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} name={self.name!r} at {id(self):#x}>"


@register("keyview")
class KeyView(Base):
	ul4attrs = {"id", "identifier", "name", "key", "user"}
	ul4onattrs = ["id", "identifier", "name", "key", "user"]

	def __init__(self, id=None, identifier=None, name=None, key=None, user=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.key = key
		self.user = user

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} name={self.name!r} at {id(self):#x}>"


@register("appparameter")
class AppParameter(Base):
	ul4attrs = {"id", "app", "identifier", "description", "value"}
	ul4onattrs = ["id", "app", "identifier", "description", "value"]

	def __init__(self, id=None, app=None, identifier=None, description=None, value=None):
		self.id = id
		self.app = app
		self.identifier = identifier
		self.description = description
		self.value = value

	def __repr__(self):
		return f"<{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} at {id(self):#x}>"


###
### Handler classes
###

class Handler:
	"""
	A :class:`Handler` object is responsible for handling communication with
	the LivingApps backend system.

	This can either be direct communication via a database interface
	(not implemented) yet or communication via an HTTP interface
	(see :class:`HTTPHandler`).
	"""
	def file(self, file):
		pass

	def get(self, appid, template=None, **params):
		pass

	def _save(self, record):
		pass

	def _insert(self, app, **kwargs):
		record = Record(
			id=None,
			app=app,
			createdat=datetime.datetime.now(),
			createdby=app.globals.user,
			updatedat=None,
			updatedby=None,
			updatecount=0
		)

		for (identifier, value) in kwargs.items():
			if identifier not in app.controls:
				raise TypeError(f"insert() got an unexpected keyword argument {identifier!r}")
			record.fields[identifier].value = value
		self._save(record)
		return record

	def _update(self, record, **kwargs):
		app = record.app
		for (identifier, value) in kwargs.items():
			if identifier not in app.controls:
				raise TypeError(f"update() got an unexpected keyword argument {identifier!r}")
			record.fields[identifier].value = value
		self._save(record)

	def _delete(self, record):
		pass

	def _executeaction(self, record, actionidentifier):
		pass


class HTTPHandler(Handler):
	def __init__(self, url, username=None, password=None):
		if not url.endswith("/"):
			url += "/"
		self.url = url
		self.username = username

		self.session = requests.Session()

		self.auth_token = None

		# If :obj:`username` or :obj:`password` are not given, we don't log in
		# This means we can only fetch data for public templates, i.e. those that are marked as "for all users"
		if username is not None and password is not None:
			# Login to the LivingApps installation and store the auth token we get
			r = self.session.post(
				self.url + "gateway/login",
				data=json.dumps({"username": username, "password": password}),
			)
			result = r.json()
			if result.get("status") == "success":
				self.auth_token = result["auth_token"]
			else:
				raise_403(r)

	def __repr__(self):
		return f"<{self.__class__.__qualname__} url={self.url!r} username={self.username!r} at {id(self):#x}>"

	def _add_auth_token(self, kwargs):
		if self.auth_token:
			if "headers" not in kwargs:
				kwargs["headers"] = {}
			kwargs["headers"]["X-La-Auth-Token"] = self.auth_token

	def file(self, file):
		kwargs = {}
		self._add_auth_token(kwargs)
		r = self.session.get(
			self.url.rstrip("/") + file.url,
			**kwargs,
		)
		return r.content

	def get(self, appid, template=None, **params):
		kwargs = {
			"headers": {
				"Accept": "application/la-ul4on",
			},
			"params": params,
		}
		self._add_auth_token(kwargs)
		if template is not None:
			kwargs["params"]["template"] = template
		r = self.session.get(
			f"{self.url}gateway/apps/{appid}",
			**kwargs,
		)
		r.raise_for_status()
		# Workaround: If we're not logged in, but request a protected template,
		# we get redirected to the login page
		# -> raise a 403 error instead
		if self.auth_token is None and r.history:
			raise_403(r)
		dump = ul4on.loads(r.content.decode("utf-8"))
		dump = attrdict(dump)
		dump.globals.handler = self
		dump.datasources = attrdict(dump.datasources)
		return dump

	def _save(self, record):
		fields = {field.control.identifier : field.control._asjson(field.value) for field in record.fields.values() if record.id is None or field.is_dirty}
		app = record.app
		recorddata = {"fields": fields}
		if record.id is not None:
			recorddata["id"] = record.id
		data = dict(id=app.id, data=[recorddata])
		kwargs = {
			"data": json.dumps({"appdd": data}),
			"headers": {
				"Content-Type": "application/json",
			},
		}
		self._add_auth_token(kwargs)
		r = self.session.post(
			f"{self.url}gateway/v1/appdd/{app.id}.json",
			**kwargs,
		)
		r.raise_for_status()
		result = json.loads(r.text)
		status = result["status"]
		if status != "ok":
			raise TypeError(f"Response status {status!r}")
		if record.id is None:
			record.id = result["id"]
			record.createdat = datetime.datetime.now()
			record.createdby = app.globals.user
			record.updatecount = 0
		else:
			record.updatedat = datetime.datetime.now()
			record.updatedby = app.globals.user
			record.updatecount += 1
		for field in record.fields.values():
			field.is_dirty = False
			field.errors = []
		record.errors = []

	def _delete(self, record):
		kwargs = {}
		self._add_auth_token(kwargs)

		r = self.session.delete(
			f"{self.url}gateway/v1/appdd/{record.app.id}/{record.id}.json",
			**kwargs,
		)
		r.raise_for_status()
		if r.text != '"Successfully deleted dataset"':
			raise TypeError(f"Unexpected response {r.text!r}")
		record.is_deleted = True

	def _executeaction(self, record, actionidentifier):
		kwargs = {
			"data": {"recid": record.id},
		}
		self._add_auth_token(kwargs)

		r = self.session.post(
			f"{self.url}gateway/api/v1/apps/{record.app.id}/actions/{actionidentifier}",
			**kwargs,
		)
		r.raise_for_status()
