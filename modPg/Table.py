# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from _objects import SchemaObject
from _pgsql import pgQuery
import adm
from wh import xlt, shlexSplit
import logger
from _pgsql import quoteIdent, quoteValue

persistenceStr={'p': "persistent", 't': "temporary", 'u': "unlogged" }

    
    
class Table(SchemaObject):
  typename=xlt("Table")
  shortname=xlt("Table")
  refreshOid="rel.oid"
  allGrants="arwdDxt"
  favtype='t'
  relkind='r'

  @staticmethod
  def FindQuery(schemaName, schemaOid, patterns):
    sql=pgQuery("pg_class c")
    sql.AddCol("relkind as kind")
    sql.AddCol("nspname")
    sql.AddCol("relname as name")
    sql.AddCol("n.oid as nspoid")
    sql.AddCol("c.oid")
    sql.AddJoin("pg_namespace n ON n.oid=relnamespace")
    sql.AddWhere("relkind='r'")
    SchemaObject.AddFindRestrictions(sql, schemaName, schemaOid, 'relname', patterns)
    return sql
    
        
  @staticmethod
  def InstancesQuery(parentNode):
    sql=pgQuery("pg_class rel")
    sql.AddCol("rel.oid, relname as name, nspname, ns.oid as nspoid, spcname, pg_get_userbyid(relowner) AS owner, relacl as acl, rel.*")
    if parentNode.GetServer().version < 8.4:
      sql.AddCol("'t' AS relpersistence")
    elif parentNode.GetServer().version < 9.1:
      sql.AddCol("CASE WHEN relistemp THEN 't' ELSE 'p' END AS relpersistence")
    else:
      sql.AddCol("relpersistence")

    sql.AddCol("description")
    sql.AddJoin("pg_namespace ns ON ns.oid=rel.relnamespace")
    sql.AddLeft("pg_tablespace ta ON ta.oid=rel.reltablespace")
    sql.AddLeft("pg_description des ON (des.objoid=rel.oid AND des.objsubid=0)")
    sql.AddLeft("pg_constraint c ON c.conrelid=rel.oid AND c.contype='p'")
    sql.AddWhere("relkind", 'r')
    sql.AddWhere("relnamespace", parentNode.parentNode.GetOid())
    sql.AddOrder("CASE WHEN nspname='%s' THEN ' ' else nspname END" % "public")
    sql.AddOrder("relname")
    return sql
  

  def GetIcon(self):
    icons=[]
    icons.append("Table")
    if self.GetOid() in self.GetDatabase().favourites:
      icons.append('fav')
    return self.GetImageId(icons)

  def __init__(self, parentNode, info):
    super(Table, self).__init__(parentNode, info)
    self.rowcount=xlt("Not counted")
    self.Init()
    
  def Refresh(self):
    self.rowcount=xlt("Not counted")
    self.DoRefresh()
    
  def Init(self):
    self.columns=[]
    self.constraints=None
      
  def GetProperties(self):
    if not len(self.properties):

      self.properties = [
        (xlt("Name"),           self.info['name']),
        (xlt("Namespace"),      self.info['nspname']),
        (    "OID" ,            self.info['oid']),
        (xlt("Owner"),          self.info['owner']),
        (xlt("Tablespace"),     self.info['spcname']),
        (xlt("Persistence"),    "%s (%s)" % (self.info['relpersistence'], xlt(persistenceStr.get(self.info['relpersistence'], "unknown")))),
        (xlt("Rows (estimated)"), int(self.info['reltuples'])),
        (xlt("Rows (counted)"), self.rowcount),
        (xlt("ACL"),            self.info['acl'])
      ]

      self.AddProperty(xlt("Description"), self.info['description'])
    return self.properties


  def GetStatisticsQuery(self):
    cols=[( 'seq_scan',       xlt("Sequential Scans") ), 
          ( 'seq_tup_read',   xlt("Sequential Tuples Read") ),
          ( 'idx_scan',       xlt("Index scans") ), 
          ( 'idx_tup_fetch',  xlt("Index Tuples Fetched") ),
          ( 'n_tup_ins',      xlt("tuples inserted") ),
          ( 'n_tup_upd',      xlt("tuples updated") ),
          ( 'n_tup_del',      xlt("tuples deleted") ),
          ( 'heap_blks_read', xlt("Heap Blocks Read") ),
          ( 'heap_blks_hit',  xlt("Heap Blocks Hit") ),
          ( 'idx_blks_read',  xlt("Index Blocks Read") ),
          ( 'idx_blks_hit',   xlt("Index Blocks Hit") ),
          ( 'toast_blks_read',xlt("Toast Blocks Read") ), 
          ( 'toast_blks_hit', xlt("Toast Blocks Hit") ),
          ( 'tidx_blks_read', xlt("Toast Index Blocks Read") ),
          ( 'tidx_blks_hit',  xlt("Toast Index Blocks Hit") ),
          ( 'pg_size_pretty(pg_relation_size(stat.relid))', xlt("Table Size") ),
          ( """CASE WHEN cl.reltoastrelid = 0 THEN '%s' ELSE pg_size_pretty(pg_relation_size(cl.reltoastrelid)+ 
          COALESCE((SELECT SUM(pg_relation_size(indexrelid))
                      FROM pg_index WHERE indrelid=cl.reltoastrelid)::int8, 0)) END""" %xlt("None"), xlt("Toast Table Size") ), 
          ( """pg_size_pretty(COALESCE((SELECT SUM(pg_relation_size(indexrelid))
          FROM pg_index WHERE indrelid=stat.relid)::int8, 0))""", xlt("Index Size"))
          ]

    return """
      SELECT %(cols)s
        FROM pg_stat_all_tables stat
        JOIN pg_statio_all_tables statio ON stat.relid = statio.relid
        JOIN pg_class cl ON cl.oid=stat.relid
       WHERE stat.relid = %(relid)d
       """ % {'relid': self.GetOid(), 
              'cols': self.GetServer().ExpandColDefs(cols)} 
 
 
  def populateColumns(self):
      if not self.columns:
        self.columns = self.GetCursor().ExecuteDictList("""
          SELECT att.*, format_type(atttypid, atttypmod) as typename, t.typname, t.typcategory, t.typbasetype, 
              pg_get_expr(adbin, attrelid) as adsrc, 
              description, cs.relname AS sername, ns.nspname AS serschema
            FROM pg_attribute att
            JOIN pg_type t ON att.atttypid=t.oid
            LEFT OUTER JOIN pg_attrdef def ON adrelid=attrelid AND adnum=attnum
            LEFT OUTER JOIN pg_description des ON des.objoid=attrelid AND des.objsubid=attnum
            
            LEFT OUTER JOIN (pg_depend JOIN pg_class cs ON objid=cs.oid AND cs.relkind='S') ON refobjid=attrelid AND refobjsubid=attnum
            LEFT OUTER JOIN pg_namespace ns ON ns.oid=cs.relnamespace
           WHERE attrelid = %(attrelid)d
             AND attnum > 0
             AND attisdropped IS FALSE
           ORDER BY attnum""" % { 'attrelid': self.GetOid()})
 
 
  @staticmethod
  def getConstraintQuery(oid):
    return """
        SELECT 1 AS conclass, CASE WHEN indisprimary THEN 'primarykey' ELSE 'index' END as type, indexrelid as oid, 
               CASE WHEN nspname='%(defaultNamespace)s' THEN '' else nspname||'.' END || relname AS fullname,
               array_agg(attname) as colnames, description,
               indisprimary, indisunique, null::bool as condeferrable, null::bool as condeferred,
               null::text as reftable, null as refcolnames
          FROM pg_index i
          JOIN pg_class c ON indexrelid=c.oid
          JOIN pg_namespace nsp on relnamespace=nsp.oid
          LEFT JOIN pg_attribute a ON attrelid=indrelid AND attnum IN (SELECT unnest(indkey))
          LEFT JOIN pg_description ON objoid=indexrelid
         WHERE indrelid=%(relid)d
         GROUP BY indexrelid, nspname, relname, indisprimary, indisunique, description
        UNION
        SELECT 2, 'foreignkey', conrelid, conname,
               array_agg(a.attname), description,
               null, null, condeferrable, condeferred,
               CASE WHEN nspname='%(defaultNamespace)s' THEN '' else nspname||'.' END || relname,
               array_agg(r.attname)
          FROM pg_constraint
          LEFT JOIN pg_attribute a ON a.attrelid=conrelid AND a.attnum IN (SELECT unnest(conkey))
          LEFT JOIN pg_description ON objoid=conrelid
          JOIN pg_class c on c.oid=confrelid
          JOIN pg_namespace nsp on relnamespace=nsp.oid
          LEFT JOIN pg_attribute r ON r.attrelid=confrelid AND r.attnum IN (SELECT unnest(confkey))
         WHERE conrelid=%(relid)s
         GROUP BY conrelid, conname, condeferrable, condeferred, relname, nspname, description
        ORDER BY 1, 7 DESC, 4
              """ % { 'relid': oid, 'defaultNamespace': "public" }
  
  def populateConstraints(self):
    if self.constraints == None:
      self.constraints=self.GetCursor().ExecuteDictList(self.getConstraintQuery(self.GetOid()))
      

