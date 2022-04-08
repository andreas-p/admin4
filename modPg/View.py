# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

from ._objects import SchemaObject
from ._pgsql import pgQuery
from wh import xlt


class View(SchemaObject):
  typename=xlt("View")
  shortname=xlt("View")
  grantTypename='TABLE'
  refreshOid="rel.oid"
  allGrants='arwdDxt'
  favtype='v'
  relkind='v'

  @staticmethod
  def FindQuery(schemaName, schemaOid, patterns):
    sql=pgQuery("pg_class c")
    sql.AddCol("relkind as kind")
    sql.AddCol("nspname")
    sql.AddCol("relname as name")
    sql.AddCol("n.oid as nspoid")
    sql.AddCol("c.oid")
    sql.AddJoin("pg_namespace n ON n.oid=relnamespace")
    sql.AddWhere("relkind='v'")
    SchemaObject.AddFindRestrictions(sql, schemaName, schemaOid, 'relname', patterns)
    return sql

  @staticmethod
  def InstancesQuery(parentNode):
    sql=pgQuery("pg_class rel")
    sql.AddCol("rel.oid, relname as name, nspname, ns.oid as nspoid, spcname, pg_get_userbyid(relowner) AS owner, relacl as acl, relkind")
    sql.AddCol("description")
    sql.AddJoin("pg_namespace ns ON ns.oid=rel.relnamespace")
    sql.AddLeft("pg_tablespace ta ON ta.oid=rel.reltablespace")
    sql.AddLeft("pg_description des ON (des.objoid=rel.oid AND des.objsubid=0)")
    sql.AddLeft("pg_constraint c ON c.conrelid=rel.oid AND c.contype='p'")
    sql.AddWhere("relkind  in ('v', 'm')")
    sql.AddWhere("relnamespace", parentNode.parentNode.GetOid())
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


  def GetSql(self):
    definition=self.info.get('definition')
    if not definition:
      definition=self.GetCursor().ExecuteSingle("SELECT pg_get_viewdef(%d, true)" % self.GetOid())
      self.info['definition']=definition
    return "CREATE OR REPLACE %(object)s %(tablespace)s AS\n%(def)s\n%(grant)s" % {
               'object': self.TypeSql(),
               'tablespace': self.TablespaceSql(), 
               'def': definition, 'grant': self.GrantCommentSql() }
  

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


