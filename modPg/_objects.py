# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from node import Node, Collection, NodeId
from _pgsql import quoteIdent, quoteValue


class ServerObject(Node):
  def __init__(self, parentNode, name):
    super(ServerObject, self).__init__(parentNode, name)
    if hasattr(self, 'Init'):
      self.Init()

  def GetComment(self):
    return self.info.get('description', "")
    
  def GetOid(self):
    return self.info['oid']

  def GetCursor(self):
    if self.connection:
      self.CheckConnection(self.connection)
      return self.connection.GetCursor()
    if self.parentNode:
      return self.parentNode.GetConnection().GetCursor()
    return None
      
  def ExecuteSet(self, cmd, args=None):
    cursor=self.GetCursor()
    rs=cursor.ExecuteSet(cmd, args)
    return rs
    
  def ExecuteRow(self, cmd, args=None):
    cursor=self.GetCursor()
    row=cursor.ExecuteRow(cmd, args)
    return row
  
  def ExecuteSingle(self, cmd, args=None):
    cursor=self.GetCursor()
    val=cursor.ExecuteSingle(cmd, args)
    return val
  
  def GrantSql(self):
    str=""
    des=self.info.get('description')
    if des:
      str += "\nCOMMENT ON %s IS %s\n" % (self.ObjectSql(), quoteValue(des)) 
    return str
  
  def TablespaceSql(self):
    ts=self.info['spcname']
    if ts:
      return "TABLESPACE %s" % quoteIdent(ts)
    return ""
  
  def ObjectSql(self):
    return "%s %s" % (self.TypeSql(), self.NameSql())
  
  def TypeSql(self):
    return self.typename.upper()
  
  @staticmethod
  def FullName(info):
    schema=info.get('nspname')
    name=info['name']
    if not schema or schema == 'public':
      return name
    else:
      return "%s.%s" % (schema, name)
    
  def NameSql(self):
    name=quoteIdent(self.info['name'])
    schema=self.info.get('nspname')
    if not schema:
      return name
    elif schema != 'public':
      schema=quoteIdent(schema)
    return "%s.%s" % (schema, name)


class DatabaseObject(ServerObject):
  def __init__(self, parentNode, info):
    ServerObject.__init__(self, parentNode, self.FullName(info))
    self.info=info
    self.id = NodeId(self, str(info['oid']))


  @classmethod
  def GetInstancesFromClass(cls, parentNode):
    instances=[]
    sql=cls.InstancesQuery(parentNode)
    set=parentNode.GetConnection().GetCursor().ExecuteSet(sql.SelectQueryString())

    if set:
      for row in set:
        if not row:
          break
        instances.append(cls(parentNode, row.getDict()))
    return instances


  def Refresh(self):
    sql=self.InstancesQuery(self.parentNode)
    sql.AddWhere("%s=%d" % (self.refreshOid, self.GetOid()))
    set=self.parentNode.GetConnection().GetCursor().ExecuteSet(sql.SelectQueryString())
    self.info = set.Next().getDict()
    self.DoRefresh()
    
  def GetDatabase(self):
    if isinstance(self.parentNode, Collection):
      return self.parentNode.parentNode.GetDatabase()
    return self.parentNode.GetDatabase()
  
class SchemaObject(DatabaseObject):
  pass

  