class ColumnPanel(adm.NotebookPanel):
  name=xlt("Column")

  def __init__(self, dlg, notebook):
    adm.NotebookPanel.__init__(self, dlg, notebook)
    self.Bind("Length Precision", self.OnPrecChange)
    self.Bind("DataType", self.OnTypeChange)
    self.BindAll()
    
  def OnPrecChange(self, evt):
    self.OnCheck(evt)
  
  def OnTypeChange(self, evt):
    self.OnCheck(evt)
    
  def Go(self):
    cd=self.dialog.colDef
    self.ColName = cd['attname']
    self.NotNull = cd['attnotnull']
    self.DefaultVal=cd['adsrc']
    self.Description=cd['description']
    self.Statistics = cd['attstattarget']
    type=cd['typename']
    ci=type.find('(')
    if (ci > 0):
      prec=type[ci+1:-1].split(',')
      self.Length=int(prec[0])
      if len(prec) > 1:
        self.Precision = int(prec[1])
    
    types=self.dialog.node.GetCursor().ExecuteDictList("SELECT oid, typname FROM pg_type WHERE typcategory=%s ORDER BY oid" % quoteValue(cd['typcategory']))
    for t in types:
      self["DataType"].AppendKey(t['oid'], t['typname'])
    
    self.DataType=cd['atttypid']
    
    if cd['atttypid'] in (20, 23) or cd['typbasetype'] in (20,23):
      if cd['sername']:
        if cd['serschema'] != 'public':
          sn="%(serschema)s.%(sername)s" % cd
        else:
          sn=cd['sername']
          
        self['Sequence'].Append(sn)
        self.Sequence=sn
    else:
      self['Sequence'].Disable()
      
      
    if cd['typcategory'] == 'S' and self.dialog.GetServer().version >= 9.1:
      colls=self.dialog.node.GetCursor().ExecuteDictList(
                                            "SELECT oid,collname FROM pg_collation WHERE collencoding IN (-1, %d) ORDER BY oid" 
                                                      % self.dialog.node.GetDatabase().info['encoding'])
      for c in colls:
        self['Collation'].AppendKey(c['oid'], c['collname'])
      
      if cd['attcollation']:
        self.Collation = cd['attcollation']
      
    else:
      self['Collation'].Disable()
    self.SetUnchanged()
    
  def GetSql(self):
    sql=[]
    params={ "colname": quoteIdent(self.ColName), "oldcol": quoteIdent(self['ColName'].unchangedValue)}

    if self.HasChanged("ColName"):
      sql.append("RENAME COLUMN %(oldcol)s TO %(colname)s" % params)

    if self.HasChanged("NotNull"):
      if self.NotNull:
        params['val'] = "SET"
      else:
        params['val'] = "DROP"
      sql.append("ALTER COLUMN %(colname)s %(val)s NOT NULL" % params)
    if self.HasChanged("Statistics"):
      params['val'] = self.Statistics
      sql.append("ALTER COLUMN %(colname)s SET STATISTICS %(val)d" % params)
      
    # type, len, prec, collate
