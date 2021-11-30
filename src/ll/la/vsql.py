#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2020 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
vSQL is a subset of UL4 expressions retargeted for generating SQL expressions
used in SQL queries. Currently only Oracle is supported.

This module contains classes and functions for generating and compiling
vSQL expressions.

A vSQL expression can be generated in two ways:

*	By directly constructing a vSQL expression via the class method :meth:`make`
	of the various :class:`AST` subclasses. For example a vSQL expression for
	``"foo".lower() + "bar".upper()`` can be constructed like this::

		vsql.AddAST.make(
			vsql.MethAST.make(
				vsql.StrAST.make("foo"),
				"lower",
			),
			vsql.MethAST.make(
				vsql.StrAST.make("bar"),
				"upper",
			),
		)

*	By compiling the appropriate UL4/vSQL source code into an :class:`AST` object.
	So ``"foo".lower() + "bar".upper()`` can be compiled like this::

		vsql.AST.fromsource("'foo'.lower() + 'bar'.upper()")

"""

import sys, datetime, itertools, re, pathlib

from ll import color, misc, ul4c, ul4on

try:
	from ll import orasql
except ImportError:
	orasql = None

###
### Typing stuff
###

from typing import *

T_AST_Content = Union["AST", str]

T_opt_str = Optional[str]
T_opt_int = Optional[int]
T_opt_ast = Optional["AST"]
T_sortdirection = Union[None, Literal["asc", "desc"]]
T_sortnulls = Union[None, Literal["first", "last"]]

def T_gen(type):
	return Generator[type, None, None]


###
### Global configurations
###

scriptname = misc.sysinfo.short_script_name


###
### Fields for the table ``VSQLRULE``
###

fields = dict(
	vr_nodetype=str,
	vr_value=T_opt_str,
	vr_result=str,
	vr_signature=T_opt_str,
	vr_arity=int,
	vr_literal1=T_opt_str,
	vr_child2=T_opt_int,
	vr_literal3=T_opt_str,
	vr_child4=T_opt_int,
	vr_literal5=T_opt_str,
	vr_child6=T_opt_int,
	vr_literal7=T_opt_str,
	vr_child8=T_opt_int,
	vr_literal9=T_opt_str,
	vr_child10=T_opt_int,
	vr_literal11=T_opt_str,
	vr_child12=T_opt_int,
	vr_literal13=T_opt_str,
	vr_cname=str,
	vr_cdate=datetime.datetime,
)


###
### Helper functions and classes
###

class sqlliteral(str):
	"""
	Marker class that can be used to spcifiy that its value should be treated
	as literal SQL.
	"""
	pass


def sql(value:Any) -> str:
	"""
	Return an SQL expression for the Python value ``value``.
	"""
	if value is None:
		return "null"
	elif isinstance(value, sqlliteral):
		return str(value)
	elif isinstance(value, int):
		return str(value)
	elif isinstance(value, datetime.datetime):
		return f"to_date('{value:%Y-%m-%d %H:%M:%S}', 'YYYY-MM-DD HH24:MI:SS')"
	elif isinstance(value, str):
		if value:
			value = value.replace("'", "''")
			return f"'{value}'"
		else:
			return "null"
	else:
		raise TypeError(f"unknown type {type(value)!r}")


class Repr:
	"""
	Base class that provides functionality for implementing :meth:`__repr__`
	and :meth:`_repr_pretty_` (used by IPython).
	"""

	def _ll_repr_prefix_(self) -> str:
		"""
		Return the initial part of the :meth:`__repr__` and :meth:`_repr_pretty_`
		output (without the initial ``"<"``).
		"""
		return f"{self.__class__.__module__}.{self.__class__.__qualname__}"

	def _ll_repr_suffix_(self) -> str:
		"""
		Return the final part of the :meth:`__repr__` and :meth:`_repr_pretty_`
		output (without the final ``">"``).
		"""
		return f"at {id(self):#x}"

	def __repr__(self) -> str:
		parts = itertools.chain(
			(f"<{self._ll_repr_prefix_()}",),
			self._ll_repr_(),
			(f"{self._ll_repr_suffix_()}>",),
		)
		return " ".join(parts)

	def _ll_repr_(self) -> T_gen(str):
		"""
		Each string produced by :meth:`!_ll_repr__` will be part of the
		:meth:`__repr__` output (joined by spaces).
		"""
		yield from ()

	def _repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter", cycle:bool) -> None:
		if cycle:
			p.text(f"{self._ll_repr_prefix_()} ... {self._ll_repr_suffix_()}>")
		else:
			with p.group(3, f"<{self._ll_repr_prefix_()}", ">"):
				self._ll_repr_pretty_(p)
				p.breakable()
				p.text(self._ll_repr_suffix_())

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		"""
		Implement the body of the :meth:`_repr_pretty_` method.

		This means that the cycle detection and :meth:`group` call have already
		been done.
		"""
		pass


class DataType(misc.Enum):
	"""
	The datatypes supported in vSQL expressions.
	"""

	NULL = "null"
	BOOL = "bool"
	INT = "int"
	NUMBER = "number"
	STR = "str"
	CLOB = "clob"
	COLOR = "color"
	GEO = "geo"
	DATE = "date"
	DATETIME = "datetime"
	DATEDELTA = "datedelta"
	DATETIMEDELTA = "datetimedelta"
	MONTHDELTA = "monthdelta"
	NULLLIST = "nulllist"
	INTLIST = "intlist"
	NUMBERLIST = "numberlist"
	STRLIST = "strlist"
	CLOBLIST = "cloblist"
	DATELIST = "datelist"
	DATETIMELIST = "datetimelist"
	NULLSET = "nullset"
	INTSET = "intset"
	NUMBERSET = "numberset"
	STRSET = "strset"
	DATESET = "dateset"
	DATETIMESET = "datetimeset"

	@classmethod
	def compatible_to(cls, given:"DataType", required:"DataType") -> Optional["Error"]:
		"""
		Check whether the type ``given`` is compatible to ``required``.

		If ``required`` is ``None`` every ``given`` type is accepted. Otherwise
		the types must be compatible (for example ``DataType.INT`` is compatible
		to ``DataType.NUMBER``, but not the other way around). Every type is
		compatible to itself.

		If ``given`` is not compatible to ``required`` the appropriate error value
		is returned, otherwise ``None`` is returned.
		"""
		# If we have no requirement for the datatype the given one is OK.
		if required is None:
			return None
		# ``NULL`` is compatible with everything
		elif given is DataType.NULL:
			return None
		# perfect match
		elif given is required:
			return None
		# some type of string
		elif required in {DataType.STR, DataType.CLOB} and given in {DataType.STR, DataType.CLOB}:
			return None
		# bool and int can be used for numbers
		elif required is DataType.NUMBER and given in {DataType.BOOL, DataType.INT, DataType.NUMBER}:
			return None
		# bool can be used for ints
		elif required is DataType.INT and given in {DataType.BOOL, DataType.INT}:
			return None
		# intlist can be used for numberlist
		elif required is DataType.NUMBERLIST and given in {DataType.INTLIST, DataType.NUMBERLIST}:
			return None
		# datelist can be used for datetimelist
		elif required is DataType.DATELIST and given in {DataType.INTLIST, DataType.DATETIMELIST}:
			return None
		# intset can be used for numberset
		elif required is DataType.NUMBERSET and given in {DataType.INTSET, DataType.NUMBERSET}:
			return None
		# dateset can be used for datetimeset
		elif required is DataType.DATESET and given in {DataType.INTSET, DataType.DATETIMESET}:
			return None
		# nulllist can be used as any list
		elif required in {DataType.INTLIST, DataType.NUMBERLIST, DataType.STRLIST, DataType.CLOBLIST, DataType.DATELIST, DataType.DATETIMELIST} and given is DataType.NULLLIST:
			return None
		# nullset can be used as any set
		elif required in {DataType.INTSET, DataType.NUMBERSET, DataType.STRSET, DataType.DATESET, DataType.DATETIMESET} and given is DataType.NULSET:
			return None
		else:
			return Error[f"DATATYPE_{required.name}"]


class NodeType(misc.Enum):
	"""
	The different types of vSQL abstract syntax tree nodes.

	This corresponds to the different subclasses of :class:`AST`.
	"""

	FIELD = "field"
	CONST_NONE = "const_none"
	CONST_BOOL = "const_bool"
	CONST_INT = "const_int"
	CONST_NUMBER = "const_number"
	CONST_STR = "const_str"
	CONST_CLOB = "const_clob"
	CONST_DATE = "const_date"
	CONST_DATETIME = "const_datetime"
	CONST_TIMESTAMP = "const_timestamp"
	CONST_COLOR = "const_color"
	LIST = "list"
	SET = "set"
	CMP_EQ = "cmp_eq"
	CMP_NE = "cmp_ne"
	CMP_LT = "cmp_lt"
	CMP_LE = "cmp_le"
	CMP_GT = "cmp_gt"
	CMP_GE = "cmp_ge"
	BINOP_ADD = "binop_add"
	BINOP_MUL = "binop_mul"
	BINOP_SUB = "binop_sub"
	BINOP_FLOORDIV = "binop_floordiv"
	BINOP_TRUEDIV = "binop_truediv"
	BINOP_MOD = "binop_mod"
	BINOP_AND = "binop_and"
	BINOP_OR = "binop_or"
	BINOP_CONTAINS = "binop_contains"
	BINOP_NOTCONTAINS = "binop_notcontains"
	BINOP_IS = "binop_is"
	BINOP_ISNOT = "binop_isnot"
	BINOP_ITEM = "binop_item"
	BINOP_SHIFTLEFT = "binop_shiftleft"
	BINOP_SHIFTRIGHT = "binop_shiftright"
	BINOP_BITAND = "binop_bitand"
	BINOP_BITOR = "binop_bitor"
	BINOP_BITXOR = "binop_bitxor"
	TERNOP_SLICE = "ternop_slice"
	UNOP_NOT = "unop_not"
	UNOP_NEG = "unop_neg"
	UNOP_BITNOT = "unop_bitnot"
	TERNOP_IF = "ternop_if"
	ATTR = "attr"
	FUNC = "func"
	METH = "meth"


class Error(misc.Enum):
	"""
	The types of errors that can lead to invalid vSQL AST nodes.

	Note that some of those can not be produced by the Python implementation.
	"""

	SUBNODEERROR = "subnodeerror" # Subnodes are invalid
	NODETYPE = "nodetype" # Unknown node type (not any of the ``NODETYPE_...`` values from above
	ARITY = "arity" # Node does not have the required number of children
	SUBNODETYPES = "subnodetypes" # Subnodes have a combination of types that are not supported by the node
	FIELD = "field" # ``NODETYPE_FIELD`` nodes references an unknown field
	CONST_BOOL = "const_bool" # ``NODETYPE_CONST_BOOL`` value is ``null`` or malformed
	CONST_INT = "const_int" # ``NODETYPE_CONST_INT`` value is ``null`` or malformed
	CONST_NUMBER = "const_number" # ``NODETYPE_CONST_NUMBER`` value is ``null`` or malformed
	CONST_DATE = "const_date" # ``NODETYPE_CONST_DATE`` value is ``null`` or malformed
	CONST_DATETIME = "const_datetime" # ``NODETYPE_CONST_DATETIME`` value is ``null`` or malformed
	CONST_TIMESTAMP = "const_timestamp" # ``NODETYPE_CONST_DATETIME`` value is ``null`` or malformed
	CONST_COLOR = "const_color" # ``NODETYPE_CONST_COLOR`` value is ``null`` or malformed
	NAME = "name" # Attribute/Function/Method is unknown
	LISTTYPEUNKNOWN = "listtypeunknown" # List is empty or only has literal ``None``s as items, so the type can't be determined
	LISTMIXEDTYPES = "listmixedtypes" # List items have incompatible types, so the type can't be determined
	LISTUNSUPPORTEDTYPES = "listunsupportedtypes" # List items have unsupported types, so the type can't be determined
	SETTYPEUNKNOWN = "settypeunknown" # Set is empty or only has literal ``None``s as items, so the type can't be determined
	SETMIXEDTYPES = "setmixedtypes" # Set items have incompatible types, so the type can't be determined
	SETUNSUPPORTEDTYPES = "setunsupportedtypes" # Set items have unsupported types, so the type can't be determined
	DATATYPE_NULL = "datatype_null" # The datatype of the node should be ``null`` but isn't
	DATATYPE_BOOL = "datatype_bool" # The datatype of the node should be ``bool`` but isn't
	DATATYPE_INT = "datatype_int" # The datatype of the node should be ``int`` but isn't
	DATATYPE_NUMBER = "datatype_number" # The datatype of the node should be ``number`` but isn't
	DATATYPE_STR = "datatype_str" # The datatype of the node should be ``str`` but isn't
	DATATYPE_CLOB = "datatype_clob" # The datatype of the node should be ``clob`` but isn't
	DATATYPE_COLOR = "datatype_color" # The datatype of the node should be ``color`` but isn't
	DATATYPE_DATE = "datatype_date" # The datatype of the node should be ``date`` but isn't
	DATATYPE_DATETIME = "datatype_datetime" # The datatype of the node should be ``datetime`` but isn't
	DATATYPE_DATEDELTA = "datatype_datedelta" # The datatype of the node should be ``datedelta`` but isn't
	DATATYPE_DATETIMEDELTA = "datatype_datetimedelta" # The datatype of the node should be ``datetimedelta`` but isn't
	DATATYPE_MONTHDELTA = "datatype_monthdelta" # The datatype of the node should be ``monthdelta`` but isn't
	DATATYPE_NULLLIST = "datatype_nulllist" # The datatype of the node should be ``nulllist`` but isn't
	DATATYPE_INTLIST = "datatype_intlist" # The datatype of the node should be ``intlist`` but isn't
	DATATYPE_NUMBERLIST = "datatype_numberlist" # The datatype of the node should be ``numberlist`` but isn't
	DATATYPE_STRLIST = "datatype_strlist" # The datatype of the node should be ``strlist`` but isn't
	DATATYPE_CLOBLIST = "datatype_cloblist" # The datatype of the node should be ``cloblist`` but isn't
	DATATYPE_DATELIST = "datatype_datelist" # The datatype of the node should be ``datelist`` but isn't
	DATATYPE_DATETIMELIST = "datatype_datetimelist" # The datatype of the node should be ``datetimelist`` but isn't
	DATATYPE_NULLSET = "datatype_nullset" # The datatype of the node should be ``nullset`` but isn't
	DATATYPE_INTSET = "datatype_intset" # The datatype of the node should be ``intset`` but isn't
	DATATYPE_NUMBERSET = "datatype_numberset" # The datatype of the node should be ``numberset`` but isn't
	DATATYPE_STRSET = "datatype_strset" # The datatype of the node should be ``strset`` but isn't
	DATATYPE_DATESET = "datatype_dateset" # The datatype of the node should be ``dateset`` but isn't
	DATATYPE_DATETIMESET = "datatype_datetimeset" # The datatype of the node should be ``datetimeset`` but isn't


@ul4on.register("de.livinglogic.vsql.field")
class Field(Repr):
	"""
	A :class:`!Field` object describes a database field.

	This field is either in a database table or view or a global package variable.

	As a table or view field it belongs to a :class:`Group` object.
	"""
	def __init__(self, identifier:T_opt_str=None, datatype:DataType=DataType.NULL, fieldsql:T_opt_str=None, joinsql:T_opt_str=None, refgroup:Optional["Group"]=None):
		self.identifier = identifier
		self.datatype = datatype
		self.fieldsql = fieldsql
		self.joinsql = joinsql
		self.refgroup = refgroup

	def _ll_repr_(self) -> T_gen(str):
		yield f"identifier={self.identifier!r}"
		if self.datatype is not None:
			yield f"datatype={self.datatype.name}"
		if self.fieldsql is not None:
			yield f"fieldsql={self.fieldsql!r}"
		if self.joinsql is not None:
			yield f"joinsql={self.joinsql!r}"
		if self.refgroup is not None:
			yield f"refgroup.tablesql={self.refgroup.tablesql!r}"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		p.breakable()
		p.text("identifier=")
		p.pretty(self.identifier)
		if self.datatype is not None:
			p.breakable()
			p.text(f"datatype={self.datatype.name}")
		if self.fieldsql is not None:
			p.breakable()
			p.text("fieldsql=")
			p.pretty(self.fieldsql)
		if self.joinsql is not None:
			p.breakable()
			p.text("joinsql=")
			p.pretty(self.joinsql)
		if self.refgroup is not None:
			p.breakable()
			p.text("refgroup.tablesql=")
			p.pretty(self.refgroup.tablesql)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		encoder.dump(self.identifier)
		encoder.dump(self.datatype.value if self.datatype is not None else None)
		encoder.dump(self.fieldsql)
		encoder.dump(self.joinsql)
		encoder.dump(self.refgroup)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		self.identifier = decoder.load()
		datatype = decoder.load()
		self.datatype = DataType(datatype) if datatype is not None else None
		self.fieldsql = decoder.load()
		self.joinsql = decoder.load()
		self.refgroup = decoder.load()


@ul4on.register("de.livinglogic.vsql.group")
class Group(Repr):
	"""
	A :class:`!Group` object describes a group of database fields.

	These fields are part of a database table or view and are instances of
	:class:`Field`.
	"""

	def __init__(self, tablesql:T_opt_str=None, **fields:Union["Field", Tuple[DataType, str], Tuple[DataType, str, str, "Group"]]):
		self.tablesql = tablesql
		self.fields = {}
		for (fieldname, fielddata) in fields.items():
			if not isinstance(fielddata, Field):
				fielddata = Field(fieldname, *fielddata)
			self.fields[fieldname] = fielddata

	def _ll_repr_(self) -> T_gen(str):
		yield f"tablesql={self.tablesql!r}"
		yield f"with {len(self.fields):,} fields"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		p.breakable()
		p.text("tablesql=")
		p.pretty(self.tablesql)

	def __getitem__(self, key:str) -> "Field":
		if key in self.fields:
			return self.fields[key]
		elif "*" in self.fields:
			return self.fields["*"]
		else:
			raise KeyError(key)

	def add_field(self, identifier:str, datatype:DataType, fieldsql:str, joinsql:T_opt_str=None, refgroup:Optional["Group"]=None) -> None:
		field = Field(identifier, datatype, fieldsql, joinsql, refgroup)
		self.fields[identifier] = field

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		encoder.dump(self.tablesql)
		encoder.dump(self.fields)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		self.tablesql = decoder.load()
		self.fields = decoder.load()


class Query(Repr):
	"""
	A :class:`!Query` object can be used to build an SQL query using vSQL expressions.
	"""
	def __init__(self, comment:T_opt_str=None, **vars:"Field"):
		"""
		Create a new empty :class:`!Query` object.

		Arguments are:

		``comment`` : :class:`str` or ``None``
			A comment that will be included in the generated SQL.

			Note that the comment test may not include ``/*`` or ``*/``.

		``vars`` : :class:`Field`
			These are the top level variables that will be availabe for vSQL
			expressions added to this query. The argument name is the name of
			the variable. The argument value is a :class:`Field` object that
			describes this variable.
		"""
		self.comment = comment
		self.vars = vars
		self._fields : Dict[str, "AST"] = {}
		self._from : Dict[str, "AST"] = {}
		self._where : Dict[str, "AST"] = {}
		self._orderby : List[Tuple[str, "AST", T_opt_str, T_opt_str]] = []
		self._identifier_aliases : Dict[str, str] = {}

	def _vsql_register(self, fieldref:"FieldRefAST") -> T_opt_str:
		if fieldref.error is not None:
			return # Don't register broken expressions
		if fieldref.parent is None:
			# No need to register anything as this is a "global variable".
			# Also we don't need a table alias to access this field.
			return None

		identifier = fieldref.parent.full_identifier
		if identifier in self._identifier_aliases:
			alias = self._identifier_aliases[identifier]
			return alias
		alias = self._vsql_register(fieldref.parent)

		newalias = f"t{len(self._from)+1}"
		joincond = fieldref.parent.field.joinsql
		if joincond is not None:
			# Only add to "where" if the join condition is not empty
			if alias is not None:
				joincond = joincond.replace("{m}", alias)
			joincond = joincond.replace("{d}", newalias)
			self._where[joincond] = fieldref.parent

		if fieldref.parent.field.refgroup.tablesql is None:
			# If this field is not part of a table (which can happen e.g. for
			# the request parameters, which we get from function calls),
			# we don't add the table aliases to the list of table aliases
			# and we don't add a table to the "from" list.
			return None

		self._identifier_aliases[identifier] = newalias
		self._from[f"{fieldref.parent.field.refgroup.tablesql} {newalias}"] = fieldref.parent
		return newalias

	def _vsql(self, expr:str) -> None:
		expr = AST.fromsource(expr, **self.vars)
		for fieldref in expr.fieldrefs():
			self._vsql_register(fieldref)
		return expr

	def select(self, *exprs:str) -> "Query":
		for expr in exprs:
			expr = self._vsql(expr)
			sqlsource = expr.sqlsource(self)
			if sqlsource not in self._fields:
				self._fields[sqlsource] = expr
		return self

	def where(self, *exprs:str) -> "Query":
		for expr in exprs:
			expr = self._vsql(expr)
			if expr.datatype is not DataType.BOOL:
				expr = FuncAST.make("bool", expr)
			sqlsource = expr.sqlsource(self)
			sqlsource = f"{sqlsource} = 1"
			if sqlsource not in self._where:
				self._where[sqlsource] = expr
		return self

	def orderby(self, expr:str, direction:T_sortdirection=None, nulls:T_sortnulls=None) -> "Query":
		r"""
		Add an "order by" specification to this query.

		"order by" specifications will be output in the query in the order they
		have been added.

		Argument are:

		``expr`` : :class:`str`
			vSQL expression to be sorted by

		``direction`` : ``None``, ``"asc"`` or ``"desc"``
			Sort in ascending order (``"asc"``) or descending order (``"desc"``).

			The default ``None`` adds neither ``asc`` nor ``desc`` (which is
			equivalent to ``asc``.

		Example::

			>>> from ll import la
			>>> from ll.la import vsql
			>>> q = vsql.Query("Example query", user=la.User.vsqlfield())
			>>> q.select("user.email") \
			...  .orderby("user.firstname", "asc") \
			...  .orderby("user.surname", "desc")
			>>> print(q.sqlsource())
			/* Example query */
			select
				t1.ide_account /* user.email */
			from
				identity t1 /* user */
			where
				livingapi_pkg.global_user = t1.ide_id(+) /* user */
			order by
				t1.ide_firstname /* user.firstname */ asc,
				t1.ide_surname /* user.surname */ desc
		"""
		expr = self._vsql(expr)
		sqlsource = expr.sqlsource(self)
		self._orderby.append((sqlsource, expr, direction, nulls))
		return self

	def sqlsource(self, indent="\t") -> str:
		tokens = []

		def a(*parts):
			tokens.extend(parts)

		def s(sqlsource, expr):
			tokens.append(sqlsource)
			vsqlsource = f" /* {expr.source()} */"
			if not sqlsource.endswith(vsqlsource):
				tokens.append(vsqlsource)

		if self.comment:
			a("/* ", self.comment, " */", None)

		a("select", None, +1)
		if self._fields:
			for (i, (field, expr)) in enumerate(self._fields.items()):
				if i:
					a(",", None)
				s(field, expr)
		else:
			a("42")
		a(None, -1)

		a("from", None, +1)
		if self._from:
			for (i, (table, expr)) in enumerate(self._from.items()):
				if i:
					a(",", None)
				s(table, expr)
			a(None, -1)
		else:
			a("dual", None, -1)

		if self._where:
			a("where", None, +1)
			for (i, (where, expr)) in enumerate(self._where.items()):
				if i:
					a(" and", None)
				s(where, expr)
			a(None, -1)

		if self._orderby:
			a("order by", None, +1)
			for (i, (sqlsource, expr, direction, nulls)) in enumerate(self._orderby):
				if i:
					a(",", None)
				s(sqlsource, expr)
				if direction:
					a(" ", direction)
				if nulls:
					a(" nulls ", nulls)
			a(None, -1)

		source = []
		first = True
		level = 0
		for part in tokens:
			if part is None:
				if indent:
					source.append("\n")
					first = True
			elif isinstance(part, int):
				level += part
			else:
				if first:
					if indent:
						source.append(level*indent)
					else:
						source.append(" ")
				source.append(part)
				first = False

		return "".join(source)


class Rule(Repr):
	_re_specials = re.compile(r"{([st])(\d)}")
	_re_sep = re.compile(r"\W+")

	# Mappings of datatypes to other datatypes for creating the SQL source
	source_aliases = {
		"bool":         "int",
		"date":         "datetime",
		"datelist":     "datetimelist",
		"datetimelist": "datetimelist",
		"intset":       "intlist",
		"numberset":    "numberlist",
		"strset":       "strlist",
		"dateset":      "datetimelist",
		"datetimeset":  "datetimelist",
	}

	def __init__(self, astcls, result, name, key, signature, source):
		self.astcls = astcls
		self.result = result
		self.name = name
		self.key = key
		self.signature = signature
		self.source = self._parse_source(signature, source)


	def _key(self) -> str:
		key = ", ".join(p.name if isinstance(p, DataType) else repr(p) for p in self.key)
		return f"({key})"

	def _signature(self):
		signature = ", ".join(p.name for p in self.signature)
		return f"({signature})"

	def _ll_repr_(self) -> T_gen(str):
		yield f"nodetype={self.astcls.nodetype.name}"
		yield f"result={self.result.name}"
		if self.name is not None:
			yield f"name={self.name!r}"
		yield f"key={self._key()}"
		yield f"signature={self._signature()}"
		yield f"source={self.source}"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		p.breakable()
		p.text("result=")
		p.text(self.result.name)
		if self.name is not None:
			p.breakable()
			p.text("name=")
			p.pretty(self.name)
		p.breakable()
		p.text("signature=")
		p.text(self._signature())
		p.breakable()
		p.text("key=")
		p.text(self._key())
		p.breakable()
		p.text("source=")
		p.pretty(self.source)

	@classmethod
	def _parse_source(cls, signature:str, source:str) -> Tuple[Union[int, str], ...]:
		final_source = []

		def append(text):
			if final_source and isinstance(final_source[-1], str):
				final_source[-1] += text
			else:
				final_source.append(text)

		pos = 0
		for match in cls._re_specials.finditer(source):
			if match.start() != pos:
				append(source[pos:match.start()])
			sigpos = int(match.group(2))
			if match.group(1) == "s":
				final_source.append(sigpos)
			else:
				type = signature[sigpos-1].name.lower()
				type = cls.source_aliases.get(type, type)
				append(type)
			pos = match.end()
		if pos != len(source):
			append(source[pos:])
		return tuple(final_source)

	def java_source(self) -> str:
		key = ", ".join(
			f"VSQLDataType.{p.name}" if isinstance(p, DataType) else misc.javaexpr(p)
			for p in self.key
		)

		return f"addRule(rules, VSQLDataType.{self.result.name}, {key});"

	def oracle_fields(self) -> Dict[str, Union[int, str, sqlliteral]]:
		fields = {}

		fields["vr_nodetype"] = self.astcls.nodetype.value
		fields["vr_value"] = self.name
		fields["vr_result"] = self.result.value
		fields["vr_signature"] = " ".join(p.value for p in self.signature)
		fields["vr_arity"] = len(self.signature)

		wantlit = True
		index = 1

		for part in self.source:
			if wantlit:
				if isinstance(part, int):
					index += 1 # skip this field
					fields[f"vr_child{index}"] = part
				else:
					fields[f"vr_literal{index}"] = part
				wantlit = False
			else:
				if isinstance(part, int):
					fields[f"vr_child{index}"] = part
				else:
					raise ValueError("two children")
				wantlit = True
			index += 1

		fields["vr_cdate"] = sqlliteral("sysdate")
		fields["vr_cname"] = sqlliteral("c_user")

		return fields

	def oracle_source(self) -> str:
		fieldnames = []
		fieldvalues = []
		for (fieldname, fieldvalue) in self.oracle_fields().items():
			fieldvalue = sql(fieldvalue)
			if fieldvalue != "null":
				fieldnames.append(fieldname)
				fieldvalues.append(fieldvalue)
		fieldnames = ", ".join(fieldnames)
		fieldvalues = ", ".join(fieldvalues)

		return f"insert into vsqlrule ({fieldnames}) values ({fieldvalues});"


###
### Classes for all vSQL abstract syntax tree node types
###

class AST(Repr):
	"""
	Base class of all vSQL abstract syntax tree node types.
	"""

	nodetype = None
	"""
	Type of the node. There's a one-to-one correspondence between :class:`AST`
	subclasses and :class:`NodeType` values (except for intermediate classes
	like :class:`BinaryAST`)
	"""

	nodevalue = None
	"""
	The node value is an instance attribute that represents a string that
	isn't be represented by any child node. E.g. the values of constants or
	the names of functions, methods and attributes. Will be overwritten by
	properties in subclasses.
	"""

	datatype = None
	rules = None

	def __init__(self, *content: T_AST_Content):
		"""
		Create a new :class:`!AST` node from its content.

		``content`` is a mix of :class:`str` objects containing the UL4 source
		and child :class:`!AST` nodes.

		Normally the user doesn't call :meth:`!__init__` directly, but uses
		:meth:`make` to create the appropriate :class:`!AST` node from child
		nodes.

		For example a function call to the function ``date`` could be created
		like this::

			FuncAST(
				"date",
				"(",
				IntAST("2000", 2000),
				", ",
				IntAST("2", 2),
				", ",
				IntAST("29", 29),
				")",
			)

		but more conveniently like this::

			FuncAST.make(
				"date",
				ConstAST.make(2000),
				ConstAST.make(2),
				ConstAST.make(29),
			)
		"""
		final_content = []
		for item in content:
			if isinstance(item, str):
				if item: # Ignore empty strings
					if final_content and isinstance(final_content[-1], str):
						# Merge string with previous string
						final_content[-1] += item
					else:
						final_content.append(item)
			elif isinstance(item, AST):
				final_content.append(item)
			elif item is not None:
				raise TypeError(item)
		self.error = None
		self.content = final_content

	@classmethod
	@misc.notimplemented
	def make(cls) -> "AST":
		"""
		Create an instance of this AST class from its child AST nodes.

		This method is abstract and is overwritten in each subclass.
		"""

	@classmethod
	def fromul4(cls, node:ul4c.AST, **vars: "Field") -> "AST":
		try:
			vsqltype = _ul42vsql[type(node)]
		except KeyError:
			pass
		else:
			return vsqltype.fromul4(node, **vars)

		if isinstance(node, ul4c.VarAST):
			field = vars.get(node.name, None)
			return FieldRefAST(None, node.name, field, *cls._make_content_from_ul4(node))
		elif isinstance(node, ul4c.AttrAST):
			obj = cls.fromul4(node.obj, **vars)
			if isinstance(obj, FieldRefAST) and isinstance(obj.field, Field) and obj.field.refgroup:
				try:
					field = obj.field.refgroup[node.attrname]
				except KeyError:
					pass # Fall through to return a generic :class:`AttrAST` node
				else:
					return FieldRefAST(
						obj,
						node.attrname,
						field,
						*cls._make_content_from_ul4(node, node.obj, obj)
					)
			return AttrAST(
				obj,
				node.attrname,
				*cls._make_content_from_ul4(node, node.obj, obj),
			)
		elif isinstance(node, ul4c.CallAST):
			obj = cls.fromul4(node.obj, **vars)

			content = [*obj.content]
			callargs = []

			if isinstance(obj, FieldRefAST):
				if obj.parent is not None:
					asttype = MethAST
					args = (obj.parent, obj.identifier)
				else:
					asttype = FuncAST
					args = (obj.identifier,)
			elif isinstance(obj, AttrAST):
				asttype = MethAST
				args = (obj.obj, obj.attrname)

			for arg in node.args:
				if not isinstance(arg, ul4c.PositionalArgumentAST):
					raise TypeError(f"Can't compile UL4 expression of type {misc.format_class(arg)}!")
				content.append(arg.value)
				arg = AST.fromul4(arg.value, **vars)
				content.append(arg)
				callargs.append(arg)

			return asttype(
				*args,
				callargs,
				*cls._make_content_from_ul4(node, *content),
			)
		raise TypeError(f"Can't compile UL4 expression of type {misc.format_class(node)}!")

	@classmethod
	def fromsource(cls, source:str, **vars: "Field") -> "AST":
		template = ul4c.Template(f"<?return {source}?>")
		expr = template.content[-1].obj
		return cls.fromul4(expr, **vars)

	def sqlsource(self, query:"Query") -> str:
		return "".join(s for s in self._sqlsource(query))

	def fieldrefs(self) -> T_gen("FieldRefAST"):
		"""
		Return all :class:`FieldRefAST` objects in this :class:`!AST`.

		This is a generator.
		"""
		for child in self.children():
			yield from child.fieldrefs()

	@classmethod
	def all_types(cls) -> T_gen(Type["AST"]):
		"""
		Return this class and all subclasses.

		This is a generator.
		"""
		yield cls
		for subcls in cls.__subclasses__():
			yield from subcls.all_types()

	@classmethod
	def all_rules(cls) -> T_gen(Rule):
		"""
		Return all grammar rules of this class and all its subclasses.

		This is a generator.
		"""
		for subcls in cls.all_types():
			if subcls.rules is not None:
				yield from subcls.rules.values()

	@classmethod
	def _add_rule(cls, rule:Rule) -> None:
		cls.rules[rule.key] = rule

	@classmethod
	def typeref(cls, s:str) -> T_opt_int:
		if s.startswith("T") and s[1:].isdigit():
			return int(s[1:])
		return None

	@classmethod
	def _specs(cls, spec:Tuple[str, ...]) -> T_gen(Tuple[str, Tuple[Union[DataType, str], ...]]):
		# Find position of potential name in the spec, so we can correct
		# the typeref offsets later.
		for (i, p) in enumerate(spec):
			if len(p) == 1 and not p[0].isupper():
				namepos = i
				name = p[0]
				break
		else:
			namepos = None
			name = None

		for spec in itertools.product(*spec):
			newspec = list(spec)
			for (i, type) in enumerate(spec):
				typeref = cls.typeref(type)
				if typeref:
					# Fetch reference type (and corect offset if there's in name in ``spec``)
					type = spec[typeref+1 if namepos and typeref >= namepos else typeref]
					if cls.typeref(type):
						raise ValueError("typeref to typeref")
				newspec[i] = type

			# Convert type names to ``DataType`` values
			newspec = tuple(DataType[p] if p.isupper() else p for p in newspec)
			yield (name, newspec)

	@classmethod
	def add_rules(cls, spec:str, source:str) -> None:
		"""
		Register new syntax rules for this AST class.

		These rules are used for type checking and type inference and for
		converting the vSQL AST into SQL source code.

		The arguments ``spec`` and ``source`` have the following meaning:

		``spec``
			``spec`` specifies the allowed combinations of operand types and the
			resulting type. It consists of the following:

			Upper case words
				These specify types (e.g. ``INT`` or ``STR``; for a list of allowed
				values see :class:`DataType`). Also allowed are:

				*	``T`` followed by an integer, this is used to refer to another
					type in the spec and

				*	a combination of several types joined with ``_``. This is a union
					type, i.e. any of the types in the combination are allowed.

			Lower case words
				They specify the names of functions, methods or attributes

			Any sequence of whitespace or other non-word characters
				They are ignored, but can be used to separate types and names and
				to make the rule clearer.

			The first word in the rule always is the result type.

			Examples:

			``INT <- BOOL + BOOL``
				Adding this rule to :class:`AddAST` specifies that the types ``BOOL``
				and ``BOOL`` can be added and the resulting type is ``INT``. Note
				that using ``+`` is only syntactic sugar. This rule could also have
				been written as ``INT BOOL BOOL`` or even as ``INT?????BOOL#$%^&*BOOL``.

			``INT <- BOOL_INT + BOOL_INT``
				This is equivalent to the four rules: ``INT <- BOOL + BOOL``,
				``INT <- INT + BOOL``, ``INT <- BOOL + INT`` and ``INT <- INT + INT``.

			``T1 <- BOOL_INT + T1``
				This is equivalent to the two rules ``BOOL <- BOOL + BOOL`` and
				``INT <- INT + INT``.

			Note that each rule will only be registered once. So the following
			code::

				AddAST.add_rules(
					"INT <- BOOL_INT + BOOL_INT",
					"..."
				)
				AddAST.add_rules(
					"NUMBER <- BOOL_INT_NUMBER + BOOL_INT_NUMBER",
					"..."
				)

			will register the rule ``INT <- BOOL + BOOL``, but not
			``NUMBER <- BOOL + BOOL`` since the first call already registered
			a rule for the signature ``BOOL BOOL``.

		``source``
			``source`` specifies the SQL source that will be generated for this
			expression. Two types of placeholders are supported: ``{s1}`` means
			"embed the source code of the first operand in this spot" (and ``{s2}``
			etc. accordingly) and ``{t1}`` embeds the type name (in lowercase) in
			this spot (and ``{t2}`` etc. accordingly).

			Example 1::

				AttrAST.add_rules(
					f"INT <- DATE.year",
					"extract(year from {s1})"
				)

			This specifies that a ``DATE`` value has an attribute ``year`` and that
			for such a value ``value`` the generated SQL source code will be:

			.. sourcecode:: sql

				extract(year from value)

			Example 2::

				EQAST.add_rules(
					f"BOOL <- STR_CLOB == STR_CLOB",
					"vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})"
				)

			This registers four rules for equality comparison between ``STR`` and
			``CLOB`` objects. The generated SQL source code for comparisons
			between ``STR`` and ``STR`` will be

			.. sourcecode:: sql

				vsqlimpl_pkg.eq_str_str(value1, value2)

			and for ``CLOB``/``CLOB`` comparison it will be

			.. sourcecode:: sql

				vsqlimpl_pkg.eq_clob_clob(value1, value2)
		"""

		# Split on non-names and drop empty parts
		spec = tuple(filter(None, Rule._re_sep.split(spec)))

		spec = [p.split("_") if p.isupper() else (p,) for p in spec]
		for (name, spec) in cls._specs(spec):
			# Drop return type from the lookup key
			key = spec[1:]
			if cls.rules is None:
				cls.rules = {}
			if key not in cls.rules:
				result = spec[0]
				# Drop name from the signature
				signature = tuple(p for p in key if isinstance(p, DataType))
				cls._add_rule(Rule(cls, result, name, key, signature, source))

	def validate(self) -> None:
		"""
		Validate the content of this AST node.

		If this node turns out to be invalid :meth:`!validate` will set the
		attribute ``datatype`` to ``None`` and ``error`` to the appropriate
		:class:`Error` value.

		If this node turns out to be valid, :meth:`!validate` will set the
		attribute ``error`` to ``None`` and ``datatype`` to the resulting data
		type of this node.
		"""
		pass

	def source(self) -> str:
		"""
		Return the UL4/vSQL source code of the AST.
		"""
		return "".join(s for s in self._source())

	def _source(self) -> T_gen(str):
		for item in self.content:
			if isinstance(item, str):
				yield item
			else:
				yield from item._source()

	def children(self) -> T_gen("AST"):
		"""
		Return the child AST nodes of this node.
		"""
		yield from ()

	def save(self, handler:"ll.la.handlers.DBHandler") -> str:
		"""
		Save this vSQL expression to the database and return the resulting
		database id ``vs_id``.

		``handler`` must be a :class:`~ll.la.handlers.DBHandler`.
		"""

		return handler.save_vsql_ast(self)[0]

	def __str__(self) -> str:
		parts = [f"{self.__class__.__module__}.{self.__class__.__qualname__}"]
		if self.datatype is not None:
			parts.append(f"(datatype {self.datatype.name})")
		if self.error is not None:
			parts.append(f"(error {self.error.name})")
		parts.append(f": {self.source()}")
		return "".join(parts)

	def _ll_repr_(self) -> T_gen(str):
		if self.datatype is not None:
			yield f"datatype={self.datatype.name}"
		if self.error is not None:
			yield f"error={self.error.name}"
		yield f"source={self.source()!r}"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		if self.datatype is not None:
			p.breakable()
			p.text(f"datatype={self.datatype.name}")
		if self.error is not None:
			p.breakable()
			p.text(f"error={self.error.name}")
		p.breakable()
		p.text("source=")
		p.pretty(self.source())

	@classmethod
	def _wrap(cls, obj:T_AST_Content, cond:bool) -> T_gen(T_AST_Content):
		if cond:
			yield "("
		yield obj
		if cond:
			yield ")"

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		encoder.dump(self._source)
		encoder.dump(self.pos)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		self._source = decoder.load()
		self.pos = decoder.load()

	@classmethod
	def _make_content_from_ul4(cls, node:ul4c.AST, *args:Union[ul4c.AST, "AST", str, None]) -> Tuple[T_AST_Content, ...]:
		content = []
		lastpos = node.pos.start
		for subnode in args:
			if isinstance(subnode, AST):
				content.append(subnode)
				lastpos += len(subnode.source())
			elif isinstance(subnode, ul4c.AST):
				if lastpos != subnode.pos.start:
					content.append(node.fullsource[lastpos:subnode.pos.start])
					lastpos = subnode.pos.start
			elif isinstance(subnode, str):
				content.append(subnode)
				lastpos += len(subnode)
		if lastpos != node.pos.stop:
			content.append(node.fullsource[lastpos:node.pos.stop])
		return content


class ConstAST(AST):
	"""
	Base class for all vSQL expressions that are constants.
	"""

	precedence = 20

	@staticmethod
	def make(value:Any) -> "ConstAST":
		cls = _consts.get(type(value))
		if cls is None:
			raise TypeError(value)
		elif cls is NoneAST:
			return cls.make()
		else:
			return cls.make(value)

	@classmethod
	def fromul4(cls, node, **vars: "Field") -> "AST":
		try:
			vsqltype = _consts[type(node.value)]
		except KeyError:
			raise TypeError(f"constant of type {misc.format_class(node.value)} not supported!") from None
		return vsqltype.fromul4(node, **vars)


@ul4on.register("de.livinglogic.vsql.none")
class NoneAST(ConstAST):
	"""
	The constant ``None``.
	"""

	nodetype = NodeType.CONST_NONE
	datatype = DataType.NULL

	@classmethod
	def make(cls) -> "NoneAST":
		return cls("None")

	def _sqlsource(self, query:"Query") -> T_gen(str):
		yield "null"

	@classmethod
	def fromul4(cls, node:ul4c.ConstAST, **vars: "Field") -> "AST":
		return cls(node.source)


class _ConstWithValueAST(ConstAST):
	"""
	Base class for all vSQL constants taht may have different values.

	(i.e. anything except ``None``).
	"""

	def __init__(self, value, *content):
		super().__init__(*content)
		self.value = value

	@classmethod
	def make(cls, value:Any) -> "ConstAST":
		return cls(value, ul4c._repr(value))

	@classmethod
	def fromul4(cls, node:ul4c.ConstAST, **vars: "Field") -> "ConstAST":
		return cls(node.value, node.source)

	@property
	def nodevalue(self) -> str:
		return self.value

	def _ll_repr_(self) -> T_gen(str):
		yield from super()._ll_repr_()
		yield f"value={self.value!r}"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("value=")
		p.pretty(self.value)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.value)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.value = decoder.load()


@ul4on.register("de.livinglogic.vsql.bool")
class BoolAST(_ConstWithValueAST):
	"""
	A boolean constant (i.e. ``True`` or ``False``).
	"""

	nodetype = NodeType.CONST_BOOL
	datatype = DataType.BOOL

	@classmethod
	def make(cls, value:Any) -> "BoolAST":
		return cls(value, "True" if value else "False")

	def _sqlsource(self, query:"Query") -> T_gen(str):
		yield "1" if self.value else "0"

	@property
	def nodevalue(self) -> str:
		return "True" if self.value else "False"


@ul4on.register("de.livinglogic.vsql.int")
class IntAST(_ConstWithValueAST):
	"""
	An integer constant.
	"""

	nodetype = NodeType.CONST_INT
	datatype = DataType.INT

	def _sqlsource(self, query:"Query") -> T_gen(str):
		yield str(self.value)

	@property
	def nodevalue(self) -> str:
		return str(self.value)


@ul4on.register("de.livinglogic.vsql.number")
class NumberAST(_ConstWithValueAST):
	"""
	A number constant (containing a decimal point).
	"""

	nodetype = NodeType.CONST_NUMBER
	datatype = DataType.NUMBER

	def _sqlsource(self, query:"Query") -> T_gen(str):
		yield str(self.value)

	@property
	def nodevalue(self) -> str:
		return repr(self.value)


@ul4on.register("de.livinglogic.vsql.str")
class StrAST(_ConstWithValueAST):
	"""
	A string constant.
	"""

	nodetype = NodeType.CONST_STR
	datatype = DataType.STR

	def _sqlsource(self, query:"Query") -> T_gen(str):
		s = self.value.replace("'", "''")
		yield f"'{s}'"


@ul4on.register("de.livinglogic.vsql.clob")
class CLOBAST(_ConstWithValueAST):
	"""
	A CLOB constant.

	This normally will not be created by the Python implementation
	"""

	nodetype = NodeType.CONST_CLOB
	datatype = DataType.CLOB

	def _sqlsource(self, query:"Query") -> T_gen(str):
		s = self.value.replace("'", "''")
		yield f"'{s}'"


@ul4on.register("de.livinglogic.vsql.color")
class ColorAST(_ConstWithValueAST):
	"""
	A color constant (e.g. ``#fff``).
	"""

	nodetype = NodeType.CONST_COLOR
	datatype = DataType.COLOR

	def _sqlsource(self, query:"Query") -> T_gen(str):
		c = self.value
		yield str((c.r() << 24) + (c.g() << 16) + (c.b() << 8) + c.a())

	@property
	def nodevalue(self) -> str:
		c = self.value
		return f"{c.r():02x}{c.g():02x}{c.b():02x}{c.a():02x}"


@ul4on.register("de.livinglogic.vsql.date")
class DateAST(_ConstWithValueAST):
	"""
	A date constant (e.g. ``@(2000-02-29)``).
	"""

	nodetype = NodeType.CONST_DATE
	datatype = DataType.DATE

	def _sqlsource(self, query:"Query") -> T_gen(str):
		yield f"to_date('{self.value:%Y-%m-%d}', 'YYYY-MM-DD')";

	@property
	def nodevalue(self) -> str:
		return f"{self.value:%Y-%m-%d}"


@ul4on.register("de.livinglogic.vsql.datetime")
class DateTimeAST(_ConstWithValueAST):
	"""
	A datetime constant (e.g. ``@(2000-02-29T12:34:56)``).
	"""

	nodetype = NodeType.CONST_DATETIME
	datatype = DataType.DATETIME

	@classmethod
	def make(cls, value:datetime.datetime) -> "DateTimeAST":
		value = value.replace(microsecond=0)
		return cls(value, ul4c._repr(value))

	def _sqlsource(self, query:"Query") -> T_gen(str):
		yield f"to_date('{self.value:%Y-%m-%d %H:%M:%S}', 'YYYY-MM-DD HH24:MI:SS')";

	@property
	def nodevalue(self) -> str:
		return f"{self.value:%Y-%m-%dT%H:%M:%S}"


class _SeqAST(AST):
	"""
	Base class of :class:`ListAST` and :class:`SetAST`.
	"""

	def __init__(self, *content:T_AST_Content):
		super().__init__(*content)
		self.items = [item for item in content if isinstance(item, AST)]
		self.datatype = None
		self.validate()

	@classmethod
	def fromul4(cls, node:ul4c.AST, **vars: "Field") -> "AST":
		content = []

		lastpos = None # This value is never used
		for item in node.items:
			if not isinstance(item, ul4c.SeqItemAST):
				raise TypeError(f"Can't compile UL4 expression of type {misc.format_class(item)}!")
			content.append(item.value)
			content.append(AST.fromul4(item.value, **vars))
		return cls(*cls._make_content_from_ul4(node, *content))

	def _sqlsource(self, query:"Query") -> T_gen(str):
		if self.datatype is self.nulltype:
			yield self.nodevalue
		else:
			(prefix, suffix) = self.sqltypes[self.datatype]
			yield prefix
			for (i, item) in enumerate(self.items):
				if i:
					yield ", "
				yield from item._sqlsource(query)
			yield suffix

	def _ll_repr_(self) -> T_gen(str):
		yield from super()._ll_repr_()
		yield f"with {len(self.items):,} items"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		for item in self.items:
			p.breakable()
			p.pretty(item)

	def children(self) -> T_gen("AST"):
		yield from self.items

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.items)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.items = decoder.load()


@ul4on.register("de.livinglogic.vsql.list")
class ListAST(_SeqAST):
	"""
	A list constant.

	For this to work the list may only contain items of "compatible" types, i.e.
	types that con be converted to a common type without losing information.
	"""

	nodetype = NodeType.LIST
	nulltype = DataType.NULLLIST
	precedence = 20

	sqltypes = {
		DataType.INTLIST: ("integers(", ")"),
		DataType.NUMBERLIST: ("numbers(", ")"),
		DataType.STRLIST: ("varchars(", ")"),
		DataType.CLOBLIST: ("clobs(", ")"),
		DataType.DATELIST: ("dates(", ")"),
		DataType.DATETIMELIST: ("dates(", ")"),
	}

	def __init__(self, *content:T_AST_Content):
		super().__init__(*content)
		self.validate()

	@classmethod
	def make(cls, *items:"AST") -> "ListAST":
		if items:
			content = []
			for (i, item) in enumerate(items):
				content.append(", " if i else "[")
				content.append(item)
			content.append("]")
			return cls(*content)
		else:
			return cls("[]")

	def validate(self) -> None:
		if any(item.error for item in self.items):
			self.error = Error.SUBNODEERROR
			self.datatype = None
		else:
			types = {item.datatype for item in self.items}
			if DataType.NULL in types:
				types.remove(DataType.NULL)
			if not types:
				self.error = None
				self.datatype = DataType.NULLLIST
			elif len(types) == 1:
				self.error = None
				datatype = misc.first(types)
				if datatype is DataType.INT:
					datatype = DataType.INTLIST
				elif datatype is DataType.NUMBER:
					datatype = DataType.NUMBERLIST
				elif datatype is DataType.STR:
					datatype = DataType.STRLIST
				elif datatype is DataType.CLOB:
					datatype = DataType.CLOBLIST
				elif datatype is DataType.DATE:
					datatype = DataType.DATELIST
				elif datatype is DataType.DATETIME:
					datatype = DataType.DATETIMELIST
				else:
					datatype = None
				self.datatype = datatype
				self.error = None if datatype else Error.LISTUNSUPPORTEDTYPES
			else:
				self.error = Error.LISTMIXEDTYPES
				self.datatype = None

	@property
	def nodevalue(self) -> str:
		return str(len(self.items)) if self.datatype is DataType.NULLLIST else None


@ul4on.register("de.livinglogic.vsql.set")
class SetAST(_SeqAST):
	"""
	A set constant.

	For this to work the set may only contain items of "compatible" types, i.e.
	types that can be converted to a common type without losing information.
	"""

	nodetype = NodeType.SET
	nulltype = DataType.NULLSET
	precedence = 20

	sqltypes = {
		DataType.INTSET: ("vsqlimpl_pkg.set_intlist(integers(", "))"),
		DataType.NUMBERSET: ("vsqlimpl_pkg.set_numberlist(numbers(", "))"),
		DataType.STRSET: ("vsqlimpl_pkg.set_strlist(varchars(", "))"),
		DataType.DATESET: ("vsqlimpl_pkg.set_datetimelist(dates(", "))"),
		DataType.DATETIMESET: ("vsqlimpl_pkg.set_datetimelist(dates(", "))"),
	}

	def __init__(self, *content:T_AST_Content):
		super().__init__(*content)
		self.validate()

	@classmethod
	def make(cls, *items:"AST") -> "SetAST":
		if items:
			content = []
			for (i, item) in enumerate(items):
				content.append(", " if i else "{")
				content.append(item)
			content.append("}")
			return cls(*content)
		else:
			return cls("{/}")

	def validate(self) -> None:
		if any(item.error for item in self.items):
			self.error = Error.SUBNODEERROR
			self.datatype = None
		else:
			types = {item.datatype for item in self.items}
			if DataType.NULL in types:
				types.remove(DataType.NULL)
			if not types:
				self.error = None
				self.datatype = DataType.NULLSET
			elif len(types) == 1:
				self.error = None
				datatype = misc.first(types)
				if datatype is DataType.INT:
					datatype = DataType.INTSET
				elif datatype is DataType.NUMBER:
					datatype = DataType.NUMBERSET
				elif datatype is DataType.STR:
					datatype = DataType.STRSET
				elif datatype is DataType.DATE:
					datatype = DataType.DATESET
				elif datatype is DataType.DATETIME:
					datatype = DataType.DATETIMESET
				else:
					datatype = None
				self.datatype = datatype
				self.error = None if datatype else Error.SETUNSUPPORTEDTYPES
			else:
				self.error = Error.SETMIXEDTYPES
				self.datatype = None

	@property
	def nodevalue(self) -> str:
		return str(len(self.items)) if self.datatype is DataType.NULLSET else None


@ul4on.register("de.livinglogic.vsql.fieldref")
class FieldRefAST(AST):
	"""
	Reference to a field defined in the database.
	"""

	nodetype = NodeType.FIELD
	precedence = 19

	def __init__(self, parent:Optional["FieldRefAST"], identifier:str, field:Optional["Field"], *content:T_AST_Content):
		"""
		Create a :class:`FieldRef` object.

		There are three possible scenarios with respect to ``identifier`` and
		``field``:

		``field is not None and field.identifier == identifier``
			In this case we have a valid :class:`Field` that describes a real
			field.

		``field is not None and field.identifier != identifier and field.identifier == "*"``
			In this case :obj:`field` is the :class:`Field` object for the generic
			typed request parameters. E.g. when the vSQL expression is
			``params.str.foo`` then :obj:`field` references the :class:`Field` for
			``params.str.*``, so ``field.identifier == "*" and
			identifier == "foo"``.

		``field is None``
			In this case the field is unknown.
		"""
		super().__init__(*content)
		self.parent = parent
		# Note that ``identifier`` might be different from ``field.identifier``
		# if ``field.identifier == "*"``.
		self.identifier = identifier
		# Note that ``field`` might be ``None`` when the field can't be found.
		self.field = field
		self.validate()

	@classmethod
	def make_root(cls, field:Union[str, "Field"]) -> "FieldRefAST":
		if isinstance(field, str):
			# This is an invalid field reference
			return FieldRefAST(None, field, None, field)
		else:
			return FieldRefAST(None, field.identifier, field, field.identifier)

	@classmethod
	def make(cls, parent:"FieldRefAST", identifier:str) -> "FieldRefAST":
		result_field = None
		parent_field = parent.field
		if parent_field is not None:
			group = parent_field.refgroup
			if group is not None:
				try:
					result_field = group[identifier]
				except KeyError:
					pass

		return FieldRefAST(parent, identifier, result_field, parent, ".", identifier)

	def _sqlsource(self, query:"Query") -> T_gen(str):
		alias = query._vsql_register(self)
		full_identifier = self.full_identifier
		if full_identifier.startswith("params."):
			# If the innermost field is "params" we need special treatment
			yield f"livingapi_pkg.reqparam_{self.parent.identifier}('{self.identifier}') /* {self.source()} */"
		elif alias is None:
			yield f"{self.field.fieldsql} /* {self.source()} */"
		else:
			yield f"{alias}.{self.field.fieldsql} /* {self.source()} */"

	def validate(self) -> None:
		self.error = Error.FIELD if self.field is None else None

	@property
	def datatype(self) -> Optional[DataType]:
		return self.field.datatype if self.field is not None else None

	@property
	def nodevalue(self) -> str:
		identifierpath = []
		node = self
		while node is not None:
			identifierpath.insert(0, node.identifier)
			node = node.parent
		return ".".join(identifierpath)

	def fieldrefs(self) -> T_gen("FieldRefAST"):
		yield self
		yield from super().fieldrefs()

	@property
	def full_identifier(self) -> Tuple[str]:
		if self.parent is None:
			return self.identifier
		else:
			return f"{self.parent.full_identifier}.{self.identifier}"

	def _ll_repr_(self) -> T_gen(str):
		yield from super()._ll_repr_()
		if self.field is None or self.field.identifier != self.identifier:
			yield f"identifier={self.identifier!r}"
		if self.field is not None:
			yield f"field={self.field!r}"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("identifier=")
		p.pretty(self.identifier)
		if self.field is None or self.field.identifier != self.identifier:
			p.breakable()
			p.text("identifier=")
			p.pretty(self.identifier)
		if self.field is not None:
			p.breakable()
			p.text("field=")
			p.pretty(self.field)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.parent)
		encoder.dump(self.identifier)
		encoder.dump(self.field)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.parent = decoder.load()
		self.identifier = decoder.load()
		self.field = decoder.load()


class BinaryAST(AST):
	"""
	Base class of all binary expressions (i.e. expressions with two operands).
	"""

	def __init__(self, obj1:AST, obj2:AST, *content:T_AST_Content):
		super().__init__(*content)
		self.obj1 = obj1
		self.obj2 = obj2
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj1:AST, obj2:AST) -> "BinaryAST":
		return cls(
			obj1,
			obj2,
			*cls._wrap(obj1, obj1.precedence < cls.precedence),
			f" {cls.operator} ",
			*cls._wrap(obj2, obj2.precedence <= cls.precedence),
		)

	def validate(self) -> None:
		if self.obj1.error or self.obj2.error:
			self.error = Error.SUBNODEERROR
		signature = (self.obj1.datatype, self.obj2.datatype)
		try:
			rule = self.rules[signature]
		except KeyError:
			self.error = Error.SUBNODETYPES
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	@classmethod
	def fromul4(cls, node:ul4c.BinaryAST, **vars: "Field") -> "AST":
		obj1 = AST.fromul4(node.obj1, **vars)
		obj2 = AST.fromul4(node.obj2, **vars)
		return cls(
			obj1,
			obj2,
			*cls._make_content_from_ul4(node, node.obj1, obj1, node.obj2, obj2),
		)

	def _sqlsource(self, query:"Query") -> T_gen(str):
		rule = self.rules[(self.obj1.datatype, self.obj2.datatype)]
		result = []
		for child in rule.source:
			if child == 1:
				yield from self.obj1._sqlsource(query)
			elif child == 2:
				yield from self.obj2._sqlsource(query)
			else:
				yield child

	def children(self) -> T_gen(AST):
		yield self.obj1
		yield self.obj2

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj1=")
		p.pretty(self.obj1)
		p.breakable()
		p.text("obj2=")
		p.pretty(self.obj2)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.obj1)
		encoder.dump(self.obj2)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.obj1 = decoder.load()
		self.obj2 = decoder.load()


@ul4on.register("de.livinglogic.vsql.eq")
class EQAST(BinaryAST):
	"""
	Equality comparison (``A == B``).
	"""

	nodetype = NodeType.CMP_EQ
	precedence = 6
	operator = "=="


@ul4on.register("de.livinglogic.vsql.ne")
class NEAST(BinaryAST):
	"""
	Inequality comparison (``A != B``).
	"""

	nodetype = NodeType.CMP_NE
	precedence = 6
	operator = "!="


@ul4on.register("de.livinglogic.vsql.lt")
class LTAST(BinaryAST):
	"""
	Less-than comparison (``A < B``).
	"""

	nodetype = NodeType.CMP_LT
	precedence = 6
	operator = "<"


@ul4on.register("de.livinglogic.vsql.le")
class LEAST(BinaryAST):
	"""
	Less-than-or equal comparison (``A <= B``).
	"""

	nodetype = NodeType.CMP_LE
	precedence = 6
	operator = "<="


@ul4on.register("de.livinglogic.vsql.gt")
class GTAST(BinaryAST):
	"""
	Greater-than comparison (``A > B``).
	"""

	nodetype = NodeType.CMP_GT
	precedence = 6
	operator = ">"


@ul4on.register("de.livinglogic.vsql.ge")
class GEAST(BinaryAST):
	"""
	Greater-than-or equal comparison (``A >= B``).
	"""

	nodetype = NodeType.CMP_GE
	precedence = 6
	operator = ">="


@ul4on.register("de.livinglogic.vsql.add")
class AddAST(BinaryAST):
	"""
	Addition (``A + B``).
	"""

	nodetype = NodeType.BINOP_ADD
	precedence = 11
	operator = "+"


@ul4on.register("de.livinglogic.vsql.sub")
class SubAST(BinaryAST):
	"""
	Subtraction (``A - B``).
	"""

	nodetype = NodeType.BINOP_SUB
	precedence = 11
	operator = "-"


@ul4on.register("de.livinglogic.vsql.mul")
class MulAST(BinaryAST):
	"""
	Multiplication (``A * B``).
	"""

	nodetype = NodeType.BINOP_MUL
	precedence = 12
	operator = "*"


@ul4on.register("de.livinglogic.vsql.truediv")
class TrueDivAST(BinaryAST):
	"""
	True division (``A / B``).
	"""

	nodetype = NodeType.BINOP_TRUEDIV
	precedence = 12
	operator = "/"


@ul4on.register("de.livinglogic.vsql.floordiv")
class FloorDivAST(BinaryAST):
	"""
	Floor division (``A // B``).
	"""

	nodetype = NodeType.BINOP_FLOORDIV
	precedence = 12
	operator = "//"


@ul4on.register("de.livinglogic.vsql.mod")
class ModAST(BinaryAST):
	"""
	Modulo operator (``A % B``).
	"""

	nodetype = NodeType.BINOP_MOD
	precedence = 12
	operator = "%"


@ul4on.register("de.livinglogic.vsql.shiftleft")
class ShiftLeftAST(BinaryAST):
	"""
	Left shift operator (``A << B``).
	"""

	nodetype = NodeType.BINOP_SHIFTLEFT
	precedence = 10
	operator = "<<"


@ul4on.register("de.livinglogic.vsql.shiftright")
class ShiftRightAST(BinaryAST):
	"""
	Right shift operator (``A >> B``).
	"""

	nodetype = NodeType.BINOP_SHIFTRIGHT
	precedence = 10
	operator = ">>"


@ul4on.register("de.livinglogic.vsql.and")
class AndAST(BinaryAST):
	"""
	Logical "and" (``A and B``).
	"""

	nodetype = NodeType.BINOP_AND
	precedence = 4
	operator = "and"


@ul4on.register("de.livinglogic.vsql.or")
class OrAST(BinaryAST):
	"""
	Logical "or" (``A or B``).
	"""

	nodetype = NodeType.BINOP_OR
	precedence = 4
	operator = "or"


@ul4on.register("de.livinglogic.vsql.contains")
class ContainsAST(BinaryAST):
	"""
	Containment test (``A in B``).
	"""

	nodetype = NodeType.BINOP_CONTAINS
	precedence = 6
	operator = "in"


@ul4on.register("de.livinglogic.vsql.notcontains")
class NotContainsAST(BinaryAST):
	"""
	Inverted containment test (``A not in B``).
	"""

	nodetype = NodeType.BINOP_NOTCONTAINS
	precedence = 6
	operator = "not in"


@ul4on.register("de.livinglogic.vsql.is")
class IsAST(BinaryAST):
	"""
	Identity test (``A is B``).
	"""

	nodetype = NodeType.BINOP_IS
	precedence = 6
	operator = "is"


@ul4on.register("de.livinglogic.vsql.isnot")
class IsNotAST(BinaryAST):
	"""
	Inverted identity test (``A is not B``).
	"""

	nodetype = NodeType.BINOP_ISNOT
	precedence = 6
	operator = "is not"


@ul4on.register("de.livinglogic.vsql.item")
class ItemAST(BinaryAST):
	"""
	Item access operator (``A[B]``).
	"""

	nodetype = NodeType.BINOP_ITEM
	precedence = 16

	@classmethod
	def make(self, obj1:AST, obj2:AST) -> "ItemAST":
		if obj1.precedence >= self.precedence:
			return cls(obj1, obj2, obj1, "[", obj2, "]")
		else:
			return cls(obj1, obj2, "(", obj1, ")[", obj2, "]")

	@classmethod
	def fromul4(cls, node:ul4c.ItemAST, **vars: "Field") -> "AST":
		if isinstance(node.obj2, ul4c.SliceAST):
			return SliceAST.fromul4(node, **vars)
		return super().fromul4(node, **vars)


@ul4on.register("de.livinglogic.vsql.bitand")
class BitAndAST(BinaryAST):
	"""
	Bitwise "and" (``A & B``).
	"""

	nodetype = NodeType.BINOP_BITAND
	precedence = 9
	operator = "&"


@ul4on.register("de.livinglogic.vsql.bitor")
class BitOrAST(BinaryAST):
	"""
	Bitwise "or" (``A | B``).
	"""

	nodetype = NodeType.BINOP_BITOR
	precedence = 7
	operator = "|"


@ul4on.register("de.livinglogic.vsql.bitxor")
class BitXOrAST(BinaryAST):
	"""
	Bitwise "exclusive or" (``A ^ B``).
	"""

	nodetype = NodeType.BINOP_BITXOR
	precedence = 8
	operator = "^"


class UnaryAST(AST):
	"""
	Base class of all unary expressions (i.e. expressions with one operand).
	"""

	def __init__(self, obj:AST, *content:T_AST_Content):
		super().__init__(*content)
		self.obj = obj
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj:AST) -> "UnaryAST":
		return cls(
			obj,
			cls.operator,
			*cls._wrap(obj, obj.precedence <= cls.precedence),
		)

	@classmethod
	def fromul4(cls, node:ul4c.UnaryAST, **vars: "Field") -> "AST":
		obj = AST.fromul4(node.obj, **vars)
		return cls(
			obj,
			*cls._make_content_from_ul4(node, node.obj, obj),
		)

	def validate(self) -> None:
		if self.obj.error:
			self.error = Error.SUBNODEERROR
		signature = (self.obj.datatype,)
		try:
			rule = self.rules[signature]
		except KeyError:
			self.error = Error.SUBNODETYPES
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	def _sqlsource(self, query:"Query") -> T_gen(str):
		rule = self.rules[(self.obj.datatype, )]
		result = []
		for child in rule.source:
			if child == 1:
				yield from self.obj._sqlsource(query)
			else:
				yield child

	def children(self) -> T_gen(AST):
		yield self.obj

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.obj)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.obj = decoder.load()


@ul4on.register("de.livinglogic.vsql.not")
class NotAST(UnaryAST):
	"""
	Logical negation (``not A``).
	"""

	nodetype = NodeType.UNOP_NOT
	precedence = 5
	operator = "not "


@ul4on.register("de.livinglogic.vsql.neg")
class NegAST(UnaryAST):
	"""
	Arithmetic negation (``-A``).
	"""

	nodetype = NodeType.UNOP_NEG
	precedence = 14
	operator = "-"


@ul4on.register("de.livinglogic.vsql.bitnot")
class BitNotAST(UnaryAST):
	"""
	Bitwise "not" (``~A``).
	"""

	nodetype = NodeType.UNOP_BITNOT
	precedence = 14
	operator = "~"


@ul4on.register("de.livinglogic.vsql.if")
class IfAST(AST):
	"""
	Ternary "if"/"else" (``A if COND else B``).
	"""

	nodetype = NodeType.TERNOP_IF
	precedence = 3

	def __init__(self, objif:AST, objcond:AST, objelse:AST, *content:T_AST_Content):
		super().__init__(*content)
		self.objif = objif
		self.objcond = objcond
		self.objelse = objelse
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, objif:AST, objcond:AST, objelse:AST) -> "IfAST":
		return cls(
			objif,
			objcond,
			objelse,
			*cls._wrap(objif, objif.precedence <= cls.precedence),
			" if ",
			*cls._wrap(objcond, objcond.precedence <= cls.precedence),
			" else ",
			*cls._wrap(objelse, objcond.precedence <= cls.precedence),
		)

	def validate(self) -> None:
		if self.objif.error or self.objcond.error or self.objelse.error:
			self.error = Error.SUBNODEERROR
		signature = (self.objif.datatype, self.objcond.datatype, self.objelse.datatype)
		try:
			rule = self.rules[signature]
		except KeyError:
			self.error = Error.SUBNODETYPES
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	@classmethod
	def fromul4(cls, node:ul4c.IfAST, **vars: "Field") -> "IfAST":
		objif = AST.fromul4(node.objif, **vars)
		objcond = AST.fromul4(node.objcond, **vars)
		objelse = AST.fromul4(node.objelse, **vars)

		return cls(
			objif,
			objcond,
			objelse,
			*cls._make_content_from_ul4(node, node.objif, objif, node.objcond, objcond, node.objelse, objelse),
		)

	def _sqlsource(self, query:"Query") -> T_gen(str):
		rule = self.rules[(self.objif.datatype, self.objcond.datatype, self.objelse.datatype)]
		result = []
		for child in rule.source:
			if child == 1:
				yield from self.objif._sqlsource(query)
			elif child == 2:
				yield from self.objcond._sqlsource(query)
			elif child == 3:
				yield from self.objelse._sqlsource(query)
			else:
				yield child

	def children(self) -> T_gen(AST):
		yield self.objif
		yield self.objcond
		yield self.objelse

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("objif=")
		p.pretty(self.objif)
		p.breakable()
		p.text("objcond=")
		p.pretty(self.objcond)
		p.breakable()
		p.text("objelse=")
		p.pretty(self.objelse)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.objif)
		encoder.dump(self.objcond)
		encoder.dump(self.objelse)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.objif = decoder.load()
		self.objcond = decoder.load()
		self.objelse = decoder.load()


@ul4on.register("de.livinglogic.vsql.if")
class SliceAST(AST):
	"""
	Slice operator (``A[B:C]``).
	"""

	nodetype = NodeType.TERNOP_SLICE
	precedence = 16

	def __init__(self, obj:AST, index1:T_opt_ast, index2:T_opt_ast, *content:T_AST_Content):
		super().__init__(*content)
		self.obj = obj
		self.index1 = index1
		self.index2 = index2
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj:AST, index1:T_opt_ast, index2:T_opt_ast) -> "SliceAST":
		if index1 is None:
			index1 = NoneAST(None)
		if index2 is None:
			index2 = NoneAST(None)

		return cls(
			obj,
			index1,
			index2,
			*cls._wrap(obj, obj.precedence < cls.precedence),
			"[",
			index1,
			":",
			index2,
			"]",
		)

	def validate(self) -> None:
		if self.obj.error or self.index1.error or self.index2.error:
			self.error = Error.SUBNODEERROR
		signature = (self.obj.datatype, self.index1.datatype, self.index2.datatype)
		try:
			rule = self.rules[signature]
		except KeyError:
			self.error = Error.SUBNODETYPES
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	@classmethod
	def fromul4(cls, node:ul4c.ItemAST, **vars: "Field") -> "AST":
		obj = AST.fromul4(node.obj1, **vars)
		index1 = AST.fromul4(node.obj2.index1, **vars) if node.obj2.index1 is not None else NoneAST("")
		index2 = AST.fromul4(node.obj2.index2, **vars) if node.obj2.index2 is not None else NoneAST("")

		return cls(
			obj,
			index1,
			index2,
			*cls._make_content_from_ul4(node, node.obj1, obj, node.obj2.index1, index1, node.obj2.index2, index2)
		)

	def _sqlsource(self, query:"Query") -> T_gen(str):
		rule = self.rules[(self.obj.datatype, self.index1.datatype, self.index2.datatype)]
		result = []
		for child in rule.source:
			if child == 1:
				yield from self.obj._sqlsource(query)
			elif child == 2:
				yield from self.index1._sqlsource(query)
			elif child == 3:
				yield from self.index2._sqlsource(query)
			else:
				yield child

	def children(self) -> T_gen(AST):
		yield self.obj
		yield self.index1 if self.index1 is None else NoneAST("")
		yield self.index2 if self.index2 is None else NoneAST("")

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)
		if self.index1 is not None:
			p.breakable()
			p.text("index1=")
			p.pretty(self.index1)
		if self.index2 is not None:
			p.breakable()
			p.text("index2=")
			p.pretty(self.index2)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.obj)
		encoder.dump(self.index1)
		encoder.dump(self.index1)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.obj = decoder.load()
		self.index1 = decoder.load()
		self.index2 = decoder.load()


@ul4on.register("de.livinglogic.vsql.attr")
class AttrAST(AST):
	"""
	Attribute access (``A.name``).
	"""

	nodetype = NodeType.ATTR
	precedence = 19

	def __init__(self, obj:AST, attrname:str, *content:T_AST_Content):
		super().__init__(*content)
		self.obj = obj
		self.attrname = attrname
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj:AST, attrname:str) -> "AttrAST":
		return cls(
			obj,
			attrname,
			*cls._wrap(obj, obj.precedence < cls.precedence),
			".",
			attrname,
		)

	def validate(self) -> None:
		if self.obj.error:
			self.error = Error.SUBNODEERROR
		signature = (self.obj.datatype, self.attrname)
		try:
			rule = self.rules[signature]
		except KeyError:
			self.error = Error.SUBNODETYPES
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	def _sqlsource(self, query:"Query") -> T_gen(str):
		rule = self.rules[(self.obj.datatype, self.attrname)]
		for child in rule.source:
			if child == 1:
				yield from self.obj._sqlsource(query)
			else:
				yield child

	@property
	def nodevalue(self) -> str:
		return self.attrname

	def children(self) -> T_gen(AST):
		yield self.obj

	def _ll_repr_(self) -> T_gen(str):
		yield from super()._ll_repr_()
		yield f"attrname={self.attrname!r}"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)
		p.breakable()
		p.text("attrname=")
		p.pretty(self.attrname)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.obj)
		encoder.dump(self.attrname)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.obj = decoder.load()
		self.attrname = decoder.load()


@ul4on.register("de.livinglogic.vsql.func")
class FuncAST(AST):
	"""
	Function call (``name(A, ...)``).
	"""

	nodetype = NodeType.FUNC
	precedence = 18
	names = {} # Maps function names to set of supported arities

	def __init__(self, name:str, args:Tuple[AST, ...], *content:T_AST_Content):
		super().__init__(*content)
		self.name = name
		self.args = args
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, name:str, *args:AST) -> "FuncAST":
		content = [name, "("]
		for (i, arg) in enumerate(args):
			if i:
				content.append(", ")
			content.append(arg)
		content.append(")")

		return cls(name, args, *content)

	def _sqlsource(self, query:"Query") -> T_gen(str):
		rule = self.rules[(self.name,) + tuple(c.datatype for c in self.args)]
		result = []
		for child in rule.source:
			if isinstance(child, int):
				yield from self.args[child-1]._sqlsource(query)
			else:
				yield child

	@classmethod
	def _add_rule(cls, rule:Rule) -> None:
		super()._add_rule(rule)
		if rule.name not in cls.names:
			cls.names[rule.name] = set()
		cls.names[rule.name].add(len(rule.signature))

	def validate(self) -> None:
		if any(arg.error is not None for arg in self.args):
			self.error = Error.SUBNODEERROR
		signature = (self.name, *(arg.datatype for arg in self.args))
		try:
			rule = self.rules[signature]
		except KeyError:
			if self.name not in self.names:
				self.error = Error.NAME
			elif len(self.args) not in self.names[self.name]:
				self.error = Error.ARITY
			else:
				self.error = Error.SUBNODETYPES
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	@property
	def nodevalue(self) -> str:
		return self.name

	def children(self) -> T_gen(AST):
		yield from self.args

	def _ll_repr_(self) -> T_gen(str):
		yield from super()._ll_repr_()
		yield f"name={self.name!r}"
		yield f"with {len(self.args):,} arguments"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		for (i, arg) in enumerate(self.args):
			p.breakable()
			p.text(f"args[{i}]=")
			p.pretty(arg)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.name)
		encoder.dump(self.args)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.name = decoder.load()
		self.args = decoder.load()


@ul4on.register("de.livinglogic.vsql.meth")
class MethAST(AST):
	"""
	Method call (``A.name(B, ...)``).
	"""

	nodetype = NodeType.METH
	precedence = 17
	names = {} # Maps (type, meth name) to set of supported arities

	def __init__(self, obj:AST, name:str, args:Tuple[AST, ...], *content:T_AST_Content):
		super().__init__(*content)
		self.obj = obj
		self.name = name
		self.args = args or ()
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj:AST, name:str, *args:AST) -> "MethAST":
		content = [*cls._wrap(obj, obj.precedence < cls.precedence), ".", name, "("]
		for (i, arg) in enumerate(args):
			if i:
				content.append(", ")
			content.append(arg)
		content.append(")")

		return cls(obj, name, args, *content)

	def _sqlsource(self, query:"Query") -> T_gen(str):
		rule = self.rules[(self.obj.datatype, self.name) + tuple(c.datatype for c in self.args)]
		result = []
		for child in rule.source:
			if isinstance(child, int):
				if child == 1:
					yield from self.obj._sqlsource(query)
				else:
					yield from self.args[child-2]._sqlsource(query)
			else:
				yield child

	@classmethod
	def _add_rule(cls, rule:Rule) -> None:
		super()._add_rule(rule)
		key = (rule.signature[0], rule.name)
		if key not in cls.names:
			cls.names[key] = set()
		cls.names[key].add(len(rule.signature)-1)

	def validate(self) -> None:
		if self.obj.error is not None or any(arg.error is not None for arg in self.args):
			self.error = Error.SUBNODEERROR
		signature = (self.obj.datatype, self.name, *(arg.datatype for arg in self.args))
		try:
			rule = self.rules[signature]
		except KeyError:
			key = (self.obj.datatype, self.name)
			if key not in self.names:
				self.error = Error.NAME
			elif len(self.args) not in self.names[key]:
				self.error = Error.ARITY
			else:
				self.error = Error.SUBNODETYPES
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	@property
	def nodevalue(self) -> str:
		return self.name

	def children(self) -> T_gen(AST):
		yield self.obj
		yield from self.args

	def _ll_repr_(self) -> T_gen(str):
		yield from super()._ll_repr_()
		yield f"name={self.name!r}"
		yield f"with {len(self.args):,} arguments"

	def _ll_repr_pretty_(self, p:"IPython.lib.pretty.PrettyPrinter") -> None:
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)
		p.breakable()
		p.text("name=")
		p.pretty(self.name)
		for (i, arg) in enumerate(self.args):
			p.breakable()
			p.text(f"args[{i}]=")
			p.pretty(arg)

	def ul4ondump(self, encoder:ul4on.Encoder) -> None:
		super().ul4ondump(encoder)
		encoder.dump(self.obj)
		encoder.dump(self.name)
		encoder.dump(self.args)

	def ul4onload(self, decoder:ul4on.Decoder) -> None:
		super().ul4onload(decoder)
		self.obj = decoder.load()
		self.name = decoder.load()
		self.args = decoder.load()


_consts = {
	type(None): NoneAST,
	bool: BoolAST,
	int: IntAST,
	float: NumberAST,
	str: StrAST,
	color.Color: ColorAST,
	datetime.date: DateAST,
	datetime.datetime: DateTimeAST,
}

# Set of UL4 AST nodes that directly map to their equivalent vSQL version
_ops = {
	ul4c.ConstAST,
	ul4c.NotAST,
	ul4c.NegAST,
	ul4c.BitNotAST,
	*ul4c.BinaryAST.__subclasses__(),
	ul4c.IfAST,
	ul4c.SliceAST,
	ul4c.ListAST,
	ul4c.SetAST
}

# Create the mapping that maps the UL4 AST type to the vSQL AST type
v = vars()
_ul42vsql = {cls: v[cls.__name__] for cls in _ops}

# Remove temporary variables
del _ops, v


###
### Create vSQL rules for all AST classes for validating datatypes and type inference
###

# Subsets of datatypes

INTLIKE = f"BOOL_INT"
NUMBERLIKE = f"{INTLIKE}_NUMBER"
NUMBERSTORED = f"BOOL_INT_NUMBER_COLOR_DATEDELTA_DATETIMEDELTA_MONTHDELTA"

TEXT = f"STR_CLOB"
LIST = f"INTLIST_NUMBERLIST_STRLIST_CLOBLIST_DATELIST_DATETIMELIST"
SET = f"INTSET_NUMBERSET_STRSET_DATESET_DATETIMESET"
SEQ = f"{TEXT}_{LIST}_{SET}"
ANY = "_".join(DataType.__members__.keys())

# Field references and constants (will not be used for generating source,
# but for checking that the node type is valid and that they have no child nodes)
FieldRefAST.add_rules(f"NULL", "")
NoneAST.add_rules(f"NULL", "")
BoolAST.add_rules(f"BOOL", "")
IntAST.add_rules(f"INT", "")
NumberAST.add_rules(f"NUMBER", "")
StrAST.add_rules(f"STR", "")
CLOBAST.add_rules(f"CLOB", "")
ColorAST.add_rules(f"COLOR", "")
DateAST.add_rules(f"DATE", "")
DateTimeAST.add_rules(f"DATETIME", "")

# Function ``today()``
FuncAST.add_rules(f"DATE today", "trunc(sysdate)")

# Function ``now(0``
FuncAST.add_rules(f"DATETIME now", "sysdate")

# Function ``bool()``
FuncAST.add_rules(f"BOOL <- bool()", "0")
FuncAST.add_rules(f"BOOL <- bool(NULL)", "0")
FuncAST.add_rules(f"BOOL <- bool(BOOL)", "{s1}")
FuncAST.add_rules(f"BOOL <- bool(INT_NUMBER_DATEDELTA_DATETIMEDELTA_MONTHDELTA_NULLLIST_NULLSET)", "(case when nvl({s1}, 0) = 0 then 0 else 1 end)")
FuncAST.add_rules(f"BOOL <- bool(DATE_DATETIME_STR_COLOR_GEO)", "(case when {s1} is null then 0 else 1 end)")
FuncAST.add_rules(f"BOOL <- bool({ANY})", "vsqlimpl_pkg.bool_{t1}({s1})")

# Function ``int()``
FuncAST.add_rules(f"INT <- int()", "0")
FuncAST.add_rules(f"INT <- int({INTLIKE})", "{s1}")
FuncAST.add_rules(f"INT <- int(NUMBER_STR_CLOB)", "vsqlimpl_pkg.int_{t1}({s1})")

# Function ``float()``
FuncAST.add_rules(f"NUMBER <- float()", "0.0")
FuncAST.add_rules(f"NUMBER <- float({NUMBERLIKE})", "{s1}")
FuncAST.add_rules(f"NUMBER <- float({TEXT})", "vsqlimpl_pkg.float_{t1}({s1})")

# Function ``geo()``
FuncAST.add_rules(f"GEO <- geo({NUMBERLIKE}, {NUMBERLIKE})", "vsqlimpl_pkg.geo_number_number_str({s1}, {s2}, null)")
FuncAST.add_rules(f"GEO <- geo({NUMBERLIKE}, {NUMBERLIKE}, STR)", "vsqlimpl_pkg.geo_number_number_str({s1}, {s2}, {s3})")

# Function ``str()``
FuncAST.add_rules(f"STR <- str()", "null")
FuncAST.add_rules(f"STR <- str(NULL)", "null")
FuncAST.add_rules(f"STR <- str(STR)", "{s1}")
FuncAST.add_rules(f"CLOB <- str(CLOB)", "{s1}")
FuncAST.add_rules(f"STR <- str(BOOL)", "(case {s1} when 0 then 'False' when null then 'None' else 'True' end)")
FuncAST.add_rules(f"STR <- str(INT)", "to_char({s1})")
FuncAST.add_rules(f"STR <- str(NUMBER)", "vsqlimpl_pkg.str_number({s1})")
FuncAST.add_rules(f"STR <- str(GEO)", "vsqlimpl_pkg.repr_geo({s1})")
FuncAST.add_rules(f"STR <- str(DATE)", "to_char({s1}, 'YYYY-MM-DD')")
FuncAST.add_rules(f"STR <- str(DATETIME)", "to_char({s1}, 'YYYY-MM-DD HH24:MI:SS')")
FuncAST.add_rules(f"STR <- str(NULLLIST)", "vsqlimpl_pkg.repr_nulllist({s1})")
FuncAST.add_rules(f"STR <- str(DATELIST)", "vsqlimpl_pkg.repr_datelist({s1})")
FuncAST.add_rules(f"STR <- str({LIST})", "vsqlimpl_pkg.repr_{t1}({s1})")
FuncAST.add_rules(f"STR <- str(NULLSET)", "vsqlimpl_pkg.repr_nullset({s1})")
FuncAST.add_rules(f"STR <- str(INTSET)", "vsqlimpl_pkg.repr_intset({s1})")
FuncAST.add_rules(f"STR <- str(NUMBERSET)", "vsqlimpl_pkg.repr_numberset({s1})")
FuncAST.add_rules(f"STR <- str(STRSET)", "vsqlimpl_pkg.repr_strset({s1})")
FuncAST.add_rules(f"STR <- str(DATESET)", "vsqlimpl_pkg.repr_dateset({s1})")
FuncAST.add_rules(f"STR <- str(DATETIMESET)", "vsqlimpl_pkg.repr_datetimeset({s1})")
FuncAST.add_rules(f"STR <- str({ANY})", "vsqlimpl_pkg.str_{t1}({s1})")

# Function ``repr()``
FuncAST.add_rules(f"STR <- repr(NULL)", "'None'")
FuncAST.add_rules(f"STR <- repr(BOOL)", "(case {s1} when 0 then 'False' when null then 'None' else 'True' end)")
FuncAST.add_rules(f"CLOB <- repr(CLOB_CLOBLIST)", "vsqlimpl_pkg.repr_{t1}({s1})")
FuncAST.add_rules(f"STR <- repr(DATE)", "vsqlimpl_pkg.repr_date({s1})")
FuncAST.add_rules(f"STR <- repr(DATELIST)", "vsqlimpl_pkg.repr_datelist({s1})")
FuncAST.add_rules(f"STR <- repr(NULLSET)", "vsqlimpl_pkg.repr_nullset({s1})")
FuncAST.add_rules(f"STR <- repr(INTSET)", "vsqlimpl_pkg.repr_intset({s1})")
FuncAST.add_rules(f"STR <- repr(NUMBERSET)", "vsqlimpl_pkg.repr_numberset({s1})")
FuncAST.add_rules(f"STR <- repr(STRSET)", "vsqlimpl_pkg.repr_strset({s1})")
FuncAST.add_rules(f"STR <- repr(DATESET)", "vsqlimpl_pkg.repr_dateset({s1})")
FuncAST.add_rules(f"STR <- repr(DATETIMESET)", "vsqlimpl_pkg.repr_datetimeset({s1})")
FuncAST.add_rules(f"STR <- repr({ANY})", "vsqlimpl_pkg.repr_{t1}({s1})")

# Function ``date()``
FuncAST.add_rules(f"DATE <- date(INT, INT, INT)", "vsqlimpl_pkg.date_int({s1}, {s2}, {s3})")
FuncAST.add_rules(f"DATE <- date(DATETIME)", "trunc({s1})")

# Function ``datetime()``
FuncAST.add_rules(f"DATETIME <- datetime(INT, INT, INT)", "vsqlimpl_pkg.datetime_int({s1}, {s2}, {s3})")
FuncAST.add_rules(f"DATETIME <- datetime(INT, INT, INT, INT)", "vsqlimpl_pkg.datetime_int({s1}, {s2}, {s3}, {s4})")
FuncAST.add_rules(f"DATETIME <- datetime(INT, INT, INT, INT, INT)", "vsqlimpl_pkg.datetime_int({s1}, {s2}, {s3}, {s4}, {s5})")
FuncAST.add_rules(f"DATETIME <- datetime(INT, INT, INT, INT, INT, INT)", "vsqlimpl_pkg.datetime_int({s1}, {s2}, {s3}, {s4}, {s5}, {s6})")
FuncAST.add_rules(f"DATETIME <- datetime(DATE)", "{s1}")
FuncAST.add_rules(f"DATETIME <- datetime(DATE, INT)", "({s1} + {s2}/24)")
FuncAST.add_rules(f"DATETIME <- datetime(DATE, INT, INT)", "({s1} + {s2}/24 + {s3}/24/60)")
FuncAST.add_rules(f"DATETIME <- datetime(DATE, INT, INT, INT)", "({s1} + {s2}/24 + {s3}/24/60 + {s4}/24/60/60)")

# Function ``len()``
FuncAST.add_rules(f"INT <- len({TEXT})", "nvl(length({s1}), 0)")
FuncAST.add_rules(f"INT <- len(NULLLIST)", "{s1}")
FuncAST.add_rules(f"INT <- len({LIST})", "vsqlimpl_pkg.len_{t1}({s1})")
FuncAST.add_rules(f"INT <- len(NULLSET)", "case when {s1} > 0 then 1 else {s1} end")
FuncAST.add_rules(f"INT <- len({SET})", "vsqlimpl_pkg.len_{t1}({s1})")

# Function ``timedelta()``
FuncAST.add_rules(f"DATEDELTA <- timedelta()", "0")
FuncAST.add_rules(f"DATEDELTA <- timedelta(INT)", "{s1}")
FuncAST.add_rules(f"DATETIMEDELTA <- timedelta(INT, INT)", "({s1} + {s2}/86400)")

# Function ``monthdelta()``
FuncAST.add_rules(f"MONTHDELTA <- monthdelta()", "0")
FuncAST.add_rules(f"MONTHDELTA <- monthdelta(INT)", "{s1}")

# Function ``years()``
FuncAST.add_rules(f"MONTHDELTA <- years(INT)", "(12 * {s1})")

# Function ``months()``
FuncAST.add_rules(f"MONTHDELTA <- months(INT)", "{s1}")

# Function ``weeks()``
FuncAST.add_rules(f"DATEDELTA <- weeks(INT)", "(7 * {s1})")

# Function ``days()``
FuncAST.add_rules(f"DATEDELTA <- days(INT)", "{s1}")

# Function ``hours()``
FuncAST.add_rules(f"DATETIMEDELTA <- hours(INT)", "({s1} / 24)")

# Function ``minutes()``
FuncAST.add_rules(f"DATETIMEDELTA <- minutes(INT)", "({s1} / 1440)")

# Function ``seconds()``
FuncAST.add_rules(f"DATETIMEDELTA <- seconds(INT)", "({s1} / 86400)")

# Function `md5()``
FuncAST.add_rules(f"STR <- md5(STR)", "lower(rawtohex(dbms_crypto.hash(utl_raw.cast_to_raw({s1}), 2)))")

# Function `random()``
FuncAST.add_rules(f"NUMBER <- random()", "dbms_random.value")

# Function `randrange()``
FuncAST.add_rules(f"INT <- randrange(INT, INT)", "floor(dbms_random.value({s1}, {s2}))")

# Function `seq()``
FuncAST.add_rules(f"INT <- seq()", "livingapi_pkg.seq()")

# Function `rgb()``
FuncAST.add_rules(f"COLOR <- rgb({NUMBERLIKE}, {NUMBERLIKE}, {NUMBERLIKE})", "vsqlimpl_pkg.rgb({s1}, {s2}, {s3})")
FuncAST.add_rules(f"COLOR <- rgb({NUMBERLIKE}, {NUMBERLIKE}, {NUMBERLIKE}, {NUMBERLIKE})", "vsqlimpl_pkg.rgb({s1}, {s2}, {s3}, {s4})")

# Function `list()``
FuncAST.add_rules(f"STRLIST <- list({TEXT})", "vsqlimpl_pkg.list_{t1}({s1})")
FuncAST.add_rules(f"T1 <- list(NULLLIST_{LIST})", "{s1}")
FuncAST.add_rules(f"NULLLIST <- list(NULLSET)", "{s1}")
FuncAST.add_rules(f"INTLIST <- list(INTSET)", "{s1}")
FuncAST.add_rules(f"NUMBERLIST <- list(NUMBERSET)", "{s1}")
FuncAST.add_rules(f"STRLIST <- list(STRSET)", "{s1}")
FuncAST.add_rules(f"DATELIST <- list(DATESET)", "{s1}")
FuncAST.add_rules(f"DATETIMELIST <- list(DATETIMESET)", "{s1}")

# Function `set()``
FuncAST.add_rules(f"STRSET <- set({TEXT})", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"T1 <- set({SET})", "{s1}")
FuncAST.add_rules(f"NULLSET <- set(NULLLIST)", "case when {s1} > 0 then 1 else {s1} end")
FuncAST.add_rules(f"INTSET <- set(INTLIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"NUMBERSET <- set(NUMBERLIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"STRSET <- set(STRLIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"DATESET <- set(DATELIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"DATETIMESET <- set(DATETIMELIST)", "vsqlimpl_pkg.set_{t1}({s1})")

# Function ``dist()``
FuncAST.add_rules(f"NUMBER <- dist(GEO, GEO)", "vsqlimpl_pkg.dist_geo_geo({s1}, {s2})")

# Function ``abs()``
FuncAST.add_rules(f"INT <- abs(BOOL)", "{s1}")
FuncAST.add_rules(f"INT <- abs(INT)", "abs({s1})")
FuncAST.add_rules(f"NUMBER <- abs(NUMBER)", "abs({s1})")

# Function ``cos()``
FuncAST.add_rules(f"NUMBER <- cos({NUMBERLIKE})", "cos({s1})")

# Function ``sin()``
FuncAST.add_rules(f"NUMBER <- sin({NUMBERLIKE})", "sin({s1})")

# Function ``tan()``
FuncAST.add_rules(f"NUMBER <- tan({NUMBERLIKE})", "tan({s1})")

# Function ``sqrt()``
FuncAST.add_rules(f"NUMBER <- sqrt({NUMBERLIKE})", "sqrt(case when {s1} >= 0 then {s1} else null end)")

# Method ``lower()``
MethAST.add_rules(f"T1 <- {TEXT}.lower()", "lower({s1})")

# Method ``upper()``
MethAST.add_rules(f"T1 <- {TEXT}.upper()", "upper({s1})")

# Method ``startswith()``
MethAST.add_rules(f"BOOL <- {TEXT}.startswith(STR_STRLIST)", "vsqlimpl_pkg.startswith_{t1}_{t2}({s1}, {s2})")

# Method ``endswith()``
MethAST.add_rules(f"BOOL <- {TEXT}.endswith(STR_STRLIST)", "vsqlimpl_pkg.endswith_{t1}_{t2}({s1}, {s2})")

# Method ``strip()``
MethAST.add_rules(f"T1 <- {TEXT}.strip()", "vsqlimpl_pkg.strip_{t1}({s1}, null, 1, 1)")
MethAST.add_rules(f"T1 <- {TEXT}.strip(STR) ", "vsqlimpl_pkg.strip_{t1}({s1}, {s2}, 1, 1)")

# Method ``lstrip()``
MethAST.add_rules(f"T1 <- {TEXT}.lstrip()", "vsqlimpl_pkg.strip_{t1}({s1}, null, 1, 0)")
MethAST.add_rules(f"T1 <- {TEXT}.lstrip(STR) ", "vsqlimpl_pkg.strip_{t1}({s1}, {s2}, 1, 0)")

# Method ``rstrip()``
MethAST.add_rules(f"T1 <- {TEXT}.rstrip()", "vsqlimpl_pkg.strip_{t1}({s1}, null, 0, 1)")
MethAST.add_rules(f"T1 <- {TEXT}.rstrip(STR) ", "vsqlimpl_pkg.strip_{t1}({s1}, {s2}, 0, 1)")

# Method ``find()``
MethAST.add_rules(f"INT <- {TEXT}.find({TEXT})", "(instr({s1}, {s2}) - 1)")
MethAST.add_rules(f"INT <- {TEXT}.find({TEXT}, NULL)", "(instr({s1}, {s2}) - 1)")
MethAST.add_rules(f"INT <- {TEXT}.find({TEXT}, NULL, NULL)", "(instr({s1}, {s2}) - 1)")
MethAST.add_rules(f"INT <- {TEXT}.find({TEXT}, NULL_INT)", "vsqlimpl_pkg.find_{t1}_{t2}({s1}, {s2}, {s3}, null)")
MethAST.add_rules(f"INT <- {TEXT}.find({TEXT}, NULL_INT, NULL_INT)", "vsqlimpl_pkg.find_{t1}_{t2}({s1}, {s2}, {s3}, {s4})")

# Method ``replace()``
MethAST.add_rules(f"T1 <- {TEXT}.replace(STR, STR)", "replace({s1}, {s2}, {s3})")

# Method ``split()``
MethAST.add_rules(f"STRLIST <- STR.split()", "vsqlimpl_pkg.split_{t1}_str({s1}, null)")
MethAST.add_rules(f"CLOBLIST <- CLOB.split()", "vsqlimpl_pkg.split_{t1}_str({s1}, null)")
MethAST.add_rules(f"STRLIST <- STR.split(NULL)", "vsqlimpl_pkg.split_{t1}_str(null, null)")
MethAST.add_rules(f"CLOBLIST <- CLOB.split(NULL)", "vsqlimpl_pkg.split_{t1}_str(null, null)")
MethAST.add_rules(f"STRLIST <- STR.split(STR)", "vsqlimpl_pkg.split_{t1}_str({s1}, {s2})")
MethAST.add_rules(f"CLOBLIST <- CLOB.split(STR)", "vsqlimpl_pkg.split_{t1}_str({s1}, {s2})")
MethAST.add_rules(f"STRLIST <- STR.split(STR, NULL)", "vsqlimpl_pkg.split_{t1}_str({s1}, {s2})")
MethAST.add_rules(f"CLOBLIST <- CLOB.split(STR, NULL)", "vsqlimpl_pkg.split_{t1}_str({s1}, {s2})")
MethAST.add_rules(f"STRLIST <- STR.split(NULL, BOOL_INT)", "vsqlimpl_pkg.split_{t1}_str({s1}, null, {s3})")
MethAST.add_rules(f"CLOBLIST <- CLOB.split(NULL, BOOL_INT)", "vsqlimpl_pkg.split_{t1}_str({s1}, null, {s3})")
MethAST.add_rules(f"STRLIST <- STR.split(STR, BOOL_INT)", "vsqlimpl_pkg.split_{t1}_str({s1}, {s2}, {s3})")
MethAST.add_rules(f"CLOBLIST <- CLOB.split(STR, BOOL_INT)", "vsqlimpl_pkg.split_{t1}_str({s1}, {s2}, {s3})")

# Method ``join()``
MethAST.add_rules(f"STR <- STR.join(STR_STRLIST)", "vsqlimpl_pkg.join_str_{t2}({s1}, {s2})")
MethAST.add_rules(f"CLOB <- STR.join(CLOB_CLOBLIST)", "vsqlimpl_pkg.join_str_{t2}({s1}, {s2})")

# Method ``lum()``
MethAST.add_rules(f"NUMBER <- COLOR.lum()", "vsqlimpl_pkg.lum({s1})")

# Method ``week()``
MethAST.add_rules(f"INT <- DATE_DATETIME.week()", "to_number(to_char({s1}, 'IW'))")

# Attributes
AttrAST.add_rules(f"INT <- DATE_DATETIME.year", "extract(year from {s1})")
AttrAST.add_rules(f"INT <- DATE_DATETIME.month", "extract(month from {s1})")
AttrAST.add_rules(f"INT <- DATE_DATETIME.day", "extract(day from {s1})")
AttrAST.add_rules(f"INT <- DATETIME.hour", "to_number(to_char({s1}, 'HH24'))")
AttrAST.add_rules(f"INT <- DATETIME.minute", "to_number(to_char({s1}, 'MI'))")
AttrAST.add_rules(f"INT <- DATETIME.second", "to_number(to_char({s1}, 'SS'))")
AttrAST.add_rules(f"INT <- DATE_DATETIME.weekday", "(to_char({s1}, 'D')-1)")
AttrAST.add_rules(f"INT <- DATE_DATETIME.yearday", "to_number(to_char({s1}, 'DDD'))")
AttrAST.add_rules(f"INT <- DATEDELTA_DATETIMEDELTA.days", "trunc({s1})")
AttrAST.add_rules(f"INT <- DATETIMEDELTA.seconds", "trunc(mod({s1}, 1) * 86400 + 0.5)")
AttrAST.add_rules(f"NUMBER <- DATETIMEDELTA.total_days", "{s1}")
AttrAST.add_rules(f"NUMBER <- DATETIMEDELTA.total_hours", "({s1} * 24)")
AttrAST.add_rules(f"NUMBER <- DATETIMEDELTA.total_minutes", "({s1} * 1440)")
AttrAST.add_rules(f"NUMBER <- DATETIMEDELTA.total_seconds", "({s1} * 86400)")
AttrAST.add_rules(f"INT <- COLOR.r", "vsqlimpl_pkg.attr_color_r({s1})")
AttrAST.add_rules(f"INT <- COLOR.g", "vsqlimpl_pkg.attr_color_g({s1})")
AttrAST.add_rules(f"INT <- COLOR.b", "vsqlimpl_pkg.attr_color_b({s1})")
AttrAST.add_rules(f"INT <- COLOR.a", "vsqlimpl_pkg.attr_color_a({s1})")
AttrAST.add_rules(f"NUMBER <- GEO.lat", "vsqlimpl_pkg.attr_geo_lat({s1})")
AttrAST.add_rules(f"NUMBER <- GEO.long", "vsqlimpl_pkg.attr_geo_long({s1})")
AttrAST.add_rules(f"STR <- GEO.info", "vsqlimpl_pkg.attr_geo_info({s1})")

# Equality comparison (A == B)
EQAST.add_rules(f"BOOL <- NULL == NULL", "1")
EQAST.add_rules(f"BOOL <- {ANY} == NULL", "(case when {s1} is null then 1 else 0 end)")
EQAST.add_rules(f"BOOL <- NULL == {ANY}", "(case when {s2} is null then 1 else 0 end)")
EQAST.add_rules(f"BOOL <- {INTLIKE} == {INTLIKE}", "vsqlimpl_pkg.eq_int_int({s1}, {s2})")
EQAST.add_rules(f"BOOL <- {NUMBERLIKE} == {NUMBERLIKE}", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- GEO == GEO", "vsqlimpl_pkg.eq_str_str({s1}, {s2})")
EQAST.add_rules(f"BOOL <- COLOR == COLOR", "vsqlimpl_pkg.eq_int_int({s1}, {s2})")
EQAST.add_rules(f"BOOL <- {TEXT} == {TEXT}", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATE_DATETIME == T1", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATEDELTA_MONTHDELTA_COLOR == T1", "vsqlimpl_pkg.eq_int_int({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATETIMEDELTA == DATETIMEDELTA", "vsqlimpl_pkg.eq_datetimedelta_datetimedelta({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLLIST == NULLLIST_{LIST}", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLLIST_{LIST} == NULLLIST", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST == INTLIST_NUMBERLIST", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- STRLIST_CLOBLIST == STRLIST_CLOBLIST", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATELIST_DATETIMELIST == DATELIST_DATETIMELIST", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLSET == NULLSET", "vsqlimpl_pkg.eq_nullset_nullset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLSET == INTSET", "vsqlimpl_pkg.eq_nullset_intset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLSET == NUMBERSET", "vsqlimpl_pkg.eq_nullset_numberset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLSET == STRSET", "vsqlimpl_pkg.eq_nullset_strset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLSET == DATESET", "vsqlimpl_pkg.eq_nullset_datetimeset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NULLSET == DATETIMESET", "vsqlimpl_pkg.eq_nullset_datetimeset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- INTSET == NULLSET", "vsqlimpl_pkg.eq_intset_nullset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NUMBERSET == NULLSET", "vsqlimpl_pkg.eq_numberset_nullset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- STRSET == NULLSET", "vsqlimpl_pkg.eq_strset_nullset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATESET == NULLSET", "vsqlimpl_pkg.eq_datetimeset_nullset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATETIMESET == NULLSET", "vsqlimpl_pkg.eq_datetimeset_nullset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- INTSET == INTSET", "vsqlimpl_pkg.eq_intset_intset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- NUMBERSET == NUMBERSET", "vsqlimpl_pkg.eq_numberset_numberset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- STRSET == STRSET", "vsqlimpl_pkg.eq_strset_strset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATESET_DATETIMESET == DATESET_DATETIMESET", "vsqlimpl_pkg.eq_datetimeset_datetimeset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- {ANY} == {ANY}", "(case when {s1} is null and {s2} is null then 1 else 0 end)")

# Inequality comparison (A != B)
NEAST.add_rules(f"BOOL <- NULL != NULL", "0")
NEAST.add_rules(f"BOOL <- {ANY} != NULL", "(case when {s1} is null then 0 else 1 end)")
NEAST.add_rules(f"BOOL <- NULL != {ANY}", "(case when {s2} is null then 0 else 1 end)")
NEAST.add_rules(f"BOOL <- {INTLIKE} != {INTLIKE}", "(1 - vsqlimpl_pkg.eq_int_int({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- {NUMBERLIKE} != {NUMBERLIKE}", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- GEO != GEO", "(1 - vsqlimpl_pkg.eq_str_str({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- COLOR != COLOR", "(1 - vsqlimpl_pkg.eq_int_int({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- {TEXT} != {TEXT}", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- DATE_DATETIME != T1", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- DATEDELTA_MONTHDELTA_COLOR != T1", "(1 - vsqlimpl_pkg.eq_int_int({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- DATETIMEDELTA != DATETIMEDELTA", "(1 - vsqlimpl_pkg.eq_datetimedelta_datetimedelta({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLLIST != NULLLIST_{LIST}", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLLIST_{LIST} != NULLLIST", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST != INTLIST_NUMBERLIST", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- STRLIST_CLOBLIST != STRLIST_CLOBLIST", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- DATELIST_DATETIMELIST != DATELIST_DATETIMELIST", "(1 - vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLSET != NULLSET", "(1 - vsqlimpl_pkg.eq_nullset_nullset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLSET != INTSET", "(1 - vsqlimpl_pkg.eq_nullset_intset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLSET != NUMBERSET", "(1 - vsqlimpl_pkg.eq_nullset_numberset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLSET != STRSET", "(1 - vsqlimpl_pkg.eq_nullset_strset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLSET != DATESET", "(1 - vsqlimpl_pkg.eq_nullset_datetimeset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NULLSET != DATETIMESET", "(1 - vsqlimpl_pkg.eq_nullset_datetimeset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- INTSET != NULLSET", "(1 - vsqlimpl_pkg.eq_intset_nullset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NUMBERSET != NULLSET", "(1 - vsqlimpl_pkg.eq_numberset_nullset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- STRSET != NULLSET", "(1 - vsqlimpl_pkg.eq_strset_nullset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- DATESET != NULLSET", "(1 - vsqlimpl_pkg.eq_datetimeset_nullset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- DATETIMESET != NULLSET", "(1 - vsqlimpl_pkg.eq_datetimeset_nullset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- INTSET != INTSET", "(1 - vsqlimpl_pkg.eq_intset_intset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- NUMBERSET != NUMBERSET", "(1 - vsqlimpl_pkg.eq_numberset_numberset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- STRSET != STRSET", "(1 - vsqlimpl_pkg.eq_strset_strset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- DATESET_DATETIMESET != DATESET_DATETIMESET", "(1 - vsqlimpl_pkg.eq_datetimeset_datetimeset({s1}, {s2}))")
NEAST.add_rules(f"BOOL <- {ANY} != {ANY}", "(case when {s1} is null and {s2} is null then 0 else 1 end)")

# The following comparisons always treat ``None`` as the smallest value

# Greater-than comparison (A > B)
GTAST.add_rules(f"BOOL <- NULL > NULL", "0")
GTAST.add_rules(f"BOOL <- {ANY} > NULL", "(case when {s1} is null then 0 else 1 end)")
GTAST.add_rules(f"BOOL <- NULL > {ANY}", "0")
GTAST.add_rules(f"BOOL <- {INTLIKE} > {INTLIKE}", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- {NUMBERLIKE} > {NUMBERLIKE}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- {TEXT} > {TEXT}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- DATE_DATETIME > T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- DATEDELTA > DATEDELTA", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- DATETIMEDELTA > DATETIMEDELTA", "(case when vsqlimpl_pkg.cmp_number_number({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST > INTLIST_NUMBERLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- STRLIST_CLOBLIST > STRLIST_CLOBLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- DATELIST_DATETIMELIST > T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- NULLLIST > NULLLIST_{LIST}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")
GTAST.add_rules(f"BOOL <- NULLLIST_{LIST} > NULLLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) > 0 then 1 else 0 end)")

# Greater-than-or equal comparison (A >= B)
GEAST.add_rules(f"BOOL <- {ANY} >= NULL", "1")
GEAST.add_rules(f"BOOL <- NULL >= {ANY}", "(case when {s2} is null then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- {INTLIKE} >= {INTLIKE}", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- {NUMBERLIKE} >= {NUMBERLIKE}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- {TEXT} >= {TEXT}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- DATE_DATETIME >= T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- DATEDELTA >= DATEDELTA", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- DATETIMEDELTA >= DATETIMEDELTA", "(case when vsqlimpl_pkg.cmp_number_number({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST >= INTLIST_NUMBERLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- STRLIST_CLOBLIST >= STRLIST_CLOBLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- DATELIST_DATETIMELIST >= T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- NULLLIST >= NULLLIST_{LIST}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")
GEAST.add_rules(f"BOOL <- NULLLIST_{LIST} >= NULLLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) >= 0 then 1 else 0 end)")

# Less-than comparison (A < B)
LTAST.add_rules(f"BOOL <- {ANY} < NULL", "0")
LTAST.add_rules(f"BOOL <- NULL < {ANY}", "(case when {s2} is null then 0 else 1 end)")
LTAST.add_rules(f"BOOL <- {INTLIKE} < {INTLIKE}", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- {NUMBERLIKE} < {NUMBERLIKE}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- {TEXT} < {TEXT}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATE_DATETIME < T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATEDELTA < DATEDELTA", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATETIMEDELTA < DATETIMEDELTA", "(case when vsqlimpl_pkg.cmp_number_number({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST < INTLIST_NUMBERLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- STRLIST_CLOBLIST < STRLIST_CLOBLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATELIST_DATETIMELIST < T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- NULLLIST < NULLLIST_{LIST}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- NULLLIST_{LIST} < NULLLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")

# Less-than-or equal comparison (A <= B)
LEAST.add_rules(f"BOOL <- NULL <= NULL", "1")
LEAST.add_rules(f"BOOL <- {ANY} <= NULL", "(case when {s1} is null then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- NULL <= {ANY}", "1")
LEAST.add_rules(f"BOOL <- {INTLIKE} <= {INTLIKE}", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- {NUMBERLIKE} <= {NUMBERLIKE}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- {TEXT} <= {TEXT}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- DATE_DATETIME <= T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- DATEDELTA <= DATEDELTA", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- DATETIMEDELTA <= DATETIMEDELTA", "(case when vsqlimpl_pkg.cmp_number_number({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST <= INTLIST_NUMBERLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- STRLIST_CLOBLIST <= STRLIST_CLOBLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- DATELIST_DATETIMELIST <= T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- NULLLIST <= NULLLIST_{LIST}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")
LEAST.add_rules(f"BOOL <- NULLLIST_{LIST} <= NULLLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) <= 0 then 1 else 0 end)")

# Addition (A + B)
AddAST.add_rules(f"INT <- {INTLIKE} + {INTLIKE}", "({s1} + {s2})")
AddAST.add_rules(f"NUMBER <- {NUMBERLIKE} + {NUMBERLIKE}", "({s1} + {s2})")
AddAST.add_rules(f"STR <- STR + STR", "({s1} || {s2})")
AddAST.add_rules(f"CLOB <- {TEXT} + {TEXT}", "({s1} || {s2})")
AddAST.add_rules(f"INTLIST <- INTLIST + INTLIST", "vsqlimpl_pkg.add_intlist_intlist({s1}, {s2})")
AddAST.add_rules(f"NUMBERLIST <- INTLIST_NUMBERLIST + INTLIST_NUMBERLIST", "vsqlimpl_pkg.add_{t1}_{t2}({s1}, {s2})")
AddAST.add_rules(f"STRLIST <- STRLIST + STRLIST", "vsqlimpl_pkg.add_strlist_strlist({s1}, {s2})")
AddAST.add_rules(f"CLOBLIST <- STRLIST_CLOBLIST + STRLIST_CLOBLIST", "vsqlimpl_pkg.add_{t1}_{t2}({s1}, {s2})")
AddAST.add_rules(f"T1 <- DATELIST_DATETIMELIST + T1", "vsqlimpl_pkg.add_{t1}_{t2}({s1}, {s2})")
AddAST.add_rules(f"NULLLIST <- NULLLIST + NULLLIST", "({s1} + {s2})")
AddAST.add_rules(f"T2 <- NULLLIST + NULLLIST_{LIST}", "vsqlimpl_pkg.add_{t1}_{t2}({s1}, {s2})")
AddAST.add_rules(f"T1 <- NULLLIST_{LIST} + NULLLIST", "vsqlimpl_pkg.add_{t1}_{t2}({s1}, {s2})")
AddAST.add_rules(f"DATE <- DATE + DATEDELTA", "({s1} + {s2})")
AddAST.add_rules(f"DATETIME <- DATETIME + DATEDELTA_DATETIMEDELTA", "({s1} + {s2})")
AddAST.add_rules(f"T1 <- DATE_DATETIME + MONTHDELTA", "vsqlimpl_pkg.add_{t1}_months({s1}, {s2})")
AddAST.add_rules(f"T2 <- MONTHDELTA + DATE_DATETIME", "vsqlimpl_pkg.add_months_{t2}({s1}, {s2})")
AddAST.add_rules(f"DATEDELTA <- DATEDELTA + DATEDELTA", "({s1} + {s2})")
AddAST.add_rules(f"DATETIMEDELTA <- DATEDELTA_DATETIMEDELTA + DATEDELTA_DATETIMEDELTA", "({s1} + {s2})")
AddAST.add_rules(f"MONTHDELTA <- MONTHDELTA + MONTHDELTA", "({s1} + {s2})")

# Subtraction (A - B)
SubAST.add_rules(f"INT <- {INTLIKE} - {INTLIKE}", "({s1} - {s2})")
SubAST.add_rules(f"NUMBER <- {NUMBERLIKE} - {NUMBERLIKE}", "({s1} - {s2})")
SubAST.add_rules(f"DATE <- DATE - DATEDELTA", "({s1} - {s2})")
SubAST.add_rules(f"DATEDELTA <- DATE - DATE", "({s1} - {s2})")
SubAST.add_rules(f"DATETIMEDELTA <- DATETIME - DATETIME", "({s1} - {s2})")
SubAST.add_rules(f"T1 <- DATE_DATETIME - MONTHDELTA", "vsqlimpl_pkg.add_{t1}_months({s1}, -{s2})")
SubAST.add_rules(f"DATETIME <- DATETIME - DATEDELTA_DATETIMEDELTA", "({s1} - {s2})")
SubAST.add_rules(f"T1 <- DATEDELTA_MONTHDELTA - T1", "({s1} - {s2})")
SubAST.add_rules(f"DATETIMEDELTA <- DATEDELTA_DATETIMEDELTA - DATEDELTA_DATETIMEDELTA" , "({s1} - {s2})")

# Multiplication (A * B)
MulAST.add_rules(f"INT <- {INTLIKE} * {INTLIKE}", "({s1} * {s2})")
MulAST.add_rules(f"NUMBER <- {NUMBERLIKE} * {NUMBERLIKE}", "({s1} * {s2})")
MulAST.add_rules(f"T2 <- {INTLIKE} * DATEDELTA_DATETIMEDELTA_MONTHDELTA", "({s1} * {s2})")
MulAST.add_rules(f"DATETIMEDELTA <- NUMBER * DATETIMEDELTA", "({s1} * {s2})")
MulAST.add_rules(f"T2 <- {INTLIKE} * {TEXT}", "vsqlimpl_pkg.mul_int_{t2}({s1}, {s2})")
MulAST.add_rules(f"T1 <- {TEXT} * {INTLIKE}", "vsqlimpl_pkg.mul_{t1}_int({s1}, {s2})")
MulAST.add_rules(f"T2 <- {INTLIKE} * {LIST}", "vsqlimpl_pkg.mul_int_{t2}({s1}, {s2})")
MulAST.add_rules(f"T1 <- {LIST} * {INTLIKE}", "vsqlimpl_pkg.mul_{t1}_int({s1}, {s2})")
MulAST.add_rules(f"NULLLIST <- {INTLIKE} * NULLLIST", "({s1} * {s2})")
MulAST.add_rules(f"NULLLIST <- NULLLIST * {INTLIKE}", "({s1} * {s2})")

# True division (A / B)
TrueDivAST.add_rules(f"INT <- BOOL / BOOL", "({s1} / {s2})")
TrueDivAST.add_rules(f"NUMBER <- {NUMBERLIKE} / {NUMBERLIKE}", "({s1} / {s2})")
TrueDivAST.add_rules(f"DATETIMEDELTA <- DATETIMEDELTA / {NUMBERLIKE}", "({s1} / {s2})")

# Floor division (A // B)
FloorDivAST.add_rules(f"INT <- {NUMBERLIKE} // {NUMBERLIKE}", "vsqlimpl_pkg.floordiv_{t1}_{t2}({s1}, {s2})")
FloorDivAST.add_rules(f"T1 <- DATEDELTA_MONTHDELTA // {INTLIKE}", "vsqlimpl_pkg.floordiv_int_int({s1}, {s2})")
FloorDivAST.add_rules(f"DATEDELTA <- DATETIMEDELTA // {NUMBERLIKE}", "vsqlimpl_pkg.floordiv_number_int({s1}, {s2})")

# Modulo operator (A % B)
ModAST.add_rules(f"INT <- {INTLIKE} % {INTLIKE}", "vsqlimpl_pkg.mod_int_int({s1}, {s2})")
ModAST.add_rules(f"NUMBER <- {NUMBERLIKE} % {NUMBERLIKE}", "vsqlimpl_pkg.mod_{t1}_{t2}({s1}, {s2})")
ModAST.add_rules(f"COLOR <- COLOR % COLOR", "vsqlimpl_pkg.mod_color_color({s1}, {s2})")

# Left shift operator (A << B)
ShiftLeftAST.add_rules(f"INT <- {INTLIKE} << {INTLIKE}", "trunc({s1} * power(2, {s2}))")

# Right shift operator (A >> B)
ShiftRightAST.add_rules(f"INT <- {INTLIKE} >> {INTLIKE}", "trunc({s1} / power(2, {s2}))")

# Logical "and" (A and B)
# Can't use the real operator ("and") in the spec, so use "?"
AndAST.add_rules(f"T1 <- {ANY} ? NULL", "null")
AndAST.add_rules(f"T2 <- NULL ? {ANY}", "null")
AndAST.add_rules(f"BOOL <- BOOL ? BOOL", "(case when {s1} = 1 then {s2} else 0 end)")
AndAST.add_rules(f"INT <- {INTLIKE} ? {INTLIKE}", "(case when nvl({s1}, 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? {NUMBERLIKE}", "(case when nvl({s1}, 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"STR <- STR ? STR", "nvl2({s1}, {s2}, {s1})")
AndAST.add_rules(f"CLOB <- CLOB ? CLOB", "(case when {s1} is not null and length({s1}) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"T1 <- DATE_DATETIME ? T1", "nvl2({s1}, {s2}, {s1})")
AndAST.add_rules(f"T1 <- DATEDELTA_DATETIMEDELTA_MONTHDELTA ? T1", "(case when nvl({s1}, 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"T1 <- {LIST} ? T1", "(case when nvl(vsqlimpl_pkg.len_{t1}({s1}), 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"DATETIMELIST <- DATELIST_DATETIMELIST ? DATELIST_DATETIMELIST", "(case when nvl(vsqlimpl_pkg.len_{t1}({s1}), 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"NULLLIST <- NULLLIST ? NULLLIST", "(case when nvl({s1}, 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"T2 <- NULLLIST ? {LIST}", "(case when nvl({s1}, 0) != 0 then {s2} else vsqlimpl_pkg.{t2}_fromlen({s1}) end)")
AndAST.add_rules(f"T1 <- {LIST} ? NULLLIST", "(case when nvl(vsqlimpl_pkg.len_{t1}({s1}), 0) != 0 then vsqlimpl_pkg.{t1}_fromlen({s2}) else {s1} end)")

# Logical "or" (A or B)
# Can't use the real operator ("or") in the spec, so use "?"
OrAST.add_rules(f"T1 <- {ANY} ? NULL", "{s1}")
OrAST.add_rules(f"T2 <- NULL ? {ANY}", "{s2}")
OrAST.add_rules(f"BOOL <- BOOL ? BOOL", "(case when {s1} = 1 then 1 else {s2} end)")
OrAST.add_rules(f"INT <- {INTLIKE} ? {INTLIKE}", "(case when nvl({s1}, 0) != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? {NUMBERLIKE}", "(case when nvl({s1}, 0) != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"STR <- STR ? STR", "nvl({s1}, {s2})")
OrAST.add_rules(f"CLOB <- CLOB ? CLOB", "(case when {s1} is not null and length({s1}) != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"T1 <- DATE_DATETIME ? T1", "nvl({s1}, {s2})")
OrAST.add_rules(f"T1 <- DATEDELTA_DATETIMEDELTA_MONTHDELTA ? T1", "(case when nvl({s1}, 0) != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"T1 <- {LIST} ? T1", "(case when nvl(vsqlimpl_pkg.len_{t1}({s1}), 0) != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"DATETIMELIST <- DATELIST_DATETIMELIST ? DATELIST_DATETIMELIST", "(case when nvl(vsqlimpl_pkg.len_{t1}({s1}), 0) != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"NULLLIST <- NULLLIST ? NULLLIST", "(case when nvl({s1}, 0) != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"T2 <- NULLLIST ? {LIST}", "(case when nvl({s1}, 0) != 0 then vsqlimpl_pkg.{t2}_fromlen({s1}) else {s2} end)")
OrAST.add_rules(f"T1 <- {LIST} ? NULLLIST", "(case when nvl(vsqlimpl_pkg.len_{t1}({s1}), 0) != 0 then {s1} else vsqlimpl_pkg.{t1}_fromlen({s2}) end)")

# Containment test (A in B)
# Can't use the real operator ("in") in the spec, so use "?"
ContainsAST.add_rules(f"BOOL <- NULL ? {LIST}_NULLLIST", "vsqlimpl_pkg.contains_null_{t2}({s2})")
ContainsAST.add_rules(f"BOOL <- STR ? STR_CLOB_STRLIST_CLOBLIST_STRSET", "vsqlimpl_pkg.contains_str_{t2}({s1}, {s2})")
ContainsAST.add_rules(f"BOOL <- INT_NUMBER ? INTLIST_NUMBERLIST_INTSET_NUMBERSET", "vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2})")
ContainsAST.add_rules(f"BOOL <- DATE ? DATELIST_DATESET", "vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2})")
ContainsAST.add_rules(f"BOOL <- DATETIME ? DATETIMELIST_DATETIMESET", "vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2})")
ContainsAST.add_rules(f"BOOL <- {ANY} ? NULLLIST", "case when {s1} is null then vsqlimpl_pkg.contains_null_nulllist({s2}) else 0 end")

# Inverted containment test (A not in B)
# Can't use the real operator ("not in") in the spec, so use "?"
NotContainsAST.add_rules(f"BOOL <- NULL ? {LIST}_NULLLIST", "(1 - vsqlimpl_pkg.contains_null_{t2}({s2}))")
NotContainsAST.add_rules(f"BOOL <- STR ? STR_CLOB_STRLIST_CLOBLIST_STRSET", "(1 - vsqlimpl_pkg.contains_str_{t2}({s1}, {s2}))")
NotContainsAST.add_rules(f"BOOL <- INT_NUMBER ? INTLIST_NUMBERLIST_INTSET_NUMBERSET", "(1 - vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2}))")
NotContainsAST.add_rules(f"BOOL <- DATE ? DATELIST_DATESET", "(1 - vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2}))")
NotContainsAST.add_rules(f"BOOL <- DATETIME ? DATETIMELIST_DATETIMESET", "(1 - vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2}))")
NotContainsAST.add_rules(f"BOOL <- {ANY} ? NULLLIST", "case when {s1} is null then 1 - vsqlimpl_pkg.contains_null_nulllist({s2}) else 1 end")

# Identity test (A is B)
# Can't use the real operator ("is") in the spec, so use "?"
IsAST.add_rules(f"BOOL <- NULL ? NULL", "1")
IsAST.add_rules(f"BOOL <- {ANY} ? NULL", "(case when {s1} is null then 1 else 0 end)")
IsAST.add_rules(f"BOOL <- NULL ? {ANY}", "(case when {s2} is null then 1 else 0 end)")

# Inverted identity test (A is not B)
# Can't use the real operator ("is not") in the spec, so use "?"
IsNotAST.add_rules(f"BOOL <- NULL ? NULL", "0")
IsNotAST.add_rules(f"BOOL <- {ANY} ? NULL", "(case when {s1} is not null then 1 else 0 end)")
IsNotAST.add_rules(f"BOOL <- NULL ? {ANY}", "(case when {s2} is not null then 1 else 0 end)")

# Item access operator (A[B])
ItemAST.add_rules(f"NULL <- NULLLIST[{INTLIKE}]", "null")
ItemAST.add_rules(f"STR <- STR_CLOB_STRLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"CLOB <- CLOBLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"INT <- INTLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"NUMBER <- NUMBERLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"DATE <- DATELIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"DATETIME <- DATETIMELIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")

# Bitwise "and" (A & B)
BitAndAST.add_rules(f"INT <- {INTLIKE} & {INTLIKE}", "bitand({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- INTSET & INTSET", "vsqlimpl_pkg.bitand_intset({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- NUMBERSET & NUMBERSET", "vsqlimpl_pkg.bitand_numberset({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- STRSET & STRSET", "vsqlimpl_pkg.bitand_strset({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- DATESET_DATETIMESET & T1", "vsqlimpl_pkg.bitand_datetimeset({s1}, {s2})")

# Bitwise "or" (A | B)
BitOrAST.add_rules(f"INT <- {INTLIKE} | {INTLIKE}", "vsqlimpl_pkg.bitor_int({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- INTSET | INTSET", "vsqlimpl_pkg.bitor_intset({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- NUMBERSET | NUMBERSET", "vsqlimpl_pkg.bitor_numberset({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- STRSET | STRSET", "vsqlimpl_pkg.bitor_strset({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- DATESET_DATETIMESET | T1", "vsqlimpl_pkg.bitor_datetimeset({s1}, {s2})")

# Bitwise "exclusive or" (A ^ B)
BitXOrAST.add_rules(f"INT <- {INTLIKE} ^ {INTLIKE}", "vsqlimpl_pkg.bitxor_int({s1}, {s2})")

# Logical negation (not A)
# Can't use the real operator ("not") in the spec, so use "?"
NotAST.add_rules(f"BOOL <- ? NULL", "1")
NotAST.add_rules(f"BOOL <- ? BOOL", "(case {s1} when 1 then 0 else 1 end)")
NotAST.add_rules(f"BOOL <- ? INT_NUMBER_DATEDELTA_DATETIMEDELTA_MONTHDELTA", "(case nvl({s1}, 0) when 0 then 1 else 0 end)")
NotAST.add_rules(f"BOOL <- ? DATE_DATETIME_STR_COLOR_GEO", "(case when {s1} is null then 1 else 0 end)")
NotAST.add_rules(f"BOOL <- ? {ANY}", "(1 - vsqlimpl_pkg.bool_{t1}({s1}))")

# Arithmetic negation (-A)
NegAST.add_rules(f"INT <- BOOL", "(-{s1})")
NegAST.add_rules(f"T1 <- INT_NUMBER_DATEDELTA_DATETIMEDELTA_MONTHDELTA", "(-{s1})")

# Bitwise "not" (~A)
BitNotAST.add_rules(f"INT <- {INTLIKE}", "(-{s1} - 1)")

# Ternary "if"/"else" (A if COND else B)
# Can't use the real operator ("if"/"else") in the spec, so use "?"
IfAST.add_rules(f"T1 <- {ANY} ? NULL ? T1", "{s3}")
IfAST.add_rules(f"INT <- {INTLIKE} ? NULL ? {INTLIKE}", "{s3}")
IfAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? NULL ? {NUMBERLIKE}", "{s3}")
IfAST.add_rules(f"T1 <- {ANY} ? NULL ? NULL", "{s3}")
IfAST.add_rules(f"T3 <- NULL ? NULL ? {ANY}", "{s3}")
IfAST.add_rules(f"T1 <- {ANY} ? {NUMBERSTORED} ? T1", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"INT <- {INTLIKE} ? {NUMBERSTORED} ? {INTLIKE}", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? {NUMBERSTORED} ? {NUMBERLIKE}", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"T1 <- {ANY} ? {NUMBERSTORED} ? NULL", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"T3 <- NULL ? {NUMBERSTORED} ? {ANY}", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"T1 <- {ANY} ? DATE_DATETIME_STR_GEO ? T1", "(case when {s2} is not null then {s1} else {s3} end)")
IfAST.add_rules(f"INT <- {INTLIKE} ? DATE_DATETIME_STR_GEO ? {INTLIKE}", "(case when {s2} is not null then {s1} else {s3} end)")
IfAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? DATE_DATETIME_STR_GEO ? {NUMBERLIKE}", "(case when {s2} is not null then {s1} else {s3} end)")
IfAST.add_rules(f"T1 <- {ANY} ? DATE_DATETIME_STR_GEO ? NULL", "(case when {s2} is not null then {s1} else {s3} end)")
IfAST.add_rules(f"T3 <- NULL ? DATE_DATETIME_STR_GEO ? {ANY}", "(case when {s2} is not null then {s1} else {s3} end)")
IfAST.add_rules(f"T1 <- {ANY} ? {ANY} ? T1", "(case when vsqlimpl_pkg.bool_{t2}({s2}) = 1 then {s1} else {s3} end)")
IfAST.add_rules(f"INT <- {INTLIKE} ? {ANY} ? {INTLIKE}", "(case when vsqlimpl_pkg.bool_{t2}({s2}) = 1 then {s1} else {s3} end)")
IfAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? {ANY} ? {NUMBERLIKE}", "(case when vsqlimpl_pkg.bool_{t2}({s2}) = 1 then {s1} else {s3} end)")
IfAST.add_rules(f"T1 <- {ANY} ? {ANY} ? NULL", "(case when vsqlimpl_pkg.bool_{t2}({s2}) = 1 then {s1} else {s3} end)")
IfAST.add_rules(f"T3 <- NULL ? {ANY} ? {ANY}", "(case when vsqlimpl_pkg.bool_{t2}({s2}) = 1 then {s1} else {s3} end)")

# Slice operator (A[B:C])
SliceAST.add_rules(f"T1 <- {TEXT}_{LIST}[NULL_{INTLIKE}:NULL_{INTLIKE}]", "vsqlimpl_pkg.slice_{t1}({s1}, {s2}, {s3})")
SliceAST.add_rules(f"NULLLIST <- NULLLIST[NULL_{INTLIKE}:NULL_{INTLIKE}]", "vsqlimpl_pkg.slice_{t1}({s1}, {s2}, {s3})")


###
### Class for regenerating the Java type information.
###

class JavaSource:
	"""
	A :class:`JavaSource` object combines the source code of a Java class that
	implements a vSQL AST type with the Python class that implements that AST
	type.

	It is used to update the vSQL syntax rules in the Java implemenatio of vSQL.
	"""

	_start_line = "//BEGIN RULES (don't remove this comment)"
	_end_line = "//END RULES (don't remove this comment)"

	def __init__(self, astcls:Type[AST], path:pathlib.Path):
		self.astcls = astcls
		self.path = path
		self.lines = path.read_text(encoding="utf-8").splitlines(False)

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} cls={self.cls!r} path={str(self.path)!r} at {id(self):#x}>"

	def new_lines(self) -> T_gen(str):
		"""
		Return an iterator over the new Java source code lines that should
		replace the static initialization block inside the Java source file.
		"""

		# How many ``addRule()`` calls to pack in one static method.
		# This avoids the ``code too large`` error from the Java compiler.
		bunch = 100

		number = 0

		yield f"\t{self._start_line}"
		for (i, rule) in enumerate(self.astcls.rules.values()):
			if i % bunch == 0:
				number += 1
				yield f"\tprivate static void addRulesPart{number}()"
				yield "\t{"
			yield f"\t\t{rule.java_source()}"
			if i % bunch == bunch-1:
				yield "\t}"
				yield ""

		if i % bunch != bunch-1:
			yield "\t}"
			yield ""

		yield f"\tstatic"
		yield "\t{"
		for i in range(1, number+1):
			yield f"\t\taddRulesPart{i}();"
		yield "\t}"

		yield f"\t{self._end_line}"

	def save(self) -> None:
		"""
		Resave the Java source code incorporating the new vSQL type info from the
		Python AST class.
		"""
		inrules = False

		with self.path.open("w", encoding="utf-8") as f:
			for line in self.lines:
				if inrules:
					if line.strip() == self._end_line:
						inrules = False
				else:
					if line.strip() == self._start_line:
						inrules = True
						for new_line in self.new_lines():
							f.write(f"{new_line}\n")
					else:
						f.write(f"{line}\n")

	@classmethod
	def all_java_source_files(cls, path: pathlib.Path) -> T_gen("JavaSource"):
		"""
		Return an iterator over all :class:`!JavaSource` objects that can be found
		in the directory ``path``. ``path`` should point to the directory
		containing the Java vSQL AST classes.
		"""

		# Find all AST classes that have rules
		classes = {cls.__name__: cls for cls in AST.all_types() if hasattr(cls, "rules")}

		for filename in path.glob("**/*.java"):
			try:
				# Do we have a Python class for this Java source?
				cls = classes[filename.stem]
			except KeyError:
				pass
			else:
				yield JavaSource(cls, filename)

	@classmethod
	def rewrite_all_java_source_files(cls, path:pathlib.Path, verbose:bool=False) -> None:
		"""
		Rewrite all Java source code files implementing Java vSQL AST classes
		in the directory ``path``. ``path`` should point to the directory
		containing the Java vSQL AST classes.
		"""
		if verbose:
			print(f"Rewriting Java source files in {str(path)!r}")
		for javasource in cls.all_java_source_files(path):
			javasource.save()


###
### Functions for regenerating the Oracle type information.
###

def oracle_sql_table() -> str:
	"""
	Return the SQL statement for creating the table ``VSQLRULE``.
	"""

	recordfields = [rule.oracle_fields() for rule in AST.all_rules()]

	sql = []
	sql.append("create table vsqlrule")
	sql.append("(")
	for (i, (fieldname, fieldtype)) in enumerate(fields.items()):
		term = "" if i == len(fields)-1 else ","
		if fieldname == "vr_cname":
			sql.append(f"\t{fieldname} varchar2(200) not null{term}")
		elif fieldtype is int:
			sql.append(f"\t{fieldname} integer not null{term}")
		elif fieldtype is T_opt_int:
			sql.append(f"\t{fieldname} integer{term}")
		elif fieldtype is datetime.datetime:
			sql.append(f"\t{fieldname} date not null{term}")
		elif fieldtype is str:
			size = max(len(r[fieldname]) for r in recordfields if fieldname in r and r[fieldname])
			sql.append(f"\t{fieldname} varchar2({size}) not null{term}")
		elif fieldtype is T_opt_str:
			size = max(len(r[fieldname]) for r in recordfields if fieldname in r and r[fieldname])
			sql.append(f"\t{fieldname} varchar2({size}){term}")
		else:
			raise ValueError(f"unknown field type {fieldtype!r}")
	sql.append(")")
	return "\n".join(sql)


def oracle_sql_procedure() -> str:
	"""
	Return the SQL statement for creating the procedure ``VSQLGRAMMAR_MAKE``.
	"""

	sql = []
	sql.append("create or replace procedure vsqlgrammar_make(c_user varchar2)")
	sql.append("as")
	sql.append("begin")
	sql.append("\tdelete from vsqlrule;")
	for rule in AST.all_rules():
		sql.append(f"\t{rule.oracle_source()}")
	sql.append("end;")
	return "\n".join(sql)


def oracle_sql_index() -> str:
	"""
	Return the SQL statement for creating the index ``VSQLRULE_I1``.
	"""

	return "create unique index vsqlrule_i1 on vsqlrule(vr_nodetype, vr_value, vr_signature, vr_arity)"


def oracle_sql_tablecomment() -> str:
	"""
	Return the SQL statement for creating a comment on the table ``VSQLRULE``.
	"""

	return "comment on table vsqlrule is 'Syntax rules for vSQL expressions.'"


def recreate_oracle(connectstring:str, verbose:bool=False) -> None:
	"""
	Recreate the vSQL syntax rules in the database.

	This recreate the procedure ``VSQLGRAMMAR_MAKE`` and the table ``VSQLRULE``
	and its content.
	"""

	from ll import orasql

	db = orasql.connect(connectstring, readlobs=True)
	cursor = db.cursor()

	oldtable = orasql.Table("VSQLRULE", connection=db)
	try:
		oldsql = oldtable.createsql(term=False).strip().lower().replace(" byte)", ")")
	except orasql.SQLObjectNotFoundError:
		oldsql = None

	newsql = oracle_sql_table()

	if oldsql is not None and oldsql != newsql:
		if verbose:
			print(f"Dropping old table VSQLRULE in {db.connectstring()!r}", file=sys.stderr)
		cursor.execute("drop table vsqlrule")
	if oldsql != newsql:
		if verbose:
			print(f"Creating new table VSQLRULE in {db.connectstring()!r}", file=sys.stderr)
		cursor.execute(newsql)
		if verbose:
			print(f"Creating index VSQLRULE_I1 in {db.connectstring()!r}", file=sys.stderr)
		cursor.execute(oracle_sql_index())
		if verbose:
			print(f"Creating table comment for VSQLRULE in {db.connectstring()!r}", file=sys.stderr)
		cursor.execute(oracle_sql_tablecomment())
	if verbose:
		print(f"Creating procedure VSQLGRAMMAR_MAKE in {db.connectstring()!r}", file=sys.stderr)
	cursor.execute(oracle_sql_procedure())
	if verbose:
		print(f"Calling procedure VSQLGRAMMAR_MAKE in {db.connectstring()!r}", file=sys.stderr)
	cursor.execute(f"begin vsqlgrammar_make('{scriptname}'); end;")
	if verbose:
		print(f"Committing transaction in {db.connectstring()!r}", file=sys.stderr)
	db.commit()


def main(args:Optional[Tuple[str, ...]]=None) -> None:
	import argparse
	p = argparse.ArgumentParser(description="Recreate vSQL type info for the Java and Oracle implementations")
	p.add_argument("-c", "--connectstring", help="Oracle database where the table VSQLRULE and the procedure VSQLGRAMMAR_MAKE will be created")
	p.add_argument("-j", "--javapath", dest="javapath", help="Path to the Java implementation of vSQL?", type=pathlib.Path)
	p.add_argument("-v", "--verbose", dest="verbose", help="Give a progress report? (default %(default)s)", default=False, action="store_true")

	args = p.parse_args(args)

	if args.connectstring:
		recreate_oracle(args.connectstring, verbose=args.verbose)
	if args.javapath:
		JavaSource.rewrite_all_java_source_files(args.javapath, verbose=args.verbose)


if __name__ == "__main__":
	sys.exit(main())
