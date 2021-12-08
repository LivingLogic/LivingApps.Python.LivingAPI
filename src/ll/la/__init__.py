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

import io, re, unicodedata, datetime, operator, string, json, pathlib, types, enum, math, base64
import urllib.parse as urlparse
from collections import abc

from PIL import Image

import requests.structures
import validators

from ll import misc, ul4c, ul4on # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``

from ll.la import vsql


__docformat__ = "reStructuredText"


###
### Typing stuff
###

from typing import *

T_opt_handler = Optional["ll.la.handlers.Handler"]
T_opt_int = Optional[int]
T_opt_float = Optional[float]
T_opt_str = Optional[str]


###
### Utility functions and classes
###

NoneType = type(None)

module = types.ModuleType("livingapps", "LivingAPI types")
module.ul4_attrs = {"__name__", "__doc__"}

def register(name):
	"""
	Used for registering a class for the UL4ON machinery.

	Similar to :func:`ll.ul4on.register`, but since we must pass the ID as a
	keyword argument, we have to take the registration logic into our own hand.
	"""
	def registration(cls):
		if name is not None:
			cls.ul4onname = "de.livinglogic.livingapi." + name
			ul4on._registry[cls.ul4onname] = cls.ul4oncreate
		setattr(module, cls.__name__, cls.ul4_type)
		module.ul4_attrs.add(cls.__name__)
		return cls
	return registration


def format_class(cls) -> str:
	"""
	Format the name of the class object ``cls``.

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


def format_list(items:List[str]) -> str:
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

	def __getattr__(self, key:Any) -> Any:
		try:
			return self[key]
		except KeyError:
			raise AttributeError(error_attribute_doesnt_exist(self, key))

	def __dir__(self) -> Iterable[str]:
		"""
		Make keys completeable in IPython.
		"""
		return set(dir(dict)) | set(self)


def makeattrs(value:Any) -> Any:
	r"""
	Convert :class:`dict`\s into :class:`attrdict`\s.

	If ``value`` is not a :class:`dict` (or it already is an :class:`attrdict`)
	it will be returned unchanged.
	"""
	if isinstance(value, dict) and not isinstance(value, attrdict):
		value = attrdict(value)
	return value


def error_attribute_doesnt_exist(instance:Any, name:str) -> str:
	return f"{misc.format_class(instance)!r} object has no attribute {name!r}."


def error_attribute_readonly(instance:Any, name:str) -> str:
	return f"Attribute {name!r} of {misc.format_class(instance)!r} object is read only."


def error_attribute_wrong_type(instance:Any, name:str, value:Any, allowed_types:List[Type]) -> str:
	if isinstance(allowed_types, tuple):
		allowed_types = format_list([format_class(t) for t in allowed_types])
	else:
		allowed_types = format_class(allowed_types)

	return f"Value for attribute {name!r} of {misc.format_class(instance)!r} object must be {allowed_types}, but is {format_class(type(value))}."


def attribute_wrong_value(instance:Any, name:str, value:Any, allowed_values:Iterable) -> str:
	allowed_values = format_list([repr(value) for value in allowed_values])

	return f"Value for attribute {name!r} of {misc.format_class(instance)} object must be {allowed_values}, but is {value!r}."


def error_required(field:"Field", value:Any) -> str:
	"""
	Return an error message for an required field that is empty.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" wird benötigt.'
	elif lang == "fr":
		return f'«{field.label}» est obligatoire.'
	elif lang == "it":
		return f'È necessario "{field.label}".'
	else:
		return f'"{field.label}" is required.'


def error_truerequired(field:"Field", value:Any) -> str:
	"""
	Return an error message for an bool field that must be set.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" akzeptiert nur "Ja".'
	elif lang == "fr":
		return f'«{field.label}» n\'accepte que «oui».'
	elif lang == "it":
		return f'"{field.label}" accetta solo "sì".'
	else:
		return f'"{field.label}" only accepts "Yes".'


def error_wrong_type(field:"Field", value:Any) -> str:
	"""
	Return an error message for an unsupported field type.

	Used when setting a field to a value of the wrong type.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" unterstützt den Typ {misc.format_class(value)} nicht.'
	elif lang == "fr":
		return f'«{field.label}» ne prend pas en charge le type {misc.format_class(value)}.'
	elif lang == "it":
		return f'"{field.label}" non supporta il tipo {misc.format_class(value)}.'
	else:
		return f'"{field.label}" doesn\'t support the type {misc.format_class(value)}.'


def error_string_tooshort(field:"Field", minlength:int, value:Any) -> str:
	"""
	Return an error message the value of a string field is too short.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" ist zu kurz. Sie müssen mindestens {minlength} Zeichen verwenden.'
	elif lang == "fr":
		return f'«{field.label}» est trop court. Vous devez utiliser au moins {minlength} caractères.'
	elif lang == "it":
		return f'"{field.label}" è troppo breve. È necessario utilizzare almeno {minlength} caratteri.'
	else:
		return f'"{field.label}" is too short. You must use at least {minlength} characters.'


def error_string_toolong(field:"Field", maxlength:int, value:Any) -> str:
	"""
	Return an error message the value of a string field is too long.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" ist zu lang. Sie dürfen höchstens {maxlength} Zeichen verwenden.'
	elif lang == "fr":
		return f'«{field.label}» est trop long. Vous pouvez utiliser un maximum de {maxlength} caractères.'
	elif lang == "it":
		return f'"{field.label}" è troppo lungo. È possibile utilizzare un massimo di {maxlength} caratteri.'
	else:
		return f'"{field.label}" is too long. You may use up to {maxlength} characters.'


def error_wrong_value(value:Any) -> str:
	"""
	Return an error message for a field value that isn't supported.

	For example when a date field is set to a string value, but the string has
	an unrecognized format, this error message will be used.
	"""
	return f"Value {value!r} is not supported."


def error_date_format(field:"Field", value:Any) -> str:
	"""
	Return an error message for a string value of a date field that has the wrong
	format.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" unterstützt dieses Datumsformat nicht.'
	elif lang == "fr":
		return f'«{field.label}» doit comporter une date valide.'
	elif lang == "it":
		return f'"{field.label}" deve essere una data.'
	else:
		return f'"{field.label}" doesn\'t support this date format.'


def error_lookupitem_unknown(field:"Field", value:str) -> str:
	r"""
	Return an error message for an unknown identifier for :class:`LookupItem`\s.

	Used when setting the field of a lookup control to an unknown identifier.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'Die Option {value!r} für "{field.label}" ist unbekannt.'
	elif lang == "fr":
		return f'L\'option {value!r} pour «{field.label}» est inconnue.'
	elif lang == "it":
		return f'L\'opzione {value!r} per "{field.label}" è sconosciuta.'
	else:
		return f'The option {value!r} for "{field.label}" is unknown.'


def error_lookupitem_foreign(field:"Field", value:"ll.la.LookupItem") -> str:
	"""
	Return an error message for a foreign :class:`LookupItem`.

	Used when setting the field of a lookup control to a :`class`LookupItem` that
	belongs to another :class:`LookupControl`.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'Die Option {value!r} in "{field.label}" gehört nicht zu dieser Auswahl.'
	elif lang == "fr":
		return f'L\'option {value!r} dans «{field.label}» n\'appartient pas à cette sélection.'
	elif lang == "it":
		return f'L\'opzione {value!r} in "{field.label}" non appartiene a questa selezione.'
	else:
		return f'The option {value!r} in "{field.label}" doesn\'t belong to this lookup.'


def error_applookuprecord_unknown(value:str) -> str:
	"""
	Return an error message for a unknown record identifier.

	Used when setting the field of an applookup control to a record identifier
	that can't be found in the target app.
	"""
	return f"Record with id {value!r} unknown."


def error_applookuprecord_foreign(field:"Field", value:"ll.la.Record") -> str:
	"""
	Return an error message for a foreign :class:`Record`.

	Used when setting the field of an applookup control to a :class:`Record`
	object that belongs to the wrong app.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'Der referenzierte Datensatz in "{field.label}" gehört zur falscher App.'
	elif lang == "fr":
		return f'L\'enregistrement référencé dans «{field.label}» appartient à la mauvaise application.'
	elif lang == "it":
		return f'Il record di riferimento in "{field.label}" appartiene all\'app sbagliata.'
	else:
		return f'The referenced record in "{field.label}" is from the wrong app.'


def error_email_format(field:"Field", value:str) -> str:
	"""
	Return an error message for malformed email address.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" muss eine gültige E-Mail-Adresse sein.'
	elif lang == "fr":
		return f'«{field.label}» doit comporter une adresse e-mail valide.'
	elif lang == "it":
		return f'"{field.label}" deve essere un indirizzo email valido.'
	else:
		return f'"{field.label}" must be a valid email address.'


def error_email_badchar(field:"Field", pos:int, value:str) -> str:
	"""
	Return an error message for a bad character in an email address.
	"""
	lang = field.control.app.globals.lang
	char = value[pos]
	charname = unicodedata.name(char, "unassigned character")
	char = ord(char)
	char = f"U+{char:08X}" if char > 0xfff else f"U+{char:04X}"
	if lang == "de":
		return f'"{field.label}" muss eine gültige E-Mail-Adresse sein, enthält aber das Zeichen {char} ({charname}) an Position {pos+1}.'
	else:
		return f'"{field.label}" must be a valid email address, but contains the character {char} ({charname}) at position {pos+1}.'


def error_tel_format(field:"Field", value:str) -> str:
	"""
	Return an error message for malformed phone number.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" muss eine gültige Telefonnummer sein.'
	elif lang == "fr":
		return f'«{field.label}» doit comporter un numéro de téléphone valide.'
	elif lang == "it":
		return f'"{field.label}" deve essere un numero di telefono valido.'
	else:
		return f'"{field.label}" must be a valid phone number.'


def error_url_format(field:"Field", value:str) -> str:
	"""
	Return an error message for malformed URL.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
			return f'"{field.label}" muss eine gültige URL im Format "http://www.xyz.de" sein.'
	elif lang == "fr":
			return f'«{field.label}» doit être au format «http://www.xyz.com».'
	elif lang == "it":
			return f'"{field.label}" deve essere formato "http://www.xyz.com".'
	else:
			return f'"{field.label}" must be a valid URL in the form "http://www.xyz.com".'

	if lang == "de":
		return f'"{field.label}" muss eine URL sein.'
	else:
		return f'"{field.label}" must be a valid URL.'


def error_file_invaliddataurl(field:"Field", value:str) -> str:
	"""
	Return an error message for an invalid ``data`` URL fir a ``file/signature`` field.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'Data-URL ist ungültig.'
	else:
		return f'Data URL is invalid.'


def error_number_format(field:"Field", value:str) -> str:
	"""
	Return an error message for string that can't be convertet to a float or int.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" unterstützt dieses Zahlenformat nicht.'
	else:
		return f'"{field.label}" doesn\'t support this number format.'


def error_object_unsaved(value:Union["ll.la.File", "ll.la.Record"]) -> str:
	"""
	Return an error message for an unsaved referenced object.
	"""
	return f"Referenced object {value!r} hasn't been saved yet."


def error_object_deleted(value:Union["ll.la.File", "ll.la.Record"]) -> str:
	"""
	Return an error message for an deleted referenced object.
	"""
	return f"Referenced object {value!r} has been deleted."


def error_foreign_view(view:"ll.la.View") -> str:
	return f"View {view!r} belongs to the wrong app."


def error_view_not_found(viewid:str) -> str:
	return f"View with id {viewid!r} can't be found."


def _resolve_type(t:Union[Type, Callable[[], Type]]) -> Type:
	if not isinstance(t, type):
		t = t()
	return t


def _is_timezone(value:str) -> bool:
	return value[0] in "+-" and value[1:3].isdigit() and value[3] == ":" and value[4:6].isdigit()


###
### Exceptions
###

class NoHandlerError(ValueError):
	def __str__(self) -> str:
		return "no handler available"


class RecordValidationError(ValueError):
	"""
	Exception that is raised when a record is invalid and saved without
	``force=True``.
	"""

	def __init__(self, record:"ll.la.Record", message:str):
		self.record = record
		self.message = message

	def __str__(self) -> str:
		return f"Validation for {self.record!r} failed: {self.message}"


class FieldValidationError(ValueError):
	"""
	Exception that is raised when a field of a record is invalid and the record
	is saved without ``force=True``.
	"""

	def __init__(self, field:"ll.la.Field", message:str):
		self.field = field
		self.message = message

	def __str__(self) -> str:
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

	def __init__(self, *types, required=False, default=None, default_factory=None, repr=False, get=False, set=False, ul4get=False, ul4set=False, ul4onget=False, ul4onset=False, ul4ondefault=False):
		"""
		Create a new :class:`Attr` data descriptor.

		The type of the attribute will be checked when the attribute is set, it
		must be any of the types in ``types``. If no type is passed any type
		(i.e. any :class:`object`) is allowed. (Furthermore subclasses might
		implement certain type conversions on setting).

		If ``required`` is ``False`` the value ``None`` is allowed too.

		``default`` specifies the default value for the attribute (which is
		used if ``None`` is used as the value).

		``default_factory`` (if not ``None``) can be a callable that is
		used instead of ``default`` to create a default value.

		``repr``, ``get``, ``set``, ``ul4get``, ``ul4set``, ``ul4onget``,
		``ul4onset`` and ``ul4ondefault`` are used to configure the behaviour
		when this attribute is accessed in certain access scenarios.

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

		``repr``
			Include the attribute in the :func:`repr` output of its object.
			The canonical implementation will produce output in the form
			``f"{name}={value!r}"``, except when the value is ``None`` in which
			case no output will be given. The signature of the callback method is
			``(instance)``.

		``get``
			Return the value of the attribute when accessed from Python.
			The canonical implementation will return the appropriate entry of the
			instance dict. The signature of the callback method is ``(instance)``.

		``set``
			Set the value of the attribute from Python. The canonical
			implementation will set the appropriate entry of the instance dict
			after checking the value against the types given by ``types``
			and ``required``. Subclasses might implement certain additional
			type conversions or checks. The signature of the callback method is
			``(instance, value)``.

		``ul4get``
			Return the value of the attribute when accessed from UL4. The canonical
			implementation will return the appropriate entry of the instance dict.
			The signature of the callback method is ``(instance)``.

		``ul4set``
			Set the value of the attribute from UL4. The canonical implementation
			will set the appropriate entry of the instance dict after checking
			the value against the types given by ``types`` and ``required``.
			Subclasses might implement certain additional type conversions or
			checks. The signature of the callback method is ``(instance, value)``.

		``ul4onget``
			Return the value of the attribute for serialization via an UL4ON dump.
			The canonical implementation will use the appropriate entry of the
			instance dict. The signature of the callback method is ``(instance)``.

		``ul4onset``
			Set the value of the attribute from the deserialized value from an
			UL4ON dump. The canonical implementation will set the appropriate
			entry of the instance dict to the given value. No type checks will be
			performed. The signature of the callback method is``(instance, value)``.

		``ul4ondefault``
			Set the value of the attribute to its default value when no value
			is available from the UL4ON dump. The canonical implementation will
			set the appropriate entry of the instance dict to the default value
			(determined vie ``default`` und ``default_factory``).
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
		Format the attribute of ``instance`` for :meth:`__repr__` output.

		If ``None`` is returned this attribute will not be output.
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
	def types(self) -> Tuple[Type, ...]:
		if self._realtypes is None:
			if not isinstance(self._types, tuple):
				self._realtypes = _resolve_type(self._types)
			else:
				self._realtypes = tuple(_resolve_type(t) for t in self._types)
		return self._realtypes

	def __repr__(self) -> str:
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

	def make_default_value(self) -> Any:
		"""
		Return the default value for this attribute.

		This either calls :attr:`default_factory` or returns :attr:`default`.
		"""
		if self.default_factory is not None:
			return self.default_factory()
		else:
			return self.default

	def _ul4onget(self, instance) -> Any:
		if isinstance(self.ul4onget, str):
			return getattr(instance, self.ul4onget)()
		elif self.ul4onget:
			return self.get(instance)
		else:
			raise AttributeError(error_attribute_doesnt_exist(instance, self.name))

	def _ul4onset(self, instance, value) -> None:
		if isinstance(self.ul4onset, str):
			getattr(instance, self.ul4onset)(value)
		elif self.ul4onset:
			self.set(instance, value)
		else:
			raise AttributeError(error_attribute_readonly(instance, self.name))


class BoolAttr(Attr):
	"""
	Subclass of :class:`Attr` for boolean values.

	Setting such an attribute also supports :class:`int`\\s as values.
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
		Set the value of this attribute of ``instance`` to ``value``.

		If ``value`` is an :class:`int` it will be converted to :class:`bool`
		automatically.
		"""
		if isinstance(value, int):
			value = bool(value)
		super()._default_set(instance, value)


