#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2018 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

import sys, os, os.path, io, datetime, json, collections, ast, enum, pathlib, mimetypes

import requests, requests.exceptions # This requires :mod:`request`, which you can install with ``pip install requests``

from ll import misc, url, ul4on # This requires :mod:`ll-xist`, which you can install with ``pip install ll-xist``

try:
	from ll import orasql
except ImportError:
	orasql = None

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
		ul4on.register("de.livinglogic.livingapi." + name)(cls)
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
### Exceptions
###

class UnsavedError(Exception):
	"""
	Exception that is thrown when an object is saved and this object references
	another object that hasn't been saved yet.
	"""


class UnsavedRecordError(UnsavedError):
	"""
	Subclass of :class:`UnsafedError` that is used for unsaved :class:`Record`
	objects.
	"""

	def __init__(self, record):
		self.record = record

	def __str__(self):
		return f"Referenced record {self.record!r} hasn't been saved yet!"


class UnsavedFileError(UnsavedError):
	"""
	Subclass of :class:`UnsafedError` that is used for unsaved :class:`File`
	objects.
	"""

	def __init__(self, file):
		self.file = file

	def __str__(self):
		return f"Referenced file {self.file!r} hasn't been saved yet!"


class DeletedRecordError(Exception):
	"""
	Exception that is thrown when a record is saved and this object references
	another record which has been deleted previously.
	"""

	def __init__(self, record):
		self.record = record

	def __str__(self):
		return f"Referenced record {self.record!r} has been deleted!"


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
		self.handler = None # The handler from which we've got the data (required for insert/update/delete/executeaction methods)

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} version={self.version!r} platform={self.platform!r} at {id(self):#x}>"

	def geo(self, lat=None, long=None, info=None):
		return self.handler.geo(lat, long, info)

	def ul4onload_setdefaultattr(self, name):
		if name == "flashes":
			self.flashes = []
		else:
			setattr(self, name, None)


@register("app")
class App(Base):
	ul4attrs = {"id", "globals", "name", "description", "language", "startlink", "iconlarge", "iconsmall", "owner", "controls", "records", "recordcount", "installation", "categories", "params", "views", "datamanagement_identifier", "basetable", "primarykey", "insertprocedure", "updateprocedure", "deleteprocedure", "templates", "insert"}
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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} name={self.name!r} at {id(self):#x}>"

	def __getattr__(self, name):
		try:
			if name.startswith("c_"):
				return self.controls[name[2:]]
		except KeyError:
			raise AttributeError(name) from None
		return super().__getattr__(name)

	def ul4getattr(self, name):
		if self.ul4hasattr(name):
			return getattr(self, name)
		raise AttributeError(name) from None

	def ul4hasattr(self, name):
		return name in self.ul4attrs or (name.startswith("c_") and name[2:] in self.controls)

	def insert(self, **kwargs):
		record = Record(
			id=None,
			app=self,
			createdat=None,
			createdby=None,
			updatedat=None,
			updatedby=None,
			updatecount=0
		)

		for (identifier, value) in kwargs.items():
			if identifier not in self.controls:
				raise TypeError(f"insert() got an unexpected keyword argument {identifier!r}")
			record.fields[identifier].value = value
		record.save()
		return record

		return self.globals.handler._insert(self, **kwargs)

	def __call__(self, **kwargs):
		record = Record(app=self)
		for (identifier, value) in kwargs.items():
			if identifier not in self.controls:
				raise TypeError(f"app_{self.id}() got an unexpected keyword argument {identifier!r}")
			field = record.fields[identifier]
			field.value = value
			field._dirty = False # The record is dirty anyway
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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} name={self.name!r} at {id(self):#x}>"


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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} name={self.name!r} at {id(self):#x}>"


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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} at {id(self):#x}>"

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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} key={self.key!r} label={self.label!r} at {id(self):#x}>"


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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} at {id(self):#x}>"

	def _convertvalue(self, value):
		return (value, None)

	def _asjson(self, value):
		return value

	def _asdbarg(self, value):
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

	def _asdbarg(self, value):
		if value is not None:
			value = int(value)
		return value


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

	def _asdbarg(self, value):
		return self._asjson(value)

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
				raise UnsavedRecordError(value)
			elif value._deleted:
				raise DeletedRecordError(value)
			value = value.id
		return value

	def _asdbarg(self, value):
		return self._asjson(value)

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
			value = []
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

	def _asdbarg(self, value):
		return self._asjson(value)


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
			value = []
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
				raise UnsavedRecordError(item)
			elif item._deleted:
				raise DeletedRecordError(item)
			newvalue.append(item.id)
		return newvalue

	def _asdbarg(self, value):
		value = self._asjson(value)
		return self.app.globals.handler.varchars(value)


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

	def _asdbarg(self, value):
		if value is not None:
			if value.internalid is None:
				raise UnsavedFileError(value)
			value = value.internalid
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
		if value is not None:
			value = f"{value.lat!r}, {value.long!r}, {value.info}"
		return value

	def _asdbarg(self, value):
		return self._asjson(value)


@register("record")
class Record(Base):
	ul4attrs = {"id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "fields", "values", "children", "attachments", "errors", "has_errors", "add_error", "clear_errors", "is_deleted", "save", "update"}
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
		self._deleted = False

	def __repr__(self):
		attrs = " ".join(f"v_{identifier}={value!r}" for (identifier, value) in self.values.items() if self.app.controls[identifier].priority)
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} {attrs} at {id(self):#x}>"

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

	def ul4getattr(self, name):
		if self.ul4hasattr(name):
			return getattr(self, name)
		raise AttributeError(name) from None

	def ul4hasattr(self, name):
		if name in self.ul4attrs:
			return True
		elif name.startswith(("f_", "v_")):
			return name[2:] in self.app.controls
		elif name.startswith("c_"):
			return name[2:] in self.children
		return False

	def ul4setattr(self, name, value):
		if name.startswith("v_") and name[2:] in self.app.controls:
			setattr(self, name, value)
		else:
			raise TypeError(f"can't set attribute {name!r}")

	def is_dirty(self):
		return self.id is None or any(field._dirty for field in self.fields.values())

	@property
	def values(self):
		if self._values is None:
			self._values = attrdict()
			for control in self.app.controls.values():
				value = self._sparsevalues.get(control.identifier)
				(value, _) = control._convertvalue(value)
				self._values[control.identifier] = value
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
		for (identifier, value) in kwargs.items():
			if identifier not in self.app.controls:
				raise TypeError(f"update() got an unexpected keyword argument {identifier!r}")
			self.fields[identifier].value = value
		self.save()

	def delete(self):
		self.app.globals.handler._delete(self)

	def executeaction(self, actionidentifier):
		self.app.globals.handler._executeaction(self, actionidentifier)

	def has_errors(self):
		return bool(self.errors) or any(field.has_errors for field in self.fields.values())

	def add_error(self, error):
		self.errors.append(error)

	def clear_errors(self):
		for field in self.fields.values():
			field.clear_errors()
		self.errors = []

	def is_deleted(self):
		return self._deleted

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
	ul4attrs = {"control", "record", "value", "is_dirty", "errors", "has_errors", "add_error", "clear_errors", "enabled", "writable", "visible"}

	def __init__(self, control, record, value):
		self.control = control
		self.record = record
		self._value = value
		self._dirty = False
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
			self._dirty = True
			if not isinstance(error, list):
				error = [error]
			self.errors = error
		else:
			if value != oldvalue:
				self._value = self.record.values[self.control.identifier] = value
				self._dirty = True

	def is_empty(self):
		return self.value is None or (isinstance(self.value, list) and not value)

	def is_dirty(self):
		return self._dirty

	def has_errors(self):
		return bool(self.errors)

	def add_error(self, error):
		self.errors.append(error)

	def clear_errors(self):
		self.errors = []

	def __repr__(self):
		s = f"<{self.__class__.__module__}.{self.__class__.__qualname__} identifier={self.control.identifier!r} value={self.value!r}"
		if self._dirty:
			s += " is_dirty()=True"
		if self.errors:
			s += " has_errors()=True"
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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} at {id(self):#x}>"


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
	ul4onattrs = ["id", "url", "filename", "mimetype", "width", "height", "internalid"]

	def __init__(self, id=None, url=None, filename=None, mimetype=None, width=None, height=None, internalid=None):
		self.id = id
		self.url = url
		self.filename = filename
		self.mimetype = mimetype
		self.width = width
		self.height = height
		self.internalid = internalid
		self.handler = None
		self._content = None

	def save(self):
		if self.internalid is None:
			if self.handler is None:
				raise ValueError(f"Can't save file {self!r}")
			self.handler._savefile(self)

	def content(self):
		"""
		Return the file content as a :class:`bytes` object.
		"""
		if self._content is not None:
			return self._content
		elif self.handler is None:
			raise ValueError(f"Can't load content of {self!r}")
		return self.handler._filecontent(self)

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} filename={self.filename!r} mimetype={self.mimetype!r} at {id(self):#x}>"


@register("geo")
class Geo(Base):
	ul4attrs = {"lat", "long", "info"}
	ul4onattrs = ["lat", "long", "info"]

	def __init__(self, lat=None, long=None, info=None):
		self.lat = lat
		self.long = long
		self.info = info

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} lat={self.lat!r} long={self.long!r} info={self.info!r} at {id(self):#x}>"


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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} firstname={self.firstname!r} surname={self.surname!r} email={self.email!r} at {id(self):#x}>"


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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} name={self.name!r} at {id(self):#x}>"


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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} name={self.name!r} at {id(self):#x}>"


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
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} identifier={self.identifier!r} at {id(self):#x}>"


###
### Handler classes
###

class Handler:
	"""
	A :class:`Handler` object is responsible for handling communication with
	the LivingApps backend system.

	This can either be direct communication via a database interface
	(see :class:`DBHandler`) or communication via an HTTP interface
	(see :class:`HTTPHandler`).
	"""
	def __init__(self):
		self.globals = None

	def get(self, appid, template=None, **params):
		pass

	def file(self, source):
		path = None
		stream = None
		mimetype = None
		if isinstance(source, pathlib.Path):
			content = source.read_bytes()
			filename = source.name
			path = source.resolve()
		if isinstance(source, str):
			with open(source, "rb") as f:
				content = f.read()
			filename = os.path.basename(source)
			path = source
		elif isinstance(source, os.PathLike):
			path = source.__fspath__()
			with open(path, "rb") as f:
				content = f.read()
			filename = os.path.basename(path)
		elif isinstance(source, url.URL):
			filename = source.file
			with source.openread() as r:
				content = r.read()
				stream = io.BytesIO(content)
		else:
			content = source.read()
			if source.name:
				filename = os.path.basename(source.name)
			else:
				filename = "Dummy"
			stream = source
		if mimetype is None:
			mimetype = mimetypes.guess_type(filename, strict=False)[0]
		file = File(filename=filename, mimetype=mimetype)
		if file.mimetype.startswith("image/"):
			from PIL import Image # This requires :mod:`Pillow`, which you can install with ``pip install pillow``
			if stream:
				stream.seek(0)
			with Image.open(path or stream) as img:
				file.width = img.size[0]
				file.height = img.size[1]
		file._content = content
		file.handler = self
		return file

	def _geofrominfo(self, info):
		import geocoder # This requires the :mod:`geocoder` module, install with ``pip install geocoder`
		for provider in (geocoder.google, geocoder.osm):
			result = provider(info, language="de")
			if not result.error and result.lat and result.lng and result.address:
				return Geo(result.lat, result.lng, result.address)

	def _geofromlatlong(self, lat, long):
		import geocoder # This requires the :mod:`geocoder` module, install with ``pip install geocoder`
		for provider in (geocoder.google, geocoder.osm):
			result = provider([lat, long], method="reverse", language="de")
			if not result.error and result.lat and result.lng and result.address:
				return Geo(result.lat, result.lng, result.address)

	def geo(self, lat=None, long=None, info=None):
		# Get coordinates from description (passed via keyword ``info``)
		if info is not None and lat is None and long is None:
			return self._geofrominfo(info)
		# Get coordinates from description (passed positionally as ``lat``)
		elif lat is not None and long is None and info is None:
			return self._geofrominfo(lat)
		# Get description from coordinates
		elif lat is not None and long is not None and info is None:
			return self._geofromlatlong(lat, long)
		else:
			raise TypeError("geo() requires either (lat, long) arguments or a (info) argument")

	def _save(self, record):
		raise NotImplementedError

	def _delete(self, record):
		raise NotImplementedError

	def _executeaction(self, record, actionidentifier):
		raise NotImplementedError

	def _filecontent(self, file):
		raise NotImplementedError

	def _savefile(self, file):
		raise NotImplementedError

	def _loadfile(self):
		file = File()
		file.handler = self
		return file

	def _loaddump(self, dump):
		registry = {
			"de.livingapps.appdd.file": self._loadfile,
			"de.livinglogic.livingapi.file": self._loadfile,
		}
		dump = ul4on.loads(dump, registry)
		dump = attrdict(dump)
		dump.globals.handler = self
		dump.datasources = attrdict(dump.datasources)
		return dump


class DBHandler(Handler):
	def __init__(self, connectstring, uploaddirectory, account):
		super().__init__()
		if orasql is None:
			raise ImportError("cx_Oracle required")
		self.db = orasql.connect(connectstring)
		self.uploaddirectory = url.URL(uploaddirectory)
		self.varchars = self.db.gettype("LL.VARCHARS")
		self.urlcontext = None

		# Procedures
		self.proc_data_insert = orasql.Procedure("LIVINGAPI_PKG.DATA_INSERT")
		self.proc_data_update = orasql.Procedure("LIVINGAPI_PKG.DATA_UPDATE")
		self.proc_data_delete = orasql.Procedure("LIVINGAPI_PKG.DATA_DELETE")
		self.proc_dataaction_execute = orasql.Procedure("LIVINGAPI_PKG.DATAACTION_EXECUTE")
		self.proc_upload_insert = orasql.Procedure("UPLOAD_PKG.UPLOAD_INSERT")
		self.custom_procs = {}

		if account is None:
			self.ide_id = None
		else:
			c = self.db.cursor()
			c.execute("select ide_id from identity where ide_account = :account", account=account)
			r = c.fetchone()
			if r is None:
				raise ValueError(f"no user {account!r}")
			self.ide_id = r.ide_id

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} connectstring={self.db.connectstring()!r} at {id(self):#x}>"

	def commit(self):
		self.db.commit()

	def _savefile(self, file):
		if file.internalid is None:
			if file._content is None:
				raise ValueError(f"Can't save {file!r} without content!")
			c = self.db.cursor()
			r = self.proc_upload_insert(
				c,
				c_user=self.ide_id,
				p_upl_orgname=file.filename,
				p_upl_size=len(file._content),
				p_upl_mimetype=file.mimetype,
				p_upl_width=file.width,
				p_upl_height=file.height,
			)
			if self.urlcontext is None:
				self.urlcontext = url.Context()
			with (self.uploaddirectory/r.p_upl_name).open("wb", context=self.urlcontext) as f:
				f.write(file._content)
			file.internalid = r.p_upl_id

	def _filecontent(self, file):
		upr_id = file.url.rsplit("/")[-1]
		c = self.db.cursor()
		c.execute("select u.upl_name from upload u, uploadref ur where u.upl_id=ur.upl_id and ur.upr_id = :upr_id", upr_id=upr_id)
		r = c.fetchone()
		if r is None:
			raise ValueError(f"no such file {file.url!r}")
		with url.Context():
			u = self.uploaddirectory/r.upl_name
			return u.openread().read()

	def get(self, appid, template=None, **params):
		c = self.db.cursor()

		c.execute("select tpl_id from template where tpl_uuid = :appid", appid=appid)
		r = c.fetchone()
		if r is None:
			raise ValueError(f"no template {appid!r}")
		tpl_id = r.tpl_id
		if template is None:
			c.execute("select vt_id from viewtemplate where tpl_id = :tpl_id and vt_defaultlist != 0", tpl_id=tpl_id)
		else:
			c.execute("select vt_id from viewtemplate where tpl_id = :tpl_id and vt_identifier = : identifier", tpl_id=tpl_id, identifier=template)
		r = c.fetchone()
		if r is None:
			raise ValueError("no such template")
		vt_id = r.vt_id
		reqparams = []
		for (key, value) in params.items():
			if value is not None:
				if isinstance(value, str):
					reqparams.append(key)
					reqparams.append(value)
				elif isinstance(value, list):
					for subvalue in value:
						reqparams.append(key)
						reqparams.append(subvalue)
		reqparams = self.varchars(reqparams)
		c.execute("select livingapi_pkg.viewtemplate_ful4on(:ide_id, :vt_id, null, :reqparams) from dual", ide_id=self.ide_id, vt_id=vt_id, reqparams=reqparams)
		r = c.fetchone()
		dump = r[0].read().decode("utf-8")
		dump = self._loaddump(dump)
		return dump

	def _save(self, record):
		app = record.app
		real = app.basetable in {"data_select", "data"}
		if real:
			proc = self.proc_data_insert if record.id is None else self.proc_data_update
			pk = "dat_id"
		else:
			proc = self._getproc(app.insertprocedure if record.id is None else app.updateprocedure)
			pk = app.primarykey

		args = {
			"c_user": self.ide_id,
		}
		if real and record.id is None:
			args["p_tpl_uuid"] = app.id
		if record.id is not None:
			args[f"p_{pk}"] = record.id
		for field in record.fields.values():
			if record.id is None or field._dirty:
				args[f"p_{field.control.field}"] = field.control._asdbarg(field.value)
				if record.id is not None:
					args[f"p_{field.control.field}_changed"] = 1
		c = self.db.cursor()
		result = proc(c, **args)

		if result.p_errormessage:
			raise ValueError(r.p_errormessage)

		if record.id is None:
			record.id = result[f"p_{pk}"]
			record.createdat = datetime.datetime.now()
			record.createdby = app.globals.user
			record.updatecount = 0
		else:
			record.updatedat = datetime.datetime.now()
			record.updatedby = app.globals.user
			record.updatecount += 1
		for field in record.fields.values():
			field._dirty = False
			field.errors = []
		record.errors = []

	def _delete(self, record):

		app = record.app
		if app.basetable in {"data_select", "data"}:
			proc = self.proc_data_delete
		else:
			proc = self._getproc(app.deleteprocedure)

		c = self.db.cursor()
		r = proc(
			c,
			c_user=self.ide_id,
			p_dat_id=record.id,
		)

		if r.p_errormessage:
			raise ValueError(r.p_errormessage)

	def _executeaction(self, record, actionidentifier):
		c = self.db.cursor()
		r = self.proc_dataaction_execute(
			c,
			c_user=self.ide_id,
			p_dat_id=record.id,
			p_da_identifier=actionidentifier,
		)

		if r.p_errormessage:
			raise ValueError(r.p_errormessage)

	def _getproc(self, procname):
		try:
			return self.custom_procs[procname]
		except KeyError:
			proc = self.db.getobject(procname)
			if not isinstance(proc, orasql.Procedure):
				raise ValueError(f"no procedure {procname}")
			self.custom_procs[procname] = proc
			return proc


class HTTPHandler(Handler):
	def __init__(self, url, username=None, password=None):
		super().__init__()
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
				f"{self.url}gateway/login",
				data=json.dumps({"username": username, "password": password}),
			)
			result = r.json()
			if result.get("status") == "success":
				self.auth_token = result["auth_token"]
			else:
				raise_403(r)

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} url={self.url!r} username={self.username!r} at {id(self):#x}>"

	def _add_auth_token(self, kwargs):
		if self.auth_token:
			if "headers" not in kwargs:
				kwargs["headers"] = {}
			kwargs["headers"]["X-La-Auth-Token"] = self.auth_token

	def _filecontent(self, file):
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
		dump = r.content.decode("utf-8")
		dump = self._loaddump(dump)
		return dump

	def _save(self, record):
		fields = {field.control.identifier : field.control._asjson(field.value) for field in record.fields.values() if record.id is None or field.is_dirty()}
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
			field._dirty = False
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
		record._deleted = True

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
