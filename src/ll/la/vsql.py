#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2020 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
Classes and functions for compiling vSQL expressions.
"""

import sys, datetime, itertools, re, pathlib, typing

from ll import color, misc, ul4c, ul4on

try:
	from ll import orasql
except ImportError:
	orasql = None


###
### Global configurations
###

scriptname = misc.sysinfo.short_script_name


###
### Fields for the table ``VSQLRULE``
###

optstr = typing.Optional[str]
optint = typing.Optional[int]

fields = dict(
	vr_nodetype=str,
	vr_value=optstr,
	vr_result=str,
	vr_signature=optstr,
	vr_arity=int,
	vr_literal1=optstr,
	vr_child2=optint,
	vr_literal3=optstr,
	vr_child4=optint,
	vr_literal5=optstr,
	vr_child6=optint,
	vr_literal7=optstr,
	vr_child8=optint,
	vr_literal9=optstr,
	vr_child10=optint,
	vr_literal11=optstr,
	vr_child12=optint,
	vr_literal13=optstr,
	vr_cname=str,
	vr_cdate=datetime.datetime,
)


###
### Helper functions and classes
###

def subclasses(cls):
	yield cls
	for subcls in cls.__subclasses__():
		yield from subclasses(subcls)


class sqlliteral(str):
	"""
	Marker class that can be used to spcifiy that its value should be treated
	as literal SQL.
	"""
	pass


def sql(value):
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


def _offset(pos):
	# Note that we know that for our slices ``start``/``stop`` are never ``None``
	return slice(pos.start-9, pos.stop-9)


def compile(source, vars={}):
	template = ul4c.Template(f"<?return {source}?>")
	expr = template.content[-1].obj
	return AST.fromul4(source, expr, vars)


def compile_and_save(handler, cursor, source, datatype, function, **queryargs):
	if source is None:
		return None
	else:
		args = ", ".join(f"{a}=>:{a}" for a in queryargs)
		query = f"select {function}({args}) from dual"
		cursor.execute(query, **queryargs)
		dump = cursor.fetchone()[0]
		dump = dump.decode("utf-8")
		vars = ul4on.loads(dump)
		ast = compile(source, vars)
		vs_id = ast.save(handler, cursor=cursor)
		cursor.execute(
			"begin vsql_pkg.vsql_validate(:vs_id, :datatype); end;",
			vs_id=vs_id,
			datatype=datatype,
		)
		return vs_id


class Repr:
	def _ll_repr_prefix_(self):
		return f"{self.__class__.__module__}.{self.__class__.__qualname__}"

	def _ll_repr_suffix_(self):
		return f"at {id(self):#x}"

	def __repr__(self):
		parts = itertools.chain(
			(f"<{self._ll_repr_prefix_()}",),
			self._ll_repr_(),
			(f"{self._ll_repr_suffix_()}>",),
		)
		return " ".join(parts)

	def _ll_repr_(self):
		yield from ()

	def _repr_pretty_(self, p, cycle):
		if cycle:
			p.text(f"{self._ll_repr_prefix_()} ... {self._ll_repr_suffix_()}>")
		else:
			with p.group(3, f"<{self._ll_repr_prefix_()}", ">"):
				self._ll_repr_pretty_(p)
				p.breakable()
				p.text(self._ll_repr_suffix_())

	def _ll_repr_pretty_(self, p):
		pass


class DataType(misc.Enum):
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
	INTLIST = "intlist"
	NUMBERLIST = "numberlist"
	STRLIST = "strlist"
	CLOBLIST = "cloblist"
	DATELIST = "datelist"
	DATETIMELIST = "datetimelist"
	INTSET = "intset"
	NUMBERSET = "numberset"
	STRSET = "strset"
	DATESET = "dateset"
	DATETIMESET = "datetimeset"


class NodeType(misc.Enum):
	FIELD = "field"
	CONST_NONE = "const_none"
	CONST_BOOL = "const_bool"
	CONST_INT = "const_int"
	CONST_NUMBER = "const_number"
	CONST_STR = "const_str"
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
	TERNOP_IFELSE = "ternop_ifelse"
	ATTR = "attr"
	FUNC = "func"
	METH = "meth"


class Error(misc.Enum):
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
	DATATYPE_INTLIST = "datatype_intlist" # The datatype of the node should be ``intlist`` but isn't
	DATATYPE_NUMBERLIST = "datatype_numberlist" # The datatype of the node should be ``numberlist`` but isn't
	DATATYPE_STRLIST = "datatype_strlist" # The datatype of the node should be ``strlist`` but isn't
	DATATYPE_CLOBLIST = "datatype_cloblist" # The datatype of the node should be ``cloblist`` but isn't
	DATATYPE_DATELIST = "datatype_datelist" # The datatype of the node should be ``datelist`` but isn't
	DATATYPE_DATETIMELIST = "datatype_datetimelist" # The datatype of the node should be ``datetimelist`` but isn't
	DATATYPE_INTSET = "datatype_intset" # The datatype of the node should be ``intset`` but isn't
	DATATYPE_NUMBERSET = "datatype_numberset" # The datatype of the node should be ``numberset`` but isn't
	DATATYPE_STRSET = "datatype_strset" # The datatype of the node should be ``strset`` but isn't
	DATATYPE_DATESET = "datatype_dateset" # The datatype of the node should be ``dateset`` but isn't
	DATATYPE_DATETIMESET = "datatype_datetimeset" # The datatype of the node should be ``datetimeset`` but isn't


###
### Core classes
###

class Def(Repr):
	pass


@ul4on.register("de.livinglogic.vsql.field")
class Field(Def):
	def __init__(self, identifier=None, datatype=None, fieldsql=None, joinsql=None, refgroup=None):
		self.identifier = identifier
		self.datatype = datatype
		self.fieldsql = fieldsql
		self.joinsql = joinsql
		self.refgroup = refgroup

	def _ll_repr_(self):
		yield f"{self.identifier!r}"
		yield f"datatype={self.datatype!r}"
		yield f"fieldsql={self.fieldsql!r}"
		if self.joinsql is not None:
			yield f"joinsql={self.joinsql!r}"
		if self.refgroup is not None:
			yield f"refgroup.tablesql={self.refgroup.tablesql!r}"

	def _ll_repr_pretty_(self, p):
		p.text(" ")
		p.pretty(self.identifier)
		p.breakable()
		p.text("datatype=")
		p.pretty(self.datatype)
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

	def ul4ondump(self, encoder):
		encoder.dump(self.identifier)
		encoder.dump(self.datatype)
		encoder.dump(self.fieldsql)
		encoder.dump(self.joinsql)
		encoder.dump(self.refgroup)

	def ul4onload(self, decoder):
		self.identifier = decoder.load()
		self.datatype = decoder.load()
		self.fieldsql = decoder.load()
		self.joinsql = decoder.load()
		self.refgroup = decoder.load()


@ul4on.register("de.livinglogic.vsql.group")
class Group(Def):
	def __init__(self, tablesql=None, **fields):
		self.tablesql = tablesql
		self.fields = fields

	def _ll_repr_(self):
		yield f"tablesql={self.tablesql!r}"
		yield f"with {len(self.fields):,} fields"

	def _ll_repr_pretty_(self, p):
		p.breakable()
		p.text("tablesql=")
		p.pretty(self.tablesql)
		for (fieldname, field) in self.fields.items():
			p.breakable()
			p.text(f"fields.{fieldname}=")
			p.pretty(field)

	def __getitem__(self, key):
		if key in self.fields:
			return self.fields[key]
		elif "*" in self.fields:
			return self.fields["*"]
		else:
			raise KeyError(key)

	def ul4ondump(self, encoder):
		encoder.dump(self.tablesql)
		encoder.dump(self.fields)

	def ul4onload(self, decoder):
		self.tablesql = decoder.load()
		self.fields = decoder.load()


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

	def __init__(self, ast, result, name, key, signature, source):
		self.ast = ast
		self.result = result
		self.name = name
		self.key = key
		self.signature = signature
		self.source = self._parse_source(signature, source)


	def _key(self):
		key = ", ".join(p.name if isinstance(p, DataType) else repr(p) for p in self.key)
		return f"({key})"

	def _signature(self):
		signature = ", ".join(p.name for p in self.signature)
		return f"({signature})"

	def _ll_repr_(self):
		yield f"nodetype={self.ast.nodetype.name}"
		yield f"result={self.result.name}"
		if self.name is not None:
			yield f"name={self.name!r}"
		yield f"key={self._key()}"
		yield f"signature={self._signature()}"
		yield f"source={self.source}"

	def _ll_repr_pretty_(self, p):
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
	def _parse_source(cls, signature, source):
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

	def java_source(self):
		key = ", ".join(
			f"VSQLDataType.{p.name}" if isinstance(p, DataType) else misc.javaexpr(p)
			for p in self.key
		)

		return f"addRule(rules, VSQLDataType.{self.result.name}, {key});"

	def oracle_fields(self):
		fields = {}

		fields["vr_nodetype"] = self.ast.nodetype.value
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

	def oracle_source(self):
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


class AST(Repr):
	dbnodetype = None
	dbnodevalue = None
	datatype = None

	def __init__(self, *content):
		final_content = []
		for item in content:
			if isinstance(item, str):
				if final_content and isinstance(final_content[-1], str):
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
	def fromul4(cls, source, node, vars):
		if isinstance(node, ul4c.Const):
			if node.value is None:
				return NoneAST.fromul4(source, node, vars)
			else:
				try:
					vsqltype = _consts[type(node.value)]
				except KeyError:
					raise TypeError(f"constant of type {misc.format_class(node.value)} not supported!") from None
				return vsqltype.fromul4(source, node, vars)
		else:
			try:
				vsqltype = _ul42vsql[type(node)]
			except KeyError:
				pass
			else:
				return vsqltype.fromul4(source, node, vars)
		if isinstance(node, ul4c.Var):
			field = vars.get(node.name, None)
			return FieldRef(source, _offset(node.pos), None, node.name, field)
		elif isinstance(node, ul4c.Attr):
			vsqlnode = cls.fromul4(source, node.obj, vars)
			if isinstance(vsqlnode, FieldRef) and isinstance(vsqlnode.field, Field) and vsqlnode.field.refgroup:
				try:
					field = vsqlnode.field.refgroup.fields[node.attrname]
				except KeyError:
					try:
						field = vsqlnode.field.refgroup.fields["*"]
					except KeyError:
						pass # Fall through to return a generic :class:`Attr` node
					else:
						return FieldRef(source, _offset(node.pos), vsqlnode, node.attrname, field)
				else:
					return FieldRef(source, _offset(node.pos), vsqlnode, node.attrname, field)
			return Attr(source, _offset(node.pos), vsqlnode, node.attrname)
		elif isinstance(node, ul4c.Call):
			vsqlnode = cls.fromul4(source, node.obj, vars)
			args = []
			for arg in node.args:
				if not isinstance(arg, ul4c.PosArg):
					raise TypeError(f"Can't compile UL4 expression of type {misc.format_class(arg)}!")
				args.append(AST.fromul4(source, arg.value, vars))
			if isinstance(vsqlnode, FieldRef):
				if vsqlnode.parent is not None:
					return Meth(source, _offset(node.pos), vsqlnode.parent, vsqlnode.identifier, args)
				else:
					return Func(source, _offset(node.pos), vsqlnode.identifier, args)
			elif isinstance(vsqlnode, Attr):
				return Meth(source, _offset(node.pos), vsqlnode.obj, vsqlnode.attrname, args)
		raise TypeError(f"Can't compile UL4 expression of type {misc.format_class(node)}!")

	@classmethod
	def all_types(cls):
		"""
		Return this class and all subclasses.

		This is a generator.
		"""
		yield cls
		for subcls in cls.__subclasses__():
			yield from subcls.all_types()

	@classmethod
	def all_rules(cls):
		"""
		Return all grammar rules of this class and all its subclasses.

		This is a generator.
		"""
		for subcls in cls.__subclasses__():
			if hasattr(subcls, "rules"):
				yield from subcls.rules.values()

	@classmethod
	def _add_rule(cls, rule):
		cls.rules[rule.key] = rule

	@classmethod
	def typeref(cls, s):
		if s.startswith("T") and s[1:].isdigit():
			return int(s[1:])
		return None

	@classmethod
	def _specs(cls, spec):
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
	def add_rules(cls, spec, source):
		"""
		Register new syntax rules to the rules of this AST class.

		These rules are used for type checking and type inference and for
		converting the vSQL AST into SQL source code.

		``spec`` specifies the allowed combinations of operand types and the
		resulting type. If consists of the following:

		Upper case words
			These specify types (for a list of allowed values see :class:`DataType`).
			Also allowed are: ``T`` followed by an integer, this is used to refer
			to another type in the spec and a combination of several types joined
			with ``_``. This is a union type, i.e. any of the types in the
			combination are allowed.

		Lower case words
			They specify to names of functions, methods or attributes

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

		``T1 <- BOOL_INT + T1
			This is equivalent to the two rules ``BOOL <- BOOL + BOOL`` and
			``INT <- INT + INT``.

		Note that each rule will only be registered once. So the following code::

			AddAST.add_rules("INT <- BOOL_INT + BOOL_INT")
			AddAST.add_rules("NUMBER <- BOOL_INT_NUMBER + BOOL_INT_NUMBER")

		So this will register the rule ``INT <- BOOL + BOOL``, but not
		``NUMBER <- BOOL + BOOL``.

		``source`` specifies the SQL source that will be generated for this
		expression. Two types of placeholders are supported: ``{s1}`` means
		"embed the source code of the first operand in this spot" (and ``{s2}``
		etc. accordingly) and ``{t1}`` embeds the type name (in lowercase) in this
		spot (and ``{t2}`` etc. accordingly).
		"""

		# Split on non-names and drop empty parts
		spec = tuple(filter(None, Rule._re_sep.split(spec)))

		spec = [p.split("_") if p.isupper() else (p,) for p in spec]
		for (name, spec) in cls._specs(spec):
			# Drop return type from the lookup key
			key = spec[1:]
			if key not in cls.rules:
				result = spec[0]
				# Drop name from the signature
				signature = tuple(p for p in key if isinstance(p, DataType))
				cls._add_rule(Rule(cls, result, name, key, signature, source))

	def validate(self):
		"""
		Validate the content of this AST node.

		If this node turns out to be invalid it will set ``datatype`` to ``None``
		and ``error`` to the appropriate :class:`Error` value.

		If this node turns out to be valid, :meth:`!validate` will set ``error``
		to ``None`` and ``datatype`` to the resulting data type of this node.
		"""
		pass

	def source(self):
		return "".join(s for s in self._source())

	def _source(self):
		for item in self.content:
			if isinstance(item, str):
				yield item
			else:
				yield from item._source()

	def dbchildren(self):
		yield from ()

	def save(self, handler, cursor=None, vs_id_super=None, vs_order=None, vss_id=None):
		"""
		Save :obj:`self` to the :class:`DBHandler` :obj:`handler`.

		``cursor``, ``vs_id_super``, ``vs_order`` and ``vss_id`` are used
		internally for recursive calls and should not be passed by the user.
		"""
		if cursor is None:
			cursor = handler.cursor()
		if vss_id is None:
			r = handler.proc_vsqlsource_insert(
				cursor,
				c_user=handler.ide_id,
				p_vss_source=self.source(),
			)
			vss_id = r.p_vss_id
		r = handler.proc_vsql_insert(
			cursor,
			c_user=handler.ide_id,
			p_vs_id_super=vs_id_super,
			p_vs_order=vs_order,
			p_vs_nodetype=self.dbnodetype,
			p_vs_value=self.dbnodevalue,
			p_vs_datatype=self.datatype,
			p_vss_id=vss_id,
			p_vs_start=self.pos.start,
			p_vs_stop=self.pos.stop,
		)
		vs_id = r.p_vs_id
		order = 10
		for child in self.dbchildren():
			child.save(handler, cursor, vs_id, order, vss_id)
			order += 10
		return vs_id

	def __str__(self):
		parts = [f"{self.__class__.__module__}.{self.__class__.__qualname__}"]
		if self.datatype is not None:
			parts.append(f"(datatype {self.datatype.name})")
		if self.error is not None:
			parts.append(f"(error {self.error.name})")
		parts.append(f": {self.source()}")
		return "".join(parts)

	def _ll_repr_(self):
		if self.datatype is not None:
			yield f"datatype={self.datatype.name}"
		if self.error is not None:
			yield f"error={self.error.name}"
		yield f"source={self.source()!r}"

	def _ll_repr_pretty_(self, p):
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
	def _wrap(cls, obj, cond):
		if cond:
			yield "("
		yield obj
		if cond:
			yield ")"

	def ul4ondump(self, encoder):
		encoder.dump(self._source)
		encoder.dump(self.pos)

	def ul4onload(self, decoder):
		self._source = decoder.load()
		self.pos = decoder.load()


class ConstAST(AST):
	precedence = 20

	@staticmethod
	def make(value):
		cls = _consts.get(type(value))
		if cls is None:
			raise TypeError(value)
		return cls.make(value)


@ul4on.register("de.livinglogic.vsql.none")
class NoneAST(ConstAST):
	nodetype = NodeType.CONST_NONE
	datatype = DataType.NULL

	@classmethod
	def make(cls):
		return cls("None")

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos))


class _ConstWithValueAST(ConstAST):
	def __init__(self, value, *content):
		super().__init__(*content)
		self.value = value

	@classmethod
	def make(cls, value):
		return cls(value, ul4c._repr(value))

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos), node.value)

	@property
	def dbnodevalue(self):
		return self.value

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"value={self.value!r}"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("value=")
		p.pretty(self.value)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.value)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.value = decoder.load()


@ul4on.register("de.livinglogic.vsql.bool")
class BoolAST(_ConstWithValueAST):
	nodetype = NodeType.CONST_BOOL
	datatype = DataType.BOOL

	@classmethod
	def make(cls, value):
		return cls(value, "True" if value else "False")

	@property
	def dbnodevalue(self):
		return "True" if self.value else "False"


@ul4on.register("de.livinglogic.vsql.int")
class IntAST(_ConstWithValueAST):
	nodetype = NodeType.CONST_INT
	datatype = DataType.INT

	@property
	def dbnodevalue(self):
		return str(self.value)


@ul4on.register("de.livinglogic.vsql.number")
class NumberAST(_ConstWithValueAST):
	nodetype = NodeType.CONST_NUMBER
	datatype = DataType.NUMBER

	@property
	def dbnodevalue(self):
		return repr(self.value)


@ul4on.register("de.livinglogic.vsql.str")
class StrAST(_ConstWithValueAST):
	nodetype = NodeType.CONST_STR
	datatype = DataType.STR


@ul4on.register("de.livinglogic.vsql.color")
class ColorAST(_ConstWithValueAST):
	nodetype = NodeType.CONST_COLOR
	datatype = DataType.COLOR

	@property
	def dbnodevalue(self):
		c = self.value
		return f"{c.r():02x}{c.g():02x}{c.b():02x}{c.a():02x}"


@ul4on.register("de.livinglogic.vsql.date")
class DateAST(_ConstWithValueAST):
	nodetype = NodeType.CONST_DATE
	datatype = DataType.DATE

	@property
	def dbnodevalue(self):
		return f"{self.value:%Y-%m-%d}"


@ul4on.register("de.livinglogic.vsql.datetime")
class DateTimeAST(_ConstWithValueAST):
	nodetype = NodeType.CONST_DATETIME
	datatype = DataType.DATETIME

	@classmethod
	def make(cls, value):
		value = value.replace(microsecond=0)
		return cls(value, ul4c._repr(value))

	@property
	def dbnodevalue(self):
		return f"{self.value:%Y-%m-%dT%H:%M:%S}"


@ul4on.register("de.livinglogic.vsql.list")
class ListAST(AST):
	nodetype = NodeType.LIST
	precedence = 20

	def __init__(self, *content):
		super().__init__(*content)
		self.items = [item for item in content if isinstance(item, AST)]
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, *items):
		content = []
		for (i, item) in enumerate(items):
			content.append(", " if i else "[")
			content.append(item)
		content.append("]")
		return cls(*content)

	@classmethod
	def fromul4(cls, source, node, vars):
		self = cls(source, _offset(node.pos))
		for item in node.items:
			if not isinstance(item, ul4c.SeqItem):
				raise TypeError(f"Can't compile UL4 expression of type {misc.format_class(item)}!")
			self.items.append(AST.fromul4(source, item.value, vars))
		return self

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"with {len(self.items):,} items"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		for item in self.items:
			p.breakable()
			p.pretty(item)

	def dbchildren(self):
		yield from self.items

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.items)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.items = decoder.load()


@ul4on.register("de.livinglogic.vsql.set")
class SetAST(AST):
	nodetype = NodeType.SET
	precedence = 20

	def __init__(self, *content):
		super().__init__(*content)
		self.items = [item for item in content if isinstance(item, AST)]
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, *items):
		if items:
			content = []
			for (i, item) in enumerate(items):
				content.append(", " if i else "{")
				content.append(item)
			content.append("}")
			return cls(*content)
		else:
			return cls("{/}")

	def dbchildren(self):
		yield from self.items

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"with {len(self.items):,} items"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		for item in self.items:
			p.breakable()
			p.pretty(item)

	@classmethod
	def fromul4(cls, source, node, vars):
		self = cls(source, _offset(node.pos))
		for item in node.items:
			if not isinstance(item, ul4c.SeqItem):
				raise TypeError(f"Can't compile UL4 expression of type {misc.format_class(item)}!")
			self.items.append(AST.fromul4(source, item.value, vars))
		return self

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.items)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.items = decoder.load()


@ul4on.register("de.livinglogic.vsql.fieldref")
class FieldRefAST(AST):
	nodetype = NodeType.FIELD
	precedence = 19

	def __init__(self, parent, identifier, field, *content):
		"""
		Create a :class:`FieldRef` object.

		There are three possible scenarios with respect to :obj`identifier` and
		:obj:`field`:

		``field is not None and field.identifier == identifier``
			In this case we have a valid :class:`Field` that describes a real
			field.

		``field is not None and field.identifier != identifier and field.identifier == "*"``
			In this case :obj:`field` is the :class:`Field` object for the generic
			typed request parameters. E.g. when the vSQL expression is
			``params.str.foo`` then :obj:`field` references the :class:`Field` for
			``params.str.*``, so ``field.identifier == "*" and
			``identifier == "foo"``.

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
	def make_root(cls, field):
		if isinstance(field, str):
			# This is an invalid field reference
			return FieldRefAST(None, field, None, field)
		else:
			return FieldRefAST(None, field.identifier, field, field.identifier)

	@classmethod
	def make(cls, parent, identifier):
		result_field = None
		parent_field = parent.field
		if parent_field is not None:
			group = parent_field.refgroup
			if group is not None:
				try:
					result_field = group[identifier]
				except KeyError:
					pass

		return FieldRefAST(parent, identifier, result_field, ".", identifier)

	def validate(self):
		self.error = Error.FIELD if self.field is None else None

	@property
	def datatype(self):
		return self.field.datatype if self.field is not None else None

	@property
	def dbnodevalue(self):
		identifierpath = []
		node = self
		while node is not None:
			identifierpath.insert(0, node.identifier)
			node = node.parent
		return ".".join(identifierpath)

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		if self.parent is not None:
			yield f"parent={self.parent!r}"
		if self.field is None or self.field.identifier != self.identifier:
			yield f"identifier={self.identifier!r}"
		if self.field is not None:
			yield f"field={self.field!r}"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		p.text(" ")
		p.pretty(self.identifier)
		if self.parent is not None:
			p.breakable()
			p.text("parent=")
			p.pretty(self.parent)
		if self.field is None or self.field.identifier != self.identifier:
			p.breakable()
			p.text("identifier=")
			p.pretty(self.identifier)
		if self.field is not None:
			p.breakable()
			p.text("field=")
			p.pretty(self.field)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.parent)
		encoder.dump(self.identifier)
		encoder.dump(self.field)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.parent = decoder.load()
		self.identifier = decoder.load()
		self.field = decoder.load()


