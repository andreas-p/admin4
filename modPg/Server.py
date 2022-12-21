# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
from wh import xlt, YesNo, StringType
from ._pgsql import pgConnectionPool, pgQuery, pgTypeCache, psycopg2, quoteIdent, quoteValue
from ._objects import SchemaObject
#from psycopg2.extensions import _param_escape

adminProcs=['pg_terminate_backend', 'pg_rotate_logfile', 'pg_reload_conf']

class Server(adm.ServerNode):
  shortname=xlt("pgsql Server")
  typename=xlt("PostgreSQL Server")
  findObjectIncremental=False

#  wantIconUpdate=True

  def __init__(self, settings):
    adm.ServerNode.__init__(self, settings)
    self.maintDb=settings['maintdb']
    self.version=None
    self.connectableDbs=None
    self.typeCache=None
    self.info=None
#    self.timeout=settings.get('querytimeout', standardTimeout)

      
  def GetConnection(self):
    if not self.connection:
      return None
    self.CheckConnection(self.connection)
    return self.connection

  def GetCursor(self):
    conn=self.GetConnection()
    if conn:
      return conn.GetCursor()
    return None
  
  
  def IsConnected(self, _deep=False):
    return self.connection != None

  def GetDsn(self, dbname, application, user=None, password=''):
    if not user:
      user=self.user
      password=self.password
      
    params= [('host', self.address),
            ('port', self.port),
            ('dbname', dbname),
            ('user', user),
            ('password', password),
            ('connect_timeout', 3),
            ('sslmode', self.settings['security']),
            ('client_encoding', 'UTF8'),
            ('application_name', application)
            ]
    return ' '.join(["%s=%s" % (key, psycopg2.extensions._param_escape(str(val))) for (key, val) in params])
    

  def GetType(self, oid):
    if self.version < 8.4:    category="' '::char as typcategory"
    else:                     category="typcategory"
    sql="""
        SELECT t.oid, typname, nspname, %s
          FROM pg_type t JOIN pg_namespace n ON n.oid=typnamespace
         WHERE typisdefined AND t.oid""" % category
    if not self.typeCache:
      rowset=self.GetCursor().ExecuteSet(sql + "<1000")
      self.typeCache=pgTypeCache(rowset)
    typ=self.typeCache.Get(oid)
    if not typ:
      rowset=self.GetCursor().ExecuteSet(sql + "=%d" % oid)
      typ=self.typeCache.Add(rowset)
    return typ
  
  def DoConnect(self, db=None):
    if db:
      dbname=db
    else: # called from adm.py
      dbname=self.maintDb

    application="%s browser" % adm.appTitle
    conn=pgConnectionPool(self, self.GetDsn(dbname, application))
    
    if not db and not self.connection:
      self.connection = conn
      self.version=conn.ServerVersion()
      self.RereadServerInfo()
        
    return conn
  

  def RereadServerInfo(self):
      parts=["""
        SELECT name, setting FROM pg_settings
         WHERE name in ('autovacuum', 'log_line_prefix', 'log_destination', 'logging_collector', 'log_directory', 'data_directory', 'config_file')
        UNION  
        SELECT 'version', version()
        UNION
        SELECT proname, proname FROM pg_proc
         WHERE proname IN ( %(adminprocs)s ) AND pronamespace=11 
        UNION
        SELECT 'adminspace', nspname FROM pg_namespace WHERE nspname='%(adminspace)s'
        UNION
        SELECT 'fav_table', relname FROM pg_class JOIN pg_namespace nsp ON nsp.oid=relnamespace 
         WHERE nspname='%(adminspace)s' AND relname='%(fav_table)s'
        """ % {'datname': self.maintDb, 
         'adminspace': self.GetPreference("AdminNamespace"),
         'fav_table': "Admin_Fav_%s" % self.user,
         'adminprocs': ", ".join(map(lambda p: "'%s'" % p, adminProcs))
         }]

      # check instrumentation of tools
      for menu in self.moduleinfo().get('menus', []):
        cls=menu['class']
        if hasattr(cls, 'GetInstrumentQuery'):
          iq=cls.GetInstrumentQuery(self)
          if iq:
            parts.append(iq)
      query="\nUNION\n".join(parts)
      self.info=self.connection.GetCursor().ExecuteDict(query)
      #self.info['lastsysoid'] = 15000 # TODO MAGIC! no pg_database.datlastsysoid since V15
      self.adminspace=self.info.get('adminspace')
      fav_table=self.info.get('fav_table')
      if fav_table:
        self.fav_table="%s.%s" % (quoteIdent(self.adminspace), quoteIdent(fav_table))
      else:
        self.fav_table=None

  
  def GetConnectableDbs(self):
    if not self.connectableDbs:
      self.connectableDbs=self.GetCursor().ExecuteList("SELECT datname FROM pg_database WHERE datallowconn ORDER BY oid")
    return self.connectableDbs
  
  def GetValue(self, name):
    return self.info.get(name)
  
  def GetLastError(self):
    if self.connection:
      return self.connection.lastError
    return None
  
  def NeedsInstrumentation(self):
    missing=[]
    for name in adminProcs:
      if not self.GetValue(name):
        missing.append(name)
    if not self.fav_table:
      missing.append('fav_table')
    
    for menu in self.moduleinfo().get('menus', []):
      cls=menu['class']
      if hasattr(cls, 'GetMissingInstrumentation'):
        mi=cls.GetMissingInstrumentation(self)
        if mi:
          if isinstance(mi, list):
            missing.extend(mi)
          else:
            missing.append(mi)
    return missing   


  def FindObject(self, tree, currentItem, patterns):
    node=tree.GetNode()
    if node == self:
      return adm.ServerNode.FindObject(self, tree, currentItem, patterns)

    if not hasattr(node, "GetDatabase"): # a collection
      node=node.parentNode
    db=node.GetDatabase()
    
    from .Schema import Schema
    if isinstance(patterns, StringType):
      patterns=patterns.split()
    
    kind=None    # TODO maybe later something sensible

    
    cp=" ".join(patterns)
    if not hasattr(self, 'currentPatterns') or self.currentPatterns != cp or not self.foundObjects:
      self.currentPatterns=cp

      if isinstance(node, SchemaObject):  schemaOid=node.GetSchemaOid()
      elif isinstance(node, Schema):      schemaOid=node.GetOid()
      else:                               schemaOid=None
      
      self.foundObjects=db.FindObject(patterns, schemaOid, kind)

    nsps={}
    kinds={}
    for ni in self.moduleinfo()['nodes'].values():
      cls=ni['class']
      if hasattr(cls, 'FindQuery'):
        kinds[cls.relkind] = cls
    
    db.PopulateChildren()
    for schemas in db.childnodes:
      if schemas.nodeclass == Schema:
        break;
    
    for row in self.foundObjects:
      del self.foundObjects[0]
      cls=kinds[row['kind']]
      
      # TODO check favourite
      
      if issubclass(cls, SchemaObject):
        nsp=row['nspname']
        oid=row['oid']
        if nsp not in nsps:
          if not nsps:
            schemas.PopulateChildren()
          for schema in schemas.childnodes:
            if schema.name == nsp:
              nsps[nsp] = schema
              schema.PopulateChildren()
              break
          schema=nsps.get(nsp)
          if not schema:
            return None
          for coll in schema.childnodes:
            if coll.nodeclass == cls:
              coll.PopulateChildren()
              for node in coll.childnodes:
                if node.GetOid() == oid:
                  root=None
                  item=tree.Find(root, node.id)
                  return item
              
    return None
     
  def ExpandColDefs(self, cols):
    return ", ".join( [ "%s as %s" % (c[0], quoteIdent(c[1])) for c in cols])

  def GetFavourites(self, db):
    if self.fav_table:
      return self.GetCursor().ExecuteList(
          "SELECT favoid FROM %(fav_table)s WHERE dboid=%(dboid)d" % 
          { 'fav_table': self.GetServer().fav_table,
            'dboid': db.GetOid() } )
    else:
      return []
    
  def AddFavourite(self, node, favgroup=None):
    query=pgQuery(self.fav_table, self.GetCursor())
    query.AddColVal('dboid',node.GetDatabase().GetOid())
    query.AddColVal('favoid', node.GetOid())
    query.AddColVal('favtype', node.favtype)
    query.AddColVal('favgroup', favgroup)
    query.Insert()
    node.GetDatabase().favourites.append(node.GetOid())
    return True
    
    self.GetCursor().ExecuteSingle(
        "INSERT INTO %(favtable)s (dboid, favoid, favtype, favgroup) VALUES (%(dboid)d, %(favoid)d, '%(favtype)s', %(favgroup)s)" %
        { 'favtable': self.fav_table,
          'dboid': node.GetDatabase().GetOid(), 
          'favoid': node.GetOid(), 
          'favtype': node.favtype,
          'favgroup': quoteValue(favgroup) } )
  
    node.GetDatabase().favourites.append(node.GetOid())
    return True

  def DelFavourite(self, node):
    try:
      node.GetDatabase().favourites.remove(node.GetOid())
    except:
      pass
    query=pgQuery(self.fav_table, self.GetCursor())
    query.AddWhere('dboid',node.GetDatabase().GetOid())
    query.AddWhere('favoid', node.GetOid())
    query.Delete()
    return True
    self.GetCursor().ExecuteSingle(
        "DELETE FROM %(favtable)s WHERE dboid=%(dboid)s AND favoid=%(favoid)s" %
        { 'favtable': self.fav_table,
          'dboid': node.GetDatabase().GetOid(), 
          'favoid': node.GetOid(), } )
    return True
  
    
  def GetHint(self):
    if self.NeedsInstrumentation():
      return ( 'instrument', xlt("Server %s not instrumented") % self.name, 
               { 'servername': self.name, 'version': str(self.version) } )
            
  def GetProperties(self):
    if not self.properties:
      missing=self.NeedsInstrumentation()
      if missing:
        instr=xlt("incomplete: %s missing" % ",".join(missing))
      else:
        instr=xlt("fully instrumented")
      self.properties= [
         ( xlt("Name"),self.name),
         ( xlt("Version"), self.info['version']),
         ( xlt("Address"), self.address),
         ( xlt("Maintenance DB"), self.maintDb),
         ( xlt("Security"), self.settings['security']),
         ( xlt("Port"), self.settings["port"]),
         ( xlt("User"), self.user),
         ( xlt("Connected"), YesNo(self.IsConnected())),
         ( xlt("Autoconnect"), YesNo(self.settings.get('autoconnect'))),
         ( xlt("Autovacuum"), YesNo(self.info['autovacuum'])),
         ( xlt("Instrumentation"), instr), 
         ]
    if self.version < 8.4:
      self.AddProperty(xlt("Ancient server"), xlt("barely supported"))
    return self.properties


  def GetStatistics(self):
    cols=[ ( 'datname',       xlt("Database") ),
           ( 'numbackends',   xlt("Backends") ),
           ( 'xact_commit',   xlt("Xact Committed") ), 
           ( 'xact_rollback', xlt("Xact Rolled Back") ),
           ( 'blks_read',     xlt("Blocks Read") ),
           ( 'blks_hit',      xlt("Blocks Written") ),
           ( 'pg_size_pretty(pg_database_size(datid))', xlt("Size"))
          ]
    rowset=self.GetCursor().ExecuteSet("""
    SELECT %(cols)s
    FROM pg_stat_database db ORDER BY datname""" % {'cols': self.ExpandColDefs(cols)})
    return rowset

  class Dlg(adm.ServerPropertyDialog):
    adm.ServerPropertyDialog.keyvals.extend( [ "MaintDb" ] )

    def __init__(self, parentWin, node):
      adm.PropertyDialog.__init__(self, parentWin, node, None)
      self['Security'].Append( { ' ': " ", 'require': xlt("required"), 'prefer': xlt("preferred"), 'allow': xlt("allowed"), 'disable': xlt("disabled") } )
      self.Bind("HostName HostAddress Port User Password Autoconnect MaintDb")


    def Go(self):
      if self.node:
        self.SetSettings(self.node.settings)
        self["HostName"].Disable()
      else:
        self.Security="prefer"
      self.OnCheck()

    def Check(self):
      ok=True
      if not self.node:
        ok=self.CheckValid(ok, self.Hostname, xlt("Host name cannot be empty"))
        ok=self.CheckValid(ok, not adm.config.existsServer(self, self.HostName), xlt("Host name already in use"))
      ok=self.CheckValid(ok, self.HostAddress, xlt("Host address cannot be empty"))
      ok=self.CheckValid(ok, self.Port, xlt("Port cannot be 0"))
      ok=self.CheckValid(ok, self.MaintDB, xlt("Maintenance DB cannot be empty"))
      return ok

    def Save(self):
      if self.GetChanged():
        settings=self.GetSettings()
        adm.config.storeServerSettings(self, settings)
        if self.node:
          self.node.settings=settings
          self.node.registrationChanged=True
        else:
          adm.RegisterServer(settings)
      return True
  
  @staticmethod
  def Register(parentWin):
    adm.DisplayDialog(Server.Dlg, parentWin, None)

  def Edit(self, parentWin):
    adm.DisplayDialog(Server.Dlg, parentWin, self)

