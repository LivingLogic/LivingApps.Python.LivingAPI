#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2020 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
Classes and functions for compiling vSQL expressions.
"""

import datetime, itertools

from ll import color, misc, ul4c, ul4on

try:
	from ll import orasql
except ImportError:
	orasql = None


###
### Helper functions and classes
###

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
		return self.fields[key]

	def ul4ondump(self, encoder):
		encoder.dump(self.tablesql)
		encoder.dump(self.fields)

	def ul4onload(self, decoder):
		self.tablesql = decoder.load()
		self.fields = decoder.load()


class AST(Repr):
	dbnodetype = None
	dbnodevalue = None
	dbdatatype = None

	def __init__(self, source=None, pos=None):
		self._source = source
		self.pos = pos

	@property
	def source(self):
		return self._source[self.pos]

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
				p_vss_source=self.source,
			)
			vss_id = r.p_vss_id
		r = handler.proc_vsql_insert(
			cursor,
			c_user=handler.ide_id,
			p_vs_id_super=vs_id_super,
			p_vs_order=vs_order,
			p_vs_nodetype=self.dbnodetype,
			p_vs_value=self.dbnodevalue,
			p_vs_datatype=self.dbdatatype,
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
		return f"{self.__class__.__name__}: {self.source[self.pos]}"

	def _ll_repr_suffix_(self):
		parts = []
		parts.append("pos=[")
		if self.pos.start is not None:
			parts.append(f"{self.pos.start:,}")
		parts.append(":")
		if self.pos.stop is not None:
			parts.append(f"{self.pos.stop:,}")
		parts.append("] ")
		parts.append(super()._ll_repr_suffix_())
		return "".join(parts)

	@classmethod
	def fromul4(cls, source, node, vars):
		if isinstance(node, ul4c.Const):
			if node.value is None:
				return None_.fromul4(source, node, vars)
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

	def ul4ondump(self, encoder):
		encoder.dump(self._source)
		encoder.dump(self.pos)

	def ul4onload(self, decoder):
		self._source = decoder.load()
		self.pos = decoder.load()


class Const(AST):
	pass


@ul4on.register("de.livinglogic.vsql.none")
class None_(Const):
	dbnodetype = "const_none"
	dbdatatype = "null"

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos))


class _ConstWithValue(Const):
	def __init__(self, source=None, pos=None, value=None):
		super().__init__(source, pos)
		self.value = value

	@property
	def dbnodevalue(self):
		return self.value

	def _ll_repr_(self):
		yield f"value={self.value!r}"

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos), node.value)

	def _ll_repr_pretty_(self, p):
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
class Bool(_ConstWithValue):
	dbnodetype = "const_bool"
	dbdatatype = "bool"

	@property
	def dbnodevalue(self):
		return "True" if self.value else "False"


@ul4on.register("de.livinglogic.vsql.int")
class Int(_ConstWithValue):
	dbnodetype = "const_int"
	dbdatatype = "int"

	@property
	def dbnodevalue(self):
		return str(self.value)


@ul4on.register("de.livinglogic.vsql.number")
class Number(_ConstWithValue):
	dbnodetype = "const_number"
	dbdatatype = "number"

	@property
	def dbnodevalue(self):
		return repr(self.value)


@ul4on.register("de.livinglogic.vsql.str")
class Str(_ConstWithValue):
	dbnodetype = "const_str"
	dbdatatype = "str"


@ul4on.register("de.livinglogic.vsql.color")
class Color(_ConstWithValue):
	dbnodetype = "const_color"
	dbdatatype = "color"

	@property
	def dbnodevalue(self):
		c = self.value
		return f"{c.r():02x}{c.g():02x}{c.b():02x}{c.a():02x}"


@ul4on.register("de.livinglogic.vsql.date")
class Date(_ConstWithValue):
	dbnodetype = "const_date"
	dbdatatype = "date"

	@property
	def dbnodevalue(self):
		return f"{self.value:%Y-%m-%d}"


@ul4on.register("de.livinglogic.vsql.datetime")
class DateTime(_ConstWithValue):
	dbnodetype = "const_datetime"
	dbdatatype = "datetime"

	@property
	def dbnodevalue(self):
		return f"{self.value:%Y-%m-%dT%H:%M:%S}"


@ul4on.register("de.livinglogic.vsql.list")
class List(AST):
	dbnodetype = "list"

	def __init__(self, source=None, pos=None):
		super().__init__(source, pos)
		self.items = []

	def _ll_repr_(self):
		yield f"with {len(self.items):,} items"

	def _ll_repr_pretty_(self, p):
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

	def dbchildren(self):
		yield from self.items

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.items)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.items = decoder.load()


@ul4on.register("de.livinglogic.vsql.set")
class Set(AST):
	dbnodetype = "set"

	def __init__(self, source=None, pos=None):
		super().__init__(source, pos)
		self.items = []

	def _ll_repr_(self):
		yield f"with {len(self.items):,} items"

	def _ll_repr_pretty_(self, p):
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

	def dbchildren(self):
		yield from self.items

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.items)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.items = decoder.load()


@ul4on.register("de.livinglogic.vsql.fieldref")
class FieldRef(AST):
	dbnodetype = "field"

	def __init__(self, source=None, pos=None, parent=None, identifier=None, field=None):
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
		super().__init__(source, pos)
		self.parent = parent
		# Note that ``identifier`` might be different from ``field.identifier``
		# if ``field.identifier == "*"``.
		self.identifier = identifier
		# Note that ``field`` might be ``None`` when the field can't be found.
		self.field = field

	@property
	def dbdatatype(self):
		return self.field.datatype

	@property
	def dbnodevalue(self):
		identifierpath = []
		node = self
		while node is not None:
			identifierpath.insert(0, node.identifier)
			node = node.parent
		return ".".join(identifierpath)

	def _ll_repr_(self):
		if self.parent is not None:
			yield f"parent={self.parent!r}"
		if self.field is None or self.field.identifier != self.identifier:
			yield f"identifier={self.identifier!r}"
		if self.field is not None:
			yield f"field={self.field!r}"

	def _ll_repr_pretty_(self, p):
		p.text(" ")
		p.pretty(self.name)
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


class Binary(AST):
	def __init__(self, source=None, pos=None, obj1=None, obj2=None):
		super().__init__(source, pos)
		self.obj1 = obj1
		self.obj2 = obj2

	def dbchildren(self):
		yield self.obj1
		yield self.obj2

	def _ll_repr_(self):
		yield f"obj1={self.obj1!r}"
		yield f"obj2={self.obj2!r}"

	def _ll_repr_pretty_(self, p):
		p.breakable()
		p.text("obj1=")
		p.pretty(self.obj1)
		p.breakable()
		p.text("obj2=")
		p.pretty(self.obj2)

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos), AST.fromul4(source, node.obj1, vars), AST.fromul4(source, node.obj2, vars))

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj1)
		encoder.dump(self.obj2)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj1 = decoder.load()
		self.obj2 = decoder.load()


@ul4on.register("de.livinglogic.vsql.eq")
class EQ(Binary):
	dbnodetype = "cmp_eq"


@ul4on.register("de.livinglogic.vsql.ne")
class NE(Binary):
	dbnodetype = "cmp_ne"


@ul4on.register("de.livinglogic.vsql.lt")
class LT(Binary):
	dbnodetype = "cmp_lt"


@ul4on.register("de.livinglogic.vsql.le")
class LE(Binary):
	dbnodetype = "cmp_le"


@ul4on.register("de.livinglogic.vsql.gt")
class GT(Binary):
	dbnodetype = "cmp_gt"


@ul4on.register("de.livinglogic.vsql.ge")
class GE(Binary):
	dbnodetype = "cmp_ge"


@ul4on.register("de.livinglogic.vsql.add")
class Add(Binary):
	dbnodetype = "binop_add"


@ul4on.register("de.livinglogic.vsql.sub")
class Sub(Binary):
	dbnodetype = "binop_sub"


@ul4on.register("de.livinglogic.vsql.mul")
class Mul(Binary):
	dbnodetype = "binop_mul"


@ul4on.register("de.livinglogic.vsql.floordiv")
class FloorDiv(Binary):
	dbnodetype = "binop_floordiv"


@ul4on.register("de.livinglogic.vsql.truediv")
class TrueDiv(Binary):
	dbnodetype = "binop_truediv"


@ul4on.register("de.livinglogic.vsql.mod")
class Mod(Binary):
	dbnodetype = "binop_mod"


@ul4on.register("de.livinglogic.vsql.and")
class And(Binary):
	dbnodetype = "binop_and"


@ul4on.register("de.livinglogic.vsql.or")
class Or(Binary):
	dbnodetype = "binop_or"


@ul4on.register("de.livinglogic.vsql.contains")
class Contains(Binary):
	dbnodetype = "binop_contains"


@ul4on.register("de.livinglogic.vsql.notcontains")
class NotContains(Binary):
	dbnodetype = "binop_notcontains"


@ul4on.register("de.livinglogic.vsql.is")
class Is(Binary):
	dbnodetype = "binop_is"


@ul4on.register("de.livinglogic.vsql.isnot")
class IsNot(Binary):
	dbnodetype = "binop_isnot"


@ul4on.register("de.livinglogic.vsql.item")
class Item(Binary):
	dbnodetype = "binop_item"

	@classmethod
	def fromul4(cls, source, node, vars):
		if isinstance(node.obj2, ul4c.Slice):
			return Slice.fromul4(source, node, vars)
		return super().fromul4(source, node, vars)


@ul4on.register("de.livinglogic.vsql.shiftleft")
class ShiftLeft(Binary):
	dbnodetype = "binop_shiftleft"


@ul4on.register("de.livinglogic.vsql.shiftright")
class ShiftRight(Binary):
	dbnodetype = "binop_shiftright"


@ul4on.register("de.livinglogic.vsql.bitand")
class BitAnd(Binary):
	dbnodetype = "binop_bitand"


@ul4on.register("de.livinglogic.vsql.bitor")
class BitOr(Binary):
	dbnodetype = "binop_bitor"


@ul4on.register("de.livinglogic.vsql.bitxor")
class BitXOr(Binary):
	dbnodetype = "binop_bitxor"


class Unary(AST):
	def __init__(self, source=None, pos=None, obj=None):
		super().__init__(source, pos)
		self.obj = obj

	def dbchildren(self):
		yield self.obj

	def _ll_repr_(self):
		yield f"obj={self.obj!r}"

	def _ll_repr_pretty_(self, p):
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(source, _offset(node.pos), AST.fromul4(source, node.obj, vars))

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj = decoder.load()


@ul4on.register("de.livinglogic.vsql.not")
class Not(Unary):
	dbnodetype = "unop_not"


@ul4on.register("de.livinglogic.vsql.neg")
class Neg(Unary):
	dbnodetype = "unop_neg"


@ul4on.register("de.livinglogic.vsql.bitnot")
class BitNot(Unary):
	dbnodetype = "unop_bitnot"


@ul4on.register("de.livinglogic.vsql.if")
class If(AST):
	dbnodetype = "ternop_if"

	def __init__(self, source=None, pos=None, objif=None, objcond=None, objelse=None):
		super().__init__(source, pos)
		self.objif = objif
		self.objcond = objcond
		self.objelse = objelse

	def dbchildren(self):
		yield self.objif
		yield self.objcond
		yield self.objelse

	def _ll_repr_(self):
		yield f"objif={self.objif!r}"
		yield f"objcond={self.objcond!r}"
		yield f"objelse={self.objelse!r}"

	def _ll_repr_pretty_(self, p):
		p.breakable()
		p.text("objif=")
		p.pretty(self.objif)
		p.text("objcond=")
		p.pretty(self.objcond)
		p.text("objelse=")
		p.pretty(self.objelse)

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(
			source,
			_offset(node.pos),
			AST.fromul4(source, node.objif, vars),
			AST.fromul4(source, node.objcond, vars),
			AST.fromul4(source, node.objelse, vars),
		)

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
class Slice(AST):
	dbnodetype = "ternop_slice"

	def __init__(self, source=None, pos=None, obj=None, index1=None, index2=None):
		super().__init__(source, pos)
		self.obj = obj
		self.index1 = index1
		self.index2 = index2

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
		yield f"obj={self.obj!r}"
		if self.index1 is not None:
			yield f"index1={self.index1!r}"
		if self.index2 is not None:
			yield f"index2={self.index2!r}"

	def _ll_repr_pretty_(self, p):
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

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(
			source,
			_offset(node.pos),
			AST.fromul4(source, node.obj1, vars),
			AST.fromul4(source, node.obj2.index1, vars) if node.obj2.index1 is not None else None,
			AST.fromul4(source, node.obj2.index2, vars) if node.obj2.index2 is not None else None,
		)

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
class Attr(AST):
	dbnodetype = "attr"

	def __init__(self, source=None, pos=None, obj=None, attrname=None):
		super().__init__(source, pos)
		self.obj = obj
		self.attrname = attrname

	@property
	def dbnodevalue(self):
		return self.attrname

	def dbchildren(self):
		yield self.obj

	def _ll_repr_(self):
		yield f"obj={self.obj!r}"
		yield f"attrname={self.attrname!r}"

	def _ll_repr_pretty_(self, p):
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)
		p.breakable()
		p.text("attrname=")
		p.pretty(self.attrname)

	@classmethod
	def fromul4(cls, source, node, vars):
		return cls(
			source,
			_offset(node.pos),
			AST.fromul4(source, node.obj1, vars),
			node.attrname,
		)

	def ul4ondump(self, encoder):
		super().ul4ondump(encoder)
		encoder.dump(self.obj)
		encoder.dump(self.attrname)

	def ul4onload(self, decoder):
		super().ul4onload(decoder)
		self.obj = decoder.load()
		self.attrname = decoder.load()


@ul4on.register("de.livinglogic.vsql.func")
class Func(AST):
	dbnodetype = "func"

	def __init__(self, source=None, pos=None, name=None, args=None):
		super().__init__(source, pos)
		self.name = name
		self.args = args

	@property
	def dbnodevalue(self):
		return self.name

	def dbchildren(self):
		yield from self.args

	def _ll_repr_(self):
		yield f"{self.name!r}"
		yield f"with {len(self.args):,} arguments"

	def _ll_repr_pretty_(self, p):
		p.text(" ")
		p.pretty(self.name)
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
class Meth(AST):
	dbnodetype = "meth"

	def __init__(self, source=None, pos=None, obj=None, name=None, args=None):
		super().__init__(source, pos)
		self.obj = obj
		self.name = name
		self.args = args or []

	@property
	def dbnodevalue(self):
		return self.name

	def dbchildren(self):
		yield self.obj
		yield from self.args

	def _ll_repr_(self):
		yield f"{self.name!r}"
		yield f"obj={self.obj!r}"
		yield f" with {len(self.args):,} arguments"

	def _ll_repr_pretty_(self, p):
		p.text(" ")
		p.pretty(self.name)
		p.breakable()
		p.text("obj=")
		p.pretty(self.obj)
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
	bool: Bool,
	int: Int,
	float: Number,
	str: Str,
	color.Color: Color,
	datetime.date: Date,
	datetime.datetime: DateTime,
}

# Set of UL4 AST nodes that directly map to their equivalent vSQL version
_ops = {ul4c.If, ul4c.Not, ul4c.Neg, ul4c.BitNot, ul4c.List, ul4c.Set}
_ops.update(ul4c.Binary.__subclasses__())

# Create the mapping that maps the UL4 AST type to the vSQL AST type
v = vars()
_ul42vsql = {cls: v[cls.__name__] for cls in _ops}

# Remove temporary variables
del _ops, v