class BinaryAST(AST):
	def __init__(self, obj1, obj2, *content):
		super().__init__(*content)
		self.obj1 = obj1
		self.obj2 = obj2
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj1, obj2):
		return cls(
			obj1,
			obj2,
			*cls._wrap(obj1, obj1.precedence < cls.precedence),
			f" {cls.operator} ",
			*cls._wrap(obj2, obj2.precedence <= cls.precedence),
		)

	def validate(self):
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
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos), AST.fromul4(source, node.obj1, vars), AST.fromul4(source, node.obj2, vars))

	def dbchildren(self):
		yield self.obj1
		yield self.obj2

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"obj1={self.obj1!r}"
		yield f"obj2={self.obj2!r}"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj1=")
		p.pretty(self.obj1)
		p.breakable()
		p.text("obj2=")
		p.pretty(self.obj2)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj1)
		encoder.dump(self.obj2)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj1 = decoder.load()
		self.obj2 = decoder.load()


@ul4on.register("de.livinglogic.vsql.eq")
class EQAST(BinaryAST):
	nodetype = NodeType.CMP_EQ
	precedence = 6
	operator = "=="
	rules = {}


@ul4on.register("de.livinglogic.vsql.ne")
class NEAST(BinaryAST):
	nodetype = NodeType.CMP_NE
	precedence = 6
	operator = "!="
	rules = {}


