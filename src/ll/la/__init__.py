#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2025 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
:mod:`ll.la` provides a Python API for the LivingApps system.

See http://www.living-apps.de/ or http://www.living-apps.com/ for more info.
"""

import os, io, re, unicodedata, datetime, mimetypes, operator, string, json, pathlib, types, enum, math, base64
import urllib.parse as urlparse
import collections
from collections import abc

from PIL import Image

import requests.structures
import validators

from ll import misc, url, ul4c, ul4on, color # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``

from ll.la import vsql


__docformat__ = "reStructuredText"


###
### Typing stuff
###

from typing import *

T_opt_handler = Optional["ll.la.handlers.Handler"]


###
### Utility functions and classes
###

NoneType = type(None)

module = types.ModuleType("la", "LivingAPI types")
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


def url_with_params(url, first, params):
	"""
	Appends a query string to an url.

	``url`` is the base URL.

	``first`` specifies if the parameters in ``params`` are the first
	parameters (if ``first`` is true) or the URL already contains parameters
	(if ``first`` is false).

	``params`` must be a dictionary. Values can be:

	:const:`None`
		Those will be ignore

	:class:`str`
		Those will be output as is

	:class:`list` or :class:`set`
		Those will be output recursively as multiple parameters

	Anything else
		Will be converted to a string via UL4's ``str`` function.

	For example::

		>>> la.url_with_params('/url', True, {})
		'/url'
		>>> la.url_with_params('/url?foo=bar', False, {'foo': 'bar?'})
		'/url?foo=bar&foo=bar%3F'
		>>> la.url_with_params('/url', True, {'foo': 'bar?'})
		'/url?foo=bar%3F'
		>>> la.url_with_params('/url', True, {'foo': 'bar?'})
		'/url?foo=bar%3F'
		>>> la.url_with_params('/url', True, {'foo': 'bar?'})
		'/url?foo=bar%3F'
		>>> la.url_with_params('/url', True, {'foo': ['bar', 42]})
		'/url?foo=bar&foo=42'
		>>> la.url_with_params('/url', True, {'foo': ['bar', 42], 'baz': None})
		'/url?foo=bar&foo=42'
		>>> la.url_with_params('/url', True, {'foo': datetime.datetime.now()})
		'/url?foo=2022-10-28%2013%3A26%3A42.643636'
	"""
	def flatten_param(name, value):
		if isinstance(value, (list, set)):
			for v in value:
				yield from flatten_param(name, v)
		elif isinstance(value, str):
			yield (name, value)
		elif value is not None:
			yield (name, ul4c._str(value))

	params = "&".join(f"{urlparse.quote(n)}={urlparse.quote(v)}" for (name, value) in params.items() for (n, v) in flatten_param(name, value))
	if params:
		url += "&?"[bool(first)] + params
	return url


def format_class(cls : Type) -> str:
	"""
	Format the name of the class object ``cls``.

	Example::

		>>> format_class(int)
		'int'
	"""
	if cls is NoneType or cls is None:
		return "None"
	else:
		mod = getattr(cls, "__module__", None)
		if mod is not None and mod not in ("builtins", "exceptions"):
			return f"{mod}.{cls.__qualname__}"
		else:
			return cls.__qualname__


def format_list(items: list[str]) -> str:
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

	def __getattr__(self, key: Any) -> Any:
		try:
			return self[key]
		except KeyError:
			raise AttributeError(error_attribute_doesnt_exist(self, key))

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		return set(dir(dict)) | set(self)


def makeattrs(value: Any) -> Any:
	r"""
	Convert :class:`dict`\s into :class:`attrdict`\s.

	If ``value`` is not a :class:`dict` (or it already is an :class:`attrdict`)
	it will be returned unchanged.
	"""
	if isinstance(value, dict) and not isinstance(value, attrdict):
		value = attrdict(value)
	return value


def _make_filter(filter: list[str] | str | None) -> list[str]:
	if filter is None:
		return []
	elif isinstance(filter, str):
		return [filter]
	elif isinstance(filter, list):
		for f in filter:
			if f is not None and not isinstance(f, str):
				raise TypeError(error_argument_wrong_type("filter", f, str))
		return [f for f in filter if f is not None]
	else:
		raise TypeError(error_argument_wrong_type("filter", filter, list))


def _make_sort(sort: list[str] | str | None) -> list[str]:
	if sort is None:
		return []
	elif isinstance(sort, str):
		return [sort]
	elif isinstance(sort, list):
		for s in sort:
			if s is not None and not isinstance(s, str):
				raise TypeError(error_argument_wrong_type("sort", s, str))
		return [s for s in sort if s is not None]
	else:
		raise TypeError(error_argument_wrong_type("filter", filter, list))


def _make_offset(offset: int | None) -> int | None:
	if offset is not None and not isinstance(offset, int):
		raise TypeError(error_argument_wrong_type("offset", offset, (int, None)))
	return offset


def _make_limit(limit: int | None) -> int | None:
	if limit is not None and not isinstance(limit, int):
		raise TypeError(error_argument_wrong_type("limit", limit, (int, None)))
	return limit


def error_attribute_doesnt_exist(instance: Any, name: str) -> str:
	return f"{misc.format_class(instance)!r} object has no attribute {name!r}."


def error_attribute_readonly(instance: Any, name: str) -> str:
	return f"Attribute {name!r} of {misc.format_class(instance)!r} object is read only."


def error_attribute_wrong_type(instance: Any, name: str, value: Any, allowed_types: list[Type]) -> str:
	if isinstance(allowed_types, (tuple, list)):
		allowed_types = format_list([format_class(t) for t in allowed_types])
	else:
		allowed_types = format_class(allowed_types)

	return f"Value for attribute {name!r} of {misc.format_class(instance)!r} object must be {allowed_types}, but is {format_class(type(value))}."


def error_argument_wrong_type(name: str, value: Any, allowed_types: list[Type] | Type) -> str:
	if isinstance(allowed_types, (tuple, list)):
		allowed_types = format_list([format_class(t) for t in allowed_types])
	else:
		allowed_types = format_class(allowed_types)

	return f"Argument {name!r} must be {allowed_types}, but is {format_class(type(value))}."


def attribute_wrong_value(instance: Any, name: str, value: Any, allowed_values: Iterable) -> str:
	allowed_values = format_list([repr(value) for value in allowed_values])

	return f"Value for attribute {name!r} of {misc.format_class(instance)} object must be {allowed_values}, but is {value!r}."


def error_required(field: Field, value: Any) -> str:
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


def error_truerequired(field: Field, value: Any) -> str:
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


def error_wrong_type(field: Field, value: Any) -> str:
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


def error_string_tooshort(field: Field, minlength: int, value: Any) -> str:
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


def error_string_toolong(field: Field, maxlength: int, value: Any) -> str:
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


def error_wrong_value(value: Any) -> str:
	"""
	Return an error message for a field value that isn't supported.

	For example when a date field is set to a string value, but the string has
	an unrecognized format, this error message will be used.
	"""
	return f"Value {value!r} is not supported."


def error_date_format(field: Field, value: Any) -> str:
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


def error_lookupitem_unknown(field: Field, value: str) -> str:
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


def error_lookupitem_foreign(field: Field, value: LookupItem) -> str:
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


def error_applookuprecord_unknown(value: str) -> str:
	"""
	Return an error message for a unknown record identifier.

	Used when setting the field of an applookup control to a record identifier
	that can't be found in the target app.
	"""
	return f"Record with id {value!r} unknown."


def error_applookuprecord_foreign(field: Field, value: Record) -> str:
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


def error_applookup_notargetapp(control: Control) -> str:
	"""
	Return an error message for an applookup without a target app.

	This can happen, when the target app gets deleted.
	"""
	lang = control.app.globals.lang
	if lang == "de":
		return 'Ziel-App nicht vorhanden'
	elif lang == "fr":
		return 'No target app'
	elif lang == "it":
		return 'No target app'
	else:
		return 'No target app'


def error_applookup_norecords(control: Control) -> str:
	"""
	Return an error message for an applookup target app without records.
	"""
	lang = control.app.globals.lang
	if lang == "de":
		return 'Keine Datensätze in Ziel-App'
	elif lang == "fr":
		return 'No records in target app'
	elif lang == "it":
		return 'No records in target app'
	else:
		return 'No records in target app'


def error_email_format(lang: str, label: str, value: str) -> str:
	"""
	Return an error message for malformed email address.
	"""
	if lang == "de":
		return f'"{label}" muss eine gültige E-Mail-Adresse sein.'
	elif lang == "fr":
		return f'«{label}» doit comporter une adresse e-mail valide.'
	elif lang == "it":
		return f'"{label}" deve essere un indirizzo email valido.'
	else:
		return f'"{label}" must be a valid email address.'


def error_email_badchar(lang: str, label: str, pos: int, value: str) -> str:
	"""
	Return an error message for a bad character in an email address.
	"""
	char = value[pos]
	charname = unicodedata.name(char, "unassigned character")
	char = ord(char)
	char = f"U+{char:08X}" if char > 0xfff else f"U+{char:04X}"
	if lang == "de":
		return f'"{label}" muss eine gültige E-Mail-Adresse sein, enthält aber das Zeichen {char} ({charname}) an Position {pos+1}.'
	else:
		return f'"{label}" must be a valid email address, but contains the character {char} ({charname}) at position {pos+1}.'


def error_tel_format(field: Field, value: str) -> str:
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


def error_url_format(field: Field, value: str) -> str:
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


def error_file_invaliddataurl(field: Field, value: str) -> str:
	"""
	Return an error message for an invalid ``data`` URL fir a ``file/signature`` field.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'Data-URL ist ungültig.'
	else:
		return f'Data URL is invalid.'