nodeinfo=[ { 'class': Server, 'collection': xlt("PostgreSQL Server") } ]
 
  
class ServerInstrument:
  name=xlt("Instrument server")
  help=xlt("Instrument server for easier administration")
  
  @staticmethod
  def CheckAvailableOn(node):
    return isinstance(node, Server) and node.NeedsInstrumentation()
  
  
  @staticmethod
  def OnExecute(_parentWin, server):
    adminspace=server.adminspace
    if not adminspace:
      adminspace=server.GetPreference("AdminNamespace")
      server.GetCursor().ExecuteSingle("CREATE SCHEMA %s AUTHORIZATION postgres" % quoteIdent(adminspace))
      server.adminspace=adminspace

    adsQuoted=quoteIdent(adminspace)

    if not server.fav_table:
      fav_table=quoteIdent("Admin_Fav_%s" % server.user)
      server.GetCursor().ExecuteSingle("""
CREATE TABLE %(adminspace)s.%(fav_table)s 
  (dboid OID, favoid OID, favtype CHAR, favgroup TEXT, PRIMARY KEY(dboid, favoid))""" % 
        {'adminspace': adsQuoted,
        'fav_table': fav_table })
      server.fav_table="%s.%s" % (adsQuoted, fav_table)

    for menu in server.moduleinfo().get('menus', []):
      cls=menu['class']
      if hasattr(cls, 'DoInstrument'):
        cls.DoInstrument(server)
    
    server.RereadServerInfo()
    return True
    
    
class ServerConfig(adm.PropertyDialog):
  name=xlt("Server Configuration")
  help=xlt("Edit PostgreSQL Server Configuration")

  def Go(self):
    pass


  @staticmethod
  def CheckEnabled(_unused_node):
    return True # TODO check if available


  @staticmethod
  def OnExecute(parentWin, node):
    dlg=ServerConfig(parentWin, node)
    return dlg.GoModal()



menuinfo=[
#        {"class": ServerConfig, "nodeclasses": Server, 'sort': 40},
        {"class": ServerInstrument, "nodeclasses": Server, 'sort': 1},
        ]