@ul4on.register("de.livinglogic.vsql.lt")
class LTAST(BinaryAST):
	nodetype = NodeType.CMP_LT
	precedence = 6
	operator = "<"
	rules = {}


@ul4on.register("de.livinglogic.vsql.le")
class LEAST(BinaryAST):
	nodetype = NodeType.CMP_LE
	precedence = 6
	operator = "<="
	rules = {}


@ul4on.register("de.livinglogic.vsql.gt")
class GTAST(BinaryAST):
	nodetype = NodeType.CMP_GT
	precedence = 6
	operator = ">"
	rules = {}


@ul4on.register("de.livinglogic.vsql.ge")
class GEAST(BinaryAST):
	nodetype = NodeType.CMP_GE
	precedence = 6
	operator = ">="
	rules = {}


@ul4on.register("de.livinglogic.vsql.add")
class AddAST(BinaryAST):
	nodetype = NodeType.BINOP_ADD
	precedence = 11
	operator = "+"
	rules = {}


@ul4on.register("de.livinglogic.vsql.sub")
class SubAST(BinaryAST):
	nodetype = NodeType.BINOP_SUB
	precedence = 11
	operator = "-"
	rules = {}


@ul4on.register("de.livinglogic.vsql.mul")
class MulAST(BinaryAST):
	nodetype = NodeType.BINOP_MUL
	precedence = 12
	operator = "*"
	rules = {}