class FloatAttr(Attr):
	"""
	Subclass of :class:`Attr` for :class:`float` values.

	Setting such an attribute also supports :class:`int`\\s as values.
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
		Set the value of this attribute of ``instance`` to ``value``.

		If ``value`` is an :class:`int` it will be converted to :class:`float`
		automatically.
		"""
		if isinstance(value, int):
			value = float(value)
		super()._default_set(instance, value)


class EnumAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are :class:`~enum.Enum` instances.

	Setting such an attribute also supports :class:`str`\\s as values.
	"""

	def __init__(self, type:Type[enum.Enum], **kwargs):
		"""
		Create an :class:`EnumAttr` data descriptor.

		``type`` must be a subclass of :class:`~enum.Enum`. All other
		arguments have the same meaning as in :meth:`Attr.__init__`.
		"""
		super().__init__(type, **kwargs)
		self.type = type

	def _default_set(self, instance, value):
		"""
		Set the value of this attribute of ``instance`` to ``value``.

		``value`` may also be the (:class:`str`) value of one of the
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

	def _default_ul4onget(self, instance):
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

	Setting such an attribute also supports :class:`int`\\s as values.
	"""

	def _default_set(self, instance, value):
		"""
		Set the value of this attribute of ``instance`` to ``value``.

		``value`` may also be the (:class:`int`) value of one of the
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

	def __init__(self, function:str, **kwargs):
		"""
		Create an :class:`VSQLAttr` data descriptor.

		The supported type will be :class:`str`. ``function`` must be the
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
		Set the value of this attribute of ``instance`` to ``value``.

		if ``value`` is a :class:`dict` (but not an :class:`attrdict`) it will
		be converted to an :class:`attrdict` automatically.
		"""
		value = makeattrs(value)
		super()._default_set(instance, value)


class CaseInsensitiveDictAttr(Attr):
	"""
	Subclass of :class:`Attr` for values that are dictionaries with
	case-insensitive string keys.

	Setting such an attribute convert a normal :class:`dict` into an
	:class:`requests.structures.CaseInsensitiveDict` object.
	"""

	def __init__(self, **kwargs):
		"""
		Create an :class:`CaseInsensitiveDictAttr` data descriptor.
		"""
		if kwargs.get("required", False):
			super().__init__(dict, abc.MutableMapping, default_factory=requests.structures.CaseInsensitiveDict, **kwargs)
		else:
			super().__init__(dict, abc.MutableMapping, **kwargs)

	def _default_set(self, instance, value):
		"""
		Set the value of this attribute of ``instance`` to ``value``.

		if ``value`` is a :class:`dict` (but not an
		:class:`~requests.structures.CaseInsensitiveDict`) it will
		be converted to an :class:`~requests.structures.CaseInsensitiveDict`
		automatically.
		"""
		if isinstance(value, (dict, abc.MutableMapping)) and not isinstance(value, requests.structures.CaseInsensitiveDict):
			value = requests.structures.CaseInsensitiveDict(value)
		super()._default_set(instance, value)


###
### Core classes
###


class Base:
	"""
	Base class of all LivingAPI classes.
	"""
	ul4_attrs = set()

	@classmethod
	def attrs(cls) -> Iterable[Attr]:
		"""
		Returns an iterator over all :class:`Attr` descriptors for this class.
		"""
		attrs = {}
		for checkcls in reversed(cls.__mro__):
			for attr in checkcls.__dict__.values():
				if isinstance(attr, Attr):
					attrs[attr.name] = attr
		return attrs.values()

	@classmethod
	def ul4oncreate(cls, id:T_opt_str=None) -> "Base":
		"""
		Alternative "constructor" used by the UL4ON machinery for creating new
		objects.

		The reason for this workaround is that in this way the constructor does
		not need to have ``id`` is its first positional argument.
		"""
		return cls(id=id)

	def __repr__(self) -> str:
		v = [f"<{self.__class__.__module__}.{self.__class__.__qualname__}"]

		for attr in self.attrs():
			repr_value = attr.repr(self)
			if repr_value is not None:
				v.append(repr_value)
		v.append(f"at {id(self):#x}>")
		return " ".join(v)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		for attr in self.attrs():
			if attr.ul4onget is not None:
				value = attr.ul4onget(self)
				encoder.dump(value)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
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

	def ul4onload_begin(self, decoder:ul4on.Decoder) -> None:
		"""
		Called before the content of the object is loaded from an UL4ON dump.

		The default implementation does nothing.
		"""

	def ul4onload_end(self, decoder:ul4on.Decoder) -> None:
		"""
		Called after the content of the object has been loaded from an UL4ON dump.

		The default implementation does nothing.
		"""

	def ul4_getattr(self, name:str) -> Any:
		attr = getattr(self.__class__, name, None)
		if isinstance(attr, Attr):
			return attr.ul4get(self)
		elif isinstance(attr, property):
			return attr.fget(self)
		elif self.ul4_hasattr(name):
			return getattr(self, name)
		raise AttributeError(error_attribute_doesnt_exist(self, name))

	def ul4_hasattr(self, name):
		return name in self.ul4_attrs

	def ul4_setattr(self, name:str, value:Any) -> None:
		attr = getattr(self.__class__, name, None)
		if isinstance(attr, Attr):
			return attr.ul4set(self, value)
		elif isinstance(attr, property):
			return attr.fset(self, value)
		raise AttributeError(error_attribute_doesnt_exist(self, name))


