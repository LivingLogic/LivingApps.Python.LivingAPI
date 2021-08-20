#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2021 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
:mod:`ll.la` provides a Python API for the LivingApps system.

See http://www.living-apps.de/ or http://www.living-apps.com/ for more info.
"""

import io, datetime, operator, string, json, pathlib, types

from ll import misc, ul4c, ul4on # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``


__docformat__ = "reStructuredText"


###
### Utility functions and classes
###

NoneType = type(None)

module = types.ModuleType("livingapps", "LivingAPI types")
module.ul4_attrs = {"__name__", "__doc__"}

def register(name):
	"""
	Since we must pass the ID as a keyword argument, we have to take the
	registration logic into our own hand.
	"""
	def registration(cls):
		if name is not None:
			cls.ul4onname = "de.livinglogic.livingapi." + name
			ul4on._registry[cls.ul4onname] = cls.ul4oncreate
		setattr(module, cls.__name__, cls.ul4_type)
		module.ul4_attrs.add(cls.__name__)
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
			raise AttributeError(error_attribute_doesnt_exist(self, key))

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


def error_attribute_doesnt_exist(instance, name):
	return f"{misc.format_class(instance)!r} object has no attribute {name!r}."


def error_attribute_readonly(instance, name):
	return f"Attribute {name!r} of {misc.format_class(instance)!r} object is read only."


def error_attribute_wrong_type(instance, name, value, allowed_types):
	if isinstance(allowed_types, tuple):
		allowed_types = format_list([format_class(t) for t in allowed_types])
	else:
		allowed_types = format_class(allowed_types)

	return f"Value for attribute {name!r} of {misc.format_class(instance)!r} object must be {allowed_types}, but is {format_class(type(value))}."


def attribute_wrong_value(instance, name, value, allowed_values):
	allowed_values = format_list([repr(value) for value in allowed_values])

	return f"Value for attribute {name!r} of {misc.format_class(instance)} object must be {allowed_values}, but is {value!r}."


def error_wrong_type(value):
	"""
	Return an error message for an unsupported field type.

	Used when setting a field to a value of the wrong type.
	"""
	return f"{misc.format_class(value)} is not supported."


def error_wrong_value(value):
	"""
	Return an error message for a field value that isn't supported.

	For example when a date field is set to a string value, but the string has
	an unrecognized format, this error message will be used.
	"""
	return f"Value {value!r} is not supported."


def error_lookupitem_unknown(value):
	r"""
	Return an error message for an unknown identifier for :class:`LookupItem`\s.

	Used when setting the field of a lookup control to an unknown identifier.
	"""
	return f"Lookup item {value!r} is unknown."


def error_lookupitem_foreign(value):
	"""
	Return an error message for a foreign :class:`LookupItem`.

	Used when setting the field of a lookup control to a :`class`LookupItem` that
	belongs to another :class:`LookupControl`.
	"""
	return f"Wrong lookup item {value!r}."


def error_applookuprecord_unknown(value):
	"""
	Return an error message for a unknown record identifier.

	Used when setting the field of an applookup control to a record identifier
	that can't be found in the target app.
	"""
	return f"Record with id {value!r} unknown."


def error_applookuprecord_foreign(value):
	"""
	Return an error message for a foreign :class:`Record`.

	Used when setting the field of an applookup control to a :class:`Record`
	object that belongs to the wrong app.
	"""
	return f"Record with id {value.id!r} is from wrong app."


def error_object_unsaved(value):
	"""
	Return an error message for an unsaved referenced object.
	"""
	return f"Referenced object {value!r} hasn't been saved yet."


def error_object_deleted(value):
	"""
	Return an error message for an deleted referenced object.
	"""
	return f"Referenced object {value!r} has been deleted."


def error_foreign_view(view):
	return f"View {view!r} belongs to the wrong app."


def error_view_not_found(viewid):
	return f"View with id {viewid!r} can't be found."

def _resolve_type(t):
	if not isinstance(t, type):
		t = t()
	return t


def _is_timezone(value):
	return value[0] in "+-" and value[1:3].isdigit() and value[3] == ":" and value[4:6].isdigit()


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

	def __init__(self, *types, required=False, default=None, default_factory=None, doc=None, repr=False, get=False, set=False, ul4get=False, ul4set=False, ul4onget=False, ul4onset=False, ul4ondefault=False):
		"""
		Create a new :class:`Attr` data descriptor.

		The type of the attribute will be checked when the attribute is set, it
		must be any of the types in :obj`types`. If no type is passed any type
		(i.e. any :class:`object`) is allowed. (Furthermore subclasses might
		implement certain type conversions on setting).

		If :object:`required` is :const:`False` the value :const:`None` is
		allowed too.

		:obj:`default` specifies the default value for the attribute (which is
		used if :const:`None` is used as the value).

		:obj:`default_factory` (if not :class:`None`) can be a callable that is
		used instead of :obj:`default` to create a default value.

		:obj:`doc` is used as the doc string of the descriptor.

		:obj:`repr`, :obj:`get`, :obj:`set`, :obj:`ul4get`, :obj:`ul4set`,
		:obj:`ul4onget`, :obj:`ul4onset` and :obj:`ul4ondefault` are used to
		configure the behaviour when this attribute is accessed in certain
		access scenarios.

		The following values are supported:

		:const:`False`
			The attribute is not available in this access scenario;

		:const:`True`
			The attribute is available in this access scenario and will be treated
			in a canonical way (e.g. getting the attribute simply returns the
			appropriate entry of the instance dict).

		``""`` (i.e. the empty string)
			The attribute will be accessed through a callback method of the owning
			class. The name is derived from the name of the attribute and access
			scenario, e.g. for getting the attribute named `foo` the method
			name will be ``"_foo_get"``, for setting it from UL4 it will be
			``"_foo_ul4set"`` etc.

		Any other string
			The attribute will be accessed through a callback method with this name.

		The access scenarios are the following:

		:obj:`repr`
			Include the attribute in the :func:`repr` output of its object.
			The canonical implementation will produce output in the form
			``f"{name}={value!r}"``, except when the value is :const:`None` in which
			case no output will be given. The signature of the callback method is
			``(instance)``.

		:obj:`get`
			Return the value of the attribute when accessed from Python.
			The canonical implementation will return the appropriate entry of the
			instance dict. The signature of the callback method is ``(instance)``.

		:obj:`set`
			Set the value of the attribute from Python. The canonical
			implementation will set the appropriate entry of the instance dict
			after checking the value against the types given by :obj:`types`
			and :obj:`required`. Subclasses might implement certain additional
			type conversions or checks. The signature of the callback method is
			``(instance, value)``.

		:obj:`ul4get`
			Return the value of the attribute when accessed from UL4. The canonical
			implementation will return the appropriate entry of the instance dict.
			The signature of the callback method is ``(instance)``.

		:obj:`ul4set`
			Set the value of the attribute from UL4. The canonical implementation
			will set the appropriate entry of the instance dict after checking
			the value against the types given by :obj:`types` and :obj:`required`.
			Subclasses might implement certain additional type conversions or
			checks. The signature of the callback method is ``(instance, value)``.

		:obj:`ul4onget`
			Return the value of the attribute for serialization via an UL4ON dump.
			The canonical implementation will use the appropriate entry of the
			instance dict. The signature of the callback method is ``(instance)``.

		:obj:`ul4onset`
			Set the value of the attribute from the deserialized value from an
			UL4ON dump. The canonical implementation will set the appropriate
			entry of the instance dict to the given value. No type checks will be
			performed. The signature of the callback method is``(instance, value)``.

		:obj:`ul4ondefault`
			Set the value of the attribute to its default value when no value
			is available from the UL4ON dump. The canonical implementation will
			set the appropriate entry of the instance dict to the default value
			(determined vie :obj:`default` und :obj:`default_factory`).
			The signature of the callback method is ``(instance)``.
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
		self.__doc__ = doc
		self._name_get = None
		self._name_set = None
		self._name_repr = None
		self._name_ul4get = None
		self._name_ul4set = None
		self._name_ul4onget = None
		self._name_ul4onset = None
		self._name_ul4ondefault = None
		# The following will be replaced by bound methods once we know the attribute name
		self.get = get
		self.set = set
		self.repr = repr
		self.ul4get = ul4get
		self.ul4set = ul4set
		self.ul4onget = ul4onget
		self.ul4onset = ul4onset
		# If the attribute should be settable via UL4ON we need a handler for ``ul4onset`` *and* ``ul4ondefault``
		if ul4onset is not False and ul4ondefault is False:
			ul4ondefault = True
		self.ul4ondefault = ul4ondefault # unknown until we know the name

	def _wireattr(self, cls, attrname, scenario, method_default, method_method, method_dont):
		attr = getattr(self, scenario)
		if isinstance(attr, str):
			if not attr:
				attr = f"_{attrname}_{scenario}"
			if not hasattr(cls, attr):
				raise TypeError(f"Required method {attr!r} missing in class {format_class(cls)}")
			setattr(self, f"_name_{scenario}", attr)
			setattr(self, scenario, method_method)
		elif getattr(self, scenario):
			setattr(self, scenario, method_default)
		else:
			setattr(self, scenario, method_dont)

	def __set_name__(self, owner, name):
		self.name = name
		self._wireattr(owner, name, "get", self._default_get, self._method_get, self._dont_get)
		self._wireattr(owner, name, "set", self._default_set, self._method_set, self._dont_set)
		self._wireattr(owner, name, "repr", self._default_repr, self._method_repr, self._dont_repr)
		self._wireattr(owner, name, "ul4get", self._default_ul4get, self._method_ul4get, self._dont_get)
		self._wireattr(owner, name, "ul4set", self._default_ul4set, self._method_ul4set, self._dont_set)
		self._wireattr(owner, name, "ul4onget", self._default_ul4onget, self._method_ul4onget, None)
		self._wireattr(owner, name, "ul4onset", self._default_ul4onset, self._method_ul4onset, None)
		self._wireattr(owner, name, "ul4ondefault", self._default_ul4ondefault, self._method_ul4ondefault, None)

	def _default_get(self, instance):
		return instance.__dict__[self.name]

	def _method_get(self, instance):
		return getattr(instance, self._name_get)()

	def _dont_get(self, instance):
		raise AttributeError(error_attribute_doesnt_exist(instance, self.name))

	def _default_set(self, instance, value):
		if value is None:
			value = self.make_default_value()
		if not isinstance(value, self.types):
			raise TypeError(error_attribute_wrong_type(instance, self.name, value, self.types))
		instance.__dict__[self.name] = value

	def _method_set(self, instance, value):
		return getattr(instance, self._name_set)(value)

	def _dont_set(self, instance, value):
		# If the attribute is not in the instance dict we allow setting it once.
		if self.name not in instance.__dict__:
			self._default_set(instance, value)
		else:
			raise AttributeError(error_attribute_readonly(instance, self.name))

	def _default_repr(self, instance):
		"""
		Format the attribute of :obj:`instance` for :meth:`__repr__` output.

		If :const:`None` is returned this attribute will not be output.
		"""
		value = self.get(instance)
		if value is not None:
			return f"{self.name}={value!r}"
		else:
			return None

	def _method_repr(self, instance):
		return getattr(instance, self._name_repr)()

	def _dont_repr(self, instance):
		return None

	def _default_ul4get(self, instance):
		return self._default_get(instance)

	def _method_ul4get(self, instance):
		return getattr(instance, self._name_ul4get)()

	def _default_ul4set(self, instance, value):
		self.set(instance, value)

	def _method_ul4set(self, instance, value):
		getattr(instance, self._name_ul4set)(value)

	def _default_ul4onget(self, instance):
		return self._default_get(instance)

	def _method_ul4onget(self, instance):
		return getattr(instance, self._name_ul4onget)()

	def _default_ul4onset(self, instance, value):
		self._default_set(instance, value)

	def _method_ul4onset(self, instance, value):
		getattr(instance, self._name_ul4onset)(value)

	def _default_ul4ondefault(self, instance):
		self.ul4onset(instance, self.make_default_value())

	def _method_ul4ondefault(self, instance):
		getattr(instance, self._name_ul4ondefault)()

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

	def __get__(self, instance, type=None):
		if instance is not None:
			return self.get(instance)
		else:
			for cls in type.__mro__:
				if self.name in cls.__dict__:
					return cls.__dict__[self.name]
			raise AttributeError(error_attribute_doesnt_exist(self, self.name))

	def __set__(self, instance, value):
		self.set(instance, value)

	def make_default_value(self):
		"""
		Return the default value for this attribute.

		This either calls :attr:`default_factory` or returns :attr:`default`.
		"""
		if self.default_factory is not None:
			return self.default_factory()
		else:
			return self.default

	def _ul4onget(self, instance):
		if isinstance(self.ul4onget, str):
			return getattr(instance, self.ul4onget)()
		elif self.ul4onget:
			return self.get(instance)
		else:
			raise AttributeError(error_attribute_doesnt_exist(instance, self.name))

	def _ul4onset(self, instance, value):
		if isinstance(self.ul4onset, str):
			getattr(instance, self.ul4onset)(value)
		elif self.ul4onset:
			self.set(instance, value)
		else:
			raise AttributeError(error_attribute_readonly(instance, self.name))


class BoolAttr(Attr):
	"""
	Subclass of :class:`Attr` for boolean values.

	Setting such an attribute also supports an integer as the value.
	"""

	def __init__(self, **kwargs):
		"""
		Create a :class:`BoolAttr` data descriptor.

		The supported type will be :class:`bool`. All other arguments have the
		same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(bool, **kwargs)

	def _default_set(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		If :obj:`value` is an :class:`int` it will be converted to :class:`bool`
		automatically.
		"""
		if isinstance(value, int):
			value = bool(value)
		super()._default_set(instance, value)


class FloatAttr(Attr):
	"""
	Subclass of :class:`Attr` for float values.

	Setting such an attribute also supports an integer as the value.
	"""

	def __init__(self, **kwargs):
		"""
		Create a :class:`BoolAttr` data descriptor.

		The supported type will be :class:`float`. All other arguments have the
		same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(float, **kwargs)

	def _default_set(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		If :obj:`value` is an :class:`int` it will be converted to :class:`float`
		automatically.
		"""
		if isinstance(value, int):
			value = float(value)
		super()._default_set(instance, value)


class EnumAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are :class:`~enum.Enum` instances.

	Setting such an attribute also supports a string as the value.
	"""

	def __init__(self, type, **kwargs):
		"""
		Create an :class:`EnumAttr` data descriptor.

		:obj:`type` must be a subclass of :class:`~enum.Enum`. All other
		arguments have the same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(type, **kwargs)
		self.type = type

	def _default_set(self, instance, value):
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
				values = [e.value for e in self.type]
				raise ValueError(attribute_wrong_value(instance, self.name, value, values))
		super()._default_set(instance, value)

	def _default_ul4get(self, instance):
		value = self.get(instance)
		if value is not None:
			value = value.value
		return value

	def _default_repr(self, instance):
		value = self.get(instance)
		if value is not None:
			return f"{self.name}={value.name!r}"
		else:
			return None


class IntEnumAttr(EnumAttr):
	"""
	Subclass of :class:`Attr` for values that are :class:`~enum.IntEnum` instances.

	Setting such an attribute also supports an integer as the value.
	"""

	def _default_set(self, instance, value):
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
				values = [e.value for e in self.type]
				raise ValueError(attribute_wrong_value(instance, self.name, value, values))
		super()._default_set(instance, value)


class VSQLAttr(Attr):
	"""
	Data descriptor for an attribute containing a vSQL expression.
	"""

	def __init__(self, function, **kwargs):
		"""
		Create an :class:`VSQLAttr` data descriptor.

		The supported type will be :class:`str`. :obj:`function` must be the
		name of a PL/SQL function for returning the UL4ON dump of the allowed
		vSQL variables.
		"""
		super().__init__(str, **kwargs)
		self.function = function


class AttrDictAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are dictionaries.

	Setting such an attribute convert a normal :class:`dict` into an
	:class:`attrdict` object.
	"""

	def __init__(self, **kwargs):
		"""
		Create an :class:`AttrDictAttr` data descriptor.
		"""
		if kwargs.get("required", False):
			super().__init__(dict, default_factory=attrdict, **kwargs)
		else:
			super().__init__(dict, **kwargs)

	def _default_set(self, instance, value):
		"""
		Set the value of this attribute of :obj:`instance` to :obj:`value`.

		if :obj:`value` is a :class:`dict` (but not an :class:`attrdict`) it will
		be converted to an :class:`attrdict` automatically.
		"""
		value = makeattrs(value)
		super()._default_set(instance, value)


###
### Core classes
###


class Base:
	ul4_attrs = set()

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

	@classmethod
	def ul4oncreate(cls, id=None):
		"""
		Alternative "constructor" used by the UL4ON machinery for creating new
		objects.

		The reason for this workaround is that
		"""
		return cls(id=id)

	def __repr__(self):
		v = [f"<{self.__class__.__module__}.{self.__class__.__qualname__}"]

		for attr in self.attrs():
			repr_value = attr.repr(self)
			if repr_value is not None:
				v.append(repr_value)
		v.append(f"at {id(self):#x}>")
		return " ".join(v)

	def ul4ondump(self, encoder):
		for attr in self.attrs():
			if attr.ul4onget is not None:
				value = attr.ul4onget(self)
				encoder.dump(value)

	def ul4onload(self, decoder):
		self.ul4onload_begin(decoder)
		attrs = (attr for attr in self.attrs() if attr.ul4onset is not None)
		dump = decoder.loadcontent()

		# Load all attributes that we get from the UL4ON dump
		# Stop when the dump is exhausted or we've loaded all known attributes.
		for (attr, value) in zip(attrs, dump):
			attr.ul4onset(self, value)

		# Exhaust the UL4ON dump
		for value in dump:
			pass

		# Initialize the rest of the attributes with default values
		for attr in attrs:
			attr.ul4ondefault(self)
		self.ul4onload_end(decoder)

	def ul4onload_begin(self, decoder):
		"""
		Called before the content of the object is loaded from an UL4ON dump.
		"""

	def ul4onload_end(self, decoder):
		"""
		Called after the content of the object has been loaded from an UL4ON dump.
		"""

	def ul4_getattr(self, name):
		attr = getattr(self.__class__, name, None)
		if isinstance(attr, Attr):
			return attr.ul4get(self)
		elif isinstance(attr, property):
			return attr.fget(self)
		elif self.ul4_hasattr(name):
			return getattr(self, name)
		raise AttributeError(error_attribute_doesnt_exist(self, name))

	def ul4_setattr(self, name, value):
		attr = getattr(self.__class__, name, None)
		if isinstance(attr, Attr):
			attr.ul4set(self, value)
		elif isinstance(attr, property):
			return attr.fset(self, value)
		raise AttributeError(error_attribute_doesnt_exist(self, name))



@register("flashmessage")
class FlashMessage(Base):
	ul4_attrs = {"timestamp", "type", "title", "message"}
	ul4_type = ul4c.Type("la", "FlashMessage", "A flash message in a web page")

	class Type(misc.Enum):
		"""
		The severity level of a :class:`FlashMessage`.
		"""

		INFO = "info"
		NOTICE = "notice"
		WARNING = "warning"
		ERROR = "error"

	timestamp = Attr(datetime.datetime, get=True, set=True, ul4onget=True, ul4onset=True)
	type = EnumAttr(Type, get=True, set=True, ul4onget=True, ul4onset=True)
	title = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)
	message = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)

	def __init__(self, timestamp=None, type=Type.INFO, title=None, message=None):
		self.timestamp = timestamp
		self.type = type
		self.title = title
		self.message = message


@register("file")
class File(Base):
	ul4_attrs = {"id", "url", "filename", "mimetype", "width", "height", "size", "createdat"}
	ul4_type = ul4c.Type("la", "File", "An uploaded file")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	url = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Server relative URL of the file")
	filename = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Original file name")
	mimetype = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="MIME type")
	width = Attr(int, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Width in pixels if this file is an image")
	height = Attr(int, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Height in pixels if this file is an image")
	internalid = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When was this file uploaded?")
	size = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The filesize in bytes")

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
	ul4_attrs = {"lat", "long", "info"}
	ul4_type = ul4c.Type("la", "Geo", "Geographical coordinates and location information")

	lat = FloatAttr(get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Latitude (i.e. north/south)")
	long = FloatAttr(get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Longitude (i.e. east/west)")
	info = Attr(str, get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Description of the location")

	def __init__(self, lat=None, long=None, info=None):
		self.lat = lat
		self.long = long
		self.info = info

	@classmethod
	def ul4oncreate(cls, id=None):
		return cls()


@register("user")
class User(Base):
	ul4_attrs = {
		"id", "gender", "title", "firstname", "surname", "initials", "email",
		"lang", "avatar_small", "avatar_large", "streetname", "streetnumber",
		"zip", "city", "phone", "fax", "summary", "interests", "personal_website",
		"company_website", "company", "position", "department", "keyviews"
	}
	ul4_type = ul4c.Type("la", "User", "A LivingApps user/account")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	publicid = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	gender = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	title = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	firstname = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	surname = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	initials = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	email = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Email address and account name")
	streetname = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Street name; part of the users address")
	streetnumber = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Street number; part of the users address")
	zip = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="ZIP code; part of the users address")
	city = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="City; part of the users address")
	phone = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	fax = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	lang = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Preferred language")
	avatar_small = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	avatar_large = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	summary = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	interests = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	personal_website = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	company_website = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	company = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	position = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	department = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="")
	keyviews = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self,
		id=None, gender=None, title=None, firstname=None, surname=None,
		initials=None, email=None, lang=None, avatar_small=None,
		avatar_large=None, streetname=None, streetnumber=None, zip=None,
		city=None, phone=None, fax=None, summary=None, interests=None,
		personal_website=None, company_website=None, company=None,
		position=None, department=None
	):
		self.id = id
		self.publicid = id
		self.gender = gender
		self.title = title
		self.firstname = firstname
		self.surname = surname
		self.initials = initials
		self.email = email
		self.lang = lang
		self.avatar_small = avatar_small
		self.avatar_large = avatar_large
		self.streetname = streetname
		self.streetnumber = streetnumber
		self.zip = zip
		self.city = city
		self.phone = phone
		self.fax = fax
		self.summary = summary
		self.interests = interests
		self.personal_website = personal_website
		self.company_website = company_website
		self.company = company
		self.position = position
		self.department = department
		self.keyviews = attrdict()

	@property
	def ul4onid(self):
		return self.id


@register("keyview")
class KeyView(Base):
	ul4_attrs = {"id", "identifier", "name", "key", "user"}
	ul4_type = ul4c.Type("la", "KeyView", "Object granting access to a view template")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="User supplied name")
	key = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Identifier used as final part of the URL")
	user = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="User, who should be considered to be the logged in user for the keyview")

	def __init__(self, identifier=None, name=None, key=None, user=None):
		self.id = None
		self.identifier = identifier
		self.name = name
		self.key = key
		self.user = user


@register("globals")
class Globals(Base):
	ul4_attrs = {
		"version",
		"hostname",
		"platform",
		"google_api_key",
		"mode",
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
	ul4_type = ul4c.Type("la", "Globals", "Global information")

	class Mode(misc.Enum):
		"""
		The type of template we're running.
		"""

		FORM_NEW_INIT = "form/new/init"
		FORM_NEW_LIVE = "form/new/live"
		FORM_NEW_ERROR = "form/new/error"
		FORM_NEW_SUCCESS = "form/new/success"
		FORM_EDIT_INIT = "form/edit/init"
		FORM_EDIT_LIVE = "form/edit/live"
		FORM_EDIT_ERROR = "form/edit/error"
		FORM_EDIT_SUCCESS = "form/edit/success"
		VIEW_LIST = "view/list"
		VIEW_DETAIL = "view/detail"
		VIEW_SUPPORT = "view/support"
		EMAIL_TEXT = "email/text"
		EMAIL_HTML = "email/html"

	version = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="API version (normally increases with every update of the LivingApps platform)")
	platform = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="A name for the platform we're running on")
	user = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The currently logging in user")
	maxdbactions = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="How many database actions may a template execute?")
	maxtemplateruntime = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="How long is a template allowed to run?")
	flashes = Attr(get=True, set=True, default_factory=list, ul4get=True, ul4onget=True, ul4onset=True, doc="List of flash messages")
	lang = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The language to be used by templates")
	datasources = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="", doc="Data for configured data sources")
	hostname = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The host name we're running on (can be used to recreate URLs)")
	app = Attr(lambda: App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app that the running template belongs to")
	record = Attr(lambda: Record, get=True, set=True, ul4get=True, ul4onget=True, ul4onset="", doc="The detail record")
	google_api_key = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Google API key (e.g. for using the Google Maps API)")
	mode = EnumAttr(Mode, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The type of template we're running")
	view_template_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True, doc="View template id of last database call")
	email_template_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True, doc="Email template id of last database call")
	view_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True, doc="View id of last database call")

	def __init__(self, id=None, version=None, hostname=None, platform=None, mode=None):
		self.version = version
		self.hostname = hostname
		self.platform = platform
		self.app = None
		self.record = None
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
		self.google_api_key = None
		self.mode = mode
		self.view_template_id = None
		self.email_template_id = None
		self.view_id = None

	@property
	def ul4onid(self):
		return "42"

	def _datasources_ul4onset(self, value):
		if value is not None:
			self.datasources = value

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
		raise AttributeError(error_attribute_doesnt_exist(self, name))

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

	def ul4_setattr(self, name, value):
		if name == "lang":
			self.lang = value
		elif self.ul4_hasattr(name):
			raise AttributeError(error_attribute_readonly(self, name))
		else:
			raise AttributeError(error_attribute_doesnt_exist(self, name))

	def ul4_hasattr(self, name):
		if name in self.ul4_attrs:
			return True
		elif self.datasources and name.startswith("d_") and name[2:] in self.datasources:
			return True
		elif name.startswith("t_") and name[2:] in self.templates:
			return True
		else:
			return False


@register("app")
class App(Base):
	ul4_attrs = {
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
	ul4_type = ul4c.Type("la", "App", "A LivingApps application")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	globals = Attr(Globals, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The :class:`Globals` objects")
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Name of the app")
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Description of the app")
	lang = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The language the app should be displayed in")
	startlink = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	iconlarge = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Large version of app icon")
	iconsmall = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Small version of app icon")
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Who created this app?")
	controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The definition of the fields of this app")
	records = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="", doc="The records of this app (if configured)")
	recordcount = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset="", doc="The number of records in this app (if configured)")
	installation = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The installation that created this app")
	categories = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="", doc="The navigation categories the currently logged in user put this app in")
	params = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="", doc="Application specific configuration parameters")
	views = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	datamanagement_identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	basetable = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Name of table or view records of this app are stored in")
	primarykey = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Name of the primary key of the table/view records of this app are stored in")
	insertprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Procedure for inserting new records of this app")
	updateprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Procedure for updating existing records of this app")
	deleteprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Procedure for deleting existing records of this app")
	_templates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When was this app created?")
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When was this app last changed?")
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When changed this app last?")
	superid = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Database id of the app this one was copied from")
	favorite = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Is this app a favorite of the currently logged in user?")
	active_view = Attr(lambda: View, str, get=True, set="", ul4get=True, ul4set=True, ul4onget=True, ul4onset=True, doc="Honor information of this view in the control objects")
	internaltemplates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Internal templates of this app")
	viewtemplates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="View templates of this app")
	dataactions = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Data actions of this app")

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
		self.active_view = None
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

	def _active_view_set(self, value):
		if isinstance(value, View):
			if value.app is not self:
				raise ValueError(error_foreign_view(value))
		elif isinstance(value, str):
			if self.views is None or value not in self.views:
				raise ValueError(error_view_not_found(value))
			value = self.views[value]
		elif value is not None:
			raise AttributeError(error_attribute_wrong_type(self, "active_view", value, (View, str)))
		self.__dict__["active_view"] = value

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
		raise AttributeError(error_attribute_doesnt_exist(self, name)) from None

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

	def ul4_hasattr(self, name):
		if name in self.ul4_attrs:
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
		return self

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
		return self

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
	_type = None
	_subtype = None
	ul4_attrs = {"id", "identifier", "app", "label", "type", "subtype", "fulltype", "priority", "order", "default", "ininsertprocedure", "inupdateprocedure"}
	ul4_type = ul4c.Type("la", "Control", "Metainformation about a field in a LivingApps application")

	class Mode(misc.Enum):
		DISPLAY = "display"
		EDIT = "edit"

	class LabelPos(misc.Enum):
		LEFT = "left"
		RIGHT = "right"
		TOP = "top"
		BOTTOM = "bottom"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	type = Attr(str, get="", ul4get="_type_get", doc="The type of the control")
	subtype = Attr(str, get="", ul4get="_subtype_get", doc="The subtype of the control (depends on the type and might be ``None``)")
	fulltype = Attr(str, get="", ul4get="_fulltype_get", doc="The full type (in the form ``type/subtype``)")
	field = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Name of the database field")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="App this control belongs to")
	label = Attr(str, get="", set=True, ul4get="_label_get", ul4onget=True, ul4onset=True, doc="Label to be displayed for this control")
	priority = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Has this control high priority, i.e. should it be displayed in lists?")
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Used to sort the controls")
	default = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The default value")
	ininsertprocedure = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Can a value for this field be passed to the insert procedure?")
	inupdateprocedure = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Can a value for this field be passed to the update procedure?")
	top = Attr(int, get="", ul4get="_top_get", doc="Top edge on screen in the input form (from the active view, else None)")
	left = Attr(int, get="", ul4get="_left_get", doc="Left edge on screen in the input form (from the active view, else None)")
	width = Attr(int, get="", ul4get="_width_get", doc="Width on screen in the input form (from the active view, else None)")
	height = Attr(int, get="", ul4get="_height_get", doc="Height on screen in the input form (from the active view, else None)")
	liveupdate = BoolAttr(get="", ul4get="_liveupdate_get", doc="Call form template when the value of this field changes? (from the active view, else False)")
	tabindex = Attr(int, get="", ul4get="_tabindex_get", doc="Tab order in the input form (from the active view, else None)")
	required = BoolAttr(get="", ul4get="_required_get", doc="Is a value required for this field? (from the active view, else False)")
	mode = EnumAttr(Mode, get="", ul4get="", doc="How to display this control in this view? (from the active view, else EDIT)")
	labelpos = EnumAttr(LabelPos, get="", ul4get="", doc="Position of the form label relative to the input field (from the active viewl, else LEFT, hide label if None).")
	in_activ_view = BoolAttr(get="", ul4get="_in_activ_view_get", doc="Is this control in the currently active view")

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

	def _type_get(self):
		return self._type

	def _subtype_get(self):
		return self._subtype

	def _fulltype_get(self):
		return self._fulltype

	def _get_viewcontrol(self):
		view = self.app.active_view
		if view is not None and view.controls is not None:
			return view.controls.get(self.identifier)
		return None

	def _label_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.label
		return self.__dict__["label"]

	def _top_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.top
		return None

	def _left_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.left
		return None

	def _width_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.width
		return None

	def _height_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.height
		return None

	def _liveupdate_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.liveupdate
		return False

	def _tabindex_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.tabindex
		return None

	def _required_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.required
		return False

	def _mode_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.mode
		return Control.Mode.EDIT

	def _mode_ul4get(self):
		mode = self._mode_get()
		if mode is not None:
			return mode.value
		return None

	def _labelpos_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.labelpos
		return Control.LabelPos.LEFT

	def _labelpos_ul4get(self):
		labelpos = self._labelpos_get()
		if labelpos is not None:
			return labelpos.value
		return None

	def _in_activ_view_get(self):
		vc = self._get_viewcontrol()
		return vc is not None

	def _set_value(self, field, value):
		field._value = value

	def _asdbarg(self, handler, field):
		return field._value

	def _asjson(self, handler, field):
		return self._asdbarg(handler, field)


class StringControl(Control):
	_type = "string"
	ul4_type = ul4c.Type("la", "StringControl", "A LivingApps string field")

	minlength = Attr(int, get="", ul4get="_minlength_get", doc="The minimum allowed string length (``None`` means unlimited).")
	maxlength = Attr(int, get="", ul4get="_maxlength_get", doc="The maximum allowed string length (``None`` means unlimited).")
	placeholder = Attr(str, get="", ul4get="_placeholder_get", doc="The placeholder for the HTML input.")

	def _minlength_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.minlength
		return 0

	def _maxlength_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.maxlength
		return 4000

	def _placeholder_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.placeholder
		return None

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, str):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value


@register("textcontrol")
class TextControl(StringControl):
	_subtype = "text"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "TextControl", "A LivingApps text field (type 'string/text')")


@register("urlcontrol")
class URLControl(StringControl):
	_subtype = "url"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "URLControl", "A LivingApps URL field (type 'string/url')")


@register("emailcontrol")
class EmailControl(StringControl):
	_subtype = "email"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "EmailControl", "A LivingApps email field (type 'string/email')")


@register("passwordcontrol")
class PasswordControl(StringControl):
	_subtype = "password"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "PasswordControl", "A LivingApps email field (type 'string/email')")


@register("telcontrol")
class TelControl(StringControl):
	_subtype = "tel"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "TelControl", "A LivingApps phone number field (type 'string/tel')")


class EncryptionType(misc.IntEnum):
	NONE = 0
	FORCE = 1
	OPTIONAL = 2


@register("textareacontrol")
class TextAreaControl(StringControl):
	_subtype = "textarea"
	_fulltype = f"{StringControl._type}/{_subtype}"

	ul4_attrs = StringControl.ul4_attrs.union({"encrypted"})
	ul4_type = ul4c.Type("la", "TextAreaControl", "A LivingApps textarea field (type 'string/textarea')")

	encrypted = IntEnumAttr(EncryptionType, get=True, set=True, default=EncryptionType.NONE, ul4get=True, ul4onget=True, ul4onset=True, doc="Is this field encrypted (and how/when will it be encrypted)?")

	def _maxlength_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.maxlength
		return None


@register("htmlcontrol")
class HTMLControl(StringControl):
	_subtype = "html"
	_fulltype = f"{StringControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "HTMLControl", "A LivingApps HTML field (type 'string/html')")


@register("intcontrol")
class IntControl(Control):
	_type = "int"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "IntControl", "A LivingApps integer field (type 'int')")

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, int):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value


@register("numbercontrol")
class NumberControl(Control):
	_type = "number"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "NumberControl", "A LivingApps number field (type 'number')")

	def _set_value(self, field, value):
		if value is not None and not isinstance(value, (int, float)):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value


@register("datecontrol")
class DateControl(Control):
	_type = "date"
	_subtype = "date"
	_fulltype = f"{_type}/{_subtype}"

	ul4_attrs = Control.ul4_attrs.union({"format"})
	ul4_type = ul4c.Type("la", "DateControl", "A LivingApps date field (type 'date/date')")

	format = Attr(str, get="", ul4get="_format_get", doc="UL4 format string for formatting values of this type (depends on ``globals.lang``")

	def _set_value(self, field, value):
		if isinstance(value, datetime.datetime):
			value = value.date()
		elif isinstance(value, str):
			charcount = len(value)
			if charcount == 10:
				try:
					value = datetime.date.fromisoformat(value)
				except ValueError:
					field.add_error(error_wrong_value(value))
			elif charcount == 19 or charcount == 26:
				try:
					value = datetime.datetime.fromisoformat(value)
				except ValueError:
					field.add_error(error_wrong_value(value))
				else:
					value = value.date()
			elif charcount == 25 or charcount == 32 and _is_timezone(value[-6:]):
				try:
					value = datetime.datetime.fromisoformat(value[:-6])
				except ValueError:
					field.add_error(error_wrong_value(value))
				else:
					value = value.date()
			else:
				field.add_error(error_wrong_value(value))
		elif value is not None and not isinstance(value, datetime.date):
			field.add_error(error_wrong_type(value))
			value = None
		field._value = value

	def _asjson(self, handler, field):
		value = field._value
		if isinstance(value, datetime.date):
			value = value.strftime("%Y-%m-%d")
		return value

	def _format_get(self):
		lang = self.app.globals.lang
		if lang in {"de", "fr", "it"}:
			return "%d.%m.%Y"
		else:
			return "%m/%d/%Y"


@register("datetimeminutecontrol")
class DatetimeMinuteControl(DateControl):
	_subtype = "datetimeminute"
	_fulltype = f"{DateControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "DatetimeMinuteControl", "A LivingApps date field (type 'date/datetimeminute')")

	def _set_value(self, field, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(second=0, microsecond=0)
		elif isinstance(value, datetime.date):
			value = datetime.datetime.combine(value, datetime.time())
		elif isinstance(value, str):
			charcount = len(value)
			if charcount == 10:
				try:
					value = datetime.datetime.fromisoformat(value)
				except ValueError:
					field.add_error(error_wrong_value(value))
			elif charcount == 19 or charcount == 26:
				try:
					value = datetime.datetime.fromisoformat(value)
				except ValueError:
					field.add_error(error_wrong_value(value))
				else:
					value = value.replace(second=0, microsecond=0)
			elif charcount == 25 or charcount == 32 and _is_timezone(value[-6:]):
				try:
					value = datetime.datetime.fromisoformat(value[:-6])
				except ValueError:
					field.add_error(error_wrong_value(value))
				else:
					value = value.replace(second=0, microsecond=0)
			else:
				field.add_error(error_wrong_value(value))
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

	def _format_get(self):
		lang = self.app.globals.lang
		if lang in {"de", "fr", "it"}:
			return "%d.%m.%Y %H:%M"
		else:
			return "%m/%d/%Y %H:%M"


@register("datetimesecondcontrol")
class DatetimeSecondControl(DateControl):
	_subtype = "datetimesecond"
	_fulltype = f"{DateControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "DatetimeSecondControl", "A LivingApps date field (type 'date/datetimesecond')")

	def _set_value(self, field, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(microsecond=0)
		elif isinstance(value, datetime.date):
			value = datetime.datetime.combine(value, datetime.time())
		elif isinstance(value, str):
			charcount = len(value)
			if charcount == 10:
				try:
					value = datetime.datetime.fromisoformat(value)
				except ValueError:
					field.add_error(error_wrong_value(value))
			elif charcount == 19 or charcount == 26:
				try:
					value = datetime.datetime.fromisoformat(value)
				except ValueError:
					field.add_error(error_wrong_value(value))
				else:
					value = value.replace(microsecond=0)
			elif charcount == 25 or charcount == 32 and _is_timezone(value[-6:]):
				try:
					value = datetime.datetime.fromisoformat(value[:-6])
				except ValueError:
					field.add_error(error_wrong_value(value))
				else:
					value = value.replace(microsecond=0)
			else:
				field.add_error(error_wrong_value(value))
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

	def _format_get(self):
		lang = self.app.globals.lang
		if lang in {"de", "fr", "it"}:
			return "%d.%m.%Y %H:%M:%S"
		else:
			return "%m/%d/%Y %H:%M:%S"


@register("boolcontrol")
class BoolControl(Control):
	_type = "bool"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "BoolControl", "A LivingApps boolean field (type 'bool')")

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
	_type = "lookup"

	ul4_attrs = Control.ul4_attrs.union({"lookupdata"})
	ul4_type = ul4c.Type("la", "LookupControl", "A LivingApps lookup field")

	lookupdata = AttrDictAttr(get=True, set=True, required=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The possible values this control might have")
	none_key = Attr(str, get="", ul4get="_none_key_get", doc='Key to use for a "Nothing selected" option. (from the active view, else None)')
	none_label = Attr(str, get="", ul4get="_none_label_get", doc='Label to display for a "Nothing selected" option. (from the active view, else None)')

	def __init__(self, id=None, identifier=None, field=None, label=None, priority=None, order=None, default=None, lookupdata=None):
		super().__init__(id=id, identifier=identifier, field=field, label=label, priority=priority, order=order, default=default)
		self.lookupdata = lookupdata

	def _none_key_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.lookup_none_key
		return None

	def _none_label_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.lookup_none_label
		return None

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


@register("lookupselectcontrol")
class LookupSelectControl(LookupControl):
	_subtype = "select"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupSelectControl", "A LivingApps lookup field (type 'lookup/select')")


@register("lookupradiocontrol")
class LookupRadioControl(LookupControl):
	_subtype = "radio"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupRadioControl", "A LivingApps lookup field (type 'lookup/radio')")


@register("lookupchoicecontrol")
class LookupChoiceControl(LookupControl):
	_subtype = "choice"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupChoiceControl", "A LivingApps lookup field (type 'lookup/choice')")


class AppLookupControl(Control):
	_type = "applookup"

	ul4_attrs = Control.ul4_attrs.union({"lookup_app", "lookup_controls", "lookupapp", "lookupcontrols"})
	ul4_type = ul4c.Type("la", "AppLookupControl", "A LivingApps applookup field")

	lookup_app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lookup_controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	local_master_control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	local_detail_controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	remote_master_control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	none_key = Attr(str, get="", ul4get="_none_key_get", doc='Key to use for a "Nothing selected" option. (from the active view, else None)')
	none_label = Attr(str, get="", ul4get="_none_label_get", doc='Label to display for a "Nothing selected" option. (from the active view, else None)')

	def __init__(self, id=None, identifier=None, field=None, label=None, priority=None, order=None, default=None, lookup_app=None, lookup_controls=None, local_master_control=None, local_detail_controls=None, remote_master_control=None):
		super().__init__(id=id, identifier=identifier, field=field, label=label, priority=priority, order=order, default=default)
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

	def _none_key_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.lookup_none_key
		return None

	def _none_label_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.lookup_none_label
		return None

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

	# The following two properties are for backwards compatibility

	@property
	def lookupcontrols(self):
		return self.lookup_controls

	@property
	def lookupapp(self):
		return self.lookup_app


@register("applookupselectcontrol")
class AppLookupSelectControl(AppLookupControl):
	_subtype = "select"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupSelectControl", "A LivingApps applookup field (type 'applookup/select')")


@register("applookupradiocontrol")
class AppLookupRadioControl(AppLookupControl):
	_subtype = "radio"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupRadioControl", "A LivingApps applookup field (type 'applookup/radio')")


@register("applookupchoicecontrol")
class AppLookupChoiceControl(AppLookupControl):
	_subtype = "choice"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupChoiceControl", "A LivingApps applookup field (type 'applookup/choice')")


class MultipleLookupControl(LookupControl):
	_type = "multiplelookup"

	ul4_type = ul4c.Type("la", "MultipleLookupControl", "A LivingApps multiplelookup field")

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
	_subtype = "select"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupSelectControl", "A LivingApps multiplelookup field (type 'multiplelookup/select')")


@register("multiplelookupcheckboxcontrol")
class MultipleLookupCheckboxControl(MultipleLookupControl):
	_subtype = "checkbox"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupCheckboxControl", "A LivingApps multiplelookup field (type 'multiplelookup/checkbox')")


@register("multiplelookupchoicecontrol")
class MultipleLookupChoiceControl(MultipleLookupControl):
	_subtype = "choice"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupChoiceControl", "A LivingApps multiplelookup field (type 'multiplelookup/choice')")


class MultipleAppLookupControl(AppLookupControl):
	_type = "multipleapplookup"

	ul4_type = ul4c.Type("la", "MultipleAppLookupControl", "A LivingApps multiple applookup field")

	def _set_value(self, field, value):
		if value is None:
			field._value = []
		elif isinstance(value, (str, Record)):
			self._set_value(field, [value])
		elif isinstance(value, list):
			field._value = []
			dat_ids = [v for v in value if isinstance(v, str)]
			if dat_ids:
				fetched = self.app.globals.handler.records_sync_data(dat_ids)
			else:
				fetched = []
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
	_subtype = "select"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupSelectControl", "A LivingApps multiple applookup field (type 'multipleapplookup/select')")


@register("multipleapplookupcheckboxcontrol")
class MultipleAppLookupCheckboxControl(MultipleAppLookupControl):
	_subtype = "checkbox"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupCheckboxControl", "A LivingApps multiple applookup field (type 'multipleapplookup/checkbox')")


@register("multipleapplookupchoicecontrol")
class MultipleAppLookupChoiceControl(MultipleAppLookupControl):
	_subtype = "choice"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupChoiceControl", "A LivingApps multiple applookup field (type 'multipleapplookup/choice')")


@register("filecontrol")
class FileControl(Control):
	_type = "file"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "FileControl", "A LivingApps upload field (type 'file')")

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
	_subtype = "signature"
	_fulltype = f"{FileControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "FileSignatureControl", "A LivingApps signature image field (type 'file/signature')")


@register("geocontrol")
class GeoControl(Control):
	_type = "geo"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "GeoControl", "A LivingApps geo field (type 'geo')")

	def _set_value(self, field, value):
		if isinstance(value, str):
			parts = value.split(",", 2)
			if len(parts) != 3:
				field.add_error(error_wrong_value(value))
			else:
				try:
					lat = float(parts[0])
					long = float(parts[1])
				except ValueError:
					field.add_error(error_wrong_value(value))
				else:
					value = Geo(lat, long, parts[2].strip())
		elif value is not None and not isinstance(value, Geo):
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
	ul4_attrs = {"id", "label", "identifier", "type", "subtype", "view", "control", "type", "subtype", "top", "left", "width", "height", "liveupdate", "default", "tabIndex", "minlength", "maxlength", "required", "placeholder", "mode", "labelpos", "lookup_none_key", "lookup_none_label", "lookupdata", "autoalign", "labelwidth", "autoexpandable"}
	ul4_type = ul4c.Type("la", "ViewControl", "Contains view specific information aboutn a control")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	identifier = Attr(str, get="", repr=True, ul4get="_identifier_get", doc="identifier of the control of this viewcontrol")
	type = Attr(str, get="", repr=True, ul4get="_type_get", doc="Type of the control of this viewcontrol")
	subtype = Attr(str, get="", repr=True, ul4get="_subtype_get", doc="Subtype of the control of this viewcontrol")
	view = Attr(lambda: View, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The view this view control belongs to.")
	control = Attr(lambda: Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The control for which this view control contains view specific info.")
	top = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Top edge on screen in the input form.")
	left = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Lfft edge on screen in the input form.")
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Width on screen in the input form.")
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Height on screen in the input form.")
	liveupdate = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Call form template when the value of this field changes?")
	default = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The default value for the field when no specific field value is given (only for string, date and lookup)")
	tabindex = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Tab order in the input form.")
	minlength = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The minimum allowed string length (``None`` means unlimited).")
	maxlength = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The maximum allowed string length (``None`` means unlimited).")
	required = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Is a value required for this field?")
	placeholder = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The placeholder for the HTML input.")
	mode = EnumAttr(Control.Mode, get=True, set=True, required=True, default=Control.Mode.EDIT, ul4onget="", ul4onset="", ul4ondefault="", doc="How to display this control in this view.")
	labelpos = EnumAttr(Control.LabelPos, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Position of the form label relative to the input field (hide label if ``None``).")
	lookup_none_key = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="""Key to use for a "Nothing selected" option (Don't display such an option if ``None``).""")
	lookup_none_label = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="""Label to display for a "Nothing selected" option (Use a generic label if ``None``).""")
	label = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="View specific version of the label.")
	autoalign = BoolAttr(get=True, set=True, required=True, default=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Is the label width automatically determined by the form builder?")
	labelwidth = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Width of the label on screen.")
	lookupdata = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Lookup items for the control in this view.")
	autoexpandable = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Automatically add missing items?")

	def __init__(self, id):
		self.id = id
		self.view = None
		self.control = None
		self.top = None
		self.left = None
		self.width = None
		self.height = None
		self.liveupdate = False
		self.default = None
		self.tabindex = None
		self.minlength = None
		self.maxlength = None
		self.required = None
		self.placeholder = None
		self.mode = Control.Mode.EDIT
		self.labelpos = None
		self.lookup_none_key = None
		self.lookup_none_label = None
		self.label = None
		self.autoalign = True
		self.labelwidth = None
		self.lookupdata = None
		self.autoexpandable = False

	@property
	def ul4onid(self):
		return self.id

	def _identifier_get(self):
		return self.control.identifier

	def _type_get(self):
		return self.control.type

	def _subtype_get(self):
		return self.control.subtype

	def _mode_ul4onget(self):
		return mode is Control.Mode.DISPLAY

	def _mode_ul4onset(self, value):
		self.mode = Control.Mode.DISPLAY if value else Control.Mode.EDIT

	def _mode_ul4ondefault(self):
		self.mode = Control.Mode.EDIT


@register("record")
class Record(Base):
	ul4_attrs = {"id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "fields", "values", "children", "attachments", "errors", "has_errors", "add_error", "clear_errors", "is_deleted", "save", "update", "executeaction", "state"}
	ul4_type = ul4c.Type("la", "Record", "A record of a LivingApp application")

	class State(misc.Enum):
		"""
		The database synchronisation state of the record.
		"""

		NEW = "new"
		SAVED = "saved"
		CHANGED = "changed"
		DELETED = "deleted"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	state = EnumAttr(State, get="", required=True, repr=True, ul4get="", doc="The state of synchronisation with the database for this record")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app this record belongs to")
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When was this record created?")
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Who created this record?")
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When was this record last updated?")
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Who updated this record last?")
	updatecount = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="How often has this record been updated?")
	fields = AttrDictAttr(get="", ul4get="_fields_get", doc="Dictionary containing :class:`Field` objects (with values, errors, etc) for each field")
	values = AttrDictAttr(get="", set=True, ul4get="_values_get", ul4onget=True, ul4onset="", doc="Dictionary containing the field values for each field")
	attachments = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Attachments for this record (if configured)")
	children = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="", doc="Detail records, i.e. records that have a field pointing back to this record")

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
			fields = self.fields
			for field in fields.values():
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
		return self._state_get().name

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
			v.append(f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r} state={self.state.name}")
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
				p.text(f"state={self.state.name}")
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
			elif name in self.__class__.__dict__:
				attr = getattr(self.__class__, name)
				if isinstance(attr, Attr):
					return attr.get(self)
		except KeyError:
			pass
		raise AttributeError(error_attribute_doesnt_exist(self, name)) from None

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
		raise AttributeError(error_attribute_readonly(self, name))

	def __dir__(self):
		"""
		Make keys completeable in IPython.
		"""
		return set(super().__dir__()) | {f"f_{identifier}" for identifier in self.app.controls} | {f"v_{identifier}" for identifier in self.app.controls} | {f"c_{identifier}" for identifier in self.children}

	def ul4_hasattr(self, name):
		if name in self.ul4_attrs:
			return True
		elif name.startswith(("f_", "v_")):
			return name[2:] in self.app.controls
		elif name.startswith("c_"):
			return name[2:] in self.children
		return False

	def ul4_getattr(self, name):
		attr = getattr(self.__class__, name, None)
		if isinstance(attr, Attr):
			return attr.ul4get(self)
		elif self.ul4_hasattr(name):
			# For these method call the version of the method instead, that doesn't
			# support the ``handler`` parameter.
			if name in {"save", "delete", "executeaction"}:
				return getattr(self, "ul4" + name)
			else:
				return getattr(self, name)
		raise AttributeError(error_attribute_doesnt_exist(self, name))

	def ul4_setattr(self, name, value):
		if name.startswith("v_") and name[2:] in self.app.controls:
			setattr(self, name, value)
		else:
			raise AttributeError(error_attribute_readonly(self, name))

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

	def ul4save(self, force=False):
		return self.save(force=force)

	def ul4delete(self):
		self.delete()

	def ul4executeaction(self, identifier=None):
		self.executeaction(identifier=identifier)

	def has_errors(self):
		if self.errors:
			return True
		elif self._sparsevalues is not None:
			# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't contain errors
			return False
		else:
			return any(field.has_errors() for field in self.fields.values())

	def add_error(self, *errors):
		self.errors.extend(errors)

	def clear_errors(self):
		# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't contain errors
		if self._sparsevalues is None:
			for field in self.fields.values():
				field.clear_errors()
		self.errors = []

	def check_errors(self):
		if self.errors:
			raise RecordValidationError(self, self.errors[0])
		# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't contain errors
		if self._sparsevalues is None:
			for field in self.fields.values():
				field.check_errors()

	def is_dirty(self):
		if self.id is None:
			return True
		elif self._sparsevalues is not None:
			# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't be dirty
			return False
		else:
			return any(field._dirty for field in self.fields.values())

	def is_deleted(self):
		return self._deleted

	def is_new(self):
		return self._new


class Field:
	ul4_attrs = {"control", "record", "label", "lookupdata", "value", "is_empty", "is_dirty", "errors", "has_errors", "add_error", "clear_errors", "enabled", "writable", "visible"}
	ul4_type = ul4c.Type("la", "Field", "The value of a field of a record (and related information)")

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
	ul4_attrs = {"id", "type", "record", "label", "active"}
	ul4_type = ul4c.Type("la", "Attachment", "An attachment of a record")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	record = Attr(Record, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The record this attachment belongs to")
	label = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="A human readable label")
	active = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Is this attachment active?")

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
	ul4_attrs = Attachment.ul4_attrs.union({"original", "thumb", "small", "medium", "large"})
	ul4_type = ul4c.Type("la", "ImageAttachment", "An image attachment of a record")

	type = "imageattachment"

	original = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Original uploaded image")
	thumb = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Thumbnail size version of the image")
	small = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Small version of the image")
	medium = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Medium version of the image")
	large = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Large version of the image")

	def __init__(self, id=None, record=None, label=None, active=None, original=None, thumb=None, small=None, medium=None, large=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.original = original
		self.thumb = thumb
		self.small = small
		self.medium = medium
		self.large = large


class SimpleAttachment(Attachment):
	ul4_attrs = Attachment.ul4_attrs.union({"value"})
	ul4_type = ul4c.Type("la", "SimpleAttachment", "A simple attachment of a record")

	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The value of the attachment (a string, file, URL, note or JSON)")

	def __init__(self, id=None, record=None, label=None, active=None, value=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.value = value


@register("fileattachment")
class FileAttachment(SimpleAttachment):
	ul4_type = ul4c.Type("la", "FileAttachment", "A file attachment of a record")

	type = "fileattachment"

	value = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("urlattachment")
class URLAttachment(SimpleAttachment):
	ul4_type = ul4c.Type("la", "URLAttachment", "A URL attachment of a record")

	type = "urlattachment"

	value = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("noteattachment")
class NoteAttachment(SimpleAttachment):
	ul4_type = ul4c.Type("la", "NoteAttachment", "A note attachment of a record")

	type = "noteattachment"

	value = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("jsonattachment")
class JSONAttachment(SimpleAttachment):
	ul4_type = ul4c.Type("la", "JSONAttachment", "A JSON attachment of a record")

	type = "jsonattachment"

	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")

	def _value_ul4onset(self, value):
		if value is not None:
			value = json.loads(value)
		self.value = value


@register(None)
class EMailAttachment(Base):
	ul4_attrs = {"mimetype", "filename", "content"}
	ul4_type = ul4c.InstantiableType("la", "EMailAttachment", "An email text attachment")

	mimetype = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, repr=True, doc="MIME type of the email attachment")
	filename = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, repr=True, doc="Filename under which this email attachment should be stored")
	content = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="String content of the email attachment")
	size = Attr(int, get="", repr=True, doc="Size of the content")

	def __init__(self, mimetype=None, filename=None, content=None):
		self.mimetype = mimetype
		self.filename = filename
		self.content = content

	def _size_get(self):
		return len(self.content) if self.content is not None else None


class Template(Base):
	ul4_type = ul4c.Type("la", "Template", "An UL4 template")

	# Data descriptors for instance attributes
	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app this template belongs to")
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	source = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="UL4 source code")
	whitespace = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Whitespace handling (extracted from <?whitespace?> tag)")
	signature = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Template signature (extracted from <?ul4?> tag)")
	doc = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Documentation (extracted from <?doc?> tag)")
	path = Attr(str, get="__str__", repr=True)

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
	ul4_type = ul4c.Type("la", "InternalTemplate", "Internal UL4 template")

	def __str__(self):
		return f"{self.app or '?'}/internaltemplate={self.identifier}"

	def save(self, handler=None, recursive=True):
		self._gethandler(handler).save_internaltemplate(self)

	def delete(self, handler=None):
		self._gethandler(handler).delete_internaltemplate(self)


@register("viewtemplate")
class ViewTemplate(Template):
	ul4_type = ul4c.Type("la", "ViewTemplate", "A view template")

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

	type = EnumAttr(Type, get=True, set=True, required=True, default=Type.LIST, ul4get=True, ul4onget=True, ul4onset=True, doc="The type of the view template (i.e. in which context it is used)")
	mimetype = Attr(str, get=True, set=True, default="text/html", ul4get=True, ul4onget=True, ul4onset=True, doc="The MIME type of the HTTP response of the view template")
	permission = IntEnumAttr(Permission, get=True, set=True, required=True, ul4get=True, default=Permission.ALL, ul4onget=True, ul4onset=True, doc="Who can access the template?")
	datasources = AttrDictAttr(get=True, set=True, required=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Configured data sources")

	def __init__(self, *args, id=None, identifier=None, source=None, whitespace="keep", signature=None, doc=None, type=Type.LIST, mimetype="text/html", permission=None):
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
		return self

	def save(self, handler=None, recursive=True):
		self._gethandler(handler).save_viewtemplate(self)

	def delete(self, handler=None):
		self._gethandler(handler).delete_viewtemplate(self)


@register("datasource")
class DataSource(Base):
	ul4_attrs = {"id", "parent", "identifier", "app", "includecloned", "appfilter", "includecontrols", "includerecords", "includecount", "recordpermission", "recordfilter", "includepermissions", "includeattachments", "includeparams", "includeviews", "includecategories", "orders", "children"}
	ul4_type = ul4c.Type("la", "DataSource", "A data source for a view, email or form template")

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

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	parent = Attr(ViewTemplate, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The view template this datasource belongs to")
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="A unique identifier for the data source (unique among the other data sources of the view template)")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app from which records are fetched (or whose records are configured)")
	includecloned = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Should copies of the app referenced by ``app`` be included?")
	appfilter = VSQLAttr("vsqlsupport_pkg3.ds_appfilter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="vSQL expression for filtering which apps might be included (if more than one app is included)")
	includecontrols = IntEnumAttr(IncludeControls, get=True, set=True, required=True, default=IncludeControls.ALL, ul4get=True, ul4onget=True, ul4onset=True, doc="Which fields of the app should be included (in ``controls`` and ``records``)?")
	includerecords = IntEnumAttr(IncludeRecords, get=True, set=True, required=True, default=IncludeRecords.RECORDS, ul4get=True, ul4onget=True, ul4onset=True, doc="Should the app include neither records nor control information, or just control information or both?")
	includecount = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Should the number of records by output in ``recordcount``?")
	recordpermission = IntEnumAttr(RecordPermission, get=True, set=True, required=True, default=RecordPermission.ALL, ul4get=True, ul4onget=True, ul4onset=True, doc="Whose records should be output?")
	recordfilter = VSQLAttr("vsqlsupport_pkg3.ds_recordfilter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="A vSQL expression for filtering when records to include")
	includepermissions = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Include permisson information (ignored)")
	includeattachments = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Include record attachments?")
	includeparams = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Include app parameter?")
	includeviews = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Include views?")
	includecategories = IntEnumAttr(IncludeCategories, get=True, set=True, required=True, default=IncludeCategories.NO, ul4get=True, ul4onget=True, ul4onset=True, doc="Include navigation categories?")
	orders = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The sort expressions for sorting the records dict")
	children = AttrDictAttr(get=True, set=True, required=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Children configuration for records that reference the record from this app")

	def __init__(self, *args, id=None, identifier=None, app=None, includecloned=False, appfilter=None, includecontrols=None, includerecords=None, includecount=False, recordpermission=None, recordfilter=None, includepermissions=False, includeattachments=False, includeparams=False, includeviews=False, includecategories=None):
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
		self.add(*args)

	def __str__(self):
		return f"{self.parent or '?'}/datasource={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	@property
	def ul4onid(self):
		return self.id

	def add(self, *items):
		for item in items:
			if isinstance(item, DataOrder):
				item.parent = self
				self.orders.append(item)
			elif isinstance(item, DataSourceChildren):
				item.datasource = self
				self.children[item.identifier] = item
			else:
				raise TypeError(f"don't know what to do with positional argument {item!r}")
		return self

	def _gethandler(self, handler):
		if handler is None:
			if self.parent is None:
				raise NoHandlerError()
		return self.parent._gethandler(handler)

	def save(self, handler=None, recursive=True):
		self._gethandler(handler).save_datasource(self)


@register("datasourcechildren")
class DataSourceChildren(Base):
	ul4_attrs = {"id", "datasource", "identifier", "control", "filters", "orders"}
	ul4_type = ul4c.Type("la", "DataSourceChildren", "A master/detail specification in a datasource")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	datasource = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The :class:`DataSource` this object belongs to")
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="A unique identifier for this object (unique among the other :class:`DataSourceChildren` objects of the :class:`DataSource`)")
	control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The :class:`AppLookupControl` object that references this app. All records from the controls app that reference our record will be added to the children dict.")
	filter = VSQLAttr("vsqlsupport_pkg3.dsc_recordfilter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Additional vSQL filter for the records.")
	orders = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The sort expressions for sorting the children dict.")

	def __init__(self, *args, id=None, identifier=None, control=None, filter=None):
		self.id = id
		self.datasource = None
		self.identifier = identifier
		self.control = control
		self.filter = filter
		self.orders = []
		self.add(*args)

	def __str__(self):
		return f"{self.datasource or '?'}/datasourcechildren={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	@property
	def ul4onid(self):
		return self.id

	def add(self, *items):
		for item in items:
			if isinstance(item, DataOrder):
				item.parent = self
				self.orders.append(item)
			else:
				raise TypeError(f"don't know what to do with positional argument {item!r}")
		return self

	def _gethandler(self, handler):
		if handler is None:
			if self.datasource is None:
				raise NoHandlerError()
		return self.datasource._gethandler(handler)

	def save(self, handler, recursive=True):
		self._gethandler(handler).save_datasourcechildren(self)


@register("dataorder")
class DataOrder(Base):
	ul4_attrs = {"id", "parent", "expression", "direction", "nulls"}
	ul4_type = ul4c.Type("la", "DataOrder", "A sort specification")

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
	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	parent = Attr(DataSource, DataSourceChildren, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The :class:`DataSource` or :class:`DataSourceChildren` this object belongs to")
	expression = VSQLAttr("?", get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="vSQL expression")
	direction = EnumAttr(Direction, get=True, set=True, required=True, default=Direction.ASC, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Sort direction (asc or desc)")
	nulls = EnumAttr(Nulls, get=True, set=True, required=True, default=Nulls.LAST, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Where to sort empty (``null``) values (first or last)")

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
	ul4_attrs = {
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
	ul4_type = ul4c.Type("la", "DataAction", "An action executed by the system or user on a record")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app this action belongs to")
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable name")
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Used to sort the actions for display")
	active = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Is this action active (otherwise it willl be ignored for display/execution)")
	icon = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Icon to display for the action")
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="What does this action do?")
	message = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Message to output after the action has been executed")
	filter = VSQLAttr("vsqlsupport_pkg3.da_filter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="vSQL expression that determines whether this action should be displayed/executed")
	as_multiple_action = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Should this action be displayed as a action button for multiple records in the datamanagement?")
	as_single_action = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Should this action be displayed as a action button for single records in the datamanagement?")
	as_mail_link = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Can this action be used as an email link (where clicking on the link in the email executes the action)?")
	before_update = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Execute before displaying an update form?")
	after_update = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Execute after updating the record?")
	before_insert = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Execute before displaying an insert form?")
	after_insert = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Execute after inserting the record?")
	before_delete = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True, doc="Execute before deleting the record?")

	commands = Attr(get=True, set=True, ul4onget=True, ul4onset=True)

	def __init__(self, *args, id=None, identifier=None, name=None, order=None, active=True, icon=None, description=None, filter=None, as_multiple_action=None, as_single_action=None, as_mail_link=None, before_update=None, after_update=None, before_insert=None, after_insert=None, before_delete=None):
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
		self.add(*args)

	@property
	def ul4onid(self):
		return self.id

	def add(self, *items):
		for item in items:
			if isinstance(item, DataActionCommand):
				item.parent = self
				self.commands.append(item)
			else:
				raise TypeError(f"don't know what to do with positional argument {item!r}")
		return self


class DataActionCommand(Base):
	ul4_attrs = {
		"id",
		"parent",
		"condition",
		"details",
	}
	ul4_type = ul4c.Type("la", "DataActionCommand", "A single instruction of a data action")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	parent = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The data action this command belongs to or the command this comamnd is a sub command of")
	condition = VSQLAttr("vsqlsupport_pkg3.dac_condition_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Only execute the command when this vSQL condition is true")
	details = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Field expressions for each field of the target app or attribute of the command")

	def __init__(self, *args, id=None, condition=None):
		self.id = id
		self.parent = None
		self.condition = condition
		self.details = []
		self.add(*args)

	@property
	def ul4onid(self):
		return self.id

	def add(self, *items):
		for item in items:
			if isinstance(item, DataActionDetail):
				item.parent = self
				self.details.append(item)
			else:
				raise TypeError(f"don't know what to do with positional argument {item!r}")
		return self


@register("dataactioncommand_update")
class DataActionCommandUpdate(DataActionCommand):
	ul4_type = ul4c.Type("la", "DataActionCommandUpdate", "A data action instruction to update a rcord")


@register("dataactioncommand_task")
class DataActionCommandTask(DataActionCommand):
	ul4_type = ul4c.Type("la", "DataActionCommandTask", "A data action instruction to create a task")


@register("dataactioncommand_delete")
class DataActionCommandDelete(DataActionCommand):
	ul4_type = ul4c.Type("la", "DataActionCommandDelete", "A data action instruction to delete a record")


@register("dataactioncommand_onboarding")
class DataActionCommandOnboarding(DataActionCommand):
	ul4_type = ul4c.Type("la", "DataActionCommandOnboarding", "A data action instruction for onboarding")


@register("dataactioncommand_daterepeater")
class DataActionCommandDateRepeater(DataActionCommand):
	ul4_type = ul4c.Type("la", "DataActionCommandDateRepeater", "A data action instruction for recurring records")


class DataActionCommandWithIdentifier(DataActionCommand):
	ul4_attrs = DataActionCommand.ul4_attrs.union({
		"app",
		"identifier",
		"children",
	})
	ul4_type = ul4c.Type("la", "DataActionCommandWithIdentifier", "The base type for data action instruction that havve fields")

	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The target app")
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="A variable name introduced by this command")
	children = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The field value for this command")

	def __init__(self, id=None, condition=None, app=None, identifier=None):
		super().__init__(id, condition)
		self.app = app
		self.identifier = identifier
		self.children = []

	def addcommand(self, *commands):
		for command in commands:
			command.parent = self
			self.commands.append(command)
		return self


@register("dataactioncommand_insert")
class DataActionCommandInsert(DataActionCommandWithIdentifier):
	ul4_type = ul4c.Type("la", "DataActionCommandInsert", "A data action instruction to insert a new record")


@register("dataactioncommand_insertform")
class DataActionCommandInsertForm(DataActionCommandWithIdentifier):
	ul4_type = ul4c.Type("la", "DataActionCommandInsertForm", "A data action instruction to insert a new record via an HTML form")


@register("dataactioncommand_insertformstatic")
class DataActionCommandInsertFormStatic(DataActionCommandWithIdentifier):
	ul4_type = ul4c.Type("la", "DataActionCommandInsertFormStatic", "A data action instruction to insert a new record via an HTML form in a static app")


@register("dataactioncommand_loop")
class DataActionCommandLoop(DataActionCommandWithIdentifier):
	ul4_type = ul4c.Type("la", "DataActionCommandLoop", "A data action instruction for lookuping over a number of records")


@register("dataactiondetail")
class DataActionDetail(Base):
	ul4_attrs = {
		"id",
		"parent",
		"control",
		"type",
		"children",
	}
	ul4_type = ul4c.Type("la", "DataActionDetail", "A parameter for data action instruction")

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

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	parent = Attr(DataActionCommand, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The data action command this detail belongs to")
	control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The control this detail refers to (i.e. which field/attribute to modify)")
	type = EnumAttr(Type, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The type of execute to execution on the field/attribute")
	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The value to use (if the :attr:`type` isn't :obj:`Type.EXPR`)")
	expression = VSQLAttr("vsqlsupport_pkg3.dac_condition_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The vSQL expression used to set the field/attribute (if :attr:`type` is :obj:`Type.EXPR`)")
	formmode = EnumAttr(FormMode, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="How to display the field in interactive actions (i.e. ``insertform`` and ``insertformstatic``")

	code = Attr(str, get="", repr=True)

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
	ul4_attrs = {"id", "name"}
	ul4_type = ul4c.Type("la", "Installation", "The installation that created an app")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, name=None):
		self.id = id
		self.name = name


class LayoutControl(Base):
	ul4_attrs = {"id", "label", "identifier", "view", "type", "subtype", "top", "left", "width", "height"}
	ul4_type = ul4c.Type("la", "LayoutControl", "A decoration in an input form")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	label = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Label to be displayed for this control")
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	view = Attr(lambda: View, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The view this layout control belongs to")
	top = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Vertical position of this layout control in the form")
	left = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Horizontal position of this layout control in the form")
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Width of this layout control in the form")
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="height of this layout control in the form")

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
	_subtype = "html"

	ul4_attrs = LayoutControl.ul4_attrs.union({"value"})
	ul4_type = ul4c.Type("la", "HTMLLayoutControl", "HTML decoration in an input form")

	value = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="HTML source")


@register("imagelayoutcontrol")
class ImageLayoutControl(LayoutControl):
	type = "image"
	_subtype = None

	ul4_attrs = LayoutControl.ul4_attrs.union({"image_original", "image_scaled"})
	ul4_type = ul4c.Type("la", "ImageLayoutControl", "An image decoration in an input form")

	image_original = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Original uploaded image")
	image_scaled = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="image scaled to final size")


@register("view")
class View(Base):
	ul4_attrs = {"id", "name", "app", "order", "width", "height", "start", "end", "lang", "controls", "layout_controls"}
	ul4_type = ul4c.Type("la", "View", "An input form for a LivingApps application")

	class CombinedType(misc.Enum):
		"""
		If this is a combined view, the type of the combined view.
		"""

		TABS = "tabs"
		WIZARD = "wizard"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	combined_type = EnumAttr(CombinedType, get=True, ul4get=True, ul4onget=True, ul4onset=True, doc="If this is a combined view, the type of the combined view.")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app this view belongs to")
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Used to sort the views")
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Width of the view in pixels")
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="height of the view in pixels")
	start = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="View is inactive before this date")
	end = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="View is inactive after this date")
	controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Additional information for the fields used in this view")
	layout_controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The layout controls used in this view")
	lang = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Language of this view")

	def __init__(self, id=None, name=None, app=None, order=None, width=None, height=None, start=None, end=None, lang=None):
		self.id = id
		self.name = name
		self.combined_type = None
		self.app = app
		self.order = order
		self.width = width
		self.height = height
		self.start = start
		self.end = end
		self.lang = lang

	@property
	def ul4onid(self):
		return self.id


@register("datasourcedata")
class DataSourceData(Base):
	ul4_attrs = {"id", "identifier", "app", "apps"}
	ul4_type = ul4c.Type("la", "DataSourceData", "The data resulting from a data source configuration")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="A unique identifier for the data source")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app reference by this datasource (or :const:`None` when the datasource is configured for all apps)")
	apps = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="All apps that this datasource references (can only be more than one, if copies of this app or all apps are included)")

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
	ul4_attrs = {"id", "control", "key", "label", "visible"}
	ul4_type = ul4c.Type("la", "LookupItem", "An option in a lookup control/field")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	control = Attr(lambda: LookupControl, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The control this lookup item belongs to")
	key = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	label = Attr(str, get="", set=True, repr=True, ul4get="_label_get", ul4onget=True, ul4onset=True, doc="Label to be displayed for this lookup item")
	visible = BoolAttr(get="", repr="", ul4get="_visible_get", doc="Is this item visible in the currently active view?")

	def __init__(self, id=None, control=None, key=None, label=None):
		self.id = id
		self.control = control
		self.key = key
		self.label = label

	def _get_viewcontrol(self):
		if self.control is None:
			return None
		active_view = self.control.app.active_view
		if active_view is None or not active_view.controls:
			return None
		return active_view.controls.get(self.control.identifier, None)

	def _get_viewlookupitem(self):
		viewcontrol = self._get_viewcontrol()
		if viewcontrol is None or viewcontrol.lookupdata is None:
			return None
		try:
			return viewcontrol.lookupdata[self.key]
		except KeyError:
			return None


	def _label_get(self):
		viewlookupitem = self._get_viewlookupitem()
		if viewlookupitem is None:
			return self.label
		return viewlookupitem.label

	def _visible_get(self):
		viewlookupitem = self._get_viewlookupitem()
		if viewlookupitem is None:
			return True
		return viewlookupitem.visible

	def _visible_repr(self):
		if self.visible:
			return None
		else:
			return "visible=False"

	@property
	def ul4onid(self):
		return self.id


@register("viewlookupitem")
class ViewLookupItem(Base):
	ul4_attrs = {"key", "label", "visible"}
	ul4_type = ul4c.Type("la", "ViewLookupItem", "View specific information about a lookup item")

	key = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	label = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Label to be displayed for this lookup item")
	visible = BoolAttr(get=True, set=True, repr="", ul4get=True, ul4onget=True, ul4onset=True, doc="Is this lookup item visible in its view?")

	def __init__(self, id=None, key=None, label=None, visible=None):
		self.key = key
		self.label = label
		self.visible = visible

	def _visible_repr(self):
		if self.visible:
			return None
		else:
			return "visible=False"


@register("category")
class Category(Base):
	ul4_attrs = {"id", "identifier", "name", "order", "parent", "children", "apps"}
	ul4_type = ul4c.Type("la", "Category", "A navigation category")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Label to be displayed for this category in the navigation")
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Used to order the categories in the navigation")
	parent = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The parent category")
	children = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The child categories")
	apps = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The apps that belong to that category")

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
	ul4_attrs = {"id", "app", "identifier", "description", "value", "createdat", "createdby", "updatedat", "updatedby"}
	ul4_type = ul4c.Type("la", "AppParameter", "A parameter of a LivingApps application")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True, doc="Unique database id")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The app this parameter belong to")
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Human readable identifier")
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Description of the parameter")
	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="The parameter value. The type of the value depends on the type of the parameter")
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When was this parameter created?")
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Who created this parameter?")
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="When was this parameter last updated?")
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, doc="Who updated this parameter last?")

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