@ul4on.register("de.livinglogic.vsql.floordiv")
class FloorDivAST(BinaryAST):
	nodetype = NodeType.BINOP_FLOORDIV
	precedence = 12
	operator = "//"
	rules = {}


@ul4on.register("de.livinglogic.vsql.truediv")
class TrueDivAST(BinaryAST):
	nodetype = NodeType.BINOP_TRUEDIV
	precedence = 12
	operator = "/"
	rules = {}


@ul4on.register("de.livinglogic.vsql.mod")
class ModAST(BinaryAST):
	nodetype = NodeType.BINOP_MOD
	precedence = 12
	operator = "%"
	rules = {}


@ul4on.register("de.livinglogic.vsql.and")
class AndAST(BinaryAST):
	nodetype = NodeType.BINOP_AND
	precedence = 4
	operator = "and"
	rules = {}


@ul4on.register("de.livinglogic.vsql.or")
class OrAST(BinaryAST):
	nodetype = NodeType.BINOP_OR
	precedence = 4
	operator = "or"
	rules = {}


@ul4on.register("de.livinglogic.vsql.contains")
class ContainsAST(BinaryAST):
	nodetype = NodeType.BINOP_CONTAINS
	precedence = 6
	operator = "in"
	rules = {}


@ul4on.register("de.livinglogic.vsql.notcontains")
class NotContainsAST(BinaryAST):
	nodetype = NodeType.BINOP_NOTCONTAINS
	precedence = 6
	operator = "not in"
	rules = {}


@ul4on.register("de.livinglogic.vsql.is")
class IsAST(BinaryAST):
	nodetype = NodeType.BINOP_IS
	precedence = 6
	operator = "is"
	rules = {}


@ul4on.register("de.livinglogic.vsql.isnot")
class IsNotAST(BinaryAST):
	nodetype = NodeType.BINOP_ISNOT
	precedence = 6
	operator = "is not"
	rules = {}


@ul4on.register("de.livinglogic.vsql.item")
class ItemAST(BinaryAST):
	nodetype = NodeType.BINOP_ITEM
	precedence = 16
	rules = {}

	@classmethod
	def make(self, obj1, obj2):
		if obj1.precedence >= self.precedence:
			return cls(obj1, obj2, obj1, "[", obj2, "]")
		else:
			return cls(obj1, obj2, "(", obj1, ")[", obj2, "]")

	@classmethod
	def fromul4(cls, source, node, vars):
		if isinstance(node.obj2, ul4c.Slice):
			return Slice.fromul4(source, node, vars)
		return super().fromul4(source, node, vars)


@ul4on.register("de.livinglogic.vsql.shiftleft")
class ShiftLeftAST(BinaryAST):
	nodetype = NodeType.BINOP_SHIFTLEFT
	precedence = 10
	operator = "<<"
	rules = {}


