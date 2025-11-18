#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2025 by LivingLogic AG, Bayreuth/Germany
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

import datetime, pathlib, itertools, json, operator, warnings, random

import requests, requests.exceptions # This requires :mod:`request`, which you can install with ``pip install requests``

from ll import misc, url, ul4c, ul4on # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``

try:
	from ll import orasql
except ImportError:
	orasql = None

orasql_required_message = "ll.orasql required (install via `pip install ll-xist`)"

try:
	import psycopg
except ImportError:
	psycopg = None

try:
	from psycopg import rows
except ImportError:
	rows = None

psycopg_required_message = "psycopg required (install via `pip install 'psycopg[binary]'`)"

from ll import la

from ll.la import vsql


__docformat__ = "reStructuredText"

__all__ = ["Handler", "HTTPHandler", "DBHandler", "FileHandler"]


###
### Typing stuff
###

from typing import *
T_opt_handler = Optional["ll.la.handlers.Handler"]
T_opt_int = Optional[int]
T_opt_float = Optional[float]
T_opt_str = Optional[str]
T_opt_file = Optional["ll.la.File"]

###
### Utility functions and classes
###

def uuid() -> str:
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
			"de.livinglogic.livingapi.globals": self._loadglobals,
		}
		self.ul4on_decoder = ul4on.Decoder(registry)

	def reset(self) -> None:
		"""
		Reset the handler to the initial state.

		This reset the UL4ON decoder.
		"""
		self.ul4on_decoder.reset()

	def commit(self) -> None:
		pass

	def rollback(self) -> None:
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

	def fetch_internaltemplates(self, tpl_uuid, type, control_id):
		raise NotImplementedError

	def viewtemplate_params_incremental_data(self, globals, id):
		return None

	def emailtemplate_params_incremental_data(self, globals, id):
		return None

	def app_params_incremental_data(self, app):
		return None

	def view_layout_controls_incremental_data(self, view):
		return None

	def app_child_controls_incremental_data(self, app):
		return None

	def app_menus_incremental_data(self, app):
		return None

	def app_panels_incremental_data(self, app):
		return None

	def record_attachments_incremental_data(self, id):
		return None

	def meta_data(self, *appids, records=False):
		raise NotImplementedError

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

	def geo(self, lat: T_opt_float = None, long: T_opt_float = None, info :T_opt_str = None) -> la.Geo:
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

	def seq(self) -> int:
		raise NotImplementedError

	def appseq(self, app) -> int:
		raise NotImplementedError

	def save_record(self, record) -> None:
		raise NotImplementedError

	def delete_record(self, record) -> None:
		raise NotImplementedError

	def save_control(self, control) -> bool:
		raise NotImplementedError

	def _executeaction(self, record, actionidentifier) -> None:
		raise NotImplementedError

	def file_content(self, file):
		raise NotImplementedError

	def save_app_config(self, app, recursive=True):
		raise NotImplementedError

	def save_file(self, file):
		raise NotImplementedError

	def save_parameter(self, parameter, recursive=True):
		raise NotImplementedError

	def save_internaltemplate(self, internaltemplate, recursive=True):
		raise NotImplementedError

	def save_viewtemplate_config(self, viewtemplate, recursive=True):
		raise NotImplementedError

	def delete_viewtemplate(self, viewtemplate):
		raise NotImplementedError

	def delete_internaltemplate(self, internaltemplate):
		raise NotImplementedError

	def save_datasourceconfig(self, datasource, recursive=True):
		raise NotImplementedError

	def save_datasourcechildrenconfig(self, datasourcechildrenconfig, recursive=True):
		raise NotImplementedError

	def change_user(self, lang, oldpassword, newpassword, newemail):
		raise NotImplementedError

	def fetch_librarytemplates(self, type : str):
		return la.attrdict()

	def fetch_libraryparams(self):
		return la.attrdict()

	def fetch_viewtemplate_params(self, globals):
		return la.attrdict()

	def fetch_emailtemplate_params(self, globals):
		return la.attrdict()

	def _loadglobals(self, id=None):
		globals = la.Globals(id=id)
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
	query_prefix = """
	with v_globals as (
		select
			:ide_id_user as ide_id_user /* user.id */,
			:lang as lang /* language */,
			:tpl_id_app as tpl_id_app /* app.internal_id */,
			:dat_id_detail as dat_id_detail /* record.id */
		from
			dual
	)
	""".strip()

	def __init__(self, *, connection=None, connectstring=None, connection_postgres=None, connectstring_postgres=None, uploaddir=None, ide_account=None, ide_id=None, session_id=None):
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

		self.requestid = uuid()
		if connection is not None:
			if connectstring is not None:
				raise ValueError("Specify connectstring or connection, but not both")
			self._db = connection
		elif connectstring is not None:
			self._db = connectstring
		else:
			self._db = None

		if connection_postgres is not None:
			if connectstring_postgres is not None:
				raise ValueError("Specify connectstring_postgres or connection_postgres, but not both")
			self._db_pg = connection_postgres
		elif connectstring_postgres is not None:
			self._db_pg = connectstring_postgres
		else:
			self._db_pg = None

		if uploaddir is not None:
			uploaddir = url.URL(uploaddir)
		self.uploaddir = uploaddir

		self._varchars = None
		self.urlcontext = None

		# Procedures
		self.proc_data_insert = orasql.Procedure("LIVINGAPI_PKG.DATA_INSERT")
		self.proc_data_update = orasql.Procedure("LIVINGAPI_PKG.DATA_UPDATE")
		self.proc_data_delete = orasql.Procedure("LIVINGAPI_PKG.DATA_DELETE")
		self.proc_control_update = orasql.Procedure("LIVINGAPI_PKG.CONTROL_UPDATE")
		self.proc_template_update = orasql.Procedure("LIVINGAPI_PKG.TEMPLATE_UPDATE")
		self.proc_appparameter_save = orasql.Procedure("APPPARAMETER_PKG.APPPARAMETER_SAVE_LA")
		self.proc_appparameter_delete = orasql.Procedure("APPPARAMETER_PKG.APPPARAMETER_DELETE")
		self.proc_dataaction_execute = orasql.Procedure("LIVINGAPI_PKG.DATAACTION_EXECUTE")
		self.proc_upload_upr_insert = orasql.Procedure("UPLOAD_PKG.UPLOAD_UPR_INSERT")
		self.proc_appparameter_import_waf = orasql.Procedure("APPPARAMETER_PKG.APPPARAMETER_IMPORT")
		self.proc_identity_change = orasql.Procedure("LIVINGAPI_PKG.IDENTITY_CHANGE")
		self.proc_email_send = orasql.Procedure("LIVINGAPI_PKG.EMAIL_SEND")
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
		self.func_template_seq = orasql.Function("LIVINGAPI_PKG.TEMPLATE_SEQ_BY_TPL_UUID")

		self.custom_procs = {} # For the insert/update/delete procedures of system templates
		self.internaltemplates = {} # Maps ``tpl_uuid`` to template dictionary
		self.viewtemplate_params = {} # Maps ``vt_id`` to parameter dictionary
		self.emailtemplate_params = {} # Maps ``et_id`` to parameter dictionary
		self.librarytemplates = {} # Maps ``lt_id`` to templates
		self.libraryparams = None # Maps ``lp_id`` to :class:`AppParameter`

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

		self.session_id = session_id

	def __repr__(self) -> str:
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} connectstring={self.db.connectstring()!r} ide_id={self.ide_id!r} at {id(self):#x}>"

	@property
	def db(self):
		if self._db is None:
			raise ValueError("No Oracle database connection available")
		elif isinstance(self._db, str):
			if orasql is None:
				raise ImportError(orasql_required_message)
			self._db = orasql.connect(self._db, readlobs=True)
		return self._db

	@property
	def db_pg(self):
		if self._db_pg is None:
			raise ValueError("No Postgres database connection available")
		elif isinstance(self._db_pg, str):
			if psycopg is None:
				raise ImportError(psycopg_required_message)
			self._db_pg = psycopg.connect(self._db_pg)
		return self._db_pg

	@property
	def varchars(self):
		if self._varchars is None:
			self._varchars = self.db.gettype("LL.VARCHARS")
		return self._varchars

	def cursor(self):
		return self.db.cursor(readlobs=True)

	def cursor_pg(self, row_factory=None):
		if row_factory is None:
			if rows is None:
				raise ImportError(psycopg_required_message)
			row_factory = rows.tuple_row
		return self.db_pg.cursor(row_factory=row_factory)

	def commit(self) -> None:
		if self._db is not None:
			self.db.commit()
		if self._db_pg is not None:
			self.db_pg.commit()

	def rollback(self) -> None:
		if self.db is not None:
			self.db.rollback()
		if self.db_pg is not None:
			self.db_pg.rollback()

	def reset(self) -> None:
		super().reset()
		self.proc_clear_all(self.cursor())

	def seq(self) -> int:
		c = self.cursor()
		(value, r) = self.func_seq(c)
		return int(value)

	def appseq(self, app) -> int:
		c = self.cursor()
		(value, r) = self.func_template_seq(c, app.id)
		return int(value)

	def send_mail(self, globals: la.Globals, app: la.App | None, record: la.Record | None, *, from_: T_opt_str = None, reply_to: T_opt_str = None, to: T_opt_str = None, cc: T_opt_str = None, bcc: T_opt_str = None, subject: T_opt_str = None, body_text: T_opt_str = None, body_html: T_opt_str = None, attachments: T_opt_file = None) -> None:
		c = self.cursor()
		self.proc_email_send(
			c,
			c_user=globals.user.id if globals.user is not None else None,
			c_lang=globals.lang,
			p_tpl_uuid=app.id if app is not None else None,
			p_dat_id=record.id if record is not None else None,
			p_from=from_,
			p_replyto=reply_to,
			p_to=to,
			p_cc=cc,
			p_bcc=bcc,
			p_subject=subject,
			p_bodytext=body_text,
			p_bodyhtml=body_html,
			p_upl_id_attachment=attachments.internal_id if attachments else None,
		)

	def save_app_config(self, app, recursive=True):
		# FIXME: Save the app itself
		if recursive:
			if app.internaltemplates is not None:
				for internaltemplate in app.internaltemplates.values():
					self.save_internaltemplate(internaltemplate, recursive=recursive)
			if app.viewtemplates_config is not None:
				for viewtemplate_config in app.viewtemplates_config.values():
					self.save_viewtemplate_config(viewtemplate_config, recursive=recursive)
			if app._ownparams is not None:
				for param in app._ownparams.values():
					self.save_parameter(param)

	def save_file(self, file):
		if file.internal_id is None:
			if file._content is None:
				raise ValueError(f"Can't save {file!r} without content!")
			c = self.cursor()
			r = self.proc_upload_upr_insert(
				c,
				c_user=self.ide_id,
				p_upl_orgname=file.filename,
				p_upl_size=len(file._content),
				p_upl_mimetype=file.mimetype,
				p_upl_width=file.width,
				p_upl_height=file.height,
				p_upl_latitude=file.geo.lat if file.geo is not None else None,
				p_upl_longitude=file.geo.long if file.geo is not None else None,
				p_upl_recorddate=file.recordedat,
			)

			if self.urlcontext is None:
				self.urlcontext = url.Context()
			with (self.uploaddir/r.p_upl_name).open("wb", context=self.urlcontext) as f:
				f.write(file._content)
			file.context_id = r.p_context_id
			file.id = f"{r.p_upr_path}/{r.p_upl_id}"
			file.internal_id = r.p_upl_id

	def file_content(self, file):
		with url.Context():
			u = self.uploaddir/file.storagefilename
			return u.openread().read()

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
		cursor = self.cursor_pg()

		cursor.execute(
			"""
			call internaltemplate.internaltemplate_import(
				c_user => %s,
				p_it_id => null,
				p_app_id => %s,
				p_it_identifier => %s,
				p_utv_source => %s,
				p_utv_signature => %s,
				p_utv_whitespace => %s,
				p_utv_doc => %s
			)
			""",
			[
				self.ide_id,
				internaltemplate.app.id,
				template.name,
				template.source,
				ul4c._str(template.signature) if template.signature is not None else None,
				template.whitespace,
				template.doc,
			]
		)

	def save_viewtemplate_config(self, viewtemplate, recursive=True):
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
			p_vt_permission_level=viewtemplate.permission_level.value
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
				self.save_datasourcechildrenconfig(children, recursive=recursive)

	def save_datasourcechildrenconfig(self, datasourcechildrenconfig, recursive=True):
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
			tpl_uuid=datasourcechildrenconfig.control.app.id,
			ctl_identifier=datasourcechildrenconfig.control.identifier,
		)
		ctl_id = cursor.fetchone()[0]

		# Compile and save the record filter
		vs_id_filter = self.save_vsql_source(
			cursor,
			datasourcechildrenconfig.filter,
			la.DataSourceChildrenConfig.filter.function,
			p_ds_id=datasourcechildrenconfig.datasource.id,
			p_ctl_id=ctl_id,
		)

		# Import the ``datasourcechildren`` record
		r = self.proc_datasourcechildren_import(
			cursor,
			c_user=self.ide_id,
			p_ds_id=datasourcechildrenconfig.datasource.id,
			p_dsc_identifier=datasourcechildrenconfig.identifier,
			p_ctl_id=ctl_id,
			p_ctl_id_syscontrol=None,
			p_vs_id_filter=vs_id_filter,
		)
		datasourcechildrenconfig.id = r.p_dsc_id

		if recursive:
			self._save_dataorders(
				cursor,
				datasourcechildrenconfig.orders,
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
		if self.session_id is not None:
			args["p_sessionid"] = self.session_id
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

	def meta_data(self, *appids, records=False):
		cursor = self.cursor()
		tpl_uuids = self.varchars(appids)
		cursor.execute(
			"select livingapi_pkg.metadata_ful4on(c_user=>:ide_id, p_tpl_uuids=>:tpl_uuids, p_records=>:records) from dual",
			ide_id=self.ide_id,
			tpl_uuids=tpl_uuids,
			records=int(bool(records))
		)
		dump = cursor.fetchone()[0]
		dump = dump.decode("utf-8")
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

	def file_sync_data(self, file_path, force=False):
		if not force:
			result = self.ul4on_decoder.persistent_object(la.File.ul4onname, file_path)
			if result is not None:
				return result
		c = self.cursor()
		path_parts = file_path.split("/")
		c.execute(
			"select livingapi_pkg.upload_sync_ful4on(p_upr_table=>:upr_table, p_upr_pkvalue=>:upr_pkvalue, p_upr_field=>:upr_field, p_upl_id=>:upl_id, p_force=>:force) from dual",
			upr_table=path_parts[0] if len(path_parts) > 0 else None,
			upr_pkvalue=path_parts[1] if len(path_parts) > 1 else None,
			upr_field=path_parts[2] if len(path_parts) > 2 else None,
			upl_id=path_parts[3] if len(path_parts) > 3 else None,
			force=int(force),
		)
		r = c.fetchone()
		dump = r[0].decode("utf-8")
		record = self._loaddump(dump)
		return record

	def _data(self, vt_id=None, et_id=None, vw_id=None, tpl_uuid=None, dat_id=None, dat_ids=None, ctl_identifier=None, searchtext=None, reqparams=None, mode=None, sync=False, exportmeta=False, funcname="data_ful4on"):
		paramslist = []
		if reqparams:
			for (key, value) in reqparams.items():
				if value is not None:
					if isinstance(value, (str, int)):
						paramslist.append(key)
						paramslist.append(str(value))
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
						p_sessionid => :p_sessionid,
						p_reqid => :p_reqid,
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
			p_sessionid=self.session_id,
			p_reqid=self.requestid,
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
			"select livingapi_pkg.viewtemplate_params_inc_ful4on(:p_vt_id) from dual",
			p_vt_id=id,
		)

	def emailtemplate_params_incremental_data(self, globals, id):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			globals,
			"select livingapi_pkg.emailtemplate_params_inc_ful4on(:p_et_id) from dual",
			p_et_id=id,
		)

	def app_params_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_params_inc_ful4on(:p_tpl_uuid) from dual",
			p_tpl_uuid=app.id,
		)

	def appgroup_params_incremental_data(self, appgroup):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			appgroup.globals,
			"select livingapi_pkg.appgroup_params_inc_ful4on(:p_ag_id) from dual",
			p_ag_id=appgroup.id,
		)

	def app_views_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_views_inc_ful4on(:p_tpl_uuid) from dual",
			p_tpl_uuid=app.id,
		)

	def record_attachments_incremental_data(self, record):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			record.app.globals,
			"select livingapi_pkg.record_attachments_inc_ful4on(:p_dat_id) from dual",
			p_dat_id=record.id,
		)

	def view_layout_controls_incremental_data(self, view):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			view.app.globals,
			"select livingapi_pkg.view_layoutcontrols_inc_ful4on(:p_vw_id) from dual",
			p_vw_id=view.id,
		)

	def app_child_controls_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_childcontrols_inc_ful4on(:p_tpl_uuid) from dual",
			p_tpl_uuid=app.id,
		)

	def app_menus_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_links_inc_ful4on(:c_user, :p_tpl_uuid, 'menuitem') from dual",
			c_user=self.ide_id,
			p_tpl_uuid=app.id,
		)

	def app_panels_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_links_inc_ful4on(:c_user, :p_tpl_uuid, 'panel') from dual",
			c_user=self.ide_id,
			p_tpl_uuid=app.id,
		)

	def appgroup_apps_incremental_data(self, appgroup):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			appgroup.globals,
			"select livingapi_pkg.appgroup_apps_inc_ful4on(:c_user, :p_ag_id) from dual",
			c_user=self.ide_id,
			p_ag_id=appgroup.id,
		)

	def appgroups_incremental_data(self, globals) -> dict[str, la.AppGroup]:
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			globals,
			"select livingapi_pkg.appgroups_inc_ful4on(:c_user) from dual",
			c_user=self.ide_id,
		)

	def app_viewtemplates_incremental_data(self, app):
		return self._execute_incremental_ul4on_query(
			self.cursor(),
			app.globals,
			"select livingapi_pkg.app_viewtemplates_inc_ful4on(:c_user, :p_tpl_uuid) from dual",
			c_user=self.ide_id,
			p_tpl_uuid=app.id,
		)

	def save_record(self, record, recursive=True):
		if record._deleted:
			return None

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
								if field not in controls_by_field:
									record.add_error(f"{field}: {part}")
								else:
									control = controls_by_field[field]
									identifier = control.identifier
									if app.active_view is not None and identifier not in app.active_view.controls:
										record.add_error(f"{identifier}: {part}")
									else:
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
		if not record._deleted:
			if record.id is None:
				# Just record that the record has been deleted
				# we don't need to call any db procedures
				record._deleted = True
			else:
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
				record.id = None

				if r.p_errormessage:
					raise ValueError(r.p_errormessage)

	def save_control(self, control) -> bool:
		c = self.cursor()
		required = control.__dict__["required"] # Use the "raw" value
		if required is not None:
			required = int(required)
		self.proc_control_update(
			c,
			c_user=self.ide_id,
			p_ctl_id=control.id,
			p_ctl_name=control.label,
			p_ctl_description=control.description,
			p_ctl_priority=int(control.priority),
			p_ctl_inmobilelist=int(control.in_mobile_list),
			p_ctl_intext=int(control.in_text),
			p_ctl_required=required,
		)
		return True

	def save_app(self, app) -> bool:
		if app.image is not None and app.image.internal_id is None:
			raise la.UnsavedObjectError(app.image)

		c = self.cursor()

		self.proc_template_update(
			c,
			c_user=self.ide_id,
			p_tpl_uuid=app.id,
			p_tpl_name=app.name,
			p_tpl_description=app.description,
			p_upl_id_image=None if app.image is None else app.image.internal_id,
			p_tpl_favorite=int(app.favorite),
			p_tpl_gramgen=app.gramgen,
			p_tpl_typename_nom_sin=app.typename_nom_sin,
			p_tpl_typename_gen_sin=app.typename_gen_sin,
			p_tpl_typename_dat_sin=app.typename_dat_sin,
			p_tpl_typename_acc_sin=app.typename_acc_sin,
			p_tpl_typename_nom_plu=app.typename_nom_plu,
			p_tpl_typename_gen_plu=app.typename_gen_plu,
			p_tpl_typename_dat_plu=app.typename_dat_plu,
			p_tpl_typename_acc_plu=app.typename_acc_plu,
		)
		return True

	def save_parameter(self, parameter, recursive=True):
		if not parameter._deleted:
			c = self.cursor()

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
					p_ap_value_other = f"#{parameter.value.r():02x}{parameter.value.g():02x}{parameter.value.b():02x}{parameter.value.a():02x}"
				elif parameter.type is parameter.Type.DATE:
					p_ap_value_date = parameter.value
				elif parameter.type is parameter.Type.DATETIME:
					p_ap_value_datetime = parameter.value
				elif parameter.type is parameter.Type.DATEDELTA:
					p_ap_value_other = str(parameter.value.days)
				elif parameter.type is parameter.Type.DATETIMEDELTA:
					seconds = parameter.value.seconds
					(minutes, seconds) = divmod(seconds, 60)
					(hours, minutes) = divmod(minutes, 60)
					p_ap_value_other = f"{parameter.value.days} days, {hours:02}:{minutes:02}:{seconds:02}"
				elif parameter.type is parameter.Type.MONTHDELTA:
					p_ap_value_other = str(parameter.value.months())
				elif parameter.type is parameter.Type.UPLOAD:
					if parameter.value.internal_id is None:
						raise la.UnsavedObjectError(parameter.value)
					p_upl_id = parameter.value.internal_id
				elif parameter.type is parameter.Type.APP:
					p_tpl_uuid_value = parameter.value.id
				elif parameter.type is parameter.Type.CONTROL:
					p_ctl_id = parameter.value.id

			try:
				result = self.proc_appparameter_save(
					c,
					c_user=self.ide_id,
					c_lang="de", # FIXME
					p_reqid=self.requestid,
					p_ap_id=parameter.id,
					p_tpl_uuid=parameter.app.id if parameter.app is not None else None,
					p_ag_id=parameter.appgroup.id if parameter.appgroup is not None else None,
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
						raise ValueError("\n".join(parts[1::2])) from None
					else:
						# An error message with strange formatting, use it as it is.
						raise ValueError(error.message) from None
				else:
					# Some other database exception
					raise

			if parameter.id is None:
				parameter.id = result.p_ap_id
				parameter.createdat = datetime.datetime.now()
				parameter.createdby = parameter.globals.user
			else:
				parameter.updatedat = datetime.datetime.now()
				parameter.updatedby = parameter.globals.user
			parameter._dirty = False
			parameter._new = False
			if recursive:
				if parameter.type is parameter.Type.LIST:
					for child in parameter.value:
						self.save_parameter(child, True)
				elif parameter.type is parameter.Type.DICT:
					for child in parameter.value.values():
						self.save_parameter(child, True)

	def delete_parameter(self, parameter):
		if not parameter._deleted:
			c = self.cursor()
			r = self.proc_appparameter_delete(
				c,
				c_user=self.ide_id,
				p_ap_id=parameter.id,
			)
			if parameter.parent is not None:
				if parameter.type is parameter.Type.DICT:
					parameter.parent.value.pop(parameter.identifier)
				elif parameter.type is parameter.Type.LIST:
					parameter.parent.value.remove(parameter)
			parameter._deleted = True

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

	def change_user(self, lang, oldpassword, newpassword, newemail):
		c = self.cursor()
		r = self.proc_identity_change(
			c,
			c_user=self.ide_id,
			c_lang=lang,
			p_oldpassword=oldpassword,
			p_newpassword=newpassword,
			p_newemail=newemail,
		)
		return r.p_errormessage

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

	def fetch_internaltemplates(self, tpl_uuid, type, control_id):
		key = (tpl_uuid, type, control_id)
		if key in self.internaltemplates:
			return self.internaltemplates[key]
		c = self.cursor_pg()
		if type is None:
			c.execute("select it_identifier, utv_source from internaltemplate.internaltemplate_select where app_id = %s and tmt_key is null and ctl_id is null", [tpl_uuid])
		elif control_id is None:
			c.execute("select it_identifier, utv_source from internaltemplate.internaltemplate_select where app_id = %s and tmt_key = %s and ctl_id is null", [tpl_uuid, type])
		else:
			c.execute("select it_identifier, utv_source from internaltemplate.internaltemplate_select where app_id = %s and tmt_key = %s and ctl_id = %s", [tpl_uuid, type, control_id])
		templates = la.attrdict()
		for r in c:
			(identifier, source) = r
			namespace = f"app_{tpl_uuid}.internaltemplates"
			if type:
				namespace += f".{type}"
			if control_id:
				namespace += f".{control_id}"
			template = ul4c.Template(source, name=identifier, namespace=namespace)
			templates[template.name] = template
		self.internaltemplates[key] = templates
		return templates

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

	def fetch_librarytemplates(self, type : str):
		if type not in self.librarytemplates:
			c = self.cursor_pg(row_factory=rows.tuple_row)
			if type is None:
				c.execute("select lt_identifier, utv_source from templatelibrary.librarytemplate_select where tmt_key is null")
			else:
				c.execute("select lt_identifier, utv_source from templatelibrary.librarytemplate_select where tmt_key = %s", [type])

			templates = la.attrdict()
			for r in c:
				(identifier, source) = r
				namespace = f"templatelibrary.{type}" if type else f"templatelibrary"
				template = ul4c.Template(source, name=identifier, namespace=namespace)
				templates[template.name] = template
			self.librarytemplates[type] = templates
		return self.librarytemplates[type]

	def fetch_libraryparams(self):
		if self.libraryparams is None:
			c = self.cursor_pg(row_factory=rows.tuple_row)
			c.execute("select templatelibrary.libraryparameters_ful4on()")
			r = c.fetchone()
			dump = r[0]
			# Don't reuse the decoder for the dumps from Oracle, this is an independent one
			# Note that we ignore the problem of persistent objects, since none of the
			# persistent objects in this dump are in the other dump
			dump = ul4on.loads(dump)
			if isinstance(dump, dict):
				dump = la.attrdict(dump)
			self.libraryparams = la.attrdict(dump)
		return self.libraryparams

	def count_records(self, app, filter):
		q = vsql.Query(
			f"Count records of app {app.name}",
			user=vsql.Field("user", vsql.DataType.STR, "v_globals.ide_id_user", "g.ide_id_user = {d}.ide_id", refgroup=la.User.vsqlgroup),
			r=app.vsqlfield_records("r", "g.tpl_id_app"),
			app=app.vsqlfield_app("app", "g.tpl_id_app"),
		)

		# Add CTE with the parameters that we'll pass to the query
		q.from_sql("v_globals", "g", "global variables")

		# Make sure that the table for `r` gets joined
		q.register_vsql("r")

		# Count records
		q.select_sql("count(*)", "c")

		# Apply use specified filter
		for f in filter:
			if f:
				q.where_vsql(f)

		query = f"{self.query_prefix}\n{q.sqlsource()}"

		c = self.cursor()
		c.execute(query, ide_id_user=self.ide_id, tpl_id_app=app.internal_id, dat_id_detail=None, lang=app.globals.lang)
		return c.fetchone()[0]

	def delete_records(self, app, filter):
		q = vsql.Query(
			f"Delete records of app {app.name}",
			user=vsql.Field("user", vsql.DataType.STR, "v_globals.ide_id_user", "g.ide_id_user = {d}.ide_id", refgroup=la.User.vsqlgroup),
			r=app.vsqlfield_records("r", "g.tpl_id_app"),
			app=app.vsqlfield_app("app", "g.tpl_id_app"),
		)

		# Add CTE with the parameters that we'll pass to the query
		q.from_sql("v_globals", "g", "global variables")

		# Make sure that the table for `r` gets joined
		q.register_vsql("r")

		# We need the pk of the record to be able to delete it.
		# (Note that this makes the `register_vsql` call unnecessary.)
		q.select_vsql("r.id", "dat_id")

		# Apply use specified filter
		for f in filter:
			if f:
				q.where_vsql(f)

		c = self.cursor()

		dat_ids = c.var(self.varchars)

		query = f"""
			declare
				v_ide_id_user identity.ide_id%type := :ide_id_user;
				v_lang varchar2(30) := :lang;
				v_reqid varchar2(30) := :req_id;
				v_tpl_uuid template.tpl_uuid%type := :tpl_uuid;
				v_tpl_id template.tpl_id%type := :tpl_id;
				v_deleted varchars := varchars();
				v_errormessage varchar2(4000);
			begin
				for row in (
					with v_globals as (
						select
							v_ide_id_user as ide_id_user /* user.id */,
							v_lang as lang /* language */,
							v_tpl_id as tpl_id_app /* app.internal_id */,
							null as dat_id_detail /* record.id */
						from
							dual
					)
					{q.sqlsource()}
				) loop
					livingapi_pkg.data_delete(
						c_user => v_ide_id_user,
						p_reqid => null,
						p_errormessage => v_errormessage,
						p_dat_id => row.dat_id,
						p_mode => 'livingapi'
					);
					varchars_pkg.append(v_deleted, row.dat_id);
				end loop;

				:dat_ids := v_deleted;
			end;
		"""

		c.execute(
			query,
			ide_id_user=self.ide_id,
			req_id=self.requestid,
			tpl_uuid=app.id,
			tpl_id=app.internal_id,
			lang=app.globals.lang,
			dat_ids=dat_ids,
		)

		dat_ids = dat_ids.getvalue().aslist()
		for dat_id in dat_ids:
			record = self.ul4on_decoder.persistent_object("de.livinglogic.livingapi.record", dat_id)
			if record is not None:
				record._deleted = True
				record.id = None
		return len(dat_ids)

	def fetch_records(self, app, filter:list[str], sort:list[str], offset=0, limit=None):
		q = vsql.Query(
			f"Fetch records of app {app.name} ({app.id})",
			user=vsql.Field("user", vsql.DataType.STR, "v_globals.ide_id_user", "g.ide_id_user = {d}.ide_id", refgroup=la.User.vsqlgroup),
			r=app.vsqlfield_records("r", "g.tpl_id_app"),
			app=app.vsqlfield_app("app", "g.tpl_id_app"),
		)

		# Add CTE with the parameters that we'll pass to the query
		q.from_sql("v_globals", "g", "global variables")

		# Make sure that the table for `r` gets joined
		q.register_vsql("r")

		# Add all the fields that we need
		q.select_vsql("r.id", "dat_id")
		q.select_vsql("r.app_internal_id", "tpl_id")
		q.select_vsql("r.app", "tpl_uuid")
		q.select_vsql("r.createdat", "dat_cdate")
		q.select_vsql("r.createdby", "dat_cname")
		q.select_vsql("r.updatedat", "dat_udate")
		q.select_vsql("r.updatedby", "dat_uname")
		q.select_vsql("r.updatecount", "dat_updatecount")
		for control in app.controls.values():
			q.select_vsql(f"r.v_{control.identifier}", control.fieldname)

		# Apply use specified filter
		for f in filter:
			if f:
				q.where_vsql(f)

		# Add offset specified by the user
		if offset is not None and offset > 0:
			q.offset(offset)

		# Add limit specified by the user
		if limit is not None:
			q.limit(limit)

		# Add sort expressions specified by the user
		for s in sort:
			direction = None
			nulls = None
			while True:
				if direction is None and s.endswith(" asc"):
					direction = "asc"
					s = s[:-4].strip()
				elif direction is None and s.endswith(" desc"):
					direction = "desc"
					s = s[:-5].strip()
				elif nulls is None and s.endswith(" nulls last"):
					nulls = "last"
					s = s[:-11].strip()
				elif nulls is None and s.endswith(" nulls first"):
					nulls = "first"
					s = s[:-12].strip()
				else:
					break
			q.orderby_vsql(s, direction=direction, nulls=nulls)

		c = self.cursor()

		dat_ids = c.var(self.varchars)

		field_statements = []
		for control in app.controls.values():
			field_statements.append(f"\t\t\t{control.sql_fetch_statement()}\n")

		query = f"""
			declare
				v_ide_id_user identity.ide_id%type := :ide_id_user;
				v_lang varchar2(30) := :lang;
				v_reqid varchar2(30) := :req_id;
				v_tpl_uuid template.tpl_uuid%type := :tpl_uuid;
				v_tpl_id template.tpl_id%type := :tpl_id;
				v_result blob;
			begin
				livingapi_pkg.records_inc_init;

				for row in (
					with v_globals as (
						select
							v_ide_id_user as ide_id_user /* user.id */,
							v_lang as lang /* language */,
							v_tpl_id as tpl_id_app /* app.internal_id */,
							null as dat_id_detail /* record.id */
						from
							dual
					)
					{q.sqlsource()}
				) loop
					if livingapi_pkg.records_inc_begin_record(
						row.dat_id,
						row.tpl_id,
						row.dat_cdate,
						row.dat_cname,
						row.dat_udate,
						row.dat_uname,
						row.dat_updatecount
					) then
						{''.join(field_statements)}
						livingapi_pkg.records_inc_end_record;
					end if;
				end loop;
				livingapi_pkg.records_inc_finish(v_result);
				:dump := v_result;
			end;
		"""

		dump = c.var(orasql.BLOB)

		args = dict(
			ide_id_user=self.ide_id,
			lang=app.globals.lang,
			req_id=self.requestid,
			tpl_uuid=app.id,
			tpl_id=app.internal_id,
		)
		c.execute(
			query,
			dump=dump,
			**args
		)

		dump = dump.getvalue()
		if dump is None:
			self._reinitialize_livingapi_db(c, app.globals)
			dump = c.var(orasql.BLOB)
			c.execute(query, dump=dump, **args)
			dump = dump.getvalue()
		dump = dump.read().decode("utf-8")
		return self.ul4on_decoder.loads(dump)

	def vsqlquery4fetch(self, app, filter, fields, record):
		q = vsql.Query(
			f"Fetch records of app {app.name} ({app.id})",
			user=vsql.Field("user", vsql.DataType.STR, "v_globals.ide_id_user", "g.ide_id_user = {d}.ide_id", refgroup=la.User.vsqlgroup),
			r=app.vsqlfield_records("r", vsql.sql(app.internal_id)),
			app=app.vsqlfield_app("app", vsql.sql(app.globals.app.internal_id)),
			record=record.app.vsqlfield_records("record", "g.dat_id_detail") if record is not None else None,
		)

		# Add CTE with the parameters that we'll pass to the query
		q.from_sql("v_globals", "g", "global variables")

		# Force the table for `r` to be joined, even if we never reference it
		table_alias = q.register_vsql("r")

		# Add the fields we need
		q.select_vsql("r.id", "dat_id")
		q.select_vsql("r.app_internal_id", "tpl_id")
		q.select_vsql("r.app", "tpl_uuid")
		q.select_vsql("r.createdat", "dat_cdate")
		q.select_vsql("r.createdby", "dat_cname")
		q.select_vsql("r.updatedat", "dat_udate")
		q.select_vsql("r.updatedby", "dat_uname")
		q.select_vsql("r.updatecount", "dat_updatecount")

		for (fieldname, field) in fields.items():
			q.select_sql(field.fieldsql.replace("{a}", table_alias), fieldname, None)

		# Add filter conditions
		for f in filter:
			if f:
				q.where_vsql(f)
		return q

	def vsqlquery4count(self, app, filter, record):
		q = vsql.Query(
			f"Fetch records of app {app.name} ({app.id})",
			user=vsql.Field("user", vsql.DataType.STR, "v_globals.ide_id_user", "g.ide_id_user = {d}.ide_id", refgroup=la.User.vsqlgroup),
			r=app.vsqlfield_records("r", vsql.sql(app.internal_id)),
			app=app.vsqlfield_app("app", vsql.sql(app.globals.app.internal_id)),
			record=record.app.vsqlfield_records("record", "g.dat_id_detail") if record is not None else None,
		)

		# Add CTE with the parameters that we'll pass to the query
		q.from_sql("v_globals", "g", "global variables")

		# Force the table for `r` to be joined, even if we never reference it
		table_alias = q.register_vsql("r")

		# Count records
		q.select_sql("count(*)", "c", None)

		# Add filter conditions
		for f in filter:
			if f:
				q.where_vsql(f)
		return q

	def fetch_records_from_apps(self, globals:la.Globals, filter:dict[la.App, list[str]], sort:list[str], offset:int|None=0, limit:int|None=None, record:la.Record | None=None) -> dict[str, la.Record]:
		if not filter:
			return {}

		record_app = record.app if record is not None else None

		# Collect all fields from all apps
		all_fields = {control.fieldname: control.vsqlfield for app in filter for control in app.controls.values()}

		inner_q = "\n\n\t\t\t\t\tunion all\n\n".join(
			self.vsqlquery4fetch(app, f, all_fields, record).sqlsource()
			for (app, f) in filter.items()
		)
		inner_q = f"(\n{inner_q}\t\t\t\t)"

		q = vsql.Query(
			"Fetch records from multiple apps",
			user=vsql.Field(
				"user",
				vsql.DataType.STR,
				"v_globals.ide_id_user",
				"g.ide_id_user = {d}.ide_id",
				refgroup=la.User.vsqlgroup
			),
			r=vsql.Field(
				"r",
				vsql.DataType.STR,
				"1 = 1",
				"2 = 2",
				la.App.vsqlgroup_records_common(inner_q),
			),
			app=globals.app.vsqlfield_app("r", vsql.sql(globals.app.internal_id)),
			record=record.app.vsqlfield_records("record", "g.dat_id_detail") if record is not None else None,
		)

		# Add CTE with the parameters that we'll pass to the query
		q.from_sql("v_globals", "g", "global variables")

		# Add the fields we need
		q.select_vsql("r.id", "dat_id")
		q.select_vsql("r.app_internal_id", "tpl_id")
		q.select_vsql("r.app", "tpl_uuid")
		q.select_vsql("r.createdat", "dat_cdate")
		q.select_vsql("r.createdby", "dat_cname")
		q.select_vsql("r.updatedat", "dat_udate")
		q.select_vsql("r.updatedby", "dat_uname")
		q.select_vsql("r.updatecount", "dat_updatecount")
		for (fieldname, field) in all_fields.items():
			# We using the field name here since field aliases for multiple lookups/applookups
			# have been put into the inner queries
			q.select_sql(f"t2.{fieldname}", fieldname, None)

		# Add sort expressions specified by the user
		for s in sort:
			direction = None
			nulls = None
			while True:
				if direction is None and s.endswith(" asc"):
					direction = "asc"
					s = s[:-4].strip()
				elif direction is None and s.endswith(" desc"):
					direction = "desc"
					s = s[:-5].strip()
				elif nulls is None and s.endswith(" nulls last"):
					nulls = "last"
					s = s[:-11].strip()
				elif nulls is None and s.endswith(" nulls first"):
					nulls = "first"
					s = s[:-12].strip()
				else:
					break
				q.orderby_vsql(s, direction=direction, nulls=nulls)

		# Add offset specified by the user
		if offset is not None and offset > 0:
			q.offset(offset)

		# Add limit specified by the user
		if limit is not None:
			q.limit(limit)

		field_sql = []
		for (i, app) in enumerate(filter):
			field_sql.append(f"\t\t\t{'elsif' if i else 'if'} row.tpl_id = {app.internal_id} then\n")
			for control in app.controls.values():
				field_sql.append(f"\t\t\t\t\t{control.sql_fetch_statement()}\n")
		field_sql.append("\t\t\t\tend if;\n")

		sql = f"""
		declare
			v_ide_id_user identity.ide_id%type := :ide_id_user;
			v_lang varchar2(30) := :lang;
			v_reqid varchar2(30) := :req_id;
			v_tpl_uuid varchar2(30) := null;
			v_dat_id_detail varchar2(30) := :dat_id_detail;
			v_result blob;
		begin
			-- Do nothing (and thus return `null`) if the UL4ON machinery
			-- hasn't been initialized yet,
			-- The client must then call `init` and pass `p_ul4onbackrefs`.
			if livingapi_pkg.livingapi_is_initialized then
				livingapi_pkg.records_inc_init;

				for row in (
					with v_globals as (
						select
							v_ide_id_user as ide_id_user /* user.id */,
							v_lang as lang, /* language */
							v_dat_id_detail as dat_id_detail /* detail record */
						from
							dual
					)
					{q.sqlsource()}
				) loop
					if livingapi_pkg.records_inc_begin_record(
						row.dat_id,
						row.tpl_id,
						row.dat_cdate,
						row.dat_cname,
						row.dat_udate,
						row.dat_uname,
						row.dat_updatecount
					) then
						{''.join(field_sql)}
						livingapi_pkg.records_inc_end_record;
					end if;
				end loop;
				livingapi_pkg.records_inc_finish(v_result);
			end if;
			:dump := v_result;
		end;
		"""

		c = self.cursor()

		dump = c.var(orasql.BLOB)

		c.execute(
			sql,
			ide_id_user=self.ide_id,
			lang=globals.lang,
			req_id=self.requestid,
			dat_id_detail=record.id if record is not None else None,
			dump=dump,
		)

		dump = dump.getvalue().read().decode("utf-8")
		return self.ul4on_decoder.loads(dump)

	def count_records_from_apps(self, globals:la.Globals, filter:dict[la.App, list[str]], record:la.Record | None=None) -> int:
		if not filter:
			return 0

		inner_sql = "\n\n\tunion all\n\n".join(
			self.vsqlquery4count(app, f, record).sqlsource()
			for (app, f) in filter.items()
		)

		sql = f"""
		with v_globals as (
			select
				:ide_id_user as ide_id_user /* user.id */,
				:lang as lang, /* language */
				:req_id as v_reqid, /* request id */
				:dat_id_detail as dat_id_detail /* record.id */
			from
				dual
		)
		select sum(c) from (
			{inner_sql}
		)
		"""

		c = self.cursor()

		dump = c.var(orasql.BLOB)

		c.execute(
			sql,
			ide_id_user=self.ide_id,
			lang=globals.lang,
			req_id=self.requestid,
			dat_id_detail=record.id if record is not None else None,
		)
		return c.fetchone()[0]

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

	def __repr__(self) -> str:
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
		if file.internal_id is None:
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
			file.context_id = result["url"].split("/")[2]
			file.id = result["upr_id"] + "/" + result["upl_id"]
			file.width = result["width"]
			file.height = result["height"]
			file.size = result["size"]
			file.mimetype = result["mimetype"]
			file.internal_id = result["upl_id"]

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

	def _loadcontrols(self, app):
		path = self.basepath/f"{app.name} ({app.id})/index.json"
		if path.exists():
			dump = json.loads(path.read_text(encoding="utf-8"))

	def save_app_config(self, app, recursive=True):
		configcontrols = self._controls_as_json(app)
		path = self.basepath/"index.json"
		self._save(path, json.dumps(configcontrols, indent="\t", ensure_ascii=False))
		if recursive:
			if app.internaltemplates is not None:
				for internaltemplate in app.internaltemplates.values():
					self.save_internaltemplate(internaltemplate, recursive=recursive)
			if app.viewtemplates_config is not None:
				for viewtemplate_config in app.viewtemplates_config.values():
					self.save_viewtemplate_config(viewtemplate_config, recursive=recursive)
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

	def _controls_as_json(self, app):
		configcontrols = {}
		for control in app.controls.values():
			# We don't have to include the identifier as this will be used as the key
			configcontrol = {
				"type": f"{control.type}/{control.subtype}" if control.subtype else control.type,
			}
			configcontrols[control.identifier] = configcontrol
		return configcontrols

	def _datasource_as_json(self, datasource):
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
		configorders = self._dataorders_as_json(datasource.orders)
		if configorders:
			configdatasource["order"] = configorders
		configdatasourcechildren = {}
		for datasourcechildren in datasource.children.values():
			configdatasourcechildren[datasourcechildren.identifier] = self._datasourcechildren_as_json(datasourcechildren)
		if configdatasourcechildren:
			configdatasource["children"] = configdatasourcechildren
		return configdatasource

	def _datasourcechildren_as_json(self, datasourcechildren):
		configdatasourcechildren = {}
		self._dumpattr(configdatasourcechildren, datasourcechildren, "identifier")
		configdatasourcechildren["app"] = datasourcechildren.control.app.fullname
		configdatasourcechildren["control"] = datasourcechildren.control.identifier
		self._dumpattr(configdatasourcechildren, datasourcechildren, "filter")
		configorders = self._dataorders_as_json(datasourcechildren.orders)
		if configorders:
			configdatasourcechildren["order"] = configorders
		return configdatasourcechildren

	def _dataorders_as_json(self, orders):
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

	def save_viewtemplate_config(self, viewtemplate, recursive=True):
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
				configalldatasources[datasource.identifier] = self._datasource_as_json(datasource)
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
		config = self._dataaction_as_json(dataaction)
		self._save(path, json.dumps(config, indent="\t", ensure_ascii=False))

	def _dataaction_as_json(self, dataaction):
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

		configcommands = [self._dataactioncommand_as_json(dac) for dac in dataaction.commands]
		if configcommands:
			configdataaction["commands"] = configcommands
		# configdatasourcechildren = {}
		# for datasourcechildren in datasource.children.values():
		# 	configdatasourcechildren[datasourcechildren.identifier] = self._datasourcechildren_as_json(datasourcechildren)
		# if configdatasourcechildren:
		# 	configdatasource["children"] = configdatasourcechildren
		return configdataaction

	def _dataactioncommand_as_json(self, dataactioncommand):
		configdataactioncommand = {}
		type = dataactioncommand.ul4onname.rpartition("_")[-1]
		configdataactioncommand["type"] = type
		self._dumpattr(configdataactioncommand, dataactioncommand, "condition")
		configdetails = [
			self._dataactiondetail_as_json(d)
			for d in dataactioncommand.details
			if d.type
		]
		if configdetails:
			configdataactioncommand["details"] = configdetails
		if isinstance(dataactioncommand, la.DataActionCommandWithIdentifier):
			configdataactioncommand["app"] = dataactioncommand.app.fullname
			self._dumpattr(configdataactioncommand, dataactioncommand, "identifier")
			configchildren = [
				self._dataactioncommand_as_json(c)
				for c in dataactioncommand.children
			]
			if configchildren:
				dataactioncommand["children"] = configchildren

		return configdataactioncommand

	def _dataactiondetail_as_json(self, dataactiondetail):
		configdataactiondetail = {}
		configdataactiondetail["control"] = dataactiondetail.control.identifier
		self._dumpattr(configdataactiondetail, dataactiondetail, "type")
		self._dumpattr(configdataactiondetail, dataactiondetail, "value")
		self._dumpattr(configdataactiondetail, dataactiondetail, "expression")
		self._dumpattr(configdataactiondetail, dataactiondetail, "formmode")
		return configdataactiondetail
