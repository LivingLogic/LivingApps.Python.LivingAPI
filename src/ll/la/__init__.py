#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2019 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
:mod:`ll.la` provides a Python API for the LivingApps system.

See http://www.living-apps.de/ or http://www.living-apps.com/ for more info.
"""

import datetime, operator, string, enum, json, pathlib, inspect

from ll import misc, ul4c, ul4on # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``


from .handlers import *

__docformat__ = "reStructuredText"


###
### Utility functions and classes
###

def register(name):
	"""
	Shortcut for registering a LivingAPI class with the UL4ON machinery.
	"""
	def registration(cls):
		ul4on.register("de.livinglogic.livingapi." + name)(cls)
		return cls
	return registration


def format_class(cls):
	"""
	Format the name of the class object :obj:`cls`.

	Example::

		>>> format_class(int)
		'int'
	"""
	if cls.__module__ not in ("builtins", "exceptions"):
		return f"{cls.__module__}.{cls.__qualname__}"
	else:
		return cls.__qualname__


def format_list(items):
	"""
	Format a list of strings for text output.

	Example::

		>>> format_list(['a', 'b', 'c'])
		'a, b or c'
	"""
	v = []
	for (i, item) in enumerate(items):
		if i:
			v.append(" or " if i == len(items)-1 else ", ")
		v.append(item)
	return "".join(v)


class attrdict(dict):
	"""
	A subclass of :class:`dict` that makes keys accessible as attributes.

	Furthermore it supports autocompletion in IPython (via :meth:`__dir__`).
	"""

	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(key)

	def __dir__(self):
		"""
		Make keys completeable in IPython.
		"""
		return set(dir(dict)) | set(self)


def makeattrs(value):
	r"""
	Convert :class:`dict`\s into :class:`attrdict`\s.

	If :obj:`value` is not a :class:`dict` (or it already is an :class:`attrdict`)
	it will be returned unchanged.
	"""
	if isinstance(value, dict) and not isinstance(value, attrdict):
		value = attrdict(value)
	return value


def error_wrong_type(value):
	"""
	Return an error message for an unsupported field type.

	Used when setting a field to a value of the wrong type.
	"""
	return f"{misc.format_class(value)} is not supported"


def error_lookupitem_unknown(value):
	r"""
	Return an error message for an unknown identifier for :class:`LookupItem`\s.

	Used when setting the field of a lookup control to an unknown identifier.
	"""
	return f"Lookup item {value!r} is unknown"


def error_lookupitem_foreign(value):
	"""
	Return an error message for a foreign :class:`LookupItem`.

	Used when setting the field of a lookup control to a :`class`LookupItem` that
	belongs to another :class:`LookupControl`.
	"""
	return f"Wrong lookup item {value!r}"


def error_applookuprecord_unknown(value):
	"""
	Return an error message for a unknown record identifier.

	Used when setting the field of an applookup control to a record identifier
	that can't be found in the target app.
	"""
	return f"Unknown record {value!r}"


def error_applookuprecord_foreign(value):
	"""
	Return an error message for a foreign :class:`Record`.

	Used when setting the field of an applookup control to a :class:`Record`
	object that belongs to the wrong app.
	"""
	return f"{value!r} is from wrong app"


###
### Data descriptors
###

class Attr:
	"""
	Data descriptor class for many of our instance attributes.

	For :class:`Attr` to work the class for which it is used must inherit from
	:class:`Base`.

	Such a descriptor does type checking and it's possible to configure
	support for :meth:`__repr__` and for automatic :mod:`ll.ul4on` support.
	"""

	def __init__(self, *types, required=False, default=None, default_factory=None, readonly=False, repr=False, ul4on=False):
		"""
		Create a new :class:`Attr` data descriptor.

		The type of the attribute will be checked when the attribute is set, it
		must be any of the types in :obj`types`. If no type is passed any
		(i.e. any :class:`object`) is allowed. (Furthermore subclasses might
		e.g. implement certain type conversion on setting).

		If :object:`required` is :const:`False` the value :const:`None` is
		allowed too.

		:obj:`default` specifies the default value for the attribute (which is
		used by :const:`None` is used as the value).

		:obj:`default_factotry` (if not :class:`None`) can be a callable that is
		used instead of :obj:`default` to create a default value.

		If :obj:`repr` is true, the attribute will automatically be included
		in the :meth:`__repr__` output.

		If :obj:`readonly` is true, the attribute can only be set once (usually
		in the constructor). After that, setting the attribute will raise a
		:exc:`TypeError`.

		If :obj:`ul4on` is true, this attribute will automatically be serialized
		and deserialized in UL4ON dumps.
		"""
		self.name = None
		if not types:
			types = object
		else:
			if not required:
				types += (type(None),)
			if len(types) == 1:
				types = types[0]
		self.types = types
		self.default = default
		self.default_factory = default_factory
		self.readonly = readonly
		self.repr = repr
		self.ul4on = ul4on

	def __repr__(self):
		if isinstance(self.types, tuple):
			types = ", ".join(format_class(t) for t in self.types)
			types = f"types=({types})"
		else:
			types = f"type={format_class(self.types)}"
		s = f"<{self.__class__.__module__}.{self.__class__.__qualname__} name={self.name!r} {types}"
		if self.default_factory is not None:
			s += f" default_factory={self.default_factory!r}"
		elif self.default is not None:
			s += f" default={self.default!r}"
		s += f" at {id(self):#x}>"
		return s

	def repr_value(self, instance):
		"""
		Format the attribute of :obj:`instance` for :meth:`__repr__` output.
		"""
		value = self.get_value(instance)
		if value is not None:
			return f"{self.name}={value!r}"
		else:
			return None

	def __get__(self, instance, type):
		if instance is not None:
			return self.get_value(instance)
		else:
			for cls in type.__mro__:
				if self.name in cls.__dict__:
					return cls.__dict__[self.name]
			raise AttributeError(self.name)

	def __set__(self, instance, value):
		if self.readonly and self.name in instance.__dict__:
			raise TypeError(f"can't set attribute {self.name!r} of type {misc.format_class(instance)}")
		self.set_value(instance, value)

	def get_value(self, instance):
		return instance.__dict__[self.name]

	def make_default_value(self):
		"""
		Return the default value for this attribute.

		This either calls :attr:`default_factory` or returns :attr:`default`.
		"""
		if self.default_factory is not None:
			return self.default_factory()
		else:
			return self.default

	def set_value(self, instance, value):
		if value is None:
			value = self.make_default_value()
		if not isinstance(value, self.types):
			raise TypeError(f"attribute {self.name!r} must be {self._format_types()}, but is {misc.format_class(value)}")
		instance.__dict__[self.name] = value

	def ul4on_get_value(self, instance):
		return self.get_value(instance)

	def ul4on_set_value(self, instance, value):
		self.set_value(instance, value)

	def ul4on_set_default_value(self, instance):
		self.ul4on_set_value(instance, None)

	def _format_types(self):
		if isinstance(self.types, tuple):
			return format_list([format_class(t) for t in self.types])
		else:
			return format_class(self.types)


class BoolAttr(Attr):
	"""
	Subclass of :class:`Attr` for boolean values.

	Setting such an attribute also supports an integer as the value.
	"""

	def __init__(self, required=False, default=None, readonly=False, repr=False, ul4on=False):
		"""
		Create a :class:`BoolAttr` data descriptor.

		The supported type will be :class:`bool`. All other arguments have the
		same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(bool, required=required, default=default, readonly=readonly, repr=repr, ul4on=ul4on)

	def set_value(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		If :obj:`value` is an :class:`int` it will be converted to :class:`bool`
		automatically.
		"""
		if isinstance(value, int):
			value = bool(value)
		super().set_value(instance, value)


class FloatAttr(Attr):
	"""
	Subclass of :class:`Attr` for float values.

	Setting such an attribute also supports an integer as the value.
	"""

	def __init__(self, required=False, default=None, readonly=False, repr=False, ul4on=False):
		"""
		Create a :class:`BoolAttr` data descriptor.

		The supported type will be :class:`float`. All other arguments have the
		same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(float, required=required, default=default, readonly=readonly, repr=repr, ul4on=ul4on)

	def set_value(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		If :obj:`value` is an :class:`int` it will be converted to :class:`float`
		automatically.
		"""
		if isinstance(value, int):
			value = float(value)
		super().set_value(instance, value)


class EnumAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are :class:`enum.Enum` instances.

	Setting such an attribute also supports a string as the value.
	"""

	def __init__(self, type, required=False, default=None, readonly=False, repr=False, ul4on=False):
		"""
		Create an :class:`EnumAttr` data descriptor.

		:obj:`type` must be a subclass of :class:`enum.Enum`. All other
		arguments have the same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(type, required=required, default=default, readonly=readonly, repr=repr, ul4on=ul4on)
		self.type = type

	def set_value(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		:obj:`value` may also be the (:class:`str`) value of one of the
		:class:`~enum.Enum` members and will be converted to the appropriate
		member automatically.
		"""
		if isinstance(value, str):
			try:
				value = self.type(value)
			except ValueError:
				values = format_list([repr(e.value) for e in self.types])
				raise ValueError(f"value for attribute {self.name!r} must be {values}, but is {value!r}") from None
		super().set_value(instance, value)


class IntEnumAttr(EnumAttr):
	"""
	Subclass of :class:`Attr` for values that are :class:`enum.IntEnum` instances.

	Setting such an attribute also supports an integer as the value.
	"""

	def set_value(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		:obj:`value` may also be the (:class:`int`) value of one of the
		:class:`~enum.IntEnum` members and will be converted to the appropriate
		member automatically.
		"""
		if isinstance(value, int):
			try:
				value = self.type(value)
			except ValueError:
				values = format_list([repr(e.value) for e in self.types])
				raise ValueError(f"value for attribute {self.name!r} must be {values}, but is {value!r}") from None
		super().set_value(instance, value)


class VSQLAttr(Attr):
	"""
	Data descriptor for an attribute containing a vSQL expression.
	"""

	def __init__(self, function, required=False, readonly=False, repr=False, ul4on=False):
		"""
		Create an :class:`VSQLAttr` data descriptor.

		The supported type will be :class:`str`. :obj:`function` must be the
		name of a PL/SQL function for returning the UL4ON dump of the allowed
		vSQL variables.
		"""
		super().__init__(str, required=required, readonly=readonly, repr=repr, ul4on=ul4on)
		self.function = function


class AttrDictAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are dictionaries.

	Setting such an attribute convert a normal :class:`dict` into an
	:class:`attrdict` object.
	"""

	def __init__(self, required=False, readonly=False, ul4on=False):
		"""
		Create an :class:`AttrDictAttr` data descriptor.
		"""
		if required:
			super().__init__(dict, required=True, default_factory=attrdict, readonly=readonly, repr=False, ul4on=ul4on)
		else:
			super().__init__(dict, required=False, readonly=readonly, repr=False, ul4on=ul4on)

	def set_value(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		if :obj:`value` is a :class:`dict` (but not an :class:`attrdict`) it will
		be converted to an :class:`attrdict` automatically.
		"""
		value = makeattrs(value)
		super().set_value(instance, value)


###
### Exceptions
###

class UnsavedError(Exception):
	"""
	Raised when an object is saved which references an unsaved object.
	"""

	def __init__(self, object):
		"""
		Create an :exc:`UnsavedError` exception.

		:obj:`object` is the unsaved object.
		"""
		self.object = object

	def __str__(self):
		return f"Referenced object {self.object!r} hasn't been saved yet!"


class DeletedError(Exception):
	"""
	Raised when an object is saved which references a deleted object.
	"""

	def __init__(self, object):
		"""
		Create an :exc:`UnsavedError` exception.

		:obj:`object` is the deleted object.
		"""
		self.object = object

	def __str__(self):
		return f"Referenced object {self.object!r} has been deleted!"


###
### Core classes
###


class BaseMetaClass(type):
	"""
	Metaclass that sets the ``name`` attribute of our data descriptors.
	"""

	def __new__(cls, name, bases, dict):
		newdict = {}
		for (key, value) in dict.items():
			if isinstance(value, Attr):
				value.name = key
			if isinstance(value, type) and issubclass(value, Attr):
				(initargnames, initvarargname, initvarkwname) = inspect.getargs(value.__init__.__code__)
				if initvarkwname is not None:
					raise TypeError(f"** arguments for {value.__init__} not supported")
				if initvarargname is not None and initvarargname in value.__dict__:
					initargs = value.__dict__[initvarargname]
				else:
					initargs = ()
				initkwargs = {k: v for (k, v) in value.__dict__.items() if k in initargnames and k != initargnames[0]}
				value = value(*initargs, **initkwargs)
				value.name = key
			newdict[key] = value
		return type.__new__(cls, name, bases, newdict)


class Base(metaclass=BaseMetaClass):
	ul4attrs = set()

	@classmethod
	def attrs(cls):
		attrs = {}
		for checkcls in reversed(cls.__mro__):
			for attr in checkcls.__dict__.values():
				if isinstance(attr, Attr):
					attrs[attr.name] = attr
		return attrs.values()

	def __repr__(self):
		v = [f"<{self.__class__.__module__}.{self.__class__.__qualname__}"]

		for attr in self.attrs():
			if attr.repr:
				repr_value = attr.repr_value(self)
				if repr_value is not None:
					v.append(repr_value)
		v.append(f"at {id(self):#x}>")
		return " ".join(v)

	def ul4ondump(self, encoder):
		for attr in self.attrs():
			if attr.ul4on:
				value = attr.ul4on_get_value(self)
				encoder.dump(value)

	def ul4onload(self, decoder):
		attrs = (attr for attr in self.attrs() if attr.ul4on)
		dump = decoder.loadcontent()

		# Load all attributes that we get from the UL4ON dump
		# Stop when the dump is exhausted or we've loaded all known attributes.
		for (attr, value) in zip(attrs, dump):
			attr.ul4on_set_value(self, value)

		# Exhaust the UL4ON dump
		for value in dump:
			pass

		# Initialize the rest of the attributes with default values
		for attr in attrs:
			attr.ul4on_set_default_value(self)


@register("flashmessage")
class FlashMessage(Base):
	ul4attrs = {"timestamp", "type", "title", "message"}

	class Type(enum.Enum):
		"""
		The severity level of a :class:`FlashMessage`.
		"""

		INFO = "info"
		NOTICE = "notice"
		WARNING = "warning"
		ERROR = "error"

	timestamp = Attr(datetime.datetime, ul4on=True)
	type = EnumAttr(Type, ul4on=True)
	title = Attr(str, ul4on=True)
	message = Attr(str, ul4on=True)

	def __init__(self, timestamp=None, type=Type.INFO, title=None, message=None):
		self.timestamp = timestamp
		self.type = type
		self.title = title
		self.message = message


@register("file")
class File(Base):
	ul4attrs = {"id", "url", "filename", "mimetype", "width", "height", "createdat"}

	id = Attr(str, repr=True, ul4on=True)
	url = Attr(str, ul4on=True)
	filename = Attr(str, repr=True, ul4on=True)
	mimetype = Attr(str, repr=True, ul4on=True)
	width = Attr(int, repr=True, ul4on=True)
	height = Attr(int, repr=True, ul4on=True)
	internalid = Attr(str, ul4on=True)
	createdat = Attr(datetime.datetime, ul4on=True)

	def __init__(self, id=None, url=None, filename=None, mimetype=None, width=None, height=None, internalid=None, createdat=None):
		self.id = id
		self.url = url
		self.filename = filename
		self.mimetype = mimetype
		self.width = width
		self.height = height
		self.internalid = internalid
		self.createdat = createdat
		self.handler = None
		self._content = None

	def save(self, handler):
		if self.internalid is None:
			if self.handler is None:
				raise ValueError(f"Can't save file {self!r}")
			self.handler.save_file(self)

	def content(self):
		"""
		Return the file content as a :class:`bytes` object.
		"""
		if self._content is not None:
			return self._content
		elif self.handler is None:
			raise ValueError(f"Can't load content of {self!r}")
		return self.handler.file_content(self)


@register("geo")
class Geo(Base):
	ul4attrs = {"lat", "long", "info"}

	lat = FloatAttr(repr=True, ul4on=True)
	long = FloatAttr(repr=True, ul4on=True)
	info = Attr(str, repr=True, ul4on=True)

	def __init__(self, lat=None, long=None, info=None):
		self.lat = lat
		self.long = long
		self.info = info


@register("user")
class User(Base):
	ul4attrs = {"id", "gender", "firstname", "surname", "initials", "email", "language", "avatar_small", "avatar_large", "keyviews"}

	internalid = Attr(str, ul4on=True)
	id = Attr(str, repr=True, ul4on=True)
	gender = Attr(str, ul4on=True)
	firstname = Attr(str, repr=True, ul4on=True)
	surname = Attr(str, repr=True, ul4on=True)
	initials = Attr(str, ul4on=True)
	email = Attr(str, repr=True, ul4on=True)
	language = Attr(str, ul4on=True)
	avatar_small = Attr(File, ul4on=True)
	avatar_large = Attr(File, ul4on=True)
	keyviews = Attr(ul4on=True)

	def __init__(self, gender=None, firstname=None, surname=None, initials=None, email=None, language=None, avatar_small=None, avatar_large=None):
		self.internalid = None
		self.id = None
		self.gender = gender
		self.firstname = firstname
		self.surname = surname
		self.initials = initials
		self.email = email
		self.language = language
		self.avatar_small = avatar_small
		self.avatar_large = avatar_large
		self.keyviews = attrdict()


@register("keyview")
class KeyView(Base):
	ul4attrs = {"id", "identifier", "name", "key", "user"}

	id = Attr(str, repr=True, ul4on=True)
	identifier = Attr(str, repr=True, ul4on=True)
	name = Attr(str, repr=True, ul4on=True)
	key = Attr(str, ul4on=True)
	user = Attr(User, ul4on=True)

	def __init__(self, identifier=None, name=None, key=None, user=None):
		self.id = None
		self.identifier = identifier
		self.name = name
		self.key = key
		self.user = user


@register("globals")
class Globals(Base):
	ul4attrs = {"version", "platform", "user", "flashes", "geo"}

	version = Attr(str, repr=True, ul4on=True)
	platform = Attr(str, repr=True, ul4on=True)
	user = Attr(User, ul4on=True)
	maxdbactions = Attr(int, ul4on=True)
	maxtemplateruntime = Attr(int, ul4on=True)
	flashes = Attr(ul4on=True)

	def __init__(self, version=None, platform=None):
		self.version = version
		self.platform = platform
		self.user = None
		self.maxdbactions = None
		self.maxtemplateruntime = None
		self.flashes = []
		self.handler = None

	def geo(self, lat=None, long=None, info=None):
		return self.handler.geo(lat, long, info)

	def ul4onload_setdefaultattr(self, name):
		if name == "flashes":
			self.flashes = []
		else:
			setattr(self, name, None)


@register("app")
class App(Base):
	ul4attrs = {"id", "globals", "name", "description", "language", "startlink", "iconlarge", "iconsmall", "createdat", "createdby", "updatedat", "updatedby", "controls", "records", "recordcount", "installation", "categories", "params", "views", "datamanagement_identifier", "basetable", "primarykey", "insertprocedure", "updateprocedure", "deleteprocedure", "templates", "insert", "internaltemplates", "viewtemplates"}

	id = Attr(str, repr=True, ul4on=True)
	globals = Attr(Globals, ul4on=True)
	name = Attr(str, repr=True, ul4on=True)
	description = Attr(str, ul4on=True)
	language = Attr(str, ul4on=True)
	startlink = Attr(str, ul4on=True)
	iconlarge = Attr(ul4on=True)
	iconsmall = Attr(ul4on=True)
	createdby = Attr(User, ul4on=True)
	controls = AttrDictAttr(ul4on=True)
	records = AttrDictAttr(ul4on=True)
	recordcount = Attr(int, ul4on=True)
	installation = Attr(ul4on=True)
	categories = Attr(ul4on=True)
	params = AttrDictAttr(ul4on=True)
	views = Attr(ul4on=True)
	datamanagement_identifier = Attr(str, ul4on=True)
	basetable = Attr(str, ul4on=True)
	primarykey = Attr(str, ul4on=True)
	insertprocedure = Attr(str, ul4on=True)
	updateprocedure = Attr(str, ul4on=True)
	deleteprocedure = Attr(str, ul4on=True)
	templates = BoolAttr(ul4on=True)
	createdat = Attr(datetime.datetime, ul4on=True)
	updatedat = Attr(datetime.datetime, ul4on=True)
	updatedby = Attr(User, ul4on=True)
	internaltemplates = AttrDictAttr(ul4on=True)
	viewtemplates = AttrDictAttr(ul4on=True)

	def __init__(self, name=None, description=None, language=None, startlink=None, iconlarge=None, iconsmall=None, createdat=None, createdby=None, updatedat=None, updatedby=None, recordcount=None, installation=None, categories=None, params=None, views=None, datamanagement_identifier=None):
		self.id = None
		self.globals = None
		self.name = name
		self.description = description
		self.language = language
		self.startlink = startlink
		self.iconlarge = iconlarge
		self.iconsmall = iconsmall
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.templates = None
		self.controls = None
		self.records = None
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
		self.internaltemplates = None
		self.viewtemplates = None

	def __str__(self):
		return self.fullname

	def __getattr__(self, name):
		try:
			if name.startswith("c_"):
				return self.controls[name[2:]]
		except KeyError:
			pass
		raise AttributeError(name) from None

	def ul4getattr(self, name):
		if self.ul4hasattr(name):
			return getattr(self, name)
		raise AttributeError(name) from None

	def ul4hasattr(self, name):
		return name in self.ul4attrs or (name.startswith("c_") and name[2:] in self.controls)

	def save(self, handler, recursive=True):
		handler.save_app(self, recursive=recursive)

	_saveletters = string.ascii_letters + string.digits + "()-+_ äöüßÄÖÜ"

	@property
	def fullname(self):
		if self.name:
			safename = "".join(c for c in self.name if c in self._saveletters)
			return f"{safename} ({self.id})"
		else:
			return self.id

	def addtemplate(self, template):
		"""
		Add :obj:`template` as a child for :obj:`self`.

		:obj:`template` may either be an :class:`Internaltemplate` (which will
		get added to the attribute ``internaltemplates``) or a
		:class:`ViewTemplate` (which will get added to the attribute
		``viewtemplates``).
		"""
		if isinstance(template, InternalTemplate):
			if self.internaltemplates is None:
				self.internaltemplates = attrdict()
			template.app = self
			self.internaltemplates[template.identifier] = template
		elif isinstance(template, ViewTemplate):
			if self.viewtemplates is None:
				self.viewtemplates = attrdict()
			template.app = self
			self.viewtemplates[template.identifier] = template
		else:
			raise TypeError(f"don't know what to do with positional argument {template!r}")

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

	def __call__(self, **kwargs):
		record = Record(app=self)
		for (identifier, value) in kwargs.items():
			if identifier not in self.controls:
				raise TypeError(f"app_{self.id}() got an unexpected keyword argument {identifier!r}")
			field = record.fields[identifier]
			field.value = value
			field._dirty = False # The record is dirty anyway
		return record


class Control(Base):
	type = None
	subtype = None
	ul4attrs = {"id", "identifier", "app", "label", "type", "subtype", "priority", "order", "default", "ininsertprocedure", "inupdateprocedure"}

	id = Attr(str, repr=True, ul4on=True)
	identifier = Attr(str, repr=True, ul4on=True)
	field = Attr(str, ul4on=True)
	app = Attr(App, ul4on=True)
	label = Attr(str, ul4on=True)
	priority = BoolAttr(ul4on=True)
	order = Attr(int, ul4on=True)
	default = Attr(ul4on=True)
	ininsertprocedure = BoolAttr(ul4on=True)
	inupdateprocedure = BoolAttr(ul4on=True)

	def __init__(self, identifier=None, field=None, label=None, priority=None, order=None, default=None):
		self.id = None
		self.app = None
		self.identifier = identifier
		self.field = field
		self.label = label
		self.priority = priority
		self.order = order
		self.default = default

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

	encrypted = IntEnumAttr(EncryptionType, default=EncryptionType.NONE, ul4on=True)


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

	lookupdata = AttrDictAttr(required=True, ul4on=True)

	def __init__(self, identifier=None, field=None, label=None, priority=None, order=None, default=None, lookupdata=None):
		super().__init__(identifier=identifier, field=field, label=label, priority=priority, order=order, default=default)
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
			return super().ul4onload_setdefaultattr(name)


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

	lookupapp = Attr(App, ul4on=True)
	lookupcontrols = AttrDictAttr(ul4on=True)

	def __init__(self, identifier=None, field=None, label=None, priority=None, order=None, default=None, lookupapp=None, lookupcontrols=None):
		super().__init__(identifier=identifier, field=field, label=label, priority=priority, order=order, default=default)
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
				raise UnsavedError(value)
			elif value._deleted:
				raise DeletedError(value)
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
				raise UnsavedError(item)
			elif item._deleted:
				raise DeletedError(item)
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
				raise UnsavedError(value)
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

	id = Attr(str, ul4on=True)
	app = Attr(App, ul4on=True)
	createdat = Attr(datetime.datetime, ul4on=True)
	createdby = Attr(User, ul4on=True)
	updatedat = Attr(datetime.datetime, ul4on=True)
	updatedby = Attr(User, ul4on=True)
	updatecount = Attr(int, ul4on=True)

	class values(AttrDictAttr):
		readonly = True
		ul4on = True

		def get_value(self, instance):
			values = instance.__dict__["values"]
			if values is None:
				values = attrdict()
				for control in instance.app.controls.values():
					value = instance._sparsevalues.get(control.identifier)
					(value, _) = control._convertvalue(value)
					values[control.identifier] = value
				instance._sparsevalues = None
				instance.__dict__["values"] = values
			return values

		def ul4on_get_value(self, instance):
			values = instance._sparsevalues
			if values is None:
				values = {identifier: value for (identifier, value) in instance.values.items() if value is not None}
			return values

		def ul4on_set_value(self, instance, value):
			instance._sparsevalues = value
			# Set the following attributes via ``__dict__``, as they are "read only".
			instance.__dict__["values"] = None
			instance.__dict__["fields"] = None

	class fields(AttrDictAttr):
		readonly = True
		ul4on = False

		def get_value(self, instance):
			fields = instance.__dict__["fields"]
			if fields is None:
				values = instance.values
				fields = attrdict((identifier, Field(instance.app.controls[identifier], instance, values[identifier])) for identifier in instance.app.controls)
				instance.__dict__["fields"] = fields
			return fields

	attachments = Attr(ul4on=True)
	children = AttrDictAttr(ul4on=True)

	def __init__(self, id=None, app=None, createdat=None, createdby=None, updatedat=None, updatedby=None, updatecount=None):
		self.id = id
		self.app = app
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.updatecount = updatecount
		self._sparsevalues = attrdict()
		self.values = None
		self.fields = None
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
		Make keys completeable in IPython.
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

	def save(self):
		self.app.globals.handler.save_record(self)

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
		return self.value is None or (isinstance(self.value, list) and not self.value)

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

	id = Attr(str, repr=True, ul4on=True)
	record = Attr(Record, ul4on=True)
	label = Attr(str, ul4on=True)
	active = BoolAttr(ul4on=True)

	def __init__(self, id=None, record=None, label=None, active=None):
		self.id = id
		self.record = record
		self.label = label
		self.active = active


@register("imageattachment")
class ImageAttachment(Attachment):
	ul4attrs = Attachment.ul4attrs.union({"original", "thumb", "small", "medium", "large"})
	type = "imageattachment"

	original = Attr(File, ul4on=True)
	thumb = Attr(File, ul4on=True)
	small = Attr(File, ul4on=True)
	medium = Attr(File, ul4on=True)
	large = Attr(File, ul4on=True)

	def __init__(self, id=None, record=None, label=None, active=None, original=None, thumb=None, small=None, medium=None, large=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.original = original
		self.thumb = thumb
		self.small = small
		self.medium = medium
		self.large = large


class SimpleAttachment(Attachment):
	ul4attrs = Attachment.ul4attrs.union({"value"})

	value = Attr(ul4on=True)

	def __init__(self, id=None, record=None, label=None, active=None, value=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.value = value


@register("fileattachment")
class FileAttachment(SimpleAttachment):
	type = "fileattachment"

	value = Attr(File, ul4on=True)


@register("urlattachment")
class URLAttachment(SimpleAttachment):
	type = "urlattachment"

	value = Attr(str, ul4on=True)


@register("noteattachment")
class NoteAttachment(SimpleAttachment):
	type = "noteattachment"

	value = Attr(str, ul4on=True)


@register("jsonattachment")
class JSONAttachment(SimpleAttachment):
	type = "jsonattachment"

	class value(Attr):
		ul4on = True

		def ul4on_set_value(self, instance, value):
			value = json.loads(value)
			super().ul4on_set_value(instance, value)


class Template(Base):
	# Data descriptors for instance attributes
	id = Attr(str, ul4on=True)
	app = Attr(App, ul4on=True)
	identifier = Attr(str, ul4on=True)
	source = Attr(str, ul4on=True)
	whitespace = Attr(str, ul4on=True)
	signature = Attr(str, ul4on=True)
	doc = Attr(str, ul4on=True)

	class path(Attr):
		types = (str,)
		readonly = True
		repr = True

		def get_value(self, instance):
			return str(instance)

	def __init__(self, identifier=None, source=None, whitespace="keep", signature=None, doc=None):
		self.id = None # Type: OptStr
		self.app = None
		self.identifier = identifier
		self.source = source
		self.signature = signature
		self.whitespace = whitespace
		self.doc = doc

	def template(self):
		return ul4c.Template(self.source, name=self.identifier, signature=self.signature, whitespace=self.whitespace)

	def _save(self, path, content):
		content = content or ""
		try:
			path.write_text(content, encoding="utf-8")
		except FileNotFoundError:
			path.parent.mkdir(parents=True)
			path.write_text(content, encoding="utf-8")

	_hints = dict(
		htmlul4=("</", "<span", "<p>", "<p ", "<div>", "<div ", "<td>", "<td ", "<th>", "<th ", "<!--"),
		cssul4=("font-size", "background-color", "{"),
		jsul4=("$(", "var ", "let ", "{"),
	)

	def _guessext(self, basedir) -> str:
		"""
		Try to guess an extension for our source.

		If there's only *one* file with a matching filename in the directory
		``basedir``, always use its filename, else try to guess the extension
		from the source.
		"""
		source = self.source or ""

		# If we have exactly *one* file with this basename in ``basedir``, use this filename
		candidates = list(pathlib.Path(basedir).glob(f"{self.identifier}.*ul4"))
		if len(candidates) == 1:
			return candidates[0].suffix[1:]
		hintcount = {key: sum(source.count(string) for string in strings) for (key, strings) in self._hints.items()}
		bestguess = max(hintcount.items(), key=operator.itemgetter(1))
		# If we've guessed "HTML", but there are no HTML markers in the file,
		# but we have a ``<?return?>`` tag, this is probably just a function.
		if bestguess[0] == "htmlul4" and bestguess[1] == 0 and "<?return " in source:
			return "ul4"
		# If we've guessed "JS" or "CSS", and the number of hints is the same
		# (probable because of the number of ``{`` characters} and we have a
		# ``<?return?>`` tag, this is probably just a function.
		elif (bestguess[0] in ("jsul4", "cssul4") and hintcount["jsul4"] == hintcount["cssul4"]) and "<?return " in source:
			return "ul4"
		# Else return the guess with the most hint matches
		return bestguess[0]


@register("internaltemplate")
class InternalTemplate(Template):
	def __str__(self):
		return f"{self.app or '?'}/internaltemplate={self.identifier}"

	def save(self, handler, recursive=True):
		handler.save_internaltemplate(self)


@register("viewtemplate")
class ViewTemplate(Template):
	class Type(enum.Enum):
		"""
		The type of a view template.

		Enum values have the following meaning:

		``LIST``
			The template is supposed to display multiple records. The URL looks
			like this::

				/gateway/apps/1234567890abcdef12345678?template=foo

			(with ``1234567890abcdef12345678`` being the app id).

		``LISTDEFAULT``
			This is similar to ``LIST``, but this view template is the default when
			no ``template`` parameter is specified, i.e. the URL looks like this::

				/gateway/apps/1234567890abcdef12345678

		``DETAIL``
			The template is supposed to display the details of a single record. The
			URL looks like this::

				/gateway/apps/1234567890abcdef12345678/1234567890abcdef12345678?template=foo

			(with ``abcdefabcdefabcdefabcdef`` being the id of the record)

		``DETAILRESULT``
			This is similar to ``DETAIL``, but is used to replace the standard display
			if a record is created or updated via the standard form.

		``SUPPORT``
			The template is supposed to be independant of any record. This can be
			used for delivering static CSS or similar stuff. The URL looks the same
			as for the type ``LIST``.
		"""

		LIST = "list"
		LISTDEFAULT = "listdefault"
		DETAIL = "detail"
		DETAILRESULT = "detailresult"
		SUPPORT = "support"

	class Permission(enum.IntEnum):
		ALL = 0
		LOGGEDIN = 1
		APP = 2
		APPEDIT = 3
		APPADMIN = 4

	# The type of the view template (i.e. in which context it is used
	type = EnumAttr(Type, required=True, default=Type.LIST, ul4on=True)

	# The MIME type of the HTTP response of the view template
	mimetype = Attr(str, default="text/html", ul4on=True)

	# Who can access the template?
	permission = IntEnumAttr(Permission, required=True, default=Permission.ALL, ul4on=True)

	# Data sources
	datasources = Attr(ul4on=True)

	def __init__(self, *args, identifier=None, source=None, whitespace="keep", signature=None, doc=None, type=Type.LIST, mimetype="text/html", permission=None):
		super().__init__(identifier=identifier, source=source, whitespace=whitespace, signature=signature, doc=doc)
		self.type = type
		self.mimetype = mimetype
		self.permission = permission
		self.datasources = attrdict()
		for arg in args:
			if isinstance(arg, DataSourceConfig):
				self.adddatasource(arg)
			else:
				raise TypeError(f"don't know what to do with positional argument {arg!r}")

	def __str__(self):
		return f"{self.app or '?'}/viewtemplate={self.identifier}"

	def adddatasource(self, *datasources):
		for datasource in datasources:
			datasource.parent = self
			self.datasources[datasource.identifier] = datasource

	def ul4onload_setattr(self, name, value):
		if name == "datasources":
			value = makeattrs(value)
		setattr(self, name, value)

	def ul4onload_setdefaultattr(self, name):
		value = attrdict() if name == "datasources" else None
		setattr(self, name, value)

	def save(self, handler, recursive=True):
		handler.save_viewtemplate(self)


@register("datasourceconfig")
class DataSourceConfig(Base):
	ul4attrs = {"id", "parent", "identifier", "app", "includecloned", "appfilter", "includecontrols", "includerecords", "includecount", "recordpermission", "recordfilter", "includepermissions", "includeattachments", "includetemplates", "includeparams", "includeviews", "includecategories", "orders", "children"}

	class IncludeControls(enum.IntEnum):
		NONE = 0
		PRIORITY = 1
		ALL = 2

	class IncludeRecords(enum.IntEnum):
		NONE = 0
		CONTROLS = 1
		RECORDS = 2

	class RecordPermission(enum.IntEnum):
		NONE = -1
		CREATED = 0
		OWNED = 1
		ALL = 2

	class IncludeCategories(enum.IntEnum):
		NO = 0
		PATH = 1
		TREE = 2
		APPS = 3

	# Database identifier
	id = Attr(str, ul4on=True)

	# The view template this datasource belongs to
	parent = Attr(ViewTemplate, ul4on=True)

	# A unique identifier for the data source
	# (unique among the other data sources of the view template)
	identifier = Attr(str, ul4on=True)

	# The app from which records are fetched (or whose records are configured)
	app = Attr(App, ul4on=True)

	# Should copies of the app referenced by ``app`` be included?
	includecloned = BoolAttr(required=True, default=False, ul4on=True)

	# If more than one app is included (when either ``app`` is ``None`` or
	# ``includecloned`` is ``True``), a vSQL expression for filtering which
	# apps might be included.
	appfilter = VSQLAttr("vsqlfield_pkg.ds_recordfilter_ful4on", ul4on=True)

	# Which fields of the app should be included (in ``controls`` and ``records``)?
	includecontrols = IntEnumAttr(IncludeControls, required=True, default=IncludeControls.NONE, ul4on=True)

	includerecords = IntEnumAttr(IncludeRecords, required=True, default=IncludeRecords.NONE, ul4on=True)
	includecount = Attr(int, required=True, default=False, ul4on=True)
	recordpermission = IntEnumAttr(RecordPermission, required=True, default=RecordPermission.NONE, ul4on=True)
	recordfilter = VSQLAttr("vsqlfield_pkg.ds_recordfilter_ful4on", ul4on=True)
	includepermissions = BoolAttr(required=True, default=False, ul4on=True)
	includeattachments = BoolAttr(required=True, default=False, ul4on=True)
	includetemplates = BoolAttr(required=True, default=False, ul4on=True)
	includeparams = BoolAttr(required=True, default=False, ul4on=True)
	includeviews = BoolAttr(required=True, default=False, ul4on=True)
	includecategories = IntEnumAttr(IncludeCategories, required=True, default=IncludeCategories.NO, ul4on=True)
	orders = Attr(ul4on=True)
	children = AttrDictAttr(required=True, ul4on=True)

	def __init__(self, *args, identifier=None, app=None, includecloned=False, appfilter=None, includecontrols=None, includerecords=None, includecount=False, recordpermission=None, recordfilter=None, includepermissions=False, includeattachments=False, includetemplates=False, includeparams=False, includeviews=False, includecategories=None):
		self.id = None
		self.parent = None
		self.identifier = identifier
		self.app = app
		self.includecloned = includecloned
		self.appfilter = appfilter
		self.includecontrols = includecontrols
		self.includerecords = includerecords
		self.includecount = includecount
		self.recordpermission = recordpermission
		self.recordfilter = recordfilter
		self.includepermissions = includepermissions
		self.includeattachments = includeattachments
		self.includetemplates = includetemplates
		self.includeparams = includeparams
		self.includeviews = includeviews
		self.includecategories = includecategories
		self.orders = []
		self.children = None
		for arg in args:
			if isinstance(arg, DataOrderConfig):
				self.addorder(arg)
			elif isinstance(arg, DataSourceChildrenConfig):
				self.addchildren(arg)
			else:
				raise TypeError(f"don't know what to do with positional argument {arg!r}")

	def __str__(self):
		return f"{self.parent or '?'}/datasource={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	def addorder(self, *orders):
		for order in orders:
			order.parent = self
			self.orders.append(order)

	def addchildren(self, children):
		children.datasourceconfig = self
		self.children[children.identifier] = children

	def ul4onload_setattr(self, name, value):
		if name == "children":
			value = makeattrs(value)
		setattr(self, name, value)

	def ul4onload_setdefaultattr(self, name):
		value = attrdict() if name == "children" else None
		setattr(self, name, value)

	def save(self, handler, recursive=True):
		handler.save_datasourceconfig(self)


@register("datasourcechildrenconfig")
class DataSourceChildrenConfig(Base):
	ul4attrs = {"id", "datasource", "identifier", "control", "filters", "orders"}

	id = Attr(str, ul4on=True)
	datasourceconfig = Attr(ul4on=True)
	identifier = Attr(str, ul4on=True)
	control = Attr(Control, ul4on=True)
	filter = VSQLAttr("vsqlfield_pkg.dsc_recordfilter_ful4on", ul4on=True)
	orders = Attr(ul4on=True)

	def __init__(self, *args, identifier=None, control=None, filter=None):
		self.id = None
		self.datasourceconfig = None
		self.identifier = identifier
		self.control = control
		self.filter = filter
		self.orders = []
		for arg in args:
			if isinstance(arg, DataOrderConfig):
				self.addorder(arg)
			else:
				raise TypeError(f"don't know what to do with positional argument {arg!r}")

	def __str__(self):
		return f"{self.datasourceconfig or '?'}/datasourcechildren={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	def addorder(self, *orders):
		for order in orders:
			order.parent = self
			self.orders.append(order)

	def save(self, handler, recursive=True):
		handler.save_datasourcechildrenconfig(self)


@register("dataorderconfig")
class DataOrderConfig(Base):
	ul4attrs = {"id", "parent", "expression", "direction", "nulls"}

	class Direction(enum.Enum):
		ASC = "asc"
		DESC = "desc"

	class Nulls(enum.Enum):
		FIRST = "first"
		LAST = "last"

	# Types and defaults for instance attributes
	id = Attr(str, ul4on=True)
	parent = Attr(DataSourceConfig, DataSourceChildrenConfig, ul4on=True)
	expression = VSQLAttr("?", repr=True, ul4on=True)
	direction = EnumAttr(Direction, required=True, default=Direction.ASC, repr=True, ul4on=True)
	nulls = EnumAttr(Nulls, required=True, default=Nulls.LAST, repr=True, ul4on=True)

	def __init__(self, expression=None, direction=Direction.ASC, nulls=Nulls.LAST):
		self.id = None
		self.parent = None
		self.expression = expression
		self.direction = direction
		self.nulls = nulls

	def __str__(self):
		if self.parent is None:
			return "?/order=?"
		else:
			for (i, order) in enumerate(self.parent.orders):
				if order is self:
					return f"{self.parent}/order={i}"
			return f"{self.parent}/order=?"

	def __repr__(self):
		s = f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} expression={self.expression!r}"
		s += f" direction={self.direction}"
		s += f" nulls={self.nulls}"
		s += f" at {id(self):#x}>"
		return s

	def save(self, handler, recursive=True):
		raise NotImplementedError("DataOrderConfig objects can only be saved by their parent")


@register("installation")
class Installation(Base):
	ul4attrs = {"id", "name"}

	id = Attr(str, repr=True, ul4on=True)
	name = Attr(str, repr=True, ul4on=True)

	def __init__(self, id=None, name=None):
		self.id = id
		self.name = name


@register("view")
class View(Base):
	ul4attrs = {"id", "name", "app", "order", "width", "height", "start", "end"}

	id = Attr(str, repr=True, ul4on=True)
	name = Attr(str, repr=True, ul4on=True)
	app = Attr(App, ul4on=True)
	order = Attr(int, ul4on=True)
	width = Attr(int, ul4on=True)
	height = Attr(int, ul4on=True)
	start = Attr(datetime.datetime, ul4on=True)
	end = Attr(datetime.datetime, ul4on=True)

	def __init__(self, id=None, name=None, app=None, order=None, width=None, height=None, start=None, end=None):
		self.id = id
		self.name = name
		self.app = app
		self.order = order
		self.width = width
		self.height = height
		self.start = start
		self.end = end


@register("datasource")
class DataSource(Base):
	ul4attrs = {"id", "identifier", "app", "apps"}

	id = Attr(str, repr=True, ul4on=True)
	identifier = Attr(str, repr=True, ul4on=True)
	app = Attr(App, ul4on=True)
	apps = AttrDictAttr(ul4on=True)

	def __init__(self, id=None, identifier=None, app=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.app = app
		self.apps = apps


@register("lookupitem")
class LookupItem(Base):
	ul4attrs = {"key", "label"}

	key = Attr(str, repr=True, ul4on=True)
	label = Attr(str, repr=True, ul4on=True)

	def __init__(self, key=None, label=None):
		self.key = key
		self.label = label


@register("category")
class Category(Base):
	ul4attrs = {"id", "identifier", "name", "order", "parent", "children", "apps"}

	id = Attr(str, repr=True, ul4on=True)
	identifier = Attr(str, repr=True, ul4on=True)
	name = Attr(str, repr=True, ul4on=True)
	order = Attr(int, ul4on=True)
	parent = Attr(ul4on=True)
	children = Attr(ul4on=True)
	apps = Attr(ul4on=True)

	def __init__(self, id=None, identifier=None, name=None, order=None, parent=None, children=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.order = order
		self.parent = parent
		self.children = children
		self.apps = apps


@register("appparameter")
class AppParameter(Base):
	ul4attrs = {"id", "app", "identifier", "description", "value"}

	id = Attr(str, repr=True, ul4on=True)
	app = Attr(App, ul4on=True)
	identifier = Attr(str, repr=True, ul4on=True)
	description = Attr(str, ul4on=True)
	value = Attr(ul4on=True)

	def __init__(self, id=None, app=None, identifier=None, description=None, value=None):
		self.id = id
		self.app = app
		self.identifier = identifier
		self.description = description
		self.value = value