def error_file_unknown(field: Field, value: str) -> str:
	"""
	Return an error message for an invalid ``data`` URL fir a ``file/signature`` field.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
			return f'Die Datei {value} für "{field.label}" wurde nicht gefunden.'
	elif lang == "fr":
			return f'Le fichier {value} pour «{field.label}» n\'a pas été trouvé.'
	elif lang == "it":
			return f'Il file {value} per "{field.label}" non è stato trovato.'
	else:
			return f'The file {value} for "{field.label}" could not be found.'


def error_number_format(field: Field, value: str) -> str:
	"""
	Return an error message for string that can't be convertet to a float or int.
	"""
	lang = field.control.app.globals.lang
	if lang == "de":
		return f'"{field.label}" unterstützt dieses Zahlenformat nicht.'
	else:
		return f'"{field.label}" doesn\'t support this number format.'


def error_object_unsaved(value: File | Record) -> str:
	"""
	Return an error message for an unsaved referenced object.
	"""
	return f"Referenced object {value!r} hasn't been saved yet."


def error_object_deleted(value: File | Record) -> str:
	"""
	Return an error message for an deleted referenced object.
	"""
	return f"Referenced object {value!r} has been deleted."


def error_foreign_view(view: View) -> str:
	return f"View {view!r} belongs to the wrong app."


def error_foreign_control(control: Control) -> str:
	return f"Control {control!r} belongs to the wrong app."


def error_control_not_in_view(control: Control, view: View) -> str:
	return f"Control {control!r} is not in view {view!r}."


def _resolve_type(t: Type | Callable[[], Type]) -> Type:
	if not isinstance(t, type):
		t = t()
	return t


def _is_timezone(value: str) -> bool:
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

	def __init__(self, record: Record, message: str):
		self.record = record
		self.message = message

	def __str__(self) -> str:
		return f"Validation for {self.record!r} failed: {self.message}"


class FieldValidationError(ValueError):
	"""
	Exception that is raised when a field of a record is invalid and the record
	is saved without ``force=True``.
	"""

	def __init__(self, field: Field, message: str):
		self.field = field
		self.message = message

	def __str__(self) -> str:
		return f"Validation for {self.field!r} failed: {self.message}"


class VersionMismatchError(ValueError):
	"""
	Exception that is raised when we get the wrong version for
	``Globals.version``.
	"""

	def __init__(self, encountered_version: str, expected_version: str):
		self.encountered_version = encountered_version
		self.expected_version = expected_version

	def __str__(self) -> str:
		return f"invalid LivingAPI version: expected {self.expected_version!r}, got {self.encountered_version!r}"


class UnsavedObjectError(ValueError):
	"""
	Exception that is raised when we are saving an object that references another object
	that hasn't been saved yet.
	"""

	def __init__(self, object : File | Record):
		self.object = object

	def __str__(self) -> str:
		return error_object_unsaved(self.object)


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
	def types(self) -> tuple[Type, ...]:
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
			return f"{self.name}={value.value!r}"
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
	def ul4oncreate(cls, id: str | None=None) -> Base:
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

	def ul4onload_begin(self, decoder: ul4on.Decoder) -> None:
		"""
		Called before the content of the object is loaded from an UL4ON dump.

		The default implementation does nothing.
		"""

	def ul4onload_end(self, decoder: ul4on.Decoder) -> None:
		"""
		Called after the content of the object has been loaded from an UL4ON dump.

		The default implementation does nothing.
		"""

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		return {name for name in self.__dict__ if name.startswith("x_")}

	def ul4_getattr(self, name: str) -> Any:
		attr = getattr(self.__class__, name, None)
		if isinstance(attr, Attr):
			return attr.ul4get(self)
		elif isinstance(attr, property):
			return attr.fget(self)
		elif self.ul4_hasattr(name):
			return getattr(self, name)
		raise AttributeError(error_attribute_doesnt_exist(self, name))

	def ul4_hasattr(self, name: str) -> Any:
		return name in self.ul4_attrs or name.startswith("x_")

	def ul4_setattr(self, name: str, value: Any) -> None:
		attr = getattr(self.__class__, name, None)
		if isinstance(attr, Attr):
			return attr.ul4set(self, value)
		elif isinstance(attr, property):
			return attr.fset(self, value)
		elif name.startswith("x_"):
			return setattr(self, name, value)
		raise AttributeError(error_attribute_doesnt_exist(self, name))


class CustomAttributes(Base):
	ul4_attrs = Base.ul4_attrs.union({"custom"})

	def __init__(self):
		super().__init__()
		self.custom = None

	@misc.notimplemented
	def _template_candidates(self) -> Generator[dict[str, ul4c.Template], None, None]:
		yield from []

	def _boundtemplate_candidates(self) -> Generator[dict[str, ul4c.Template | ul4c.BoundTemplate], None, None]:
		for templates in self._template_candidates():
			yield dict((identifier, ul4c.BoundTemplate(self, template) if self._template_is_bound(template) else template) for (identifier, template) in templates.items())

	@property
	def templates(self) -> Mapping[str, ul4c.Template | ul4c.BoundTemplate]:
		return collections.ChainMap(*self._boundtemplate_candidates())

	def _template_is_bound(self, template : ul4c.Template) -> bool:
		"""
		Return whether the template is supposed to be a bound member template.

		A bound member template can be called as a method and implicitely passes
		``self`` as the first argument.

		A "unbound" member templates behaves like a global function (and can only
		appear as attributes of :class:`App` or :class:`Globals`).

		We can determine the result based on the templates ``namespace`` (and need
		to overwrite this method for :class:`Field` or :class:`Control` member templates
		bound to specific instances).
		"""
		return template.namespace.endswith("_instance")

	def _fetch_template(self, identifier):
		for templates in self._template_candidates():
			if identifier in templates:
				template = templates[identifier]
				if self._template_is_bound(template):
					template = ul4c.BoundTemplate(self, template)
				return template
		return None

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = set(self.ul4_attrs)
		for attrname in self.__dict__:
			if attrname.startswith("x_"):
				attrs.add(attrname)
		for templates in self._template_candidates():
			for identifier in templates:
				attrs.add(f"t_{identifier}")
		return attrs

	def __getattr__(self, name):
		if name.startswith("t_"):
			template = self._fetch_template(name[2:])
			if template is not None:
				return template
		raise AttributeError(error_attribute_doesnt_exist(self, name)) from None

	def ul4_dir(self):
		return dir(self)

	def ul4_hasattr(self, name: str) -> bool:
		if name in self.ul4_attrs:
			return True
		elif name.startswith("x_"):
			return name in self.__dict__
		elif name.startswith("t_"):
			identifier = name[2:]
			for templates in self._template_candidates():
				if identifier in templates:
					return True
			return False
		else:
			return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name.startswith("x_"):
			return getattr(self, name)
		elif name.startswith("t_"):
			template = self._fetch_template(name[2:])
			if template is not None:
				return template
		return super().ul4_getattr(name)

	def ul4_setattr(self, name: str, value: Any) -> None:
		if name.startswith("x_") or name == "custom":
			setattr(self, name, value)
		else:
			super().ul4_setattr(name, value)


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

	ul4_attrs = Base.ul4_attrs.union({"timestamp", "type", "title", "message"})
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
class File(CustomAttributes):
	"""
	An uploaded file.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: globals
		:type: Globals

		The :class:`Globals` objects.

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

	.. attribute:: size
		:type: int

		The filesize in bytes.

	.. attribute:: duration
		:type: Optional[int]

		Duration of the audio or video file in milliseconds.

	.. attribute:: geo
		:type: Optional[Geo]

		Location where the original file was recorded/created (extracted from EXIF).

	.. attribute:: recordedat
		:type: datetime.datetime

		Point in time when the original file was recorded/created (extracted from EXIF).

	.. attribute:: internal_id
		:type: str

		Internal database id.

	.. attribute:: createdat
		:type: datetime.datetime

		When was this file uploaded?
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({"id", "url", "filename", "mimetype", "width", "height", "size", "recordedat", "createdat"})
	ul4_type = ul4c.Type("la", "File", "An uploaded file")

	id = Attr(str, get=True, set=True, ul4get=True)
	globals = Attr(lambda: Globals, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	filename = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	mimetype = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	width = Attr(int, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	height = Attr(int, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	internal_id = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	size = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	duration = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	geo = Attr(lambda: Geo, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	recordedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	storagefilename = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	archive = Attr(lambda: File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	url = Attr(str, get="", ul4get="_url_get", repr="_url_repr")
	archive_url = Attr(str, get=True, ul4get=True)
	context_id = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, filename=None, mimetype=None, width=None, height=None, size=None, duration=None, geo=None, recordedat=None, storagefilename=None, archive=None, internal_id=None, createdat=None, content=None):
		super().__init__()
		self.id = id
		self.globals = None
		self.filename = filename
		self.mimetype = mimetype
		self.width = width
		self.height = height
		self.size = size
		self.duration = duration
		self.geo = geo
		self.recordedat = recordedat
		self.storagefilename = storagefilename
		self.internal_id = internal_id
		self.createdat = createdat
		self.context_id = None
		self._content = content
		if content is not None and mimetype.startswith("image/") and width is None and height is None:
			from PIL import Image # This requires :mod:`Pillow`, which you can install with ``pip install pillow``
			stream = io.BytesIO(content)
			with Image.open(stream) as img:
				self.width = img.size[0]
				self.height = img.size[1]

	def _template_candidates(self):
		handler = self.globals._gethandler()
		yield handler.fetch_internaltemplates(self.globals.app.id, "file_instance", None)
		yield handler.fetch_librarytemplates("file_instance")

	def ul4_getattr(self, name: str) -> Any:
		if name == "internalid":
			return self.internal_id
		else:
			return super().ul4_getattr(name)

	@property
	def ul4onid(self) -> str:
		return self.id

	def _url_get(self) -> str:
		if self.context_id is not None and self.id is not None:
			if self.globals is None:
				return f"/files/{self.context_id}/{self.id}"
			else:
				return f"https://{self.globals.hostname}/files/{self.context_id}/{self.id}"
		else:
			return None

	def _url_repr(self) -> str:
		return f"url={self.url!r}"

	@property
	def archive_url(self) -> str:
		if self.archive is None:
			return self.url
		else:
			return f"{self.archive.url}/{self.filename}"

	def save_meta(self) -> None:
		self.globals._gethandler().save_file(self)

	def content(self) -> bytes:
		"""
		Return the file content as a :class:`bytes` object.
		"""
		if self._content is not None:
			return self._content
		return self.globals._gethandler().file_content(self)

	vsqlgroup = vsql.Group(
		"upload_ref_select",
		internal_id=(vsql.DataType.STR, "upl_id"),
		id=(vsql.DataType.STR, "upr_path"),
		filename=(vsql.DataType.STR, "upl_orgname"),
		mimetype=(vsql.DataType.STR, "upl_mimetype"),
		width=(vsql.DataType.INT, "upl_width"),
		height=(vsql.DataType.INT, "upl_height"),
		size=(vsql.DataType.INT, "upl_size"),
		duration=(vsql.DataType.INT, "upl_duration"),
		recordedat=(vsql.DataType.DATETIME, "upl_recorddate"),
		createdat=(vsql.DataType.DATETIME, "upl_ctimestamp"),
	)


@register("geo")
class Geo(Base):
	"""
	Geolocation information.

	Relevant instance attributes are:

	.. attribute:: globals
		:type: Globals

		The :class:`Globals` objects.

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

	ul4_attrs = Base.ul4_attrs.union({"lat", "long", "info"})
	ul4_type = ul4c.Type("la", "Geo", "Geographical coordinates and location information")

	globals = Attr(lambda: Globals, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lat = FloatAttr(get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	long = FloatAttr(get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	info = Attr(str, get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, lat=None, long=None, info=None):
		self.globals = None
		self.lat = lat
		self.long = long
		self.info = info

	def _template_candidates(self):
		handler = self.globals._gethandler()
		yield handler.fetch_internaltemplates(self.globals.app.id, "geo_instance", None)
		yield handler.fetch_librarytemplates("geo_instance")

	def __getattr__(self, name: str) -> Any:
		if name.startswith("t_"):
			template = self._fetch_template(name[2:])
			if template is not None:
				return template
		raise AttributeError(error_attribute_doesnt_exist(self, name)) from None

	def ul4_hasattr(self, name: str) -> bool:
		if name.startswith("t_"):
			identifier = name[2:]
			for templates in self._template_candidates():
				if identifier in templates:
					return True
			return False
		else:
			return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name.startswith(("t_")):
			return getattr(self, name)
		else:
			return super().ul4_getattr(name)

	@classmethod
	def ul4oncreate(cls, id: str | None=None) -> Geo:
		return cls()


@register("user")
class User(CustomAttributes):
	r"""
	A LivingApps user account.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: globals
		:type: Globals

		The :class:`Globals` objects.

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

		The users fax number

	.. attribute:: lang
		:type: str

		Preferred language

	.. attribute:: image
		:type: File

		Avatar icon (visible in the top right corner of the page when this user
		is logged in)

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

	Note that the following attributes will always be ``None`` for users that
	are not the logged in user: ``street``, ``streetnumber``, ``zip``, ``city``,
	``phone``, ``fax``, ``summary``, ``interests``, ``personal_website``,
	``company_website``, ``company``, ``position``, ``department``.
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({
		"id", "globals", "gender", "title", "firstname", "surname", "initials", "email",
		"lang", "image", "avatar_small", "avatar_large", "streetname", "streetnumber",
		"zip", "city", "phone", "fax", "summary", "interests", "personal_website",
		"company_website", "company", "position", "department", "keyviews", "change"
	})
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
	image = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	avatar_small = Attr(File, get="_image_get", ul4get="_image_get")
	avatar_large = Attr(File, get="_image_get", ul4get="_image_get")
	summary = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	interests = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	personal_website = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	company_website = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	company = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	position = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	department = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	keyviews = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	globals = Attr(lambda: Globals, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

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

	def _image_get(self) -> File | None:
		return self.image

	def _template_candidates(self):
		handler = self.globals._gethandler()
		yield handler.fetch_internaltemplates(self.globals.app.id, "user_instance", None)
		yield handler.fetch_librarytemplates("user_instance")

	@classmethod
	def vsqlfield(cls, ul4var: str="user", sqlvar: str="livingapi_pkg.global_user") -> vsql.Field:
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
		image=(
			vsql.DataType.STR,
			"upl_id_image",
			"({m}.upl_id_image = {d}.upl_id and {d}.upr_table = 'identity' and {d}.upr_pkvalue = {m}.ide_id and {d}.upr_field = 'upl_id_image')",
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

	def isvalidemail(self, emailaddress: str) -> str | None:
		if not EmailField._pattern.match(emailaddress):
			pos = misc.first(i for (i, c) in enumerate(emailaddress) if ord(c) > 0x7f)
			if pos is not None:
				return error_email_badchar(self.globals.lang, "email", pos, emailaddress)
			else:
				return error_email_format(self.globals.lang, "email", emailaddress)
		return None

	def change(self, oldpassword: str, newpassword: str | None, newemail: str | None) -> list[str]:
		errormessages = []
		if newpassword is not None or newemail is not None:
			if newemail is not None:
				errormessage = self.isvalidemail(newemail)
				if errormessage is not None:
					errormessages.append(errormessage)
			if not errormessages:
				dberrormessage = self.globals._gethandler().change_user(self.globals.lang, oldpassword, newpassword, newemail)
				if dberrormessage:
					errormessages.append(dberrormessage)
			if not errormessages and newemail is not None:
				self.email = newemail
		return errormessages


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

	ul4_attrs = Base.ul4_attrs.union({"id", "identifier", "name", "key", "user"})
	ul4_type = ul4c.Type("la", "KeyView", "Object granting access to a view template")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	key = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	user = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, identifier=None, name=None, key=None, user=None):
		self.id = id
		self.identifier = identifier
		self.name = name
		self.key = key
		self.user = user

	@property
	def ul4onid(self) -> str:
		return self.id


@register("permission")
class Permissions(Base):
	ul4_attrs = {
		"edit",
		"config",
		"delete",
		"task_manage",
		"data_edit",
		"data_view",
		"task_view",
		"frontend",
		"data_connect_external",
		"perform_evaluation",
		"to_catalog",
		"data_import_export",
		"mydata_view",
		"mydata_edit",
		"user_admin",
	}
	ul4_type = ul4c.Type("la", "Permission", "Permission information")

	def __init__(self, permissions: str):
		for (i, attrname) in enumerate(self.ul4_attrs):
			setattr(self, attrname, permissions != 0)

	def __repr__(self) -> str:
		attrs = "".join(f" {attrname}=True" for attrname in self.ul4_attrs if getattr(self, attrname))
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__}{attrs} at {id(self):#x}>"


@register("globals")
class Globals(CustomAttributes):
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
		:type: User | None

		The currently logged in user.

	.. attribute:: user_record
		:type: Record | None

		A record containing additional information specific to the currently logged in user.

	.. attribute:: maxdbactions
		:type: int | None

		How many database actions may a template execute?.

	.. attribute:: maxtemplateruntime
		:type: int | None

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

	.. attribute:: externaldatasources
		:type: dict[str, ExternalDataSource]

		Configuration and data for external data sources.

	.. attribute:: hostname
		:type: str

		The host name we're running on (can be used to recreate URLs).

	.. attribute:: app
		:type: App

		The app that the running template belongs to.

	.. attribute:: record
		:type: Record | None

		The detail record.

	.. attribute:: mode
		:type: Mode

		The type of template we're running.

	.. attribute:: viewtemplate_id
		:type: Optional[str]

		View template id of last database call.

	.. attribute:: emailtemplate_id
		:type: Optional[str]

		Email template id of last database call.

	.. attribute:: view_id
		:type: Optional[str]

		View id of last database call.

	.. attribute:: params
		:type: Optional[dict[str, AppParameter]]

		Parameters of the view or email template that overwrite the parameters
		of the app.
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({
		"id",
		"version",
		"hostname",
		"free",
		"platform",
		"mode",
		"form",
		"app",
		"record",
		"datasources",
		"externaldatasources",
		"groups",
		"user",
		"user_record",
		"lang",
		"templates",
		"params",
		"flashes",
		"request",
		"response",
		"custom",
		"log_debug",
		"log_info",
		"log_notice",
		"log_warning",
		"log_error",
		"geo",
		"scaled_url",
		"qrcode_url",
		"seq",
		"flash_info",
		"flash_notice",
		"flash_warning",
		"flash_error",
		"dist",
		"my_apps_url",
		"my_tasks_url",
		"catalog_url",
		"chats_url",
		"profile_url",
		"account_url",
		"logout_url",
	})
	ul4_type = ul4c.Type("la", "Globals", "Global information")

	supported_version = "136"

	class Mode(misc.Enum):
		"""
		The type of template we're running.
		"""

		FORM_NEW_INIT = "form/new/init"
		FORM_NEW_SEARCH = "form/new/search"
		FORM_NEW_LIVE = "form/new/live"
		FORM_NEW_INPUT = "form/new/input"
		FORM_NEW_GEO = "form/new/geo"
		FORM_NEW_ERROR = "form/new/error"
		FORM_NEW_SUCCESS = "form/new/success"
		FORM_EDIT_INIT = "form/edit/init"
		FORM_EDIT_SEARCH = "form/edit/search"
		FORM_EDIT_LIVE = "form/edit/live"
		FORM_EDIT_INPUT = "form/edit/input"
		FORM_EDIT_GEO = "form/edit/geo"
		FORM_EDIT_ERROR = "form/edit/error"
		FORM_EDIT_SUCCESS = "form/edit/success"
		VIEW_LIST = "view/list"
		VIEW_DETAIL = "view/detail"
		VIEW_SUPPORT = "view/support"
		EMAIL_TEXT = "email/text"
		EMAIL_HTML = "email/html"

	class Form(misc.Enum):
		"""
		The type of form we are in (if we are in a form).
		"""

		STANAALONE = "standalone"
		EMBEDDED= "embedded"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	version = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	platform = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	user = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	user_record = Attr(lambda: Record, get=True, set=True, ul4get=True, ul4set=True)
	maxdbactions = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	maxtemplateruntime = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	lang = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	datasources = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	hostname = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	free = BoolAttr(get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(lambda: App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	record = Attr(lambda: Record, get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	templates = Attr(get="", ul4get="_templates_get")
	mode = EnumAttr(Mode, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	form = EnumAttr(Form, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	viewtemplate_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)
	emailtemplate_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)
	view_id = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)
	externaldatasources = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	template_params = AttrDictAttr(get="", ul4onget="_template_params_get", ul4onset="_template_params_ul4onset")
	groups = AttrDictAttr(get="", ul4get="_groups_get", ul4onget="_groups_get")
	params = AttrDictAttr(get="", ul4get="_params_get")
	custom = Attr(get=True, set=True, ul4get=True, ul4set=True)

	def __init__(self, id=None, version=None, hostname=None, platform=None, mode=None):
		super().__init__()
		self.id = id
		self.version = version
		self.hostname = hostname
		self.free = True
		self.platform = platform
		self.app = None
		self.record = None
		self.user_record = None
		self.datasources = attrdict()
		self._groups = None
		self.user = None
		self.maxdbactions = None
		self.maxtemplateruntime = None
		self.__dict__["_flashes"] = []
		self.lang = None
		self.handler = None
		self.request = None
		self.response = None
		self.mode = mode
		self.viewtemplate_id = None
		self.emailtemplate_id = None
		self.view_id = None
		self.externaldatasources = attrdict()
		self._template_params = {}
		self._library_params = None
		self._params = None

	@property
	def ul4onid(self) -> str:
		return self.id

	def ul4onload_end(self, decoder:ul4on.Decoder) -> None:
		if self.version != self.supported_version:
			raise VersionMismatchError(self.version, self.supported_version)

	def _gethandler(self) -> Handler:
		if self.handler is None:
			raise NoHandlerError()
		return self.handler

	def _datasources_ul4onset(self, value):
		if value is not None:
			self.datasources = value

	def _externaldatasources_ul4onset(self, value):
		if value is not None:
			self.externaldatasources = value

	def _groups_get(self) -> dict[str, AppGroup]:
		groups = self._groups
		if groups is None:
			handler = self.handler
			if handler is not None:
				groups = handler.appgroups_incremental_data(self)
				if groups is not None:
					groups = attrdict(groups)
					self._groups = groups
		return groups

	def _record_ul4onset(self, value):
		if value is not None:
			self.record = value

	def file(self, source) -> File:
		"""
		Create a :class:`~ll.la.File` object from :obj:`source`.

		:obj:`source` can be :class:`pathlib.Path` or :class:`os.PathLike` object,
		an :class:`~ll.url.URL` object or a stream (i.e. an object with a
		:meth:`read` method and a :attr:`name` attribute.
		"""
		path = None
		mimetype = None
		if isinstance(source, pathlib.Path):
			content = source.read_bytes()
			filename = source.name
			path = str(source.resolve())
		elif isinstance(source, str):
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
		else:
			content = source.read()
			name = getattr(source, "name", None)
			filename = os.path.basename(name) if name else "Unnamed"
		if mimetype is None:
			mimetype = mimetypes.guess_type(filename, strict=False)[0]
			if mimetype is None:
				mimetype = "application/octet-stream"
		file = File(filename=filename, mimetype=mimetype, content=content)
		file.globals = self
		return file

	def geo(self, lat: float | None=None, long: float | None=None, info: str | None=None) -> Geo:
		if lat is not None and long is not None and info is not None:
			# If we have all the info for a ``Geo`` object, we can return it directly
			geo = Geo(lat, long, info)
			geo.globals = self
			return geo
		return self.handler.geo(lat, long, info)

	def seq(self) -> int:
		return self.handler.seq()

	def _add_flash(self, type: FlashMessage.MessageType | str, title: str, message: str | None):
		self.__dict__["_flashes"].append(FlashMessage(type=type, title=title, message=message))

	def flash_info(self, title: str, message: str | None) -> None:
		self._add_flash(FlashMessage.MessageType.INFO, title, message)

	def flash_notice(self, title: str, message: str | None) -> None:
		self._add_flash(FlashMessage.MessageType.NOTICE, title, message)

	def flash_warning(self, title: str, message: str | None) -> None:
		self._add_flash(FlashMessage.MessageType.WARNING, title, message)

	def flash_error(self, title: str, message: str | None) -> None:
		self._add_flash(FlashMessage.MessageType.ERROR, title, message)

	def flashes(self) -> list[FlashMessage]:
		flashes = self.__dict__["_flashes"]
		self.__dict__["_flashes"] = []
		return flashes

	def dist(self, geo1: Geo, geo2: Geo) -> float:
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

	def scaled_url(self, image: File | str, width: int | None, height: int | None, *, type: str="fill", enlarge: bool=True, gravity: str="sm", quality: int | None=None, rotate: int=0, blur: float | None=None, sharpen: float | None=None, format: str | None=None, cache: bool=True) -> str:
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
			Defines how images should be cropped when aspect ratios differ between
			the original and the target sizes.

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
			Supported formats are ``"png"``, ``"jpg"``, ``"webp"``, ``"avif"``,
			``"gif"``, ``"ico"``, ``"svg"``, ``"heic"``, ``"bmp"`` and ``"tiff"``
			as well as ``None`` which results in the same format as the original
			image. For more information see `the imgproxy documentation`__.

			__ https://docs.imgproxy.net/generating_the_url?id=format

		``cache`` : :class:`bool`
			If true, return an URL that caches the scaled image, so that is doesn't
			have to be rescaled on each request. Otherwise return an URL that
			rescales the image on each request.
		"""
		v = [f"https://{self.hostname}/"]
		if cache:
			v.append("imgproxycache/insecure")
		else:
			v.append("imgproxy/insecure")

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
			v.append(f"/plain/{image.url}")
		elif isinstance(image, str):
			v.append(f"/plain/{urlparse.quote(image)}")
		else:
			raise TypeError(f"`Globals.scaled_url()` image argument must be a `File` or `str`, but is `{misc.format_class(image)}`")
		return "".join(v)

	def qrcode_url(self, /, data: str, size: int) -> str:
		"""
		Return an URL for a QR code.

		Arguments are:

		``data`` : :class:`str`
			The text encoded by the QR code (usually an URL itself)

		``size`` : :class:`int`
			The width and height of the resulting image

		For example:

		.. sourcecode:: ul4

			<?print globals.qrcode_url("https://my.living-apps.de", 200)?>

		prints

		.. sourcecode:: text

			https://my.living-apps.de/qr/generate?data=https%3A%2F%2Fmy.living-apps.de%2F&size=200
		"""
		return f"https://{self.hostname}/qr/generate?data={urlparse.quote(data, safe='')}&size={size}"

	def log_debug(self, *args) -> None:
		pass

	def log_info(self, *args) -> None:
		pass

	def log_notice(self, *args) -> None:
		pass

	def log_warning(self, *args) -> None:
		pass

	def log_error(self, *args) -> None:
		pass

	def _template_candidates(self):
		if self.app is not None:
			yield from self.app._template_candidates()

	def _templates_get(self) -> dict[str, ul4c.Template]:
		if self.app is not None:
			return self.app.templates
		else:
			return attrdict()

	def _template_params_get(self) -> dict[str, MutableAppParameter]:
		if self._template_params is None:
			if self.handler is None:
				raise NoHandlerError()
			if self.viewtemplate_id is not None:
				self._template_params = attrdict(self.handler.fetch_viewtemplate_params(self))
			elif self.emailtemplate_id is not None:
				self._template_params = attrdict(self.handler.fetch_emailtemplate_params(self))
			else:
				self._template_params = attrdict()
		return self._template_params

	def _template_params_ul4onset(self, value):
		self._template_params = attrdict(value) if value else attrdict()

	@property
	def library_params(self) -> dict[str, AppParameter]:
		if self._library_params is None:
			handler = self._gethandler()
			self._library_params = attrdict()
			for p in handler.fetch_libraryparams().values():
				p = AppParameter(id=p.id, type=p.type, identifier=p.identifier, value=p.value, description=p.description)
				p._globals = self
				self._library_params[p.identifier] = p
		return self._library_params

	def _params_get(self) -> dict[str, MutableAppParameter]:
		if self._params is None:
			if self.template_params:
				if self.app.params:
					self._params = attrdict(
						collections.ChainMap(
							self.template_params,
							self.app.params,
						)
					)
				else:
					self._params = self.template_params
			else:
				self._params = self.app.params
		return self._params

	vsqlsearchfield = vsql.Field("search", vsql.DataType.STR, "livingapi_pkg.global_search")

	@classmethod
	def vsqlsearchexpr(cls) -> vsql.AST:
		return vsql.FieldRefAST.make_root(cls.vsqlsearchfield)

	def __getattr__(self, name: str) -> Any:
		if name.startswith("d_"):
			identifier = name[2:]
			if self.datasources and identifier in self.datasources:
				return self.datasources[identifier]
		elif name.startswith("e_"):
			identifier = name[2:]
			if self.externaldatasources and identifier in self.externaldatasources:
				return self.externaldatasources[identifier]
		elif name.startswith("p_"):
			identifier = name[2:]
			if self.app and identifier in self.params:
				return self.params[identifier]
		elif name.startswith("pv_"):
			identifier = name[3:]
			if self.app and identifier in self.params:
				return self.params[identifier].value
		else:
			return super().__getattr__(name)

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = super().__dir__()
		if self.datasources:
			for identifier in self.datasources:
				attrs.add(f"d_{identifier}")
		if self.externaldatasources:
			for identifier in self.externaldatasources:
				attrs.add(f"e_{identifier}")
		if self.app:
			for identifier in self.app.params:
				attrs.add(f"p_{identifier}")
				attrs.add(f"pv_{identifier}")
		return attrs

	def ul4_hasattr(self, name: str) -> bool:
		if self.datasources and name.startswith("d_") and name[2:] in self.datasources:
			return True
		elif self.externaldatasources and name.startswith("e_") and name[2:] in self.externaldatasources:
			return True
		elif self.app and name.startswith("p_") and name[2:] in self.params:
			return True
		elif self.app and name.startswith("pv_") and name[3:] in self.params:
			return True
		else:
			return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name.startswith(("d_", "e", "t_", "p_", "pv_")):
			return getattr(self, name)
		else:
			return super().ul4_getattr(name)

	def ul4_setattr(self, name: str, value: Any) -> None:
		if name == "lang":
			self.lang = value
		elif name.startswith("pv_") and self.app:
			setattr(self.app, name, value)
		else:
			super().ul4_setattr(name, value)

	def my_apps_url(self) -> str:
		return f"https://{self.hostname}/apps.htm"

	def my_tasks_url(self) -> str:
		return f"https://{self.hostname}/xist4c/web/aufgaben_id_393_.htm"

	def catalog_url(self) -> str:
		return f"https://{self.hostname}/katalog/home.htm"

	def chats_url(self) -> str:
		return f"https://{self.hostname}/chats.htm"

	def profile_url(self) -> str:
		return f"https://{self.hostname}/profil/index.htm"

	def account_url(self) -> str:
		return f"https://{self.hostname}/account.htm"

	def logout_url(self) -> str:
		return f"https://{self.hostname}/login.htm?logout=standardCug"


@register("app")
class App(CustomAttributes):
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

	.. attribute:: main
		:type: bool

		Is this app the main app of its app group?

	.. attribute:: ai_generated
		:type: bool

		Has this app been generated by Lilo?

	.. attribute:: startlink
		:type: str

	.. attribute:: image
		:type: File

		App icon.

	.. attribute:: createdby
		:type: User

		Who created this app?

	.. attribute:: controls
		:type: Optional[dict[str, Control]]

		The definition of the fields of this app.

	.. attribute:: child_controls
		:type: dict[str, Control]

		All controls of type ``applookup`` or ``multipleapplookup`` whose target
		app is this app.

	.. attribute:: menus
		:type: list[MenuItem]

		All menus and menu items that have been configured for this app that are
		currently active and where the target page is accessible to the current
		user.

	.. attribute:: panels
		:type: list[Panel]

		All panels that have been configured for this app that are currently
		active and where the target page is accessible to the current user.

	.. attribute:: records
		:type: Optional[dict[str, Record]]

		The records of this app (if configured).

	.. attribute:: record_total
		:type: int

		The number of records in this app (if configured).

	.. attribute:: record_start
		:type: int

		The start index of records (when paging parameters are in use or vSQL
		expressions for paging are configured).

	.. attribute:: record_count
		:type: int

		The number of records per page (when paging parameters are in use or vSQL
		expressions for paging are configured).

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

	.. attribute:: viewtemplates
		:type: dict[str, ViewTemplateInfo]

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

	.. attribute:: viewtemplatesconfig
		:type: Optional[dict[str, ViewTemplate]]

		View templates of this app.

	.. attribute:: dataactions
		:type: Optional[dict[str, DataAction]]

		Data actions of this app.
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({
		"id",
		"globals",
		"name",
		"description",
		"lang",
		"group",
		"appgroup",
		"main",
		"ai_generated",
		"filter_default",
		"sort_default",
		"filter_owndata",
		"permissions",
		"gramgen",
		"typename_nom_sin",
		"typename_gen_sin",
		"typename_dat_sin",
		"typename_acc_sin",
		"typename_nom_plu",
		"typename_gen_plu",
		"typename_dat_plu",
		"typename_acc_plu",
		"startlink",
		"image",
		"iconlarge",
		"iconsmall",
		"createdat",
		"createdby",
		"updatedat",
		"updatedby",
		"controls",
		"layout_controls",
		"child_controls",
		"menus",
		"panels",
		"records",
		"recordpage",
		"record_start",
		"record_count",
		"record_total",
		"installation",
		"categories",
		"params",
		"views",
		"datamanagement_identifier",
		"custom",
		# "basetable",
		# "primarykey",
		# "insertprocedure",
		# "updateprocedure",
		# "deleteprocedure",
		"templates",
		"viewtemplates",
		"insert",
		"favorite",
		"active_view",
		"datasource",
		# "internaltemplates",
		# "viewtemplates",
		# "dataactions",
		"add_param",
		"template_url",
		"new_embedded_url",
		"new_standalone_url",
		"new_url",
		"home_url",
		"datamanagement_url",
		"import_url",
		"tasks_url",
		# "formbuilder_url",
		# "tasks_config_url",
		"datamanagement_config_url",
		"permissions_url",
		"datamanageview_url",
		"seq",
		"send_mail",
		"save",
		"count_records",
		"delete_records",
		"fetch_records",
		"fetch_recordpage",
	})
	ul4_type = ul4c.Type("la", "App", "A LivingApps application")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	globals = Attr(Globals, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	internal_id = Attr(str, get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	lang = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	appgroup = Attr(lambda: AppGroup, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	gramgen = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_nom_sin = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_gen_sin = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_dat_sin = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_acc_sin = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_nom_plu = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_gen_plu = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_dat_plu = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	typename_acc_plu = Attr(str, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	startlink = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	image = Attr(File, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	iconlarge = Attr(File, get="_image_get", ul4get="_image_get")
	iconsmall = Attr(File, get="_image_get", ul4get="_image_get")
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	controls = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	layout_controls = AttrDictAttr(get="", ul4get="_layout_controls_get")
	records = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	recordpage = Attr(lambda: RecordPage, get="", ul4get="_recordpage_get")
	record_start = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	record_count = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	record_total = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	installation = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	categories = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")
	ownparams = AttrDictAttr(get="", set="", ul4onget="", ul4onset="")
	params = AttrDictAttr(get="", ul4get="_params_get")
	views = Attr(get="", set="", ul4get="_views_get", ul4onget="_views_ul4onget", ul4onset="_views_set")
	datamanagement_identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	basetable = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	primarykey = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	insertprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updateprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	deleteprocedure = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	owntemplates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	superid = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	favorite = BoolAttr(get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	active_view = Attr(lambda: View, str, get=True, set="", ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	datasource = Attr(lambda: DataSource, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	main = BoolAttr(get=True, ul4get=True, ul4onget=True, ul4onset=True)
	ai_generated = BoolAttr(get=True, ul4get=True, ul4onget=True, ul4onset=True)
	viewtemplates = Attr(get="", ul4get="_viewtemplates_get", ul4onget="", ul4onset="")
	filter_default = Attr(list, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	sort_default = Attr(list, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	filter_owndata = Attr(list, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	permissions = Attr(Permissions, get=True, ul4get=True, ul4onget=True, ul4onset="")
	menus = Attr(get="", set="", ul4get="_menus_get")
	panels = Attr(get="", set="", ul4get="_panels_get")
	child_controls = Attr(get="", set="", ul4get="_child_controls_get")
	internaltemplates = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	viewtemplates_config = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	dataactions = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	custom = Attr(get=True, set=True, ul4get=True, ul4set=True)

	def __init__(self, *args, id=None, name=None, description=None, lang=None, startlink=None, image=None, createdat=None, createdby=None, updatedat=None, updatedby=None, installation=None, datamanagement_identifier=None):
		super().__init__()
		self.id = id
		self.internal_id = None
		self.superid = None
		self.globals = None
		self.handler = None
		self.name = name
		self.description = description
		self.lang = lang
		self.appgroup = None
		self.startlink = startlink
		self.image = image
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.controls = None
		self._child_controls = None
		self._menus = None
		self._panels = None
		self.records = None
		self.__dict__["recordpage"] = None
		self.record_start = None
		self.record_count = None
		self.record_total = None
		self.installation = installation
		self.categories = None
		self._templates = None
		self._viewtemplates = None
		self._views = None
		self.datamanagement_identifier = datamanagement_identifier
		self.basetable = None
		self.primarykey = None
		self.insertprocedure = None
		self.updateprocedure = None
		self.deleteprocedure = None
		self._owntemplates = None
		self._ownparams = None
		self._params = None
		self.favorite = False
		self.active_view = None
		self.datasource = None
		self.main = False
		self.ai_generated = False
		self.filter_default = []
		self.sort_default = []
		self.filter_owndata = []
		self.permissions = None
		self.internaltemplates = None
		self.viewtemplates_config = None
		self.dataactions = None
		self._vsqlgroup_records = None
		self._vsqlgroup_app = None
		self._add_param(*args)

	def __str__(self) -> str:
		return self.fullname

	@property
	def ul4onid(self) -> str:
		return self.id

	@property
	def group(self) -> AppGroup:
		return self.appgroup

	def _add_param(self, *params):
		for param in params:
			param.app = self
			self.ownparams[param.identifier] = param
			if self._params is not None:
				self._params[param.identifier] = param
		return self

	def add_param(self, identifier, *, type=None, description=None, value=None):
		param = MutableAppParameter(app=self, type=type, identifier=identifier, description=description, value=value)
		self._add_param(param)
		return param

	def _image_get(self) -> File | None:
		return self.image

	def _records_ul4onset(self, value):
		if value is not None:
			self.records = value

	def _record_total_ul4onset(self, value):
		if value is not None:
			self.record_total = value

	def _recordpage_get(self):
		if self.__dict__["recordpage"] is None:
			rp = AppRecordPage(self, filter=self.filter_default, sort=self.sort_default, offset=self.record_start, limit=self.record_count)
			rp._records = self.records
			rp._count = len(rp._records)
			rp._total = self.record_total
			self.__dict__["recordpage"] = rp
		return self.__dict__["recordpage"]

	def _categories_ul4onset(self, value):
		if value is not None:
			self.records = value

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

	def _template_candidates(self):
		handler = self._gethandler()
		yield handler.fetch_internaltemplates(self.id, None, None)
		yield handler.fetch_internaltemplates(self.id, "app_instance", None)
		if "la" in self.ownparams and isinstance(self.ownparams["la"].value, App):
			yield from self.ownparams["la"].value._template_candidates()
		else:
			yield handler.fetch_librarytemplates(None)
			yield handler.fetch_librarytemplates("app_instance")

	def _viewtemplates_get(self):
		viewtemplates = self._viewtemplates
		if viewtemplates is None:
			handler = self.globals.handler
			if handler is not None:
				viewtemplates = handler.app_viewtemplates_incremental_data(self)
				if viewtemplates is not None:
					viewtemplates = attrdict(viewtemplates)
					self._viewtemplates = viewtemplates
		return viewtemplates

	def _viewtemplates_ul4onget(self):
		return self._viewtemplates

	def _viewtemplates_ul4onset(self, value):
		self._viewtemplates = value

	def _viewtemplates_ul4ondefault(self):
		self._viewtemplates = None

	def template_url(self, identifier, record=None, /, **params) -> str:
		url = f"https://{self.globals.hostname}/gateway/apps/{self.id}"
		if record is not None:
			url += f"/{record.id}"
		url += f"?template={identifier}"
		return url_with_params(url, False, params)

	def new_embedded_url(self, **params) -> str:
		url = f"https://{self.globals.hostname}/dateneingabe/{self.id}/new"
		return url_with_params(url, True, params)

	def new_standalone_url(self, **params) -> str:
		url = f"https://{self.globals.hostname}/gateway/apps/{self.id}/new"
		return url_with_params(url, True, params)

	def new_url(self, **params) -> str:
		if self.ownparams["la_default_form_variant"] == "standalone":
			return self.new_standalone_url(**params)
		else:
			return self.new_embedded_url(**params)

	def home_url(self) -> str:
		return f"https://{self.globals.hostname}/apps/{self.id}.htm"

	def datamanagement_url(self) -> str:
		return f"https://{self.globals.hostname}/_id_36_.htm?uuid={self.id}&dId={self.id}&resetInfo=true&templateIdentifier=created_{self.id}"

	def import_url(self) -> str:
		return f"https://{self.globals.hostname}/import-export/{self.id}.htm"

	def tasks_url(self) -> str:
		return f"https://{self.globals.hostname}/_id_1073_.htm?uuid={self.id}&dId={self.id}&p_tpl_uuid={self.id}&resetInfo=true&templateIdentifier=created_task_{self.id}"

	# def formbuilder_url(self) -> str:
	# 	lang = self.globals.lang
	# 	if not lang:
	# 		lang = "de"
	# 	return f"https://{self.globals.hostname}/formbuilder/index.html?lang={lang}&searchDescription={tpl_id}&p_tpl_uuid={self.id}&p_cl_id={cl_id}"

	# def tasks_config_url(self):
	# 	return f"https://{self.globals.hostname}/konfiguration/aufgaben.htm?com.livinglogic.cms.apps.search.model.SearchState.search_submit=true&searchDescription={tpl_id}&dId={self.id}"

	def datamanagement_config_url(self) -> str:
		return f"https://{self.globals.hostname}/datenmanagement-konfigurieren/{self.id}.htm"

	def permissions_url(self) -> str:
		return f"https://{self.globals.hostname}/_id_833_.htm?uuid={self.id}&dId={self.id}&resetInfo=true"

	def datamanageview_url(self, identifier: str) -> str:
		return f"https://{self.globals.hostname}/_id_36_.htm?uuid={self.id}&dId={self.id}&resetInfo=true&templateIdentifier=created_{self.id}_datamanage_master_{identifier}"

	def seq(self) -> int:
		return self.globals.handler.appseq(self)

	def send_mail(self, from_: str | None = None, reply_to: str | None = None, to: str | None = None, cc: str | None = None, bcc: str | None = None, subject: str | None = None, body_text: str | None = None, body_html: str | None = None, attachments: la.File | None = None) -> None:
		self.globals.handler.send_mail(
			globals=self.globals,
			app=self,
			record=None,
			from_=from_,
			reply_to=reply_to,
			to=to,
			cc=cc,
			bcc=bcc,
			subject=subject,
			body_text=body_text,
			body_html=body_html,
			attachments=attachments,
		)

	def save(self):
		handler = self._gethandler()
		return handler.save_app(self)

	def __getattr__(self, name: str) -> Any:
		if name.startswith("c_"):
			identifier = name[2:]
			if self.controls and identifier in self.controls:
				return self.controls[identifier]
		elif name.startswith("lc_"):
			identifier = name[3:]
			if self.layout_controls and identifier in self.layout_controls:
				return self.layout_controls[identifier]
		elif name.startswith("p_"):
			identifier = name[2:]
			if self.params and identifier in self.params:
				return self.params[identifier]
		elif name.startswith("pv_"):
			identifier = name[3:]
			if self.params and identifier in self.params:
				return self.params[identifier].value
		else:
			return super().__getattr__(name)

	def __setattr__(self, name: str, value: Any) -> None:
		if name.startswith("pv_"):
			identifier = name[3:]
			if identifier in self.params:
				self.params[identifier].value = value
			else:
				self.addparam(None, identifier, None, value)
			return
		super().__setattr__(name, value)

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = super().__dir__()
		for identifier in self.controls:
			attrs.add(f"c_{identifier}")
		if self.layout_controls:
			for identifier in self.layout_controls:
				attrs.add(f"lc_{identifier}")
		for identifier in self.params:
			attrs.add(f"p_{identifier}")
			attrs.add(f"pv_{identifier}")
		for identifier in self.templates:
			attrs.add(f"t_{identifier}")
		return attrs

	def ul4_hasattr(self, name: str) -> bool:
		if name.startswith("c_") and name[2:] in self.controls:
			return True
		elif name.startswith("lc_") and name[3:] in self.layout_controls:
			return True
		elif name.startswith("p_") and name[2:] in self.params:
			return True
		elif name.startswith("pv_") and name[3:] in self.params:
			return True
		else:
			return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name.startswith(("c_", "lc_", "p_", "pv_", "t_")):
			return getattr(self, name)
		elif self.ul4_hasattr(name):
			return super().ul4_getattr(name)

	def ul4_setattr(self, name: str, value: Any) -> None:
		if name.startswith("pv_"):
			setattr(self, name, value)
		else:
			super().ul4_setattr(name, value)

	def _gethandler(self) -> Handler:
		if self.handler is not None:
			return self.handler
		if self.globals is None:
			raise NoHandlerError()
		return self.globals._gethandler()

	def _params_candidates(self):
		yield self._ownparams_get()
		if self.appgroup:
			yield self.appgroup.ownparams
		if "la" in self.ownparams and isinstance(self._ownparams["la"].value, App):
			yield from self.ownparams["la"].value._params_candidates()
		else:
			yield self.globals.library_params

	def _param(self, identifier: str) -> AppParameter:
		for params in self._params_candidates():
			if identifier in params:
				return params[identifier]
		return None

	def _ownparams_get(self) -> dict[str, AppParameter]:
		params = self._ownparams
		if params is None:
			handler = self._gethandler()
			params = handler.app_params_incremental_data(self)
			params = attrdict(params)
			self._ownparams = params
		return params

	def _ownparams_set(self, value):
		self._ownparams = value

	def _ownparams_ul4onget(self):
		# Bypass the logic that fetches the parameters from the database
		return self._ownparams

	def _ownparams_ul4onset(self, value):
		if value is not None:
			self._ownparams = value

	def _params_get(self):
		if self._params is None:
			params = collections.ChainMap(*self._params_candidates())
			self._params = params
		return self._params

	def _permissions_ul4onset(self, value):
		self.__dict__["permissions"] = Permissions(value)

	def _menus_get(self):
		menus = self._menus
		if menus is None:
			handler = self.globals.handler
			if handler is not None:
				menus = self._menus = handler.app_menus_incremental_data(self)
		return menus

	def _menus_set(self, value):
		self._menus = value

	def _panels_get(self):
		panels = self._panels
		if panels is None:
			handler = self.globals.handler
			if handler is not None:
				panels = self._panels = handler.app_panels_incremental_data(self)
		return panels

	def _panels_set(self, value):
		self._panels = value

	def _child_controls_get(self):
		child_controls = self._child_controls
		if child_controls is None:
			handler = self.globals.handler
			if handler is not None:
				child_controls = self._child_controls = handler.app_child_controls_incremental_data(self)
		return child_controls

	def _child_controls_set(self, value):
		self._child_controls = value

	def _views_get(self):
		views = self._views
		if views is None:
			handler = self.globals.handler
			if handler is not None:
				views = self._views = handler.app_views_incremental_data(self)
		return views

	def _views_set(self, value):
		self._views = value

	def _views_ul4onget(self):
		return self._views

	def _layout_controls_get(self):
		if self.active_view is None:
			return attrdict()
		return self.active_view.layout_controls

	def save_meta(self, recursive=True):
		self._gethandler().save_app(self, recursive=recursive)

	_saveletters = string.ascii_letters + string.digits + "()-+_ äöüßÄÖÜ"

	@property
	def fullname(self) -> str:
		if self.name:
			safename = "".join(c for c in self.name if c in self._saveletters)
			return f"{safename} ({self.id})"
		else:
			return self.id

	def addcontrol(self, *controls: Control) -> Self:
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
			elif isinstance(template, ViewTemplateConfig):
				if self.viewtemplates_config is None:
					self.viewtemplates_config = attrdict()
				template.app = self
				self.viewtemplates_config[template.identifier] = template
			else:
				raise TypeError(f"don't know what to do with positional argument {template!r}")
		return self

	def insert(self, **kwargs) -> Record:
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

	def __call__(self, **kwargs) -> Record:
		record = Record(app=self)
		for identifier in kwargs:
			if identifier not in self.controls:
				raise TypeError(f"app_{self.id}() got an unexpected keyword argument {identifier!r}")

		record._make_fields(True, kwargs, {}, {})
		return record

	def vsqlfield_records(self, ul4var: str, sqlvar: str) -> vsql.Field:
		return vsql.Field(ul4var, vsql.DataType.STR, sqlvar, f"{sqlvar} = {{d}}.tpl_id", self.vsqlgroup_records)

	def vsqlfield_app(self, ul4var: str, sqlvar: str) -> vsql>Field:
		return vsql.Field(ul4var, vsql.DataType.STR, sqlvar, f"{sqlvar} = {{d}}.tpl_id", self.vsqlgroup_app)

	@staticmethod
	def vsqlgroup_records_common(base_query: str) -> vsql.Group:
		g = vsql.Group(base_query)
		g.add_field("id", vsql.DataType.STR, "{a}.dat_id")
		g.add_field("app", vsql.DataType.STR, "{a}.tpl_uuid")
		g.add_field("app_internal_id", vsql.DataType.INT, "{a}.tpl_id")
		g.add_field("createdat", vsql.DataType.DATETIME, "{a}.dat_cdate")
		g.add_field("createdby", vsql.DataType.STR, "{a}.dat_cname", "{m}.dat_cname = {d}.ide_id(+)", User.vsqlgroup)
		g.add_field("updatedat", vsql.DataType.DATETIME, "{a}.dat_udate")
		g.add_field("updatedby", vsql.DataType.STR, "{a}.dat_uname", "{m}.dat_uname = {d}.ide_id(+)", User.vsqlgroup)
		g.add_field("updatecount", vsql.DataType.INT, "{a}.dat_updatecount")
		g.add_field("url", vsql.DataType.STR, "'https://' || parameter_pkg.str_os('INGRESS_HOST') || '/gateway/apps/' || {a}.tpl_uuid || '/' || {a}.dat_id || '/edit'")
		return g

	@property
	def vsqlgroup_records(self) -> vsql.Group:
		if self._vsqlgroup_records is None:
			self._vsqlgroup_records = g = self.vsqlgroup_records_common("data_select_la")
			if self.controls is not None:
				for control in self.controls.values():
					vsqlfield = control.vsqlfield
					g.fields[vsqlfield.identifier] = vsqlfield
		return self._vsqlgroup_records

	@property
	def vsqlgroup_app(self) -> vsql.Group:
		if self._vsqlgroup_app is None:
			self._vsqlgroup_app = g = vsql.Group("template")
			g.add_field("id", vsql.DataType.STR, "{a}.tpl_uuid")
			g.add_field("name", vsql.DataType.STR, "{a}.tpl_name")
			g.add_field("description", vsql.DataType.STR, "{a}.tpl_description")
			g.add_field("createdat", vsql.DataType.DATETIME, "{a}.tpl_ctimstamp")
			g.add_field("createdby", vsql.DataType.STR, "{a}.tpl_cname", "{m}.tpl_cname = {d}.ide_id(+)", User.vsqlgroup)
			g.add_field("updatedat", vsql.DataType.DATETIME, "{a}.tpl_utimstamp")
			g.add_field("updatedby", vsql.DataType.STR, "{a}.tpl_uname", "{m}.tpl_uname = {d}.ide_id(+)", User.vsqlgroup)
			g.add_field("installation", vsql.DataType.STR, "{a}.inl_id", "{m}.inl_id = {d}.inl_id(+)", Installation.vsqlgroup)
			# FIXME: Add app parameters
		return self._vsqlgroup_app

	def vsqlsearchexpr(self, record: Record, maxdepth: int, controls: dict[str, Control] | None=None):
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

	def vsqlsortexpr(self, record: Record, maxdepth: int, controls: dict[str, Control] | None=None):
		result = []
		if maxdepth:
			usecontrols = controls if controls is not None else self.controls
			for control in usecontrols.values():
				if controls is None or control.priority:
					result.extend(control.vsqlsortexpr(record, maxdepth-1))
		return result

	def count_records(self, filter:str | list[str]) -> int:
		"""
		Return the number of records in this app matching the vSQL condition ``filter``.

		For example::

			app.count_records("r.v_createdat >= now() - days(30)")

		will return the number of records created in the last 30 days.

		.. hint::

			To count all records you can use::

				app.count_records("True")
		"""

		filter = _make_filter(filter)
		handler = self._gethandler()
		return handler.count_records(self, filter)

	def delete_records(self, filter: list[str] | str) -> int:
		"""
		Delete records in this app matching the vSQL condition ``filter``.

		Return the number of records deleted.

		LivingAPI objects for records that have been deleted will be marked
		as deleted.

		For example::

			app.delete_records("r.v_createdat < now() - days(30)")

		will delete all records that weren't created in the last 30 days and
		will return how many were deleted.

		.. hint::

			To delete all records you can use::

				app.delete_records("True")
		"""

		filter = _make_filter(filter)

		handler = self._gethandler()
		return handler.delete_records(self, filter)

	def fetch_records(self, filter:list[str] | str, sort:list[str] | str | None = None, offset: int | None = 0, limit: int | None = None) -> dict[str, Record]:
		"""
		Return records in this app matching the vSQL condition ``filter``.

		``sorts`` can be a string or list of strings specifying how records should
		be sorted. If ``sorts`` is a list of multiple strings the records will be
		sorted lexicographically. Each sort expression must be a valid vSQL
		expression optionally followed by ``asc`` or ``desc`` optionally followed
		by ``nulls first`` or ``nulls last``. If ``sorts`` is ``None`` or an empty
		list records will be returned in "natural" order.

		If ``offset`` is not ``None`` it must be a non-negative integer and
		defines at which offset in the actual list of records output will begin.
		I.e. passing ``offset=1`` will skip the first record.

		If ``limit`` is not ``None`` it must be a positive integer and defines
		how may records (starting at the record defined by ``offset``) should be
		returned.

		Records will be returned as a dictionary which record ids as the keys and
		:class:`Record` objects as the value.
		"""

		filter = _make_filter(filter)
		sort = _make_sort(sort)
		offset = _make_offset(offset)
		limit = _make_limit(limit)

		handler = self._gethandler()
		return handler.fetch_records(self, filter=filter, sort=sort, offset=offset, limit=limit)

	def fetch_recordpage(self, filter:list[str] | str, sort:list[str] | str | None = None, offset: int | None = 0, limit: int | None = None) -> RecordPage:
		"""
		Return records in this app matching the vSQL condition ``filter``.

		``sort`` can be a string or list of strings specifying how records should
		be sorted. If ``sort`` is a list of multiple strings the records will be
		sorted lexicographically. Each sort expression must be a valid vSQL
		expression optionally followed by ``asc`` or ``desc`` optionally followed
		by ``nulls first`` or ``nulls last``. If ``sort`` is ``None`` or an empty
		list records will be returned in "natural" order.

		If ``offset`` is not ``None`` it must be a non-negative integer and
		defines at which offset in the actual list of records output will begin.
		I.e. passing ``offset=1`` will skip the first record.

		If ``limit`` is not ``None`` it must be a positive integer and defines
		how may records (starting at the record defined by ``offset``) should be
		returned.

		Records will be returned as an :class:`AppRecordPage`.
		"""

		filter = _make_filter(filter)
		sort = _make_sort(sort)
		offset = _make_offset(offset)
		limit = _make_limit(limit)

		return AppRecordPage(self, filter=filter, sort=sort, offset=offset, limit=limit)


@register("appgroup")
class AppGroup(CustomAttributes):
	"""
	An :class:`!AppGroup` describes group of apps that together form an application.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: globals
		:type: Globals

		The :class:`Globals` objects.

	.. attribute:: name
		:type: str

		Name of the group.

	.. attribute:: description
		:type: str

		Description of the group.

	.. attribute:: image
		:type: File

		The image of the group.

	.. attribute:: apps
		:type: dict[str, App]

		The LivingApps that belong to this group.

	.. attribute:: params
		:type: dict[str, AppParameter]

		Parameters of this app group.
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({"id", "globals", "name", "apps", "main_app", "params", "add_param", "count_records", "fetch_records", "fetch_recordpage"})
	ul4_type = ul4c.Type("la", "AppGroup", "A group of LivingApps")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	globals = Attr(lambda: Globals, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	image = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	apps = AttrDictAttr(get="", ul4get="_apps_get", ul4onget="_apps_get", ul4onset=True)
	main_app = Attr(lambda: App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	ownparams = AttrDictAttr(get="", set="", ul4onget="", ul4onset="")
	params = AttrDictAttr(get="", ul4get="_params_get")

	def __init__(self, id=None, globals=None, name=None, description=None):
		super().__init__()
		self.id = id
		self.globals = globals
		self.name = name
		self.description = description
		self.image = None
		self._apps = None
		self.main_app = None
		self._ownparams = None
		self._params = None

	def _template_candidates(self):
		handler = self.globals._gethandler()
		yield handler.fetch_internaltemplates(self.globals.app.id, "appgroup_instance", None)
		yield handler.fetch_librarytemplates("appgroup_instance")

	@property
	def ul4onid(self) -> str:
		return self.id

	def __getattr__(self, name: str) -> Any:
		if name.startswith("p_"):
			identifier = name[2:]
			if self.params and identifier in self.params:
				return self.params[identifier]
		elif name.startswith("pv_"):
			identifier = name[3:]
			if self.params and identifier in self.params:
				return self.params[identifier].value
		else:
			return super().__getattr__(name)

	def __setattr__(self, name: str, value: Any) -> None:
		if name.startswith("pv_"):
			identifier = name[3:]
			if identifier in self.ownparams:
				self.ownparams[identifier].value = value
			else:
				self.addparam(None, identifier, None, value)
			return
		super().__setattr__(name, value)

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = super().__dir__()
		for identifier in self.params:
			attrs.add(f"p_{identifier}")
			attrs.add(f"pv_{identifier}")
		return attrs

	def ul4_hasattr(self, name: str) -> Any:
		if name.startswith("p_") and name[2:] in self.params:
			return True
		elif name.startswith("pv_") and name[3:] in self.params:
			return True
		elif name.startswith("pv_") and name[3:] in self.params:
			return True
		else:
			return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name.startswith(("p_", "pv_", "t_")):
			return getattr(self, name)
		elif self.ul4_hasattr(name):
			return super().ul4_getattr(name)

	def ul4_setattr(self, name: str, value: Any) -> None:
		if name.startswith("pv_"):
			setattr(self, name, value)
		else:
			super().ul4_setattr(name, value)

	def _apps_get(self):
		apps = self._apps
		if apps is None:
			handler = self.globals.handler
			if handler is not None:
				apps = handler.appgroup_apps_incremental_data(self)
				if apps is not None:
					apps = attrdict(apps)
					self._apps = apps
		return apps

	def _ownparams_get(self) -> dict[str, AppParameter]:
		params = self._params
		if params is None:
			handler = self.globals._gethandler()
			params = handler.appgroup_params_incremental_data(self)
			if params is not None:
				params = attrdict(params)
				self._ownparams = params
		return params

	def _ownparams_set(self, value):
		self._ownparams = value

	def _ownparams_ul4onget(self):
		# Bypass the logic that fetches the parameters from the database
		return self._ownparams

	def _ownparams_ul4onset(self, value):
		if value is not None:
			self._ownparams = value

	def _params_get(self) -> dict[str, AppParameter]:
		if self._params is None:
			self._params = attrdict(collections.ChainMap(self.ownparams, self.globals.library_params))
		return self._params

	def add_param(self, identifier, *, type=None, description=None, value=None) -> AppParameter:
		param = MutableAppParameter(appgroup=self, type=type, identifier=identifier, description=description, value=value)
		self.params[param.identifier] = param
		return param

	def _make_filter(self, filter:dict[App, list[str] | str]) -> dict[App, list[str]]:
		if not isinstance(filter, dict):
			raise TypeError("`filter` must be a dict")

		new_filter = {}

		for (app, value) in filter.items():
			if not isinstance(app, App):
				raise TypeError("`filter` keys must be `App` objects")
			if app.id not in self.apps:
				raise TypeError("`filter` keys must be `App` objects that belong to the appgroup")
			new_filter[app] = _make_filter(value)

		return new_filter

	def count_records(self, filter:dict[App, list[str] | str]) -> int:
		"""
		Return the number of records in this app group matching the vSQL condition ``filter``.

		``filter`` must map apps of the app group to vSQL filter expressions
		(or list of expressions, which will be ombined with ``and``).
		"""

		handler = self.globals._gethandler()
		filter = self._make_filter(filter)
		return handler.count_records_from_apps(self.globals, filter)

	def fetch_records(self, filter:dict[App, list[str] | str], sort:list[str] | str | None=None, offset:int | None = 0, limit: int | None=None) -> dict[str, Record]:
		"""
		Return records in this app group matching the vSQL conditions in ``filter``.

		``filter`` must map apps of the app group to vSQL filter expressions
		(or list of expressions, which will be ombined with ``and``).

		``sort`` can be a string or list of strings specifying how records should
		be sorted. If ``sort`` is a list of multiple strings the records will be
		sorted lexicographically. Each sort expression must be a valid vSQL
		expression optionally followed by ``asc`` or ``desc`` optionally followed
		by ``nulls first`` or ``nulls last``. If ``sort`` is ``None`` or an empty
		list records will be returned in "natural" order.

		If ``offset`` is not ``None`` it must be a non-negative integer and
		defines at which offset in the actual list of records output will begin.
		I.e. passing ``offset=1`` will skip the first record.

		If ``limit`` is not ``None`` it must be a positive integer and defines
		how may records (starting at the record defined by ``offset``) should be
		returned.

		Records will be returned as a dictionary which record ids as the keys and
		:class:`Record` objects as the value.
		"""

		handler = self.globals._gethandler()
		return handler.fetch_records_from_apps(
			globals=self.globals,
			filter=self._make_filter(filter),
			sort=_make_sort(sort),
			offset=_make_offset(offset),
			limit=_make_limit(limit),
		)

	def fetch_recordpage(self, filter:dict[App, list[str] | str], sort:list[str] | str | None = None, offset: int | None = 0, limit: int | None = None) -> RecordPage:
		"""
		Return records in this app group matching the vSQL conditions in ``filter``.

		``sort`` can be a string or list of strings specifying how records should
		be sorted. If ``sort`` is a list of multiple strings the records will be
		sorted lexicographically. Each sort expression must be a valid vSQL
		expression optionally followed by ``asc`` or ``desc`` optionally followed
		by ``nulls first`` or ``nulls last``. If ``sort`` is ``None`` or an empty
		list records will be returned in "natural" order.

		If ``offset`` is not ``None`` it must be a non-negative integer and
		defines at which offset in the actual list of records output will begin.
		I.e. passing ``offset=1`` will skip the first record.

		If ``limit`` is not ``None`` it must be a positive integer and defines
		how may records (starting at the record defined by ``offset``) should be
		returned.

		Records will be returned as an :class:`AppRecordPage`.
		"""

		filter = self._make_filter(filter)
		sort = _make_sort(sort)
		offset = _make_offset(offset)
		limit = _make_limit(limit)

		return AppGroupRecordPage(self, filter=filter, sort=sort, offset=offset, limit=limit)


class Field(CustomAttributes):
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

		A field specific label. Setting the label to ``None`` resets the value
		back to the label of the :class:`Control`.

	.. attribute:: description
		:type: str

		A field specific description. Setting the description to ``None`` resets
		the value back to the description of the :class:`Control`.

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

	.. attribute:: priority
		:type: bool

		This mirrors :attr:`Control.priority`.

	.. attribute:: in_list
		:type: bool

		This is an alias for :attr:`priority`.

	.. attribute:: in_mobile_list
		:type: bool

		This mirrors :attr:`Control.in_mobile_list`.

	.. attribute:: in_text
		:type: bool

		This mirrors :attr:`Control.in_text`.

		This attribute is settable.

	.. attribute:: mode
		:type: Control.Mode

		TODO

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

	.. attribute:: required
		:type: bool

		Is this field required or not in the input form? Setting the label to ``None``
		resets the value back to the ``required`` field of the :class:`Control`.
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({"control", "record", "label", "description", "value", "is_empty", "is_dirty", "errors", "priority", "in_list", "in_mobile_list", "in_text", "required", "mode", "has_errors", "add_error", "set_error", "clear_errors", "enabled", "writable", "visible"})
	ul4_type = ul4c.Type("la", "Field", "The value of a field of a record (and related information)")

	def __init__(self, control, record, value):
		super().__init__()
		self.control = control
		self.record = record
		self._label = None
		self._description = None
		self._lookupdata = None
		self._value = None
		self._dirty = False
		self.errors = []
		self._in_text = None
		self._required = None
		self._mode = None
		self.enabled = True
		self.writable = True
		self.visible = True
		self._set_value(value)
		self._dirty = False

	def _template_candidates(self):
		handler = self.record.app.globals._gethandler()
		app_id = self.record.app.id
		yield handler.fetch_internaltemplates(app_id, "field_instance", self.control.id)
		yield handler.fetch_internaltemplates(app_id, f"field_{self.control.type}_instance", None)
		yield handler.fetch_internaltemplates(app_id, f"field_instance", None)
		yield handler.fetch_librarytemplates(f"field_{self.control.type}_instance")
		yield handler.fetch_librarytemplates("field_instance")

	def _template_is_bound(self, template):
		return template.namespace.endswith(("_instance", f"_instance.{self.control.id}"))

	@property
	def label(self) -> str:
		return self._label if self._label is not None else self.control.label

	@label.setter
	def label(self, label: str | None) -> None:
		self._label = label

	@property
	def description(self) -> str:
		return self._description if self._description is not None else self.control.description

	@description.setter
	def description(self, description: str | None) -> None:
		self._description = description

	@property
	def priority(self) -> bool:
		return self.control.priority

	@property
	def in_list(self) -> bool:
		return self.control.in_list

	@property
	def in_mobile_list(self) -> bool:
		return self.control.in_mobile_list

	@property
	def in_text(self) -> bool:
		return self._in_text if self._in_text is not None else self.control.in_text

	@in_text.setter
	def in_text(self, in_text) -> bool:
		self._in_text = in_text

	@property
	def required(self) -> bool:
		return self._required if self._required is not None else self.control.required

	@required.setter
	def required(self, required: bool | None) -> None:
		self._required = required

	@property
	def value(self) -> Any:
		return self._value

	@value.setter
	def value(self, value: Any) -> None:
		oldvalue = self._value
		self.clear_errors()
		self._set_value(value)
		if value != oldvalue:
			self.record.values[self.control.identifier] = self._value
			self._dirty = True

	def is_empty(self) -> bool:
		return self._value is None or (isinstance(self._value, list) and not self._value)

	def is_dirty(self) -> bool:
		return self._dirty

	def has_errors(self) -> bool:
		return bool(self.errors)

	def add_error(self, *errors: str) -> None:
		self.errors.extend(errors)

	def set_error(self, error: str | None) -> None:
		if error is None:
			self.errors = []
		else:
			self.errors = [error]

	def clear_errors(self) -> None:
		self.errors = []

	def check_errors(self) -> None:
		if self.errors:
			raise FieldValidationError(self, self.errors[0])

	@property
	def mode(self) -> str:
		return self._mode if self._mode is not None else self.control.mode

	@mode.setter
	def mode(self, mode: str) -> None:
		self._mode = mode

	def _asjson(self, handler: Handler) -> Any:
		return self.control._asjson(handler, self)

	def _asdbarg(self, handler: Handler) -> Any:
		return self.control._asdbarg(handler, self)

	def ul4_getattr(self, name: str) -> Any:
		if name == "mode":
			mode = self.mode
			if mode is not None:
				mode = mode.value
			return mode
		else:
			return getattr(self, name)

	def __repr__(self) -> str:
		s = f"<{self.__class__.__module__}.{self.__class__.__qualname__} identifier={self.control.identifier!r} value={self._value!r}"
		if self._dirty:
			s += " is_dirty()=True"
		if self.errors:
			s += " has_errors()=True"
		s += f" at {id(self):#x}>"
		return s

	def ul4ondump(self, encoder: ul4on.Encoder) -> None:
		encoder.dump(self.control)
		encoder.dump(self.record)
		encoder.dump(self.label)
		encoder.dump(self.lookupdata)
		encoder.dump(self.value)
		encoder.dump(self.errors)
		encoder.dump(self.enabled)
		encoder.dump(self.writable)
		encoder.dump(self.visible)
		encoder.dump(self._required)

	def ul4onload(self, decoder: ul4on.Decoder) -> None:
		self.control = decoder.load()
		self.record = decoder.load()
		self.label = decoder.load()
		self.lookupdata = decoder.load()
		self.value = decoder.load()
		self.errors = decoder.load()
		self.enabled = decoder.load()
		self.writable = decoder.load()
		self.visible = decoder.load()
		self._required = decoder.load()


class BoolField(Field):
	def _set_value(self, value):
		if value is None:
			if self.required:
				self.add_error(error_required(self, value))
			value = None
		elif isinstance(value, str):
			if not value:
				if self.required:
					self.add_error(error_required(self, value))
				value = False
			elif value.lower() in {"false", "no", "0", "off"}:
				if self.required:
					self.add_error(error_truerequired(self, value))
				value = False
			else:
				value = True
		elif isinstance(value, bool):
			if not value and self.required:
				self.add_error(error_truerequired(self, value))
		else:
			self.add_error(error_wrong_type(self, value))
			value = None
		self._value = value


class IntField(Field):
	def _set_value(self, value):
		if value is None or value == "":
			if self.required:
				self.add_error(error_required(self, value))
			value = None
		elif isinstance(value, int):
			value = int(value) # This converts :class:`bool`\s etc.
		elif isinstance(value, str):
			try:
				value = int(value)
			except ValueError:
				self.add_error(error_number_format(self, value))
		else:
			self.add_error(error_wrong_type(self, value))
			value = None
		self._value = value


class NumberField(Field):
	def _set_value(self, value):
		if value is None or value == "":
			if self.required:
				self.add_error(error_required(self, value))
			value = None
		elif isinstance(value, (int, float)):
			# This converts :class:`bool`\s and :class:`int`\s.
			value = float(value)
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
				self.add_error(error_number_format(self, value))
		else:
			self.add_error(error_wrong_type(self, value))
			value = None
		self._value = value


class StringField(Field):
	def _set_value(self, value):
		if value is None or value == "":
			if self.required:
				self.add_error(error_required(self, value))
			value = None
		elif isinstance(value, str):
			minlength = self.control.minlength
			maxlength = self.control.maxlength
			if minlength is not None and len(value or "") < minlength:
				self.add_error(error_string_tooshort(self, minlength, value))
			if maxlength is not None and len(value or "") > maxlength:
				self.add_error(error_string_toolong(self, maxlength, value))
		else:
			self.add_error(error_wrong_type(self, value))
			value = None
		self._value = value


class TextField(StringField):
	pass


class URLField(StringField):
	def _set_value(self, value):
		if isinstance(value, str) and value:
			if not validators.url(value):
				self.add_error(error_url_format(self, value))
		super()._set_value(value)


class EmailField(StringField):
	_pattern = re.compile("^[a-zA-Z0-9_#$%&’*+/=?^.-]+(?:\\.[a-zA-Z0-9_+&*-]+)*@(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,7}$")

	def _set_value(self, value):
		if isinstance(value, str) and value and not self._pattern.match(value):
			# Check if we have any non-ASCII characters
			pos = misc.first(i for (i, c) in enumerate(value) if ord(c) > 0x7f)
			if pos is not None:
				self.add_error(error_email_badchar(self.control.app.globals.lang, self.label, pos, value))
			else:
				self.add_error(error_email_format(self.control.app.globals.lang, self.label, value))
		super()._set_value(value)


class TelField(StringField):
	_pattern = re.compile("^\\+?[0-9 /()-]+$")

	def _set_value(self, value):
		if isinstance(value, str) and value and not self._pattern.match(value):
			self.add_error(error_tel_format(self, value))
		super()._set_value(value)


class PasswordField(StringField):
	pass


class TextAreaField(StringField):
	pass


class HTMLField(StringField):
	pass


class DateField(Field):
	def _convert(self, value):
		if isinstance(value, datetime.datetime):
			value = value.date()
		return value

	def _parse_value(self, value):
		lang = self.control.app.globals.lang
		if lang in self.control.formats:
			for format in self.control.formats[lang]:
				try:
					return self._convert(datetime.datetime.strptime(value, format))
				except ValueError:
					pass
		try:
			return self._convert(datetime.datetime.fromisoformat(value))
		except ValueError:
			pass
		return value

	def _set_value(self, value):
		if value is None or value == "":
			if self.required:
				self.add_error(error_required(self, value))
			value = None
		elif isinstance(value, datetime.date):
			value = self._convert(value)
		elif isinstance(value, str):
			value = self._parse_value(value)
			if isinstance(value, str):
				self.add_error(error_date_format(self, value))
				# We keep the string value, as a <form> input might want to display it.
		else:
			self.add_error(error_wrong_type(self, value))
			value = None
		self._value = value


class DatetimeMinuteField(DateField):
	def _convert(self, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(second=0, microsecond=0)
		else:
			value = datetime.datetime.combine(value, datetime.time())
		return value


class DatetimeSecondField(DateField):
	def _convert(self, value):
		if isinstance(value, datetime.datetime):
			value = value.replace(microsecond=0)
		else:
			value = datetime.datetime.combine(value, datetime.time())
		return value


class FileField(Field):
	def _set_value(self, value):
		if value is None or value == "":
			if self.required:
				self.add_error(error_required(self, value))
			value = None
		elif not isinstance(value, File):
			self.add_error(error_wrong_type(self, value))
			value = None
		elif isinstance(value, str):
			file = globals.handler.file_sync_data(value, False)
			if not file:
				self.add_error(error_file_unknown(self, value))
				self._value = None
			else:
				self._value = file
		self._value = value


class FileSignatureField(FileField):
	def _set_value(self, value):
		if isinstance(value, str) and value:
			pos_slash = value.find("/")
			pos_semi = value.find(";")
			pos_comma = value.find(",")
			if not value.startswith("data:") or max(pos_semi, pos_comma, pos_slash) < 0 or not (pos_slash < pos_semi < pos_comma):
				self.add_error(error_file_invaliddataurl(self, value))
				value = None
			else:
				mimetype = value[5:pos_semi]
				extension = value[pos_slash+1:pos_semi]
				encoding = value[pos_semi+1:pos_comma]
				if encoding != "base64":
					self.add_error(error_file_invaliddataurl(self, value))
					value = None
				else:
					base64str = value[pos_comma+1:] + "=="
					try:
						bytes = base64.b64decode(base64str)
					except Exception:
						self.add_error(error_file_invaliddataurl(self, value))
						value = None
					else:
						try:
							img = Image.open(io.BytesIO(bytes))
						except Exception:
							self.add_error(error_file_invaliddataurl(self, value))
							value = None
						else:
							value = File(
								filename=f"{self.control.identifier}.{extension}",
								mimetype=mimetype,
								width=img.size[0],
								height=img.size[1],
								size=len(bytes),
								createdat=datetime.datetime.now(),
								content=bytes,
							)
		self._value = value


class GeoField(Field):
	def _set_value(self, value):
		if value is None or value == "":
			if self.required:
				self.add_error(error_required(self, value))
			value = None
		elif isinstance(value, Geo):
			pass
		elif isinstance(value, str):
			tryvalue = self.control.app.globals.handler._geofromstring(value)
			if tryvalue is None:
				self.add_error(error_wrong_value(value))
			else:
				value = tryvalue
		elif value is not None and not isinstance(value, Geo):
			self.add_error(error_wrong_type(self, value))
			value = None
		self._value = value


class LookupField(Field):
	r"""
	Adds the following attribute to instances:

	.. attribute:: lookupdata
		:type: dict[str, str | LookupItem]

		Custom lookup data for this field.

		The dictionary keys should be the ``key`` attribute of
		:class:`LookupItem`\s and the values should be :class:`LookupItem` or
		:class:`str` objects.

		Using :class:`str` as the values makes it possible to use custom labels
		in input forms.
	"""

	ul4_attrs = Field.ul4_attrs.union({"lookupdata", "has_custom_lookupdata"})

	def __init__(self, control, record, value):
		super().__init__(control, record, value)
		self._lookupdata = None

	@property
	def lookupdata(self):
		return self._lookupdata if self._lookupdata is not None else self.control.lookupdata

	@lookupdata.setter
	def lookupdata(self, lookupdata):
		control = self.control
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

	def has_custom_lookupdata(self):
		return self._lookupdata is not None

	def _find_lookupitem(self, value) -> tuple[None | LookupItem | str, str | None]:
		lookupdata = self.control.lookupdata
		if isinstance(value, str):
			if lookupdata is None:
				return (value, None)
			if value not in lookupdata:
				if self.control.autoexpandable:
					for lookupitem in lookupdata:
						if value == lookupitem.label:
							return (lookupitem, None)
				return (None, error_lookupitem_unknown(self, value))
			return (lookupdata[value], None)
		elif isinstance(value, LookupItem):
			if lookupdata is None:
				return (value, None)
			tryvalue = lookupdata.get(value.key, None)
			if value is not tryvalue:
				return (None, error_lookupitem_foreign(self, value))
			return (tryvalue, None)
		else:
			return (None, error_wrong_type(self, value))

	def _set_value(self, value):
		if value is None or value == "" or value == self.control.none_key:
			if self.required:
				self.add_error(error_required(self, value))
			self._value = None
		else:
			(value, error) = self._find_lookupitem(value)
			self._value = value
			if error is not None:
				self.add_error(error)


class LookupSelectField(LookupField):
	pass


class LookupRadioField(LookupField):
	pass


class LookupChoiceField(LookupField):
	pass


class AppLookupField(Field):
	r"""
	Adds the following attribute to instances:

	.. attribute:: lookupdata
		:type: dict[str, str | Record]

		Custom lookup data for this field.

		The dictionary keys should be the ``id`` attribute of :class:`Record`
		objects and the values should be :class:`Record` or :class:`str` objects.

		Using :class:`str` as the values makes it possible to use custom labels
		in input forms.
	"""

	ul4_attrs = Field.ul4_attrs.union({"lookupdata", "has_custom_lookupdata"})

	def __init__(self, control, record, value):
		super().__init__(control, record, value)
		self._lookupdata = None

	@property
	def lookupdata(self):
		lookupdata = self._lookupdata
		if lookupdata is None:
			if self.control.lookupapp is not None:
				lookupdata = self.control.lookupapp.records
			else:
				lookupdata = {"nolookupapp": error_applookup_notargetapp(self.control)}
		if lookupdata is None:
			lookupdata = {"norecords": error_applookup_norecords(self.control)}
		return lookupdata

	@lookupdata.setter
	def lookupdata(self, lookupdata):
		if lookupdata is None:
			lookupdata = []
		elif isinstance(lookupdata, str):
			lookupdata = [lookupdata]
		elif isinstance(lookupdata, dict):
			lookupdata = [v if isinstance(v, Record) else k for (k, v) in lookupdata.items()]
		records = []
		fetched = self.control.app.globals.handler.records_sync_data([v for v in lookupdata if isinstance(v, str)])
		for v in lookupdata:
			if isinstance(v, str):
				record = fetched.get(v, None)
				if record is None:
					raise ValueError(error_applookuprecord_unknown(v))
				v = record
			if isinstance(v, Record):
				if v.app is not self.control.lookup_app:
					raise ValueError(error_applookuprecord_foreign(self, v))
				else:
					records.append(v)
			elif v is not None:
				raise ValueError(error_wrong_type(self, v))
		self._lookupdata = {r.id : r for r in records}

	def has_custom_lookupdata(self):
		return self._lookupdata is not None

	def _find_lookup_record(self, value) -> tuple[Record | None, str | None]:
		if isinstance(value, str):
			record = self.control.app.globals.handler.record_sync_data(value)
			if record is None:
				return (None, error_applookuprecord_unknown(value))
			value = record
		if isinstance(value, Record):
			if self.control.lookup_app is not None and value.app is not self.control.lookup_app:
				return (None, error_applookuprecord_foreign(self, value))
		else:
			return (None, error_wrong_type(self, value))
		return (value, None)

	def _set_value(self, value):
		if value is None or value == "" or value == self.control.none_key:
			if self.required:
				self.add_error(error_required(self, value))
			self._value = None
		else:
			(value, error) = self._find_lookup_record(value)
			self._value = value
			if error is not None:
				self.add_error(error)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self._lookupdata)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self._lookupdata = decoder.load()


class AppLookupSelectField(AppLookupField):
	pass


class AppLookupRadioField(AppLookupField):
	pass


class AppLookupChoiceField(AppLookupField):
	"""
	:class:`AppLookupChoiceField` has the following additional attributes:

	.. attribute:: search_url
		:type: str

		The URL to use for the ajax search in view templates. This value is
		inherited from the control and can be changed.

	.. attribute:: search_param_name
		:type: str

		The name for the parameter containing the search term. This value is
		inherited from the control and can be changed.

	.. attribute:: target_param_name
		:type: str

		The name for the parameter containing css selector for the target html element.
		This value is inherited from the control and can be changed.
	"""
	ul4_attrs = AppLookupField.ul4_attrs.union({"search_url", "search_param_name", "target_param_name"})

	def __init__(self, control, record, value):
		super().__init__(control, record, value)
		self._search_url = None
		self._search_param_name = None
		self._target_param_name = None

	@property
	def search_url(self):
		return self._search_url if self._search_url is not None else self.control.search_url

	@search_url.setter
	def search_url(self, search_url):
		self._search_url = search_url

	@property
	def search_param_name(self):
		return self._search_param_name if self._search_param_name is not None else self.control.search_param_name

	@search_param_name.setter
	def search_param_name(self, search_param_name):
		self._search_param_name = search_param_name

	@property
	def target_param_name(self):
		return self._target_param_name if self._target_param_name is not None else self.control.target_param_name

	@target_param_name.setter
	def target_param_name(self, target_param_name):
		self._target_param_name = target_param_name


class MultipleLookupField(LookupField):
	def _set_value(self, value):
		if value is None or value == "" or value == self.control.none_key:
			if self.required:
				self.add_error(error_required(self, value))
			self._value = []
		elif isinstance(value, (str, LookupItem)):
			self._set_value([value])
		elif isinstance(value, list):
			lookupdata = self.control.lookupdata
			self._value = []
			for v in value:
				if v is None or v == "" or v == self.control.none_key:
					continue
				if isinstance(v, str):
					if v in lookupdata:
						self._value.append(lookupdata[v])
					else:
						self.add_error(error_lookupitem_unknown(self, v))
				elif isinstance(v, LookupItem):
					if v.key not in lookupdata or lookupdata[v.key] is not v:
						self.add_error(error_lookupitem_foreign(self, v))
					else:
						self._value.append(v)
			if not self._value and self.required:
				self.add_error(error_required(self, value))
		else:
			self.add_error(error_wrong_type(self, value))
			self._value = []


class MultipleLookupSelectField(MultipleLookupField):
	pass


class MultipleLookupCheckboxField(MultipleLookupField):
	pass


class MultipleLookupChoiceField(MultipleLookupField):
	pass


class MultipleAppLookupField(AppLookupField):
	def _set_value(self, value):
		if value is None or value == "" or value == self.control.none_key:
			if self.required:
				self.add_error(error_required(self, value))
			self._value = []
		elif isinstance(value, (str, Record)):
			self._set_value(self, [value])
		elif isinstance(value, list):
			self._value = []
			dat_ids = [v for v in value if isinstance(v, str) and v and v != self.control.none_key]
			if dat_ids:
				fetched = self.control.app.globals.handler.records_sync_data(dat_ids)
			else:
				fetched = {}
			for v in value:
				if v is None or v == "" or v == self.control.none_key:
					continue
				if isinstance(v, str):
					record = fetched.get(v, None)
					if record is None:
						self.add_error(error_applookuprecord_unknown(v))
						v = None
					else:
						v = record
				if isinstance(v, Record):
					if self.control.lookup_app is not None and v.app is not self.control.lookup_app:
						self.add_error(error_applookuprecord_foreign(self, v))
					else:
						self._value.append(v)
				elif v is not None:
					self.add_error(error_wrong_type(self, v))
			if not self._value and self.required:
				self.add_error(error_required(self, value))
		else:
			self.add_error(error_wrong_type(self, value))
			self._value = []


class MultipleAppLookupSelectField(MultipleAppLookupField):
	pass


class MultipleAppLookupCheckboxField(MultipleAppLookupField):
	pass


class MultipleAppLookupChoiceField(MultipleAppLookupField):
	pass


class Control(CustomAttributes):
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

		This attribute is settable.

	.. attribute:: description
		:type: str

		Description of this control.

		This attribute is settable.

	.. attribute:: priority
		:type: bool

		Has this control high priority, i.e. should it be displayed in lists?

		This attribute is settable.

	.. attribute:: in_list
		:type: bool

		This is an alias for :attr:`priority`.

	.. attribute:: in_mobile_list
		:type: bool

		Should this control be displayed in lists on mobile devices?

		This attribute is settable.

	.. attribute:: in_text
		:type: bool

		Should this control be displayed when a record is printed as text?

		This attribute is settable.

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

		Is a value required for this field?

		If a view is active this value is the value from the active view.

		This attribute is settable (but the value will be shadowd unless/until
		there's no active view).

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
	ul4_attrs = CustomAttributes.ul4_attrs.union({"id", "identifier", "type", "subtype", "fulltype", "app", "label", "description", "priority", "in_list", "in_mobile_list", "in_text", "required", "order", "default", "top", "left", "width", "height", "liveupdate", "tabindex", "mode", "labelpos", "labelwidth", "autoalign", "in_active_view", "is_focused", "ininsertprocedure", "inupdateprocedure", "save"})
	ul4_type = ul4c.Type("la", "Control", "Metainformation about a field in a LivingApps application")

	class Mode(misc.Enum):
		DISPLAY = "display"
		EDIT = "edit"
		READONLY = "readonly"
		HIDDEN = "hidden"
		ABSENT = "absent"

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
	fieldname = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get="", set=True, ul4get="_label_get", ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	priority = BoolAttr(get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	in_list = BoolAttr(get="_in_list_get", set="_in_list_set", ul4get="_in_list_get", ul4set="_in_list_set")
	in_mobile_list = BoolAttr(get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	in_text = BoolAttr(get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	required = BoolAttr(get="", set="", ul4get="_required_get", ul4onset=True, ul4onget=True)
	required_in_view = BoolAttr(ul4onset=True, ul4onget=True)
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	default = Attr(get="", ul4get="_default_get")
	ininsertprocedure = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	inupdateprocedure = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	top = Attr(int, get="", ul4get="_top_get")
	left = Attr(int, get="", ul4get="_left_get")
	width = Attr(int, get="", ul4get="_width_get")
	height = Attr(int, get="", ul4get="_height_get")
	z_index = Attr(int, get="", ul4get="_z_index_get")
	liveupdate = BoolAttr(get="", ul4get="_liveupdate_get")
	tabindex = Attr(int, get="", ul4get="_tabindex_get")
	mode = EnumAttr(Mode, get="", ul4get="", set=True, ul4set=True)
	labelpos = EnumAttr(LabelPos, get="", ul4get="")
	labelwidth = Attr(int, get="", ul4get="_labelwidth_get")
	autoalign = BoolAttr(get="", ul4get="_autoalign_get")
	custom = Attr(get=True, set=True, ul4get=True, ul4set=True)

	def __init__(self, id=None, identifier=None, fieldname=None, label=None, priority=None, order=None):
		super().__init__()
		self.id = id
		self.app = None
		self.identifier = identifier
		self.fieldname = fieldname
		self.label = label
		self.description = None
		self.priority = priority
		self.__dict__["required"] = None
		self.__dict__["required_in_view"] = None
		self.order = order
		self._mode = None
		self._vsqlfield = None

	def _gethandler(self) -> Handler:
		return self.app._gethandler()

	def _template_candidates(self):
		handler = self.app.globals._gethandler()
		app_id = self.app.id
		yield handler.fetch_internaltemplates(app_id, "control_instance", self.id)
		yield handler.fetch_internaltemplates(app_id, f"control_{self.type}_instance", None)
		yield handler.fetch_internaltemplates(app_id, f"control_instance", None)
		yield handler.fetch_librarytemplates(f"control_{self.type}_instance")
		yield handler.fetch_librarytemplates("control_instance")

	def _template_is_bound(self, template):
		return template.namespace.endswith(("_instance", f"_instance.{self.id}"))

	@property
	def ul4onid(self) -> str:
		return self.id

	def _type_get(self):
		return self._type

	def _subtype_get(self):
		return self._subtype

	def _fulltype_get(self):
		return self._fulltype

	def _get_viewviewcontrol(self):
		view = self.app.active_view
		if view is None:
			return (None, None)
		if view.controls is None:
			return (view, None)
		return (view, view.controls.get(self.identifier))

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

	def _in_list_get(self):
		return self.priority

	def _in_list_set(self, value):
		self.priority = value

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

	def _z_index_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.z_index
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
		(v, vc) = self._get_viewviewcontrol()
		# We have a corresponding control it the view, so we can use its info
		if vc is not None:
			return vc.required
		# We have a view, but it doesn't contain the control, so it can never be required
		if v is not None:
			return False
		required = self.__dict__["required"]
		if required is not None:
			return required
		return self.__dict__["required_in_view"]

	def _required_set(self, value):
		self.__dict__["required"] = None if value is None else bool(value)

	def _mode_get(self):
		if self._mode is not None:
			return self._mode
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.mode
		return Control.Mode.DISPLAY

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

	def _labelwidth_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.labelwidth
		return None

	def _autoalign_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.autoalign
		return None

	def in_active_view(self):
		vc = self._get_viewcontrol()
		return vc is not None

	def is_focused(self):
		active_view = self.app.active_view
		return active_view is not None and self is active_view.focus_control

	def _default_get(self):
		return None

	def save(self):
		handler = self._gethandler()
		return handler.save_control(self)

	def _asdbarg(self, handler, field):
		return field._value

	def _asjson(self, handler, field):
		return self._asdbarg(handler, field)

	def vsqlsearchexpr(self, record, maxdepth):
		return None # The default is that this field cannot be searched

	def vsqlsortexpr(self, record, maxdepth):
		return [] # The default doesn't add any sort expressions

	def sql_fetch_statement(self):
		return f"livingapi_pkg.field_{self._type}_inc_ul4on({vsql.sql(self.identifier)}, row.{self.fieldname});"


class StringControl(Control):
	"""
	Base class for all controls of type ``string``.

	Relevant instance attributes are:

	.. attribute::  -> strminlength
		:type: Optional[int]

		The minimum allowed string length (``None`` means unlimited).

	.. attribute:: maxlength
		:type: Optional[int] -> str

		The maximum allowed string length (``None`` means unlimited).

	.. attribute:: placeholder
		:type: Optional[str]

		The placeholder for the HTML input.
	"""

	ul4_attrs = Control.ul4_attrs.union({"minlength", "maxlength", "placeholder"})

	_type = "string"
	ul4_type = ul4c.Type("la", "StringControl", "A LivingApps string field")

	minlength = Attr(int, get="", ul4get="_minlength_get")
	maxlength = Attr(int, get="", ul4get="_maxlength_get")
	placeholder = Attr(str, get="", ul4get="_placeholder_get")

	fieldtype = StringField

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR, f"{{a}}.{self.fieldname}")
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


@register("textcontrol")
class TextControl(StringControl):
	"""
	Describes a field of type ``string``/``text``.
	"""

	_subtype = "text"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "TextControl", "A LivingApps text field (type 'string/text')")

	fieldtype = TextField


@register("urlcontrol")
class URLControl(StringControl):
	"""
	Describes a field of type ``string``/``url``.
	"""

	_subtype = "url"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "URLControl", "A LivingApps URL field (type 'string/url')")

	fieldtype = URLField


@register("emailcontrol")
class EmailControl(StringControl):
	"""
	Describes a field of type ``string``/``email``.
	"""

	_subtype = "email"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "EmailControl", "A LivingApps email field (type 'string/email')")

	fieldtype = EmailField


@register("passwordcontrol")
class PasswordControl(StringControl):
	"""
	Describes a field of type ``string``/``password``.
	"""

	_subtype = "password"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "PasswordControl", "A LivingApps email field (type 'string/email')")

	fieldtype = PasswordField


@register("telcontrol")
class TelControl(StringControl):
	"""
	Describes a field of type ``string``/``tel``.
	"""

	_subtype = "tel"
	_fulltype = f"{StringControl._type}/{_subtype}"
	ul4_type = ul4c.Type("la", "TelControl", "A LivingApps phone number field (type 'string/tel')")

	fieldtype = TelField


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

	fieldtype = TextAreaField

	def _maxlength_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			return vc.maxlength
		return None

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.CLOB, f"{{a}}.{self.fieldname}")
		return self._vsqlfield

	def sql_fetch_statement(self):
		return f"livingapi_pkg.field_textarea_inc_ul4on({vsql.sql(self.identifier)}, row.{self.fieldname});"


@register("htmlcontrol")
class HTMLControl(StringControl):
	"""
	Describes a field of type ``string``/``html``.
	"""

	_subtype = "html"
	_fulltype = f"{StringControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "HTMLControl", "A LivingApps HTML field (type 'string/html')")

	fieldtype = HTMLField

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.CLOB, f"{{a}}.{self.fieldname}")
		return self._vsqlfield


@register("intcontrol")
class IntControl(Control):
	"""
	Describes a field of type ``int``.
	"""

	_type = "int"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "IntControl", "A LivingApps integer field (type 'int')")

	fieldtype = IntField

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.INT, f"{{a}}.{self.fieldname}")
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

	ul4_attrs = Control.ul4_attrs.union({"precision", "minimum", "maximum"})
	ul4_type = ul4c.Type("la", "NumberControl", "A LivingApps number field (type 'number')")

	precision = Attr(int, get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	minimum = FloatAttr(get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	maximum = FloatAttr(get=True, set=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)

	fieldtype = NumberField

	def __init__(self, id=None, identifier=None, fieldname=None, label=None, priority=None, order=None):
		super().__init__(id=id, identifier=identifier, fieldname=fieldname, label=label, priority=priority, order=order)
		self.precision = None
		self.minimum = None
		self.maximum = None

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.NUMBER, f"{{a}}.{self.fieldname}")
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

	fieldtype = DateField

	_suffixes = [
		"",
		" %H:%M",
		"T%H:%M",
		" %H:%M:%S",
		"T%H:%M:%S",
		" %H:%M:%S.%f",
		"T%H:%M:%S.%f",
		" %H:%M%z",
		"T%H:%M%z",
		" %H:%M:%S%z",
		"T%H:%M:%S%z",
		" %H:%M:%S.%f%z",
		"T%H:%M:%S.%f%z",
		" %H:%M %z",
		"T%H:%M %z",
		" %H:%M:%S %z",
		"T%H:%M:%S %z",
		" %H:%M:%S.%f %z",
		"T%H:%M:%S.%f %z",
	]

	formats = dict(
		en=["%m/%d/%Y" + suffix for suffix in _suffixes],
		de=["%d.%m.%Y" + suffix for suffix in _suffixes],
		fr=["%d.%m.%Y" + suffix for suffix in _suffixes],
		it=["%d.%m.%Y" + suffix for suffix in _suffixes],
	)

	del _suffixes

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			default = vc.default
			if default == "{today}":
				return datetime.date.today()
		return None

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
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.DATE, f"{{a}}.{self.fieldname}")
		return self._vsqlfield


@register("datetimeminutecontrol")
class DatetimeMinuteControl(DateControl):
	"""
	Describes a field of type ``date``/``datetimeminute``.
	"""

	_subtype = "datetimeminute"
	_fulltype = f"{DateControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "DatetimeMinuteControl", "A LivingApps date field (type 'date/datetimeminute')")

	fieldtype = DatetimeMinuteField

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
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.DATETIME, f"{{a}}.{self.fieldname}")
		return self._vsqlfield

	def sql_fetch_statement(self):
		return f"livingapi_pkg.field_datetime_inc_ul4on({vsql.sql(self.identifier)}, row.{self.fieldname});"


@register("datetimesecondcontrol")
class DatetimeSecondControl(DateControl):
	"""
	Describes a field of type ``date``/``datetimesecond``.
	"""

	_subtype = "datetimesecond"
	_fulltype = f"{DateControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "DatetimeSecondControl", "A LivingApps date field (type 'date/datetimesecond')")

	fieldtype = DatetimeSecondField

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
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.DATETIME, f"{{a}}.{self.fieldname}")
		return self._vsqlfield

	def sql_fetch_statement(self):
		return f"livingapi_pkg.field_datetime_inc_ul4on({vsql.sql(self.identifier)}, row.{self.fieldname});"


@register("boolcontrol")
class BoolControl(Control):
	"""
	Describes a field of type ``bool``.
	"""

	_type = "bool"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "BoolControl", "A LivingApps boolean field (type 'bool')")

	fieldtype = BoolField

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			value = int(value)
		return value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.BOOL, f"{{a}}.{self.fieldname}")
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

	fieldtype = LookupField

	def __init__(self, id=None, identifier=None, fieldname=None, label=None, priority=None, order=None, lookupdata=None, autoexpandable=False):
		super().__init__(id=id, identifier=identifier, fieldname=fieldname, label=label, priority=priority, order=order)
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

	def _asdbarg(self, handler, field):
		value = field._value
		if isinstance(value, LookupItem):
			value = value.key
		return value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR, f"{{a}}.{self.fieldname}")
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

	def sql_fetch_statement(self):
		return f"livingapi_pkg.field_{self._type}_inc_ul4on({vsql.sql(self.identifier)}, {vsql.sql(self.id)}, row.{self.fieldname});"


