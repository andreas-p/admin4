# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from _objects import DatabaseObject, Query
from wh import xlt


class Schema(DatabaseObject):
  typename=xlt("Schema")
  shortname=xlt("Schema")
  refreshOid="nsp.oid"
  
  @staticmethod
  def InstancesQuery(parentNode):
    sql=Query("pg_namespace nsp")
    sql.AddCol("nsp.oid, *, nspname as name, pg_get_userbyid(nspowner) AS owner, description")
    sql.AddLeft("pg_description des ON des.objoid=nsp.oid")
    sql.AddWhere("(nsp.oid=2200 OR nsp.oid > %d)" % parentNode.GetServer().GetLastSysOid())
    sql.AddOrder("nspname")
    return sql


  def GetIcon(self):
    icons=[]
    icons.append("Schema")
    oid=self.GetOid()
    if oid <= self.GetServer().GetLastSysOid() and oid != 2200:
      icons.append('pg')
    return self.GetImageId(icons)

    
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