#    if self.HasChanged("Collation"):
#      params['val'] = self["Collation"].GetValue()
#      sql.append("ALTER COLUMN %(colname)s SET COLLATE \"%(val)d\";" % params)
      
    if sql:
      return "ALTER TABLE %s\n   %s;" % (self.dialog.node.NameSql() , ",\n   ".join(sql))
    return ""
  
  
class PrivilegePanel(adm.NotebookPanel):
  name=xlt("Privileges")
  privString={ 'a': "INSERT",
               'r': "SELECT",
               'w': "UPDATE",
               'd': "DELETE",
               'D': "TRUNCATE",
               'x': "REFERENCE",
               't': "TRIGGER",
               'U': "USAGE",
               'C': "CREATE",
               'T': "TEMP",
               'c': "CONNECT",
               'X': "EXECUTE",
               }
  @classmethod
  def CreatePanel(cls, dlg, notebook):
    if dlg.GetServer().version < 8.4:
      return None 
    return cls(dlg, notebook)

  def Go(self):
    pl=self['PrivList']
    pl.ClearAll()
    pl.AddColumnInfo(xlt("Usr/Group"), 20)
    pl.AddColumnInfo(xlt("Privilege"), -1)
    acls=self.dialog.colDef['attacl']
    if acls:
      for acl in shlexSplit(acls[1:-1], ','):
        up = shlexSplit(acl, '=')
        if len(up) == 1:
          priv=up[0]
          usr="public"
        else:
          usr=up[0]
          priv=up[1]
        up=shlexSplit(priv, '/')
        priv=up[0]
        if len(up) > 1: grantor=up[1]
        else:           grantor=None
        print usr, priv, grantor
    pl.Show()       

  
