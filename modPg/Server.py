# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
from wh import xlt, YesNo
from _pgsql import pgConnectionPool, pgQuery, pgTypeCache, psycopg2, quoteIdent, quoteValue

adminProcs=['pg_terminate_backend', 'pg_rotate_logfile', 'pg_reload_conf']

class Server(adm.ServerNode):
  shortname=xlt("pgsql Server")
  typename=xlt("PostgreSQL Server")
  
#  wantIconUpdate=True

  def __init__(self, settings):
    adm.ServerNode.__init__(self, settings)
    self.maintDb=settings['maintdb']
    self.version=None
    self.connectableDbs=None
    self.typeCache=None
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

  def GetDsn(self, dbname, application):
    params= [('host', self.address),
            ('port', self.port),
            ('dbname', dbname),
            ('user', self.user),
            ('password', self.password),
            ('connect_timeout', 3),
            ('application_name', application)
            ]
    return ' '.join(["%s=%s" % (key, psycopg2._param_escape(str(val))) for (key, val) in params])
    

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
      
      self.info=conn.GetCursor().ExecuteDict("""
        SELECT name, setting FROM pg_settings
         WHERE name in ('autovacuum', 'log_line_prefix', 'log_destination')
        UNION  
        SELECT 'version', version()
        UNION
        SELECT 'lastsysoid', datlastsysoid::text from pg_database
         WHERE datname=%(datname)s
        UNION
        SELECT proname, proname from pg_proc
         WHERE proname in ( %(adminprocs)s ) 
        UNION
        SELECT 'adminspace', nspname FROM pg_namespace WHERE nspname=%(adminspace)s
        UNION
        SELECT 'fav_table', relname FROM pg_class JOIN pg_namespace nsp ON nsp.oid=relnamespace 
         WHERE nspname=%(adminspace)s AND relname=%(fav_table)s
        UNION
        SELECT 'snippet_table', relname FROM pg_class JOIN pg_namespace nsp ON nsp.oid=relnamespace 
         WHERE nspname=%(adminspace)s AND relname=%(snippet_table)s""" %
        {'datname': quoteValue(dbname), 
         'adminspace': quoteValue(self.GetPreference("AdminNamespace")),
         'fav_table': quoteValue("Admin_Fav_%s" % self.user),
         'adminprocs': ", ".join(map(lambda p: "'%s'" % p, adminProcs)),
         'snippet_table': quoteValue("Admin_Snippet_%s" % self.user)})

      v=self.info['version'].split(' ')[1]
      self.version=float(v[0:v.rfind('.')])
      self.adminspace=self.info.get('adminspace')
      fav_table=self.info.get('fav_table')
      if fav_table:
        self.fav_table="%s.%s" % (quoteIdent(self.adminspace), quoteIdent(fav_table))
      else:
        self.fav_table=None
      snippet_table=self.info.get('snippet_table')
      if snippet_table:
        self.snippet_table="%s.%s" % (quoteIdent(self.adminspace), quoteIdent(snippet_table))
      else:
        self.snippet_table=None
    return conn
  

  
  def GetConnectableDbs(self):
    if not self.connectableDbs:
      self.connectableDbs=self.GetCursor().ExecuteList("SELECT datname FROM pg_database WHERE datallowconn ORDER BY oid")
    return self.connectableDbs
  
  def GetValue(self, name):
    return self.info.get(name)
  
  def GetLastSysOid(self):
    return int(self.info['lastsysoid'])
  
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
    if not self.snippet_table:
      missing.append('snippet_table')  
    return missing   


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

    if not server.snippet_table:
      snippet_table=quoteIdent("Admin_Snippet_%s" % server.user)
      server.GetCursor().ExecuteSingle("""
CREATE TABLE %(adminspace)s.%(snippet_table)s 
  (id SERIAL PRIMARY KEY, parent INT4 NOT NULL DEFAULT 0, sort FLOAT NOT NULL DEFAULT 0.0, name TEXT, snippet TEXT);""" % 
        {'adminspace': adsQuoted,
        'snippet_table': snippet_table })
      server.snippet_table="%s.%s" % (adsQuoted, snippet_table)
    return True
    
    
class ServerConfig(adm.PropertyDialog):
  name=xlt("Server Configuration")
  help=xlt("Edit PostgreSQL Server Configuration")

  def Go(self):
    pass


  @staticmethod
  def CheckEnabled(unused_node):
    return True # TODO check if available


  @staticmethod
  def OnExecute(parentWin, node):
    dlg=ServerConfig(parentWin, node)
    return dlg.GoModal()



menuinfo=[
#        {"class": ServerConfig, "nodeclasses": Server, 'sort': 40},
        {"class": ServerInstrument, "nodeclasses": Server, 'sort': 1},
        ]
