# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage

from ._objects import SchemaObject
from ._pgsql import pgQuery
from wh import xlt
import adm



class Sequence(SchemaObject):
  typename=xlt("Sequence")
  shortname=xlt("Sequence")
  refreshOid="rel.oid"
  allGrants="rwU"
  favtype='s'
  relkind='S'
  
  @staticmethod
  def FindQuery(schemaName, schemaOid, patterns):
    sql=pgQuery("pg_class c")
    sql.AddCol("relkind as kind")
    sql.AddCol("nspname")
    sql.AddCol("relname as name")
    sql.AddCol("n.oid as nspoid")
    sql.AddCol("c.oid")
    sql.AddJoin("pg_namespace n ON n.oid=relnamespace")
    sql.AddWhere("relkind='S'")
    SchemaObject.AddFindRestrictions(sql, schemaName, schemaOid, 'relname', patterns)
    return sql
  
  
  def GetSql(self):
    if not self.properties:
      self.GetProperties()
    return """CREATE SEQUENCE %(name)s
     MINVALUE %(min)d MAXVALUE %(max)d INCREMENT %(inc)d
     CACHE %(cache)d START %(start)d;

%(grant)s""" % {
               'name': self.NameSql(),
               'tablespace': self.TablespaceSql(),
               'min': self.info['min_value'],
               'max': self.info['max_value'], 
               'inc': self.info['increment_by'],
               'cache': self.info['cache_value'],
               'start': self.nextval,
               'grant': self.GrantCommentSql() }

  def GetIcon(self):
    icons=[]
    icons.append("Sequence")
    if self.GetOid() in self.GetDatabase().favourites:
      icons.append('fav')
    return self.GetImageId(icons)


  @staticmethod
  def InstancesQuery(parentNode):
    sql=pgQuery("pg_class rel")
    sql.AddCol("rel.oid, relname as name, nspname, ns.oid as nspoid, spcname, pg_get_userbyid(relowner) AS owner, relacl as acl, relkind")
    sql.AddCol("description")
    sql.AddJoin("pg_namespace ns ON ns.oid=rel.relnamespace")
    sql.AddLeft("pg_tablespace ta ON ta.oid=rel.reltablespace")
    sql.AddLeft("pg_description des ON (des.objoid=rel.oid AND des.objsubid=0)")
    sql.AddWhere("relkind  in ('S')")
    sql.AddWhere("relnamespace", parentNode.parentNode.GetOid())
    sql.AddOrder("CASE WHEN nspname='%s' THEN ' ' else nspname END" % "public")
    sql.AddOrder("relname")
    if parentNode.GetServer().version >= 10:
      sql.AddJoin("pg_sequence seq ON seqrelid=rel.oid")
      sql.AddCol("seqincrement AS increment_by, seqstart AS start_value")
      sql.AddCol("seqmin AS min_value, seqmax AS max_value, seqcache AS cache_value")
      sql.AddCol("seqcycle AS is_cycled")
    return sql
  
  def GetProperties(self):
    if not len(self.properties):
      row=self.GetCursor().ExecuteRow("SELECT * FROM %s" % self.NameSql())
      self.info.update(row.getDict())
      self.nextval=self.info['last_value']
      if self.info['is_called']:
        self.nextval += self.info['increment_by']
        
      self.properties = [
        (xlt("Name"),           self.info['name']),
        (xlt("Namespace"),      self.info['nspname']),
        (    "OID" ,            self.info['oid']),
        (xlt("Owner"),          self.info['owner']),
        (xlt("Tablespace"),     self.info['spcname']),
        (xlt("ACL"),            self.info['acl']),
        (xlt("Next Value"),     self.nextval),
        (xlt("Increment"),      self.info['increment_by']),
        (xlt("Min Value"),      self.info['min_value']),
        (xlt("Max Value"),      self.info['max_value']),
        (xlt("Cache"),          self.info['cache_value']),
        (xlt("Cycled"),         self.info['is_cycled'])
      ]

      self.AddProperty(xlt("Description"), self.info['description'])
      
    return self.properties
  
  
  class Dlg(adm.PropertyDialog):
  
    def Go(self):
      pass
     
    def Check(self):
      ok=True
      if not self.node:
        pass
      
      return ok
  
  
nodeinfo= [ { "class" : Sequence, "parents": ["Schema"], "sort": 70, "collection": "Sequences", "pages": ["SqlPage"] } ]    