@ul4on.register("de.livinglogic.vsql.shiftright")
class ShiftRightAST(BinaryAST):
	nodetype = NodeType.BINOP_SHIFTRIGHT
	precedence = 10
	operator = ">>"
	rules = {}


@ul4on.register("de.livinglogic.vsql.bitand")
class BitAndAST(BinaryAST):
	nodetype = NodeType.BINOP_BITAND
	precedence = 9
	operator = "&"
	rules = {}


@ul4on.register("de.livinglogic.vsql.bitor")
class BitOrAST(BinaryAST):
	nodetype = NodeType.BINOP_BITOR
	precedence = 7
	operator = "|"
	rules = {}


@ul4on.register("de.livinglogic.vsql.bitxor")
class BitXOrAST(BinaryAST):
	nodetype = NodeType.BINOP_BITXOR
	precedence = 8
	operator = "^"
	rules = {}


class UnaryAST(AST):
	def __init__(self, obj, *content):
		super().__init__(*content)
		self.obj = obj
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj):
		return cls(
			obj,
			cls.operator,
			*cls._wrap(obj, obj.precedence <= cls.precedence),
		)

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos), AST.fromul4(source, node.obj, vars))

	def validate(self):
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

	def dbchildren(self):
		yield self.obj

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"obj={self.obj!r}"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj = decoder.load()


@ul4on.register("de.livinglogic.vsql.not")
class NotAST(UnaryAST):
	nodetype = NodeType.UNOP_NOT
	precedence = 5
	operator = "not "
	rules = {}


@ul4on.register("de.livinglogic.vsql.neg")
class NegAST(UnaryAST):
	nodetype = NodeType.UNOP_NEG
	precedence = 14
	operator = "-"
	rules = {}


@ul4on.register("de.livinglogic.vsql.bitnot")
class BitNotAST(UnaryAST):
	nodetype = NodeType.UNOP_BITNOT
	precedence = 14
	operator = "~"
	rules = {}


@ul4on.register("de.livinglogic.vsql.if")
class IfAST(AST):
	nodetype = NodeType.TERNOP_IFELSE
	precedence = 3
	rules = {}

	def __init__(self, objif, objcond, objelse, *content):
		super().__init__(*content)
		self.objif = objif
		self.objcond = objcond
		self.objelse = objelse
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, objif, objcond, objelse):
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

	def validate(self):
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
	def fromul4(cls, source, node, vars):
		return cls(
			source,
			_offset(node.pos),
			AST.fromul4(source, node.objif, vars),
			AST.fromul4(source, node.objcond, vars),
			AST.fromul4(source, node.objelse, vars),
		)

	def dbchildren(self):
		yield self.objif
		yield self.objcond
		yield self.objelse

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"objif={self.objif!r}"
		yield f"objcond={self.objcond!r}"
		yield f"objelse={self.objelse!r}"

	def _ll_repr_pretty_(self, p):
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

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.objif)
		encoder.dump(self.objcond)
		encoder.dump(self.objelse)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.objif = decoder.load()
		self.objcond = decoder.load()
		self.objelse = decoder.load()


@ul4on.register("de.livinglogic.vsql.if")
class SliceAST(AST):
	nodetype = NodeType.TERNOP_SLICE
	precedence = 16
	rules = {}

	def __init__(self, obj, index1, index2, *content):
		super().__init__(*content)
		self.obj = obj
		self.index1 = index1
		self.index2 = index2
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj, index1, index2):
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
		)

	def validate(self):
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
	def fromul4(cls, source, node, vars):
		return cls(
			source,
			_offset(node.pos),
			AST.fromul4(source, node.obj1, vars),
			AST.fromul4(source, node.obj2.index1, vars) if node.obj2.index1 is not None else None,
			AST.fromul4(source, node.obj2.index2, vars) if node.obj2.index2 is not None else None,
		)

	def dbchildren(self):
		yield self.obj
		if self.index1 is None:
			pos = self.obj.pos.stop
			yield None_(self._source, slice(pos, pos))
		else:
			pos = self.index1.stop
			yield self.index1
		if self.index2 is None:
			yield None_(self._source, slice(pos, pos))
		else:
			yield self.index2

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"obj={self.obj!r}"
		if self.index1 is not None:
			yield f"index1={self.index1!r}"
		if self.index2 is not None:
			yield f"index2={self.index2!r}"

	def _ll_repr_pretty_(self, p):
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

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj)
		encoder.dump(self.index1)
		encoder.dump(self.index1)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj = decoder.load()
		self.index1 = decoder.load()
		self.index2 = decoder.load()


@ul4on.register("de.livinglogic.vsql.attr")
class AttrAST(AST):
	nodetype = NodeType.ATTR
	precedence = 19
	rules = {}
	names = set()

	def __init__(self, obj, attrname, *content):
		super().__init__(*content)
		self.obj = obj
		self.attrname = attrname
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj, attrname):
		return cls(
			obj,
			attrname,
			*cls._wrap(obj, obj.precedence < cls.precedence),
			".",
			attrname,
		)

	@classmethod
	def _add_rule(cls, rule):
		super()._add_rule(rule)
		cls.names.add(rule.name)

	def validate(self):
		if self.obj.error:
			self.error = Error.SUBNODEERROR
		signature = (self.obj.datatype, self.attrname)
		try:
			rule = self.rules[signature]
		except KeyError:
			self.error = Error.SUBNODETYPES if self.name in self.names else Error.NAME
			self.datatype = None
		else:
			self.error = None
			self.datatype = rule.result

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(
			source,
			_offset(node.pos),
			AST.fromul4(source, node.obj1, vars),
			node.attrname,
		)

	@property
	def dbnodevalue(self):
		return self.attrname

	def dbchildren(self):
		yield self.obj

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"obj={self.obj!r}"
		yield f"attrname={self.attrname!r}"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)
		p.breakable()
		p.text("attrname=")
		p.pretty(self.attrname)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj)
		encoder.dump(self.attrname)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj = decoder.load()
		self.attrname = decoder.load()


@ul4on.register("de.livinglogic.vsql.func")
class FuncAST(AST):
	nodetype = NodeType.FUNC
	precedence = 18
	rules = {}
	names = {} # Maps function names to set of supported arities

	def __init__(self, name, args, *content):
		super().__init__(*content)
		self.name = name
		self.args = args
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, name, *args):
		content = [name, "("]
		for (i, arg) in enumerate(args):
			if i:
				content.append(", ")
			content.append(arg)
		content.append(")")

		return cls(name, args, *content)

	@classmethod
	def _add_rule(cls, rule):
		super()._add_rule(rule)
		if rule.name not in cls.names:
			cls.names[rule.name] = set()
		cls.names[rule.name].add(len(rule.signature))

	def validate(self):
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
	def dbnodevalue(self):
		return self.name

	def dbchildren(self):
		yield from self.args

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"{self.name!r}"
		yield f"with {len(self.args):,} arguments"

	def _ll_repr_pretty_(self, p):
		super()._ll_repr_pretty_(p)
		for (i, arg) in enumerate(self.args):
			p.breakable()
			p.text(f"args[{i}]=")
			p.pretty(arg)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.name)
		encoder.dump(self.args)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.name = decoder.load()
		self.args = decoder.load()