@register("lookupselectcontrol")
class LookupSelectControl(LookupControl):
	"""
	Describes a field of type ``lookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupSelectControl", "A LivingApps lookup field (type 'lookup/select')")

	fieldtype = LookupSelectField


@register("lookupradiocontrol")
class LookupRadioControl(LookupControl):
	"""
	Describes a field of type ``lookup``/``radio``.
	"""

	_subtype = "radio"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupRadioControl", "A LivingApps lookup field (type 'lookup/radio')")

	fieldtype = LookupRadioField



@register("lookupchoicecontrol")
class LookupChoiceControl(LookupControl):
	"""
	Describes a field of type ``lookup``/``choice``.
	"""

	_subtype = "choice"
	_fulltype = f"{LookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "LookupChoiceControl", "A LivingApps lookup field (type 'lookup/choice')")

	fieldtype = LookupChoiceField


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

	fieldtype = AppLookupField

	def __init__(self, id=None, identifier=None, fieldname=None, label=None, priority=None, order=None, lookup_app=None, lookup_controls=None, local_master_control=None, local_detail_controls=None, remote_master_control=None):
		super().__init__(id=id, identifier=identifier, fieldname=fieldname, label=label, priority=priority, order=order)
		self.lookup_app = lookup_app
		self.lookup_controls = lookup_controls
		self.local_master_control = local_master_control
		self.local_detail_controls = local_detail_controls
		self.remote_master_control = remote_master_control

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
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR, f"{{a}}.{self.fieldname}", f"({{m}}.{self.fieldname} = {{d}}.dat_id(+))", self.lookup_app.vsqlgroup_records)
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

	def sql_fetch_statement(self):
		return f"livingapi_pkg.field_{self._type}_inc_ul4on({vsql.sql(self.identifier)}, {vsql.sql(str(self.lookup_app.internal_id))}, row.{self.fieldname});"


@register("applookupselectcontrol")
class AppLookupSelectControl(AppLookupControl):
	"""
	Describes a field of type ``applookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupSelectControl", "A LivingApps applookup field (type 'applookup/select')")

	fieldtype = AppLookupSelectField


