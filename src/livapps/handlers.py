#!/usr/bin/env python
# -*- coding: utf-8 -*-
# cython: language_level=3, always_allow_keywords=True

## Copyright 2016-2019 by LivingLogic AG, Bayreuth/Germany
##
## All Rights Reserved

import os, io, datetime, pathlib, itertools, json, mimetypes, operator
import typing as T

import requests, requests.exceptions # This requires :mod:`request`, which you can install with ``pip install requests``

from ll import misc, url, ul4c, ul4on # This requires the :mod:`ll` package, which you can install with ``pip install ll-xist``

try:
	from ll import orasql
except ImportError:
	orasql = None

import livapps as la

from livapps import vsql


__docformat__ = "reStructuredText"

__all__ = ["Handler", "HTTPHandler", "DBHandler", "FileHandler"]

###
### Types
###

if T.TYPE_CHECKING:
	OptStr = T.Optional[str]
	OptInt = T.Optional[int]
	OptFloat = T.Optional[float]
	OptBool = T.Optional[bool]
	OptDatetime = T.Optional[datetime.datetime]
	PK = str
	OptPK = T.Optional[PK]
	ReqParams = T.Dict[str, T.Union[None, str, T.List[str]]]


###
### Utility functions and classes
###

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

	This can either be direct communication via a database interface
	(see :class:`DBHandler`) or communication via an HTTP interface
	(see :class:`HTTPHandler`).
	"""

	def __init__(self):
		# type: () -> None
		self.globals = None

	def get(self, *path, **params):
		# type: (*str, **T.Union[str, T.List[str]]) -> T.Any
		pass

	def file(self, source):
		# type: (T.Union[str, os.PathLike, pathlib.Path, url.URL, T.IO[bytes]]) -> la.File
		path = None # type: OptStr
		stream = None # type: T.Optional[T.IO[bytes]]
		mimetype = None # type: OptStr
		if isinstance(source, pathlib.Path):
			content = source.read_bytes()
			filename = source.name
			path = str(source.resolve())
		if isinstance(source, str):
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
				stream = io.BytesIO(content)
		else:
			content = source.read()
			if source.name:
				filename = os.path.basename(source.name)
			else:
				filename = "Dummy"
			stream = source
		if mimetype is None:
			mimetype = mimetypes.guess_type(filename, strict=False)[0]
		file = la.File(filename=filename, mimetype=mimetype)
		if file.mimetype.startswith("image/"):
			from PIL import Image # This requires :mod:`Pillow`, which you can install with ``pip install pillow``
			if stream:
				stream.seek(0)
			with Image.open(path or stream) as img:
				file.width = img.size[0]
				file.height = img.size[1]
		file._content = content
		file.handler = self
		return file

	def _geofrominfo(self, info):
		# type: (str) -> T.Optional[la.Geo]
		import geocoder # This requires the :mod:`geocoder` module, install with ``pip install geocoder`
		for provider in (geocoder.google, geocoder.osm):
			result = provider(info, language="de")
			if not result.error and result.lat and result.lng and result.address:
				return la.Geo(result.lat, result.lng, result.address)
		return None

	def _geofromlatlong(self, lat, long):
		# type: (float, float) -> T.Optional[la.Geo]
		import geocoder # This requires the :mod:`geocoder` module, install with ``pip install geocoder`
		for provider in (geocoder.google, geocoder.osm):
			result = provider([lat, long], method="reverse", language="de")
			if not result.error and result.lat and result.lng and result.address:
				return la.Geo(result.lat, result.lng, result.address)
		return None

	def geo(self, lat=None, long=None, info=None):
		# overload: (str) -> la.Geo
		# overload: (float, float) -> la.Geo
		# Get coordinates from description (passed via keyword ``info``)
		if info is not None and lat is None and long is None:
			return self._geofrominfo(info)
		# Get coordinates from description (passed positionally as ``lat``)
		elif lat is not None and long is None and info is None:
			return self._geofrominfo(lat)
		# Get description from coordinates
		elif lat is not None and long is not None and info is None:
			return self._geofromlatlong(lat, long)
		else:
			raise TypeError("geo() requires either (lat, long) arguments or a (info) argument")

	def save_record(self, record):
		# type: (la.Record) -> None
		raise NotImplementedError

	def _delete(self, record):
		# type: (la.Record) -> None
		raise NotImplementedError

	def _executeaction(self, record, actionidentifier):
		# type: (la.Record, str) -> None
		raise NotImplementedError

	def file_content(self, file):
		# type: (la.File) -> bytes
		raise NotImplementedError

	def save_file(self, file):
		# type: (la.File) -> None
		raise NotImplementedError

	def save_internaltemplate(self, internaltemplate, recursive=True):
		# type: (la.InternalTemplate, bool) -> None
		raise NotImplementedError

	def save_viewtemplate(self, viewtemplate, recursive=True):
		# type: (la.ViewTemplate, bool) -> None
		raise NotImplementedError

	def save_datasourceconfig(self, datasourceconfig, recursive=True):
		# type: (la.DataSourceConfig, bool) -> None
		raise NotImplementedError

	def save_datasourcechildrenconfig(self, datasourcechildrenconfig, recursive=True):
		# type: (la.DataSourceChildrenConfig, bool) -> None
		raise NotImplementedError

	def _loadfile(self):
		# type: () -> la.File
		file = la.File()
		file.handler = self
		return file

	def _loadglobals(self):
		# type: () -> la.Globals
		globals = la.Globals()
		globals.handler = self
		return globals

	def _loaddump(self, dump):
		# type: (str) -> T.Mapping[str, T.Any]
		registry = {
			"de.livingapps.appdd.file": self._loadfile,
			"de.livinglogic.livingapi.file": self._loadfile,
			"de.livingapps.appdd.globals": self._loadglobals,
			"de.livinglogic.livingapi.globals": self._loadglobals,
		}
		dump = ul4on.loads(dump, registry)
		dump = la.attrdict(dump)
		if "datasources" in dump:
			dump.datasources = la.attrdict(dump.datasources)
		return dump


class DBHandler(Handler):
	def __init__(self, connectstring, uploaddirectory, account):
		# type: (str, T.Union[str, url.URL], OptStr) -> None
		super().__init__()
		if orasql is None:
			raise ImportError("ll.orasql required")
		self.db = orasql.connect(connectstring, readlobs=True)
		self.uploaddirectory = url.URL(uploaddirectory)
		self.varchars = self.db.gettype("LL.VARCHARS")
		self.urlcontext = None

		# Procedures
		self.proc_data_insert = orasql.Procedure("LIVINGAPI_PKG.DATA_INSERT")
		self.proc_data_update = orasql.Procedure("LIVINGAPI_PKG.DATA_UPDATE")
		self.proc_data_delete = orasql.Procedure("LIVINGAPI_PKG.DATA_DELETE")
		self.proc_dataaction_execute = orasql.Procedure("LIVINGAPI_PKG.DATAACTION_EXECUTE")
		self.proc_upload_insert = orasql.Procedure("UPLOAD_PKG.UPLOAD_INSERT")
		self.proc_internaltemplate_import = orasql.Procedure("INTERNALTEMPLATE_PKG.INTERNALTEMPLATE_IMPORT")
		self.proc_viewtemplate_import = orasql.Procedure("VIEWTEMPLATE_PKG.VIEWTEMPLATE_IMPORT")
		self.proc_datasource_import = orasql.Procedure("DATASOURCE_PKG.DATASOURCE_IMPORT")
		self.proc_datasourcechildren_import = orasql.Procedure("DATASOURCE_PKG.DATASOURCECHILDREN_IMPORT")
		self.proc_dataorder_import = orasql.Procedure("DATAMANAGE_PKG.DATAORDER_IMPORT")
		self.proc_dataorder_delete = orasql.Procedure("DATAMANAGE_PKG.DATAORDER_DELETE")
		self.proc_vsqlsource_insert = orasql.Procedure("VSQL_PKG.VSQLSOURCE_INSERT")
		self.proc_vsql_insert = orasql.Procedure("VSQL_PKG.VSQL_INSERT")

		self.custom_procs = {} # type: T.Dict[str, orasql.Procedure]

		if account is None:
			self.ide_id = None
		else:
			c = self.cursor()
			c.execute("select ide_id from identity where ide_account = :account", account=account)
			r = c.fetchone()
			if r is None:
				raise ValueError(f"no user {account!r}")
			self.ide_id = r.ide_id

	def __repr__(self):
		# type: () -> str
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} connectstring={self.db.connectstring()!r} at {id(self):#x}>"

	def cursor(self):
		# type: () -> orasql.Cursor
		return self.db.cursor()

	def commit(self):
		# type: () -> None
		self.db.commit()

	def save_file(self, file):
		# type: (la.File) -> None
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
			with (self.uploaddirectory/r.p_upl_name).open("wb", context=self.urlcontext) as f:
				f.write(file._content)
			file.internalid = r.p_upl_id

	def file_content(self, file):
		# type: (la.File) -> bytes
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
			u = self.uploaddirectory/r.upl_name
			return u.openread().read()

	def save_vsql(self, cursor, source, function, datatype=None, **queryargs):
		# type: (orasql.Cursor, OptStr, str, OptStr, T.Any) -> OptPK
		return vsql.compile_and_save(self, cursor, source, datatype, function, **queryargs)

	def save_internaltemplate(self, internaltemplate, recursive=True):
		# type: (la.InternalTemplate, bool) -> None
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
		# type: (la.ViewTemplate, bool) -> None
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
			p_vt_defaultlist=int(viewtemplate.type is la.ViewTemplate.Type.LISTDEFAULT) if viewtemplate.type in {la.ViewTemplate.Type.LIST, la.ViewTemplate.Type.LISTDEFAULT} else None,
			p_vt_resultpage=int(viewtemplate.type is la.ViewTemplate.Type.DETAILRESULT) if viewtemplate.type is {la.ViewTemplate.Type.DETAIL, la.ViewTemplate.Type.DETAILRESULT} else None,
			p_vt_permission_level=viewtemplate.permission.value
		)
		viewtemplate.id = r.p_vt_id
		if recursive:
			for datasource in viewtemplate.datasources.values():
				datasource.save(self, recursive=recursive)

	def save_datasourceconfig(self, datasourceconfig, recursive=True):
		# type: (la.DataSourceConfig, bool) -> None
		cursor = self.cursor()

		# Compile and save the app filter
		vs_id_appfilter = self.save_vsql(
			cursor,
			datasourceconfig.appfilter,
			la.DataSourceConfig.appfilter.function,
			p_vt_id=datasourceconfig.parent.id,
			p_tpl_uuid_a=None,
		)

		# Compile and save the record filter
		vs_id_recordfilter = self.save_vsql(
			cursor,
			datasourceconfig.recordfilter,
			la.DataSourceConfig.recordfilter.function,
			p_vt_id=datasourceconfig.parent.id,
			p_tpl_uuid_r=datasourceconfig.app.id if datasourceconfig.app is not None else None,
		)

		# FIXME: Support for system apps?
		r = self.proc_datasource_import(
			cursor,
			c_user=self.ide_id,
			p_vt_id=datasourceconfig.parent.id,
			p_tpl_uuid=datasourceconfig.app.id if datasourceconfig.app is not None else None,
			p_dmv_id=None,
			p_tpl_uuid_systemplate=None,
			p_ds_includetemplates=int(datasourceconfig.includetemplates),
			p_ds_includerecords=int(datasourceconfig.includerecords),
			p_ds_includecontrols=int(datasourceconfig.includecontrols),
			p_ds_includecount=int(datasourceconfig.includecount),
			p_ds_includecloned=int(datasourceconfig.includecloned),
			p_ds_identifier=datasourceconfig.identifier,
			p_ds_includepermissions=int(datasourceconfig.includepermissions),
			p_ds_includeattachments=int(datasourceconfig.includeattachments),
			p_ds_includecategories=int(datasourceconfig.includecategories),
			p_ds_includeparams=int(datasourceconfig.includeparams),
			p_ds_includeviews=int(datasourceconfig.includeviews),
			p_ds_recordpermission=int(datasourceconfig.recordpermission),
			p_vs_id_appfilter=vs_id_appfilter,
			p_vs_id_recordfilter=vs_id_recordfilter,
		)
		datasourceconfig.id = r.p_ds_id

		if recursive:
			self._save_dataorderconfigs(
				cursor,
				datasourceconfig.orders,
				"VSQLFIELD_PKG.DS_ORDER_FUL4ON",
				ds_id=r.p_ds_id,
			)
			for children in datasourceconfig.children.values():
				children.save(self, recursive=recursive)

	def save_datasourcechildrenconfig(self, datasourcechildrenconfig, recursive=True):
		# type: (la.DataSourceChildrenConfig, bool) -> None
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
		vs_id_filter = self.save_vsql(
			cursor,
			datasourcechildrenconfig.filter,
			la.DataSourceChildrenConfig.filter,
			p_ds_id=datasourcechildrenconfig.datasourceconfig.id,
			p_ctl_id=ctl_id,
		)

		# Import the ``datasourcechildren`` record
		r = self.proc_datasourcechildren_import(
			cursor,
			c_user=self.ide_id,
			p_ds_id=datasourcechildrenconfig.datasourceconfig.id,
			p_dsc_identifier=datasourcechildrenconfig.identifier,
			p_ctl_id=ctl_id,
			p_ctl_id_syscontrol=None,
			p_vs_id_filter=vs_id_filter,
		)
		datasourcechildrenconfig.id = r.p_dsc_id

		if recursive:
			self._save_dataorderconfigs(
				cursor,
				datasourcechildrenconfig.orders,
				"VSQLFIELD_PKG.DSC_ORDER_FUL4ON",
				dsc_id=r.p_dsc_id,
			)

	def _save_dataorderconfigs(self, cursor, orders, function, **kwargs):
		# type: (orasql.Cursor, T.List[la.DataOrderConfig], str, **str) -> None
		queryargs = " and ".join(f"{k}=:{k}" for k in kwargs)
		procargs = {"p_" + k: v for (k, v) in kwargs.items()}
		query = f"select do_id, do_order from dataorder where {queryargs} order by do_order"
		cursor.execute(query, **kwargs)
		old_records = [(r2.do_id, r2.do_order) for r2 in cursor]
		last_order = 0
		for (old_record, dataorderconfig) in itertools.zip_longest(old_records, orders):
			if old_record is not None:
				(do_id, do_order) = old_record
			else:
				(do_id, do_order) = (None, last_order + 10)
			if dataorderconfig is not None:
				# Compile and save the order expression
				vs_id_expression = self.save_vsql(
					cursor,
					dataorderconfig.expression,
					function,
					**procargs,
				)

				# Import the ``dataorder`` record
				r = self.proc_dataorder_import(
					cursor,
					c_user=self.ide_id,
					p_vs_id_expression=vs_id_expression,
					p_do_direction=dataorderconfig.direction.value,
					p_do_nulls=dataorderconfig.nulls.value,
					p_do_order=do_order,
					**procargs,
				)
				dataorderconfig.id = r.p_do_id
				last_order = do_order
			else:
				self.proc_dataorder_delete(cursor, c_user=self.ide_id, p_do_id=do_id)

	def getmeta(self, *appids):
		# type: (*str) -> T.Mapping[str, T.Any]
		cursor = self.cursor()

		tpl_uuids = self.varchars(appids)
		cursor.execute(
			"select livingapi_pkg.metadata_ful4on(:ide_id, :tpl_uuids) from dual",
			ide_id=self.ide_id,
			tpl_uuids=tpl_uuids,
		)
		r = cursor.fetchone()
		dump = r[0].decode("utf-8")
		dump = self._loaddump(dump)
		return dump

	def get(self, *path, **params):
		# type: (*str, **T.Union[str, T.List[str]]) -> T.Mapping[str, T.Any]
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
				"select vt_id from viewtemplate where tpl_id = :tpl_id and vt_identifier = : identifier",
				tpl_id=tpl_id,
				identifier=template,
			)
		else:
			template = None
			c.execute(
				"select vt_id from viewtemplate where tpl_id = :tpl_id and vt_defaultlist != 0",
				tpl_id=tpl_id,
			)
		r = c.fetchone()
		if r is None:
			if template is None:
				raise ValueError(f"no default template for app {appid!r}")
			else:
				raise ValueError(f"no template named {template!r} for app {appid!r}")
		vt_id = r.vt_id
		reqparams = []
		for (key, value) in params.items():
			if value is not None:
				if isinstance(value, str):
					reqparams.append(key)
					reqparams.append(value)
				elif isinstance(value, list):
					for subvalue in value:
						reqparams.append(key)
						reqparams.append(subvalue)
		reqparams = self.varchars(reqparams)
		c.execute(
			"select livingapi_pkg.viewtemplatedata_ful4on(:ide_id, :vt_id, :dat_id, :reqparams) from dual",
			ide_id=self.ide_id,
			vt_id=vt_id,
			dat_id=datid,
			reqparams=reqparams,
		)
		r = c.fetchone()
		dump = r[0].decode("utf-8")
		dump = self._loaddump(dump)
		return dump

	def save_record(self, record):
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
		if real and record.id is None:
			args["p_tpl_uuid"] = app.id
		if record.id is not None:
			args[f"p_{pk}"] = record.id
		for field in record.fields.values():
			if record.id is None or field._dirty:
				args[f"p_{field.control.field}"] = field.control._asdbarg(field.value)
				if record.id is not None:
					args[f"p_{field.control.field}_changed"] = 1
		c = self.cursor()
		result = proc(c, **args)

		if result.p_errormessage:
			raise ValueError(result.p_errormessage)

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
			field.errors = []
		record.errors = []

	def _delete(self, record):
		app = record.app
		if app.basetable in {"data_select", "data"}:
			proc = self.proc_data_delete
		else:
			proc = self._getproc(app.deleteprocedure)

		c = self.cursor()
		r = proc(
			c,
			c_user=self.ide_id,
			p_dat_id=record.id,
		)

		if r.p_errormessage:
			raise ValueError(r.p_errormessage)

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
			proc = self.db.getobject(procname)
			if not isinstance(proc, orasql.Procedure):
				raise ValueError(f"no procedure {procname}")
			self.custom_procs[procname] = proc
			return proc


class HTTPHandler(Handler):
	def __init__(self, url, username=None, password=None):
		# type: (str, OptStr, OptStr) -> None
		super().__init__()
		if not url.endswith("/"):
			url += "/"
		self.url = url
		self.username = username

		self.session = requests.Session()

		self.auth_token = None # type: OptStr

		# If :obj:`username` or :obj:`password` are not given, we don't log in
		# This means we can only fetch data for public templates, i.e. those that are marked as "for all users"
		if username is not None and password is not None:
			# Login to the LivingApps installation and store the auth token we get
			r = self.session.post(
				f"{self.url}gateway/login",
				data=json.dumps({"username": username, "password": password}),
				headers={'content-type': "application/json"},
			)
			result = r.json()
			if result.get("status") == "success":
				self.auth_token = result["auth_token"]
			else:
				raise_403(r)

	def __repr__(self):
		# type: () -> str
		return f"<{self.__class__.__module__}.{self.__class__.__qualname__} url={self.url!r} username={self.username!r} at {id(self):#x}>"

	def _add_auth_token(self, kwargs):
		# type: (T.Dict[str, T.Any]) -> None
		if self.auth_token:
			if "headers" not in kwargs:
				kwargs["headers"] = {}
			kwargs["headers"]["X-La-Auth-Token"] = self.auth_token

	def file_content(self, file):
		# type: (la.File) -> bytes
		kwargs = {} # type: ReqParams
		self._add_auth_token(kwargs)
		r = self.session.get(
			self.url.rstrip("/") + file.url,
			**kwargs,
		)
		return r.content

	def get(self, *path, **params):
		# type: (*str, **T.Union[str, T.List[str]]) -> T.Dict[str, T.Any]
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
			f"{self.url}gateway/apps/{path}",
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

	def save_record(self, record):
		# type: (la.Record) -> None
		fields = {field.control.identifier: field.control._asjson(field.value) for field in record.fields.values() if record.id is None or field.is_dirty()}
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
			f"{self.url}gateway/v1/appdd/{app.id}.json",
			**kwargs,
		)
		r.raise_for_status()
		result = json.loads(r.text)
		status = result["status"]
		if status != "ok":
			raise TypeError(f"Response status {status!r}")
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
			field.errors = []
		record.errors = []

	def _delete(self, record):
		kwargs = {}
		self._add_auth_token(kwargs)

		r = self.session.delete(
			f"{self.url}gateway/v1/appdd/{record.app.id}/{record.id}.json",
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
			f"{self.url}gateway/api/v1/apps/{record.app.id}/actions/{actionidentifier}",
			**kwargs,
		)
		r.raise_for_status()


class FileHandler(Handler):
	def __init__(self, basepath=None):
		# type: (T.Union[None, str, pathlib.Path]) -> None
		if basepath is None:
			basepath = pathlib.Path()
		self.basepath = basepath

	def save_app(self, app, recursive=True):
		# FIXME: Save the app itself
		if recursive:
			for internaltemplate in app.internaltemplates.values():
				internaltemplate.save(self)
			for viewtemplate in app.viewtemplates.values():
				viewtemplate.save(self)

	def _save(self, path, content):
		# type: (pathlib.Path, str) -> None
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
	) # type: T.Dict[str, T.Tuple[str, ...]]

	def _guessext(self, basedir, template):
		# type: (T.Union[str, pathlib.Path], la.Template) -> str
		"""
		Try to guess an extension for the template ``template``.

		If there's only *one* file with a matching filename in the directory
		``basedir``, always use its filename, else try to guess the extension
		from the source.
		"""
		source = template.source or ""

		# If we have exactly *one* file with this basename in ``basedir``, use this filename
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
		"""
		Put the attribute named ``name`` into the JSON configuration ``config``.

		This means that if the attribute has the default value it will not be put
		into the config. All other values (e.g. ``enum``\\s) have to be converted
		to a JSON compatible type.
		"""
		value = getattr(obj, name)
		attr = getattr(obj.__class__, name)
		if value != attr.default:
			if isinstance(attr, la.EnumAttr):
				value = value.name.lower()
			config[name] = value

	def save_internaltemplate(self, internaltemplate, recursive=True):
		# type: (la.InternalTemplate, bool) -> None
		dir = f"{self.basepath}/{internaltemplate.app.fullname}/internaltemplates"
		ext = self._guessext(dir, internaltemplate)
		path = pathlib.Path(dir, f"{internaltemplate.identifier}.{ext}")
		self._save(path, internaltemplate.source)

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
			configorder = {} # type: T.Union[str, T.Dict[str, str]]
			self._dumpattr(configorder, order, "expression")
			self._dumpattr(configorder, order, "direction")
			self._dumpattr(configorder, order, "nulls")
			if list(configorder) == ["expression"]:
				configorder = configorder["expression"]
			configorders.append(configorder)
		return configorders

	def save_viewtemplate(self, viewtemplate, recursive=True):
		# type: (la.ViewTemplate, bool) -> None

		# Save the template itself
		dir = f"{self.basepath}/{viewtemplate.app.fullname}/viewtemplates"
		ext = self._guessext(dir, viewtemplate)
		path = pathlib.Path(dir, f"{viewtemplate.identifier}.{ext}")
		self._save(path, viewtemplate.source)

		# Save the template meta data
		config = {} # type: T.Dict[str, T.Any]
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
			self._save(configpath, json.dumps(config, indent="\t"))
		else:
			try:
				configpath.unlink()
			except FileNotFoundError:
				pass
