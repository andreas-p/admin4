# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import adm
from wh import xlt, YesNo, prettyDate

class Role(adm.Node):
  typename=xlt("Role")
  shortname=xlt("Role")
  
  @staticmethod
  def GetInstances(parentNode):
    instances=[]
    set=parentNode.GetConnection().GetCursor().ExecuteSet("""
      SELECT rolname as name, *,
        (SELECT array_agg(rolname) FROM pg_roles r JOIN pg_auth_members m on r.oid=m.member WHERE m.roleid=u.oid) AS members,
        (SELECT array_agg(rolname) FROM pg_roles r JOIN pg_auth_members m on r.oid=m.roleid WHERE m.member=u.oid) AS memberof
        FROM pg_roles u ORDER BY rolname""")
    if set:
      for row in set:
        if not row:
          break
        instances.append(Role(parentNode, row['name'], row.getDict()))
    return instances
  
  def __init__(self, parentNode, name, info):
    super(Role, self).__init__(parentNode, name)
    self.info=info
    
  def GetIcon(self):
    icons=[]
    if self.info['members']:
      icons.append("Group")
    else:
      icons.append("User")
    return self.GetImageId(icons)
  
  
  def GetProperties(self):
    if not len(self.properties):

      self.properties = [
        (xlt("Name"), self.name, self.GetImageId('Role')),
        (    "OID",   self.info['oid']),
        (xlt("Can Login"), YesNo(self.info['rolcanlogin'])),
        (xlt("Superuser"), YesNo(self.info['rolsuper'])),
        (xlt("Catalog Update"), YesNo(self.info['rolcatupdate'])),
        (xlt("Create DB"), YesNo(self.info['rolcreatedb'])),
        (xlt("Create Role"), YesNo(self.info['rolcreaterole'])),
        (xlt("Inherits rights"), YesNo(self.info['rolinherit'])),
      ]
      until=self.info['rolvaliduntil']
      if not until or until.year == 9999:
        until=xlt("never")
      else:
        until=prettyDate(until)
      self.properties.append((xlt("Expires"), until))
      
      self.AddChildrenProperty(self.info['memberof'], xlt("Member of"), self.GetImageId("Group"))
      self.AddChildrenProperty(self.info['members'], xlt("Members"), self.GetImageId("User"))
      self.AddChildrenProperty(self.info['rolconfig'], xlt("Variables"), -1)

    return self.properties


class RolesPage(adm.NotebookPage):
  name=xlt("Roles")
  order=50
  availableOn="Server"
  roleFlags={'rolcreaterole': 'createRole',
             'rolcreatedb': 'crDb',
             'rolcatupdate': 'catUpd',
             'rolreplication': 'repl'
            }
  
  def Display(self, node, _detached):
    if node != self.lastNode:
      self.lastNode=node

      def members(row):
        d=row['members']
        if d:  return ",".join(d)
      def flags(row):
        fl=[]
        for key, desc in self.roleFlags.items():
          if row.get(key):
            fl.append(desc)
        return" ".join(fl)
        
      add=self.control.AddColumnInfo
      add(xlt("Name"), 20,         colname='name')
      add(xlt("Flags"), 25,        proc=flags)
      add(xlt("Members"), 40,      proc=members)

      values=[]
      
      self.allRoles=node.GetConnection().GetCursor().ExecuteDictList("""
        SELECT rolname as name, *,
          (SELECT array_agg(rolname) FROM pg_roles r JOIN pg_auth_members m on r.oid=m.member WHERE m.roleid=u.oid) AS members,
          (SELECT array_agg(rolname) FROM pg_roles r JOIN pg_auth_members m on r.oid=m.roleid WHERE m.member=u.oid) AS memberof
          FROM pg_roles u ORDER BY rolname""")
      
      for role in self.allRoles:
        # rolsuper, rolcreaterole, colcreatedb, rolcanupdate
        icons=[]
        if role['members']:
          icons.append("group")
        elif role['rolsuper']:
          icons.append('admin')
        else:
          icons.append("user")
        if role['rolcanlogin']:
          icons.append('key')

        icon=self.lastNode.GetImageId(icons)
        values.append( (role, icon))
      self.control.Fill(values, 'name')

pageinfo=[RolesPage]
nodeinfo=[]
#nodeinfo= [ { "class" : Role, "parents": ["Server"], "sort": 70, "collection": xlt("Roles") } ]