@register("applookupradiocontrol")
class AppLookupRadioControl(AppLookupControl):
	"""
	Describes a field of type ``applookup``/``radio``.
	"""

	_subtype = "radio"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "AppLookupRadioControl", "A LivingApps applookup field (type 'applookup/radio')")

	fieldtype = AppLookupRadioField


@register("applookupchoicecontrol")
class AppLookupChoiceControl(AppLookupControl):
	"""
	Describes a field of type ``applookup``/``choice``.

	:class:`AppLookupChoiceControl` has the following additional attributes:

	.. attribute:: search_url
		:type: str

		The URL to use for the ajax search in view templates.

	.. attribute:: search_param_name
		:type: str

		The name for the parameter containing the search term.

	.. attribute:: target_param_name
		:type: str

		The name for the parameter containing css selector for the target html element.
	"""

	_subtype = "choice"
	_fulltype = f"{AppLookupControl._type}/{_subtype}"

	ul4_attrs = AppLookupControl.ul4_attrs.union({"search_url", "search_param_name", "target_param_name"})
	ul4_type = ul4c.Type("la", "AppLookupChoiceControl", "A LivingApps applookup field (type 'applookup/choice')")

	fieldtype = AppLookupChoiceField

	@property
	def search_url(self):
		return self.app.template_url(f"field_{self.identifier}_search")

	search_param_name = "q"
	target_param_name = "target"