@register("flashmessage")
class FlashMessage(Base):
	"""
	A flash message that might be displayed on a web page to inform the user
	that an event has taken place.

	Relevant instance attributes are:

	.. attribute:: timestamp
		:type: datetime.datetime

		When was the :class:`!FlashMessage` created?

	.. attribute:: type
		:type: MessageType

		The type of the message.

	.. attribute:: title

		:type: Optional[str]

		The message tile

	.. attribute:: message
		:type: Optional[str]

		The message itself
	"""

	ul4_attrs = {"timestamp", "type", "title", "message"}
	ul4_type = ul4c.Type("la", "FlashMessage", "A flash message in a web page")

	class MessageType(misc.Enum):
		"""
		The severity level of a :class:`FlashMessage`.

		Allowed values are ``INFO``, ``NOTICE``, ``WARNING`` and ``ERROR``
		"""

		INFO = "info"
		NOTICE = "notice"
		WARNING = "warning"
		ERROR = "error"

	timestamp = Attr(datetime.datetime, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	type = EnumAttr(MessageType, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	title = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	message = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, type=MessageType.INFO, title=None, message=None):
		self.timestamp = datetime.datetime.now()
		self.type = type
		self.title = title
		self.message = message


@register("file")
class File(Base):
	"""
	An uploaded file.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: url
		:type: str

		Server relative URL of the file.

	.. attribute:: filename
		:type: str

		Original file name.

	.. attribute:: mimetype
		:type: str

		MIME type.

	.. attribute:: width
		:type: Optional[int]

		Width in pixels if this file is an image.

	.. attribute:: height
		:type: Optional[int]

		Height in pixels if this file is an image.

	.. attribute:: internalid
		:type: str

		Internal database id.

	.. attribute:: createdat
		:type: datetime.datetime

		When was this file uploaded?

	.. attribute:: size
		:type: int

		The filesize in bytes.
	"""

	ul4_attrs = {"id", "url", "filename", "mimetype", "width", "height", "size", "createdat"}
	ul4_type = ul4c.Type("la", "File", "An uploaded file")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	url = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	filename = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	mimetype = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	width = Attr(int, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	height = Attr(int, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	internalid = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	size = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
		return self.id

	def ul4_getattr(self, name):
		# For these method call the version of the method instead, that doesn't
		# support the ``handler`` parameter.
		if name == "save":
			return getattr(self, "ul4" + name)
		return super().ul4_getattr(name)

	def _gethandler(self, handler:T_opt_handler) -> "ll.la.handlers.Handler":
		if handler is None:
			if self.handler is None:
				raise NoHandlerError()
			handler = self.handler
		return handler

	def save(self, handler:T_opt_handler=None) -> None:
		self._gethandler(handler).save_file(self)

	def ul4save(self) -> None:
		self.save()

	def content(self, handler:T_opt_handler=None) -> bytes:
		"""
		Return the file content as a :class:`bytes` object.
		"""
		if self._content is not None:
			return self._content
		return self._gethandler(handler).file_content(self)

	vsqlgroup = vsql.Group(
		"uploadref_select",
		internalid=(vsql.DataType.STR, "upl_id"),
		id=(vsql.DataType.STR, "upr_id"),
		filename=(vsql.DataType.STR, "upl_orgname"),
		mimetype=(vsql.DataType.STR, "upl_mimetype"),
		width=(vsql.DataType.INT, "upl_width"),
		height=(vsql.DataType.INT, "upl_height"),
		size=(vsql.DataType.INT, "upl_size"),
		createdat=(vsql.DataType.DATETIME, "upl_cdate"),
	)


@register("geo")
class Geo(Base):
	"""
	Geolocation information.

	Relevant instance attributes are:

	.. attribute:: lat
		:type: float

		Latitude (i.e. north/south).

	.. attribute:: long
		:type: float

		Longitude (i.e. east/west).

	.. attribute:: info
		:type: str

		Description of the location.
	"""

	ul4_attrs = {"lat", "long", "info"}
	ul4_type = ul4c.Type("la", "Geo", "Geographical coordinates and location information")

	lat = FloatAttr(get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	long = FloatAttr(get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	info = Attr(str, get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, lat=None, long=None, info=None):
		self.lat = lat
		self.long = long
		self.info = info

	@classmethod
	def ul4oncreate(cls, id:T_opt_str=None) -> "Geo":
		return cls()


@register("user")
class User(Base):
	r"""
	A LivingApps user account.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: publicid
		:type: str

		Unique public id

	.. attribute:: gender
		:type: Optional[str]

		``"m"`` or ``"f"``.

	.. attribute:: title
		:type: Optional[str]

	.. attribute:: firstname
		:type: str

	.. attribute:: surname
		:type: str

	.. attribute:: initials
		:type: Optional[str]

	.. attribute:: email
		:type: str

		Email address and account name

	.. attribute:: streetname
		:type: Optional[str]

		Street name; part of the users address

	.. attribute:: streetnumber
		:type: Optional[str]

		Street number; part of the users address

	.. attribute:: zip
		:type: Optional[str]

		ZIP code; part of the users address

	.. attribute:: city
		:type: Optional[str]

		City; part of the users address

	.. attribute:: phone
		:type: Optional[str]

		The users phone number

	.. attribute:: fax
		:type: str

		The user's fax number

	.. attribute:: lang
		:type: str

		Preferred language

	.. attribute:: avatar_small
		:type: File

		Small version of the avatar icon (visible in the top right corner of the
		page when this user is logged in)

	.. attribute:: avatar_large
		:type: File

		Large version of the avatar icon.

	.. attribute:: summary
		:type: Optional[str]

		Optional self description of the user.

	.. attribute:: interests
		:type: Optional[str]

		The users interests.

	.. attribute:: personal_website
		:type: Optional[str]

		URL of the users personal website.

	.. attribute:: company_website
		:type: Optional[str]

		URL of the company the user works for.

	.. attribute:: company
		:type: Optional[str]

		The name of the company the user works for.

	.. attribute:: position
		:type: Optional[str]

		The position the user has in his/her company.

	.. attribute:: department
		:type: Optional[str]

		The department the user works for in his/her company.

	.. attribute:: keyviews
		:type: Optional[dict[str, KeyView]]

		The :class:`KeyView`\s of this user (only when it is the logged in user)
	"""

	ul4_attrs = {
		"id", "gender", "title", "firstname", "surname", "initials", "email",
		"lang", "avatar_small", "avatar_large", "streetname", "streetnumber",
		"zip", "city", "phone", "fax", "summary", "interests", "personal_website",
		"company_website", "company", "position", "department", "keyviews"
	}
	ul4_type = ul4c.Type("la", "User", "A LivingApps user/account")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	publicid = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	gender = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	title = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	firstname = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	surname = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	initials = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	email = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	streetname = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	streetnumber = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	zip = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	city = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	phone = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	fax = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lang = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	avatar_small = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	avatar_large = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	summary = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	interests = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	personal_website = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	company_website = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	company = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	position = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	department = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
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
	def ul4onid(self) -> str:
		return self.id

	@classmethod
	def vsqlfield(cls, ul4var="user", sqlvar="livingapi_pkg.global_user"):
		return vsql.Field(ul4var, vsql.DataType.STR, sqlvar, f"{sqlvar} = {{d}}.ide_id(+)", cls.vsqlgroup)

	vsqlgroup = vsql.Group(
		"identity",
		id=(vsql.DataType.STR, "ide_publicid"),
		gender=(vsql.DataType.STR, "ide_gender"),
		title=(vsql.DataType.STR, "ide_title"),
		firstname=(vsql.DataType.STR, "ide_firstname"),
		surname=(vsql.DataType.STR, "ide_surname"),
		initials=(vsql.DataType.STR, "ide_initials"),
		email=(vsql.DataType.STR, "ide_account"),
		street=(vsql.DataType.STR, "ide_street"),
		streetnumber=(vsql.DataType.STR, "ide_streetnumber"),
		zip=(vsql.DataType.STR, "ide_zip"),
		city=(vsql.DataType.STR, "ide_city"),
		phone=(vsql.DataType.STR, "ide_phone"),
		fax=(vsql.DataType.STR, "ide_fax"),
		lang=(vsql.DataType.STR, "ide_lang"),
		# FIXME: We can't add the uploads, because the Oracle side doesn't support it yet.
		avatar_small=(
			vsql.DataType.STR,
			"upl_id_avatar_small",
			"({m}.upl_id_avatar_small = {d}.upl_id and {d}.upr_table = 'identity' and {d}.upr_pkvalue = {m}.ide_id and {d}.upr_field = 'upl_id_avatar_small')",
			File.vsqlgroup,
		),
		avatar_large=(
			vsql.DataType.STR,
			"upl_id_avatar_large",
			"({m}.upl_id_avatar_large = {d}.upl_id and {d}.upr_table = 'identity' and {d}.upr_pkvalue = {m}.ide_id and {d}.upr_field = 'upl_id_avatar_large')",
			File.vsqlgroup,
		),
		summary=(vsql.DataType.STR, "ide_summary"),
		interests=(vsql.DataType.STR, "ide_interests"),
		personal_website=(vsql.DataType.STR, "ide_personal_website"),
		company_website=(vsql.DataType.STR, "ide_company_website"),
		company=(vsql.DataType.STR, "ide_company"),
		position=(vsql.DataType.STR, "ide_position"),
		department=(vsql.DataType.STR, "ide_department"),
	)


@register("keyview")
class KeyView(Base):
	"""
	A :class:`!KeyView` makes one :class:`ViewTemplate` publicly accessible
	for everybody with the access rights of another account.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

			Unique database id.

	.. attribute:: identifier
		:type: str

			Human readable identifier.

	.. attribute:: name
		:type: str

			User supplied name.

	.. attribute:: key
		:type: str

			Identifier used as final part of the URL.

	.. attribute:: user
		:type: User

			User who should be considered to be the logged in user for the keyview.

	"""

	ul4_attrs = {"id", "identifier", "name", "key", "user"}
	ul4_type = ul4c.Type("la", "KeyView", "Object granting access to a view template")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	key = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	user = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, identifier=None, name=None, key=None, user=None):
		self.id = None
		self.identifier = identifier
		self.name = name
		self.key = key
		self.user = user


@register("globals")
class Globals(Base):
	r"""
	Global information.

	An instance of this class will be passed to all :class:`ViewTemplate`\s as
	the global variable ``globals``.

	Relevant instance attributes are:

	.. attribute:: version
		:type: str

		API version (normally increases with every update of the LivingApps platform).

	.. attribute:: platform
		:type: str

		A name for the platform we're running on.

	.. attribute:: user
		:type: Optional[User]

		The currently logging in user.

	.. attribute:: maxdbactions
		:type: Optional[int]

		How many database actions may a template execute?.

	.. attribute:: maxtemplateruntime
		:type: Optional[int]

		How long is a template allowed to run?.

	.. attribute:: flashes
		:type: list[FlashMessage]

		List of flash messages.

	.. attribute:: lang
		:type: str

		The language to be used by templates.

	.. attribute:: datasources
		:type: dict[str, DataSourceData]

		Data for configured data sources.

	.. attribute:: hostname
		:type: str

		The host name we're running on (can be used to recreate URLs).

	.. attribute:: app
		:type: App

		The app that the running template belongs to.

	.. attribute:: record
		:type: Optional[Record]

		The detail record.

	.. attribute:: google_api_key
		:type: Optional[str]

		Google API key (e.g. for using the Google Maps API).

	.. attribute:: mode
		:type: Mode

		The type of template we're running.

	.. attribute:: view_template_id
		:type: Optional[str]

		View template id of last database call.

	.. attribute:: email_template_id
		:type: Optional[str]

		Email template id of last database call.

	.. attribute:: view_id
		:type: Optional[str]

		View id of last database call.
	"""

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
		"scaled_url",
		"seq",
		"flash_info",
		"flash_notice",
		"flash_warning",
		"flash_error",
		"dist",
	}
	ul4_type = ul4c.Type("la", "Globals", "Global information")

	class Mode(misc.Enum):
		"""
		The type of template we're running.
		"""

		FORM_NEW_INIT = "form/new/init"
		FORM_NEW_SEARCH = "form/new/search"
		FORM_NEW_LIVE = "form/new/live"
		FORM_NEW_ERROR = "form/new/error"
		FORM_NEW_SUCCESS = "form/new/success"
		FORM_EDIT_INIT = "form/edit/init"
		FORM_EDIT_SEARCH = "form/edit/search"
		FORM_EDIT_LIVE = "form/edit/live"
		FORM_EDIT_ERROR = "form/edit/error"
		FORM_EDIT_SUCCESS = "form/edit/success"
		VIEW_LIST = "view/list"
		VIEW_DETAIL = "view/detail"
		VIEW_SUPPORT = "view/support"
		EMAIL_TEXT = "email/text"
		EMAIL_HTML = "email/html"

	version = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	platform = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	user = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	maxdbactions = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	maxtemplateruntime = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	_flashes = Attr(default_factory=list, ul4onget=True, ul4onset=True)
	lang = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	datasources = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	hostname = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(lambda: App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	record = Attr(lambda: Record, get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	google_api_key = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	mode = EnumAttr(Mode, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	view_template_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)
	email_template_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)
	view_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)

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
		self.__dict__["_flashes"] = []
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
	def ul4onid(self) -> str:
		return "42"

	def _datasources_ul4onset(self, value):
		if value is not None:
			self.datasources = value

	def _record_ul4onset(self, value):
		if value is not None:
			self.record = value

	def geo(self, lat:T_opt_float=None, long:T_opt_float=None, info:T_opt_str=None) -> Geo:
		return self.handler.geo(lat, long, info)

	def seq(self) -> int:
		return self.handler.seq()

	def _add_flash(self, type, title, message):
		self.__dict__["_flashes"].append(FlashMessage(type=type, title=title, message=message))

	def flash_info(self, title:str, message:T_opt_str) -> None:
		self._add_flash(FlashMessage.MessageType.INFO, title, message)

	def flash_notice(self, title:str, message:T_opt_str) -> None:
		self._add_flash(FlashMessage.MessageType.NOTICE, title, message)

	def flash_warning(self, title:str, message:T_opt_str) -> None:
		self._add_flash(FlashMessage.MessageType.WARNING, title, message)

	def flash_error(self, title:str, message:T_opt_str) -> None:
		self._add_flash(FlashMessage.MessageType.ERROR, title, message)

	def flashes(self) -> List[FlashMessage]:
		flashes = self.__dict__["_flashes"]
		self.__dict__["_flashes"] = []
		return flashes

	def dist(self, geo1:Geo, geo2:Geo) -> float:
		lat1 = math.radians(geo1.lat)
		lng1 = math.radians(geo1.long)
		lat2 = math.radians(geo2.lat)
		lng2 = math.radians(geo2.long)
		radius = 6378.137 # Equatorial radius of earth in km
		flat = 1/298.257223563 # Earth flattening

		f = (lat1 + lat2)/2
		g = (lat1 - lat2)/2
		l = (lng1 - lng2)/2

		def sqsin(x):
			x = math.sin(x)
			return x * x
		
		def sqcos(x):
			x = math.cos(x)
			return x * x
		
		s = sqsin(g) * sqcos(l) + sqcos(f) * sqsin(l)
		c = sqcos(g) * sqcos(l) + sqsin(f) * sqsin(l)

		w = math.atan(math.sqrt(s/c))

		dist = 2 * w * radius

		if w != 0.0:
			t = math.sqrt(s * c)/w
			h1 = (3*t-1)/(2*c)
			h2 = (3*t+1)/(2*s)
			dist *= (1 + flat * h1 * sqsin(f) * sqcos(g) - flat * h2 * sqcos(f) * sqsin(g))
		return dist

	def scaled_url(self, /, image:Union["File", str], width:T_opt_int, height:T_opt_int, *, type:str="fill", enlarge:bool=True, gravity:str="sm", quality:T_opt_int=None, rotate:int=0, blur:T_opt_float=None, sharpen:T_opt_float=None, format:T_opt_str=None, cache:bool=True) -> str:
		"""
		Return a new URL for a scaled version of an existing image. These images
		will be scaled by imgproxy__

		__ https://imgproxy.net/

		Arguments are:

		``image`` : :class:`File` or :class:`str`
			Either the URL of an image or a :class:`File` object that contains
			an image.

		``type`` : :class:`str` or ``None``
			Allowed values are: ``"fit"``, ``"fill"``, ``"fill-down"``, ``"force"``
			and  ``"auto"``. The default is ``"fill"``. For more information see
			`the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=resizing-type

		``width`` : :class:`int` or ``None``
			The target width of the image. The default is ``None``. For more
			information see `the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=width

		``height`` : :class:`int` or ``None``
			The target height of the image. The default is ``None``. ``width`` and
			``height`` may not be both ``None``. For more information see
			`the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=height

		``enlarge`` : :class:`bool`
			Enlarge the image if it is smaller than the target size? The default
			is ``True``. For more information see
			`the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=enlarge

		``gravity`` : :class:`str` or ``None``
			Allowed values are ``"no"``, ``"so"``, ``"ea"``, ``"we"``, ``"noea"``,
			``"nowe"``, ``"soea"``, ``"sowe"``, ``"ce"`` and ``"sm"``. The default
			is ``"sm"``. For more information see `the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=gravity

		``quality`` : :class:`int` or ``None``
			If given, the value mut be between 0 and 100. The default is ``None``.
			For more information see `the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=quality

		``rotate`` : :class:`int` or ``None``
			Rotation. If given, the value must be a multiple of 90.
			For more information see `the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=rotate

		``blur`` : :class:`float` or ``None``
			Blurs the image. For more information see
			`the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=blur

		``sharpen`` : :class:`float` or ``None``
			Sharpens the image. For more information see
			`the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=sharpen

		``format`` : :class:`str` or ``None``
			Resulting image format. For more information see
			`the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=format

		``cache`` : :class:`bool`
			If true, return an URL that caches the scaled image, so that is doesn't
			have to be rescaled on each request. Otherwise return an URL that
			rescales the image on each request.
		"""
		v = []
		if cache:
			v.append("/imgproxycache/insecure")
		else:
			v.append("/imgproxy/insecure")

		v.append(f"/rt:{type}")
		if width and width > 0:
			v.append(f"/w:{width}")
		if height and height > 0:
			v.append(f"/h:{height}")
		if enlarge:
			v.append(f"/el:1")
		if gravity is not None:
			v.append(f"/g:{gravity}")
		if quality is not None:
			v.append(f"/q:{quality}")
		if rotate:
			v.append(f"/rot:{rotate}")
		if blur is not None:
			v.append(f"/bl:{blur}")
		if sharpen is not None:
			v.append(f"/sh:{sharpen}")
		if format is not None:
			v.append(f"/f:{format}")
		if isinstance(image, File):
			filename = image.filename.rsplit("/", 1)[-1]
			encoded_filename = urlparse.quote(filename)
			if encoded_filename == filename:
				v.append(f"/fn:{encoded_filename}")
			v.append(f"/plain/https://{self.hostname}/gateway/files/{image.id}")
		else:
			v.append(f"/plain/{urlparse.quote(image)}")
		return "".join(v)


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

	vsqlsearchfield = vsql.Field("search", vsql.DataType.STR, "livingapi_pkg.global_search")

	@classmethod
	def vsqlsearchexpr(cls):
		return vsql.FieldRefAST.make_root(cls.vsqlsearchfield)

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
	"""
	A LivingApp.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: globals
		:type: Globals

		The :class:`Globals` objects.

	.. attribute:: name
		:type: str

		Name of the app.

	.. attribute:: description
		:type: Optional[str]

		Description of the app.

	.. attribute:: lang
		:type: str

		The language the app should be displayed in.

	.. attribute:: startlink
		:type: str

	.. attribute:: iconlarge
		:type: File

		Large version of app icon.

	.. attribute:: iconsmall
		:type: File

		Small version of app icon.

	.. attribute:: createdby
		:type: User

		Who created this app?

	.. attribute:: controls
		:type: Optional[dict[str, Control]]

		The definition of the fields of this app.

	.. attribute:: records
		:type: Optional[dict[str, Record]]

		The records of this app (if configured).

	.. attribute:: recordcount
		:type: int

		The number of records in this app (if configured).

	.. attribute:: installation
		:type: Optional[Installation]

		The installation that created this app.

	.. attribute:: categories
		:type: Optional[dict[str, Category]]

		The navigation categories the currently logged in user put this app in.

	.. attribute:: params
		:type: Optional[dict[str, AppParameter]]

		Application specific configuration parameters.

	.. attribute:: views
		:type: Optional[dict[str, View]

	.. attribute:: datamanagement_identifier
		:type: str

	.. attribute:: basetable
		:type: str

		Name of table or view records of this app are stored in.

	.. attribute:: primarykey
		:type: str

		Name of the primary key of the table/view records of this app are stored in.

	.. attribute:: insertprocedure
		:type: str

		Procedure for inserting new records of this app.

	.. attribute:: updateprocedure
		:type: str

		Procedure for updating existing records of this app.

	.. attribute:: deleteprocedure
		:type: str

		Procedure for deleting existing records of this app.

	.. attribute:: templates
		:type: dict[str, ul4c.Template]

	.. attribute:: createdat
		:type: datetime.datetime

		When was this app created?

	.. attribute:: updatedat
		:type: Optional[datetime.datetime]

		When was this app last changed?

	.. attribute:: updatedby
		:type: Optional[User]

		When changed this app last?.

	.. attribute:: superid
		:type: Optional[str]

		Database id of the app this one was copied from.

	.. attribute:: favorite
		:type: bool

		Is this app a favorite of the currently logged in user?.

	.. attribute:: active_view
		:type: Optional[View]

		Honor information of this view in the control objects.

	.. attribute:: internaltemplates
		:type: Optional[dict[str, InternalTemplate]]

		Internal templates of this app.

	.. attribute:: viewtemplates
		:type: Optional[dict[str, ViewTemplate]]

		View templates of this app.

	.. attribute:: dataactions
		:type: Optional[dict[str, DataAction]]

		Data actions of this app.
	"""

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
		"active_view",
		"datasource",
		"internaltemplates",
		"viewtemplates",
		"dataactions",
	}
	ul4_type = ul4c.Type("la", "App", "A LivingApps application")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	globals = Attr(Globals, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lang = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	startlink = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	iconlarge = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	iconsmall = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	records = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	recordcount = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	installation = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	categories = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	params = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	views = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	datamanagement_identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	basetable = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	primarykey = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	insertprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updateprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	deleteprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	_templates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	superid = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	favorite = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	active_view = Attr(lambda: View, str, get=True, set="", ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	datasource = Attr(lambda: DataSourceData, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	internaltemplates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	viewtemplates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	dataactions = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

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
		self.datasource = None
		self.internaltemplates = None
		self.viewtemplates = None
		self.dataactions = None
		self._vsqlgroup_records = None
		self._vsqlgroup_app = None

	def __str__(self):
		return self.fullname

	@property
	def ul4onid(self) -> str:
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

	def save(self, handler:T_opt_handler=None, recursive=True):
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
		Add each control object in ``controls`` to ``self``.
		"""
		if self.controls is None:
			self.controls = attrdict()
		for control in controls:
			control.app = self
			self.controls[control.identifier] = control
		return self

	def addtemplate(self, *templates):
		"""
		Add each template in ``templates`` as a child for ``self``.

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
		for identifier in kwargs:
			if identifier not in self.controls:
				raise TypeError(f"app_{self.id}() got an unexpected keyword argument {identifier!r}")

		record._make_fields(True, kwargs, {}, {})
		return record

	def vsqlfield_records(self, ul4var, sqlvar):
		return vsql.Field(ul4var, vsql.DataType.STR, sqlvar, f"{sqlvar} = {{d}}.tpl_id(+)", self.vsqlgroup_records)

	def vsqlfield_app(self, ul4var, sqlvar):
		return vsql.Field(ul4var, vsql.DataType.STR, sqlvar, f"{sqlvar} = {{d}}.tpl_id(+)", self.vsqlgroup_app)

	@property
	def vsqlgroup_records(self):
		if self._vsqlgroup_records is None:
			self._vsqlgroup_records = g = vsql.Group("data_select_la")
			g.add_field("id", vsql.DataType.STR, "dat_id")
			g.add_field("app", vsql.DataType.STR, "tpl_uuid")
			g.add_field("createdat", vsql.DataType.DATETIME, "dat_cdate")
			g.add_field("createdby", vsql.DataType.STR, "dat_cname", "{m}.dat_cname = {d}.ide_id(+)", User.vsqlgroup)
			g.add_field("updatedat", vsql.DataType.DATETIME, "dat_udate")
			g.add_field("updatedby", vsql.DataType.STR, "dat_uname", "{m}.dat_uname = {d}.ide_id(+)", User.vsqlgroup)
			g.add_field("url", vsql.DataType.STR, "'https://' || parameter_pkg.str_os('INGRESS_HOST') || '/gateway/apps/' || tpl_uuid || '/' || dat_id || '/edit'")
			if self.controls is not None:
				for control in self.controls.values():
					vsqlfield = control.vsqlfield
					g.fields[vsqlfield.identifier] = vsqlfield
		return self._vsqlgroup_records

	@property
	def vsqlgroup_app(self):
		if self._vsqlgroup_app is None:
			self._vsqlgroup_app = g = vsql.Group("template")
			g.add_field("id", vsql.DataType.STR, "tpl_uuid")
			g.add_field("name", vsql.DataType.STR, "tpl_name")
			g.add_field("description", vsql.DataType.STR, "tpl_description")
			g.add_field("createdat", vsql.DataType.DATETIME, "tpl_ctimstamp")
			g.add_field("createdby", vsql.DataType.STR, "tpl_cname", "{m}.tpl_cname = {d}.ide_id(+)", User.vsqlgroup)
			g.add_field("updatedat", vsql.DataType.DATETIME, "tpl_utimstamp")
			g.add_field("updatedby", vsql.DataType.STR, "tpl_uname", "{m}.tpl_uname = {d}.ide_id(+)", User.vsqlgroup)
			g.add_field("installation", vsql.DataType.STR, "inl_id", "{m}.inl_id = {d}.inl_id(+)", Installation.vsqlgroup)
			# FIXME: Add app parameters
		return self._vsqlgroup_app

	def vsqlsearchexpr(self, record, maxdepth, controls=None):
		result = None
		if maxdepth:
			usecontrols = controls if controls is not None else self.controls
			for control in usecontrols.values():
				if controls is None or control.priority:
					vsqlexpr = control.vsqlsearchexpr(record, maxdepth-1)
					if vsqlexpr is not None:
						if result is None:
							result = vsqlexpr
						else:
							result = vsql.OrAST.make(result, vsqlexpr)
		return result

	def vsqlsortexpr(self, record, maxdepth, controls=None):
		result = []
		if maxdepth:
			usecontrols = controls if controls is not None else self.controls
			for control in usecontrols.values():
				if controls is None or control.priority:
					result.extend(control.vsqlsortexpr(record, maxdepth-1))
		return result


class Control(Base):
	"""
	Describes a field in a LivingApp.

	Functionality for each field type is implented in subclasses.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: identifier
		:type: str

		Human readable identifier.

	.. attribute:: type
		:type: str

		The type of the control.

	.. attribute:: subtype
		:type: Optional[str]

		The subtype of the control (depends on the type and might be ``None``).

	.. attribute:: fulltype
		:type: str

		The full type (in the form ``type/subtype``).

	.. attribute:: field
		:type: str

		Name of the database field.

	.. attribute:: app
		:type: App

		App this control belongs to.

	.. attribute:: label
		:type: str

		Label to be displayed for this control.

	.. attribute:: priority
		:type: bool

		Has this control high priority, i.e. should it be displayed in lists?

	.. attribute:: order
		:type: bool

		Used to sort the controls.

	.. attribute:: default

		The default value.

	.. attribute:: ininsertprocedure
		:type: bool

		Can a value for this field be passed to the insert procedure?.

	.. attribute:: inupdateprocedure
		:type: bool

		Can a value for this field be passed to the update procedure?.

	.. attribute:: top
		:type: int

		Top edge on screen in the input form (from the active view, else ``None``).

	.. attribute:: left
		:type: int

		Left edge on screen in the input form (from the active view, else ``None``).

	.. attribute:: width
		:type: int

		Width on screen in the input form (from the active view, else ``None``).

	.. attribute:: height
		:type: int

		Height on screen in the input form (from the active view, else ``None``).

	.. attribute:: liveupdate
		:type: bool

		Call form template when the value of this field changes? (from the active
		view, else ``False``).

	.. attribute:: tabindex
		:type: int

		Tab order in the input form (from the active view, else ``None``).

	.. attribute:: required
		:type: bool

		Is a value required for this field? (from the active view, else ``False``).

	.. attribute:: mode
		:type: Mode

		How to display this control in this view? (from the active view,
		else ``EDIT``).

	.. attribute:: labelpos
		:type: LabelPos

		Position of the form label relative to the input field (from the active
		view, else ``LEFT``, hide label if ``None``).

	.. attribute:: in_active_view
		:type: bool

		Is this control in the currently active view?
	"""

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

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	type = Attr(str, get="", ul4get="_type_get")
	subtype = Attr(str, get="", ul4get="_subtype_get")
	fulltype = Attr(str, get="", ul4get="_fulltype_get")
	field = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get="", set=True, ul4get="_label_get", ul4onget=True, ul4onset=True)
	priority = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	default = Attr(get="", ul4get="_default_get")
	ininsertprocedure = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	inupdateprocedure = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	top = Attr(int, get="", ul4get="_top_get")
	left = Attr(int, get="", ul4get="_left_get")
	width = Attr(int, get="", ul4get="_width_get")
	height = Attr(int, get="", ul4get="_height_get")
	liveupdate = BoolAttr(get="", ul4get="_liveupdate_get")
	tabindex = Attr(int, get="", ul4get="_tabindex_get")
	required = BoolAttr(get="", ul4get="_required_get")
	mode = EnumAttr(Mode, get="", ul4get="")
	labelpos = EnumAttr(LabelPos, get="", ul4get="")
	in_active_view = BoolAttr(get="", ul4get="_in_active_view_get")

	def __init__(self, id=None, identifier=None, field=None, label=None, priority=None, order=None):
		self.id = id
		self.app = None
		self.identifier = identifier
		self.field = field
		self.label = label
		self.priority = priority
		self.order = order
		self._vsqlfield = None

	@property
	def ul4onid(self) -> str:
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

	def _in_active_view_get(self):
		vc = self._get_viewcontrol()
		return vc is not None

	def _default_get(self):
		return None

	def _set_value(self, field, value):
		field._value = value

	def _asdbarg(self, handler, field):
		return field._value

	def _asjson(self, handler, field):
		return self._asdbarg(handler, field)

	def vsqlsearchexpr(self, record, maxdepth):
		return None # The default is that this field cannot be searched

	def vsqlsortexpr(self, record, maxdepth):
		return [] # The default doesn't add any sort expressions


class StringControl(Control):
	"""
	Base class for all controls of type ``string``.

	Relevant instance attributes are:

	.. attribute:: minlength
		:type: Optional[int]

		The minimum allowed string length (``None`` means unlimited).

	.. attribute:: maxlength
		:type: Optional[int]

		The maximum allowed string length (``None`` means unlimited).

	.. attribute:: placeholder
		:type: Optional[str]

		The placeholder for the HTML input.
	"""

	_type = "string"
	ul4_type = ul4c.Type("la", "StringControl", "A LivingApps string field")

	minlength = Attr(int, get="", ul4get="_minlength_get")
	maxlength = Attr(int, get="", ul4get="_maxlength_get")
	placeholder = Attr(str, get="", ul4get="_placeholder_get")

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR, self.field)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		return vsql.ContainsAST.make(
			Globals.vsqlsearchexpr(),
			vsql.MethAST.make(vsql.FieldRefAST.make(record, f"v_{self.identifier}"), "lower"),
		)

	def vsqlsortexpr(self, record, maxdepth):
		return [
			vsql.MethAST.make(vsql.FieldRefAST.make(record, f"v_{self.identifier}"), "lower")
		]

	def _get_user_placeholder(self, user, placeholder):
		if placeholder is None:
			return None
		elif placeholder == "{gender}":
			return user.gender if user is not None else None
		elif placeholder == "{title}":
			return user.title if user is not None else None
		elif placeholder == "{firstname}":
			return user.firstname if user is not None else None
		elif placeholder == "{surname}":
			return user.surname if user is not None else None
		elif placeholder == "{account}":
			return user.email if user is not None else None
		elif placeholder == "{streetname}":
			return user.streetname if user is not None else None
		elif placeholder == "{streetnumber}":
			return user.streetnumber if user is not None else None
		elif placeholder == "{street}":
			if user is None:
				return None
			elif user.street:
				if user.streetnumber:
					return f"{user.street} {user.streetnumber}"
				else:
					return user.street
			else:
				return user.streetnumber
		elif placeholder == "{zip}":
			return user.zip if user is not None else None
		elif placeholder == "{phone}":
			return user.phone if user is not None else None
		elif placeholder == "{fax}":
			return user.fax if user is not None else None
		elif placeholder == "{company}":
			return user.company if user is not None else None
		elif placeholder == "{city}":
			return user.city if user is not None else None
		elif placeholder == "{summary}":
			return user.summary if user is not None else None
		elif placeholder == "{interests}":
			return user.interests if user is not None else None
		elif placeholder == "{personal_website}":
			return user.personal_website if user is not None else None
		elif placeholder == "{company_website}":
			return user.company_website if user is not None else None
		elif placeholder == "{position}":
			return user.position if user is not None else None
		elif placeholder == "{department}":
			return user.department if user is not None else None
		elif placeholder == "{today}":
			return r"{datetime.date.today():%Y-%m-%d}"
		else:
			return placeholder

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return self._get_user_placeholder(self.app.globals.user, vc.default)
		return None

	def _minlength_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.minlength
		return None

	def _maxlength_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return min(4000, vc.maxlength or 4000)
		return 4000

	def _placeholder_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.placeholder
		return None

	def _set_value(self, field, value):
		if value is None or value == "":
			if self.required:
				field.add_error(error_required(field, value))
			value = None
		elif isinstance(value, str):
			minlength = self.minlength
			maxlength = self.maxlength
			if minlength is not None and len(value or "") < minlength:
				field.add_error(error_string_tooshort(field, minlength, value))
			if maxlength is not None and len(value or "") > maxlength:
				field.add_error(error_string_toolong(field, maxlength, value))
		else:
			field.add_error(error_wrong_type(field, value))
			value = None
		field._value = value


@register("textcontrol")
class TextControl(StringControl):
	"""
	Describes a field of type ``string``/``text``.
	"""

	_subtype = "text"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "TextControl", "A LivingApps text field (type 'string/text')")


@register("urlcontrol")
class URLControl(StringControl):
	"""
	Describes a field of type ``string``/``url``.
	"""

	_subtype = "url"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "URLControl", "A LivingApps URL field (type 'string/url')")

	def _set_value(self, field, value):
		if isinstance(value, str) and value:
			if not validators.url(value):
				field.add_error(error_url_format(field, value))
		super()._set_value(field, value)


@register("emailcontrol")
class EmailControl(StringControl):
	"""
	Describes a field of type ``string``/``email``.
	"""

	_subtype = "email"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "EmailControl", "A LivingApps email field (type 'string/email')")

	_pattern = re.compile("^[a-zA-Z0-9_#$%&’*+/=?^.-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$")

	def _set_value(self, field, value):
		if isinstance(value, str) and value and not self._pattern.match(value):
			# Check if we have any non-ASCII characters
			pos = misc.first(i for (i, c) in enumerate(value) if ord(c) > 0x7f)
			if pos is not None:
				field.add_error(error_email_badchar(field, pos, value))
			else:
				field.add_error(error_email_format(field, value))
		super()._set_value(field, value)


