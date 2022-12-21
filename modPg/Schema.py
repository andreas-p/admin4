# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from ._objects import DatabaseObject
from ._pgsql import pgQuery
from wh import xlt


class Schema(DatabaseObject):
  typename=xlt("Schema")
  shortname=xlt("Schema")
  refreshOid="nsp.oid"
  
  sysNamespaces=['pg_toast', 'pg_catalog', 'information_schema']
  
  @staticmethod
  def InstancesQuery(parentNode):
    sql=pgQuery("pg_namespace nsp")
    sql.AddCol("nsp.oid, nspacl, nspname as name, pg_get_userbyid(nspowner) AS owner, description")
    sql.AddLeft("pg_description des ON des.objoid=nsp.oid")
    sql.AddWhere("nspname not in (%s)" % ",".join(map(lambda x: "'%s'" % x, Schema.sysNamespaces)))
    sql.AddOrder("nspname")
    return sql


  def GetIcon(self):
    icons=[]
    icons.append("Schema")
    if self.name in self.sysNamespaces:
      icons.append('pg')
    return self.GetImageId(icons)
  
  def GetSchemaOid(self):
    return self.GetOid()

    
  def GetProperties(self):
    if not len(self.properties):

      self.properties = [
        (xlt("Name"),           self.name),
        (  "OID" ,              self.info['oid']),
        (xlt("Owner"),          self.info['owner']),
        (xlt("ACL"),            self.info['nspacl'])
      ]

      self.AddProperty(xlt("Description"), self.info['description'])
    return self.properties


nodeinfo= [ { "class" : Schema, "parents": ["Database"], "sort": 4, "collection": xlt("Schemas"),  } ]    