class MultipleLookupControl(LookupControl):
	"""
	Base class for all controls of type ``multiplelookup``.
	"""

	_type = "multiplelookup"

	ul4_type = ul4c.Type("la", "MultipleLookupControl", "A LivingApps multiplelookup field")

	fieldtype = MultipleLookupField

	def _default_get(self):
		vc = self._get_viewcontrol()
		if vc is not None:
			value = self.lookupdata.get(vc.default, None)
			if value is not None:
				return [value]
		return None

	def _asjson(self, handler, field):
		return [item.key for item in field._value]

	def _asdbarg(self, handler, field):
		return handler.varchars([item.key for item in field._value])

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			id = self.fieldname.removeprefix("lup_kennungs")
			fieldsql = f"cast(multiset(select lup_kennung from data_lookup_select dl where dl.dat_id = {{a}}.dat_id and dl.dl_i = {id}) as varchars)"
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STRLIST, fieldsql)
		return self._vsqlfield


@register("multiplelookupselectcontrol")
class MultipleLookupSelectControl(MultipleLookupControl):
	"""
	Describes a field of type ``multiplelookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupSelectControl", "A LivingApps multiplelookup field (type 'multiplelookup/select')")

	fieldtype = MultipleLookupSelectField


@register("multiplelookupcheckboxcontrol")
class MultipleLookupCheckboxControl(MultipleLookupControl):
	"""
	Describes a field of type ``multiplelookup``/``checkbox``.
	"""

	_subtype = "checkbox"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupCheckboxControl", "A LivingApps multiplelookup field (type 'multiplelookup/checkbox')")

	fieldtype = MultipleLookupCheckboxField


@register("multiplelookupchoicecontrol")
class MultipleLookupChoiceControl(MultipleLookupControl):
	"""
	Describes a field of type ``multiplelookup``/``choice``.
	"""

	_subtype = "choice"
	_fulltype = f"{MultipleLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleLookupChoiceControl", "A LivingApps multiplelookup field (type 'multiplelookup/choice')")

	fieldtype = MultipleLookupChoiceField


class MultipleAppLookupControl(AppLookupControl):
	"""
	Base class for all controls of type ``multipleapplookup``.
	"""

	_type = "multipleapplookup"

	ul4_type = ul4c.Type("la", "MultipleAppLookupControl", "A LivingApps multiple applookup field")

	fieldtype = MultipleAppLookupField

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
			id = self.fieldname.removeprefix("dat_ids_applookup")
			fieldsql = f"cast(multiset(select dat_id_applookup from data_applookup dal where dal.dat_id = {{a}}.dat_id and dal.dal_i = {id}) as varchars)"
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STRLIST, fieldsql)
		return self._vsqlfield


@register("multipleapplookupselectcontrol")
class MultipleAppLookupSelectControl(MultipleAppLookupControl):
	"""
	Describes a field of type ``multipleapplookup``/``select``.
	"""

	_subtype = "select"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupSelectControl", "A LivingApps multiple applookup field (type 'multipleapplookup/select')")

	fieldtype = MultipleAppLookupSelectField


@register("multipleapplookupcheckboxcontrol")
class MultipleAppLookupCheckboxControl(MultipleAppLookupControl):
	"""
	Describes a field of type ``multipleapplookup``/``checkbox``.
	"""

	_subtype = "checkbox"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupCheckboxControl", "A LivingApps multiple applookup field (type 'multipleapplookup/checkbox')")

	fieldtype = MultipleAppLookupCheckboxField


@register("multipleapplookupchoicecontrol")
class MultipleAppLookupChoiceControl(MultipleAppLookupControl):
	"""
	Describes a field of type ``multipleapplookup``/``choice``.
	"""

	_subtype = "choice"
	_fulltype = f"{MultipleAppLookupControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "MultipleAppLookupChoiceControl", "A LivingApps multiple applookup field (type 'multipleapplookup/choice')")

	fieldtype = MultipleAppLookupChoiceField


@register("filecontrol")
class FileControl(Control):
	"""
	Describes a field of type ``file``.
	"""

	_type = "file"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "FileControl", "A LivingApps upload field (type 'file')")

	fieldtype = FileField

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			if value.internal_id is None:
				field.add_error(error_object_unsaved(value))
				value = field._value = None
			else:
				value = value.internal_id
		return value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			# FIXME: This should reference :class:`File`, but Oracle doesn't support this yet.
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.STR, f"{{a}}.{self.fieldname}")
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

	def sql_fetch_statement(self):
		return f"livingapi_pkg.field_{self._type}_inc_ul4on({vsql.sql(self.identifier)}, {vsql.sql(self.fieldname)}, row.dat_id, v_tpl_uuid, row.{self.fieldname});"


@register("filesignaturecontrol")
class FileSignatureControl(FileControl):
	"""
	Describes a field of type ``file``/``signature``.
	"""

	_subtype = "signature"
	_fulltype = f"{FileControl._type}/{_subtype}"

	ul4_type = ul4c.Type("la", "FileSignatureControl", "A LivingApps signature image field (type 'file/signature')")

	fieldtype = FileSignatureField


@register("geocontrol")
class GeoControl(Control):
	"""
	Describes a field of type ``geo``.
	"""

	_type = "geo"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "GeoControl", "A LivingApps geo field (type 'geo')")

	fieldtype = GeoField

	def _asdbarg(self, handler, field):
		value = field._value
		if value is not None:
			value = f"{value.lat!r}, {value.long!r}, {value.info}"
		return value

	@property
	def vsqlfield(self):
		if self._vsqlfield is None:
			self._vsqlfield = vsql.Field(f"v_{self.identifier}", vsql.DataType.GEO, f"{{a}}.{self.fieldname}")
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
		:type: Optional[dict[str, str | LookupItem | Record]

		Lookup items for the control in this view.

	.. attribute:: autoexpandable
		:type: Optional[bool]

		Automatically add missing items (only for ``lookup`` and
		``multiplelookup``).
	"""

	ul4_attrs = Base.ul4_attrs.union({
		"id", "label", "identifier", "type", "subtype", "view", "control",
		"type", "subtype", "top", "left", "width", "height", "z_index", "liveupdate",
		"default", "tabIndex", "minlength", "maxlength", "required", "placeholder",
		"mode", "labelpos", "lookup_none_key", "lookup_none_label", "lookupdata",
		"autoalign", "labelwidth", "autoexpandable"
	})
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
	z_index = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
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
		self.z_index = None
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
		return self.control.identifier if self.control is not None else "?"

	def _type_get(self):
		return self.control.type if self.control is not None else "?"

	def _subtype_get(self):
		return self.control.subtype if self.control is not None else "?"

	def _mode_ul4onget(self):
		return self.mode is Control.Mode.DISPLAY

	def _mode_ul4onset(self, value):
		self.mode = Control.Mode.DISPLAY if value else Control.Mode.EDIT

	def _mode_ul4ondefault(self):
		self.mode = Control.Mode.EDIT


