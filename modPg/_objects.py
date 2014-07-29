# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from node import Node, Collection, NodeId
from _pgsql import quoteIdent, quoteValue
from wh import shlexSplit

rightString={'r': "SELECT",
               'w': "UPDATE",
               'a': "INSERT",
               'd': "DELETE",
               'D': "TRUNCATE",
               'x': "REFERENCES",
               't': "TRIGGER",
               'X': "EXECUTE",
               'U': "USAGE",
               'C': "CREATE",
               'c': "CONNECT",
               'T': "TEMPORARY" }

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
  
               
  def GrantCommentSql(self):
    str=""
    acl=self.info.get('acl')
    if acl:
      for grant in shlexSplit(acl[1:-1], ','):
        if grant.startswith('='):
          user="public"
          rest=grant[1:]
        else:
          user, rest=shlexSplit(grant, '=')
          user=quoteIdent(user)
        rights=shlexSplit(rest, '/')[0]
        if rights == self.allGrants:
          rights="ALL"
        else:
          rightlist=[]
          for right in rights:
            rightlist.append(rightString[right])
          rights=",".join(rightlist)
        str += "GRANT %s ON %s TO %s\n" % (rights, self.ObjectSql(), user)
      
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
    return "%s %s" % (self.GrantTypeSql(), self.NameSql())
  
  
  def GrantTypeSql(self):
    if hasattr(self, 'grantTypename'):
      return self.grantTypename.upper()
    return self.TypeSql()
  
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
  
  @classmethod
  def AddFindRestrictions(cls, sql, schemaName, schemaOid, namecol, patterns):
    if issubclass(cls, SchemaObject):
      if schemaName:
        sql.AddWhere("nspname ILIKE '%%%s%%'" % schemaName)
      elif schemaOid:
        sql.AddWhere("n.oid=%d" % schemaOid)
    for p in patterns:
      sql.AddWhere("%s ILIKE '%%%s%%'" % (namecol, p))


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
    n=set.Next()
    if n: self.info = n.getDict()
    else: n={}
    self.DoRefresh()
    
  def GetDatabase(self):
    if isinstance(self.parentNode, Collection):
      return self.parentNode.parentNode.GetDatabase()
    return self.parentNode.GetDatabase()
  
class SchemaObject(DatabaseObject):
  def GetSchemaOid(self):
    oid=self.info.get('nspoid')
    return oid

  