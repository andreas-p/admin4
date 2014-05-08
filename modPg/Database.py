# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from _objects import ServerObject, DatabaseObject
from wh import xlt, YesNo

class Database(ServerObject):
  typename=xlt("Database")
  shortname=xlt("Database")

  @staticmethod
  def GetInstances(parentNode):
    instances=[]
    params={'sysrestr': " WHERE d.oid > %s" % parentNode.GetServer().GetLastSysOid() }
    set=parentNode.GetConnection().ExecuteSet("""
      SELECT d.*, pg_encoding_to_char(encoding) AS pgencoding, pg_get_userbyid(datdba) AS dbowner, spcname, d.oid, description
        FROM pg_database d
        JOIN pg_tablespace t ON t.oid=dattablespace
        LEFT JOIN pg_shdescription des ON des.objoid=d.oid
        %(sysrestr)s
       ORDER BY datname
      """ % params)
    if set:
      for row in set:
        if not row:
          break
        instances.append(Database(parentNode, row['datname'], row.getDict()))

      for db in instances:
        db.favourites=db.GetServer().GetFavourites(db)

    return instances

  def __init__(self, parentNode, name, info):
    super(Database, self).__init__(parentNode, name)
    self.info=info
    

  def GetDatabase(self):
    return self

  def GetIcon(self):
    icons=[]
    if self.IsConnected():
      icons.append("Database-conn")
    else:
      icons.append("Database-noconn")
    if self.IsMaintenanceConnection():
      icons.append("pg")
    return self.GetImageId(icons)
  
  
  def IsMaintenanceConnection(self):
    return self.name == self.GetServer().maintDb
  
  def IsConnected(self):
    if self.IsMaintenanceConnection():
      return self.GetServer().IsConnected()
    return self.connection != None
  
  def DoConnect(self, application=None):
    return self.GetServer().DoConnect(self.name, application)
  
  
  def GetConnection(self, detached=False):
    if detached:
      return super(Database, self).GetConnection(detached)
    
    if self.IsMaintenanceConnection():
      return self.GetServer().GetConnection()
    if not self.connection:
      self.connection = self.DoConnect()
      self.IconUpdate(True)
      self.properties=[]
    else:
      self.CheckConnection(self.connection)
    return self.connection


  def Disconnect(self):
    self.connection.disconnect()
    self.connection = None
    #self.Refresh()
    self.IconUpdate(True)
    
    
     
  def GetProperties(self):
    if not len(self.properties):
      dict=self.GetConnection().ExecuteDict("""
          SELECT 'languages', array_agg(lanname) as lannames 
            FROM (SELECT lanname FROM pg_language ORDER BY lanispl desc, lanname) AS langlist""")
      self.info.update(dict)
      if self.GetServer().version >= 9.1:
        dict=self.GetConnection().ExecuteDict("""
          SELECT 'extensions', array_agg(name) as extnames
            FROM (SELECT extname || ' V' || extversion AS name FROM pg_extension ORDER BY extname) AS extlist
          UNION
          SELECT 'available_extensions', array_agg(name) as extnames
            FROM (SELECT name || ' V' || default_version AS name FROM pg_available_extensions WHERE installed_version is null ORDER BY name) AS avextlist
          """)
        self.info.update(dict)
          
          
        
      self.properties = [
        (xlt("Name"),           self.name),
        (  "OID" ,              self.info['oid']),
        (xlt("Owner"),          self.info['dbowner']),
        (xlt("Tablespace"),     self.info['spcname']),
        (xlt("Encoding"),       self.info['pgencoding']),
        (xlt("Connected"),      YesNo(self.IsConnected())),
      ]

      self.AddProperty(xlt("Backend PID"), self.GetConnection().conn.get_backend_pid())
      if self.info['datistemplate']:
        self.AddYesNoProperty(xlt("Template"), True)
      if 'datctype' in self.info:
        self.AddProperty(xlt("Collate"), self.info['datcollate'])
        self.AddProperty(xlt("CType"), self.info['datctype'])
      self.AddProperty(xlt("Languages"), ", ".join(self.info['languages']))
      ext=self.info.get('extensions')
      if ext != None:
        if ext:
          ext=", ".join(ext)
        self.AddProperty(xlt("Installed Extensions"), ext)
        avext=self.info.get('available_extensions')
        if avext:
          avext=".".join(avext)
        self.AddProperty(xlt("Available Extensions"), avext)
      self.AddProperty(xlt("Description"), self.info['description'])
    return self.properties
  
class Programming(DatabaseObject):
  typename="Programming"
  shortname="Programming"
  @staticmethod
  def GetInstances(parentNode):
    instances=[Programming(parentNode, "")]
    return instances

  def GetProperties(self):
    return []
  
nodeinfo= [ { "class": Database, "parents": ["Server"], "sort": 30, "pages": "SqlPage" },
#            { 'class': Programming, 'parents': Database, 'sort': 50 }
            ]    


class DbDisconnect:
  name=xlt("Disconnect")
  help=xlt("Disconnect database connection")
  
  @staticmethod
  def CheckEnabled(node):
    return node.connection != None

  @staticmethod
  def OnExecute(_parentWin, node):
    node.Disconnect()
    
menuinfo=[
           {"class": DbDisconnect, "nodeclasses": Database , "sort": 1 } ,
          ]
