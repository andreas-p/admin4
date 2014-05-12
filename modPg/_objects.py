# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from node import Node, Collection, NodeId

class ServerObject(Node):
  def __init__(self, parentNode, name):
    super(ServerObject, self).__init__(parentNode, name)

  def GetComment(self):
    return self.info.get('description', "")
    
  def GetOid(self):
    return self.info['oid']

  def GetCursor(self):
    if self.connection:
      self.CheckConnection(self.connection)
      return self.connection.GetCursor()
    if self.parentNode:
      return self.parentNode.GetCursor()
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
      str += "\nCOMMENT ON %s IS %s\n" % (self.ObjectSql(), self.GetServer().quoteString(des)) 
    return str
  
  def TablespaceSql(self):
    ts=self.info['spcname']
    if ts:
      return "TABLESPACE %s" % self.GetServer().quoteIdent(ts)
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
    schema=self.GetServer().quoteIdent(self.info['nspname'])
    name=self.GetServer().quoteIdent(self.info['name'])
    if schema == '"public"':
      schema="public"
    return "%s.%s" % (schema, name)



class DatabaseObject(ServerObject):
  def __init__(self, parentNode, info):
    super(DatabaseObject, self).__init__(parentNode, self.FullName(info))
    self.info=info
    self.id = NodeId(self, str(info['oid']))


  @classmethod
  def GetInstancesFromClass(cls, parentNode):
    instances=[]
    sql=cls.InstancesQuery(parentNode)
    set=parentNode.GetConnection().GetCursor().ExecuteSet(sql.Select())

    if set:
      for row in set:
        if not row:
          break
        instances.append(cls(parentNode, row.getDict()))
    return instances


  def Refresh(self):
    sql=self.InstancesQuery(self.parentNode)
    sql.AddWhere("%s=%d" % (self.refreshOid, self.GetOid()))
    set=self.parentNode.GetCursor().ExecuteSet(sql.Select())
    self.info = set.Next().getDict()
    self.DoRefresh()
    
  def GetDatabase(self):
    if isinstance(self.parentNode, Collection):
      return self.parentNode.parentNode.GetDatabase()
    return self.parentNode.GetDatabase()
  
  
class Query:
  def __init__(self, tab=None):
    self.columns=[]
    self.vals=[]
    self.tables=[]
    self.where=[]
    self.order=[]
    self.group=[]
    if tab:
      self.tables.append(tab)
  
  def AddCol(self, name):
    if name:
      if isinstance(name, list):
        self.columns.extend(name)
      else:
        self.columns.append(name)
  
  def AddColVal(self, name, val):
    if name:
      self.columns.append(name)
      self.vals.append(val)

  def AddJoin(self, tab):
    if tab:
      self.tables.append("JOIN %s" % tab)
      
  def AddLeft(self, tab):
    if tab:
      self.tables.append("LEFT OUTER JOIN %s" % tab)

  def AddWhere(self, where):
    if where:
      self.where.append(where)
  
  def AddOrder(self, order):
    if order:
      self.order.append(order)
    
    def AddGroup(self, group):
      if group:
        self.group.append(group)
    
  def Select(self):
    sql=["SELECT %s" % ", ".join(self.columns), 
         "  FROM  %s" % "\n  ".join(self.tables) ]
    if self.where:
      sql.append(" WHERE %s" % "\n   AND ".join(self.where))
    if self.group:
      sql.append(" GROUP BY %s" % ", ".join(self.group))
    if self.order:
      sql.append(" ORDER BY %s" % ", ".join(self.order))
    return "\n".join(sql)
    