class SecurityPanel(adm.NotebookPanel):
  name=xlt("Security Labels")
  @classmethod
  def CreatePanel(cls, dlg, notebook):
    if dlg.GetServer().version < 9.1:
      return None 
    return cls(dlg, notebook)


class SqlPanel(adm.NotebookPanel):
  name=xlt("SQL")

  def Display(self):
    sql=self.dialog.GetSql()
    if sql:
      self.SqlText=sql
    else:
      self.SqlText=xlt("-- No change")
    self.Show()



class Column(adm.PagedPropertyDialog):
  name=xlt("Column")
  privFlags='arwx'
#  panelClasses=[ColumnPanel, PrivilegePanel, SecurityPanel, SqlPanel]
  panelClasses=[ColumnPanel, SqlPanel]

  def __init__(self, parentWin, node, colDef):
    adm.PagedPropertyDialog.__init__(self, parentWin, node, None)
    self.colDef=colDef

  def GetSql(self):
    sql=""
    for panel in self.panels:
      if hasattr(panel, "GetSql"):
        sql += panel.GetSql()
    return sql

  def Save(self):
    return True
  
  
class ColumnsPage(adm.NotebookPage):
  name=xlt("Columns")
  order=1
    
  def Display(self, node, _detached):
    if node != self.lastNode:
      def _typename(row):
        n= [row['typename'], ['NULL', 'NOT NULL'][row['attnotnull']] ]
        default=row['adsrc']
        if default != None:
          if default == "nextval('%s_%s_seq'::regclass)" % (node.info['relname'], row['attname']):
            if n[0] == "integer":
              n[0] = "serial"
            elif n[0] == "bigint":
              n[0] = "bigserial"
            else:
              logger.debug("Unknown serial type %s for %s", n[0], default)
              n.append("DEFAULT")
              n.append(default)
          else:
            n.append("DEFAULT")
            n.append(default)
        return "  ".join(n)

      self.lastNode=node
      self.control.ClearAll()
      
      add=self.control.AddColumnInfo
      add(xlt("Name"), 20,         colname='attname')
      add(xlt("Type"), -1,         proc=_typename)
      self.RestoreListcols()

      node.populateColumns()
      icon=node.GetImageId('column')
      values=[]
      for col in node.columns:
        values.append( (col, icon))
      self.control.Fill(values, 'attname')

  def OnItemDoubleClick(self, evt):
    adm.DisplayDialog(Column, self.control, self.lastNode, self.lastNode.columns[evt.Index])
      
class ConstraintPage(adm.NotebookPage):
  name=xlt("Constraints")
  order=2
  
  def Display(self, node, _detached):
    if node != self.lastNode:
      self.lastNode=node
      
      def _getDetails(row):
        info=[]
        if row['type'] == 'primarykey':
            info.append('PRIMARY')
        elif row['type'] == 'index':
          if row['indisunique']:
            info.append('UNIQUE')
        elif row['type'] == 'foreignkey':
          info.append(row['reftable'])
          info.append("(%s)" % ",".join(row['refcolnames']))
        elif row['type'] == 'check':
          pass
        return "".join(info)
      
      add=self.control.AddColumnInfo
      add(xlt("Name"), 10,         colname='fullname')
      add(xlt("Columns"), 15,      colname='colnames', proc=lambda x: ", ".join(x))
      add(xlt("Details"), 15,      proc=_getDetails)
      add(xlt("Description"), -1,  colname='description')
      self.RestoreListcols()

      node.populateConstraints()
      
      values=[]
      for con in node.constraints:
        icon = node.GetImageId(con['type'])
        values.append( (con, icon) )
      self.control.Fill(values, 'fullname')
   
nodeinfo= [ { "class" : Table, "parents": ["Schema"], "sort": 10, "collection": "Tables", "pages": [ColumnsPage, ConstraintPage, "StatisticsPage" , "SqlPage"] } ]    
pageinfo=[ColumnsPage, ConstraintPage]


class RowCount:
  name=xlt("Count")
  help=xlt("Count rows in table")
  

  @staticmethod
  def OnExecute(_parentWin, node):
    node.rowcount=node.ExecuteSingle("SELECT COUNT(1) FROM ONLY %s" % node.NameSql())
    return True


menuinfo = [ 
            { "class" : RowCount, "nodeclasses" : Table, 'sort': 80 },
             ]
