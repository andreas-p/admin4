# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from _objects import DatabaseObject, Query
from wh import xlt, YesNo
import logger


class Function(DatabaseObject):
  typename=xlt("Function")
  shortname=xlt("Function")
  refreshOid="pro.oid"
  favtype='v'


  @staticmethod
  def InstancesQuery(parentNode):
    sql=Query("pg_proc pro")
    sql.AddCol("pro.oid, pg_get_userbyid(proowner) AS owner, proacl as acl, proname as name, pro.*, nspname, lanname, description")
    if parentNode.GetServer().version >= 8.4:
      sql.AddCol("pg_get_function_arguments(pro.oid) as arguments, pg_get_function_result(pro.oid) as result")
    sql.AddJoin("pg_language lang ON lang.oid=prolang")
    sql.AddLeft("pg_namespace ns ON ns.oid=pronamespace")
    sql.AddLeft("pg_description des ON (des.objoid=pro.oid AND des.objsubid=0)")
    sql.AddWhere("pronamespace=%d" % parentNode.parentNode.GetOid())
    sql.AddOrder("proname")
    return sql

  def __init__(self, parentNode, info):
    super(Function, self).__init__(parentNode, info)
    args=self.info.get('arguments')
    if args!= None:
      self.name="%s(%s)" % (self.name, args)
      
  def GetIcon(self):
    icons=[]
    icons.append("Function")
    if self.GetOid() in self.GetDatabase().favourites:
      icons.append('fav')
    return self.GetImageId(icons)


  def GetSql(self):
    definition=self.info.get('definition')
    if not definition:
      definition=self.GetCursor().ExecuteSingle("SELECT pg_get_functiondef(%d)" % self.GetOid())
      self.info['definition']=definition
    return "%(def)s\n%(grant)s" % {
               'object': self.ObjectSql(),
               'def': definition, 'grant': self.GrantSql() }
  

  def GetProperties(self):
    if not len(self.properties):
      args=self.info.get('arguments')
      if args == None:
        logger.error("PGSQL < 8.4; no function args/returns")
        args=""
        self.info['arguments']=""
        self.info['result']=""
      self.info['definition']=None
      result=self.info.get('result', "")
      self.properties = [
        (xlt("Name"),           "%s(%s)" % (self.info['name'], args)),
        (xlt("Namespace"),      self.info['nspname']),
        (xlt("Language"),       self.info['lanname']),
        (xlt("Strict"),         YesNo(self.info['proisstrict'])),
        (    "OID" ,            self.info['oid']),
        (xlt("Returns"),        result),
        (xlt("Owner"),          self.info['owner']),
        (xlt("ACL"),            self.info['acl'])
      ]
      
      self.AddProperty(xlt("Description"), self.info['description'])
    return self.properties
  
    
nodeinfo= [ { "class" : Function, "parents": ["Schema"], "sort": 60, "collection": "Functions", "pages": ["SqlPage"] } ]    