@register("passwordcontrol")
class PasswordControl(StringControl):
	"""
	Describes a field of type ``string``/``password``.
	"""

	_subtype = "password"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "PasswordControl", "A LivingApps email field (type 'string/email')")


@register("telcontrol")
class TelControl(StringControl):
	"""
	Describes a field of type ``string``/``tel``.
	"""

	_subtype = "tel"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "TelControl", "A LivingApps phone number field (type 'string/tel')")

	_pattern = re.compile("^\\+?[0-9 /()-]+$")

	def _set_value(self, field, value):
		if isinstance(value, str) and value and not self._pattern.match(value):
			field.add_error(error_tel_format(field, value))
		super()._set_value(field, value)


class EncryptionType(misc.IntEnum):
	"""
	The type of encruption for a field of type ``string``/``textarea``.
	"""

	NONE = 0
	FORCE = 1
	OPTIONAL = 2


@register("textareacontrol")
class TextAreaControl(StringControl):
	"""
	Describes a field of type ``string``/``textarea``.

	Relevant instance attributes are:

	.. attribute:: encrypted
		:type: EncryptionType

		Is this field encrypted (and how/when will it be encrypted)?
	"""

	_subtype = "textarea"
	_fulltype = f"{StringControl._type}/{_subtype}"

	ul4_attrs = StringControl.ul4_attrs.union({"encrypted"})
	ul4_type = ul4c.Type("la", "TextAreaControl", "A LivingApps textarea field (type 'string/textarea')")

	encrypted = IntEnumAttr(EncryptionType, get=True, set=True, default=EncryptionType.NONE, ul4get=True, ul4onget=True, ul4onset=True)

	def _maxlength_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.maxlength
		return None

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.CLOB, self.field)
		return self._vsqlfield


@register("htmlcontrol")
class HTMLControl(StringControl):
	"""
	Describes a field of type ``string``/``html``.
	"""

	_subtype = "html"
	_fulltype = f"{StringControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "HTMLControl", "A LivingApps HTML field (type 'string/html')")

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.CLOB, self.field)
		return self._vsqlfield


@register("intcontrol")
class IntControl(Control):
	"""
	Describes a field of type ``int``.
	"""

	_type = "int"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "IntControl", "A LivingApps integer field (type 'int')")

	def _set_value(self, field, value):
		if value is not None or value == "":
			if self.required:
				field.add_error(error_required(field, value))
			value = None
		elif isinstance(value, int):
			value = int(value) # This converts :class:`bool`\s etc.
		elif isinstance(value, str):
			try:
				value = int(value)
			except ValueError:
				field.add_error(error_number_format(field, value))
		else:
			field.add_error(error_wrong_type(field, value))
			value = None
		field._value = value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.INT, self.field)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		return vsql.EQAST.make(
			Globals.vsqlsearchexpr(),
			vsql.FuncAST.make("str", vsql.FieldRefAST.make(record, f"v_{self.identifier}")),
		)

	def vsqlsortexpr(self, record, maxdepth):
		return [
			vsql.FieldRefAST.make(record, f"v_{self.identifier}")
		]


@register("numbercontrol")
class NumberControl(Control):
	"""
	Describes a field of type ``number``.
	"""

	_type = "number"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "NumberControl", "A LivingApps number field (type 'number')")

	def _set_value(self, field, value):
		if value is not None or value == "":
			if self.required:
				field.add_error(error_required(field, value))
			value = None
		elif isinstance(value, (int, float)):
			value = float(value) # This converts :class:`bool`\s etc.
		elif isinstance(value, str):
			count_dots = value.count(".")
			count_commas = value.count(",")
			if count_commas == 0:
				format = 1 if count_dots >= 2 else 0
			elif count_commas == 1:
				if count_dots != 1:
					format = 1
				else:
					format = 1 if value.find(".") < value.find(",") else 0
			else: # count_commas >= 2
				format = 0 if count_dots <= 1 else -1
			if format == 0:
				tryvalue = value.replace(",", "")
			elif format == 1:
				tryvalue = value.replace(".", "").replace(",", ".")
			try:
				value = float(tryvalue)
			except ValueError:
				field.add_error(error_number_format(field, value))
		else:
			field.add_error(error_wrong_type(field, value))
			value = None
		field._value = value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.NUMBER, self.field)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		return vsql.EQAST.make(
			Globals.vsqlsearchexpr(),
			vsql.FuncAST.make("str", vsql.FieldRefAST.make(record, f"v_{self.identifier}")),
		)

	def vsqlsortexpr(self, record, maxdepth):
		return [
			vsql.FieldRefAST.make(record, f"v_{self.identifier}")
		]


@register("datecontrol")
class DateControl(Control):
	"""
	Describes a field of type ``date``/``date``.

	Relevant instance attributes are:

	.. attribute:: format
		:type: str

		UL4 format string for formatting values of this type (depends on
		:attr:`Globals.lang`).
	"""

	_type = "date"
	_subtype = "date"
	_fulltype = f"{_type}/{_subtype}"

	ul4_attrs = Control.ul4_attrs.union({"format"})
	ul4_type = ul4c.Type("la", "DateControl", "A LivingApps date field (type 'date/date')")

	format = Attr(str, get="", ul4get="_format_get")

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			default = vc.default
			if default == "{today}":
				return datetime.date.today()
		return None

	def _convert(self, value):
		if isinstance(value, datetime.datetime):
			value = value.date()
		return value

	def _set_value(self, field, value):
		if value is None or value == "":
			if self.required:
				field.add_error(error_required(field, value))
			value = None
		elif isinstance(value, datetime.date):
			value = self._convert(value)
		elif isinstance(value, str):
			charcount = len(value)
			if charcount == 10:
				try:
					value = datetime.date.fromisoformat(value)
				except ValueError:
					field.add_error(error_date_format(field, value))
					# We keep the string value, as a <form> input might want to display it.
				else:
					value = self._convert(value)
			elif charcount in {16, 19, 26}:
				try:
					value = datetime.datetime.fromisoformat(value)
				except ValueError:
					field.add_error(error_date_format(field, value))
					# We keep the string value, as a <form> input might want to display it.
				else:
					value = self._convert(value)
			elif charcount in {22, 25, 32} and _is_timezone(value[-6:]):
				try:
					value = datetime.datetime.fromisoformat(value[:-6])
				except ValueError:
					field.add_error(error_date_format(field, value))
					# We keep the string value, as a <form> input might want to display it.
				else:
					value = self._convert(value)
			else:
				field.add_error(error_date_format(field, value))
		else:
			field.add_error(error_wrong_type(field, value))
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

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.DATE, self.field)
		return self._vsqlfield


@register("datetimeminutecontrol")
class DatetimeMinuteControl(DateControl):
	"""
	Describes a field of type ``date``/``datetimeminute``.
	"""

	_subtype = "datetimeminute"
	_fulltype = f"{DateControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "DatetimeMinuteControl", "A LivingApps date field (type 'date/datetimeminute')")

	def _convert(self, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(second=0, microsecond=0)
		else:
			value = datetime.datetime.combine(value, datetime.time())
		return value

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			default = vc.default
			if default == "{today}":
				return datetime.datetime.now().replace(second=0, microsecond=0)
		return None

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

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.DATETIME, self.field)
		return self._vsqlfield


@register("datetimesecondcontrol")
class DatetimeSecondControl(DateControl):
	"""
	Describes a field of type ``date``/``datetimesecond``.
	"""

	_subtype = "datetimesecond"
	_fulltype = f"{DateControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "DatetimeSecondControl", "A LivingApps date field (type 'date/datetimesecond')")

	def _convert(self, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(microsecond=0)
		else:
			value = datetime.datetime.combine(value, datetime.time())
		return value

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			default = vc.default
			if default == "{today}":
				return datetime.datetime.now().replace(microsecond=0)
		return None

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

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.DATETIME, self.field)
		return self._vsqlfield


