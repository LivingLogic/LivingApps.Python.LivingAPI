#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2021 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

"""
:mod:`handlers` provides various handler classes for talking to LivingApps.

:class:`Handler` is the base class of all handler classes. Subclasses are:

:class:`DBHandler`
	This provides direct communication to LivingApps via a database interface.

	This means that you need to have your own custom installation of LivingApps
	and you need to have direct access to the Oracle database.

:class:`HTTPHandler`
	This commuicates with LivingApps via an HTTP interface.

	You need the URL of the LivingApps system, and account name and a password
	to use an :class:`HTTPHandler`.

:class:`FileHandler`
	This is used to store LivingApps meta data in the local file system.

	This makes it possible to import and export internal and view templates
	and their configuration into and out of LivingApps.
"""

import os, datetime, pathlib, itertools, json, mimetypes, operator, warnings, random

import requests, requests.exceptions # This requires :mod:`request`, which you can install with ``pip install requests``

from ll import url, ul4c, ul4on # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``

try:
	from ll import orasql
except ImportError:
	orasql = None

try:
	import psycopg
except ImportError:
	psycopg = None

try:
	from psycopg import rows
except ImportError:
	rows = None

from ll import la

from ll.la import vsql


__docformat__ = "reStructuredText"

__all__ = ["Handler", "HTTPHandler", "DBHandler", "FileHandler"]


###
### Utility functions and classes
###

def uuid():
	now = datetime.datetime.now()
	return f"{int(now.timestamp()):08x}{now.microsecond & 0xffff:04x}{random.randint(0, (1<<(12*4))-1):012x}"


def raise_403(response):
	"""
	Raise an HTTP exception with the status code 403 (i.e. "Forbidden").

	(This is used if the HTTP interface would redirect us to a different page,
	which we don't want).
	"""
	http_error_msg = f"403 Client Error: Forbidden for url: {response.url}"
	raise requests.exceptions.HTTPError(http_error_msg, response=response)


###
### Handler classes
###

class Handler:
	"""
	A :class:`Handler` object handles communication with a LivingApps system.
	"""

	def __init__(self):
		self.globals = None
		registry = {
			"de.livinglogic.livingapi.file": self._loadfile,
			"de.livinglogic.livingapi.globals": self._loadglobals,
		}
		self.ul4on_decoder = ul4on.Decoder(registry)

	def reset(self):
		"""
		Reset the handler to the initial state.

		This reset the UL4ON decoder.
		"""
		self.ul4on_decoder.reset()

	def commit(self):
		pass

	def rollback(self):
		pass

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.reset()
		if exc_type is not None:
			self.rollback()
		else:
			self.commit()

	def get(self, *path, **params):
		warnings.warn("The method get() is deprecated, please use viewtemplate_data() instead.")
		return self.viewtemplate_data(*path, **params)

	def viewtemplate_data(self, *path, **params):
		raise NotImplementedError

	def viewtemplate_params_incremental_data(self, globals, id):
		return None

	def emailtemplate_params_incremental_data(self, globals, id):
		return None

	def app_params_incremental_data(self, app):
		return None

	def record_attachments_data(self, id):
		return None

	def meta_data(self, *appids):
		raise NotImplementedError

	def file(self, source):
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
			if source.name:
				filename = os.path.basename(source.name)
			else:
				filename = "Unnnamed"
		if mimetype is None:
			mimetype = mimetypes.guess_type(filename, strict=False)[0]
			if mimetype is None:
				mimetype = "application/octet-stream"
		file = la.File(filename=filename, mimetype=mimetype, content=content)
		file.handler = self
		return file

	def _geofrominfo(self, info:str) -> la.Geo:
		import geocoder # This requires the :mod:`geocoder` module, install with ``pip install geocoder``
		provider = geocoder.osm
		result = provider(info, language="de")
		if not result.error and result.lat and result.lng and result.address:
			return la.Geo(result.lat, result.lng, result.address)
		return None

	def _geofromlatlong(self, lat:float, long:float) -> la.Geo:
		import geocoder # This requires the :mod:`geocoder` module, install with ``pip install geocoder``
		provider = geocoder.osm
		result = provider([lat, long], method="reverse", language="de")
		if not result.error and result.lat and result.lng and result.address:
			return la.Geo(result.lat, result.lng, result.address)
		return None

	def _geofromstring(self, s:str) -> la.Geo:
		parts = s.split(",", 2)
		if len(parts) < 2:
			return self._geofrominfo(s)
		else:
			try:
				lat = float(parts[0])
				long = float(parts[1])
			except ValueError:
				return self._geofrominfo(s)
			else:
				if len(parts) == 2:
					return self._geofromlatlong(lat, long)
				else:
					return la.Geo(lat, long, parts[2].strip())

	def geo(self, lat=None, long=None, info=None):
		"""
		Create a :class:`~ll.la.Geo` object from :obj:`lat`/:obj`long` or :obj:`info`.

		Example::

			>>> from ll import la
			>>> h = la.FileHandler()
			>>> h.geo('Bayreuth, Germany')
			<ll.la.Geo lat=49.9427202 long=11.5763079 info='Bayreuth, Oberfranken, Bayern, 95444, Deutschland' at 0x1096e0d68>
			>>> h.geo(49.95, 11.57)
			<ll.la.Geo lat=49.9501244 long=11.5704134713533 info='Verwaltung Verkehrsbetrieb, 4, Eduard-Bayerlein-Straße, Gewerbegebiet Neue Spinnerei, Nördliche Innenstadt, Innenstadt, Bayreuth, Oberfranken, Bayern, 95445, Deutschland' at 0x1098706d8>
		"""
		# Get coordinates from description (passed via keyword :obj:`info`)
		if info is not None and lat is None and long is None:
			return self._geofrominfo(info)
		# Get coordinates from description (passed positionally as :obj:`lat`)
		elif lat is not None and long is None and info is None:
			return self._geofrominfo(lat)
		# Get description from coordinates
		elif lat is not None and long is not None and info is None:
			return self._geofromlatlong(lat, long)
		else:
			raise TypeError("geo() requires either (lat, long) arguments or a (info) argument")

	def seq(self):
		raise NotImplementedError

	def save_record(self, record):
		raise NotImplementedError

	def delete_record(self, record):
		raise NotImplementedError

	def _executeaction(self, record, actionidentifier):
		raise NotImplementedError

	def file_content(self, file):
		raise NotImplementedError

	def save_app(self, app, recursive=True):
		raise NotImplementedError

	def save_file(self, file):
		raise NotImplementedError

	def save_param(self, param, recursive=True):
		raise NotImplementedError

	def save_internaltemplate(self, internaltemplate, recursive=True):
		raise NotImplementedError

	def save_viewtemplate(self, viewtemplate, recursive=True):
		raise NotImplementedError

	def delete_viewtemplate(self, viewtemplate):
		raise NotImplementedError

	def delete_internaltemplate(self, internaltemplate):
		raise NotImplementedError

	def save_datasourceconfig(self, datasource, recursive=True):
		raise NotImplementedError

	def save_datasourcechildren(self, datasourcechildren, recursive=True):
		raise NotImplementedError

	def fetch_templates(self, app):
		return la.attrdict()

	def fetch_templatelibraries(self):
		return la.attrdict()

	def fetch_viewtemplate_params(self, globals):
		return la.attrdict()

	def fetch_emailtemplate_params(self, globals):
		return la.attrdict()

	def _loadfile(self, id):
		file = la.File(id=id)
		file.handler = self
		return file

	def _loadglobals(self, id=None):
		globals = la.Globals()
		globals.handler = self
		return globals

	def _loaddump(self, dump):
		dump = self.ul4on_decoder.loads(dump)
		if isinstance(dump, dict):
			dump = la.attrdict(dump)
			if "datasources" in dump:
				dump.datasources = la.attrdict(dump.datasources)
		return dump