@ul4on.register("de.livinglogic.vsql.meth")
class MethAST(AST):
	nodetype = NodeType.METH
	precedence = 17
	rules = {}
	names = {} # Maps (type, meth name) to set of supported arities

	def __init__(self, obj, name, args, *content):
		super().__init__(*content)
		self.obj = obj
		self.name = name
		self.args = args or ()
		self.datatype = None
		self.validate()

	@classmethod
	def make(cls, obj, name, *args):
		content = [*cls._wrap(obj, obj.precedence < cls.precedence), ".", name, "("]
		for (i, arg) in enumerate(args):
			if i:
				content.append(", ")
			content.append(arg)
		content.append(")")

		return cls(obj, name, args, *content)

	@classmethod
	def _add_rule(cls, rule):
		super()._add_rule(rule)
		key = (rule.signature[0], rule.name)
		if key not in cls.names:
			cls.names[key] = set()
		cls.names[key].add(len(rule.signature)-1)

	def validate(self):
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
	def dbnodevalue(self):
		return self.name

	def dbchildren(self):
		yield self.obj
		yield from self.args

	def _ll_repr_(self):
		yield from super()._ll_repr_()
		yield f"obj={self.obj!r}"
		yield f"name={self.name!r}"
		yield f"with {len(self.args):,} arguments"

	def _ll_repr_pretty_(self, p):
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

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj)
		encoder.dump(self.name)
		encoder.dump(self.args)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj = decoder.load()
		self.name = decoder.load()
		self.args = decoder.load()


_consts = {
	bool: BoolAST,
	int: IntAST,
	float: NumberAST,
	str: StrAST,
	color.Color: ColorAST,
	datetime.date: DateAST,
	datetime.datetime: DateTimeAST,
}

# Set of UL4 AST nodes that directly map to their equivalent vSQL version
_ops = {ul4c.IfAST, ul4c.NotAST, ul4c.NegAST, ul4c.BitNotAST, ul4c.ListAST, ul4c.SetAST}
_ops.update(ul4c.BinaryAST.__subclasses__())

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
BOOL_NUMBER = f"BOOL_INT_NUMBER_COLOR_DATEDELTA_DATETIMEDELTA_MONTHDELTA"

TEXT = f"STR_CLOB"
LIST = f"INTLIST_NUMBERLIST_STRLIST_CLOBLIST_DATELIST_DATETIMELIST"
SET = f"INTSET_NUMBERSET_STRSET_DATESET_DATETIMESET"
SEQ = f"{TEXT}_{LIST}_{SET}"
ANY = "_".join(DataType.__members__.keys())

# Function ``today()``
FuncAST.add_rules(f"DATE today", "trunc(sysdate)")

# Function ``now(0``
FuncAST.add_rules(f"DATETIME now", "sysdate")

# Function ``bool()``
FuncAST.add_rules(f"BOOL <- bool()", "0")
FuncAST.add_rules(f"BOOL <- bool(NULL)", "0")
FuncAST.add_rules(f"BOOL <- bool(BOOL)", "{s1}")
FuncAST.add_rules(f"BOOL <- bool(INT_NUMBER_DATEDELTA_DATETIMEDELTA_MONTHDELTA)", "(case {s1} when 0 then 0 when null then 0 else 1 end)")
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
FuncAST.add_rules(f"STR <- str(DATELIST)", "vsqlimpl_pkg.repr_datelist({s1})")
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
FuncAST.add_rules(f"DATETIME <- datetime(DATE, INT)", "?")
FuncAST.add_rules(f"DATETIME <- datetime(DATE, INT, INT)", "?")
FuncAST.add_rules(f"DATETIME <- datetime(DATE, INT, INT, INT)", "?")

# Function ``len()``
FuncAST.add_rules(f"INT <- len({TEXT})", "nvl(length({s1}), 0)")
FuncAST.add_rules(f"INT <- len({LIST})", "vsqlimpl_pkg.len_{t1}({s1})")
FuncAST.add_rules(f"INT <- len(INTSET)", "vsqlimpl_pkg.len_{t1}({s1})")
FuncAST.add_rules(f"INT <- len(NUMBERSET)", "vsqlimpl_pkg.len_{t1}({s1})")
FuncAST.add_rules(f"INT <- len(STRSET)", "vsqlimpl_pkg.len_{t1}({s1})")
FuncAST.add_rules(f"INT <- len(DATESET)", "vsqlimpl_pkg.len_{t1}({s1})")
FuncAST.add_rules(f"INT <- len(DATETIMESET)", "vsqlimpl_pkg.len_{t1}({s1})")

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
FuncAST.add_rules(f"T1 <- list({LIST})", "{s1}")
FuncAST.add_rules(f"INTLIST <- list(INTSET)", "{s1}")
FuncAST.add_rules(f"NUMBERLIST <- list(NUMBERSET)", "{s1}")
FuncAST.add_rules(f"STRLIST <- list(STRSET)", "{s1}")
FuncAST.add_rules(f"DATELIST <- list(DATESET)", "{s1}")
FuncAST.add_rules(f"DATETIMELIST <- list(DATETIMESET)", "{s1}")