@register("boolcontrol")
class BoolControl(Control):
	"""
	Describes a field of type ``bool``.
	"""

	_type = "bool"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "BoolControl", "A LivingApps boolean field (type 'bool')")

	def _set_value(self, field, value):
		if value is None or value == "":
			if self.required:
				field.add_error(error_required(field, value))
			value = None
		elif isinstance(value, bool):
			if not value and self.required:
				field.add_error(error_truerequired(field, value))
		else:
			field.add_error(error_wrong_type(field, value))
			value = None
		field._value = value

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			value = int(value)
		return value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.BOOL, self.field)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		searchterm = Globals.vsqlsearchexpr()
		field = vsql.FieldRefAST.make(record, f"v_{self.identifier}")

		return vsql.AndAST.make(
			vsql.ContainsAST.make(
				vsql.MethAST.make(
					vsql.MethAST.make(
						searchterm,
						"lstrip",
						vsql.ConstAST.make("!"),
					),
					"lower",
				),
				vsql.ConstAST.make(self.label.lower()),
			),
			vsql.IfAST.make(
				vsql.NotAST.make(field),
				vsql.MethAST.make(searchterm, "startswith", vsql.ConstAST.make("!")),
				field,
			)
		)

	def vsqlsortexpr(self, record, maxdepth):
		return [
			vsql.FieldRefAST.make(record, f"v_{self.identifier}")
		]


class LookupControl(Control):
	"""
	Base class for all controls of type ``lookup``.

	Relevant instance attributes are:

	.. attribute:: lookupdata
		:type: dict[str, LookupItem]

		The possible values this control might have.

	.. attribute:: none_key
		:type: Optional[str]

		Key to use for a "Nothing selected" option (from the active view,
		else ``None``).

	.. attribute:: none_label
		:type: Optional[str]

		Label to display for a "Nothing selected" option (from the active view,
		else ``None``).
	"""

	_type = "lookup"

	ul4_attrs = Control.ul4_attrs.union({"lookupdata", "none_key", "none_label", "autoexpandable"})
	ul4_type = ul4c.Type("la", "LookupControl", "A LivingApps lookup field")

	lookupdata = AttrDictAttr(get=True, set=True, required=True, ul4get=True, ul4onget=True, ul4onset=True)
	none_key = Attr(str, get="", ul4get="_none_key_get")
	none_label = Attr(str, get="", ul4get="_none_label_get")
	autoexpandable = BoolAttr(get="", ul4get="_autoexpandable_get")

	def __init__(self, id=None, identifier=None, field=None, label=None, priority=None, order=None, lookupdata=None, autoexpandable=False):
		super().__init__(id=id, identifier=identifier, field=field, label=label, priority=priority, order=order)
		self.lookupdata = lookupdata
		self.autoexpandable = autoexpandable

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return self.lookupdata.get(vc.default, None)
		return None

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

	def _autoexpandable_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.autoexpandable
		return False

	def _find_lookupitem(self, field, value) -> Tuple[Union[None, "LookupItem", str], T_opt_str]:
		if isinstance(value, str):
			if self.lookupdata is None:
				return (value, None)
			if value not in self.lookupdata:
				if self.autoexpandable:
					for lookupitem in self.lookupdata:
						if value == lookupitem.label:
							return (lookupitem, None)
				return (None, error_lookupitem_unknown(field, value))
			return (self.lookupdata[value], None)
		elif isinstance(value, LookupItem):
			if self.lookupdata is None:
				return (value, None)
			tryvalue = self.lookupdata.get(value.key, None)
			if value is not tryvalue:
				return (None, error_lookupitem_foreign(field, value))
			return (tryvalue, None)
		else:
			return (None, error_wrong_type(field, value))

	def _set_value(self, field, value):
		if value is None or value == "" or value == self.none_key:
			if self.required:
				field.add_error(error_required(field, value))
			field._value = None
		else:
			(value, error) = self._find_lookupitem(field, value)
			field._value = value
			if error is not None:
				field.add_error(error)

	def _asdbarg(self, handler, field):
		value = field._value
		if isinstance(value, LookupItem):
			value = value.key
		return value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR, self.field)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		return vsql.ContainsAST.make(
			Globals.vsqlsearchexpr(),
			vsql.MethAST.make(
				vsql.AttrAST.make(vsql.FieldRefAST.make(record, f"v_{self.identifier}")),
				"lower",
			)
		)

	def vsqlsortexpr(self, record, maxdepth):
		return [
			vsql.MethAST.make(vsql.FieldRefAST.make(record, f"v_{self.identifier}"), "lower")
		]


@register("lookupselectcontrol")
class LookupSelectControl(LookupControl):
	"""
	Describes a field of type ``lookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupSelectControl", "A LivingApps lookup field (type 'lookup/select')")


@register("lookupradiocontrol")
class LookupRadioControl(LookupControl):
	"""
	Describes a field of type ``lookup``/``radio``.
	"""

	_subtype = "radio"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupRadioControl", "A LivingApps lookup field (type 'lookup/radio')")


@register("lookupchoicecontrol")
class LookupChoiceControl(LookupControl):
	"""
	Describes a field of type ``lookup``/``choice``.
	"""

	_subtype = "choice"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupChoiceControl", "A LivingApps lookup field (type 'lookup/choice')")


class AppLookupControl(Control):
	"""
	Base class for all controls of type ``applookup``.

	Relevant instance attributes are:

	.. attribute:: lookup_app
		:type: App

		The target app, i.e. the app whose records will be used as values
		of fields of this :class:`!AppLookupControl`.

	.. attribute:: lookup_controls
		:type: dict[str, Control]

		Controls that should be displayed when displaying records from the
		target app.

	.. attribute:: local_master_control
		:type: Control

	.. attribute:: local_detail_controls
		:type: dict

	.. attribute:: remote_master_control
		:type: Control

	.. attribute:: none_key
		:type: str

		Key to use for a "Nothing selected" option (from the active view,
		else ``None``).

	.. attribute:: none_label
		:type: str

		Label to display for a "Nothing selected" option (from the active view,
		else ``None``).

	"""

	_type = "applookup"

	ul4_attrs = Control.ul4_attrs.union({"lookup_app", "lookup_controls", "lookupapp", "lookupcontrols"})
	ul4_type = ul4c.Type("la", "AppLookupControl", "A LivingApps applookup field")

	lookup_app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lookup_controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	local_master_control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	local_detail_controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	remote_master_control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	none_key = Attr(str, get="", ul4get="_none_key_get")
	none_label = Attr(str, get="", ul4get="_none_label_get")

	def __init__(self, id=None, identifier=None, field=None, label=None, priority=None, order=None, lookup_app=None, lookup_controls=None, local_master_control=None, local_detail_controls=None, remote_master_control=None):
		super().__init__(id=id, identifier=identifier, field=field, label=label, priority=priority, order=order)
		self.lookup_app = lookup_app
		self.lookup_controls = lookup_controls
		self.local_master_control = local_master_control
		self.local_detail_controls = local_detail_controls
		self.remote_master_control = remote_master_control

	def _find_lookup_record(self, field, value) -> Tuple[Optional["Record"], T_opt_str]:
		if isinstance(value, str):
			value = self.app.globals.handler.record_sync_data(value)
			if value is None:
				return (None, error_applookuprecord_unknown(value))
		if isinstance(value, Record):
			if self.lookup_app is not None and value.app is not self.lookup_app:
				return (None, error_applookuprecord_foreign(field, value))
		else:
			return (None, error_wrong_type(field, value))
		return (value, None)

	def _set_value(self, field, value):
		if value is None or value == "" or value == self.none_key:
			if self.required:
				field.add_error(error_required(field, value))
			field._value = None
		else:
			(value, error) = self._find_lookup_record(field, value)
			field._value = value
			if error is not None:
				field.add_error(error)

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

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR, self.field, f"{{m}}.{self.field} = {{d}}.dat_id(+)", self.lookup_app.vsqlgroup_records)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		return self.lookup_app.vsqlsearchexpr(
			vsql.FieldRefAST.make(record, f"v_{self.identifier}"),
			maxdepth,
		)

	def vsqlsortexpr(self, record, maxdepth):
		return self.lookup_app.vsqlsortexpr(
			vsql.FieldRefAST.make(record, f"v_{self.identifier}"),
			maxdepth,
		)


@register("applookupselectcontrol")
class AppLookupSelectControl(AppLookupControl):
	"""
	Describes a field of type ``applookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupSelectControl", "A LivingApps applookup field (type 'applookup/select')")


@register("applookupradiocontrol")
class AppLookupRadioControl(AppLookupControl):
	"""
	Describes a field of type ``applookup``/``radio``.
	"""

	_subtype = "radio"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupRadioControl", "A LivingApps applookup field (type 'applookup/radio')")


@register("applookupchoicecontrol")
class AppLookupChoiceControl(AppLookupControl):
	"""
	Describes a field of type ``applookup``/``choice``.
	"""

	_subtype = "choice"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupChoiceControl", "A LivingApps applookup field (type 'applookup/choice')")


class MultipleLookupControl(LookupControl):
	"""
	Base class for all controls of type ``multiplelookup``.
	"""

	_type = "multiplelookup"

	ul4_type = ul4c.Type("la", "MultipleLookupControl", "A LivingApps multiplelookup field")

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			value = self.lookupdata.get(vc.default, None)
			if value is not None:
				return [value]
		return None

	def _set_value(self, field, value):
		if value is None or value == "" or value == self.none_key:
			if self.required:
				field.add_error(error_required(field, value))
			field._value = []
		elif isinstance(value, (str, LookupItem)):
			self._set_value(field, [value])
		elif isinstance(value, list):
			field._value = []
			for v in value:
				if v is None or v == "" or v == self.none_key:
					continue
				if isinstance(v, str):
					if v in self.lookupdata:
						field._value.append(self.lookupdata[v])
					else:
						field.add_error(error_lookupitem_unknown(field, v))
				elif isinstance(v, LookupItem):
					if v.key not in self.lookupdata or self.lookupdata[v.key] is not v:
						field.add_error(error_lookupitem_foreign(field, v))
					else:
						field._value.append(v)
			if not field._value and self.required:
				field.add_error(error_required(field, value))
		else:
			field.add_error(error_wrong_type(field, value))
			field._value = []

	def _asjson(self, handler, field):
		return [item.key for item in field._value]

	def _asdbarg(self, handler, field):
		return handler.varchars([item.key for item in field._value])

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STRLIST)
		return self._vsqlfield


@register("multiplelookupselectcontrol")
class MultipleLookupSelectControl(MultipleLookupControl):
	"""
	Describes a field of type ``multiplelookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupSelectControl", "A LivingApps multiplelookup field (type 'multiplelookup/select')")


@register("multiplelookupcheckboxcontrol")
class MultipleLookupCheckboxControl(MultipleLookupControl):
	"""
	Describes a field of type ``multiplelookup``/``checkbox``.
	"""

	_subtype = "checkbox"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupCheckboxControl", "A LivingApps multiplelookup field (type 'multiplelookup/checkbox')")


@register("multiplelookupchoicecontrol")
class MultipleLookupChoiceControl(MultipleLookupControl):
	"""
	Describes a field of type ``multiplelookup``/``choice``.
	"""

	_subtype = "choice"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupChoiceControl", "A LivingApps multiplelookup field (type 'multiplelookup/choice')")


class MultipleAppLookupControl(AppLookupControl):
	"""
	Base class for all controls of type ``multipleapplookup``.
	"""

	_type = "multipleapplookup"

	ul4_type = ul4c.Type("la", "MultipleAppLookupControl", "A LivingApps multiple applookup field")

	def _set_value(self, field, value):
		if value is None or value == "" or value == self.none_key:
			if self.required:
				field.add_error(error_required(field, value))
			field._value = []
		elif isinstance(value, (str, Record)):
			self._set_value(field, [value])
		elif isinstance(value, list):
			field._value = []
			dat_ids = [v for v in value if isinstance(v, str) and v and v != self.none_key]
			if dat_ids:
				fetched = self.app.globals.handler.records_sync_data(dat_ids)
			else:
				fetched = {}
			for v in value:
				if v is None or v == "" or v == self.none_key:
					continue
				if isinstance(v, str):
					record = fetched.get(v, None)
					if record is None:
						field.add_error(error_applookuprecord_unknown(v))
						v = None
					else:
						v = record
				if isinstance(v, Record):
					if self.lookup_app is not None and v.app is not self.lookup_app:
						field.add_error(error_applookuprecord_foreign(field, v))
					else:
						field._value.append(v)
				elif v is not None:
					field.add_error(error_wrong_type(field, v))
			if not field._value and self.required:
				field.add_error(error_required(field, value))
		else:
			field.add_error(error_wrong_type(field, value))
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

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STRLIST)
		return self._vsqlfield


@register("multipleapplookupselectcontrol")
class MultipleAppLookupSelectControl(MultipleAppLookupControl):
	"""
	Describes a field of type ``multipleapplookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupSelectControl", "A LivingApps multiple applookup field (type 'multipleapplookup/select')")


@register("multipleapplookupcheckboxcontrol")
class MultipleAppLookupCheckboxControl(MultipleAppLookupControl):
	"""
	Describes a field of type ``multipleapplookup``/``checkbox``.
	"""

	_subtype = "checkbox"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupCheckboxControl", "A LivingApps multiple applookup field (type 'multipleapplookup/checkbox')")


@register("multipleapplookupchoicecontrol")
class MultipleAppLookupChoiceControl(MultipleAppLookupControl):
	"""
	Describes a field of type ``multipleapplookup``/``choice``.
	"""

	_subtype = "choice"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupChoiceControl", "A LivingApps multiple applookup field (type 'multipleapplookup/choice')")


@register("filecontrol")
class FileControl(Control):
	"""
	Describes a field of type ``file``.
	"""

	_type = "file"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "FileControl", "A LivingApps upload field (type 'file')")

	def _set_value(self, field, value):
		if value is None or value == "":
			if self.required:
				field.add_error(error_required(field, value))
			value = None
		elif not isinstance(value, File):
			field.add_error(error_wrong_type(field, value))
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

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			# FIXME: This should reference :class:`File`, but Oracle doesn't support this yet.
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		field = vsql.vsql.FieldRefAST.make(record, f"v_{self.identifier}")

		# FIXME: Oracle doesn't support this yet
		# return vsql.OrAST.make(
		# 	vsql.ContainsAST.make(
		# 		Globals.vsqlsearchexpr(),
		# 		vsql.MethAST.make(vsql.FieldRefAST.make(field, "filename"), "lower"),
		# 	),
		# 	vsql.ContainsAST.make(
		# 		Globals.vsqlsearchexpr(),
		# 		vsql.MethAST.make(vsql.FieldRefAST.make(field, "mimetype"), "lower"),
		# 	),
		# )

		return vsql.ContainsAST.make(
			Globals.vsqlsearchexpr(),
			vsql.MethAST.make(field, "lower"),
		)

	def vsqlsortexpr(self, record, maxdepth):
		return [
			vsql.MethAST.make(vsql.FieldRefAST.make(record, f"v_{self.identifier}"), "lower")
		]


@register("filesignaturecontrol")
class FileSignatureControl(FileControl):
	"""
	Describes a field of type ``file``/``signature``.
	"""

	_subtype = "signature"
	_fulltype = f"{FileControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "FileSignatureControl", "A LivingApps signature image field (type 'file/signature')")

	def _set_value(self, field, value):
		if isinstance(value, str) and value:
			pos_slash = value.find("/")
			pos_semi = value.find(";")
			pos_comma = value.find(",")
			if not value.startswith("data:") or max(pos_semi, pos_comma, pos_slash) < 0 or not (pos_slash < pos_semi < pos_comma):
				field.add_error(error_file_invaliddataurl(field, value))
				value = None
			else:
				mimetype = value[5:pos_semi]
				extension = value[pos_slash+1:pos_semi]
				encoding = value[pos_semi+1:pos_comma]
				if encoding != "base64":
					field.add_error(error_file_invaliddataurl(field, value))
					value = None
				else:
					base64str = value[pos_comma+1:] + "=="
					try:
						bytes = base64.b64decode(base64str)
					except Exception:
						field.add_error(error_file_invaliddataurl(field, value))
						value = None
					else:
						try:
							img = Image.open(io.BytesIO(bytes))
						except Exception:
							field.add_error(error_file_invaliddataurl(field, value))
							value = None
						else:
							value = File(
								filename=f"{self.identifier}.{extension}",
								mimetype=mimetype,
								width=img.size[0],
								height=img.size[1],
								size=len(bytes),
								createdat=datetime.datetime.now(),
								content=bytes,
							)
							self.handler = self.app.globals.handler
		field._value = value