class DBHandler(Handler):
	def __init__(self, *, connection=None, connectstring=None, connection_postgres=None, connectstring_postgres=None, uploaddir=None, ide_account=None, ide_id=None):
		"""
		Create a new :class:`DBHandler`.

		For the database connection pass either ``connection`` with an
		:mod:`~ll.orasql` connection or ``connectstring`` with a connecstring.

		For a connection to the Postgres database pass either
		``connection_postgres`` with a :mod:`psycopg` connection or
		``connectstring_postgres`` with a connecstring. If you pass neither,
		functionality that requires the Postgres database (like template libraries)
		will not be available and will fail if used.

		``uploaddir`` must be an ``ssh`` URL specifying the upload directory
		on the web server. If no uploads will be made, it can also be :const:`None`.

		To use a user account either specify ``ide_account`` which must be the
		account name (i.e. the email address) of the user or ``ide_id`` which
		must be the users database id. If neither is given only public view
		templates can be fetched.
		"""

		super().__init__()

		now = datetime.datetime.now()
		self.requestid = uuid()
		if connection is not None:
			if connectstring is not None:
				raise ValueError("Specify connectstring or connection, but not both")
			self._db = connection
		elif connectstring is not None:
			self._db = connectstring

		if connection_postgres is not None:
			if connectstring_postgres is not None:
				raise ValueError("Specify connectstring_postgres or connection_postgres, but not both")
			self._db_pg = connection_postgres
		elif connectstring_postgres is not None:
			self._db_pg = connectstring_postgres

		if uploaddir is not None:
			uploaddir = url.URL(uploaddir)
		self.uploaddir = uploaddir

		self._varchars = None
		self.urlcontext = None

		# Procedures
		self.proc_data_insert = orasql.Procedure("LIVINGAPI_PKG.DATA_INSERT")
		self.proc_data_update = orasql.Procedure("LIVINGAPI_PKG.DATA_UPDATE")
		self.proc_data_delete = orasql.Procedure("LIVINGAPI_PKG.DATA_DELETE")
		self.proc_appparameter_save = orasql.Procedure("APPPARAMETER_PKG.APPPARAMETER_SAVE_LA")
		self.proc_dataaction_execute = orasql.Procedure("LIVINGAPI_PKG.DATAACTION_EXECUTE")
		self.proc_upload_insert = orasql.Procedure("UPLOAD_PKG.UPLOAD_INSERT")
		self.proc_appparameter_import_waf = orasql.Procedure("APPPARAMETER_PKG.APPPARAMETER_IMPORT")
		self.proc_internaltemplate_import = orasql.Procedure("INTERNALTEMPLATE_PKG.INTERNALTEMPLATE_IMPORT")
		self.proc_internaltemplate_delete = orasql.Procedure("INTERNALTEMPLATE_PKG.INTERNALTEMPLATE_DELETE")
		self.proc_viewtemplate_import = orasql.Procedure("VIEWTEMPLATE_PKG.VIEWTEMPLATE_IMPORT")
		self.proc_viewtemplate_delete = orasql.Procedure("VIEWTEMPLATE_PKG.VIEWTEMPLATE_DELETE")
		self.proc_datasource_import = orasql.Procedure("DATASOURCE_PKG.DATASOURCE_IMPORT")
		self.proc_datasourcechildren_import = orasql.Procedure("DATASOURCE_PKG.DATASOURCECHILDREN_IMPORT")
		self.proc_dataorder_import = orasql.Procedure("DATASOURCE_PKG.DATAORDER_IMPORT")
		self.proc_dataorder_delete = orasql.Procedure("DATASOURCE_PKG.DATAORDER_DELETE")
		self.proc_vsqlsource_insert = orasql.Procedure("VSQL_PKG.VSQLSOURCE_INSERT")
		self.proc_vsql_insert = orasql.Procedure("VSQL_PKG.VSQL_INSERT")
		self.proc_init = orasql.Procedure("LIVINGAPI_PKG.INIT")
		self.proc_clear_all = orasql.Procedure("LIVINGAPI_PKG.CLEAR_ALL")
		self.func_seq = orasql.Function("LIVINGAPI_PKG.SEQ")

		self.custom_procs = {} # For the insert/update/delete procedures of system templates
		self.internaltemplates = {} # Maps ``tpl_uuid`` to template dictionary
		self.viewtemplate_params = {} # Maps ``vt_id`` to parameter dictionary
		self.emailtemplate_params = {} # Maps ``et_id`` to parameter dictionary
		self.templatelibraries = None # Maps ``tl_id`` to template library

		if ide_id is not None:
			if ide_account is not None:
				raise ValueError("Specify ide_id or ide_account, but not both")
			self.ide_id = ide_id
		elif ide_account is not None:
			c = self.cursor()
			c.execute("select ide_id from identity where ide_account = :ide_account", ide_account=ide_account)
			r = c.fetchone()
			if r is None:
				raise ValueError(f"no user {ide_account!r}")
			self.ide_id = r.ide_id
		else:
			self.ide_id = None

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} connectstring={self.db.connectstring()!r} ide_id={self.ide_id!r} at {id(self):#x}>"

	@property
	def db(self):
		if self._db is None:
			raise ValueError("Not Oracle database connection available")
		elif isinstance(self._db, str):
			if orasql is None:
				raise ImportError("ll.orasql required")
			self._db = orasql.connect(self._db, readlobs=True)
		return self._db

	@property
	def db_pg(self):
		if self._db_pg is None:
			raise ValueError("Not Postgres database connection available")
		elif isinstance(self._db_pg, str):
			if psycopg is None:
				raise ImportError("psycopg required")
			self._db_pg = psycopg.connect(self._db_pg)
		return self._db_pg

	@property
	def varchars(self):
		if self._varchars is None:
			self._varchars = self.db.gettype("LL.VARCHARS")
		return self._varchars

	def cursor(self):
		return self.db.cursor(readlobs=True)

	def cursor_pg(self, row_factory=rows.tuple_row):
		return self.db_pg.cursor(row_factory=row_factory)

	def commit(self):
		self.db.commit()

	def rollback(self):
		self.db.rollback()

	def reset(self):
		super().reset()
		self.proc_clear_all(self.cursor())

	def seq(self):
		c = self.cursor()
		(value, r) = self.func_seq(c)
		return value

	def save_app(self, app, recursive=True):
		# FIXME: Save the app itself
		if recursive:
			if app.internaltemplates is not None:
				for internaltemplate in app.internaltemplates.values():
					self.save_internaltemplate(internaltemplate, recursive=recursive)
			if app.viewtemplates is not None:
				for viewtemplate in app.viewtemplates.values():
					self.save_viewtemplate(viewtemplate, recursive=recursive)
			if app._params is not None:
				for param in app._params.values():
					self.save_param(param)

	def save_file(self, file):
		if file.internalid is None:
			if file._content is None:
				raise ValueError(f"Can't save {file!r} without content!")
			c = self.cursor()
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
			with (self.uploaddir/r.p_upl_name).open("wb", context=self.urlcontext) as f:
				f.write(file._content)
			file.internalid = r.p_upl_id

	def file_content(self, file):
		upr_id = file.url.rsplit("/")[-1]
		c = self.cursor()
		c.execute(
			"select u.upl_name from upload u, uploadref ur where u.upl_id=ur.upl_id and ur.upr_id = :upr_id",
			upr_id=upr_id,
		)
		r = c.fetchone()
		if r is None:
			raise ValueError(f"no such file {file.url!r}")
		with url.Context():
			u = self.uploaddir/r.upl_name
			return u.openread().read()

	def save_param(self, param):
		c = self.cursor()
		r = self._save_param(
			c,
			identifier=param.identifier,
			description=param.description,
			value=param.value,
			parentappid=param.parent.id if isinstance(param.parent, la.App) else None,
			parentviewtemplateid=param.parent.id if isinstance(param.parent, la.ViewTemplateConfig) else None,
			parentemailtemplateid=param.parent.id if isinstance(param.parent, la.EMailTemplate) else None,
		)
		param.id = r.p_ap_id

	def _save_param(self, cursor, *, identifier=None, order=None, description=None, value=None, superid=None, parentappid=None, parentviewtemplateid=None, parentemailtemplateid=None):
		p_ap_type = None
		p_ap_value_bool = None
		p_ap_value_date = None
		p_ap_value_datetime = None
		p_ap_value_other = None
		p_upl_id = None
		p_tpl_uuid_value = None
		p_ctl_id = None

		if value is None:
			# Could be any other type too
			p_ap_type = "str"
		elif isinstance(value, bool):
			p_ap_value_bool = int(value)
			p_ap_type = "bool"
		elif isinstance(value, datetime.datetime):
			p_ap_value_datetime = value
			p_ap_type = "datetime"
		elif isinstance(value, datetime.date):
			p_ap_value_date = value
			p_ap_type = "date"
		elif isinstance(value, la.File):
			p_upl_id = value.internalid
			p_ap_type = "upload"
		elif isinstance(value, la.App):
			p_tpl_uuid_value = value.id
			p_ap_type = "App"
		elif isinstance(value, la.Control):
			p_ctl_id = value.id
			p_ap_type = "control"
		elif isinstance(value, int):
			p_ap_value_other = str(value)
			p_ap_type = "int"
		elif isinstance(value, float):
			p_ap_value_other = str(value)
			p_ap_type = "number"
		elif isinstance(value, str):
			p_ap_value_other = value
			p_ap_type = "str"
		elif isinstance(value, color.Color):
			p_ap_value_other = str((((value.r() << 8) + value.g() << 8) + value.b() << 8) + value.a())
			p_ap_type = "color"
		elif isinstance(value, datetime.timedelta):
			value = value.total_seconds()/86400
			p_ap_type = "datetimedelta" if value.seconds or value.microseconds else "datedelta"
		elif isinstance(value, misc.monthdelta):
			p_ap_value_other = str(value.months)
			p_ap_type = "monthdelta"
		elif isinstance(value, list):
			p_ap_type = "list"
		elif isinstance(value, dict):
			p_ap_type = "dict"
		else:
			raise TypeError(f"Can't save parameter of type {type(value)}")

		r = self.proc_appparameter_import_waf(
			cursor,
			c_user=self.ide_id,
			p_tpl_uuid=parentappid,
			p_vt_id=parentviewtemplateid,
			p_et_id=parentemailtemplateid,
			p_ap_id_super=superid,
			p_ap_order=order,
			p_ap_identifier=identifier,
			p_ap_type=p_ap_type,
			p_ap_description=description,
			p_ap_value_bool=p_ap_value_bool,
			p_ap_value_date=p_ap_value_date,
			p_ap_value_datetime=p_ap_value_datetime,
			p_ap_value_other=p_ap_value_other,
			p_upl_id=p_upl_id,
			p_tpl_uuid_value=p_tpl_uuid_value,
			p_ctl_id=p_ctl_id,
		)

		if isinstance(value, list):
			order = 10
			for v in value:
				self._save_param(
					c,
					order=order,
					value=v,
					superid=r.p_ap_id,
					parentappid=parentappid,
					parentviewtemplateid=parentviewtemplateid,
					parentemailtemplateid=parentemailtemplateid,
				)
				order += 10
		elif isinstance(value, dict):
			for (identifier, v) in value.items():
				self._save_param(
					c,
					identifier=identifier,
					value=v,
					superid=r.p_ap_id,
					parentappid=parentappid,
					parentviewtemplateid=parentviewtemplateid,
					parentemailtemplateid=parentemailtemplateid,
				)
		return r


	def _save_vsql_ast(self, vsqlexpr, required_datatype=None, cursor=None, vs_id_super=None, vs_order=None, vss_id=None, pos=None):
		"""
		Save the vSQL expression :obj:`vsqlexpr`.

		``cursor``, ``vs_id_super``, ``vs_order``, ``vss_id`` and ``pos`` are used
		internally for recursive calls and should not be passed by the user.
		"""
		if cursor is None:
			cursor = self.cursor()
		source = vsqlexpr.source()
		sourcelen = len(source)
		if pos is None:
			pos = 0
		finalpos = pos + sourcelen

		datatype = vsqlexpr.datatype
		error = vsqlexpr.error
		if vss_id is None:
			# Validate target datatype (if the tree is valid so far)
			if datatype is not None:
				error = vsql.DataType.compatible_to(datatype, required_datatype)
				if error is not None:
					datatype = None

			r = self.proc_vsqlsource_insert(
				cursor,
				c_user=self.ide_id,
				p_vss_source=source,
			)
			vss_id = r.p_vss_id
		r = self.proc_vsql_insert(
			cursor,
			c_user=self.ide_id,
			p_vs_id_super=vs_id_super,
			p_vs_order=vs_order,
			p_vs_nodetype=vsqlexpr.nodetype.value,
			p_vs_value=vsqlexpr.nodevalue,
			p_vs_datatype=datatype.value if datatype is not None else None,
			p_vs_erroridentifier=error.value if error is not None else None,
			p_vss_id=vss_id,
			p_vs_start=pos,
			p_vs_stop=finalpos,
		)
		vs_id = r.p_vs_id
		# FieldRefAST has children in the implementation, but in the database it has not
		if not isinstance(vsqlexpr, vsql.FieldRefAST):
			order = 10
			for child in vsqlexpr.content:
				if isinstance(child, str):
					pos += len(child)
				else:
					(_, pos) = self._save_vsql_ast(child, None, cursor, vs_id, order, vss_id, pos)
					order += 10
		return (vs_id, finalpos)

	def save_vsql_ast(self, vsqlexpr, datatype=None, cursor=None):
		return self._save_vsql_ast(vsqlexpr, datatype, cursor)[0]

	def save_vsql_source(self, cursor, source, function, datatype=None, **queryargs):
		if not source:
			return None

		if cursor is None:
			cursor = self.cursor()

		args = ", ".join(f"{a}=>:{a}" for a in queryargs)
		query = f"select {function}({args}) from dual"
		cursor.execute(query, **queryargs)
		dump = cursor.fetchone()[0]
		dump = dump.decode("utf-8")
		vars = ul4on.loads(dump)
		vsqlexpr = vsql.AST.fromsource(source, **vars)
		return self.save_vsql_ast(vsqlexpr, datatype, cursor)

	def save_internaltemplate(self, internaltemplate, recursive=True):
		template = ul4c.Template(internaltemplate.source, name=internaltemplate.identifier)
		cursor = self.cursor()
		self.proc_internaltemplate_import(
			cursor,
			c_user=self.ide_id,
			p_tpl_uuid=internaltemplate.app.id,
			p_it_identifier=template.name,
			p_utv_source=template.source,
			p_utv_signature=ul4c._str(template.signature) if template.signature is not None else None,
			p_utv_whitespace=template.whitespace,
			p_utv_doc=template.doc,
		)

	def save_viewtemplate(self, viewtemplate, recursive=True):
		template = ul4c.Template(viewtemplate.source, name=viewtemplate.identifier)
		cursor = self.cursor()
		r = self.proc_viewtemplate_import(
			cursor,
			c_user=self.ide_id,
			p_tpl_uuid=viewtemplate.app.id,
			p_vt_type=viewtemplate.type.value,
			p_vt_identifier=template.name,
			p_vt_mimetype=viewtemplate.mimetype,
			p_utv_signature=ul4c._str(template.signature) if template.signature is not None else None,
			p_utv_whitespace=template.whitespace,
			p_utv_doc=template.doc,
			p_utv_source=template.source,
			p_vt_permission_level=viewtemplate.permission.value
		)
		viewtemplate.id = r.p_vt_id
		if recursive:
			for datasource in viewtemplate.datasources.values():
				self.save_datasourceconfig(datasource, recursive=recursive)

	def delete_viewtemplate(self, viewtemplate):
		cursor = self.cursor()
		self.proc_viewtemplate_delete(
			cursor,
			c_user=self.ide_id,
			p_vt_id=viewtemplate.id,
		)
		viewtemplate._deleted = True

	def delete_internaltemplate(self, internaltemplate):
		cursor = self.cursor()
		self.proc_internaltemplate_delete(
			cursor,
			c_user=self.ide_id,
			p_it_id=internaltemplate.id,
		)
		internaltemplate._deleted = True

	def save_datasourceconfig(self, datasource, recursive=True):
		cursor = self.cursor()

		# Compile and save the app filter
		vs_id_appfilter = self.save_vsql_source(
			cursor,
			datasource.appfilter,
			la.DataSourceConfig.appfilter.function,
			p_vt_id=datasource.parent.id,
			p_tpl_uuid_a=None,
		)

		# Compile and save the record filter
		vs_id_recordfilter = self.save_vsql_source(
			cursor,
			datasource.recordfilter,
			la.DataSourceConfig.recordfilter.function,
			p_vt_id=datasource.parent.id,
			p_tpl_uuid_r=datasource.app.id if datasource.app is not None else None,
		)

		# FIXME: Support for system apps?
		r = self.proc_datasource_import(
			cursor,
			c_user=self.ide_id,
			p_vt_id=datasource.parent.id,
			p_tpl_uuid=datasource.app.id if datasource.app is not None else None,
			p_dmv_id=None,
			p_tpl_uuid_systemplate=None,
			p_ds_includerecords=int(datasource.includerecords),
			p_ds_includecontrols=int(datasource.includecontrols),
			p_ds_includecount=int(datasource.includecount),
			p_ds_includecloned=int(datasource.includecloned),
			p_ds_identifier=datasource.identifier,
			p_ds_includepermissions=int(datasource.includepermissions),
			p_ds_includeattachments=int(datasource.includeattachments),
			p_ds_includecategories=int(datasource.includecategories),
			p_ds_includeparams=int(datasource.includeparams),
			p_ds_includeviews=int(datasource.includeviews),
			p_ds_recordpermission=int(datasource.recordpermission),
			p_vs_id_appfilter=vs_id_appfilter,
			p_vs_id_recordfilter=vs_id_recordfilter,
		)
		datasource.id = r.p_ds_id

		if recursive:
			self._save_dataorders(
				cursor,
				datasource.orders,
				"VSQLSUPPORT_PKG3.DS_ORDER_FUL4ON",
				ds_id=r.p_ds_id,
			)
			for children in datasource.children.values():
				self.save_datasourcechildren(children, recursive=recursive)

	def save_datasourcechildren(self, datasourcechildren, recursive=True):
		cursor = self.cursor()

		# Find the ``ctl_id`` for the target control
		query = """
			select
				ctl_id
			from
				template t,
				control c
			where
				t.tpl_uuid = :tpl_uuid and
				t.tpl_id = c.tpl_id and
				c.ctl_identifier = :ctl_identifier
		"""

		cursor.execute(
			query,
			tpl_uuid=datasourcechildren.control.app.id,
			ctl_identifier=datasourcechildren.control.identifier,
		)
		ctl_id = cursor.fetchone()[0]

		# Compile and save the record filter
		vs_id_filter = self.save_vsql_source(
			cursor,
			datasourcechildren.filter,
			la.DataSourceChildren.filter.function,
			p_ds_id=datasourcechildren.datasource.id,
			p_ctl_id=ctl_id,
		)

		# Import the ``datasourcechildren`` record
		r = self.proc_datasourcechildren_import(
			cursor,
			c_user=self.ide_id,
			p_ds_id=datasourcechildren.datasource.id,
			p_dsc_identifier=datasourcechildren.identifier,
			p_ctl_id=ctl_id,
			p_ctl_id_syscontrol=None,
			p_vs_id_filter=vs_id_filter,
		)
		datasourcechildren.id = r.p_dsc_id

		if recursive:
			self._save_dataorders(
				cursor,
				datasourcechildren.orders,
				"VSQLSUPPORT_PKG3.DSC_ORDER_FUL4ON",
				dsc_id=r.p_dsc_id,
			)

	def _save_dataorders(self, cursor, orders, function, **kwargs):
		queryargs = " and ".join(f"{k}=:{k}" for k in kwargs)
		procargs = {"p_" + k: v for (k, v) in kwargs.items()}
		query = f"select do_id, do_order from dataorder where {queryargs} order by do_order"
		cursor.execute(query, **kwargs)
		old_records = [(r2.do_id, r2.do_order) for r2 in cursor]
		last_order = 0
		for (old_record, dataorder) in itertools.zip_longest(old_records, orders):
			if old_record is not None:
				(do_id, do_order) = old_record
			else:
				(do_id, do_order) = (None, last_order + 10)
			if dataorder is not None:
				# Compile and save the order expression
				vs_id_expression = self.save_vsql_source(
					cursor,
					dataorder.expression,
					function,
					**procargs,
				)

				# Import the ``dataorder`` record
				r = self.proc_dataorder_import(
					cursor,
					c_user=self.ide_id,
					p_vs_id_expression=vs_id_expression,
					p_do_direction=dataorder.direction.value,
					p_do_nulls=dataorder.nulls.value,
					p_do_order=do_order,
					**procargs,
				)
				dataorder.id = r.p_do_id
				last_order = do_order
			else:
				self.proc_dataorder_delete(cursor, c_user=self.ide_id, p_do_id=do_id)

	def _reinitialize_livingapi_db(self, cursor, globals):
		"""
		Reinitialize the server side state of the UL4ON codec machinery.

		We do this by calling ``livingapi_pkg.init()`` passing the local
		information about the current view/email template and detail record.

		We also need to pass the state of the local UL4ON backref registry to
		the server so that existing object won't have to be loaded again.

		(This is mostly a performance optimization, but for email templates it
		is essential that the detail record won't be loaded again, as we want
		to use the state of the record as it was recorded in
		``emailqueue.eq_data``).
		"""
		backrefs = []

		# The backref registry might contain objects for which we can't sync
		# backreferences to the database. This can happen when the dump hasn't
		# been created by the database (for example when the template gateway
		# puts an UL4ON dump into the session). But since the database doesn't
		# know how to create those backreferences, we can be sure that it doesn't
		# create then, so we can put any object into that backreference slot
		# (But we **do** have to put something in that slot, otherwise all
		# following backreference indexes would be off by one.
		# For those fake backreferences we use the special type ``ignore``
		# which is handled specifically by ``livingapi_pkg.init_ul4on()``
		for obj in self.ul4on_decoder._objects:
			ul4onname = "ignore"
			ul4onid = None
			if isinstance(obj, str):
				# We tell the database to ignore long string, since it can't
				# create backreferences to those.
				if len(obj) < 296:
					ul4onname = "str"
					ul4onid = obj
				# Else:
			elif hasattr(obj, "ul4onname"):
				# Ignore backreferences to ``Geo`` objects
				if not isinstance(obj, la.Geo):
					if obj.ul4onid is None:
						raise TypeError(f"Can't sync backreference to non-persistent object of type {type(obj)!r}")
					else:
						ul4onname = obj.ul4onname
						ul4onid = obj.ul4onid
			# For everthing else we have a back reference that couldn't have been
			# produced by the database, so we ignore it too.
			backrefs.append(ul4onname)
			backrefs.append(ul4onid)

		args = dict(
			c_user=self.ide_id,
			p_ul4onbackrefs=self.varchars(backrefs),
		)
		if globals.emailtemplate_id is not None:
			args["p_et_id"] = globals.emailtemplate_id
		elif globals.viewtemplate_id is not None:
			args["p_vt_id"] = globals.viewtemplate_id
		elif globals.view_id is not None:
			args["p_vw_id"] = globals.view_id
		elif globals.app is not None:
			args["p_tpl_uuid"] = globals.app.id
		if globals.record is not None:
			args["p_dat_id"] = globals.record.id
		self.proc_init(cursor, **args)

	def _execute_incremental_ul4on_query(self, cursor, globals, query, **args):
		"""
		Returns the deserialized UL4ON data from executing a database function
		that returns an "incremental" dump. ("incremental" means that it might
		have backreferences to a previous dump). The data from this dump
		will be merged into the exiting data.

		When such a database function (e.g. ``livingapi_pkg.app_params_inc_ful4on()``)
		detects that the UL4ON codec machinery in ``ul4onblobbuffer_pkg`` and
		``livingapi_pkg`` hasn't been initialized yet, it returns ``null``.

		This can happen in email templates where the UL4ON dump will not be loaded
		via calls to ``livingapi_pkg.data_ful4on()`` (but from
		``emailqueue.eq_data``) or when executing a data action results in an
		email, so that an UL4ON dump for the email queue will be generated, which
		results in the UL4ON codec machinery being reset.

		In this case we have to reinitialize the UL4ON codec machinery (by calling
		:meth:`_reinitialize_livingapi_db`) and try calling the database function
		again.
		"""
		cursor.execute(query, **args)
		dump = cursor.fetchone()[0]
		if dump is None:
			self._reinitialize_livingapi_db(cursor, globals)
			cursor.execute(query, **args)
			dump = cursor.fetchone()[0]
		dump = dump.decode("utf-8")
		dump = self._loaddump(dump)
		return dump

	def meta_data(self, *appids):
		cursor = self.cursor()
		tpl_uuids = self.varchars(appids)
		cursor.execute(
			"select livingapi_pkg.metadata_ful4on(c_user=>:ide_id, p_tpl_uuids=>:tpl_uuids) from dual",
			ide_id=self.ide_id,
			tpl_uuids=tpl_uuids,
		)
		r = cursor.fetchone()
		dump = r[0].decode("utf-8")
		dump = self._loaddump(dump)
		return dump

	def record_sync_data(self, dat_id, force=False):
		if not force:
			result = self.ul4on_decoder.persistent_object(la.Record.ul4onname, dat_id)
			if result is not None:
				return result
		c = self.cursor()
		c.execute(
			"select livingapi_pkg.record_sync_ful4on(p_dat_id=>:dat_id, p_force=>:force) from dual",
			dat_id=dat_id,
			force=int(force),
		)
		r = c.fetchone()
		dump = r[0].decode("utf-8")
		record = self._loaddump(dump)
		return record

	def records_sync_data(self, dat_ids, force=False):
		if force:
			missing = set(dat_ids)
		else:
			missing = set()
			for dat_id in dat_ids:
				record = self.ul4on_decoder.persistent_object(la.Record.ul4onname, dat_id)
				if record is None:
					missing.add(dat_id)
				else:
					found[dat_id] = record
		c = self.cursor()
		c.execute(
			"select livingapi_pkg.records_sync_ful4on(p_dat_ids=>:dat_ids, p_force=>:force) from dual",
			dat_ids=self.varchars(missing),
			force=int(force),
		)
		r = c.fetchone()
		dump = r[0].decode("utf-8")
		records = self._loaddump(dump)
		return records

	def _data(self, vt_id=None, et_id=None, vw_id=None, tpl_uuid=None, dat_id=None, dat_ids=None, ctl_identifier=None, searchtext=None, reqparams=None, mode=None, sync=False, exportmeta=False, funcname="data_ful4on"):
		paramslist = []
		if reqparams:
			for (key, value) in reqparams.items():
				if value is not None:
					if isinstance(value, str):
						paramslist.append(key)
						paramslist.append(value)
					elif isinstance(value, list):
						for subvalue in value:
							paramslist.append(key)
							paramslist.append(subvalue)
		paramslist = self.varchars(paramslist)

		c = self.cursor()

		# Reset the UL4ON decoder before loading
		# (since the server will reset its UL4ON codec state too)
		self.reset()

		c.execute(
			"""
				select
					livingapi_pkg.data_ful4on(
						c_user => :c_user,
						p_requestid => :p_requestid,
						p_vt_id => :p_vt_id,
						p_et_id => :p_et_id,
						p_vw_id => :p_vw_id,
						p_tpl_uuid => :p_tpl_uuid,
						p_dat_id => :p_dat_id,
						p_dat_ids => :p_dat_ids,
						p_ctl_identifier => :p_ctl_identifier,
						p_searchtext => :p_searchtext,
						p_reqparams => :p_reqparams,
						p_mode => :p_mode,
						p_sync => :p_sync,
						p_exportmeta => :p_exportmeta,
						p_funcname => :p_funcname
					)
				from dual
			""",
			c_user=self.ide_id,
			p_requestid=self.requestid,
			p_vt_id=vt_id,
			p_et_id=et_id,
			p_vw_id=vw_id,
			p_tpl_uuid=tpl_uuid,
			p_dat_id=dat_id,
			p_dat_ids=self.varchars(dat_ids or []),
			p_ctl_identifier=ctl_identifier,
			p_searchtext=searchtext,
			p_reqparams=paramslist,
			p_mode=mode,
			p_sync=int(sync),
			p_exportmeta=int(exportmeta),
			p_funcname=funcname,
		)

		r = c.fetchone()
		dump = r[0].decode("utf-8")
		dump = self._loaddump(dump)
		# Since the database didn't reset its backref registry, we don't either
		return dump

	def viewtemplate_data(self, *path, **params):
		if not 1 <= len(path) <= 2:
			raise ValueError(f"need one or two path components, got {len(path)}")

		appid = path[0]
		datid = path[1] if len(path) > 1 else None

		c = self.cursor()

		c.execute("select tpl_id from template where tpl_uuid = :appid", appid=appid)
		r = c.fetchone()
		if r is None:
			raise ValueError(f"no app {appid!r}")
		tpl_id = r.tpl_id
		if "template" in params:
			template = params.pop("template")
			c.execute(
				"select vt_id from viewtemplate where tpl_id = :tpl_id and vt_identifier = :identifier",
				tpl_id=tpl_id,
				identifier=template,
			)
		else:
			template = None
			c.execute(
				"select vt_id from viewtemplate where tpl_id = :tpl_id and vt_type = 'listdefault'",
				tpl_id=tpl_id,
			)
		r = c.fetchone()
		if r is None:
			if template is None:
				raise ValueError(f"no default template for app {appid!r}")
			else:
				raise ValueError(f"no template named {template!r} for app {appid!r}")
		vt_id = r.vt_id

		return self._data(vt_id=r.vt_id, dat_id=datid, reqparams=params, funcname="viewtemplatedata_ful4on")

	def viewtemplate_params_incremental_data(self, globals, id):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			globals,
			"select livingapi_pkg.viewtemplate_params_inc_ful4on(:vtid) from dual",
			vtid=id,
		)

	def emailtemplate_params_incremental_data(self, globals, id):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			globals,
			"select livingapi_pkg.emailtemplate_params_inc_ful4on(:etid) from dual",
			etid=id,
		)

	def app_params_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_params_inc_ful4on(:appid) from dual",
			appid=app.id,
		)

	def app_views_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_views_inc_ful4on(:appid) from dual",
			appid=app.id,
		)

	def record_attachments_incremental_data(self, record):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			record.app.globals,
			"select livingapi_pkg.record_attachments_inc_ful4on(:dataid) from dual",
			dat=record.id,
		)

	def save_record(self, record, recursive=True):
		record.clear_errors()
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
		if real:
			if record.id is None:
				args["p_tpl_uuid"] = app.id
			mode = record.app.globals.mode
			args["p_mode"] = mode.value if mode is not None else None
		if record.id is not None:
			args[f"p_{pk}"] = record.id
		for field in record.fields.values():
			if record.id is None or field._dirty:
				args[f"p_{field.control.fieldname}"] = field._asdbarg(self)
				if record.id is not None:
					args[f"p_{field.control.fieldname}_changed"] = 1
		c = self.cursor()
		try:
			result = proc(c, **args)
		except orasql.DatabaseError as exc:
			error = exc.args[0]
			if error.code == 20010:
				parts = error.message.split("\x01")[1:-1]
				if parts:
					# An error message with the usual formatting from ``errmsg_pkg``.
					controls_by_field = {c.field: c for c in record.app.controls.values()} # Maps the field name to the control
					field = None
					for (i, part) in enumerate(parts):
						if i % 2:
							if field:
								identifier = controls_by_field[field].identifier
								record.fields[identifier].add_error(part)
							else:
								record.add_error(part)
						else:
							field = part
				else:
					# An error message with strange formatting, use this as is.
					record.add_error(error.message)
				return False
			else:
				# Some other database exception
				raise

		if result.p_errormessage:
			record.add_error(result.p_errormessage)
			saved = False
		else:
			saved = True

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

		return saved

	def delete_record(self, record):
		app = record.app
		args = {
			"c_user": self.ide_id,
			"p_dat_id": record.id,
		}
		if app.basetable in {"data_select", "data"}:
			proc = self.proc_data_delete
			mode = record.app.globals.mode
			args["p_mode"] = mode.value if mode is not None else None
		else:
			proc = self._getproc(app.deleteprocedure)

			mode = record.app.globals.mode

		c = self.cursor()
		r = proc(c, **args)
		record._deleted = True

		if r.p_errormessage:
			raise ValueError(r.p_errormessage)

	def save_parameter(self, parameter, recursive=True):
		c = self.cursor()
		app = parameter.owner

		p_ap_value_bool = None
		p_ap_value_date = None
		p_ap_value_datetime = None
		p_ap_value_str = None
		p_ap_value_html = None
		p_ap_value_other = None
		p_upl_id = None
		p_tpl_uuid_value = None
		p_ctl_id = None

		if parameter.value is not None:
			if parameter.type is parameter.Type.BOOL:
				p_ap_value_bool = int(parameter.value)
			elif parameter.type is parameter.Type.INT:
				p_ap_value_other = str(parameter.value)
			elif parameter.type is parameter.Type.NUMBER:
				p_ap_value_other = str(parameter.value)
			elif parameter.type is parameter.Type.STR:
				p_ap_value_str = parameter.value
			elif parameter.type is parameter.Type.HTML:
				p_ap_value_html = parameter.value
			elif parameter.type is parameter.Type.COLOR:
				p_ap_value_other = parameter.value.r << 24 | parameter.value.g << 16 | parameter.value.b << 8 | parameter.value.a
			elif parameter.type is parameter.Type.DATE:
				p_ap_value_other = parameter.value
			elif parameter.type is parameter.Type.DATETIME:
				p_ap_value_date = parameter.value
			elif parameter.type is parameter.Type.DATETIME:
				p_ap_value_datetime = parameter.value
			elif parameter.type is parameter.Type.DATEDELTA:
				p_ap_value_datetime = parameter.value.days
			elif parameter.type is parameter.Type.DATETIMEDELTA:
				p_ap_value_datetime = parameter.value.days + parameter.value.days/24/60/60 + parameter.value.days/24/60/60/100000
			elif parameter.type is parameter.Type.MONTHDELTA:
				p_ap_value_datetime = parameter.value.months
			elif parameter.type is parameter.Type.UPLOAD:
				if parameter.value.internalid is None:
					raise la.ValueError(error_object_unsaved(parameter.value))
				p_upl_id = parameter.value.internalid
			elif parameter.type is parameter.Type.APP:
				p_tpl_uuid_value = parameter.value.id
			elif parameter.type is parameter.Type.CONTROL:
				p_ctl_id = parameter.value.id

		try:
			result = self.proc_appparameter_save(
				c,
				c_user=self.ide_id,
				c_lang="de", # FIXME
				p_requestid=self.requestid,
				p_ap_id=parameter.id,
				p_tpl_uuid=app.id,
				p_vt_id=None,
				p_et_id=None,
				p_ap_id_super=parameter.parent.id if parameter.parent is not None else None,
				p_ap_order=parameter.order,
				p_ap_identifier=parameter.identifier,
				p_ap_type=parameter.type.value,
				p_ap_description=parameter.description,
				p_ap_value_bool=p_ap_value_bool,
				p_ap_value_date=p_ap_value_date,
				p_ap_value_datetime=p_ap_value_datetime,
				p_ap_value_str=p_ap_value_str,
				p_ap_value_html=p_ap_value_html,
				p_ap_value_other=p_ap_value_other,
				p_upl_id=p_upl_id,
				p_tpl_uuid_value=p_tpl_uuid_value,
				p_ctl_id=p_ctl_id,
			)
		except orasql.DatabaseError as exc:
			error = exc.args[0]
			if error.code == 20010:
				parts = error.message.split("\x01")[1:-1]
				if parts:
					# An error message with the usual formatting from ``errmsg_pkg``.
					raise ValueError("\n".join(parts[1::2]))
				else:
					# An error message with strange formatting, use it as it is.
					raise ValueError(error.message)
			else:
				# Some other database exception
				raise

		if parameter.id is None:
			parameter.id = result.p_ap_id
			parameter.createdat = datetime.datetime.now()
			parameter.createdby = app.globals.user
		else:
			parameter.updatedat = datetime.datetime.now()
			parameter.updatedby = app.globals.user
		parameter._dirty = False

	def parameter_sync_data(self, ap_id):
		c = self.cursor()
		c.execute(
			"select livingapi_pkg.appparam_sync_ful4on(p_ap_id=>:ap_id) from dual",
			ap_id=ap_id,
		)
		r = c.fetchone()
		dump = r[0].decode("utf-8")
		parameter = self._loaddump(dump)
		return parameter

	def _executeaction(self, record, actionidentifier):
		c = self.cursor()
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
			proc = self.db.object_named(procname)
			if not isinstance(proc, orasql.Procedure):
				raise ValueError(f"no procedure {procname}")
			self.custom_procs[procname] = proc
			return proc

	def _loadinternaltemplates(self, tpl_uuid):
		if tpl_uuid in self.internaltemplates:
			return self.internaltemplates[tpl_uuid]
		c = self.cursor()
		c.execute("""
			select
				it_identifier,
				utv_source
			from
				internaltemplate_select
			where
				tpl_uuid=:tpl_uuid
		""", tpl_uuid=tpl_uuid)
		templates = {}
		for r in c:
			template = ul4c.Template(r.utv_source, name=r.it_identifier)
			templates[template.name] = template
		self.internaltemplates[tpl_uuid] = templates
		return templates

	def fetch_templates(self, app):
		if app.superid is None:
			return self._loadinternaltemplates(app.id)
		else:
			return {
				**self._loadinternaltemplates(app.superid),
				**self._loadinternaltemplates(app.id),
			}

	def fetch_viewtemplate_params(self, globals):
		id = globals.viewtemplate_id
		if id not in self.viewtemplate_params:
			self.viewtemplate_params[id] = self.viewtemplate_params_incremental_data(globals, id)
		return self.viewtemplate_params[id]

	def fetch_emailtemplate_params(self, globals):
		id = globals.emailtemplate_id
		if id not in self.emailtemplate_params:
			self.emailtemplate_params[id] = self.emailtemplate_params_incremental_data(globals, id)
		return self.emailtemplate_params[id]

	def fetch_templatelibraries(self):
		if self.templatelibraries is None:
			c = self.cursor_pg(row_factory=rows.tuple_row)
			c.execute("select templatelibrary.alltemplatelibraries_ful4on()")
			r = c.fetchone()
			dump = r[0]
			# Don't reuse the decoder for the dumps from Oracle, this is an independent one
			# Note that we ignore the problem of persistent objects, since none of the
			# persistent objects in this dump are in the other dump
			dump = ul4on.loads(dump)
			if isinstance(dump, dict):
				dump = la.attrdict(dump)
			self.templatelibraries = la.attrdict(dump)
		return self.templatelibraries