class State(misc.Enum):
	"""
	The database synchronisation state of the record or parameter.

	Values are:

	``NEW``
		The object has been created by the template, but hasn't been saved yet.

	``SAVED``
		The object has been loaded from the database and hasn't been changed since.

	``CHANGED``
		The object has been changed by the user.

	``DELETED``
		The object has been deleted in the database.
	"""

	NEW = "new"
	SAVED = "saved"
	CHANGED = "changed"
	DELETED = "deleted"


@register("record")
class Record(CustomAttributes):
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

	.. attribute:: details
		:type: dict[str, RecordChildren]

		Detail records, i.e. records that have a field pointing back to this
		record.
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({
		"id",
		"app",
		"createdat",
		"createdby",
		"updatedat",
		"updatedby",
		"updatecount",
		"fields",
		"values",
		"details",
		"children",
		"attachments",
		"errors",
		"custom",
		"has_errors",
		"has_errors_in_active_view",
		"add_error",
		"clear_errors",
		"clear_all_errors",
		"is_deleted",
		"is_dirty",
		"save",
		"update",
		"delete",
		"executeaction",
		"state",
		"template_url",
		"edit_embedded_url",
		"edit_standalone_url",
		"edit_url",
		"display_embedded_url",
		"display_standalone_url",
		"display_url",
		"send_mail",
		"fetch_child_records",
		"count_child_records",
		"fetch_child_recordpage",
	})
	ul4_type = ul4c.Type("la", "Record", "A record of a LivingApp application")

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
	attachments = Attr(get="", set="", ul4get="_attachments_get", ul4onget="_attachments_ul4onget", ul4onset="_attachments_set")
	details = AttrDictAttr(get=True, ul4get=True, ul4set=True, ul4onget=True, ul4onset=True)
	errors = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	fielderrors = AttrDictAttr(ul4onget="", ul4onset="")
	lookupdata = AttrDictAttr(ul4onget="", ul4onset="")
	custom = Attr(get=True, set=True, ul4get=True, ul4set=True)

	def __init__(self, id=None, app=None, createdat=None, createdby=None, updatedat=None, updatedby=None, updatecount=None):
		super().__init__()
		self.id = id
		self.app = app
		self.createdat = createdat
		self.createdby = createdby
		self.updatedat = updatedat
		self.updatedby = updatedby
		self.updatecount = updatecount
		self._sparse_values = attrdict()
		self._sparse_fielderrors = attrdict()
		self._sparse_lookupdata = attrdict()
		self._sparse_search_url = attrdict()
		self._sparse_search_param_name = attrdict()
		self._sparse_target_param_name = attrdict()
		self.__dict__["values"] = None
		self.__dict__["fields"] = None
		self.__dict__["details"] = None
		self.attachments = None
		self.errors = []
		self._new = True
		self._deleted = False

	@property
	def ul4onid(self) -> str:
		return self.id

	def __str__(self) -> str:
		return f"app={self.app or '?'}/record={self.id or '?'}"

	def ul4onload_end(self, decoder:ul4on.Decoder) -> None:
		self._new = False
		self._deleted = False

	def _make_fields(self, use_defaults, values, errors, lookupdata):
		fields = attrdict()
		for control in self.app.controls.values():
			identifier = control.identifier
			value = None
			if values is not None and identifier in values:
				value = values[identifier]
			elif use_defaults:
				value = control.default
			field = control.fieldtype(control, self, value)
			fields[identifier] = field
		self.__dict__["fields"] = fields
		self._sparse_values = None
		self._sparse_fielderrors = None
		self._sparse_lookupdata = None

	def _template_candidates(self):
		handler = self.app.globals._gethandler()
		yield handler.fetch_internaltemplates(self.app.id, "record_instance", None)
		yield handler.fetch_librarytemplates("record_instance")

	def _fields_get(self):
		if self.__dict__["fields"] is None:
			self._make_fields(False, self._sparse_values, self._sparse_fielderrors, self._sparse_lookupdata)
		return self.__dict__["fields"]

	def _values_get(self):
		values = self.__dict__["values"]
		if values is None:
			values = attrdict()
			for field in self.fields.values():
				values[field.control.identifier] = field.value
			self._sparse_values = None
			self.__dict__["values"] = values
		return values

	def _values_ul4onget(self):
		values = self._sparse_values
		if values is None:
			values = {field.control.identifier: field.value for field in self.fields.values() if not field.is_empty()}
		return values

	def _values_ul4onset(self, value):
		self._sparse_values = value
		# Set the following attributes via ``__dict__``, as they are "read only".
		self.__dict__["values"] = None
		self.__dict__["fields"] = None

	def _attachments_get(self):
		attachments = self._attachments
		if attachments is None and self.id is not None:
			handler = self.app.globals.handler
			if handler is not None:
				attachments = handler.record_attachments_incremental_data(self)
				if attachments is not None:
					attachments = attrdict(attachments)
					self._attachments = attachments
		return attachments

	def _attachments_set(self, value):
		self._attachments = value

	def _attachments_ul4onget(self):
		return self._attachments

	def _fielderrors_ul4onget(self):
		if self._sparse_fielderrors is not None:
			return self._sparse_fielderrors

		result = {field.control.identifier: field.errors for field in self.fields.values() if field.has_errors()}
		return result or None

	def _fielderrors_ul4onset(self, value):
		self._sparse_fielderrors = value
		# Set the following attributes via ``__dict__``, as they are "read only".
		self.__dict__["values"] = None
		self.__dict__["fields"] = None

	def _lookupdata_ul4onget(self):
		pass

	def _lookupdata_ul4onset(self, value):
		self._sparse_lookupdata = value
		# Set the following attributes via ``__dict__``, as they are "read only".
		self.__dict__["values"] = None
		self.__dict__["fields"] = None

	@property
	def children(self):
		return {k: v.records for (k, v) in self.details.items()}

	def _details_ul4onset(self, value):
		if value is not None:
			self.details = value

	@children.setter
	def children(self, value):
		pass # Ignore assignment, since this is now longer required

	def _state_get(self):
		if self._deleted:
			return State.DELETED
		elif self._new:
			return State.NEW
		elif self.is_dirty():
			return State.CHANGED
		else:
			return State.SAVED

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

	def __getattr__(self, name: str) -> Any:
		if name.startswith("v_"):
			identifier = name[2:]
			if identifier in self.fields:
				return self.fields[identifier].value
		elif name.startswith("f_"):
			identifier = name[2:]
			if identifier in self.fields:
				return self.fields[identifier]
		elif name.startswith("d_"):
			identifier = name[2:]
			if identifier in self.details:
				return self.details[identifier]
		elif name.startswith("c_"):
			identifier = name[2:]
			if identifier in self.details:
				return self.details[identifier].records
		else:
			return super().__getattr__(name)

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = super().__dir__()
		for identifier in self.app.controls:
			attrs.add(f"f_{identifier}")
			attrs.add(f"v_{identifier}")
		if self.details:
			for identifier in self.details:
				attrs.add(f"c_{identifier}")
				attrs.add(f"d_{identifier}")
		return attrs

	def ul4_dir(self):
		return dir(self)

	def ul4_hasattr(self, name: str) -> Any:
		if name.startswith(("f_", "v_")):
			return name[2:] in self.app.controls
		elif name.startswith(("c_", "d_")):
			return name[2:] in self.details
		elif name.startswith("x_") and name in self.__dict__:
			return True
		else:
			return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name.startswith(("f_", "v_", "c_", "d_", "t_")):
			return getattr(self, name)
		else:
			return super().ul4_getattr(name)

	def __setattr__(self, name: str, value: Any) -> None:
		if name.startswith("v_"):
			name = name[2:]
			if name in self.fields:
				self.fields[name].value = value
				return
			else:
				raise AttributeError(error_attribute_doesnt_exist(self, name)) from None
		elif name.startswith("c_"):
			name = name[2:]
			if name in self.details:
				self.details[name].records = value
				return
			else:
				raise AttributeError(error_attribute_doesnt_exist(self, name)) from None
		else:
			super().__setattr__(name, value)

	def ul4_setattr(self, name: str, value: Any) -> None:
		if name.startswith("x_"):
			setattr(self, name, value)
		elif name.startswith("v_") and name[2:] in self.app.controls:
			setattr(self, name, value)
			return
		elif name.startswith("c_"):
			setattr(self, name, value)
		elif name == "children":
			# Ignore assignment here
			return
		super().ul4_setattr(name, value)

	def _gethandler(self) -> Handler:
		if self.app is None:
			raise NoHandlerError()
		return self.app._gethandler()

	def save(self, force=False, sync=False):
		if self._deleted:
			return None
		handler = self._gethandler()
		if not force:
			self.check_errors()
		result = handler.save_record(self)
		if not force:
			self.check_errors()
		if sync:
			handler.ul4on_decoder.store_persistent_object(self)
			handler.record_sync_data(self.id, force=True)
		self._new = False
		return result

	def update(self, **kwargs):
		for (identifier, value) in kwargs.items():
			if identifier not in self.app.controls:
				raise TypeError(f"update() got an unexpected keyword argument {identifier!r}")
			self.fields[identifier].value = value
		self.save(force=True)

	def delete(self):
		self._gethandler().delete_record(self)

	def executeaction(self, identifier=None):
		self._gethandler()._executeaction(self, identifier)

	def ul4save(self, force=False, sync=False):
		return self.save(force=force, sync=sync)

	def template_url(self, identifier, /, **params):
		url = f"https://{self.app.globals.hostname}/gateway/apps/{self.app.id}/{self.id}?template={identifier}"
		return url_with_params(url, False, params)

	def edit_embedded_url(self, **params):
		url = f"https://{self.app.globals.hostname}/dateneingabe/{self.app.id}/{self.id}/edit"
		return url_with_params(url, True, params)

	def edit_standalone_url(self, **params):
		url = f"https://{self.app.globals.hostname}/gateway/apps/{self.app.id}/{self.id}/edit"
		return url_with_params(url, True, params)

	def edit_url(self, **params):
		if self.app.ownparams["la_default_form_variant"] == "standalone":
			return self.edit_standalone_url(**params)
		else:
			return self.edit_embedded_url(**params)

	def display_embedded_url(self, **params):
		url = f"https://{self.app.globals.hostname}/dateneingabe/{self.app.id}/{self.id}/display"
		return url_with_params(url, True, params)

	def display_standalone_url(self, **params):
		url = f"https://{self.app.globals.hostname}/gateway/apps/{self.app.id}/{self.id}/display"
		return url_with_params(url, True, params)

	def display_url(self, **params):
		if self.app.ownparams["la_default_form_variant"] == "standalone":
			return self.display_standalone_url(**params)
		else:
			return self.display_embedded_url(**params)

	def send_mail(self, from_: str | None = None, reply_to: str | None = None, to: str | None = None, cc: str | None = None, bcc: str | None = None, subject: str | None = None, body_text: str | None = None, body_html: str | None = None, attachments: la.File | None = None) -> None:
		self._gethandler().send_mail(
			globals=self.app.globals,
			app=self.app,
			record=self,
			from_=from_,
			reply_to=reply_to,
			to=to,
			cc=cc,
			bcc=bcc,
			subject=subject,
			body_text=body_text,
			body_html=body_html,
			attachments=attachments,
		)

	def _make_children_filter(self, filter:dict[App, list[str] | str]) -> dict[App, list[str]]:
		if self.id is None:
			# Record is unsaved, so it can not have children
			return {}

		if not isinstance(filter, dict):
			raise TypeError("`filter` must be a dict")

		new_filter = {}

		for control in self.app.child_controls.values():
			# Ignore ``MultipleAppLookupControl``s, since we don't know
			# how to handle them in the UI
			if control.app in filter and not isinstance(control, MultipleAppLookupControl):
				# We might have multiple controls in one app that point to us.
				# Create filter only once.
				if control.app not in new_filter:
					f = _make_filter(filter[control.app])[:]
					f.append(" or ".join(f"r.v_{c.identifier}.id == {self.id!r}" for c in control.app.controls.values() if isinstance(c, AppLookupControl) and c.lookupapp is self.app))
					new_filter[control.app] = f
		return new_filter

	def count_child_records(self, filter:dict[App, list[str] | str]) -> int:
		return self._gethandler().count_records_from_apps(
			globals=self.app.globals,
			filter=self._make_children_filter(filter),
			record=self,
		)

	def fetch_child_records(self, filter: dict[App, list[str] | str], sort:list[str] | str | None=None, offset:int | None = 0, limit: int | None=None) -> dict[str, Record]:
		return self._gethandler().fetch_records_from_apps(
			globals=self.app.globals,
			filter=self._make_children_filter(filter),
			sort=_make_sort(sort),
			offset=_make_offset(offset),
			limit=_make_limit(limit),
			record=self,
		)

	def fetch_child_recordpage(self, filter:dict[App, list[str] | str], sort:list[str] | str | None=None, offset:int | None=0, limit:int | None=None) -> RecordPage:
		return RecordChildrenRecordPage(
			self,
			filter,
			_make_sort(sort),
			_make_offset(offset),
			_make_limit(limit),
		)

	def has_errors(self):
		if self.errors:
			return True
		elif self._sparse_values is not None:
			# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't contain errors
			return False
		else:
			return any(field.has_errors() for field in self.fields.values())

	def has_errors_in_active_view(self):
		if self.errors:
			return True
		elif self._sparse_values is not None:
			# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't contain errors
			return False
		elif self.app.active_view is not None:
			for field in self.fields.values():
				if field.control.identifier in self.app.active_view.controls and field.has_errors():
					return True
		else:
			return False

	def add_error(self, *errors):
		self.errors.extend(errors)

	def clear_errors(self):
		self.errors = []

	def clear_all_errors(self):
		self.clear_errors()
		# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't contain errors
		if self._sparse_values is None:
			for field in self.fields.values():
				field.clear_errors()

	def check_errors(self):
		if self.errors:
			raise RecordValidationError(self, self.errors[0])
		# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't contain errors
		if self._sparse_values is None:
			for field in self.fields.values():
				field.check_errors()

	def is_dirty(self):
		if self.id is None:
			return True
		elif self._sparse_values is not None:
			# Shortcut: If we haven't constructed the :class:`Field` objects yet, they can't be dirty
			return False
		else:
			return any(field._dirty for field in self.fields.values())

	def is_deleted(self):
		return self._deleted

	def is_new(self):
		return self._new