@register("geocontrol")
class GeoControl(Control):
	"""
	Describes a field of type ``geo``.
	"""

	_type = "geo"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "GeoControl", "A LivingApps geo field (type 'geo')")

	def _set_value(self, field, value):
		if value is None or value == "":
			if self.required:
				field.add_error(error_required(field, value))
			value = None
		elif isinstance(value, Geo):
			pass
		elif isinstance(value, str):
			tryvalue = self.app.globals.handler._geofromstring(value)
			if tryvalue is None:
				field.add_error(error_wrong_value(value))
			else:
				value = tryvalue
		elif value is not None and not isinstance(value, Geo):
			field.add_error(error_wrong_type(field, value))
			value = None
		field._value = value

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			value = f"{value.lat!r}, {value.long!r}, {value.info}"
		return value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.GEO)
		return self._vsqlfield

	def vsqlsearchexpr(self, record, maxdepth):
		return vsql.ContainsAST.make(
			Globals.vsqlsearchexpr(),
			vsql.MethAST.make(
				vsql.AttrAST.make(
					vsql.FieldRefAST.make(record, f"v_{self.identifier}"),
					"info"
				),
				"lower",
			)
		)

	def vsqlsortexpr(self, record, maxdepth):
		return [
			vsql.MethAST.make(
				vsql.AttrAST.make(
					vsql.FieldRefAST.make(record, f"v_{self.identifier}"),
					"info"
				),
				"lower",
			)
		]


@register("viewcontrol")
class ViewControl(Base):
	"""
	Additional information for a :class:`Control` provided by a :class:`View`.

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: identifier
		:type: str

		Identifier of the control of this view control.

	.. attribute:: type
		:type: str

		Type of the control of this view control.

	.. attribute:: subtype
		:type: str

		Subtype of the control of this view control.

	.. attribute:: view
		:type: View

		The view this view control belongs to.

	.. attribute:: control
		:type: Control

		The control for which this view control contains view specific info.

	.. attribute:: top
		:type: int

		Top edge on screen in the input form.

	.. attribute:: left
		:type: int

		Lfft edge on screen in the input form.

	.. attribute:: width
		:type: int

		Width on screen in the input form.

	.. attribute:: height
		:type: int

		Height on screen in the input form.

	.. attribute:: liveupdate
		:type: bool

		Call form template when the value of this field changes?

	.. attribute:: default
		:type: str

		The default value for the field when no specific field value is given
		(only for ``string``, ``date`` and ``lookup``).

	.. attribute:: tabindex
		:type: int

		Tab order in the input form.

	.. attribute:: minlength
		:type: Optional[int]

		The minimum allowed string length (``None`` means unlimited).

	.. attribute:: maxlength
		:type: Optional[int]

		The maximum allowed string length (``None`` means unlimited).

	.. attribute:: required
		:type: bool

		Is a value required for this field?

	.. attribute:: placeholder
		:type: Optional[str]

		The placeholder for the HTML input.

	.. attribute:: mode
		:type: Control.Mode

		How to display this control in this view.

	.. attribute:: labelpos
		:type: Control.LabelPos

		Position of the form label relative to the input field (hide label if
		``None``).

	.. attribute:: lookup_none_key
		:type: str

		Key to use for a "Nothing selected" option (Don't display such an option
		if ``None``).

	.. attribute:: lookup_none_label
		:type: str

		Label to display for a "Nothing selected" option (Use a generic label
		if ``None``).

	.. attribute:: label
		:type: str

		View specific version of the label.

	.. attribute:: autoalign
		:type: bool

		Is the label width automatically determined by the form builder?

	.. attribute:: labelwidth
		:type: int

		Width of the label on screen.

	.. attribute:: lookupdata
		:type: Optional[dict[str, Union[str, LookupItem, Record]]

		Lookup items for the control in this view.

	.. attribute:: autoexpandable
		:type: Optional[bool]

		Automatically add missing items (only for ``lookup`` and
		``multiplelookup``).
	"""

	ul4_attrs = {
		"id", "label", "identifier", "type", "subtype", "view", "control",
		"type", "subtype", "top", "left", "width", "height", "liveupdate",
		"default", "tabIndex", "minlength", "maxlength", "required", "placeholder",
		"mode", "labelpos", "lookup_none_key", "lookup_none_label", "lookupdata",
		"autoalign", "labelwidth", "autoexpandable"
	}
	ul4_type = ul4c.Type("la", "ViewControl", "Contains view specific information aboutn a control")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get="", repr=True, ul4get="_identifier_get")
	type = Attr(str, get="", repr=True, ul4get="_type_get")
	subtype = Attr(str, get="", repr=True, ul4get="_subtype_get")
	view = Attr(lambda: View, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	control = Attr(lambda: Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	top = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	left = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	liveupdate = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	default = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	tabindex = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	minlength = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	maxlength = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	required = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	placeholder = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	mode = EnumAttr(Control.Mode, get=True, set=True, required=True, default=Control.Mode.EDIT, ul4onget="", ul4onset="", ul4ondefault="")
	labelpos = EnumAttr(Control.LabelPos, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lookup_none_key = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lookup_none_label = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	autoalign = BoolAttr(get=True, set=True, required=True, default=True, ul4get=True, ul4onget=True, ul4onset=True)
	labelwidth = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lookupdata = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	autoexpandable = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
		return self.id

	def _identifier_get(self):
		return self.control.identifier

	def _type_get(self):
		return self.control.type

	def _subtype_get(self):
		return self.control.subtype

	def _mode_ul4onget(self):
		return self.mode is Control.Mode.DISPLAY

	def _mode_ul4onset(self, value):
		self.mode = Control.Mode.DISPLAY if value else Control.Mode.EDIT

	def _mode_ul4ondefault(self):
		self.mode = Control.Mode.EDIT


@register("record")
class Record(Base):
	"""
	A record from a LivingApp.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: state
		:type: State

		The state of synchronisation with the database for this record.

	.. attribute:: app
		:type: :class:`App`

		The app this record belongs to.

	.. attribute:: createdat
		:type: :class:`datetime.datetime`

		When was this record created?

	.. attribute:: createdby
		:type: :class:`User`

		Who created this record?

	.. attribute:: updatedat
		:type: Optional[datetime.datetime]

		When was this record last updated?

	.. attribute:: updatedby
		:type: Optional[User]

		Who updated this record last?.

	.. attribute:: updatecount
		:type: int

		How often has this record been updated?.

	.. attribute:: fields
		:type: dict[str, Field]

		Dictionary containing :class:`Field` objects (with values, errors, etc)
		for each field.

	.. attribute:: values
		:type: dict[str, Any]

		Dictionary containing the field values for each field.

	.. attribute:: errors
		:type: list[str]

		List of error messages attached to the record.

	.. attribute:: attachments
		:type: Optional[dict[str, Attachment]]

		Attachments for this record (if configured).

	.. attribute:: children
		:type: dict[str, dict[str, Record]]

		Detail records, i.e. records that have a field pointing back to this
		record.
	"""

	ul4_attrs = {"id", "app", "createdat", "createdby", "updatedat", "updatedby", "updatecount", "fields", "values", "children", "attachments", "errors", "has_errors", "add_error", "clear_errors", "is_deleted", "is_dirty", "save", "update", "executeaction", "state"}
	ul4_type = ul4c.Type("la", "Record", "A record of a LivingApp application")

	class State(misc.Enum):
		"""
		The database synchronisation state of the record.

		Values are:

		``NEW``
			The record object has been created by the template, but hasn't been
			saved yet.

		``SAVED``
			The record object has been loaded from the database and hasn't been
			changed since.

		``CHANGED``
			The record object has been changed by the user.

		``DELETED``
			The record has been deleted in the database.
		"""

		NEW = "new"
		SAVED = "saved"
		CHANGED = "changed"
		DELETED = "deleted"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	state = EnumAttr(State, get="", required=True, repr=True, ul4get="")
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatecount = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	fields = AttrDictAttr(get="", ul4get="_fields_get")
	values = AttrDictAttr(get="", set=True, ul4get="_values_get", ul4onget="", ul4onset="")
	attachments = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	children = AttrDictAttr(get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset="")
	errors = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	fielderrors = AttrDictAttr(ul4onget="", ul4onset="")
	lookupdata = AttrDictAttr(ul4onget="", ul4onset="")

	def __init__(self, id=None, app=None, createdat=None, createdby=None, updatedat=None, updatedby=None, updatecount=None):
		self.id = id
		self.app = app
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.updatecount = updatecount
		self._sparsevalues = attrdict()
		self._sparsefielderrors = attrdict()
		self._sparselookupdata = attrdict()
		self.__dict__["values"] = None
		self.__dict__["fields"] = None
		self.children = attrdict()
		self.attachments = None
		self.errors = []
		self._new = True
		self._deleted = False

	@property
	def ul4onid(self) -> str:
		return self.id

	def ul4onload_end(self, decoder:ul4on.Decoder) -> None:
		self._new = False
		self._deleted = False

	def _make_fields(self, use_defaults, values, errors, lookupdata):
		fields = attrdict()
		for control in self.app.controls.values():
			identifier = control.identifier
			value = None
			if values is not None:
				if use_defaults and identifier not in values:
					value = control.default
				else:
					value = values.get(identifier, None)
			field = Field(control, self, value)
			fields[identifier] = field
		self.__dict__["fields"] = fields
		self._sparsevalues = None
		self._sparsefielderrors = None
		self._sparselookupdata = None

	def _fields_get(self):
		if self.__dict__["fields"] is None:
			self._make_fields(False, self._sparsevalues, self._sparsefielderrors, self._sparselookupdata)
		return self.__dict__["fields"]

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
			values = {field.control.identifier: field.value for field in self.fields.values() if not field.is_empty()}
		return values

	def _values_ul4onset(self, value):
		self._sparsevalues = value
		# Set the following attributes via ``__dict__``, as they are "read only".
		self.__dict__["values"] = None
		self.__dict__["fields"] = None

	def _fielderrors_ul4onget(self):
		if self._sparsefielderrors is not None:
			return self._sparsefielderrors

		result = {field.control.identifier: field.errors for field in self.fields.values() if field.has_errors()}
		return result or None

	def _fielderrors_ul4onset(self, value):
		self._sparsefielderrors = value
		# Set the following attributes via ``__dict__``, as they are "read only".
		self.__dict__["values"] = None
		self.__dict__["fields"] = None

	def _lookupdata_ul4onget(self):
		pass

	def _lookupdata_ul4onset(self, value):
		self._sparselookupdata = value
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
			v.append(f"<{self.__class__.__module__}.{self.__class__.__qualname__} id={self.id!r}")
			if self.has_errors():
				v.append(" has_errors()=True")
			for field in self.fields.values():
				if field.control.priority and not field.is_empty():
					v.append(f" v_{field.control.identifier}=")
					self._repr_value(v, seen, field.value)
			seen.remove(self)
			v.append(f" state={self.state.name}")
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
		# For these method call the version of the method instead, that doesn't
		# support the ``handler`` parameter.
		if name in {"save", "delete", "executeaction"}:
			return getattr(self, "ul4" + name)
		return super().ul4_getattr(name)

	def ul4_setattr(self, name, value):
		if name.startswith("v_") and name[2:] in self.app.controls:
			setattr(self, name, value)
		elif name.startswith("c_"):
			if self.children is None:
				self.children = attrdict()
			self.children[name[2:]] = value
		elif name == "children":
			self.children = value
		else:
			raise AttributeError(error_attribute_readonly(self, name))

	def _gethandler(self, handler):
		if handler is None:
			if self.app is None:
				raise NoHandlerError()
		return self.app._gethandler(handler)

	def save(self, force=False, sync=False, handler:T_opt_handler=None):
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

	def delete(self, handler:T_opt_handler=None):
		self._gethandler(handler).delete_record(self)

	def executeaction(self, handler:T_opt_handler=None, identifier=None):
		self._gethandler(handler)._executeaction(self, identifier)

	def ul4save(self, force=False, sync=False):
		return self.save(force=force, sync=sync)

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


class Field(Base):
	r"""
	A :class:`!Field` object contains the value of a certain field (i.e. a
	:class:`Control`) for a certain :class:`Record`.

	Relevant instance attributes are:

	.. attribute:: control
		:type: Control

		The :class:`Control` for which this :class:`!Field` holds a value.

	.. attribute:: record
		:type: Record

		The :class:`Record` for which this :class:`!Field` holds a value.

	.. attribute:: label
		:type: str

		A field specific label. Setting the label to ``None`` reset the value
		back to the label of the :class:`Control`.

	.. attribute:: lookupdata
		:type: dict[str, Union[str, LookupItem, Record]]

		Custom lookup data for this field. 

		For fields belonging to :class:`LookupControl` or
		:class:`MultipleLookupControl` objects the dictionary keys should be the
		``key`` attribute of :class:`LookupItem`\s and the values should be
		:class:`LookupItem` or :class:`str` objects.

		For fields belonging to :class:`AppLookupControl` or
		:class:`MultipleAppLookupControl` objects the dictionary keys should be
		the ``id`` attribute of :class:`Record` objects and the values should be
		:class:`Record` or :class:`str` objects.

		Using :class:`str` as the values makes it possible to use custom labels
		in input forms.

	.. attribute:: value

		The field value. The type of the value depends on the type of the
		:class:`Control` this field belongs to.

	.. attribute:: dirty
		:type: bool

		Has this field been changed since the record was loaded from the
		database?

	.. attribute:: errors
		:type: list[str]

		List of error messages for this field.

	.. attribute:: enabled
		:type: bool

		Should the input for this field be enabled in the input form?
		Disabling the input usually means to add the HTML attribute ``disabled``.
		In this case the field value will not be submitted when submitting the
		form.

	.. attribute:: writable
		:type: bool

		Should the input for this field be writable in the input form?
		Setting the input the read-only usually means to add the HTML attribute
		``readonly``. In this case the user cant change the input, but the field
		value will still be submitted when submitting the form.

	.. attribute:: visible
		:type: bool

		Should the input for this field be visible or invisible in the input form?
	"""

	ul4_attrs = {"control", "record", "label", "lookupdata", "value", "is_empty", "is_dirty", "errors", "has_errors", "has_custom_lookupdata", "add_error", "clear_errors", "enabled", "writable", "visible"}
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
						raise ValueError(error_lookupitem_unknown(self, v))
					items.append(control.lookupdata[v])
				elif isinstance(v, LookupItem):
					if control.lookupdata.get(v.key, None) is not v:
						raise ValueError(error_lookupitem_foreign(self, v))
					items.append(v)
				elif v is not None:
					raise ValueError(error_wrong_type(self, v))
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
						raise ValueError(error_applookuprecord_foreign(self, v))
					else:
						records.append(v)
				elif v is not None:
					raise ValueError(error_wrong_type(self, v))
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

	def has_custom_lookupdata(self):
		return self._lookupdata is not None

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
	"""
	An attachment for a :class:`Record`.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: record
		:type: Record

		The record this attachment belongs to.

	.. attribute:: label
		:type: str

		A human readable label.

	.. attribute:: active
		:type: bool

		Is this attachment active?
	"""

	ul4_attrs = {"id", "type", "record", "label", "active"}
	ul4_type = ul4c.Type("la", "Attachment", "An attachment of a record")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	record = Attr(Record, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	active = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, record=None, label=None, active=None):
		self.id = id
		self.record = record
		self.label = label
		self.active = active

	@property
	def ul4onid(self) -> str:
		return self.id


@register("imageattachment")
class ImageAttachment(Attachment):
	"""
	An image attachment for a :class:`Record`.

	Relevant instance attributes are:

	.. attribute:: original
		:type: File

		Original uploaded image.

	.. attribute:: thumb
		:type: File

		Thumbnail size version of the image.

	.. attribute:: small
		:type: File

		Small version of the image.

	.. attribute:: medium
		:type: File

		Medium version of the image.

	.. attribute:: large
		:type: File

		Large version of the image.
	"""

	ul4_attrs = Attachment.ul4_attrs.union({"original", "thumb", "small", "medium", "large"})
	ul4_type = ul4c.Type("la", "ImageAttachment", "An image attachment of a record")

	type = "imageattachment"

	original = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	thumb = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	small = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	medium = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	large = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, record=None, label=None, active=None, original=None, thumb=None, small=None, medium=None, large=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.original = original
		self.thumb = thumb
		self.small = small
		self.medium = medium
		self.large = large


class SimpleAttachment(Attachment):
	"""
	Base class for all :class:`Record` attachment that consist of a single value.
	"""

	ul4_attrs = Attachment.ul4_attrs.union({"value"})
	ul4_type = ul4c.Type("la", "SimpleAttachment", "A simple attachment of a record")

	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, record=None, label=None, active=None, value=None):
		super().__init__(id=id, record=record, label=label, active=active)
		self.value = value


@register("fileattachment")
class FileAttachment(SimpleAttachment):
	"""
	A file attachment for a :class:`Record`.

	Relevant instance attributes are:

	.. attribute:: value
		:type: File

		The file.
	"""

	ul4_type = ul4c.Type("la", "FileAttachment", "A file attachment of a record")

	type = "fileattachment"

	value = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("urlattachment")
class URLAttachment(SimpleAttachment):
	"""
	An URL attachment for a :class:`Record`.

	Relevant instance attributes are:

	.. attribute:: value
		:type: str

		The URL.
	"""

	ul4_type = ul4c.Type("la", "URLAttachment", "A URL attachment of a record")

	type = "urlattachment"

	value = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("noteattachment")
class NoteAttachment(SimpleAttachment):
	"""
	A note attachment for a :class:`Record`.

	Relevant instance attributes are:

	.. attribute:: value
		:type: str

		The note.
	"""

	ul4_type = ul4c.Type("la", "NoteAttachment", "A note attachment of a record")

	type = "noteattachment"

	value = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("jsonattachment")
class JSONAttachment(SimpleAttachment):
	"""
	A JSON attachment for a :class:`Record`.

	Relevant instance attributes are:

	.. attribute:: value

		A JSON compatible object (or ``None``).
	"""

	ul4_type = ul4c.Type("la", "JSONAttachment", "A JSON attachment of a record")

	type = "jsonattachment"

	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")

	def _value_ul4onset(self, value):
		if value is not None:
			value = json.loads(value)
		self.value = value


@register(None)
class EMailAttachment(Base):
	"""
	An additional text attachment for an email to be sent.

	An :class:`!EMailAttachment` can be created by an email template to attach
	an addtional text attachment to the email to be sent.

	Relevant instance attributes are:

	.. attribute:: mimetype
		:type: str

		MIME type of the email attachment

	.. attribute:: filename
		:type: str

		Filename under which this email attachment should be stored

	.. attribute:: content
		:type: Optional[str]

		String content of the email attachment.

	.. attribute:: size
		:type: Optional[int]

		Size of the content in characters or ``None`` if ``content`` is ``None``.
	"""

	ul4_attrs = {"mimetype", "filename", "content"}
	ul4_type = ul4c.InstantiableType("la", "EMailAttachment", "An email text attachment")

	mimetype = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, repr=True)
	filename = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True, repr=True)
	content = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	size = Attr(int, get="", repr=True)

	def __init__(self, mimetype=None, filename=None, content=None):
		self.mimetype = mimetype
		self.filename = filename
		self.content = content

	def _size_get(self):
		return len(self.content) if self.content is not None else None