class HTTPHandler(Handler):
	def __init__(self, url, username=None, password=None, auth_token=None):
		super().__init__()
		if not url.endswith("/"):
			url += "/"
		url += "gateway/"
		self.url = url
		self.username = username
		self.password = password
		self.session = None
		self.auth_token = auth_token

	def __repr__(self):
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} url={self.url!r} username={self.username!r} at {id(self):#x}>"

	def _login(self):
		if self.session is None:
			self.session = requests.Session()
			if self.auth_token is None:
				# If :obj:`username` or :obj:`password` are not given, we don't log in
				# This means we can only fetch data for public templates, i.e. those that are marked as "for all users"
				if self.username is not None and self.password is not None:
					# Login to the LivingApps installation and store the auth token we get
					r = self.session.post(
						f"{self.url}login",
						data=json.dumps({"username": self.username, "password": self.password}),
						headers={"Content-Type": "application/json"},
					)
					result = r.json()
					if result.get("status") == "success":
						self.auth_token = result["auth_token"]
					else:
						raise_403(r)

	def _add_auth_token(self, kwargs):
		self._login()
		if self.auth_token:
			if "headers" not in kwargs:
				kwargs["headers"] = {}
			kwargs["headers"]["X-La-Auth-Token"] = self.auth_token

	def save_file(self, file):
		if file.internalid is None:
			if file._content is None:
				raise ValueError(f"Can't save {file!r} without content!")
			kwargs = {
				"files": {
					"files[]": (file.filename, file._content, file.mimetype),
				},
			}
			self._add_auth_token(kwargs)
			r = self.session.post(
				f"{self.url}upload/tempfiles",
				**kwargs,
			)
			r.raise_for_status()
			result = r.json()[0]
			file.name = result["orgname"]
			file.id = result["upr_id"]
			file.width = result["width"]
			file.height = result["height"]
			file.size = result["size"]
			file.mimetype = result["mimetype"]
			file.internalid = result["upl_id"]
			file.url = f"/gateway/files/{file.id}"

	def file_content(self, file):
		kwargs = {}
		self._add_auth_token(kwargs)
		r = self.session.get(
			self.url.rstrip("/") + file.url,
			**kwargs,
		)
		r.raise_for_status()
		return r.content

	def records_sync_data(self, dat_ids, force=False):
		if not dat_ids:
			return {}
		raise NotImplementedError("Can't sync records via {self!r}")

	def viewtemplate_data(self, *path, **params):
		if not 1 <= len(path) <= 2:
			raise ValueError(f"need one or two path components, got {len(path)}")
		kwargs = {
			"headers": {
				"Accept": "application/la-ul4on",
			},
			"params": {
				key + "[]" if isinstance(value, list) else key: value
				for (key, value) in params.items()
			},
		}
		path = "/".join(path)
		self._add_auth_token(kwargs)
		r = self.session.get(
			f"{self.url}apps/{path}",
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

	def save_record(self, record, recursive=True):
		record.clear_errors()
		fields = {field.control.identifier: field._asjson(self) for field in record.fields.values() if record.id is None or field.is_dirty()}
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
			f"{self.url}v1/appdd/{app.id}.json",
			**kwargs,
		)
		if r.status_code >= 300 and r.status_code != 422:
			r.raise_for_status()
		result = json.loads(r.text)
		status = result["status"]
		if status != "ok":
			errors_added = False
			if "globalerrors" in result:
				for error in result["globalerrors"]:
					record.add_error(error)
					errors_added = True
			if "fielderrors" in result:
				for (identifier, errors) in result["fielderrors"].items():
					record.fields[identifier].add_error(*errors)
					errors_added = True
			if not errors_added:
				record.add_error(f"Response status {status!r}")
			return False
		else:
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
			return True

	def delete_record(self, record):
		kwargs = {}
		self._add_auth_token(kwargs)

		r = self.session.delete(
			f"{self.url}v1/appdd/{record.app.id}/{record.id}.json",
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
			f"{self.url}api/v1/apps/{record.app.id}/actions/{actionidentifier}",
			**kwargs,
		)
		r.raise_for_status()

	def record_sync_data(self, dat_id, force=False):
		result = self.ul4on_decoder.persistent_object(la.Record.ul4onname, dat_id)
		if result is not None and not force:
			return result
		raise NotImplementedError


class FileHandler(Handler):
	controltypes = {}
	for c in la.Control.__subclasses__():
		if hasattr(c, "fulltype"):
			controltypes[c.fulltype] = c
		for c2 in c.__subclasses__():
			if hasattr(c2, "fulltype"):
				controltypes[c2.fulltype] = c2
			del c2
		del c

	def __init__(self, basepath=None):
		if basepath is None:
			basepath = pathlib.Path()
		self.basepath = pathlib.Path(basepath)

	def meta_data(self, *appids):
		apps = {}
		for childpath in self.basepath.iterdir():
			if childpath.is_dir() and childpath.name.endswith(")") and " (" in childpath.name:
				pos = childpath.name.rfind(" (")
				id = childpath.name[pos+2:-1]
				name = childpath.name[:pos]
				app = la.App(name=name)
				app.id = id
				self._loadcontrols(app)
				self._loadinternaltemplates(app)
				apps[app.id] = app
		return attrdict(apps)

	def _loadcontrols(self, app):
		path = self.basepath/f"{app.name} ({app.id})/index.json"
		if path.exists():
			dump = json.loads(path.read_text(encoding="utf-8"))


	def _loadinternaltemplates(self, app):
		dir = self.basepath/f"{app.name} ({app.id})/internaltemplates"
		if dir.exists():
			for filepath in dir.iterdir():
				identifier = filepath.with_suffix("").name
				source = filepath.read_text(encoding="utf-8")
				template = ul4c.Template(source, name=identifier)
				internaltemplate = la.InternalTemplate(
					identifier=identifier,
					source=source,
					signature=str(template.signature) if template.signature is not None else None,
					whitespace=template.whitespace,
					doc=template.doc
				)
				app.addtemplate(internaltemplate)

	def save_app(self, app, recursive=True):
		configcontrols = self._controls_as_config(app)
		path = self.basepath/"index.json"
		self._save(path, json.dumps(configcontrols, indent="\t", ensure_ascii=False))
		if recursive:
			if app.internaltemplates is not None:
				for internaltemplate in app.internaltemplates.values():
					self.save_internaltemplate(internaltemplate, recursive=recursive)
			if app.viewtemplates is not None:
				for viewtemplate in app.viewtemplates.values():
					self.save_viewtemplate(viewtemplate, recursive=recursive)
			if app.dataactions is not None:
				for dataaction in app.dataactions.values():
					self.save_dataaction(dataaction)

	def _save(self, path, content):
		"""
		Save the text :obj:`context` to the path :obj:`path`.

		This method creates the parent directory of :obj:`path` if neccessary.
		"""
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

	def _guessext(self, basedir, template):
		"""
		Try to guess an extension for the template :obj:`template`.

		If there's only *one* file with a matching filename in the directory :obj:`basedir`,
		always use its filename, else try to guess the extension from the source.
		"""
		source = template.source or ""

		# If we have exactly *one* file with this basename in :obj:`basedir`, use this filename.
		candidates = list(pathlib.Path(basedir).glob(f"{template.identifier}.*ul4"))
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

	def _dumpattr(self, config, obj, name):
		r"""
		Put the attribute named :obj:`name` into the JSON configuration :obj:`config`.

		This means that if the attribute has the default value it will not be put
		into the config. All other values (e.g. :class:`Enum`\s) have to be converted
		to a JSON compatible type.
		"""
		value = getattr(obj, name)
		attr = getattr(obj.__class__, name)
		if value != attr.default:
			if isinstance(attr, la.EnumAttr):
				value = value.name.lower()
			elif isinstance(value, la.LookupItem):
				value = value.key
			elif isinstance(value, datetime.date):
				value = format(value, "%Y-%m-%d")
			elif isinstance(value, datetime.datetime):
				value = format(value, "%Y-%m-%d %H:%M:%S")
			elif isinstance(value, la.Record):
				value = value.id
			config[name] = value

	def save_internaltemplate(self, internaltemplate, recursive=True):
		dir = f"{self.basepath}/{internaltemplate.app.fullname}/internaltemplates"
		ext = self._guessext(dir, internaltemplate)
		path = pathlib.Path(dir, f"{internaltemplate.identifier}.{ext}")
		self._save(path, internaltemplate.source)

	def _controls_as_config(self, app):
		configcontrols = {}
		for control in app.controls.values():
			# We don't have to include the identifier as this will be used as the key
			configcontrol = {
				"type": f"{control.type}/{control.subtype}" if control.subtype else control.type,
			}
			configcontrols[control.identifier] = configcontrol
		return configcontrols

	def _datasource_as_config(self, datasource):
		configdatasource = {}
		if datasource.app is not None:
			configdatasource["app"] = datasource.app.fullname
		self._dumpattr(configdatasource, datasource, "includecloned")
		self._dumpattr(configdatasource, datasource, "appfilter")
		self._dumpattr(configdatasource, datasource, "includerecords")
		self._dumpattr(configdatasource, datasource, "includecontrols")
		self._dumpattr(configdatasource, datasource, "includecount")
		self._dumpattr(configdatasource, datasource, "recordpermission")
		self._dumpattr(configdatasource, datasource, "recordfilter")
		self._dumpattr(configdatasource, datasource, "includepermissions")
		self._dumpattr(configdatasource, datasource, "includeattachments")
		self._dumpattr(configdatasource, datasource, "includetemplates")
		self._dumpattr(configdatasource, datasource, "includeparams")
		self._dumpattr(configdatasource, datasource, "includeviews")
		self._dumpattr(configdatasource, datasource, "includecategories")
		configorders = self._dataorders_as_config(datasource.orders)
		if configorders:
			configdatasource["order"] = configorders
		configdatasourcechildren = {}
		for datasourcechildren in datasource.children.values():
			configdatasourcechildren[datasourcechildren.identifier] = self._datasourcechildren_as_config(datasourcechildren)
		if configdatasourcechildren:
			configdatasource["children"] = configdatasourcechildren
		return configdatasource

	def _datasourcechildren_as_config(self, datasourcechildren):
		configdatasourcechildren = {}
		self._dumpattr(configdatasourcechildren, datasourcechildren, "identifier")
		configdatasourcechildren["app"] = datasourcechildren.control.app.fullname
		configdatasourcechildren["control"] = datasourcechildren.control.identifier
		self._dumpattr(configdatasourcechildren, datasourcechildren, "filter")
		configorders = self._dataorders_as_config(datasourcechildren.orders)
		if configorders:
			configdatasourcechildren["order"] = configorders
		return configdatasourcechildren

	def _dataorders_as_config(self, orders):
		configorders = []
		for order in orders:
			configorder = {}
			self._dumpattr(configorder, order, "expression")
			self._dumpattr(configorder, order, "direction")
			self._dumpattr(configorder, order, "nulls")
			if list(configorder) == ["expression"]:
				configorder = configorder["expression"]
			configorders.append(configorder)
		return configorders

	def save_viewtemplate(self, viewtemplate, recursive=True):
		# Save the template itself
		dir = f"{self.basepath}/{viewtemplate.app.fullname}/viewtemplates"
		ext = self._guessext(dir, viewtemplate)
		path = pathlib.Path(dir, f"{viewtemplate.identifier}.{ext}")
		self._save(path, viewtemplate.source)

		# Save the template meta data
		config = {}
		self._dumpattr(config, viewtemplate, "type")
		self._dumpattr(config, viewtemplate, "mimetype")
		self._dumpattr(config, viewtemplate, "permission")
		if recursive:
			configalldatasources = {}
			for datasource in viewtemplate.datasources.values():
				configalldatasources[datasource.identifier] = self._datasource_as_config(datasource)
			if configalldatasources:
				config["datasources"] = configalldatasources
		# Only save a configuration if any of the values differs from the default
		configpath = path.with_suffix(".json")
		if config:
			self._save(configpath, json.dumps(config, indent="\t", ensure_ascii=False))
		else:
			try:
				configpath.unlink()
			except FileNotFoundError:
				pass

	def save_dataaction(self, dataaction, recursive=True):
		dir = f"{self.basepath}/{dataaction.app.fullname}/dataactions"
		path = pathlib.Path(dir, f"{dataaction.identifier}.json")
		config = self._dataaction_as_config(dataaction)
		self._save(path, json.dumps(config, indent="\t", ensure_ascii=False))

	def _dataaction_as_config(self, dataaction):
		configdataaction = {}
		self._dumpattr(configdataaction, dataaction, "name")
		self._dumpattr(configdataaction, dataaction, "order")
		self._dumpattr(configdataaction, dataaction, "active")
		self._dumpattr(configdataaction, dataaction, "icon")
		self._dumpattr(configdataaction, dataaction, "description")
		self._dumpattr(configdataaction, dataaction, "message")
		self._dumpattr(configdataaction, dataaction, "filter")
		self._dumpattr(configdataaction, dataaction, "as_multiple_action")
		self._dumpattr(configdataaction, dataaction, "as_single_action")
		self._dumpattr(configdataaction, dataaction, "as_mail_link")
		self._dumpattr(configdataaction, dataaction, "before_form")
		self._dumpattr(configdataaction, dataaction, "after_update")
		self._dumpattr(configdataaction, dataaction, "after_insert")

		configcommands = [self._dataactioncommand_as_config(dac) for dac in dataaction.commands]
		if configcommands:
			configdataaction["commands"] = configcommands
		# configdatasourcechildren = {}
		# for datasourcechildren in datasource.children.values():
		# 	configdatasourcechildren[datasourcechildren.identifier] = self._datasourcechildren_as_config(datasourcechildren)
		# if configdatasourcechildren:
		# 	configdatasource["children"] = configdatasourcechildren
		return configdataaction

	def _dataactioncommand_as_config(self, dataactioncommand):
		configdataactioncommand = {}
		type = dataactioncommand.ul4onname.rpartition("_")[-1]
		configdataactioncommand["type"] = type
		self._dumpattr(configdataactioncommand, dataactioncommand, "condition")
		configdetails = [
			self._dataactiondetail_as_config(d)
			for d in dataactioncommand.details
			if d.type
		]
		if configdetails:
			configdataactioncommand["details"] = configdetails
		if isinstance(dataactioncommand, la.DataActionCommandWithIdentifier):
			configdataactioncommand["app"] = dataactioncommand.app.fullname
			self._dumpattr(configdataactioncommand, dataactioncommand, "identifier")
			configchildren = [
				self._dataactioncommand_as_config(c)
				for c in dataactioncommand.children
			]
			if configchildren:
				dataactioncommand["children"] = configchildren

		return configdataactioncommand

	def _dataactiondetail_as_config(self, dataactiondetail):
		configdataactiondetail = {}
		configdataactiondetail["control"] = dataactiondetail.control.identifier
		self._dumpattr(configdataactiondetail, dataactiondetail, "type")
		self._dumpattr(configdataactiondetail, dataactiondetail, "value")
		self._dumpattr(configdataactiondetail, dataactiondetail, "expression")
		self._dumpattr(configdataactiondetail, dataactiondetail, "formmode")
		return configdataactiondetail
