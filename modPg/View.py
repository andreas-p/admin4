# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

from _objects import DatabaseObject, Query
from wh import xlt


class View(DatabaseObject):
  typename=xlt("View")
  shortname=xlt("View")
  refreshOid="rel.oid"
  favtype='v'


  @staticmethod
  def InstancesQuery(parentNode):
    sql=Query("pg_class rel")
    sql.AddCol("rel.oid, relname as name, nspname, spcname, pg_get_userbyid(relowner) AS owner, relacl as acl, relkind")
    sql.AddCol("description")
    sql.AddJoin("pg_namespace ns ON ns.oid=rel.relnamespace")
    sql.AddLeft("pg_tablespace ta ON ta.oid=rel.reltablespace")
    sql.AddLeft("pg_description des ON (des.objoid=rel.oid AND des.objsubid=0)")
    sql.AddLeft("pg_constraint c ON c.conrelid=rel.oid AND c.contype='p'")
    sql.AddWhere("relkind  in ('v', 'm')")
    sql.AddWhere("relnamespace=%d" % parentNode.parentNode.GetOid())
    sql.AddOrder("CASE WHEN nspname='%s' THEN ' ' else nspname END" % "public")
    sql.AddOrder("relname")
    return sql

 
  def TypeSql(self):
    if self.IsMaterialized():
      return "MATERIALIZED VIEW"
    else:
      return "VIEW"
  
  def GetIcon(self):
    icons=[]
    if self.IsMaterialized():
      icons.append("MatView")
    else:
      icons.append("View")
    if self.GetOid() in self.GetDatabase().favourites:
      icons.append('fav')
    return self.GetImageId(icons)


  def GetSql(self, detached):
    definition=self.info.get('definition')
    if not definition:
      definition=self.GetConnection(detached).ExecuteSingle("SELECT pg_get_viewdef(%d, true)" % self.GetOid())
      self.info['definition']=definition
    return "CREATE %(object)s %(tablespace)s AS\n%(def)s\n%(grant)s" % {
               'object': self.ObjectSql(),
               'tablespace': self.TablespaceSql(), 
               'def': definition, 'grant': self.GrantSql() }
  

  def GetProperties(self):
    if not len(self.properties):
      self.info['definition']=None
      self.properties = [
        (xlt("Name"),           self.info['name']),
        (xlt("Namespace"),      self.info['nspname']),
        (    "OID" ,            self.info['oid']),
        (xlt("Owner"),          self.info['owner']),
        (xlt("Tablespace"),     self.info['spcname']),
        (xlt("ACL"),            self.info['acl'])
      ]

      if self.IsMaterialized():
        self.AddProperty(xlt("Materialized"), xlt("Yes"))
      self.AddProperty(xlt("Description"), self.info['description'])
    return self.properties
  
  def IsMaterialized(self):
    return self.info['relkind'] == 'm'

    
nodeinfo= [ { "class" : View, "parents": ["Schema"], "sort": 30, "collection": "Views", "pages": ["SqlPage"] } ]    