class Template(Base):
	"""
	Base class for various classes that use an UL4 template.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: app
		:type: App

		The app this template belongs to.

	.. attribute:: identifier
		:type: str

		Human readable identifier.

	.. attribute:: source
		:type: str

		UL4 source code.

	.. attribute:: whitespace
		:type: str

		Whitespace handling (extracted from ``<?whitespace?>`` tag).

	.. attribute:: signature
		:type: str

		Template signature (extracted from ``<?ul4?>`` tag).

	.. attribute:: doc
		:type: str

		Documentation (extracted from ``<?doc?>`` tag).

	.. attribute:: path
		:type: str

		Unique "path-like" string that identifies this template.

	"""

	ul4_type = ul4c.Type("la", "Template", "An UL4 template")

	# Data descriptors for instance attributes
	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	source = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	whitespace = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	signature = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	doc = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
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
	def ul4onid(self) -> str:
		return self.id

	def template(self:T_opt_handler) -> "ll.la.handlers.Handler":
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
	r"""
	An internal template can be used by :class:`ViewTemplate`\s as reusable building blocks.

	In internal template is not callable from outside. All internal templates
	will be available via ``globals.templates`` (which is a :class:`dict` that
	maps the template identifiers to the templates).
	"""

	ul4_type = ul4c.Type("la", "InternalTemplate", "Internal UL4 template")

	def __str__(self):
		return f"{self.app or '?'}/internaltemplate={self.identifier}"

	def save(self, handler:T_opt_handler=None, recursive=True):
		self._gethandler(handler).save_internaltemplate(self)

	def delete(self, handler:T_opt_handler=None):
		self._gethandler(handler).delete_internaltemplate(self)


