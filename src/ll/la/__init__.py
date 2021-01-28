#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2020 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
:mod:`ll.la` provides a Python API for the LivingApps system.

See http://www.living-apps.de/ or http://www.living-apps.com/ for more info.
"""

import io, datetime, operator, string, json, pathlib

from ll import misc, ul4c, ul4on # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``


__docformat__ = "reStructuredText"


###
### Utility functions and classes
###

NoneType = type(None)

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
	elif cls is NoneType:
		return "None"
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
	return f"Record with id {value!r} unknown"


def error_applookuprecord_foreign(value):
	"""
	Return an error message for a foreign :class:`Record`.

	Used when setting the field of an applookup control to a :class:`Record`
	object that belongs to the wrong app.
	"""
	return f"Record with id {value.id!r} is from wrong app"


def error_object_unsaved(value):
	"""
	Return an error message for an unsaved referenced object.
	"""
	return f"Referenced object {value!r} hasn't been saved yet!"


def error_object_deleted(value):
	"""
	Return an error message for an deleted referenced object.
	"""
	return f"Referenced object {value!r} has been deleted!"


def _resolve_type(t):
	if not isinstance(t, type):
		t = t()
	return t


###
### Exceptions
###


class NoHandlerError(ValueError):
	def __str__(self):
		return "no handler available"


class RecordValidationError(ValueError):
	"""
	Exception that is raised when a record is invalid and saved without
	``force=True``.
	"""

	def __init__(self, record, message):
		self.record = record
		self.message = message

	def __str__(self):
		return f"Validation for {self.record!r} failed: {self.message}"


class FieldValidationError(ValueError):
	"""
	Exception that is raised when a field of a record is invalid and the record
	is saved without ``force=True``.
	"""

	def __init__(self, field, message):
		self.field = field
		self.message = message

	def __str__(self):
		return f"Validation for {self.field!r} failed: {self.message}"


###
### Data descriptors
###

class Attr:
	"""
	Data descriptor class for many of our instance attributes.

	For :class:`Attr` to work the class for which it is used must subclass
	:class:`Base`.

	Such a descriptor does type checking and it's possible to configure
	support for :meth:`__repr__` and for automatic :mod:`ll.ul4c` and
	:mod:`ll.ul4on` support.
	"""

	def __init__(self, *types, required=False, default=None, default_factory=None, readonly=False, repr=False, doc=None, ul4on=False, get=None, set=None, ul4get=None, ul4set=None, ul4onget=None, ul4onset=None, ul4onsetdefault=None):
		"""
		Create a new :class:`Attr` data descriptor.

		The type of the attribute will be checked when the attribute is set, it
		must be any of the types in :obj`types`. If no type is passed any type
		(i.e. any :class:`object`) is allowed. (Furthermore subclasses might
		e.g. implement certain type conversion on setting).

		If :object:`required` is :const:`False` the value :const:`None` is
		allowed too.

		:obj:`default` specifies the default value for the attribute (which is
		used if :const:`None` is used as the value).

		:obj:`default_factory` (if not :class:`None`) can be a callable that is
		used instead of :obj:`default` to create a default value.

		If :obj:`repr` is true, the attribute will automatically be included
		in the :meth:`__repr__` output. If :obj:`repr` is a string it must be
		the name of a method. This method will be called for formatting this
		attribute for :meth:`__repr__` output.

		If :obj:`readonly` is true, the attribute can only be set once (usually
		in the constructor). After that, setting the attribute will raise a
		:exc:`TypeError`.

		:obj:`doc` is used for to set the doc string on the descriptor.

		If :obj:`ul4on` is true, this attribute will automatically be serialized
		and deserialized in UL4ON dumps.

		:obj:`ul4get`, :obj:`ul4set`, :obj:`ul4onget`, :obj:`ul4onset` and
		:obj:`ul4onsetdefault` are the names of methods that will be called
		instead of the default implementation to execute custom functionality
		for this attribute in certain situation (i.e. getting and setting the
		attribute from Python, UL4 and UL4ON)

		"""
		self.name = None
		if not types:
			types = object
		else:
			if not required:
				types += (type(None),)
			if len(types) == 1:
				types = types[0]
		self._types = types
		self._realtypes = None # Updated version of ``_types`` where callables are resolved
		self.default = default
		self.default_factory = default_factory
		self.readonly = readonly
		self.repr = repr
		self.__doc__ = doc
		self.ul4on = ul4on
		self.get = get
		self.set = set
		self.ul4get = ul4get
		self.ul4set = ul4set
		self.ul4onget = ul4onget
		self.ul4onset = ul4onset
		self.ul4onsetdefault = ul4onsetdefault

	@property
	def types(self):
		if self._realtypes is None:
			if not isinstance(self._types, tuple):
				self._realtypes = _resolve_type(self._types)
			else:
				self._realtypes = tuple(_resolve_type(t) for t in self._types)
		return self._realtypes

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

	def _repr(self, instance):
		"""
		Format the attribute of :obj:`instance` for :meth:`__repr__` output.

		If :const:`None` is returned this attribute will not be output.
		"""
		if isinstance(self.repr, str):
			return getattr(instance, self.repr)()
		value = self._get(instance)
		if value is not None:
			return f"{self.name}={value!r}"
		else:
			return None

	def __get__(self, instance, type):
		if instance is not None:
			return self._get(instance)
		else:
			for cls in type.__mro__:
				if self.name in cls.__dict__:
					return cls.__dict__[self.name]
			raise AttributeError(self.name)

	def __set__(self, instance, value):
		self._set(instance, value)

	def _get(self, instance):
		if self.get is not None:
			return getattr(instance, self.get)()
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

	def _set(self, instance, value):
		if self.set is not None:
			return getattr(instance, self.set)(value)
		if self.readonly:
			raise TypeError(f"Attribute {misc.format_class(instance)}.{self.name} is read only")
		if value is None:
			value = self.make_default_value()
		if not isinstance(value, self.types):
			raise TypeError(f"Attribute {misc.format_class(instance)}.{self.name} must be {self._format_types()}, but is {format_class(type(value))}")
		instance.__dict__[self.name] = value

	def _ul4get(self, instance):
		if self.ul4get is not None:
			return getattr(instance, self.ul4get)()
		return self._get(instance)

	def _ul4set(self, instance, value):
		if self.ul4set is not None:
			return getattr(instance, self.ul4set)(value)
		return self._set(instance, value)

	def _ul4onget(self, instance):
		if self.ul4onget is not None:
			return getattr(instance, self.ul4onget)()
		return self._get(instance)

	def _ul4onset(self, instance, value):
		if self.ul4onset is not None:
			return getattr(instance, self.ul4onset)(value)
		return self._set(instance, value)

	def _ul4onsetdefault(self, instance):
		if self.ul4onsetdefault is not None:
			return getattr(instance, self.ul4onsetdefault)()
		return self._set(instance, self.make_default_value())

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

	def __init__(self, required=False, default=None, readonly=False, **kwargs):
		"""
		Create a :class:`BoolAttr` data descriptor.

		The supported type will be :class:`bool`. All other arguments have the
		same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(bool, required=required, default=default, readonly=readonly, **kwargs)

	def _set(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		If :obj:`value` is an :class:`int` it will be converted to :class:`bool`
		automatically.
		"""
		if isinstance(value, int):
			value = bool(value)
		super()._set(instance, value)


class FloatAttr(Attr):
	"""
	Subclass of :class:`Attr` for float values.

	Setting such an attribute also supports an integer as the value.
	"""

	def __init__(self, required=False, default=None, readonly=False, **kwargs):
		"""
		Create a :class:`BoolAttr` data descriptor.

		The supported type will be :class:`float`. All other arguments have the
		same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(float, required=required, default=default, readonly=readonly, **kwargs)

	def _set(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		If :obj:`value` is an :class:`int` it will be converted to :class:`float`
		automatically.
		"""
		if isinstance(value, int):
			value = float(value)
		super()._set(instance, value)


class EnumAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are :class:`~enum.Enum` instances.

	Setting such an attribute also supports a string as the value.
	"""

	def __init__(self, type, required=False, default=None, readonly=False, **kwargs):
		"""
		Create an :class:`EnumAttr` data descriptor.

		:obj:`type` must be a subclass of :class:`~enum.Enum`. All other
		arguments have the same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(type, required=required, default=default, readonly=readonly, **kwargs)
		self.type = type

	def _set(self, instance, value):
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
				raise ValueError(f"Value for attribute {misc.format_class(instance)}.{self.name} must be {values}, but is {value!r}") from None
		super()._set(instance, value)

	def _ul4get(self, instance):
		e = self._get(instance)
		if e is not None:
			e = e.value
		return e


class IntEnumAttr(EnumAttr):
	"""
	Subclass of :class:`Attr` for values that are :class:`~enum.IntEnum` instances.

	Setting such an attribute also supports an integer as the value.
	"""

	def _set(self, instance, value):
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
				raise ValueError(f"Value for attribute {misc.format_class(instance)}.{self.name} must be {values}, but is {value!r}") from None
		super()._set(instance, value)


class VSQLAttr(Attr):
	"""
	Data descriptor for an attribute containing a vSQL expression.
	"""

	def __init__(self, function, required=False, readonly=False, repr=False, ul4on=False, **kwargs):
		"""
		Create an :class:`VSQLAttr` data descriptor.

		The supported type will be :class:`str`. :obj:`function` must be the
		name of a PL/SQL function for returning the UL4ON dump of the allowed
		vSQL variables.
		"""
		super().__init__(str, required=required, readonly=readonly, repr=repr, ul4on=ul4on, **kwargs)
		self.function = function


class AttrDictAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are dictionaries.

	Setting such an attribute convert a normal :class:`dict` into an
	:class:`attrdict` object.
	"""

	def __init__(self, required=False, readonly=False, ul4on=False, **kwargs):
		"""
		Create an :class:`AttrDictAttr` data descriptor.
		"""
		if required:
			super().__init__(dict, required=True, default_factory=attrdict, readonly=readonly, repr=False, ul4on=ul4on, **kwargs)
		else:
			super().__init__(dict, required=False, readonly=readonly, repr=False, ul4on=ul4on, **kwargs)

	def _set(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		if :obj:`value` is a :class:`dict` (but not an :class:`attrdict`) it will
		be converted to an :class:`attrdict` automatically.
		"""
		value = makeattrs(value)
		super()._set(instance, value)


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
			newdict[key] = value
		return type.__new__(cls, name, bases, newdict)


class Base(metaclass=BaseMetaClass):
	ul4attrs = set()

	@classmethod
	def attrs(cls):
		"""
		Returns an iterator over all :class:`Attr` descriptors for the class.
		"""
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
				repr_value = attr._repr(self)
				if repr_value is not None:
					v.append(repr_value)
		v.append(f"at {id(self):#x}>")
		return " ".join(v)

	def ul4ondump(self, encoder):
		for attr in self.attrs():
			if attr.ul4on:
				value = attr._ul4onget(self)
				encoder.dump(value)

	def ul4onload(self, decoder):
		self.ul4onload_begin(decoder)
		attrs = (attr for attr in self.attrs() if attr.ul4on)
		dump = decoder.loadcontent()

		# Load all attributes that we get from the UL4ON dump
		# Stop when the dump is exhausted or we've loaded all known attributes.
		for (attr, value) in zip(attrs, dump):
			attr._ul4onset(self, value)

		# Exhaust the UL4ON dump
		for value in dump:
			pass

		# Initialize the rest of the attributes with default values
		for attr in attrs:
			attr._ul4onsetdefault(self)
		self.ul4onload_end(decoder)

	def ul4onload_begin(self, decoder):
		"""
		Called before the content of the object is loaded from an UL4ON dump.
		"""

	def ul4onload_end(self, decoder):
		"""
		Called after the content of the object has been loaded from an UL4ON dump.
		"""


@register("flashmessage")
class FlashMessage(Base):
	ul4attrs = {"timestamp", "type", "title", "message"}

	class Type(misc.Enum):
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
	ul4attrs = {"id", "url", "filename", "mimetype", "width", "height", "size", "createdat"}

	id = Attr(str, repr=True, doc="Unique database id")
	url = Attr(str, ul4on=True, doc="Server relative URL of the file")
	filename = Attr(str, repr=True, ul4on=True, doc="Original file name")
	mimetype = Attr(str, repr=True, ul4on=True, doc="MIME type")
	width = Attr(int, repr=True, ul4on=True, doc="Width in pixels if this file is an image")
	height = Attr(int, repr=True, ul4on=True, doc="Height in pixels if this file is an image")
	internalid = Attr(str, ul4on=True)
	createdat = Attr(datetime.datetime, ul4on=True, doc="When was this file uploaded?")
	size = Attr(int, ul4on=True, doc="The filesize in bytes")

	def __init__(self, id=None, url=None, filename=None, mimetype=None, width=None, height=None, size=None, internalid=None, createdat=None, content=None):
		self.id = id
		self.url = url
		self.filename = filename
		self.mimetype = mimetype
		self.width = width
		self.height = height
		self.size = size
		self.internalid = internalid
		self.createdat = createdat
		self.handler = None
		self._content = content
		if content is not None and mimetype.startswith("image/") and width is None and height is None:
			from PIL import Image # This requires :mod:`Pillow`, which you can install with ``pip install pillow``
			stream = io.BytesIO(content)
			with Image.open(stream) as img:
				self.width = img.size[0]
				self.height = img.size[1]

	@property
	def ul4onid(self):
		return self.id

	def _gethandler(self, handler):
		if handler is None:
			if self.handler is None:
				raise NoHandlerError()
			handler = self.handler
		return handler

	def save(self, handler=None):
		self._gethandler(handler).save_file(self)

	def content(self, handler=None):
		"""
		Return the file content as a :class:`bytes` object.
		"""
		if self._content is not None:
			return self._content
		return self._gethandler(handler).file_content(self)


@register("geo")
class Geo(Base):
	ul4attrs = {"lat", "long", "info"}

	lat = FloatAttr(repr=True, ul4on=True, doc="Latitude (i.e. north/south)")
	long = FloatAttr(repr=True, ul4on=True, doc="Longitude (i.e. east/west)")
	info = Attr(str, repr=True, ul4on=True, doc="Description of the location")

	def __init__(self, lat=None, long=None, info=None):
		self.lat = lat
		self.long = long
		self.info = info


@register("user")
class User(Base):
	ul4attrs = {"id", "gender", "firstname", "surname", "initials", "email", "lang", "avatar_small", "avatar_large", "keyviews"}

	id = Attr(str, repr=True, doc="Unique database id")
	publicid = Attr(str, ul4on=True)
	gender = Attr(str, ul4on=True)
	firstname = Attr(str, repr=True, ul4on=True)
	surname = Attr(str, repr=True, ul4on=True)
	initials = Attr(str, ul4on=True)
	email = Attr(str, repr=True, ul4on=True, doc="Email address and account name")
	lang = Attr(str, ul4on=True, doc="Preferred language")
	avatar_small = Attr(File, ul4on=True)
	avatar_large = Attr(File, ul4on=True)
	keyviews = Attr(ul4on=True)

	def __init__(self, id=None, gender=None, firstname=None, surname=None, initials=None, email=None, lang=None, avatar_small=None, avatar_large=None):
		self.id = id
		self.publicid = id
		self.gender = gender
		self.firstname = firstname
		self.surname = surname
		self.initials = initials
		self.email = email
		self.lang = lang
		self.avatar_small = avatar_small
		self.avatar_large = avatar_large
		self.keyviews = attrdict()

	@property
	def ul4onid(self):
		return self.id


@register("keyview")
class KeyView(Base):
	ul4attrs = {"id", "identifier", "name", "key", "user"}

	id = Attr(str, repr=True, ul4on=True, doc="Unique database id")
	identifier = Attr(str, repr=True, ul4on=True, doc="Human readable identifier")
	name = Attr(str, repr=True, ul4on=True, doc="User supplied name")
	key = Attr(str, ul4on=True, doc="Identifier used as final part of the URL")
	user = Attr(User, ul4on=True, doc="User, who should be considered to be the logged in user for the keyview")

	def __init__(self, identifier=None, name=None, key=None, user=None):
		self.id = None
		self.identifier = identifier
		self.name = name
		self.key = key
		self.user = user


@register("globals")
class Globals(Base):
	ul4attrs = {
		"version",
		"hostname",
		"platform",
		"app",
		"record",
		"datasources",
		"user",
		"flashes",
		"log_debug",
		"log_info",
		"log_notice",
		"log_warning",
		"log_error",
		"lang",
		"templates",
		"request",
		"response",
		"geo",
	}

	id = Attr(str, doc="This is just used to make the :class:`Globals` object persistent")
	version = Attr(str, repr=True, ul4on=True, doc="API version (normally increases with every update of the LivingApps platform)")
	platform = Attr(str, repr=True, ul4on=True, doc="A name for the platform we're running on")
	user = Attr(User, ul4on=True, doc="The currently logging in user")
	maxdbactions = Attr(int, ul4on=True, doc="How many database actions may a template execute?")
	maxtemplateruntime = Attr(int, ul4on=True, doc="How long is a template allowed to run?")
	flashes = Attr(ul4on=True, ul4onsetdefault="flashes_ul4onset_default", doc="List of flash messages")
	lang = Attr(str, repr=True, ul4on=True, doc="The language to be used by templates")
	datasources = AttrDictAttr(ul4on=True, ul4onset="_datasources_ul4onset", ul4onsetdefault="_datasources_ul4onsetdefault", doc="Data for configured data sources")
	hostname = Attr(str, repr=True, ul4on=True, doc="The host name we're running on (can be used to recreate URLs)")
	app = Attr(lambda: App, ul4on=True, doc="The app that the running template belongs to")
	record = Attr(lambda: Record, ul4on=True, ul4onset="_record_ul4onset", doc="The detail record")

	def __init__(self, version=None, hostname=None, platform=None):
		self.id = None
		self.version = version
		self.hostname = hostname
		self.platform = platform
		self.app = None
		self.datasources = attrdict()
		self.user = None
		self.maxdbactions = None
		self.maxtemplateruntime = None
		self.flashes = []
		self.lang = None
		self.handler = None
		self.request = None
		self.response = None
		self._templates = None

	def flashes_ul4onset_default(self):
		self.flashes = []

	def _datasources_ul4onset(self, value):
		if value is not None:
			self.datasources = value

	def _datasources_ul4onsetdefault(self):
		self.datasources = {}

	def _record_ul4onset(self, value):
		if value is not None:
			self.record = value

	def geo(self, lat=None, long=None, info=None):
		return self.handler.geo(lat, long, info)

	def log_debug(self, *args):
		pass

	def log_info(self, *args):
		pass

	def log_notice(self, *args):
		pass

	def log_warning(self, *args):
		pass

	def log_error(self, *args):
		pass

	@property
	def templates(self):
		return self.app.templates

	def __getattr__(self, name):
		if self.datasources and name.startswith("d_"):
			try:
				return self.datasources[name[2:]]
			except KeyError:
				pass
		elif name.startswith("t_"):
			try:
				return self.templates[name[2:]]
			except KeyError:
				pass
		raise AttributeError(name)

	def __dir__(self):
		"""
		Make keys completeable in IPython.
		"""
		attrs = set(super().__dir__())
		if self.datasources:
			for identifier in self.datasources:
				attrs.add(f"d_{identifier}")
		for identifier in self.templates:
			attrs.add(f"t_{identifier}")
		return attrs

	def ul4getattr(self, name):
		if self.ul4hasattr(name):
			return getattr(self, name)
		raise AttributeError(name) from None

	def ul4setattr(self, name, value):
		if name == "lang":
			if value is not None and not isinstance(value, str):
				raise TypeError(f"Attribute {misc.format_class(self)}.{name} does not support type {misc.format_class(value)}")
			self.lang = value
		elif self.ul4hasattr(name):
			raise TypeError(f"Attribute {misc.format_class(self)}.{name} is read only")
		else:
			raise AttributeError(name)

	def ul4hasattr(self, name):
		if name in self.ul4attrs:
			return True
		elif self.datasources and name.startswith("d_") and name[2:] in self.datasources:
			return True
		elif name.startswith("t_") and name[2:] in self.templates:
			return True
		else:
			return False


@register("app")
class App(Base):
	ul4attrs = {
		"id",
		"globals",
		"name",
		"description",
		"lang",
		"startlink",
		"iconlarge",
		"iconsmall",
		"createdat",
		"createdby",
		"updatedat",
		"updatedby",
		"controls",
		"records",
		"recordcount",
		"installation",
		"categories",
		"params",
		"views",
		"datamanagement_identifier",
		"basetable",
		"primarykey",
		"insertprocedure",
		"updateprocedure",
		"deleteprocedure",
		"templates",
		"insert",
		"favorite",
		"internaltemplates",
		"viewtemplates",
		"dataactions",
	}

	id = Attr(str, repr=True, doc="Unique database id")
	globals = Attr(Globals, ul4on=True, doc="The :class:`Globals` objects")
	name = Attr(str, repr=True, ul4on=True, doc="Name of the app")
	description = Attr(str, ul4on=True, doc="Description of the app")
	lang = Attr(str, ul4on=True, doc="The language the app should be displayed in")
	startlink = Attr(str, ul4on=True)
	iconlarge = Attr(ul4on=True, doc="Large version of app icon")
	iconsmall = Attr(ul4on=True, doc="Small version of app icon")
	createdby = Attr(User, ul4on=True, doc="Who created this app?")
	controls = AttrDictAttr(ul4on=True, doc="The definition of the fields of this app")
	records = AttrDictAttr(ul4on=True, ul4onset="_records_ul4onset", doc="The records of this app (if configured)")
	recordcount = Attr(int, ul4on=True, ul4onset="_recordcount_ul4onset", doc="The number of records in this app (if configured)")
	installation = Attr(ul4on=True, doc="The installation that created this app")
	categories = Attr(ul4on=True, ul4onset="_categories_ul4onset", doc="The navigation categories the currently logged in user put this app in")
	params = AttrDictAttr(ul4on=True, ul4onset="_params_ul4onset", doc="Application specific configuration parameters")
	views = Attr(ul4on=True)
	datamanagement_identifier = Attr(str, ul4on=True)
	basetable = Attr(str, ul4on=True, doc="Name of table or view records of this app are stored in")
	primarykey = Attr(str, ul4on=True, doc="Name of the primary key of the table/view records of this app are stored in")
	insertprocedure = Attr(str, ul4on=True, doc="Procedure for inserting new records of this app")
	updateprocedure = Attr(str, ul4on=True, doc="Procedure for updating existing records of this app")
	deleteprocedure = Attr(str, ul4on=True, doc="Procedure for deleting existing records of this app")
	_templates = AttrDictAttr(ul4on=True)
	createdat = Attr(datetime.datetime, ul4on=True, doc="When was this app created?")
	updatedat = Attr(datetime.datetime, ul4on=True, doc="When was this app last changed?")
	updatedby = Attr(User, ul4on=True, doc="When changed this app last?")
	superid = Attr(str, ul4on=True, doc="Database id of the app this one was copied from")
	favorite = BoolAttr(ul4on=True, doc="Is this app a favorite of the currentlyt logged in user?")
	internaltemplates = AttrDictAttr(ul4on=True, doc="Internal templates of this app")
	viewtemplates = AttrDictAttr(ul4on=True, doc="View templates of this app")
	dataactions = AttrDictAttr(ul4on=True, doc="Data actions of this app")

	def __init__(self, id=None, name=None, description=None, lang=None, startlink=None, iconlarge=None, iconsmall=None, createdat=None, createdby=None, updatedat=None, updatedby=None, recordcount=None, installation=None, categories=None, params=None, views=None, datamanagement_identifier=None):
		self.id = id
		self.superid = None
		self.globals = None
		self.name = name
		self.description = description
		self.lang = lang
		self.startlink = startlink
		self.iconlarge = iconlarge
		self.iconsmall = iconsmall
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
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
		self._templates = None
		self.favorite = False
		self.internaltemplates = None
		self.viewtemplates = None
		self.dataactions = None

	def __str__(self):
		return self.fullname

	@property
	def ul4onid(self):
		return self.id

	def _records_ul4onset(self, value):
		if value is not None:
			self.records = value

	def _recordcount_ul4onset(self, value):
		if value is not None:
			self.recordcound = value

	def _categories_ul4onset(self, value):
		if value is not None:
			self.records = value

	def _params_ul4onset(self, value):
		if value is not None:
			self.params = value

	@property
	def templates(self):
		if self._templates is None:
			self._templates = self.globals.handler.fetch_templates(self)
		return self._templates

	def __getattr__(self, name):
		try:
			if name.startswith("c_"):
				return self.controls[name[2:]]
			elif name.startswith("t_"):
				return self.templates[name[2:]]
			elif name.startswith("p_") and self.params:
				return self.params[name[2:]]
		except KeyError:
			pass
		raise AttributeError(name) from None

	def __dir__(self):
		"""
		Make keys completeable in IPython.
		"""
		attrs = set(super().__dir__())
		for identifier in self.controls:
			attrs.add(f"c_{identifier}")
		if self.params:
			for identifier in self.params:
				attrs.add(f"p_{identifier}")
		for identifier in self.templates:
			attrs.add(f"t_{identifier}")
		return attrs

	def ul4getattr(self, name):
		if self.ul4hasattr(name):
			return getattr(self, name)
		raise AttributeError(name) from None

	def ul4hasattr(self, name):
		if name in self.ul4attrs:
			return True
		elif name.startswith("c_") and name[2:] in self.controls:
			return True
		elif name.startswith("p_") and self.params and name[2:] in self.params:
			return True
		elif name.startswith("t_") and name[2:] in self.templates:
			return True
		else:
			return False

	def _gethandler(self, handler):
		if handler is None:
			if self.globals is None or self.globals.handler is None:
				raise NoHandlerError()
			handler = self.globals.handler
		return handler

	def save(self, handler=None, recursive=True):
		self._gethandler(handler).save_app(self, recursive=recursive)

	_saveletters = string.ascii_letters + string.digits + "()-+_ äöüßÄÖÜ"

	@property
	def fullname(self):
		if self.name:
			safename = "".join(c for c in self.name if c in self._saveletters)
			return f"{safename} ({self.id})"
		else:
			return self.id

	def addcontrol(self, *controls):
		"""
		Add each control object in :obj:`controls` to :obj:`self`.
		"""
		if self.controls is None:
			self.controls = attrdict()
		for control in controls:
			control.app = self
			self.controls[control.identifier] = control

	def addtemplate(self, *templates):
		"""
		Add each template in :obj:`templates` as a child for :obj:`self`.

		This object may either be an :class:`Internaltemplate` (which will
		get added to the attribute ``internaltemplates``) or a
		:class:`ViewTemplate` (which will get added to the attribute
		``viewtemplates``).
		"""
		for template in templates:
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
		record.save(force=True)
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

	id = Attr(str, repr=True, doc="Unique database id")
	identifier = Attr(str, repr=True, ul4on=True, doc="Human readable identifier")
	field = Attr(str, ul4on=True, doc="Name of the database field")
	app = Attr(App, ul4on=True, doc="App this control belongs to")
	label = Attr(str, ul4on=True, doc="Label to be displayed for this control")
	priority = BoolAttr(ul4on=True, doc="Has this control high priority, i.e. should it be displayed in lists?")
	order = Attr(int, ul4on=True, doc="Used to sort the controls")
	default = Attr(ul4on=True, doc="The default value")
	ininsertprocedure = BoolAttr(ul4on=True, doc="Can a value for this field be passed to the insert procedure?")
	inupdateprocedure = BoolAttr(ul4on=True, doc="Can a value for this field be passed to the update procedure?")

	def __init__(self, id=None, identifier=None, field=None, label=None, priority=None, order=None, default=None):
		self.id = id
		self.app = None
		self.identifier = identifier
		self.field = field
		self.label = label
		self.priority = priority
		self.order = order
		self.default = default

	@property
	def ul4onid(self):
		return self.id

	def _set_value(self, field, value):
		field._value = value

	def _asdbarg(self, handler, field):
		return field._value

	def _asjson(self, handler, field):
		return self._asdbarg(handler, field)


class StringControl(Control):
	type = "string"

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, str):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value


@register("textcontrol")
class TextControl(StringControl):
	subtype = "text"
	fulltype = f"{StringControl.type}/{subtype}"


@register("urlcontrol")
class URLControl(StringControl):
	subtype = "url"
	fulltype = f"{StringControl.type}/{subtype}"


@register("emailcontrol")
class EmailControl(StringControl):
	subtype = "email"
	fulltype = f"{StringControl.type}/{subtype}"


@register("passwordcontrol")
class PasswordControl(StringControl):
	subtype = "password"
	fulltype = f"{StringControl.type}/{subtype}"


@register("telcontrol")
class TelControl(StringControl):
	subtype = "tel"
	fulltype = f"{StringControl.type}/{subtype}"


class EncryptionType(misc.IntEnum):
	NONE = 0
	FORCE = 1
	OPTIONAL = 2


@register("textareacontrol")
class TextAreaControl(StringControl):
	subtype = "textarea"
	fulltype = f"{StringControl.type}/{subtype}"

	ul4attrs = StringControl.ul4attrs.union({"encrypted"})

	encrypted = IntEnumAttr(EncryptionType, default=EncryptionType.NONE, ul4on=True, doc="Is this field encrypted (and how/when will it be encrypted)?")


@register("htmlcontrol")
class HTMLControl(StringControl):
	subtype = "html"
	fulltype = f"{StringControl.type}/{subtype}"


@register("intcontrol")
class IntControl(Control):
	type = "int"
	fulltype = type

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, int):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value


@register("numbercontrol")
class NumberControl(Control):
	type = "number"
	fulltype = type

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, (int, float)):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value


@register("datecontrol")
class DateControl(Control):
	type = "date"
	subtype = "date"
	fulltype = f"{type}/{subtype}"

	def _set_value(self, field, value):
		if isinstance(value, datetime.datetime):
			value = value.date()
		elif value is not None and not isinstance(value, datetime.date):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asjson(self, handler, field):
		value = field._value
		if isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d")
		return value


@register("datetimeminutecontrol")
class DatetimeMinuteControl(DateControl):
	subtype = "datetimeminute"
	fulltype = f"{DateControl.type}/{subtype}"

	def _set_value(self, field, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(second=0, microsecond=0)
		elif isinstance(value, datetime.date):
			value = datetime.datetime.combine(value, datetime.time())
		elif value is not None:
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asjson(self, handler, field):
		value = field._value
		if isinstance(value, datetime.datetime):
			value = value.strftime("%Y-%m-%d %H:%M")
		elif isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d 00:00")
		return value


@register("datetimesecondcontrol")
class DatetimeSecondControl(DateControl):
	subtype = "datetimesecond"
	fulltype = f"{DateControl.type}/{subtype}"

	def _set_value(self, field, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(microsecond=0)
		elif isinstance(value, datetime.date):
			value = datetime.datetime.combine(value, datetime.time())
		elif value is not None:
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asjson(self, handler, field):
		value = field._value
		if isinstance(value, datetime.datetime):
			value = value.strftime("%Y-%m-%d %H:%M:%S")
		elif isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d 00:00:00")
		return value


@register("boolcontrol")
class BoolControl(Control):
	type = "bool"
	fulltype = type

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, bool):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			value = int(value)
		return value


class LookupControl(Control):
	type = "lookup"

	ul4attrs = Control.ul4attrs.union({"lookupdata"})

	lookupdata = AttrDictAttr(required=True, ul4on=True, ul4onset="_lookupdata_ul4onset", ul4onsetdefault="_lookupdata_ul4onsetdefault", doc="The possible values this control might have")

	def __init__(self, identifier=None, field=None, label=None, priority=None, order=None, default=None, lookupdata=None):
		super().__init__(identifier=identifier, field=field, label=label, priority=priority, order=order, default=default)
		self.lookupdata = lookupdata

	def _set_value(self, field, value):
		if isinstance(value, str):
			if value in self.lookupdata:
				value = self.lookupdata[value]
			else:
				field.add_error(error_lookupitem_unknown(value))
				value = None
		elif isinstance(value, LookupItem):
			if value.key not in self.lookupdata or self.lookupdata[value.key] is not value:
				field.add_error(error_lookupitem_foreign(value))
				value = None
		elif value is not None:
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asdbarg(self, handler, field):
		value = field._value
		if isinstance(value, LookupItem):
			value = value.key
		return value

	def _lookupdata_ul4onset(self, value):
		self.lookupdata = makeattrs(value)

	def _lookupdata_ul4onsetdefault(self, value):
		self.lookupdata = attrdict()


@register("lookupselectcontrol")
class LookupSelectControl(LookupControl):
	subtype = "select"
	fulltype = f"{LookupControl.type}/{subtype}"


@register("lookupradiocontrol")
class LookupRadioControl(LookupControl):
	subtype = "radio"
	fulltype = f"{LookupControl.type}/{subtype}"


@register("lookupchoicecontrol")
class LookupChoiceControl(LookupControl):
	subtype = "choice"
	fulltype = f"{LookupControl.type}/{subtype}"


class AppLookupControl(Control):
	type = "applookup"

	ul4attrs = Control.ul4attrs.union({"lookup_app", "lookup_controls", "lookupapp", "lookupcontrols"})

	lookup_app = Attr(App, ul4on=True)
	lookup_controls = AttrDictAttr(ul4on=True, ul4onset="_lookup_controls_ul4onset", ul4onsetdefault="_lookup_controls_ul4onsetdefault")
	local_master_control = Attr(Control, ul4on=True)
	local_detail_controls = AttrDictAttr(ul4on=True)
	remote_master_control = Attr(Control, ul4on=True)

	def __init__(self, identifier=None, field=None, label=None, priority=None, order=None, default=None, lookup_app=None, lookup_controls=None, local_master_control=None, local_detail_controls=None, remote_master_control=None):
		super().__init__(identifier=identifier, field=field, label=label, priority=priority, order=order, default=default)
		self.lookup_app = lookup_app
		self.lookup_controls = lookup_controls
		self.local_master_control = local_master_control
		self.local_detail_controls = local_detail_controls
		self.remote_master_control = remote_master_control

	def _set_value(self, field, value):
		if isinstance(value, str):
			record = self.app.globals.handler.record_sync_data(value)
			if record is None:
				field.add_error(error_applookuprecord_unknown(value))
				value = None
			else:
				value = record
		if isinstance(value, Record):
			if value.app is not self.lookup_app:
				field.add_error(error_applookuprecord_foreign(value))
				value = None
		elif value is not None:
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			if value.id is None:
				field.add_error(error_object_unsaved(value))
				value = field._value = None
			elif value._deleted:
				field.add_error(error_object_deleted(value))
				value = field._value = None
			else:
				value = value.id
		return value

	def _lookup_controls_ul4onset(self, value):
		self.lookup_controls = makeattrs(value)

	def _lookup_controls_ul4onsetdefault(self, value):
		self.lookup_controls = attrdict()

	def _local_detail_controls_ul4onset(self, value):
		self.local_detail_controls = makeattrs(value)

	def _local_detail_controls_ul4onsetdefault(self, value):
		self.local_detail_controls = attrdict()

	# The following two properties are for backwards compatibility

	@property
	def lookupcontrols(self):
		return self.lookup_controls

	@property
	def lookupapp(self):
		return self.lookup_app


@register("applookupselectcontrol")
class AppLookupSelectControl(AppLookupControl):
	subtype = "select"
	fulltype = f"{AppLookupControl.type}/{subtype}"


@register("applookupradiocontrol")
class AppLookupRadioControl(AppLookupControl):
	subtype = "radio"
	fulltype = f"{AppLookupControl.type}/{subtype}"


@register("applookupchoicecontrol")
class AppLookupChoiceControl(AppLookupControl):
	subtype = "choice"
	fulltype = f"{AppLookupControl.type}/{subtype}"


class MultipleLookupControl(LookupControl):
	type = "multiplelookup"

	def _set_value(self, field, value):
		if value is None:
			field._value = []
		elif isinstance(value, (str, LookupItem)):
			self._set_value(field, [value])
		elif isinstance(value, list):
			field._value = []
			for v in value:
				if isinstance(v, str):
					if v in self.lookupdata:
						field._value.append(self.lookupdata[v])
					else:
						field.add_error(error_lookupitem_unknown(v))
				elif isinstance(v, LookupItem):
					if v.key not in self.lookupdata or self.lookupdata[v.key] is not v:
						field.add_error(error_lookupitem_foreign(v))
					else:
						field._value.append(v)
		else:
			field.add_error(error_wrong_type(value))
			field._value = []

	def _asjson(self, handler, field):
		return [item.key for item in field._value]

	def _asdbarg(self, handler, field):
		return handler.varchars([item.key for item in field._value])


@register("multiplelookupselectcontrol")
class MultipleLookupSelectControl(MultipleLookupControl):
	subtype = "select"
	fulltype = f"{MultipleLookupControl}/{subtype}"


@register("multiplelookupcheckboxcontrol")
class MultipleLookupCheckboxControl(MultipleLookupControl):
	subtype = "checkbox"
	fulltype = f"{MultipleLookupControl}/{subtype}"


@register("multiplelookupchoicecontrol")
class MultipleLookupChoiceControl(MultipleLookupControl):
	subtype = "choice"
	fulltype = f"{MultipleLookupControl}/{subtype}"


class MultipleAppLookupControl(AppLookupControl):
	type = "multipleapplookup"

	def _set_value(self, field, value):
		if value is None:
			field._value = []
		elif isinstance(value, (str, Record)):
			self._set_value(field, [value])
		elif isinstance(value, list):
			field._value = []
			fetched = self.app.globals.handler.records_sync_data([v for v in value if isinstance(v, str)])
			for v in value:
				if isinstance(v, str):
					record = fetched.get(v, None)
					if record is None:
						field.add_error(error_applookuprecord_unknown(v))
						v = None
					else:
						v = record
				if isinstance(v, Record):
					if v.app is not self.lookup_app:
						field.add_error(error_applookuprecord_foreign(v))
					else:
						field._value.append(v)
				elif v is not None:
					field.add_error(error_wrong_type(v))
		else:
			field.add_error(error_wrong_type(value))
			field._value = []

	def _asjson(self, handler, field):
		value = []
		i = 0
		while i < len(field._value):
			item = field._value[i]
			if item.id is None:
				field.add_error(error_object_unsaved(item))
				del field._value[i]
			elif item._deleted:
				del field._value[i]
				field.add_error(error_object_deleted(item))
			else:
				value.append(item.id)
				i += 1
		return value

	def _asdbarg(self, handler, field):
		value = self._asjson(handler, field)
		return handler.varchars(value)


@register("multipleapplookupselectcontrol")
class MultipleAppLookupSelectControl(MultipleAppLookupControl):
	subtype = "select"
	fulltype = f"{MultipleAppLookupControl.type}/{subtype}"


@register("multipleapplookupcheckboxcontrol")
class MultipleAppLookupCheckboxControl(MultipleAppLookupControl):
	subtype = "checkbox"
	fulltype = f"{MultipleAppLookupControl.type}/{subtype}"


@register("multipleapplookupchoicecontrol")
class MultipleAppLookupChoiceControl(MultipleAppLookupControl):
	subtype = "choice"
	fulltype = f"{MultipleAppLookupControl.type}/{subtype}"


@register("filecontrol")
class FileControl(Control):
	type = "file"
	fulltype = type

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, File):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			if value.internalid is None:
				field.add_error(error_object_unsaved(value))
				value = field._value = None
			else:
				value = value.internalid
		return value


@register("filesignaturecontrol")
class FileSignatureControl(FileControl):
	subtype = "signature"
	fulltype = f"{FileControl.type}/{subtype}"


@register("geocontrol")
class GeoControl(Control):
	type = "geo"
	fulltype = type

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, Geo):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			value = f"{value.lat!r}, {value.long!r}, {value.info}"
		return value


@register("viewcontrol")
class ViewControl(Base):
	ul4attrs = {"id", "identifier", "type", "subtype", "view", "control", "top", "left", "width", "height", "liveupdate", "taborder"}

	id = Attr(str, repr=True, doc="Unique database id")

	identifier = Attr(str, repr=True, readonly=True, get="_identifier_get", doc="Human readable identifier")
	type = Attr(str, repr=True, readonly=True, get="_type_get", doc="Type of the control")
	subtype = Attr(str, repr=True, required=False, readonly=True, get="_subtype_get", doc="Subtype of the control")
	view = Attr(lambda: View, ul4on=True, doc="The view this view control belongs to")
	control = Attr(Control, ul4on=True)
	top = Attr(int, ul4on=True, doc="Vertical position of this view control in the form")
	left = Attr(int, ul4on=True, doc="Horizontal position of this view control in the form")
	width = Attr(int, ul4on=True, doc="Width of this view control in the form")
	height = Attr(int, ul4on=True, doc="Height of this view control in the form")
	liveupdate = BoolAttr(ul4on=True, doc="Should changes in the input field for this control call the server side form template?")
	default = Attr(str, ul4on=True, doc="Default value")
	taborder = Attr(int, ul4on=True, doc="Keyboard navigation order of this view control in the form")

	def __init__(self, id):
		self.id = id
		self.view = None
		self.control = None
		self.top = None
		self.left = None
		self.width = None
		self.height = None
		self.default = None
		self.taborder = None

	@property
	def ul4onid(self):
		return self.id

	def _identifier_get(self):
		return self.control.identifier

	def _type_get(self):
		return self.control.type


@register("record")
class Record(Base):
	ul4attrs = {"id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "fields", "values", "children", "attachments", "errors", "has_errors", "add_error", "clear_errors", "is_deleted", "save", "update", "state"}

	class State(misc.Enum):
		"""
		The database synchronisation state of the record.
		"""

		NEW = "new"
		SAVED = "saved"
		CHANGED = "changed"
		DELETED = "deleted"

	id = Attr(str, repr=True, doc="Unique database id")
	state = EnumAttr(State, readonly=True, required=True, repr=True, get="_state_get", ul4get="_state_ul4get", doc="The state of synchronisation with the database for this record")
	app = Attr(App, ul4on=True, doc="The app this record belongs to")
	createdat = Attr(datetime.datetime, ul4on=True, doc="When was this record created?")
	createdby = Attr(User, ul4on=True, doc="Who created this record?")
	updatedat = Attr(datetime.datetime, ul4on=True, doc="When was this record last updated?")
	updatedby = Attr(User, ul4on=True, doc="Who updated this record last?")
	updatecount = Attr(int, ul4on=True, doc="How often has this record been updated?")
	fields = AttrDictAttr(readonly=True, ul4on=False, get="_fields_get", doc="Dictionary containing :class:`Field` objects (with values, errors, etc) for each field")
	values = AttrDictAttr(readonly=True, ul4on=True, get="_values_get", set="_values_set", ul4onset="_values_ul4onset", doc="Ditionary containing the field values for each field")
	attachments = Attr(ul4on=True, doc="Attachments for this record (if configured)")
	children = AttrDictAttr(ul4on=True, ul4onset="_children_ul4onset", doc="Detail records, i.e. records that have a field pointing back to this record")

	def __init__(self, id=None, app=None, createdat=None, createdby=None, updatedat=None, updatedby=None, updatecount=None):
		self.id = id
		self.app = app
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.updatecount = updatecount
		self._sparsevalues = attrdict()
		self.__dict__["values"] = None
		self.__dict__["fields"] = None
		self.children = attrdict()
		self.attachments = None
		self.errors = []
		self._new = True
		self._deleted = False

	@property
	def ul4onid(self):
		return self.id

	def ul4onload_end(self, decoder):
		self._new = False
		self._deleted = False

	def _fields_get(self):
		fields = self.__dict__["fields"]
		if fields is None:
			fields = attrdict()
			for control in self.app.controls.values():
				field = Field(control, self, self._sparsevalues.get(control.identifier))
				fields[control.identifier] = field
			self._sparsevalues = None
			self.__dict__["fields"] = fields
		return fields

	def _values_get(self):
		values = self.__dict__["values"]
		if values is None:
			values = attrdict()
			for field in self.fields.values():
				values[field.control.identifier] = field.value
			self._sparsevalues = None
			self.__dict__["values"] = values
		return values

	def _values_ul4onget(self):
		values = self._sparsevalues
		if values is None:
			values = {identifier: value for (identifier, value) in self.values.items() if value is not None}
		return values

	def _values_ul4onset(self, value):
		self._sparsevalues = value
		# Set the following attributes via ``__dict__``, as they are "read only".
		self.__dict__["values"] = None
		self.__dict__["fields"] = None

	def _children_ul4onset(self, value):
		if value is not None:
			self.children = value

	def _repr_value(self, v, seen, value):
		if isinstance(value, Record):
			value._repr_helper(v, seen)
		elif isinstance(value, list):
			v.append("[")
			for (i, item) in enumerate(value):
				if i:
					v.append(", ")
				self._repr_value(v, seen, item)
			v.append("]")
		else:
			v.append(repr(value))

	def _repr_helper(self, v, seen):
		if self in seen:
			v.append("...")
		else:
			seen.add(self)
			v.append(f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} state={self.state.value}")
			if self.has_errors():
				v.append(" has_errors()=True")
			for (identifier, value) in self.values.items():
				if self.app.controls[identifier].priority:
					v.append(f" v_{identifier}=")
					self._repr_value(v, seen, value)
			seen.remove(self)
			v.append(f" at {id(self):#x}>")

	def __repr__(self):
		v = []
		self._repr_helper(v, set())
		return "".join(v)

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
				p.text(f"state={self.state.value}")
				if self.has_errors():
					p.breakable()
					p.text("has_errors()=True")
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
			elif name.startswith("c_"):
				self.children[name[2:]] = value
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
			attr = getattr(self.__class__, name, None)
			if isinstance(attr, Attr):
				return attr._ul4get(self)
			else:
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

	def _gethandler(self, handler):
		if handler is None:
			if self.app is None:
				raise NoHandlerError()
		return self.app._gethandler(handler)

	def save(self, force=False, sync=False, handler=None):
		handler = self._gethandler(handler)
		if not force:
			self.check_errors()
		result = handler.save_record(self)
		if not force:
			self.check_errors()
		if sync:
			handler.ul4on_decoder.store_persistent_object(self)
			handler.record_sync_data(self.id, force=True)
		return result

	def update(self, **kwargs):
		for (identifier, value) in kwargs.items():
			if identifier not in self.app.controls:
				raise TypeError(f"update() got an unexpected keyword argument {identifier!r}")
			self.fields[identifier].value = value
		self.save(force=True)

	def delete(self, handler=None):
		self._gethandler(handler).delete_record(self)

	def executeaction(self, handler=None, identifier=None):
		self._gethandler(handler)._executeaction(self, identifier)

	def has_errors(self):
		return bool(self.errors) or any(field.has_errors() for field in self.fields.values())

	def add_error(self, *errors):
		self.errors.extend(errors)

	def clear_errors(self):
		for field in self.fields.values():
			field.clear_errors()
		self.errors = []

	def check_errors(self):
		if self.errors:
			raise RecordValidationError(self, self.errors[0])
		for field in self.fields.values():
			field.check_errors()

	def is_dirty(self):
		return self.id is None or any(field._dirty for field in self.fields.values())

	def is_deleted(self):
		return self._deleted

	def is_new(self):
		return self._new

	def _state_get(self):
		if self._deleted:
			return Record.State.DELETED
		elif self._new:
			return Record.State.NEW
		elif self.is_dirty():
			return Record.State.CHANGED
		else:
			return Record.State.SAVED

	def _state_ul4get(self):
		return self._state_get().value


class Field:
	ul4attrs = {"control", "record", "label", "lookupdata", "value", "is_empty", "is_dirty", "errors", "has_errors", "add_error", "clear_errors", "enabled", "writable", "visible"}

	def __init__(self, control, record, value):
		self.control = control
		self.record = record
		self._label = None
		self._lookupdata = None
		self._value = None
		self._dirty = False
		self.errors = []
		self.enabled = True
		self.writable = True
		self.visible = True
		control._set_value(self, value)
		self._dirty = False

	@property
	def label(self):
		return self._label if self._label is not None else self.control.label

	@label.setter
	def label(self, label):
		self._label = label

	@property
	def lookupdata(self):
		if isinstance(self.control, LookupControl):
			return self._lookupdata if self._lookupdata is not None else self.control.lookupdata
		elif isinstance(self.control, AppLookupControl):
			lookupdata = self._lookupdata
			if lookupdata is None:
				lookupdata = self.control.lookupapp.records
			if lookupdata is None:
				lookupdata = {}
			return lookupdata
		else:
			return None

	@lookupdata.setter
	def lookupdata(self, lookupdata):
		control = self.control
		if isinstance(control, LookupControl):
			if lookupdata is None:
				lookupdata = []
			elif isinstance(lookupdata, (str, LookupItem)):
				lookupdata = [lookupdata]
			elif isinstance(lookupdata, dict):
				lookupdata = lookupdata.values()
			items = []
			for v in lookupdata:
				if isinstance(v, str):
					if v not in control.lookupdata:
						raise ValueError(error_lookupitem_unknown(v))
					items.append(control.lookupdata[v])
				elif isinstance(v, LookupItem):
					if control.lookupdata.get(v.key, None) is not v:
						raise ValueError(error_lookupitem_foreign(v))
					items.append(v)
				elif v is not None:
					raise ValueError(error_wrong_type(v))
			self._lookupdata = attrdict({r.key : r for r in items})
		elif isinstance(control, AppLookupControl):
			self._lookupdata = lookupdata
			if lookupdata is None:
				lookupdata = []
			elif isinstance(lookupdata, (str, LookupItem)):
				lookupdata = [lookupdata]
			elif isinstance(lookupdata, dict):
				lookupdata = lookupdata.values()
			records = []
			fetched = self.control.app.globals.handler.records_sync_data([v for v in lookupdata if isinstance(v, str)])
			for v in lookupdata:
				if isinstance(v, str):
					record = fetched.get(v, None)
					if record is None:
						raise ValueError(error_applookuprecord_unknown(v))
					v = record
				if isinstance(v, Record):
					if v.app is not control.lookup_app:
						raise ValueError(error_applookuprecord_foreign(v))
					else:
						records.append(v)
				elif v is not None:
					raise ValueError(error_wrong_type(v))
			self._lookupdata = {r.id : r for r in records}
		# Ignore assignment for any other control type

	@property
	def value(self):
		return self._value

	@value.setter
	def value(self, value):
		oldvalue = self._value
		self.clear_errors()
		self.control._set_value(self, value)
		if value != oldvalue:
			self.record.values[self.control.identifier] = self._value
			self._dirty = True

	def is_empty(self):
		return self._value is None or (isinstance(self._value, list) and not self._value)

	def is_dirty(self):
		return self._dirty

	def has_errors(self):
		return bool(self.errors)

	def add_error(self, *errors):
		self.errors.extend(errors)

	def clear_errors(self):
		self.errors = []

	def check_errors(self):
		if self.errors:
			raise FieldValidationError(self, self.errors[0])

	def _asjson(self, handler):
		return self.control._asjson(handler, self)

	def _asdbarg(self, handler):
		return self.control._asdbarg(handler, self)

	def __repr__(self):
		s = f"<{self.__class__.__module__}.{self.__class__.__qualname__} identifier={self.control.identifier!r} value={self._value!r}"
		if self._dirty:
			s += " is_dirty()=True"
		if self.errors:
			s += " has_errors()=True"
		s += f" at {id(self):#x}>"
		return s

	def ul4ondump(self, encoder):
		encoder.dump(self.control)
		encoder.dump(self.record)
		encoder.dump(self.label)
		encoder.dump(self.lookupdata)
		encoder.dump(self.value)
		encoder.dump(self.errors)
		encoder.dump(self.enabled)
		encoder.dump(self.writable)
		encoder.dump(self.visible)

	def ul4onload(self, decoder):
		self.control = decoder.load()
		self.record = decoder.load()
		self.label = decoder.load()
		self.lookupdata = decoder.load()
		self.value = decoder.load()
		self.errors = decoder.load()
		self.enabled = decoder.load()
		self.writable = decoder.load()
		self.visible = decoder.load()


class Attachment(Base):
	ul4attrs = {"id", "type", "record", "label", "active"}

	id = Attr(str, repr=True, doc="Unique database id")
	record = Attr(Record, ul4on=True, doc="The record this attachment belongs to")
	label = Attr(str, ul4on=True, doc="A human readable label")
	active = BoolAttr(ul4on=True, doc="Is this attachment active?")

	def __init__(self, id=None, record=None, label=None, active=None):
		self.id = id
		self.record = record
		self.label = label
		self.active = active

	@property
	def ul4onid(self):
		return self.id


@register("imageattachment")
class ImageAttachment(Attachment):
	ul4attrs = Attachment.ul4attrs.union({"original", "thumb", "small", "medium", "large"})
	type = "imageattachment"

	original = Attr(File, ul4on=True, doc="Original uploaded image")
	thumb = Attr(File, ul4on=True, doc="Thumbnail size version of the image")
	small = Attr(File, ul4on=True, doc="Small version of the image")
	medium = Attr(File, ul4on=True, doc="Medium version of the image")
	large = Attr(File, ul4on=True, doc="Large version of the image")

	def __init__(self, id=None, record=None, label=None, active=None, original=None, thumb=None, small=None, medium=None, large=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.original = original
		self.thumb = thumb
		self.small = small
		self.medium = medium
		self.large = large


class SimpleAttachment(Attachment):
	ul4attrs = Attachment.ul4attrs.union({"value"})

	value = Attr(ul4on=True, doc="The value of the attachment (a string, file, URL, note or JSON)")

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
	id = Attr(str, doc="Unique database id")
	app = Attr(App, ul4on=True, doc="The app this template belongs to")
	identifier = Attr(str, ul4on=True, doc="Human readable identifier")
	source = Attr(str, ul4on=True, doc="UL4 source code")
	whitespace = Attr(str, ul4on=True, doc="Whitespace handling (extracted from <?whitespace?> tag)")
	signature = Attr(str, ul4on=True, doc="Template signature (extracted from <?ul4?> tag)")
	doc = Attr(str, ul4on=True, doc="Documentation (extracted from <?doc?> tag)")
	path = Attr(str, readonly=True, repr=True, get="__str__")

	def __init__(self, id=None, identifier=None, source=None, whitespace="keep", signature=None, doc=None):
		self.id = id
		self.app = None
		self.identifier = identifier
		self.source = source
		self.signature = signature
		self.whitespace = whitespace
		self.doc = doc
		self._deleted = False

	@property
	def ul4onid(self):
		return self.id

	def template(self):
		return ul4c.Template(self.source, name=self.identifier, signature=self.signature, whitespace=self.whitespace)

	def _gethandler(self, handler):
		if handler is None:
			if self.app is None:
				raise NoHandlerError()
		return self.app._gethandler(handler)

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

	def save(self, handler=None, recursive=True):
		self._gethandler(handler).save_internaltemplate(self)

	def delete(self, handler=None):
		self._gethandler(handler).delete_internaltemplate(self)


@register("viewtemplate")
class ViewTemplate(Template):
	class Type(misc.Enum):
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

	class Permission(misc.IntEnum):
		ALL = 0
		LOGGEDIN = 1
		APP = 2
		APPEDIT = 3
		APPADMIN = 4

	type = EnumAttr(Type, required=True, default=Type.LIST, ul4on=True, doc="The type of the view template (i.e. in which context it is used)")
	mimetype = Attr(str, default="text/html", ul4on=True, doc="The MIME type of the HTTP response of the view template")
	permission = IntEnumAttr(Permission, required=True, default=Permission.ALL, ul4on=True, doc="Who can access the template?")
	datasources = AttrDictAttr(required=True, ul4on=True, ul4onset="_datasources_ul4onset", ul4onsetdefault="_datasources_ul4onsetdefault", doc="Configured data sources")

	def __init__(self, id=None, *args, identifier=None, source=None, whitespace="keep", signature=None, doc=None, type=Type.LIST, mimetype="text/html", permission=None):
		super().__init__(id=id, identifier=identifier, source=source, whitespace=whitespace, signature=signature, doc=doc)
		self.type = type
		self.mimetype = mimetype
		self.permission = permission
		self.datasources = attrdict()
		for arg in args:
			if isinstance(arg, DataSource):
				self.adddatasource(arg)
			else:
				raise TypeError(f"don't know what to do with positional argument {arg!r}")

	def __str__(self):
		return f"{self.app or '?'}/viewtemplate={self.identifier}"

	def adddatasource(self, *datasources):
		for datasource in datasources:
			datasource.parent = self
			self.datasources[datasource.identifier] = datasource

	def _datasources_ul4onset(self, value):
		self.datasources = makeattrs(value)

	def _datasources_ul4onsetdefault(self):
		self.datasources = attrdict()

	def save(self, handler=None, recursive=True):
		self._gethandler(handler).save_viewtemplate(self)

	def delete(self, handler=None):
		self._gethandler(handler).delete_viewtemplate(self)


@register("datasource")
class DataSource(Base):
	ul4attrs = {"id", "parent", "identifier", "app", "includecloned", "appfilter", "includecontrols", "includerecords", "includecount", "recordpermission", "recordfilter", "includepermissions", "includeattachments", "includeparams", "includeviews", "includecategories", "orders", "children"}

	class IncludeControls(misc.IntEnum):
		"""
		Specify which controls should be included in the app and the records.

		Enum values have the following meaning:

		``NONE``
			Don't include any controls;

		``PRIORITY``
			Include only list/priority controls;

		``ALL``
			Include all controls.
		"""

		NONE = 0
		PRIORITY = 1
		ALL = 2
		ALL_LAYOUT = 3

	class IncludeRecords(misc.IntEnum):
		"""
		Specify wether controls and/or records should be included in the :class:`App` object.

		Enum values have the following meaning:

		``NONE``
			Don't include controls or records;

		``CONTROLS``
			Include control, but not records;

		``RECORDS``
			Include controls and records.
		"""

		NONE = 0
		CONTROLS = 1
		RECORDS = 2

	class RecordPermission(misc.IntEnum):
		NONE = -1
		CREATED = 0
		OWNED = 1
		OWNED_ALL = 2
		ALL = 3

	class IncludeCategories(misc.IntEnum):
		"""
		Specify how much information about app categories should be included in the :class:`App` object.

		Enum values have the following meaning:

		``NO``

		``PATH``

		``TREE``

		``APPS``
		"""

		NO = 0
		PATH = 1
		TREE = 2
		APPS = 3

	id = Attr(str, doc="Unique database id")
	parent = Attr(ViewTemplate, ul4on=True, doc="The view template this datasource belongs to")
	identifier = Attr(str, ul4on=True, doc="A unique identifier for the data source (unique among the other data sources of the view template)")
	app = Attr(App, ul4on=True, doc="The app from which records are fetched (or whose records are configured)")
	includecloned = BoolAttr(required=True, default=False, ul4on=True, doc="Should copies of the app referenced by ``app`` be included?")
	appfilter = VSQLAttr("vsqlsupport_pkg3.ds_appfilter_ful4on", ul4on=True, doc="vSQL expression for filtering which apps might be included (if more than one app is included)")
	includecontrols = IntEnumAttr(IncludeControls, required=True, default=IncludeControls.ALL, ul4on=True, doc="Which fields of the app should be included (in ``controls`` and ``records``)?")
	includerecords = IntEnumAttr(IncludeRecords, required=True, default=IncludeRecords.RECORDS, ul4on=True, doc="Should the app include neither records nor control information, or just control information or both?")
	includecount = BoolAttr(required=True, default=False, ul4on=True, doc="Should the number of records by output in ``recordcount``?")
	recordpermission = IntEnumAttr(RecordPermission, required=True, default=RecordPermission.ALL, ul4on=True, doc="Whose records should be output?")
	recordfilter = VSQLAttr("vsqlsupport_pkg3.ds_recordfilter_ful4on", ul4on=True, doc="A vSQL expression for filtering when records to include")
	includepermissions = BoolAttr(required=True, default=False, ul4on=True, doc="Include permisson information (ignored)")
	includeattachments = BoolAttr(required=True, default=False, ul4on=True, doc="Include record attachments?")
	includeparams = BoolAttr(required=True, default=False, ul4on=True, doc="Include app parameter?")
	includeviews = BoolAttr(required=True, default=False, ul4on=True, doc="Include views?")
	includecategories = IntEnumAttr(IncludeCategories, required=True, default=IncludeCategories.NO, ul4on=True, doc="Include navigation categories?")
	orders = Attr(ul4on=True, doc="The sort expressions for sorting the records dict")
	children = AttrDictAttr(required=True, ul4on=True, doc="Children configuration for records that reference the record from this app")

	def __init__(self, id=None, *args, identifier=None, app=None, includecloned=False, appfilter=None, includecontrols=None, includerecords=None, includecount=False, recordpermission=None, recordfilter=None, includepermissions=False, includeattachments=False, includeparams=False, includeviews=False, includecategories=None):
		self.id = id
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
		self.includeparams = includeparams
		self.includeviews = includeviews
		self.includecategories = includecategories
		self.orders = []
		self.children = None
		for arg in args:
			if isinstance(arg, DataOrder):
				self.addorder(arg)
			elif isinstance(arg, DataSourceChildren):
				self.addchildren(arg)
			else:
				raise TypeError(f"don't know what to do with positional argument {arg!r}")

	def __str__(self):
		return f"{self.parent or '?'}/datasource={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	@property
	def ul4onid(self):
		return self.id

	def addorder(self, *orders):
		for order in orders:
			order.parent = self
			self.orders.append(order)

	def addchildren(self, children):
		children.datasource = self
		self.children[children.identifier] = children

	def _gethandler(self, handler):
		if handler is None:
			if self.parent is None:
				raise NoHandlerError()
		return self.parent._gethandler(handler)

	def save(self, handler=None, recursive=True):
		self._gethandler(handler).save_datasource(self)


@register("datasourcechildren")
class DataSourceChildren(Base):
	ul4attrs = {"id", "datasource", "identifier", "control", "filters", "orders"}

	id = Attr(str, doc="Unique database id")
	datasource = Attr(ul4on=True, doc="The :class:`DataSource` this object belongs to")
	identifier = Attr(str, ul4on=True, doc="A unique identifier for this object (unique among the other :class:`DataSourceChildren` objects of the :class:`DataSource`)")
	control = Attr(Control, ul4on=True, doc="The :class:`AppLookupControl` object that references this app. All records from the controls app that reference our record will be added to the children dict.")
	filter = VSQLAttr("vsqlsupport_pkg3.dsc_recordfilter_ful4on", ul4on=True, doc="Additional vSQL filter for the records.")
	orders = Attr(ul4on=True, doc="The sort expressions for sorting the children dict.")

	def __init__(self, id=None, *args, identifier=None, control=None, filter=None):
		self.id = id
		self.datasource = None
		self.identifier = identifier
		self.control = control
		self.filter = filter
		self.orders = []
		for arg in args:
			if isinstance(arg, DataOrder):
				self.addorder(arg)
			else:
				raise TypeError(f"don't know what to do with positional argument {arg!r}")

	def __str__(self):
		return f"{self.datasource or '?'}/datasourcechildren={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	@property
	def ul4onid(self):
		return self.id

	def addorder(self, *orders):
		for order in orders:
			order.parent = self
			self.orders.append(order)

	def _gethandler(self, handler):
		if handler is None:
			if self.datasource is None:
				raise NoHandlerError()
		return self.datasource._gethandler(handler)

	def save(self, handler, recursive=True):
		self._gethandler(handler).save_datasourcechildren(self)


@register("dataorder")
class DataOrder(Base):
	ul4attrs = {"id", "parent", "expression", "direction", "nulls"}

	class Direction(misc.Enum):
		"""
		The sort direction.

		``ASC``
			Sort ascending (i.e. A to Z)

		``DESC``
			Sort descending (i.e. Z to A)
		"""

		ASC = "asc"
		DESC = "desc"

	class Nulls(misc.Enum):
		"""
		Specify where to sort null values.

		``FIRST``
			Null values come first.

		``LAST``
			Null values come last.
		"""

		FIRST = "first"
		LAST = "last"

	# Types and defaults for instance attributes
	id = Attr(str, doc="Unique database id")
	parent = Attr(DataSource, DataSourceChildren, ul4on=True, doc="The :class:`DataSource` or :class:`DataSourceChildren` this object belongs to")
	expression = VSQLAttr("?", repr=True, ul4on=True, doc="vSQL expression")
	direction = EnumAttr(Direction, required=True, default=Direction.ASC, repr=True, ul4on=True, doc="Sort direction (asc or desc)")
	nulls = EnumAttr(Nulls, required=True, default=Nulls.LAST, repr=True, ul4on=True, doc="Where to sort empty (``null``) values (first or last)")

	def __init__(self, id=None, expression=None, direction=Direction.ASC, nulls=Nulls.LAST):
		self.id = id
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

	@property
	def ul4onid(self):
		return self.id

	def save(self, handler=None, recursive=True):
		raise NotImplementedError("DataOrder objects can only be saved by their parent")


@register("dataaction")
class DataAction(Base):
	ul4attrs = {
		"id",
		"app",
		"identifier",
		"name",
		"order",
		"active",
		"icon",
		"description",
		"message",
		"filter",
		"commands",
	}

	id = Attr(str, repr=True, doc="Unique database id")
	app = Attr(App, ul4on=True, doc="The app this action belongs to")
	identifier = Attr(str, repr=True, ul4on=True, doc="Human readable identifier")
	name = Attr(str, repr=True, ul4on=True, doc="Human readable name")
	order = Attr(int, ul4on=True, doc="Used to sort the actions for display")
	active = BoolAttr(ul4on=True, doc="Is this action active (otherwise it willl be ignored for display/execution)")
	icon = Attr(str, ul4on=True, doc="Icon to display for the action")
	description = Attr(str, ul4on=True, doc="What does this action do?")
	message = Attr(str, ul4on=True, doc="Message to output after the action has been executed")
	filter = VSQLAttr("vsqlsupport_pkg3.da_filter_ful4on", ul4on=True, doc="vSQL expression that determines whether this action should be displayed/executed")
	as_multiple_action = BoolAttr(required=True, default=False, ul4on=True, doc="Should this action be displayed as a action button for multiple records in the datamanagement?")
	as_single_action = BoolAttr(required=True, default=False, ul4on=True, doc="Should this action be displayed as a action button for single records in the datamanagement?")
	as_mail_link = BoolAttr(required=True, default=False, ul4on=True, doc="Can this action be used as an email link (where clicking on the link in the email executes the action)?")
	before_update = BoolAttr(required=True, default=False, ul4on=True, doc="Execute before displaying an update form?")
	after_update = BoolAttr(required=True, default=False, ul4on=True, doc="Execute after updating the record?")
	before_insert = BoolAttr(required=True, default=False, ul4on=True, doc="Execute before displaying an insert form?")
	after_insert = BoolAttr(required=True, default=False, ul4on=True, doc="Execute after inserting the record?")
	before_delete = BoolAttr(required=True, default=False, ul4on=True, doc="Execute before deleting the record?")

	commands = Attr(ul4on=True)

	def __init__(self, id=None, identifier=None, name=None, order=None, active=True, icon=None, description=None, filter=None, as_multiple_action=None, as_single_action=None, as_mail_link=None, before_update=None, after_update=None, before_insert=None, after_insert=None, before_delete=None):
		self.id = id
		self.app = None
		self.identifier = identifier
		self.name = name
		self.order = order
		self.active = active
		self.icon = icon
		self.description = description
		self.filter = filter
		self.as_multiple_action = as_multiple_action
		self.as_single_action = as_single_action
		self.as_mail_link = as_mail_link
		self.before_update = before_update
		self.after_update = after_update
		self.before_insert = before_insert
		self.after_insert = after_insert
		self.before_delete = before_delete
		self.commands = []

	@property
	def ul4onid(self):
		return self.id

	def addcommand(self, *commands):
		for command in commands:
			command.parent = self
			self.commands.append(command)


class DataActionCommand(Base):
	ul4attrs = {
		"id",
		"parent",
		"condition",
		"details",
	}

	id = Attr(str, repr=True, doc="Unique database id")
	parent = Attr(ul4on=True, doc="The data action this command belongs to or the command this comamnd is a sub command of")
	condition = VSQLAttr("vsqlsupport_pkg3.dac_condition_ful4on", ul4on=True, doc="Only execute the command when this vSQL condition is true")
	details = Attr(ul4on=True, doc="Field expressions for each field of the target app or attribute of the command")

	def __init__(self, id=None, condition=None):
		self.id = id
		self.parent = None
		self.condition = condition
		self.details = []

	@property
	def ul4onid(self):
		return self.id

	def adddetail(self, *details):
		for detail in details:
			detail.parent = self
			self.details.append(detail)


@register("dataactioncommand_update")
class DataActionCommandUpdate(DataActionCommand):
	pass


@register("dataactioncommand_task")
class DataActionCommandTask(DataActionCommand):
	pass


@register("dataactioncommand_delete")
class DataActionCommandDelete(DataActionCommand):
	pass


@register("dataactioncommand_onboarding")
class DataActionCommandOnboarding(DataActionCommand):
	pass


@register("dataactioncommand_daterepeater")
class DataActionCommandDateRepeater(DataActionCommand):
	pass


class DataActionCommandWithIdentifier(DataActionCommand):
	ul4attrs = DataActionCommand.ul4attrs.union({
		"app",
		"identifier",
		"children",
	})

	app = Attr(App, ul4on=True, doc="The target app ")
	identifier = Attr(str, ul4on=True, doc="A variable name introduced by this command")
	children = Attr(ul4on=True, doc="The sucomamnds of this command")

	def __init__(self, id=None, condition=None, app=None, identifier=None):
		super().__init__(id, condition)
		self.app = app
		self.identifier = identifier
		self.children = []

	def addcommand(self, *commands):
		for command in commands:
			command.parent = self
			self.commands.append(command)


@register("dataactioncommand_insert")
class DataActionCommandInsert(DataActionCommandWithIdentifier):
	pass


@register("dataactioncommand_insertform")
class DataActionCommandInsertForm(DataActionCommandWithIdentifier):
	pass


@register("dataactioncommand_insertformstatic")
class DataActionCommandInsertFormStatic(DataActionCommandWithIdentifier):
	pass


@register("dataactioncommand_loop")
class DataActionCommandLoop(DataActionCommandWithIdentifier):
	pass


@register("dataactiondetail")
class DataActionDetail(Base):
	ul4attrs = {
		"id",
		"parent",
		"control",
		"type",
		"children",
	}

	class Type(misc.Enum):
		"""
		The type of action for this field/parameter.

		``SETNULL``
			Set to ``None``;

		``SETNOW``
			Set to the current date/time (for ``date`` or ``datetime`` fields);

		``SET``
			Set to a constant (in :attr:`value`);

		``ADD``
			Add a constant to the curent value (in :attr:`value`);

		``EXPR``
			Set the field to the value of a vSQL expression (in :attr:`expression`);
		"""

		SETNULL = "setnull"
		SETNOW = "setnow"
		SET = "set"
		ADD = "add"
		EXPR = "expr"

	class FormMode(misc.Enum):
		"""
		How to use the field in an interactive data action form.

		``EDIT``
			The value can be edited (the configured value is the default);

		``DISABLE``
			The value will be displayed, but can't be edited (the configured value
			will be the field value);

		``HIDE``
			The value will not be dsiplayed and can't be edited (the configured
			value will be the field value);
		"""

		EDIT = "edit"
		DISABLE = "disable"
		HIDE = "hide"

	id = Attr(str, repr=True, doc="Unique database id")
	parent = Attr(DataActionCommand, ul4on=True, doc="The data action command this detail belongs to")
	control = Attr(Control, ul4on=True, doc="The control this detail refers to (i.e. which field/attribute to modify)")
	type = EnumAttr(Type, ul4on=True, doc="The type of execute to execution on the field/attribute")
	value = Attr(ul4on=True, doc="The value to use (if the :attr:`type` isn't :obj:`Type.EXPR`)")
	expression = VSQLAttr("vsqlsupport_pkg3.dac_condition_ful4on", ul4on=True, doc="The vSQL expression used to set the field/attribute (if :attr:`type` is :obj:`Type.EXPR`)")
	formmode = EnumAttr(FormMode, ul4on=True, doc="How to display the field in interactive actions (i.e. ``insertform`` and ``insertformstatic``")

	code = Attr(str, repr=True, readonly=True, get="_code_get")

	def __init__(self, id=None, type=None, value=None, formmode=None):
		self.id = id
		self.parent = None
		self.control = None
		self.type = type
		self.value = value
		self.expression = None
		self.formmode = None

	@property
	def ul4onid(self):
		return self.id

	def _code_get(self):
		if self.type is DataActionDetail.Type.SETNULL:
			return f"(r.v_{self.control.identifier} = None)"
		elif self.type is DataActionDetail.Type.SETNOW:
			if self.control.subtype == "date":
				return f"(r.v_{self.control.identifier} = today())"
			else:
				return f"(r.v_{self.control.identifier} = now())"
		elif self.type is DataActionDetail.Type.SET:
			return f"(r.v_{self.control.identifier} = {self.value!r})"
		elif self.type is DataActionDetail.Type.ADD:
			return f"(r.v_{self.control.identifier} += {self.value!r})"
		elif self.type is DataActionDetail.Type.EXPR:
			return f"(r.v_{self.control.identifier} = {self.expression})"
		else:
			return None


@register("installation")
class Installation(Base):
	ul4attrs = {"id", "name"}

	id = Attr(str, repr=True, doc="Unique database id")
	name = Attr(str, repr=True, ul4on=True)

	def __init__(self, id=None, name=None):
		self.id = id
		self.name = name


class LayoutControl(Base):
	ul4attrs = {"id", "label", "identifier", "view", "type", "subtype", "top", "left", "width", "height"}

	id = Attr(str, repr=True, doc="Unique database id")
	label = Attr(str, repr=True, ul4on=True, doc="Label to be displayed for this control")
	identifier = Attr(str, repr=True, ul4on=True, doc="Human readable identifier")
	view = Attr(lambda: View, ul4on=True, doc="The view this layout control belongs to")
	top = Attr(int, ul4on=True, doc="Vertical position of this layout control in the form")
	left = Attr(int, ul4on=True, doc="Horizontal position of this layout control in the form")
	width = Attr(int, ul4on=True, doc="Width of this layout control in the form")
	height = Attr(int, ul4on=True, doc="height of this layout control in the form")

	def __init__(self, id=None, label=None, identifier=None):
		self.id = id
		self.label = label
		self.identifier = identifier

	@property
	def ul4onid(self):
		return self.id


@register("htmllayoutcontrol")
class HTMLLayoutControl(LayoutControl):
	type = "string"
	subtype = "html"
	ul4attrs = LayoutControl.ul4attrs.union({"value"})

	value = Attr(str, ul4on=True, doc="HTML source")


@register("imagelayoutcontrol")
class ImageLayoutControl(LayoutControl):
	type = "image"
	subtype = None

	ul4attrs = LayoutControl.ul4attrs.union({"image_original", "image_scaled"})

	image_original = Attr(File, ul4on=True, doc="Original uploaded image")
	image_scaled = Attr(File, ul4on=True, doc="image scaled to final size")


@register("view")
class View(Base):
	ul4attrs = {"id", "name", "app", "order", "width", "height", "start", "end", "controls", "layout_controls"}

	id = Attr(str, repr=True, doc="Unique database id")
	name = Attr(str, repr=True, ul4on=True)
	app = Attr(App, ul4on=True, doc="The app this view belongs to")
	order = Attr(int, ul4on=True, doc="Used to sort the views")
	width = Attr(int, ul4on=True, doc="Width of the view in pixels")
	height = Attr(int, ul4on=True, doc="height of the view in pixels")
	start = Attr(datetime.datetime, ul4on=True, doc="View is inactive before this date")
	end = Attr(datetime.datetime, ul4on=True, doc="View is inactive after this date")
	controls = AttrDictAttr(ul4on=True, doc="Additional information for the fields used in this view")
	layout_controls = AttrDictAttr(ul4on=True, doc="The layout controls used in this view")

	def __init__(self, id=None, name=None, app=None, order=None, width=None, height=None, start=None, end=None):
		self.id = id
		self.name = name
		self.app = app
		self.order = order
		self.width = width
		self.height = height
		self.start = start
		self.end = end

	@property
	def ul4onid(self):
		return self.id


@register("datasourcedata")
class DataSourceData(Base):
	ul4attrs = {"id", "identifier", "app", "apps"}

	id = Attr(str, repr=True, doc="Unique database id")
	identifier = Attr(str, repr=True, ul4on=True, doc="A unique identifier for the data source")
	app = Attr(App, ul4on=True, doc="The app reference by this datasource (or :const:`None` when the datasource is configured for all apps)")
	apps = AttrDictAttr(ul4on=True, doc="All apps that this datasource references (can only be more than one, if copies of this app or all apps are included)")

	def __init__(self, id=None, identifier=None, app=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.app = app
		self.apps = apps

	@property
	def ul4onid(self):
		return self.id


@register("lookupitem")
class LookupItem(Base):
	ul4attrs = {"key", "label"}

	key = Attr(str, repr=True, ul4on=True, doc="Human readable identifier")
	label = Attr(str, repr=True, ul4on=True, doc="Label to be displayed for this lookup item")

	def __init__(self, key=None, label=None):
		self.key = key
		self.label = label


@register("category")
class Category(Base):
	ul4attrs = {"id", "identifier", "name", "order", "parent", "children", "apps"}

	id = Attr(str, repr=True, doc="Unique database id")
	identifier = Attr(str, repr=True, ul4on=True, doc="Human readable identifier")
	name = Attr(str, repr=True, ul4on=True, doc="Label to be displayed for this category in the navigation")
	order = Attr(int, ul4on=True, doc="Used to order the categories in the navigation")
	parent = Attr(ul4on=True, doc="The parent category")
	children = Attr(ul4on=True, doc="The child categories")
	apps = Attr(ul4on=True, doc="The apps that belong to that category")

	def __init__(self, id=None, identifier=None, name=None, order=None, parent=None, children=None, apps=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.order = order
		self.parent = parent
		self.children = children
		self.apps = apps

	@property
	def ul4onid(self):
		return self.id


@register("appparameter")
class AppParameter(Base):
	ul4attrs = {"id", "app", "identifier", "description", "value", "createdat", "createdby", "updatedat", "updatedby"}

	id = Attr(str, repr=True, doc="Unique database id")
	app = Attr(App, ul4on=True, doc="The app this parameter belong to")
	identifier = Attr(str, repr=True, ul4on=True, doc="Human readable identifier")
	description = Attr(str, ul4on=True, doc="Description of the parameter")
	value = Attr(ul4on=True, doc="The parameter value. The type of the value depends on the type of the parameter")
	createdat = Attr(datetime.datetime, ul4on=True, doc="When was this parameter created?")
	createdby = Attr(User, ul4on=True, doc="Who created this parameter?")
	updatedat = Attr(datetime.datetime, ul4on=True, doc="When was this parameter last updated?")
	updatedby = Attr(User, ul4on=True, doc="Who updated this parameter last?")

	def __init__(self, id=None, app=None, identifier=None, description=None, value=None):
		self.id = id
		self.app = app
		self.identifier = identifier
		self.description = description
		self.value = value
		self.createdat = None
		self.createdby = None
		self.updatedat = None
		self.updatedby = None

	@property
	def ul4onid(self):
		return self.id


from .handlers import *