@register("recordchildren")
class RecordChildren(Base):
	"""
	A :class:`RecordChildren` object the details records of a master record and
	references to the configuration defining this master/detail relation.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: record
		:type: Record

		The :class:`Record` these detail records belong to.

	.. attribute:: datasourcechildren
		:type: :class:`DataSourceChildren`

		The configuration that led to these detail records.

	.. attribute:: records
		:type: dict[str, Record]

		The detail records as a dictionary mapping record ids to
		:class:`Record` objects.
	.. attribute:: record_total
		:type: int

		The number of records in this object (if configured).

	.. attribute:: record_start
		:type: int

		The start index of records (when paging parameters are in use or vSQL
		expressions for paging are configured).

	.. attribute:: record_count
		:type: int

		The number of records per page (when paging parameters are in use or vSQL
		expressions for paging are configured).
	"""

	ul4_attrs = Base.ul4_attrs.union({"id", "record", "datasourcechildren", "records"})
	ul4_type = ul4c.Type("la", "RecordChildren", "The detail records for a master record")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	record = Attr(Record, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	datasourcechildren = Attr(lambda: DataSourceChildren, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	records = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	record_start = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	record_count = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	record_total = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	recordpage = Attr(lambda: RecordPage, get=True, ul4get=True)

	def __init__(self, id=None, record=None, datasourcechildren=None):
		self.id = id
		self.record = record
		self.datasourcechildren = datasourcechildren
		self.records = {}
		self.__dict__["recordpage"] = None
		self.record_start = None
		self.record_count = None
		self.record_total = None

	def __str__(self) -> str:
		return f"{self.record or '?'}/recordchildren={self.id}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	@property
	def ul4onid(self) -> str:
		return self.id

	def _gethandler(self) -> Handler:
		if self.record is None:
			raise NoHandlerError()
		return self.record._gethandler()

	def _recordpage_get(self):
		if self.__dict__["recordpage"] is None:
			rp = RecordChildrenRecordPage(self, filter=None, sort=None, offset=self.record_start, limit=self.record_count)
			rp._records = self.records
			rp._count = len(rp._records)
			rp._total = self.record_total
			self.__dict__["recordpage"] = rp
		return self.__dict__["recordpage"]


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

	ul4_attrs = Base.ul4_attrs.union({"id", "type", "record", "label", "active"})
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


class SimpleAttachment(Attachment):
	"""
	Base class for all :class:`Record` attachment that consist of a single value.
	"""

	ul4_attrs = Attachment.ul4_attrs.union({"value"})
	ul4_type = ul4c.Type("la", "SimpleAttachment", "A simple attachment of a record")

	value = Attr(repr=True, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

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

	value = Attr(File, repr=True, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


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

	value = Attr(str, repr=True, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


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

	value = Attr(str, repr=True, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


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

	value = Attr(repr=True, get=True, set=True, ul4get=True, ul4onget=True, ul4onset="")

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

	ul4_attrs = Base.ul4_attrs.union({"mimetype", "filename", "content"})
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


@register("recordpage")
class RecordPage(Base):
	"""
	A :class:RecordPage` object represents a subset of records retrieved from
	a database query, defined by a given limit and offset, along with the total
	number of matching records.

	Instance attributes are:

	.. attribute:: app
		:type: App

		The app to which the records belong.

	.. attribute:: filter
		:type: str

		The vSQL filter expression that the records match. Only records where
		this expression evaluated to true will be included in ``records``.

	.. attribute:: sort
		:type: :class:`list[str]`

		vSQL sort expressions. Each item in the list is a vSQL expression
		optionally followed by ``asc``/``desc`` and/or
		``nulls first``/``nulls last``. Records are sorted lexicographically
		by these expressions.

	.. attribute:: offset
		:type: int

		The index of the first record to return, i.e. the number of matching
		records (after applying ``filter`` and ``sort``) that are skipped before
		the first record in ``records``.

	.. attribute:: limit
		:type: int | None

		The maximum number of records to return, i.e. the upper bound on how many
		matching records (after applying ``filter`` and ``sort``) can appear in
		``records``.

	.. attribute:: records
		:type: dict[str, Record]

		The records as a dictionary mapping database iD to :class:`Record` objects.
		The dictioanry is sorted by the ``sort`` expr

	.. attribute:: count
		:type: int

		The number of records in this object (i.e. the length of ``records``.

	.. attribute:: total
		:type: int

		The total number of recors matching ``filter`` (i.e. then number of
		records that would have been return without ``limit`` and ``offset``.
	"""

	ul4_attrs = Base.ul4_attrs.union({"filter", "sort", "offset", "limit", "records", "count", "total"})
	ul4_type = ul4c.Type("la", "RecordPage", "A window of query results with pagination metadata (limit, offset, total count)")

	filter = Attr(list, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	sort = Attr(list, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	offset = Attr(int, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	limit = Attr(int, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	records = Attr(dict, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	count = Attr(int, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	total = Attr(int, get=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, filter: list[str], sort: list[str] | None=None, offset: int=0, limit: int | None=None):
		self.filter = filter
		self.sort = sort
		self.offset = offset or 0
		self.limit = limit
		self._records = None
		self._count = None
		self._total = None

	def __repr__(self) -> str:
		v = [f"<{self.__class__.__module__}.{self.__class__.__qualname__} filter={self.filter!r} sort={self.sort!r}"]
		if self.offset is not None:
			v.append(f" offset={self.offset}")
		if self.limit is not None:
			v.append(f" limit={self.limit}")
		if self._count is not None:
			v.append(f" count={self._count}")
		if self._total is not None:
			v.append(f" total={self._total}")
		v.append(f" at {id(self):#x}>")
		return "".join(v)

	@property
	def records(self) -> dict[str, Record]:
		if self._records is None:
			self._records = self._fetch_records()
		return self._records

	@property
	def count(self) -> int:
		if self._count is None:
			self._count = len(self.records)
		return self._count

	@property
	def total(self) -> int:
		if self._total is None:
			if self.offset > 0 or self.limit is not None:
				self._total = self._count_records()
			else:
				self._total = self.count
		return self._total

	@misc.notimplemented
	def _fetch_records(self) -> dict[str, Record]:
		pass

	@misc.notimplemented
	def _count_records(self) -> int:
		pass


class AppRecordPage(RecordPage):
	"""
	A subclass of :class:`RecordPage` where records have been fetched from an app.

	Relevant instance attributes are:

	.. attribute:: app
		:type: App

		The app to which the records belong.
	"""

	ul4_attrs = RecordPage.ul4_attrs.union({"app"})
	ul4_type = ul4c.Type("la", "AppRecordPage", "A window of query results fetched from an app with pagination metadata (limit, offset, total count)")

	app = Attr(App, get=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, app, filter, sort=None, offset=0, limit=None):
		super().__init__(filter=filter, sort=sort, offset=offset, limit=limit)
		self.app = app

	def _fetch_records(self) -> dict[str, Record]:
		return self.app.fetch_records(self.filter, self.sort, self.offset, self.limit)

	def _count_records(self) -> int:
		return self.app.count_records(self.filter)


class RecordChildrenRecordPage(RecordPage):
	"""
	A subclass of :class:`RecordPage` where records have an `applookup` field
	referencing a parent record.

	Relevant instance attributes are:

	.. attribute:: record
		:type: Record

		The parent record.
	"""

	ul4_attrs = RecordPage.ul4_attrs.union({"record"})
	ul4_type = ul4c.Type("la", "AppRecordPage", "A window of query results fetched from a record with pagination metadata (limit, offset, total count)")

	filter = Attr(dict, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	record = Attr(Record, get=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, record, filter, sort=None, offset=0, limit=None):
		super().__init__(filter=filter, sort=sort, offset=offset, limit=limit)
		self.record = record

	def _fetch_records(self) -> dict[str, Record]:
		return self.record.fetch_child_records(self.filter, self.sort, self.offset, self.limit)

	def _count_records(self) -> int:
		return self.record.count_child_records(self.filter)


class AppGroupRecordPage(RecordPage):
	"""
	A subclass of :class:`RecordPage` where records are fetched from an
	:class:`AppGroup`.

	Relevant instance attributes are:

	.. attribute:: appgroup
		:type: AppGroup

		The app group.
	"""

	ul4_attrs = RecordPage.ul4_attrs.union({"appgroup"})
	ul4_type = ul4c.Type("la", "AppGroupRecordPage", "A window of query results fetched from the apps of an app group with pagination metadata (limit, offset, total count)")

	filter = Attr(dict, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	appgroup = Attr(AppGroup, get=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, appgroup, filter, sort=None, offset=0, limit=None):
		super().__init__(filter=filter, sort=sort, offset=offset, limit=limit)
		self.appgroup = appgroup

	def _fetch_records(self) -> dict[str, Record]:
		return self.appgroup.fetch_records(self.filter, self.sort, self.offset, self.limit)

	def _count_records(self) -> int:
		return self.appgroup.count_records(self.filter)


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

	def template(self) -> ul4.Template:
		return ul4c.Template(self.source, name=self.identifier, signature=self.signature, whitespace=self.whitespace)

	def _gethandler(self) -> Handler:
		if self.app is None:
			raise NoHandlerError()
		return self.app._gethandler()

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

	def __str__(self) -> str:
		return f"{self.app or '?'}/internaltemplate={self.identifier}"

	def save_meta(self, recursive=True):
		self._gethandler().save_internaltemplate(self)

	def delete_meta(self):
		self._gethandler().delete_internaltemplate(self)


@register("viewtemplateconfig")
class ViewTemplateConfig(Template):
	"""
	A :class:`!ViewTemplateConfig` provides a webpage.

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

	ul4_type = ul4c.Type("la", "ViewTemplateConfig", "A view template")

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

		``LISTDATAMANAGEMENT``
			This is similar to ``LIST``, but a link to this view template will be
			available in the datamanagement and the menu.

		``DETAIL``
			The template is supposed to display the details of a single record. The
			URL looks like this::

				/gateway/apps/1234567890abcdef12345678/abcdefabcdefabcdefabcdef?template=foo

			(with ``abcdefabcdefabcdefabcdef`` being the id of the record)

		``DETAILRESULT``
			This is similar to ``DETAIL``, but is used to replace the standard display
			if a record is created or updated via the standard form.

		``DETAILDATAMANAGEMENT``
			This is similar to ``DETAIL``, but a link to this view template will be
			available for each record in the datamanagement.

		``SUPPORT``
			The template is supposed to be independant of any record. This can be
			used for delivering static CSS or similar stuff. The URL looks the same
			as for the type ``LIST``.
		"""

		LIST = "list"
		LISTDEFAULT = "listdefault"
		LISTDATAMANAGEMENT = "listdatamanagement"
		DETAIL = "detail"
		DETAILRESULT = "detailresult"
		DETAILDATAMANAGEMENT = "detaildatamanagement"
		SUPPORT = "support"

	class Permission(misc.IntEnum):
		ALL = 0
		LOGGEDIN = 1
		APP = 2
		APPEDIT = 3
		APPADMIN = 4

	type = EnumAttr(Type, get=True, set=True, required=True, default=Type.LIST, ul4get=True, ul4onget=True, ul4onset=True)
	mimetype = Attr(str, get=True, set=True, default="text/html", ul4get=True, ul4onget=True, ul4onset=True)
	permission_level = IntEnumAttr(Permission, get=True, set=True, required=True, ul4get=True, default=Permission.ALL, ul4onget=True, ul4onset=True)
	datasources = AttrDictAttr(get=True, set=True, required=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, *args, id=None, identifier=None, source=None, whitespace="keep", signature=None, doc=None, type=Type.LIST, mimetype="text/html", permission_level=None):
		super().__init__(id=id, identifier=identifier, source=source, whitespace=whitespace, signature=signature, doc=doc)
		self.type = type
		self.mimetype = mimetype
		self.permission_level = permission_level
		self.datasources = attrdict()
		for arg in args:
			if isinstance(arg, DataSourceConfig):
				self.adddatasource(arg)
			else:
				raise TypeError(f"don't know what to do with positional argument {arg!r}")

	def __str__(self) -> str:
		return f"{self.app or '?'}/viewtemplate={self.identifier}"

	def adddatasource(self, *datasources):
		for datasource in datasources:
			datasource.parent = self
			self.datasources[datasource.identifier] = datasource
		return self

	def save_meta(self, recursive=True):
		self._gethandler().save_viewtemplate(self)

	def delete_meta(self):
		self._gethandler().delete_viewtemplate(self)


@register("viewtemplateinfo")
class ViewTemplateInfo(CustomAttributes):
	"""
	A :class:`!ViewTemplateInfo` provides data of a view template.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		The database primary key of this view template.

	.. attribute:: app
		:type: App

		The app this view template belongs to.

	.. attribute:: identifier
		:type: str

		The database primary key of this view template.

	.. attribute:: name
		:type: str

		The name of this view template.

	.. attribute:: icon
		:type: str

		The icon of this view template.

	.. attribute:: type
		:type: Type

		The type of the view template (i.e. in which context it is used)

	.. attribute:: mimetype
		:type: str

		The MIME type of the HTTP response of the view template

	.. attribute:: permission_level
		:type: Permission

		Who can access the template?
	"""

	ul4_type = ul4c.Type("la", "ViewTemplateInfo", "A view template info object")

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

		``LISTDATAMANAGEMENT``
			This is similar to ``LIST``, but a link to this view template will be
			available in the datamanagement and the menu.

		``DETAIL``
			The template is supposed to display the details of a single record. The
			URL looks like this::

				/gateway/apps/1234567890abcdef12345678/abcdefabcdefabcdefabcdef?template=foo

			(with ``abcdefabcdefabcdefabcdef`` being the id of the record)

		``DETAILRESULT``
			This is similar to ``DETAIL``, but is used to replace the standard display
			if a record is created or updated via the standard form.

		``DETAILDATAMANAGEMENT``
			This is similar to ``DETAIL``, but a link to this view template will be
			available for each record in the datamanagement.

		``SUPPORT``
			The template is supposed to be independant of any record. This can be
			used for delivering static CSS or similar stuff. The URL looks the same
			as for the type ``LIST``.
		"""

		LIST = "list"
		LISTDEFAULT = "listdefault"
		LISTDATAMANAGEMENT = "listdatamanagement"
		DETAIL = "detail"
		DETAILRESULT = "detailresult"
		DETAILDATAMANAGEMENT = "detaildatamanagement"
		SUPPORT = "support"

	class Permission(misc.IntEnum):
		ALL = 0
		LOGGEDIN = 1
		APP = 2
		APPEDIT = 3
		APPADMIN = 4

	app = Attr(App, get=True, set=True, default=None, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, default=None, ul4get=True, ul4onget=True, ul4onset=True, repr=True)
	name = Attr(str, get=True, set=True, default=None, ul4get=True, ul4onget=True, ul4onset=True)
	icon = Attr(str, get=True, set=True, default=None, ul4get=True, ul4onget=True, ul4onset=True)
	type = EnumAttr(Type, get=True, set=True, required=True, default=Type.LIST, ul4get=True, ul4onget=True, ul4onset=True, repr=True)
	mimetype = Attr(str, get=True, set=True, default="text/html", ul4get=True, ul4onget=True, ul4onset=True, repr=True)
	permission_level = IntEnumAttr(Permission, get=True, set=True, required=True, ul4get=True, default=Permission.ALL, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, app=None, identifier=None, name=None, icon=None, type=Type.LIST, mimetype="text/html", permission_level=None):
		super().__init__()
		self.id = id
		self.app = app
		self.identifier = identifier
		self.name = name
		self.icon = icon
		self.type = type
		self.mimetype = mimetype
		self.permission_level = permission_level

	@property
	def ul4onid(self) -> str:
		return self.id

	def __str__(self) -> str:
		return f"{self.app or '?'}/viewtemplate={self.identifier}"


@register("datasourceconfig")
class DataSourceConfig(Base):
	"""
	A :class:`DataSourceConfig` contains the configuration to provide information about
	one (or more) apps and their records to a :class:`ViewTemplateConfig` or other
	templates.

	The resulting information will be a :class:`DataSource` object.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: parent
		:type: ViewTemplateConfig

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
		:type: dict[str, DataSourceChildrenConfig]

		Children configuration for records that reference the record from this app.
	"""

	ul4_attrs = Base.ul4_attrs.union({"id", "parent", "identifier", "app", "includecloned", "appfilter", "includecontrols", "includerecords", "includecount", "recordpermission", "recordfilter", "includepermissions", "includeattachments", "includeparams", "includeviews", "includecategories", "orders", "children"})
	ul4_type = ul4c.Type("la", "DataSourceConfig", "A data source for a view, email or form template")

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

		``ALL_LAYOUT``
			Include all controls and layout controls.
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
	parent = Attr(ViewTemplateConfig, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
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

	def __str__(self) -> str:
		return f"{self.parent or '?'}/datasource={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	@property
	def ul4onid(self) -> str:
		return self.id

	def add(self, *items:DataOrder | DataSourceChildrenConfig) -> Self:
		for item in items:
			if isinstance(item, DataOrder):
				item.parent = self
				self.orders.append(item)
			elif isinstance(item, DataSourceChildrenConfig):
				item.datasource = self
				self.children[item.identifier] = item
			else:
				raise TypeError(f"don't know what to do with positional argument {item!r}")
		return self

	def _gethandler(self) -> Handler:
		if self.parent is None:
			raise NoHandlerError()
		return self.parent._gethandler()

	def save_meta(self, recursive=True):
		self._gethandler().save_datasourceconfig(self)


@register("datasourcechildrenconfig")
class DataSourceChildrenConfig(Base):
	"""
	A :class:`DataSourceChildrenConfig` object contains the configuration for
	attachment detail records to a master record.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: datasource
		:type: DataSourceConfig

		The :class:`DataSourceConfig` this object belongs to.

	.. attribute:: identifier
		:type: str

		A unique identifier for this object (unique among the other
		:class:`DataSourceChildrenConfig` objects of the :class:`DataSourceConfig`).

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

	ul4_attrs = Base.ul4_attrs.union({"id", "datasource", "identifier", "control", "filters", "orders"})
	ul4_type = ul4c.Type("la", "DataSourceChildrenConfig", "A master/detail specification in a datasource")

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

	def __str__(self) -> str:
		return f"{self.datasource or '?'}/datasourcechildrenconfig={self.identifier}"

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

	def _gethandler(self) -> Handler:
		if self.datasource is None:
			raise NoHandlerError()
		return self.datasource._gethandler()

	def save_meta(self, recursive=True):
		self._gethandler().save_datasourcechildrenconfig(self)


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
		:type: DataSourceConfig | DataSourceChildrenConfig

		The :class:`DataSourceConfig` or :class:`DataSourceChildrenConfig` this object
		belongs to

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

	ul4_attrs = Base.ul4_attrs.union({"id", "parent", "expression", "direction", "nulls"})
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
	parent = Attr(DataSourceConfig, DataSourceChildrenConfig, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	expression = VSQLAttr("?", get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	direction = EnumAttr(Direction, get=True, set=True, required=True, default=Direction.ASC, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	nulls = EnumAttr(Nulls, get=True, set=True, required=True, default=Nulls.LAST, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, expression=None, direction=Direction.ASC, nulls=Nulls.LAST):
		self.id = id
		self.parent = None
		self.expression = expression
		self.direction = direction
		self.nulls = nulls

	def __str__(self) -> str:
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

	def save_meta(self, handler:T_opt_handler=None, recursive:bool=True):
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

	ul4_attrs = Base.ul4_attrs.union({
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
	})
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


# We don't have to register this class, since only subclasses will be put into
# UL4ON dumps
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
		:type: DataAction | DataActionCommand

		The data action this command belongs to or the command this comamnd is a
		sub command of.

	.. attribute:: condition
		:type: str

		Only execute the command when this vSQL condition is true.

	.. attribute:: details
		:type: list[DataActionDetail]

		Field expressions for each field of the target app or parameter of the command.
	"""

	ul4_attrs = Base.ul4_attrs.union({
		"id",
		"parent",
		"condition",
		"details",
	})
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
		super().__init__(id=id, condition=condition)
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

	ul4_attrs = Base.ul4_attrs.union({
		"id",
		"parent",
		"control",
		"type",
		"children",
	})
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

	def _code_get(self) -> str:
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

	ul4_attrs = Base.ul4_attrs.union({"id", "name"})
	ul4_type = ul4c.Type("la", "Installation", "The installation that created a LivingApp")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, name=None):
		self.id = id
		self.name = name

	@property
	def ul4onid(self) -> str:
		return self.id

	vsqlgroup = vsql.Group(
		"installation_link",
		internalid=(vsql.DataType.STR, "upl_id"),
		id=(vsql.DataType.STR, "inl_id"),
		name=(vsql.DataType.STR, "inl_additional_name"),
	)


class LayoutControl(CustomAttributes):
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

	_type = None
	_subtype = None

	ul4_attrs = CustomAttributes.ul4_attrs.union({"id", "label", "identifier", "view", "type", "subtype", "fulltype", "top", "left", "width", "height", "z_index", "visible"})
	ul4_type = ul4c.Type("la", "LayoutControl", "A decoration in an input form")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	label = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	type = Attr(str, get="", ul4get="_type_get")
	subtype = Attr(str, get="", ul4get="_subtype_get")
	fulltype = Attr(str, get="", ul4get="_fulltype_get")
	view = Attr(lambda: View, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	top = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	left = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	z_index = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	visible = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, label=None, identifier=None):
		super().__init__()
		self.id = id
		self.label = label
		self.identifier = identifier
		self.visible = True
		self.view = None
		self.top = None
		self.left = None
		self.width = None
		self.height = None
		self.z_index = None
		self.visible = True

	def _template_candidates(self):
		handler = self.view.app.globals._gethandler()
		app_id = self.view.app.id
		yield handler.fetch_internaltemplates(app_id, f"layoutcontrol_{self.type}_instance", None)
		yield handler.fetch_internaltemplates(app_id, f"layoutcontrol_instance", None)
		yield handler.fetch_librarytemplates(f"layoutcontrol_{self.type}_instance")
		yield handler.fetch_librarytemplates("layoutcontrol_instance")

	@property
	def ul4onid(self) -> str:
		return self.id

	def _type_get(self):
		return self._type

	def _subtype_get(self):
		return self._subtype

	def _fulltype_get(self):
		return self._fulltype


@register("htmllayoutcontrol")
class HTMLLayoutControl(LayoutControl):
	"""
	A :class:`!HTMLLayoutControl` provides HTML "decoration" in an input form.

	Relevant instance attributes are:

	.. attribute:: value
		:type: str

		HTML source
	"""

	_type = "string"
	_subtype = "html"
	_fulltype = f"{_type}/{_subtype}"

	ul4_attrs = LayoutControl.ul4_attrs.union({"value"})
	ul4_type = ul4c.Type("la", "HTMLLayoutControl", "HTML decoration in an input form")

	value = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("imagelayoutcontrol")
class ImageLayoutControl(LayoutControl):
	"""
	An :class:`!ImageLayoutControl` provides an image as decoration for an input form.

	Relevant instance attributes are:

	.. attribute:: image_original
		:type: File

		Original uploaded image

	.. attribute:: image_scaled
		:type: File

		Image scaled to final size
	"""

	_type = "image"
	_fulltype = _type

	ul4_attrs = LayoutControl.ul4_attrs.union({"image"})
	ul4_type = ul4c.Type("la", "ImageLayoutControl", "An image decoration in an input form")

	image = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)


@register("buttonlayoutcontrol")
class ButtonLayoutControl(LayoutControl):
	"""
	A :class:`!ButtonLayoutControl` describes a submit button in an input form.
	"""

	_type = "button"
	_fulltype = _type

	ul4_type = ul4c.Type("la", "ButtonLayoutControl", "A submit button in an input form")


@register("view")
class View(CustomAttributes):
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

	.. attribute:: login_required
		:type: bool

		If true the user mut be logged in to be able to fill out the form.

	.. attribute:: result_page
		:type: bool

		If true the content of the standard result page will be replaced with
		the output of a view template.

	.. attribute:: use_geo
		:type: View.UseGeo

		Should the input form use the geo location of the user?

	.. attribute:: focus_control
		:type: Control

		Which control to focus in the form
	"""

	ul4_attrs = CustomAttributes.ul4_attrs.union({"id", "name", "combined_type", "app", "order", "width", "height", "start", "end", "lang", "login_required", "result_page", "use_geo", "controls", "layout_controls", "focus_control", "focus_first_control"})
	ul4_type = ul4c.Type("la", "View", "An input form for a LivingApps application")

	class CombinedType(misc.Enum):
		"""
		If this is a combined view, the type of the combined view.
		"""

		TABS = "tabs"
		WIZARD = "wizard"

	class UseGeo(misc.Enum):
		"""
		Use geo location in the input form?
		"""

		NO = "no"
		ONCE = "once"
		WATCH = "watch"

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
	layout_controls = Attr(get="", set="", ul4get="_layout_controls_get", ul4onget="_layout_controls_ul4onget", ul4onset="_layout_controls_set")
	lang = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	login_required = BoolAttr(get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	result_page = BoolAttr(get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset="")
	use_geo = EnumAttr(UseGeo, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	focus_control = Attr(Control, get=True, set="", ul4get=True, ul4set="_focus_control_set")

	def __init__(self, id=None, name=None, app=None, order=None, width=None, height=None, start=None, end=None, lang=None, login_required=False, result_page=True, use_geo="no"):
		super().__init__()
		self.id = id
		self.name = name
		self.combined_type = None
		self.app = app
		self.order = order
		self.width = width
		self.height = height
		self.start = start
		self.end = end
		self._layout_controls = None
		self.lang = lang
		self.login_required = login_required
		self.result_page = result_page
		self.use_geo = use_geo
		self.__dict__["focus_control"] = None

	@property
	def ul4onid(self) -> str:
		return self.id

	def _result_page_ul4onset(self, value):
		self.use_use = not value

	def _focus_control_set(self, control):
		if control is not None:
			if not isinstance(control, Control):
				raise TypeError(f"focus_control must be be a Control not {misc.format_class(control)}")
			if control.app is not self.app:
				raise ValueError(error_foreign_control(control))
			if control.identifier not in self.controls:
				raise ValueError(error_control_not_in_view(control, self))
		self.__dict__["focus_control"] = control

	def focus_first_control(self):
		first_view_control = min((c for c in self.controls.values() if c.tabindex is not None), key=operator.attrgetter("tabindex"))
		if first_view_control is not None:
			self.focus_control = first_view_control.control

	def __getattr__(self, name: str) -> Any:
		if name.startswith("c_"):
			identifier = name[2:]
			if identifier in self.controls:
				return self.controls[identifier]
		elif name.startswith("lc_"):
			identifier = name[3:]
			if identifier in self.layout_controls:
				return self.layout_controls[identifier]
		else:
			return super().__getattr__(name)

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = super().__dir__()
		for identifier in self.controls:
			attrs.add(f"c_{identifier}")
		for identifier in self.layout_controls:
			attrs.add(f"lc_{identifier}")
		return attrs

	def ul4_hasattr(self, name: str) -> Any:
		if name.startswith("c_") and name[2:] in self.controls:
			return True
		elif name.startswith("lc_") and name[3:] in self.layout_controls:
			return True
		else:
			return super().ul4_hasattr(name)

	def _layout_controls_get(self):
		layout_controls = self._layout_controls
		if layout_controls is None:
			handler = self.app.globals.handler
			if handler is not None:
				layout_controls = self._layout_controls = handler.view_layout_controls_incremental_data(self)
		return layout_controls

	def _layout_controls_set(self, value):
		self._layout_controls = value

	def _layout_controls_ul4onget(self):
		return self._layout_controls


@register("datasource")
class DataSource(Base):
	"""
	A :class:`!DataSource` object provides information about one (or more)
	apps and their records to a :class:`ViewTemplate` or other templates.

	This information is configured by :class:`DataSourceConfig` objects.

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

	.. attribute:: children
		:type: list[DataSourceChildren]

		The configurations for detail records of records in this data source.

	.. attribute:: filter
		:type: str | None

		vSQL filter expression. Only records where this expression evaluated to
		true will be included in ``app.records``.

	.. attribute:: sort
		:type: list[str]

		vSQL sort expressions. Each item in the list is a vSQL expression
		optionally followed by ``asc``/``desc`` and/or
		``nulls first``/``nulls last``. Records are sorted lexicographically
		by these expressions.
	"""

	ul4_attrs = Base.ul4_attrs.union({"id", "identifier", "app", "apps", "children"})
	ul4_type = ul4c.Type("la", "DataSource", "The data resulting from a data source configuration")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	apps = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	children = Attr(get=True, ul4get=True, ul4onget=True, ul4onset=True)
	filter = Attr(str, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	sort = Attr(get=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id:str=None, identifier:str=None, app:App | None=None, apps:dict[str, App]=None):
		self.id = id
		self.identifier = identifier
		self.app = app
		self.apps = apps
		self.children = []
		self.filter = None
		self.sort = []

	@property
	def ul4onid(self) -> str:
		return self.id

	def __str__(self) -> str:
		return f"datasource={self.identifier}"


@register("externaldatasource")
class ExternalDataSource(Base):
	"""
	An :class:`!ExternalDataSource` object contains information about an
	external datasource, which is an URL that provides additional data to a
	view template. This data can either be text or JSON.

	Relevant instance attribytes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: identifier
		:type: str

		A unique identifier for the external data source

	.. attribute:: description
		:type: Optional[str]

		A description of the external data source.

	.. attribute:: url
		:type: str

		The URL from which external data will be fetched.

	.. attribute:: data
		:type: Any

		The data that has been fetched from the external data source.
	"""

	ul4_attrs = Base.ul4_attrs.union({"id", "identifier", "description", "url", "data"})
	ul4_type = ul4c.Type("la", "ExternalDataSource", "The configuration of and the data resulting from an external data source")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	url = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	data = Attr(get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id:str=None, identifier:str=None, description:str | None=None, url:str=None):
		self.id = id
		self.identifier = identifier
		self.description = description
		self.url = url
		self.data = None

	@property
	def ul4onid(self) -> str:
		return self.id


@register("datasourcechildren")
class DataSourceChildren(Base):
	"""
	A :class:`DataSourceChildren` object contains information about detail records
	for a master record that is available during a running view, form or email templates.

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
		:type: list[str] | None

		vSQL filter expression. Only records where this expression evaluated to
		true will be included in ``app.records``.

	.. attribute:: sort
		:type: list[str]

		vSQL sort expressions. Each item in the list is a vSQL expression
		optionally followed by ``asc``/``desc`` and/or
		``nulls first``/``nulls last``. Records are sorted lexicographically
		by these expressions.
	"""

	ul4_attrs = Base.ul4_attrs.union({"id", "datasource", "identifier", "control"})
	ul4_type = ul4c.Type("la", "DataSourceChildren", "A master/detail specification in a datasource")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	datasource = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	control = Attr(Control, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	filter = Attr(list, get=True, ul4get=True, ul4onget=True, ul4onset=True)
	sort = Attr(get=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, identifier=None, control=None):
		self.id = id
		self.datasource = None
		self.identifier = identifier
		self.control = control
		self.filter = []
		self.sort = []

	def __str__(self) -> str:
		return f"{self.datasource or '?'}/datasourcechildren={self.identifier}"

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} path={str(self)!r} at {id(self):#x}>"

	@property
	def ul4onid(self) -> str:
		return self.id

	def _gethandler(self) -> Handler:
		if self.datasource is None:
			raise NoHandlerError()
		return self.datasource._gethandler()


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

	ul4_attrs = Base.ul4_attrs.union({"id", "control", "key", "label", "visible"})
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

	def _get_viewlookupitem(self) -> ViewLookupItem | None:
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

	def _label_set(self, label:str | None) -> None:
		self._label = label

	def _label_ul4ondefault(self) -> None:
		self._label = None

	def _visible_get(self) -> bool:
		viewlookupitem = self._get_viewlookupitem()
		if viewlookupitem is None:
			return True
		return viewlookupitem.visible

	def _visible_repr(self) -> str | None:
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

	ul4_attrs = Base.ul4_attrs.union({"id", "key", "label", "visible"})
	ul4_type = ul4c.Type("la", "ViewLookupItem", "View specific information about a lookup item")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	key = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	visible = BoolAttr(get=True, set=True, repr="", ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id:str=None, key:str=None, label:str=None, visible:bool=None):
		self.id = id
		self.key = key
		self.label = label
		self.visible = visible

	def _visible_repr(self) -> str | None:
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

	ul4_attrs = Base.ul4_attrs.union({"id", "identifier", "name", "order", "parent", "children", "apps"})
	ul4_type = ul4c.Type("la", "Category", "A navigation category")

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	name = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	parent = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	children = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	apps = Attr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id:str=None, identifier:str=None, name:str=None, order:int=None, parent:Optional["Category"]=None, children:Optional[List["Category"]]=None, apps:Optional[dict[str, App]]=None):
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
class AppParameter(CustomAttributes):
	r"""
	An parameter for an app, app group or the library.

	This class provides objects that can not be changed by UL4 templates, and
	are therefore used for the library parameters. The mutable subclass
	:class:`MutableAppParameter` is used for parameters attached to apps or
	app group. This can e.g. be used to provide a simple way to configure
	the behaviour of :class:`ViewTemplate`\s.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id.

	.. attribute:: app
		:type: App

		The app this parameter belong to.

	.. attribute:: appgroup
		:type: AppGroup

		The app group this parameter belong to.

	.. attribute:: owner
		:type: App

		The app this parameter belong to.

	.. attribute:: parent
		:type: Optional[AppParameter]

		If this is a :class:`!AppParameter` object inside another
		:class:`!AppParameter` object of type ``list`` or ``dict``, ``parent``
		references this parent object.

	.. attribute:: order
		:type: Optional[int]

		Numeric value used to order the items in an :class:`!AppParameter` object
		of type ``list``.

	.. attribute:: identifier
		:type: Optional[str]

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
		:class:`File`, :class:`App`, :class:`Control`, :class:`list`,
		:class:`dict` (and ``None``).

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

	ul4_attrs = CustomAttributes.ul4_attrs.union({"id", "app", "appgroup", "parent", "type", "order", "identifier", "description", "value", "createdat", "createdby", "updatedat", "updatedby", "state"})
	ul4_type = ul4c.Type("la", "AppParameter", "A parameter of a LivingApps application, app group or library")

	class Type(misc.Enum):
		"""
		The type of a parameter. Possible values are:

		*	``BOOL``
		*	``INT``
		*	``NUMBER``
		*	``STR``
		*	``HTML``
		*	``COLOR``
		*	``DATE``
		*	``DATETIME``
		*	``DATEDELTA``
		*	``DATETIMEDELTA``
		*	``MONTHDELTA``
		*	``UPLOAD``
		*	``APP``
		*	``CONTROL``
		*	``LIST``
		*	``DICT``
		"""

		BOOL = "bool"
		INT = "int"
		NUMBER = "number"
		STRING = "string"
		HTML = "html"
		COLOR = "color"
		DATE = "date"
		DATETIME = "datetime"
		DATEDELTA = "datedelta"
		DATETIMEDELTA = "datetimedelta"
		MONTHDELTA = "monthdelta"
		UPLOAD = "upload"
		APP = "app"
		CONTROL = "control"
		LIST = "list"
		DICT = "dict"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	appgroup = Attr(AppGroup, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	parent = Attr(lambda: AppParameter, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	type = EnumAttr(Type, get=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	order = Attr(int, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	value = Attr(get=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, parent=None, app=None, appgroup=None, type=None, order=None, identifier=None, description=None, value=None):
		super().__init__()
		self.id = id
		self._globals = None
		self.app = app
		self.appgroup = appgroup
		self.parent = parent
		self.order = order
		self.identifier = identifier
		self.description = description
		self.createdat = None
		self.createdby = None
		self.updatedat = None
		self.updatedby = None
		self._new = True
		self._deleted = False
		self._dirty = True
		self.__dict__["type"] = type
		self.__dict__["value"] = value

	@property
	def ul4onid(self) -> str:
		return self.id

	@property
	def globals(self) -> Globals:
		if self.app is not None:
			return self.app.globals
		elif self.appgroup is not None:
			return self.appgroup.globals
		else:
			return self._globals

	def _template_candidates(self):
		globals = self.globals
		handler = globals._gethandler()

		app = self.app if self.app is not None else globals.app
		yield handler.fetch_internaltemplates(app.id, f"parameter_{self.type.value}_instance", None)
		yield handler.fetch_internaltemplates(app.id, "parameter_instance", None)
		yield handler.fetch_librarytemplates(f"parameter_{self.type.value}_instance")
		yield handler.fetch_librarytemplates("parameter_instance")


@register("mutableappparameter")
class MutableAppParameter(AppParameter):
	r"""
	A modifiable parameter for an app.

	Instances of this class can be changed by UL4 templates.
	"""

	ul4_attrs = AppParameter.ul4_attrs.union({"state", "save", "delete"})
	ul4_type = ul4c.Type("la", "MutableAppParameter", "A mutable parameter of a LivingApps application")

	state = EnumAttr(State, get="", required=True, repr=True, ul4get="")
	type = EnumAttr(AppParameter.Type, get=True, set="", repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	value = Attr(get=True, set="", ul4get=True, ul4set="_value_set", ul4onget=True, ul4onset=True)

	def __init__(self, id=None, app=None, appgroup=None, parent=None, type=None, order=None, identifier=None, description=None, value=None):
		super().__init__(id=id, app=app, appgroup=appgroup, parent=parent, type=type, order=order, identifier=identifier, description=description, value=value)
		self._new = True
		self._deleted = False
		self._dirty = True
		if type is not None:
			self.type = type
			if value is not None:
				self.value = value
		elif value is not None:
			self.value = value

	def ul4onload_end(self, decoder:ul4on.Decoder) -> None:
		self._new = False
		self._deleted = False
		self._dirty = False

	def ul4_hasattr(self, name: str) -> Any:
		if name == "append_param" and self.type is self.Type.LIST:
			return True
		elif name == "add_param" and self.type is self.Type.DICT:
			return True
		return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name == "append_param" and self.type is self.Type.LIST:
			return self.append_param
		elif name == "add_param" and self.type is self.Type.DICT:
			return self.add_param
		return super().ul4_getattr(name)

	def _state_get(self):
		if self._deleted:
			return State.DELETED
		elif self._new:
			return State.NEW
		elif self.is_dirty():
			return State.CHANGED
		else:
			return State.SAVED

	def _state_ul4get(self):
		return self._state_get().name

	def _type_set(self, type):
		if self.__dict__.get("type", None) is not type:
			if isinstance(type, str):
				type = self.Type(type)
			self.__dict__["type"] = type
			self._dirty = True
			if self.value is not None:
				if type is self.Type.BOOL:
					if not isinstance(self.value, bool):
						self.value = None
				elif type is self.Type.INT:
					if not isinstance(self.value, int):
						self.value = None
				elif type is self.Type.NUMBER:
					if not isinstance(self.value, (int, float)):
						self.value = None
				elif type is self.Type.STRING or type is self.Type.HTML:
					if not isinstance(self.value, str):
						self.value = None
				elif type is self.Type.COLOR:
					if not isinstance(self.value, color.Color):
						self.value = None
				elif type is self.Type.DATE:
					if isinstance(self.value, datetime.datetime):
						self.value = self.value.date()
					elif not isinstance(self.value, datetime.date):
						self.value = None
				elif type is self.Type.DATETIME:
					if isinstance(self.value, datetime.date) and not isinstance(self.value, datetime.datetime):
						self.value = datetime.datetime(self.value.year, self.value.month, self.value.day)
					else:
						self.value = None
				elif type is self.Type.DATEDELTA:
					if isinstance(self.value, datetime.timedelta):
						if self.value.seconds or self.value.microseconds:
							self.value = datetime.timedelta(self.value.days)
					else:
						self.value = None
				elif type is self.Type.DATETIMEDELTA:
					if not isinstance(self.value, datetime.timedelta):
						self.value = None
				elif type is self.Type.MONTHDELTA:
					if not isinstance(self.value, misc.monthdelta):
						self.value = None
				elif type is self.Type.UPLOAD:
					if not isinstance(self.value, File):
						self.value = None
				elif type is self.Type.APP:
					if not isinstance(self.value, App):
						self.value = None
				elif type is self.Type.CONTROL:
					if not isinstance(self.value, Control):
						self.value = None
				else:
					self.value = None

	def _value_set(self, value):
		oldvalue = self.__dict__.get("value", None)
		if value is None:
			if oldvalue is not None:
				# If the value is ``None``, we can keep the type
				self.__dict__["value"] = None
				self._dirty = True
		elif isinstance(value, bool):
			if self.type is not self.Type.BOOL or oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.BOOL
				self._dirty = True
		elif isinstance(value, int):
			if self.type is not self.Type.INT or oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.INT
				self._dirty = True
		elif isinstance(value, float):
			if self.type is not self.Type.NUMBER or oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.NUMBER
				self._dirty = True
		elif isinstance(value, str):
			if oldvalue != value:
				self.__dict__["value"] = value
				if self.type is not self.Type.HTML:
					self.__dict__["type"] = self.Type.STRING
				self._dirty = True
		elif isinstance(value, color.Color):
			if oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.COLOR
				self._dirty = True
		elif isinstance(value, datetime.datetime):
			if oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.DATETIME
				self._dirty = True
		elif isinstance(value, datetime.date):
			if oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.DATE
				self._dirty = True
		elif isinstance(value, datetime.timedelta):
			if oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.DATETIMEDELTA if value.seconds or value.microseconds else self.Type.DATEDELTA
				self._dirty = True
		elif isinstance(value, misc.monthdelta):
			if oldvalue != value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.MONTHDELTA
				self._dirty = True
		elif isinstance(value, File):
			if oldvalue is not value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.UPLOAD
				self._dirty = True
		elif isinstance(value, App):
			if oldvalue is not value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.APP
				self._dirty = True
		elif isinstance(value, Control):
			if oldvalue is not value:
				self.__dict__["value"] = value
				self.__dict__["type"] = self.Type.CONTROL
				self._dirty = True
		else:
			raise TypeError(f"Type {type(value)} not supported for app parameters")

	def _gethandler(self) -> Handler:
		globals = self.globals
		if globals is None:
			raise NoHandlerError()
		return globals._gethandler()

	def save(self, sync=False):
		handler = self._gethandler()
		handler.save_parameter(self)
		if sync:
			handler.parameter_sync_data(self.id)
		return True

	def delete(self):
		self._gethandler().delete_parameter(self)

	def append_param(self, *, type=None, description=None, value=None):
		if self.type is not self.Type.LIST:
			raise TypeError(f"Can't append parameter to parameter of type {self.type}")
		if self.value is None:
			self.__dict__["value"] = []
		if type is None and value is None:
			raise ValueError("one of type or value must not be None")
		param = AppParameter(parent=self, owner=self.owner, type=type, order=self.value[-1].order+10 if self.value else 10, description=description, value=value)
		self.value.append(param)
		return param

	def add_param(self, identifier, *, type=None, description=None, value=None):
		if self.type is not self.Type.DICT:
			raise TypeError(f"Can't append parameter to parameter of type {self.type}")
		if self.value is None:
			self.__dict__["value"] = {}
		if type is None and value is None:
			raise ValueError("one of type or value must not be None")
		param = AppParameter(parent=self, owner=self.owner, type=type, identifier=identifier, description=description, value=value)
		self.value[identifier] = param
		return param

	def is_dirty(self) -> bool:
		if self.id is None:
			return True
		return self._dirty

	def is_deleted(self) -> bool:
		return self._deleted

	def is_new(self) -> bool:
		return self._new


@register("menuitem")
class MenuItem(CustomAttributes):
	r"""
	An additional menu item in an app that links to a target page.

	Relevant instance attributes are:

	.. attribute:: id
		:type: str

		Unique database id

	.. attribute:: label
		:type: str

		The link text.

	.. attribute:: app
		:type: App

		The app this item belongs to.

	.. attribute:: type
		:type: MenuItem.Type

		What kind of page does the item link to?

	.. attribute:: icon
		:type: Optional[str]

		The name of a Font Awesome icon.

		The name might have one of the suffixes ``-brand``, ``-sharp-solid``,
		``-sharp-regular``, ``-solid``, ``-regular``, ``-light``, ``-thin`` or
		``-duotone`` to force the use of the appropriate Font Awesome style
		instead of the default.

	.. attribute:: title
		:type: Optional[str]

		The ``title`` attribute for the link.

	.. attribute:: target
		:type: Optional[str]

		The ``target`` attribute for the link.

	.. attribute:: cssclass
		:type: Optional[str]

		The ``class`` attribute for the link.

	.. attribute:: url
		:type: str

		The link itself.

	.. attribute:: order
		:type: Optional[int]

		Items are ordered by this integer value in menus and panels (except for
		panels on the custom overview page, where panels are displayed in a
		two-dimensional grid).

	.. attribute:: children
		:type: List[MenuItem]

		List of sub items

	.. attribute:: start_time
		:type: Optional[datetime.datetime]

		If ``start_time`` is not ``None``, the item should not be displayed before
		this point in time (and will not be output as part of the :class:`Apps`\s
		``menus`` or ``panels`` attribute).

	.. attribute:: end_time
		:type: Optional[datetime.datetime]

		If ``end_time`` is not ``None``, the item should not be displayed before
		this point in time (and will not be output as part of the :class:`Apps`\s
		``menus`` or ``panels`` attribute).

	.. attribute:: on_app_overview_page
		:type: bool

		Should this item be displayed on the app overview page (i.e. the page
		containing the list of apps)?

	.. attribute:: on_app_detail_page
		:type: bool

		Should this item be displayed on the app detail page (i.e. the start
		page of an app)?

	.. attribute:: on_form_page
		:type: bool

		Should this item be displayed on the form page?

	.. attribute:: on_iframe_page
		:type: bool

		Should this item be displayed on the iframe page?

	.. attribute:: on_custom_overview_page
		:type: bool

		Should this item be displayed on the custom overview page?

	.. attribute:: createdat
		:type: datetime.datetime

		When was this item created?

	.. attribute:: createdby
		:type: User

		Who created this item?

	.. attribute:: updatedat
		:type: Optional[datetime.datetime]

		When was this item last updated?

	.. attribute:: updatedby
		:type: Optional[User]

		Who updated this item last?
	"""

	ul4_attrs = Base.ul4_attrs.union({"id", "identifier", "label", "parent", "app", "type", "icon", "title", "target", "cssclass", "url", "order", "start_time", "end_time", "on_app_overview_page", "on_app_detail_page", "on_form_page", "on_iframe_page", "on_custom_overview_page", "on_view_template", "accessible", "children", "createdat", "createdby", "updatedat", "updatedby"})
	ul4_type = ul4c.Type("la", "MenuItem", "An additional menu item in an app that links to a target page.")

	class Type(misc.Enum):
		"""
		What is the target of the link? Possible values are:

		*	``NEWFORM_STANDALONE``
		*	``NEWFORM_EMBEDDED``
		*	``DATAMANAGEMENT``
		*	``CUSTOMOVERVIEW``
		*	``EVALUATION``
		*	``IMPORT_EXPORT``
		*	``TASKS``
		*	``FORMBUILDER``
		*	``WORKFLOW_MANAGER``
		*	``DATA_CONFIG``
		*	``PERMISSIONS``
		*	``EXPERT``
		*	``VIEWTEMPLATE``
		*	``DATAMANAGEVIEW``
		*	``CUSTOM``
		"""

		APPSTART = "appstart"
		NEWFORM_STANDALONE = "newform_standalone"
		NEWFORM_EMBEDDED = "newform_embedded"
		DATAMANAGEMENT = "datamanagement"
		CUSTOMOVERVIEW = "customoverview"
		EVALUATION = "evaluation"
		IMPORT_EXPORT = "import_export"
		TASKS = "tasks"
		FORMBUILDER = "formbuilder"
		WORKFLOW_MANAGER = "workflow_manager"
		DATA_CONFIG = "data_config"
		PERMISSIONS = "permissions"
		EXPERT = "expert"
		VIEWTEMPLATE = "viewtemplate"
		DATAMANAGEVIEW = "datamanageview"
		CUSTOM = "custom"
		NOLINK = "nolink"

	id = Attr(str, get=True, set=True, repr=True, ul4get=True)
	app = Attr(App, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	identifier = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	label = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	parent = Attr(lambda: MenuItem, lambda: Panel, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	type = EnumAttr(Type, get=True, set=False, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	icon = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	title = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	target = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	cssclass = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	url = Attr(str, get=True, set=True, repr=True, ul4get=True, ul4onget=True, ul4onset=True)
	order = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	start_time = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	end_time = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	on_app_overview_page = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	on_app_detail_page = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	on_form_page = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	on_iframe_page = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	on_view_template = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	on_custom_overview_page = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	accessible = BoolAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	children = AttrDictAttr(get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	createdby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedat = Attr(datetime.datetime, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	updatedby = Attr(User, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, identifier=None, label=None, app=None, type=None):
		super().__init__()
		self.id = id
		self.identifier = identifier
		self.label = label
		self.app = app
		self.parent = None
		self.type = type
		self.icon = None
		self.title = None
		self.target = None
		self.cssclass = None
		self.url = None
		self.start_time = None
		self.end_time = None
		self.on_app_overview_page = False
		self.on_app_detail_page = False
		self.on_form_page = False
		self.on_iframe_page = False
		self.on_view_template = False
		self.on_custom_overview_page = False
		self.accessible = False
		self.children = attrdict()
		self.createdat = None
		self.createdby = None
		self.updatedat = None
		self.updatedby = None

	@property
	def ul4onid(self) -> str:
		return self.id

	def _template_candidates(self):
		handler = self.app.globals._gethandler()
		yield handler.fetch_internaltemplates(self.app.id, "menuitem_instance", None)
		yield handler.fetch_librarytemplates("menuitem_instance")

	def __getattr__(self, name: str) -> Any:
		if name.startswith("c_"):
			identifier = name[2:]
			if identifier in self.children:
				return self.children[identifier]
		return super().__getattr__(name)

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = set(super().__dir__())
		for identifier in self.children:
			attrs.add(f"c_{identifier}")
		return attrs

	def ul4_hasattr(self, name: str) -> Any:
		if name in self.ul4_attrs:
			return True
		elif name.startswith("c_") and name[2:] in self.children:
			return True
		else:
			return super().ul4_hasattr(name)

	def ul4_getattr(self, name: str) -> Any:
		if name.startswith("c_"):
			return getattr(self, name)
		elif self.ul4_hasattr(name):
			return super().ul4_getattr(name)


@register("panel")
class Panel(MenuItem):
	r"""
	An additional panel in an app that is display on various LivingApps pages
	and links to a target page.

	In addition to the attributes inherited from :class:`MenuItem` the following
	instance attributes are available:

	.. attribute:: description
		:type: Optional[str]

		Additional HTML description for the panel.

	.. attribute:: description_url
		:type: Optional[str]

		If this is not :const:`None`, the description should be fetched as an HTML
		snippet from this URL.

	.. attribute:: image
		:type: Optional[File]

		An image to be displayed as the panel title.

	.. attribute:: row
		:type: Optional[int]

		Row number for displaying this panel on the custom overview page.

	.. attribute:: column
		:type: Optional[int]

		Column number for displaying this panel on the custom overview page.

	.. attribute:: width
		:type: Optional[int]

		Width of this panel on the custom overview page.

	.. attribute:: height
		:type: Optional[int]

		Height of this panel on the custom overview page.

	.. attribute:: header_type
		:type: HeaderType

		How to display the header of the panel.

	.. attribute:: header_background
		:type: Optional[HeaderBackground]

		Which background to show for the header.

	.. attribute:: text_color
		:type: Optional[color.Color]

		The text color for the header.

	.. attribute:: background_color1
		:type: Optional[color.Color]

		The primary (or only) background color for the header.

	.. attribute:: background_color2
		:type: Optional[color.Color]

		The secondary background color for the header.
	"""

	ul4_attrs = MenuItem.ul4_attrs.union({"description", "description_url", "image", "row", "column", "width", "height", "header_type", "header_background", "text_color", "background_color1", "background_color2"})
	ul4_type = ul4c.Type("la", "Panel", "An additional panel in an app that is displayed on various LivingApps pages and links to a target page.")

	class HeaderType(misc.Enum):
		"""
		How to display the panel header.

		Enum values have the following meaning:

		``TITLE``
			A normal title bar.

		``CARD``
			Show more of the background, with increased height.
		"""

		TITLE = "title"
		CARD = "card"

	class HeaderBackground(misc.Enum):
		"""
		What background to display for the panel header.

		Enum values have the following meaning:

		``UNIFORMCOLOR``
			The background is just a single color.

		``LINEARGRADIENT``
			The background is a linear background from top to bottom.

		``RADIALGRADIENT``
			The background is a radial background centered at the middle of the top edge.

		``IMAGE``
			The background is an image.
		"""

		UNIFORMCOLOR = "uniformcolor"
		LINEARGRADIENT = "lineargradient"
		RADIALGRADIENT = "radialgradient"
		IMAGE = "image"

	description = Attr(str, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	description_url = Attr(str, get=True, set=True, ul4onget=True, ul4onset=True)
	image = Attr(File, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	row = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	column = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	width = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	height = Attr(int, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	header_type = EnumAttr(HeaderType, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	header_background = EnumAttr(HeaderBackground, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	text_color = Attr(color.Color, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	background_color1 = Attr(color.Color, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)
	background_color2 = Attr(color.Color, get=True, set=True, ul4get=True, ul4onget=True, ul4onset=True)

	def __init__(self, id=None, identifier=None, label=None, app=None, type=None):
		super().__init__(id=id, identifier=identifier, label=label, app=app, type=type)
		self.description = None
		self.description_url = None
		self.image = None
		self.row = None
		self.column = None
		self.width = None
		self.height = None
		self.header_type = None
		self.header_background = None
		self.text_color = None
		self.background_color1 = None
		self.background_color2 = None

	def _template_candidates(self):
		handler = self.app.globals._gethandler()
		yield handler.fetch_internaltemplates(self.app.id, "panel_instance", None)
		yield handler.fetch_internaltemplates(self.app.id, "menuitem_instance", None)
		yield handler.fetch_librarytemplates("panel_instance")
		yield handler.fetch_librarytemplates("menuitem_instance")

	def __dir__(self) -> set[str]:
		"""
		Make keys completeable in IPython.
		"""
		attrs = set(super().__dir__())
		attrs.add("description")
		attrs.add("description_url")
		attrs.add("image")
		attrs.add("row")
		attrs.add("column")
		attrs.add("width")
		attrs.add("height")
		attrs.add("header_type")
		attrs.add("header_background")
		attrs.add("text_color")
		attrs.add("background_color1")
		attrs.add("background_color2")
		return attrs


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
		:type: dict[str, str | File | list[str | File]]

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

	ul4_attrs = Base.ul4_attrs.union({"method", "headers", "params", "seq"})
	ul4_type = ul4c.Type("la", "HTTPRequest", "An HTTP request")

	method = Attr(str, get=True, set=True, repr=True, ul4get=True)
	headers = CaseInsensitiveDictAttr(get=True, ul4get=True)
	params = AttrDictAttr(get=True, ul4get=True)

	def __init__(self, method:str="get"):
		self.method = method
		self.headers = {}
		self.params = {}
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