@register("viewtemplate")
class ViewTemplate(Template):
	"""
	A :class:`!ViewTemplate` provides a webpage.

	Relevant instance attributes are:

	.. attribute:: type
		:type: Type

		The type of the view template (i.e. in which context it is used)

	.. attribute:: mimetype
		:type: str

		The MIME type of the HTTP response of the view template

	.. attribute:: permission
		:type: Permission

		Who can access the template?

	.. attribute:: datasources
		:type: dict[str, DataSource] 

		Configured data sources
	"""

	ul4_type = ul4c.Type("la", "ViewTemplate", "A view template")

	class Type(misc.Enum):
		"""
		The type of a view template.

		Enum values have the following meaning:

		``LIST``
			The template is supposed to display multiple records. The URL looks
			like this:

			.. sourcecode:: text

				/gateway/apps/1234567890abcdef12345678?template=foo

			(with ``1234567890abcdef12345678`` being the app id).

		``LISTDEFAULT``
			This is similar to ``LIST``, but this view template is the default when
			no ``template`` parameter is specified, i.e. the URL looks like this:

			.. sourcecode:: text

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

	type = EnumAttr(Type, get=True, set=True, required=True, default=Type.LIST, ul4get=True, ul4onget=True, ul4onset=True)
	mimetype = Attr(str, get=True, set=True, default="text/html", ul4get=True, ul4onget=True, ul4onset=True)
	permission = IntEnumAttr(Permission, get=True, set=True, required=True, ul4get=True, default=Permission.ALL, ul4onget=True, ul4onset=True)
	datasources = AttrDictAttr(get=True, set=True, required=True, ul4get=True, ul4onget=True, ul4onset=True)

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

	def save(self, handler:T_opt_handler=None, recursive=True):
		self._gethandler(handler).save_viewtemplate(self)

	def delete(self, handler:T_opt_handler=None):
		self._gethandler(handler).delete_viewtemplate(self)


@register("datasource")
class DataSource(Base):
	"""
	A :class:`DataSource` contains the configuration to provide information about
	one (or more) apps and their records to a :class:`ViewTemplate` or other
	templates.

	The resulting information will be a :class:`DataSourceData` object.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: parent
		:type: ViewTemplate

		The view template this datasource belongs to.

	.. attribute:: identifier
		:type: str

		A unique identifier for the data source (unique among the other data
		sources of the view template).

	.. attribute:: app
		:type: App

		The app from which records are fetched (or whose records are configured).

	.. attribute:: includecloned
		:type: bool

		Should copies of the app referenced by ``app`` be included?

	.. attribute:: appfilter
		:type: str

		vSQL expression for filtering which apps might be included (if more than
		one app is included).

	.. attribute:: includecontrols
		:type: IncludeControls

		Which fields of the app should be included (in ``controls`` and
		``records``)?

	.. attribute:: includerecords
		:type: IncludeRecords

		Should the app include neither records nor control information, or just
		control information or both?

	.. attribute:: includecount
		:type: bool

		Should the number of records by output in ``recordcount``?

	.. attribute:: recordpermission
		:type: RecordPermission

		Whose records should be output?

	.. attribute:: recordfilter
		:type: str

		A vSQL expression for filtering when records to include.

	.. attribute:: includepermissions
		:type: str

		Include permisson information (ignored).

	.. attribute:: includeattachments
		:type: str

		Include record attachments?

	.. attribute:: includeparams
		:type: str

		Include app parameter?

	.. attribute:: includeviews
		:type: str

		Include views?

	.. attribute:: includecategories
		:type: IncludeCategories

		Include navigation categories?

	.. attribute:: orders
		:type: list[DataOrder]

		The sort expressions for sorting the records dict.

	.. attribute:: children
		:type: dict[str, DataSourceChildren]

		Children configuration for records that reference the record from this app.
	"""

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
		Specify how much information about app categories should be included in
		the :class:`App` object.

		Enum values have the following meaning:

		``NO``
			No category info.

		``PATH``
			The :class:`App` attribute ``categories`` contains the navigation
			categories the app belong to. :class:`Category` objects are linked
			via their ``parent`` attribute.

		``TREE``
			Addtionally to ``PATH``, :class:`Category` objects contain their
			child categories in the attribute ``children``.

		``APPS``
			Addtionally to ``TREE``, :class:`Category` objects contain the apps
			in this category in the attribute ``apps``.
		"""

		NO = 0
		PATH = 1
		TREE = 2
		APPS = 3

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	parent = Attr(ViewTemplate, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	includecloned = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	appfilter = VSQLAttr("vsqlsupport_pkg3.ds_appfilter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	includecontrols = IntEnumAttr(IncludeControls, get=True, set=True, required=True, default=IncludeControls.ALL, ul4get=True, ul4onget=True, ul4onset=True)
	includerecords = IntEnumAttr(IncludeRecords, get=True, set=True, required=True, default=IncludeRecords.RECORDS, ul4get=True, ul4onget=True, ul4onset=True)
	includecount = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	recordpermission = IntEnumAttr(RecordPermission, get=True, set=True, required=True, default=RecordPermission.ALL, ul4get=True, ul4onget=True, ul4onset=True)
	recordfilter = VSQLAttr("vsqlsupport_pkg3.ds_recordfilter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	includepermissions = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	includeattachments = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	includeparams = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	includeviews = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	includecategories = IntEnumAttr(IncludeCategories, get=True, set=True, required=True, default=IncludeCategories.NO, ul4get=True, ul4onget=True, ul4onset=True)
	orders = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	children = AttrDictAttr(get=True, set=True, required=True, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
		return self.id

	def add(self, *items:T_opt_handler) -> "ll.la.handlers.Handler":
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

	def save(self, handler:T_opt_handler=None, recursive=True):
		self._gethandler(handler).save_datasource(self)


@register("datasourcechildren")
class DataSourceChildren(Base):
	"""
	A :class:`DataSourceChildren` object contains the configuration for
	attachment detail records to a master record.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: datasource
		:type: DataSource

		The :class:`DataSource` this object belongs to.

	.. attribute:: identifier
		:type: str

		A unique identifier for this object (unique among the other
		:class:`DataSourceChildren` objects of the :class:`DataSource`).

	.. attribute:: control
		:type: Control

		The :class:`AppLookupControl` object that references this app. All records
		from the controls app that reference our record will be added to the
		children dict.

	.. attribute:: filter
		:type: str

		Additional vSQL filter for the records.

	.. attribute:: orders
		:type: list[DataOrder]

		The sort expressions for sorting the children dict.
	"""

	ul4_attrs = {"id", "datasource", "identifier", "control", "filters", "orders"}
	ul4_type = ul4c.Type("la", "DataSourceChildren", "A master/detail specification in a datasource")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	datasource = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	filter = VSQLAttr("vsqlsupport_pkg3.dsc_recordfilter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	orders = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
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
	"""
	A :class:`DataOrder` object contains one sort specification how multiple
	records should be sorted.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: parent
		:type: DataSource

		The :class:`DataSource` or :class:`DataSourceChildren` this object belongs to

	.. attribute:: expression
		:type: str

		vSQL expression by which to sort.

	.. attribute:: direction
		:type: Direction

		Sort direction (``ASC`` or ``DESC``).

	.. attribute:: nulls
		:type: Nulls

		Where to sort empty (``null``) values (``FIRST`` or ``LAST``)
	"""

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

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	parent = Attr(DataSource, DataSourceChildren, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	expression = VSQLAttr("?", get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	direction = EnumAttr(Direction, get=True, set=True, required=True, default=Direction.ASC, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	nulls = EnumAttr(Nulls, get=True, set=True, required=True, default=Nulls.LAST, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
		return self.id

	def save(self, handler:T_opt_handler=None, recursive:bool=True):
		raise NotImplementedError("DataOrder objects can only be saved by their parent")


@register("dataaction")
class DataAction(Base):
	"""
	A :class:`DataAction` object contains the -> None configuration of a data action.

	A data action gets executed on a record in certain situation automatically
	or on user demand.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: app
		:type: App

		The app this action belongs to

	.. attribute:: identifier
		:type: str

		Human readable identifier

	.. attribute:: name
		:type: str

		Human readable name

	.. attribute:: order
		:type: int

		Used to sort the actions for display

	.. attribute:: active
		:type: bool

		Is this action active (otherwise it willl be ignored for display/execution)

	.. attribute:: icon
		:type: File

		Icon to display for the action

	.. attribute:: description
		:type: str

		What does this action do?

	.. attribute:: message
		:type: str

		Message to output after the action has been executed

	.. attribute:: filter
		:type: str

		vSQL expression that determines whether this action should be
		displayed/executed

	.. attribute:: as_multiple_action
		:type: bool

		Should this action be displayed as a action button for multiple records
		in the datamanagement?

	.. attribute:: as_single_action
		:type: bool

		Should this action be displayed as a action button for single records in
		the datamanagement?

	.. attribute:: as_mail_link
		:type: bool

		Can this action be used as an email link (where clicking on the link in
		the email executes the action)?

	.. attribute:: before_update
		:type: bool

		Execute before displaying an update form?

	.. attribute:: after_update
		:type: bool

		Execute after updating the record?

	.. attribute:: before_insert
		:type: bool

		Execute before displaying an insert form?

	.. attribute:: after_insert
		:type: bool

		Execute after inserting the record?

	.. attribute:: before_delete
		:type: bool

		Execute before deleting the record?
	"""

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

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	active = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	icon = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	message = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	filter = VSQLAttr("vsqlsupport_pkg3.da_filter_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	as_multiple_action = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	as_single_action = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	as_mail_link = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	before_update = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	after_update = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	after_insert = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)
	before_delete = BoolAttr(get=True, set=True, required=True, default=False, ul4get=True, ul4onget=True, ul4onset=True)

	commands = Attr(get=True, set=True, ul4onget=True, ul4onset=True)

	def __init__(self, *args, id=None, identifier=None, name=None, order=None, active=True, icon=None, description=None, filter=None, as_multiple_action=None, as_single_action=None, as_mail_link=None, before_update=None, after_update=None, after_insert=None, before_delete=None):
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
		self.after_insert = after_insert
		self.before_delete = before_delete
		self.commands = []
		self.add(*args)

	@property
	def ul4onid(self) -> str:
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
	"""
	A :class:`DataAction` consists of multiple :class:`DataActionCommand`
	objects.

	Different command types are implemented by subclasses.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: parent
		:type: Union[DataAction, DataActionCommand]

		The data action this command belongs to or the command this comamnd is a
		sub command of.

	.. attribute:: condition
		:type: str

		Only execute the command when this vSQL condition is true.

	.. attribute:: details
		:type: list[DataActionDetail]

		Field expressions for each field of the target app or parameter of the command.
	"""

	ul4_attrs = {
		"id",
		"parent",
		"condition",
		"details",
	}
	ul4_type = ul4c.Type("la", "DataActionCommand", "A single instruction of a data action")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	parent = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	condition = VSQLAttr("vsqlsupport_pkg3.dac_condition_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	details = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, *args, id=None, condition=None):
		self.id = id
		self.parent = None
		self.condition = condition
		self.details = []
		self.add(*args)

	@property
	def ul4onid(self) -> str:
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
	"""
	A :class:`DataActionCommand` that updates an existing record.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandUpdate", "A data action instruction to update a rcord")


@register("dataactioncommand_task")
class DataActionCommandTask(DataActionCommand):
	"""
	A :class:`DataActionCommand` that creates a task.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandTask", "A data action instruction to create a task")


@register("dataactioncommand_delete")
class DataActionCommandDelete(DataActionCommand):
	"""
	A :class:`DataActionCommand` that deletes an existing record.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandDelete", "A data action instruction to delete a record")


@register("dataactioncommand_onboarding")
class DataActionCommandOnboarding(DataActionCommand):
	"""
	A :class:`DataActionCommand` that invites users to LivingApps and automatically
	installs a number of apps for them.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandOnboarding", "A data action instruction for onboarding")


@register("dataactioncommand_daterepeater")
class DataActionCommandDateRepeater(DataActionCommand):
	"""
	A :class:`DataActionCommand` that creates additional records based on timing
	information.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandDateRepeater", "A data action instruction for recurring records")


class DataActionCommandWithIdentifier(DataActionCommand):
	"""
	Base class of for all data actions that have an identifier an introduce additional vSQL variables.

	Relevant instance attributes are:

	.. attribute:: app
		:type: App

		The target app

	.. attribute:: identifier
		:type: str

		A variable name introduced by this command

	.. attribute:: children
		:type: list[DataActionCommand]

		The sub commands
	"""

	ul4_attrs = DataActionCommand.ul4_attrs.union({
		"app",
		"identifier",
		"children",
	})
	ul4_type = ul4c.Type("la", "DataActionCommandWithIdentifier", "The base type for data action instruction that havve fields")

	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	children = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, condition=None, app=None, identifier=None):
		super().__init__(id, condition)
		self.app = app
		self.identifier = identifier
		self.children = []

	def addcommand(self, *commands):
		for command in commands:
			command.parent = self
			self.children.append(command)
		return self


@register("dataactioncommand_insert")
class DataActionCommandInsert(DataActionCommandWithIdentifier):
	"""
	A :class:`DataActionCommand` that creates a new record.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandInsert", "A data action instruction to insert a new record")


@register("dataactioncommand_insertform")
class DataActionCommandInsertForm(DataActionCommandWithIdentifier):
	"""
	A :class:`DataActionCommand` that interactively lets the user create a new record.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandInsertForm", "A data action instruction to insert a new record via an HTML form")


@register("dataactioncommand_insertformstatic")
class DataActionCommandInsertFormStatic(DataActionCommandWithIdentifier):
	"""
	A :class:`DataActionCommand` that interactively lets the user create a new record.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandInsertFormStatic", "A data action instruction to insert a new record via an HTML form in a static app")


@register("dataactioncommand_loop")
class DataActionCommandLoop(DataActionCommandWithIdentifier):
	"""
	A :class:`DataActionCommand` that executes sub commands for a number of
	records.
	"""

	ul4_type = ul4c.Type("la", "DataActionCommandLoop", "A data action instruction for lookuping over a number of records")


@register("dataactiondetail")
class DataActionDetail(Base):
	"""
	A :class:`DataActionDetail` contains instructions how to set or modify a
	single field of a record affected by a :class:`DataActionCommand` or set
	a parameter for a :class:`DataActionCommand`.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: parent
		:type: DataActionCommand

		The data action command this detail belongs to

	.. attribute:: control
		:type: Control

		The control this detail refers to (i.e. which field/attribute to modify)

	.. attribute:: type
		:type: DataActionDetail.Type

		The type of action to perform on the field/attribute.

	.. attribute:: value
		:type:

		The value to use (if the :attr:`type` isn't ``Type.EXPR``). The type
		depends on the value of the field or parameter.

	.. attribute:: expression
		:type: str

		The vSQL expression used to set the field/attribute (if :attr:`type` is
		``Type.EXPR``)

	.. attribute:: formmode
		:type: DataActionDetail.FormMode

		How to display the field in interactive actions (i.e. ``insertform``
		and ``insertformstatic``)
	"""

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

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	parent = Attr(DataActionCommand, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	type = EnumAttr(Type, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	expression = VSQLAttr("vsqlsupport_pkg3.dac_condition_ful4on", get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	formmode = EnumAttr(FormMode, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
		return self.id

	def _code_get(self:T_opt_handler) -> "ll.la.handlers.Handler":
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
	"""
	An :class:`!Installation` describes an installation proccess that has been
	used to automatically install an app for a user.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: name
		:type: str

		Name of the installation
	"""

	ul4_attrs = {"id", "name"}
	ul4_type = ul4c.Type("la", "Installation", "The installation that created an app")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, name=None):
		self.id = id
		self.name = name

	vsqlgroup = vsql.Group(
		"installation_link",
		internalid=(vsql.DataType.STR, "upl_id"),
		id=(vsql.DataType.STR, "inl_id"),
		name=(vsql.DataType.STR, "inl_additional_name"),
	)


class LayoutControl(Base):
	r"""
	A :class:`!LayoutControl` is similar to a :class:`Control`, except that it
	does not correspond to a real field of :class:`Record`\s, but simply
	provides decoration for an input form (i.e. a :class:`View`).

	Specific types of decorations are implemented by subclasses.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: label
		:type: str

		Label to be displayed for this control

	.. attribute:: identifier
		:type: str

		Human readable identifier

	.. attribute:: view
		:type: View

		The view this layout control belongs to

	.. attribute:: top
		:type: int

		Vertical position of this layout control in the form

	.. attribute:: left
		:type: int

		Horizontal position of this layout control in the form

	.. attribute:: width
		:type: int

		Width of this layout control in the form

	.. attribute:: height
		:type: int

		height of this layout control in the form
	"""

	ul4_attrs = {"id", "label", "identifier", "view", "type", "subtype", "top", "left", "width", "height"}
	ul4_type = ul4c.Type("la", "LayoutControl", "A decoration in an input form")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	label = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	view = Attr(lambda: View, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	top = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	left = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, label=None, identifier=None):
		self.id = id
		self.label = label
		self.identifier = identifier

	@property
	def ul4onid(self) -> str:
		return self.id


@register("htmllayoutcontrol")
class HTMLLayoutControl(LayoutControl):
	"""
	A :class:`!HTMLLayoutControl` provides HTML "decorarion" in an input form.

	Relevant instance attributes are:

	.. attribute:: value
		:type: str

		HTML source
	"""

	type = "string"
	_subtype = "html"

	ul4_attrs = LayoutControl.ul4_attrs.union({"value"})
	ul4_type = ul4c.Type("la", "HTMLLayoutControl", "HTML decoration in an input form")

	value = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("imagelayoutcontrol")
class ImageLayoutControl(LayoutControl):
	"""
	An :class:`!ImageLayoutControl` provides an image as decorarion for an input form.

	Relevant instance attributes are:

	.. attribute:: image_original
		:type: File

		Original uploaded image

	.. attribute:: image_scaled
		:type: File

		Image scaled to final size
	"""

	type = "image"
	_subtype = None

	ul4_attrs = LayoutControl.ul4_attrs.union({"image_original", "image_scaled"})
	ul4_type = ul4c.Type("la", "ImageLayoutControl", "An image decoration in an input form")

	image_original = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	image_scaled = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("view")
class View(Base):
	r"""
	An :class:`App` can have multiple :class:`View`\s which provide different
	form for creating or changing record.

	This differnt version can be used for example to provide the input form in
	multiple languages or for multiple roles or workflow states.

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: name
		:type: str

		The name of the view as configured in the FormBuilder.

	.. attribute:: combined_type
		:type: Optional[CombinedType]

		If this is a combined view, the type of the combined view.

	.. attribute:: app
		:type: App

		The app this view belongs to

	.. attribute:: order
		:type: int

		Used to sort the views

	.. attribute:: width
		:type: int

		Width of the view in pixels

	.. attribute:: height
		:type: int

		height of the view in pixels

	.. attribute:: start
		:type: Optional[datetime.datetime]

		View is inactive before this date

	.. attribute:: end
		:type: Optional[datetime.datetime]

		View is inactive after this date

	.. attribute:: controls
		:type: dict[str, ViewControl]

		Additional information for the fields used in this view

	.. attribute:: layout_controls
		:type: dict[str, LayoutControl]

		The layout controls used in this view

	.. attribute:: lang
		:type: str

		Language of this view
	"""

	ul4_attrs = {"id", "name", "app", "order", "width", "height", "start", "end", "lang", "controls", "layout_controls"}
	ul4_type = ul4c.Type("la", "View", "An input form for a LivingApps application")

	class CombinedType(misc.Enum):
		"""
		If this is a combined view, the type of the combined view.
		"""

		TABS = "tabs"
		WIZARD = "wizard"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	combined_type = EnumAttr(CombinedType, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	start = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	end = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	layout_controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lang = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
		return self.id


@register("datasourcedata")
class DataSourceData(Base):
	"""
	A :class:`!DataSourceData` object provides information about one (or more)
	apps and their records to a :class:`ViewTemplate` or other templates.

	This information is configured by :class:`DataSource` objects.

	Relevant instance attribytes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: identifier
		:type: str

		A unique identifier for the data source

	.. attribute:: app
		:type: Optional[App]

		The app reference byd this datasource (or ``None`` when the datasource is
		configured for all apps)

	.. attribute:: apps
		:type: dict[str, App]

		All apps that this datasource references (can only be more than one
		if copies of this app or all apps are included)
	"""

	ul4_attrs = {"id", "identifier", "app", "apps"}
	ul4_type = ul4c.Type("la", "DataSourceData", "The data resulting from a data source configuration")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	apps = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id:str=None, identifier:str=None, app:Optional["App"]=None, apps:Dict[str, "App"]=None):
		self.id = id
		self.identifier = identifier
		self.app = app
		self.apps = apps

	@property
	def ul4onid(self) -> str:
		return self.id


@register("lookupitem")
class LookupItem(Base):
	r"""
	A :class:`!LookupItem` is the field value of :class:`LookupControl`\s and
	:class:`MultipleLookupControl`\s fields.

	Relevant instance attributes/properties are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: control
		:type: LookupControl

		The control this lookup item belongs to

	.. attribute:: key
		:type: str

		Human readable identifier

	.. attribute:: label
		:type: str

		Label to be displayed for this lookup item

	.. attribute:: visible
		:type: bool

		Is this item visible in the currently active view?
	"""

	ul4_attrs = {"id", "control", "key", "label", "visible"}
	ul4_type = ul4c.Type("la", "LookupItem", "An option in a lookup control/field")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	control = Attr(lambda: LookupControl, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	key = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get="", set="", repr=True, ul4get="_label_get", ul4onget="_label_get", ul4onset="_label_set", ul4ondefault="")
	visible = BoolAttr(get="", repr="", ul4get="_visible_get")

	def __init__(self, id=None, control=None, key=None, label=None):
		self.id = id
		self.control = control
		self.key = key
		self._label = label

	def _get_viewcontrol(self):
		if self.control is None:
			return None
		active_view = self.control.app.active_view
		if active_view is None or not active_view.controls:
			return None
		return active_view.controls.get(self.control.identifier, None)

	def _get_viewlookupitem(self) -> Optional["ViewLookupItem"]:
		viewcontrol = self._get_viewcontrol()
		if viewcontrol is None or viewcontrol.lookupdata is None:
			return None
		try:
			return viewcontrol.lookupdata[self.key]
		except KeyError:
			return None

	def _label_get(self) -> str:
		viewlookupitem = self._get_viewlookupitem()
		if viewlookupitem is None:
			return self._label
		return viewlookupitem.label

	def _label_set(self, label:T_opt_str) -> None:
		self._label = label

	def _label_ul4ondefault(self) -> None:
		self._label = None

	def _visible_get(self) -> bool:
		viewlookupitem = self._get_viewlookupitem()
		if viewlookupitem is None:
			return True
		return viewlookupitem.visible

	def _visible_repr(self) -> T_opt_str:
		if self.visible:
			return None
		else:
			return "visible=False"

	@property
	def ul4onid(self) -> str:
		return self.id


@register("viewlookupitem")
class ViewLookupItem(Base):
	"""
	A :class:`!ViewLookupItem` provides additional view specific information
	for a :class:`LookupItem`.

	Relevant instance attributes are:

	.. attribute:: key
		:type: str

		Human readable identifier

	.. attribute:: label
		:type: str

		Label to be displayed for this lookup item

	.. attribute:: visible
		:type: bool

		Is this lookup item visible in its view?
	"""

	ul4_attrs = {"key", "label", "visible"}
	ul4_type = ul4c.Type("la", "ViewLookupItem", "View specific information about a lookup item")

	key = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	visible = BoolAttr(get=True, set=True, repr="", ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id:str=None, key:str=None, label:str=None, visible:bool=None):
		self.key = key
		self.label = label
		self.visible = visible

	def _visible_repr(self) -> T_opt_str:
		if self.visible:
			return None
		else:
			return "visible=False"


@register("category")
class Category(Base):
	r"""
	A navigation category.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: identifier
		:type: str

		Human readable identifier.

	.. attribute:: name
		:type: str

		Label to be displayed for this category in the navigation.

	.. attribute:: order
		:type: int

		Used to order the categories in the navigation.

	.. attribute:: parent
		:type: Optional[Category]

		The parent category.

	.. attribute:: children
		:type: Optional[dict[str, Category]]

		The child categories.

	.. attribute:: apps
		:type: Optional[dict[str, App]]

		The apps that belong to that category. The :class:`dict` keys are the
		:class:`App`'s :attr:`~App.id`\s.
	"""

	ul4_attrs = {"id", "identifier", "name", "order", "parent", "children", "apps"}
	ul4_type = ul4c.Type("la", "Category", "A navigation category")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	parent = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	children = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	apps = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id:str=None, identifier:str=None, name:str=None, order:int=None, parent:Optional["Category"]=None, children:Optional[List["Category"]]=None, apps:Optional[Dict[str, App]]=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.order = order
		self.parent = parent
		self.children = children
		self.apps = apps

	@property
	def ul4onid(self) -> str:
		return self.id


@register("appparameter")
class AppParameter(Base):
	r"""
	An additional parameter for an app.

	This can e.g. be used to provide a simple way to configure the behaviour
	of :class:`ViewTemplate`\s.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: app
		:type: App

		The app this parameter belong to

	.. attribute:: identifier
		:type: str

		Human readable identifier

	.. attribute:: description
		:type: str

		Description of the parameter

	.. attribute:: value

		The parameter value. The type of the value depends on the type of the
		parameter. Possible types are: :class:`bool`, :class:`int`,
		:class:`float`, :class:`str`, :class:`~ll.color.Color`,
		:class:`datetime.date`, :class:`datetime.datetime`,
		:class:`datetime.timedelta`, :class:`~ll.misc.monthdelta`,
		:class:`File` and :class:`App` (and ``None``).

	.. attribute:: createdat
		:type: datetime.datetime

		When was this parameter created?

	.. attribute:: createdby
		:type: User

		Who created this parameter?

	.. attribute:: updatedat
		:type: Optional[datetime.datetime]

		When was this parameter last updated?

	.. attribute:: updatedby
		:type: Optional[User]

		Who updated this parameter last?
	"""

	ul4_attrs = {"id", "app", "identifier", "description", "value", "createdat", "createdby", "updatedat", "updatedby"}
	ul4_type = ul4c.Type("la", "AppParameter", "A parameter of a LivingApps application")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	value = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

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
	def ul4onid(self) -> str:
		return self.id


class HTTPRequest(Base):
	r"""
	An :class:`HTTPRequest` object holds values related to an HTTP request.

	Relevant instance attributes are:

	.. attribute:: method
		:type: str

		Request method (e.g. ``'get'`` or ``'post'`` etc.)

	.. attribute:: headers
		:type: requests.structures.CaseInsensitiveDict[str, str]

		Request headers as a :class:`dict` with case-insensitive keys.

	.. attribute:: params
		:type: dict[str, Union[str, File, list[Union[str, File]]]

		Request parameters.

		Normally parameter value are :class:`str`\s. An uploaded filed in a
		``POST`` request is a :class:`File`. If a parameter is specified multiple
		times the value will be a list (of :class:`str`\s or :class:`File`\s).

	Relevant class attributes are:

	.. attribute:: vsqlfield
		:type: ll.la.vsql.Field

		The vSQL field for the vSQL variable ``params`` that references ``vsqlgroup``.

	.. attribute:: vsqlgroup
		:type: ll.la.vsql.Group

		The vSQL group for the vSQL variable ``params`` with the following
		subgroups: ``str``, ``strlist``, ``int``, ``intlist``, ``float``,
		``floatlist``, ``date``, ``datelist``, ``datetime`` and ``datetimelist``.

	.. attribute:: vsqlsearchexpr
		:type: ll.la.vsql.Field

		The vSQL expression used for the search term in the Ajax search.

		This search term is used in the input form for
		:class:`AppLookupChoiceControl` and
		:class:`MultipleAppLookupChoiceControl` fields.
	"""

	ul4_attrs = {"method", "headers", "params", "seq"}
	ul4_type = ul4c.Type("la", "HTTPRequest", "An HTTP request")

	method = Attr(str, get=True, set=True, repr=True, ul4get=True)
	headers = CaseInsensitiveDictAttr(get=True, ul4get=True)
	params = AttrDictAttr(get=True, ul4get=True)

	def __init__(self, method:str="get"):
		self.method = method
		self.headers = {}
		self.parsms = {}
		self._seqvalue = 0

	def seq(self) -> int:
		result = self._seqvalue
		self._seqvalue += 1
		return result

	datatypes = {
		vsql.DataType.STR,
		vsql.DataType.STRLIST,
		vsql.DataType.INT,
		vsql.DataType.INTLIST,
		vsql.DataType.NUMBER,
		vsql.DataType.NUMBERLIST,
		vsql.DataType.DATE,
		vsql.DataType.DATELIST,
		vsql.DataType.DATETIME,
		vsql.DataType.DATETIMELIST,
	}

	vsqlgroup = vsql.Group(
		**{
			dt.value: vsql.Field(refgroup=vsql.Group(**{"*": vsql.Field("*", dt)}))
			for dt in datatypes
		}
	)

	vsqlfield = vsql.Field("params", refgroup=vsqlgroup)


from .handlers import *