# Function `set()``
FuncAST.add_rules(f"STRSET <- set({TEXT})", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"T1 <- set({SET})", "{s1}")
FuncAST.add_rules(f"INTSET <- set(INTLIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"NUMBERSET <- set(NUMBERLIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"STRSET <- set(STRLIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"DATESET <- set(DATELIST)", "vsqlimpl_pkg.set_{t1}({s1})")
FuncAST.add_rules(f"DATETIMESET <- set(DATETIMELIST)", "vsqlimpl_pkg.set_{t1}({s1})")

# Function ``geo()``
FuncAST.add_rules(f"NUMBER <- dist(GEO, GEO)", "vsqlimpl_pkg.dist_geo_geo({s1}, {s2})")

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
EQAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST == INTLIST_NUMBERLIST", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- STRLIST_CLOBLIST == STRLIST_CLOBLIST", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- {SET} == T1", "vsqlimpl_pkg.eq_{t1}_{t2}({s1}, {s2})")
EQAST.add_rules(f"BOOL <- DATESET_DATETIMESET == DATESET_DATETIMESET", "vsqlimpl_pkg.eq_datetimeset_datetimeset({s1}, {s2})")
EQAST.add_rules(f"BOOL <- {ANY} == {ANY}", "(case when {s1} is null and {s2} is null then 1 else 0 end)")

# Inequality comparison (A != B)
NEAST.add_rules(f"BOOL <- NULL != NULL", "0")
NEAST.add_rules(f"BOOL <- {ANY} != NULL", "(case when {s1} is null then 0 else 1 end)")
NEAST.add_rules(f"BOOL <- NULL != {ANY}", "(case when {s2} is null then 0 else 1 end)")
NEAST.add_rules(f"BOOL <- {INTLIKE} != {INTLIKE}", "vsqlimpl_pkg.ne_int_int({s1}, {s2})")
NEAST.add_rules(f"BOOL <- {NUMBERLIKE} != {NUMBERLIKE}", "vsqlimpl_pkg.ne_{t1}_{t2}({s1}, {s2})")
NEAST.add_rules(f"BOOL <- GEO != GEO", "vsqlimpl_pkg.ne_str_str({s1}, {s2})")
NEAST.add_rules(f"BOOL <- COLOR != COLOR", "vsqlimpl_pkg.ne_int_int({s1}, {s2})")
NEAST.add_rules(f"BOOL <- {TEXT} != {TEXT}", "vsqlimpl_pkg.ne_{t1}_{t2}({s1}, {s2})")
NEAST.add_rules(f"BOOL <- DATE_DATETIME != T1", "vsqlimpl_pkg.ne_{t1}_{t2}({s1}, {s2})")
NEAST.add_rules(f"BOOL <- DATEDELTA_MONTHDELTA_COLOR != T1", "vsqlimpl_pkg.ne_int_int({s1}, {s2})")
NEAST.add_rules(f"BOOL <- DATETIMEDELTA != DATETIMEDELTA", "vsqlimpl_pkg.ne_datetimedelta_datetimedelta({s1}, {s2})")
NEAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST != INTLIST_NUMBERLIST", "vsqlimpl_pkg.ne_{t1}_{t2}({s1}, {s2})")
NEAST.add_rules(f"BOOL <- STRLIST_CLOBLIST != STRLIST_CLOBLIST", "vsqlimpl_pkg.ne_{t1}_{t2}({s1}, {s2})")
NEAST.add_rules(f"BOOL <- {SET} != T1", "vsqlimpl_pkg.ne_{t1}_{t2}({s1}, {s2})")
NEAST.add_rules(f"BOOL <- DATESET_DATETIMESET != DATESET_DATETIMESET", "vsqlimpl_pkg.ne_datetimeset_datetimeset({s1}, {s2})")
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

# Greater-than-or equal comparison (A >= B)
GEAST.add_rules(f"BOOL <- NULL >= NULL", "1")
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

# Less-than comparison (A < B)
LTAST.add_rules(f"BOOL <- NULL < NULL", "0")
LTAST.add_rules(f"BOOL <- {ANY} < NULL", "0")
LTAST.add_rules(f"BOOL <- NULL < {ANY}", "(case when {s2} is null then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- {INTLIKE} < {INTLIKE}", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- {NUMBERLIKE} < {NUMBERLIKE}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- {TEXT} < {TEXT}", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATE_DATETIME < T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATEDELTA < DATEDELTA", "(case when vsqlimpl_pkg.cmp_int_int({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATETIMEDELTA < DATETIMEDELTA", "(case when vsqlimpl_pkg.cmp_number_number({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- INTLIST_NUMBERLIST < INTLIST_NUMBERLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- STRLIST_CLOBLIST < STRLIST_CLOBLIST", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")
LTAST.add_rules(f"BOOL <- DATELIST_DATETIMELIST < T1", "(case when vsqlimpl_pkg.cmp_{t1}_{t2}({s1}, {s2}) < 0 then 1 else 0 end)")

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

# Logical and (A and B)
# Can't use the real operator ("and") in the spec, so use "?"
AndAST.add_rules(f"T1 <- {ANY} ? NULL", "null")
AndAST.add_rules(f"T2 <- NULL ? {ANY}", "null")
AndAST.add_rules(f"BOOL <- BOOL ? BOOL", "(case when {s1} = 1 then {s2} else 0 end)")
AndAST.add_rules(f"INT <- {INTLIKE} ? {INTLIKE}", "(case when nvl({s1}, 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? {NUMBERLIKE}", "(case when nvl({s1}, 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"NUMBER <- STR ? STR", "nvl2({s1}, {s2}, {s1})")
AndAST.add_rules(f"CLOB <- CLOB ? CLOB", "(case when {s1} is not null and length({s1}) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"T1 <- DATE_DATETIME ? T1", "nvl2({s1}, {s2}, {s1})")
AndAST.add_rules(f"T1 <- DATEDELTA_DATETIMEDELTA_MONTHDELTA ? T1", "(case when nvl({s1}, 0) != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"T1 <- {LIST} ? T1", "(case when {s1} is not null and {s1}.count != 0 then {s2} else {s1} end)")
AndAST.add_rules(f"DATETIMELIST <- DATELIST_DATETIMELIST ? DATELIST_DATETIMELIST", "(case when {s1} is not null and {s1}.count != 0 then {s2} else {s1} end)")

# Logical or (A or B)
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
OrAST.add_rules(f"T1 <- {LIST} ? T1", "(case when {s1} is not null and {s1}.count != 0 then {s1} else {s2} end)")
OrAST.add_rules(f"DATETIMELIST <- DATELIST_DATETIMELIST ? DATELIST_DATETIMELIST", "(case when {s1} is not null and {s1}.count != 0 then {s1} else {s2} end)")

# Containment test (A in B)
# Can't use the real operator ("in") in the spec, so use "?"
ContainsAST.add_rules(f"BOOL <- NULL ? {LIST}", "vsqlimpl_pkg.contains_null_{t2}({s2})")
ContainsAST.add_rules(f"BOOL <- STR ? STR_CLOB_STRLIST_CLOBLIST_STRSET", "vsqlimpl_pkg.contains_str_{t2}({s1}, {s2})")
ContainsAST.add_rules(f"BOOL <- INT_NUMBER ? INTLIST_NUMBERLIST_INTSET_NUMBERSET", "vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2})")
ContainsAST.add_rules(f"BOOL <- DATE ? DATELIST_DATESET", "vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2})")
ContainsAST.add_rules(f"BOOL <- DATETIME ? DATETIMELIST_DATETIMESET", "vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2})")

# Inverted containment test (A not in B)
# Can't use the real operator ("not in") in the spec, so use "?"
NotContainsAST.add_rules(f"BOOL <- NULL ? {LIST}", "(1 - vsqlimpl_pkg.contains_null_{t2}({s2}))")
NotContainsAST.add_rules(f"BOOL <- STR ? STR_CLOB_STRLIST_CLOBLIST_STRSET", "(1 - vsqlimpl_pkg.contains_str_{t2}({s1}, {s2}))")
NotContainsAST.add_rules(f"BOOL <- INT_NUMBER ? INTLIST_NUMBERLIST_INTSET_NUMBERSET", "(1 - vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2}))")
NotContainsAST.add_rules(f"BOOL <- DATE ? DATELIST_DATESET", "(1 - vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2}))")
NotContainsAST.add_rules(f"BOOL <- DATETIME ? DATETIMELIST_DATETIMESET", "(1 - vsqlimpl_pkg.contains_{t1}_{t2}({s1}, {s2}))")

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

# Item operator (A[B])
ItemAST.add_rules(f"STR <- STR_CLOB_STRLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"CLOB <- CLOBLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"INT <- INTLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"NUMBER <- NUMBERLIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"DATE <- DATELIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")
ItemAST.add_rules(f"DATETIME <- DATETIMELIST[{INTLIKE}]", "vsqlimpl_pkg.item_{t1}({s1}, {s2})")

# Slice operator (A[B:C])
SliceAST.add_rules(f"T1 <- {SEQ}[NULL_{INTLIKE}:NULL_{INTLIKE}]", "vsqlimpl_pkg.slice_{t1}({s1}, {s2}, {s3})")

# Arithmetic negation (-A)
NegAST.add_rules(f"INT <- BOOL", "(-{s1})")
NegAST.add_rules(f"T1 <- INT_NUMBER_DATEDELTA_DATETIMEDELTA_MONTHDELTA", "(-{s1})")

# Logical negation (not A)
# Can't use the real operator ("not") in the spec, so use "?"
NotAST.add_rules(f"BOOL <- ? NULL", "1")
NotAST.add_rules(f"BOOL <- ? BOOL", "(case {s1} when 1 then 0 else 1 end)")
NotAST.add_rules(f"BOOL <- ? INT_NUMBER_DATEDELTA_DATETIMEDELTA_MONTHDELTA", "(case {s1} when 0 then 1 when null then 1 else 0 end)")
NotAST.add_rules(f"BOOL <- ? DATE_DATETIME_STR_COLOR_GEO", "(case {s1} when null then 1 else 0 end)")
NotAST.add_rules(f"BOOL <- ? {ANY}", "(1 - vsqlimpl_pkg.bool_{t1}({s1}))")

# Ternary if (A if COND else B)
# Can't use the real operator ("if"/"else") in the spec, so use "?"
IfAST.add_rules(f"T1 <- {ANY} ? NULL ? T1", "{s3}")
IfAST.add_rules(f"INT <- {INTLIKE} ? NULL ? {INTLIKE}", "{s3}")
IfAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? NULL ? {NUMBERLIKE}", "{s3}")
IfAST.add_rules(f"T1 <- {ANY} ? NULL ? NULL", "{s3}")
IfAST.add_rules(f"T3 <- NULL ? NULL ? {ANY}", "{s3}")
IfAST.add_rules(f"T1 <- {ANY} ? BOOL_NUMBER ? T1", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"INT <- {INTLIKE} ? BOOL_NUMBER ? {INTLIKE}", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"NUMBER <- {NUMBERLIKE} ? BOOL_NUMBER ? {NUMBERLIKE}", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"T1 <- {ANY} ? BOOL_NUMBER ? NULL", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
IfAST.add_rules(f"T3 <- NULL ? BOOL_NUMBER ? {ANY}", "(case when nvl({s2}, 0) != 0 then {s1} else {s3} end)")
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

# Bitwise and (A & B)
BitAndAST.add_rules(f"INT <- {INTLIKE} & {INTLIKE}", "bitand({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- INTSET & INTSET", "vsqlimpl_pkg.bitand_intset({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- NUMBERSET & NUMBERSET", "vsqlimpl_pkg.bitand_numberset({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- STRSET & STRSET", "vsqlimpl_pkg.bitand_strset({s1}, {s2})")
BitAndAST.add_rules(f"T1 <- DATESET_DATETIMESET & T1", "vsqlimpl_pkg.bitand_datetimeset({s1}, {s2})")

# Bitwise or (A | B)
BitOrAST.add_rules(f"INT <- {INTLIKE} | {INTLIKE}", "vsqlimpl_pkg.bitor_int({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- INTSET | INTSET", "vsqlimpl_pkg.bitor_intset({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- NUMBERSET | NUMBERSET", "vsqlimpl_pkg.bitor_numberset({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- STRSET | STRSET", "vsqlimpl_pkg.bitor_strset({s1}, {s2})")
BitOrAST.add_rules(f"T1 <- DATESET_DATETIMESET | T1", "vsqlimpl_pkg.bitor_datetimeset({s1}, {s2})")

# Bitwise exclusive or (A ^ B)
BitXOrAST.add_rules(f"INT <- {INTLIKE} ^ {INTLIKE}", "vsqlimpl_pkg.bitxor_int({s1}, {s2})")

# Bitwise not (~A)
BitNotAST.add_rules(f"INT <- {INTLIKE}", "(-{s1} - 1)")


###
### Class for regenerating the Java type information.
###

class JavaSource:
	"""
	A :class:`JavaSource` object combines the source code of a Java class that
	implements a vSQL AST type with the Python class that implements that AST
	type.
	"""
	def __init__(self, astcls, path):
		self.astcls = astcls
		self.path = path
		self.lines = path.read_text(encoding="utf-8").splitlines(False)

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} cls={self.cls!r} path={str(self.path)!r} at {id(self):#x}>"

	def new_lines(self):
		"""
		Return an iterator over the new Java source code lines that should
		replace the static initialization block inside the Java source file.
		"""
		yield "\tstatic"
		yield "\t{"

		for rule in self.astcls.rules.values():
			yield f"\t\t{rule.java_source()}"

		yield "\t}"

	def save(self):
		"""
		Resave the Java source code incorporating the new vSQL type info from the
		Python AST class.
		"""
		inrules = False

		start_line = "static"
		end_line = "}"

		with self.path.open("w", encoding="utf-8") as f:
			for line in self.lines:
				if inrules:
					if line.strip() == end_line:
						inrules = False
				else:
					if line.strip() == start_line:
						inrules = True
						for new_line in self.new_lines():
							f.write(f"{new_line}\n")
					else:
						f.write(f"{line}\n")

	@classmethod
	def all_java_source_files(cls, path: pathlib.Path):
		"""
		Return an iterator over all :class:`!JavaSource` objects that can be found
		in the directory ``path`` that should point to the directory containing
		the Java vSQL AST classes.
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
	def rewrite_all_java_source_files(cls, path:pathlib.Path, verbose:bool=False):
		"""
		Rewrite all Java source code files implementing Java vSQL AST classes
		in the directory ``path`` that should point to the directory containing
		the Java vSQL AST classes..
		"""
		if verbose:
			print(f"Rewriting Java source files in {str(path)!r}")
		for javasource in cls.all_java_source_files(path):
			javasource.save()


###
### Functions for regenerating the Oracle type information.
###

def oracle_sql_table():
	recordfields = [rule.oracle_fields() for rule in AST.all_rules()]

	sql = []
	sql.append("create table vsqlrule")
	sql.append("(")
	for (i, (fieldname, fieldtype)) in enumerate(fields.items()):
		term = "" if i == len(fields)-1 else ","
		if fieldname == "vr_cname":
			sql.append(f"\t{fieldname} varchar2({len(scriptname)}) not null{term}")
		elif fieldtype is int:
			sql.append(f"\t{fieldname} integer not null{term}")
		elif fieldtype is optint:
			sql.append(f"\t{fieldname} integer{term}")
		elif fieldtype is datetime.datetime:
			sql.append(f"\t{fieldname} date not null{term}")
		elif fieldtype is str:
			size = max(len(r[fieldname]) for r in recordfields if fieldname in r and r[fieldname])
			sql.append(f"\t{fieldname} varchar2({size}) not null{term}")
		elif fieldtype is optstr:
			size = max(len(r[fieldname]) for r in recordfields if fieldname in r and r[fieldname])
			sql.append(f"\t{fieldname} varchar2({size}){term}")
		else:
			raise ValueError(f"unknown field type {fieldtype!r}")
	sql.append(")")
	return "\n".join(sql)


def oracle_sql_procedure():
	sql = []
	sql.append("create or replace procedure vsqlgrammar_make(c_user varchar2)")
	sql.append("as")
	sql.append("begin")
	sql.append("\tdelete from vsqlrule;")
	for rule in AST.all_rules():
		sql.append(f"\t{rule.oracle_source()}")
	sql.append("end;")
	return "\n".join(sql)


def oracle_sql_index():
	return "create unique index vsqlrule_i1 on vsqlrule(vr_nodetype, vr_value, vr_signature, vr_arity)"


def oracle_sql_tablecomment(self):
	return "comment on table vsqlrule is 'Syntax rules for vSQL expressions.'"


def recreate_oracle(connectstring: str, verbose:bool=False):
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
			print(f"Dropping old table VSQLRULE in {db.connectstring()!r}")
		cursor.execute("drop table vsqlrule")
	if oldsql != newsql:
		if verbose:
			print(f"Creating new table VSQLRULE in {db.connectstring()!r}")
		cursor.execute(newsql)
		if verbose:
			print(f"Creating index VSQLRULE_I1 in {db.connectstring()!r}")
		cursor.execute(oracle_sql_index())
		if verbose:
			print(f"Creating table comment for VSQLRULE in {db.connectstring()!r}")
		cursor.execute(oracle_sql_tablecomment())
	if verbose:
		print(f"Creating procedure VSQLGRAMMAR_MAKE in {db.connectstring()!r}")
	cursor.execute(oracle_sql_procedure())
	if verbose:
		print(f"Calling procedure VSQLGRAMMAR_MAKE in {db.connectstring()!r}")
	cursor.execute(f"begin vsqlgrammar_make('{scriptname}'); end;")


def main(args=None):
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
