# The Admin4 Project
# (c) 2013-2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


from ._objects import SchemaObject
from ._pgsql import pgQuery
import adm
from wh import xlt, shlexSplit, localTimeMillis
import logger
from ._pgsql import quoteIdent, quoteValue

persistenceStr={'p': "persistent", 't': "temporary", 'u': "unlogged" }

    
    
class Table(SchemaObject):
  typename=xlt("Table")
  shortname=xlt("Table")
  refreshOid="rel.oid"
  allGrants="arwdDxt"
  favtype='t'
  relkind='r'
  relispartition=False

  @classmethod
  def FindQuery(cls, schemaName, schemaOid, patterns):
    sql=pgQuery("pg_class c")
    sql.AddCol("relkind as kind")
    sql.AddCol("nspname")
    sql.AddCol("relname as name")
    sql.AddCol("n.oid as nspoid")
    sql.AddCol("c.oid")
    sql.AddJoin("pg_namespace n ON n.oid=relnamespace")
    sql.AddWhere("relkind = '%s'" % cls.relkind)
    SchemaObject.AddFindRestrictions(sql, schemaName, schemaOid, 'relname', patterns)
    return sql
    
        
  @classmethod
  def InstancesQuery(cls, parentNode):
    sql=pgQuery("pg_class rel")
    sql.AddCol("rel.oid, relname as name, nspname, ns.oid as nspoid, spcname, pg_get_userbyid(relowner) AS owner, relacl as acl, rel.*")
    if parentNode.GetServer().version < 8.4:
      sql.AddCol("'t' AS relpersistence")
    elif parentNode.GetServer().version < 9.1:
      sql.AddCol("CASE WHEN relistemp THEN 't' ELSE 'p' END AS relpersistence")
    else:
      sql.AddCol("relpersistence")
    if parentNode.GetServer().version >= 10:
      sql.AddCol("pg_get_expr(relpartbound, rel.oid, true) AS relpartbound")
      sql.AddLeft("pg_partitioned_table pt ON partrelid=rel.oid")
      sql.AddCol("pg_get_expr(partexprs, partrelid, true) AS partexprs")
      sql.AddCol('partstrat')
      sql.AddCol("(SELECT array_to_string(array_agg(attname), ', ') FROM pg_attribute WHERE attnum=any(partattrs) AND attrelid=partrelid) AS partattrs")
      if cls.relispartition:
        sql.AddWhere("relispartition")
      else:
        sql.AddWhere("not relispartition")

    sql.AddCol("description")
    sql.AddJoin("pg_namespace ns ON ns.oid=rel.relnamespace")
    sql.AddLeft("pg_tablespace ta ON ta.oid=rel.reltablespace")
    sql.AddLeft("pg_description des ON (des.objoid=rel.oid AND des.objsubid=0)")
    sql.AddLeft("pg_constraint c ON c.conrelid=rel.oid AND c.contype='p'")
    sql.AddWhere("relkind ='%s'" % cls.relkind)
    sql.AddWhere("relnamespace", cls.GetParentSchemaOid(parentNode))
    sql.AddOrder("CASE WHEN nspname='%s' THEN ' ' else nspname END" % "public")
    sql.AddOrder("relname")
    return sql

  def GetIcon(self):
    icons=[self.__class__.__name__]
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
      ]
      if self.relkind == 'p':
        if self.info['partstrat'] == 'r':
          key="RANGE(%s)" % self.info['partattrs']
        else:
          key=self.info['partexprs']
        self.AddProperty(xlt("Partition Key"), key)
      elif self.relispartition:
        self.AddProperty(xlt("Partition of Table"), self.GetPartitionMaster())
        self.AddProperty(xlt("Partition"), self.info['relpartbound'])

      self.AddProperty(xlt("ACL"), self.info['acl'])
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
 
 
  def _getRefTables(self, col, refcol):
      rels=self.GetCursor().ExecuteDictList("""
        SELECT relname AS name, nspname
          FROM pg_depend
          JOIN pg_class r ON r.oid=%s
          JOIN pg_namespace n ON n.oid=relnamespace
         WHERE classid=to_regclass('pg_class')
           AND refclassid=to_regclass('pg_class')
           AND deptype='a' AND relkind IN ('r', 'p')
           AND %s=%s
      """ % (refcol, col, self.info['oid']))
      return rels
    
  def GetSql(self):
    self.populateColumns()
    cols=[]
    for col in self.columns:
      cols.append(quoteIdent(col['attname']) + ' ' + self.colTypeName(col));

    constraints=[]
    self.populateConstraints()

    for constraint in self.constraints:
      c=[]
      for col in constraint['colnames']:
        c.append(quoteIdent(col))
      if constraint['indisprimary']:
        cols.append("PRIMARY KEY("+ ", ".join(c)+")")
      else:
        if constraint['type'] == 'index':
          info=['CREATE']
          if constraint['indisunique']:
            info.append('UNIQUE')
          info.append("INDEX")
          info.append(constraint['fullname'])
          info.append('ON ' + self.NameSql())
          info.append("(%s)" % ",".join(c))
          constraints.append(" ".join(info) + ";")
        elif constraint['type'] == 'foreignkey':
          info=[f"ALTER TABLE {self.NameSql()} ADD CONSTRAINT {constraint['fullname']}"]
          info.append(f"\n  FOREIGN KEY ({','.join(constraint['colnames'])}) REFERENCES {quoteIdent(constraint['reftable'])}")
          info.append("(%s)" % ",".join(map(quoteIdent, constraint['refcolnames'])))
          constraints.append(" ".join(info) +";")
        elif constraint['type'] == 'check':
          pass


    sql=[]
    if self.relispartition:
      sql.append("CREATE TABLE " + self.NameSql() + " PARTITION OF " + self.GetPartitionMaster())
      sql.append("  " + self.info['relpartbound']+";")
    else:
      pi=""
      if (self.relkind == 'p'):
        if self.info['partstrat'] == 'r':
          pi=" PARTITION BY RANGE(%s)" % self.info['partattrs']
        else:
          pi=" PARTITION BY %s" % self.info['partexprs']
      sql.append("CREATE TABLE " + self.NameSql())
      sql.append("(");
      sql.append("  " + ",\n  ".join(cols))
      if (self.info.get('relhasoids')):
        sql.append(") WITH OIDs%s;" % pi)
      else:                    
        sql.append(")%s;" % pi)
      sql.append("")          
      sql.append("ALTER TABLE " + self.NameSql() + " OWNER TO " + quoteIdent(self.info['owner']) + ";")
      sql.extend(constraints)
    sql.extend(self.getAclDef('relacl', "arwdDxt"))
    sql.extend(self.getCommentDef())
    return "\n".join(sql); 
  
  
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
   
  def colTypeName(self, col):   
    n= [col['typename'], ['NULL', 'NOT NULL'][col['attnotnull']] ]
    default=col['adsrc']
    if default != None:
      if default == "nextval('%s_%s_seq'::regclass)" % (self.info['relname'], col['attname']):
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

class ColumnPanel(adm.NotebookPanel):
  name=xlt("Column")

  def __init__(self, dlg, notebook):
    adm.NotebookPanel.__init__(self, dlg, notebook)
    self.typeInfo={}
    self.Bind("DataType", self.OnTypeChange)
    self.BindAll("DataType")
    
  def OnTypeChange(self, evt):
    precFlag=self.typeInfo.get(self.DataType)
    self.EnableControls("Length", precFlag>0)
    self.EnableControls("Precision", precFlag==2)
    self.OnCheck(evt)
    
  def Go(self):
    cd=self.dialog.colDef
    self.ColName = cd['attname']
    self.NotNull = cd['attnotnull']
    self.DefaultVal=cd['adsrc']
    self.Description=cd['description']
    self.Statistics = cd['attstattarget']

    ctype=cd['typename']
    ci=ctype.find('(')
    if (ci > 0):
      prec=ctype[ci+1:-1].split(',')
      self.Length=int(prec[0])
      if len(prec) > 1:
        self.Precision = int(prec[1])
    self.typeInfo={}
    types=self.dialog.node.GetCursor().ExecuteDictList("SELECT oid, typname, typmodin FROM pg_type WHERE typcategory=%s ORDER BY oid" % quoteValue(cd['typcategory']))
    for t in types:
      oid=t['oid']
      self["DataType"].AppendKey(t['oid'], t['typname'])
      if t['typmodin'] != '-':
        precFlag=1
      else:
        precFlag=0
      self.typeInfo[oid] = precFlag
    
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
      
    if self.dialog.GetServer().version >= 9.1:
      if cd['typcategory'] == 'S':
        colls=self.dialog.node.GetCursor().ExecuteDictList(
                                            "SELECT oid,collname FROM pg_collation WHERE collencoding IN (-1, %d) ORDER BY oid" 
                                                      % self.dialog.node.GetDatabase().info['encoding'])
        for c in colls:
          self['Collation'].AppendKey(c['oid'], c['collname'])
      
        if cd['attcollation']:
          self.Collation = cd['attcollation']
      else:
        self['Collation'].Disable()
    else:
      self.ShowControls("Collation", False)
    self.Comment=cd['description']
      
    # Not yet supported
    self.ShowControls("Sequence Storage Statistics", False)
    self.OnTypeChange(None)

    self.SetUnchanged()
    
  def Check(self):
    if self.typeInfo.get(self.DataType) == 2:
      return self.CheckValid(True, self.Precision <= self.Length, xlt("Precision must be <= Length"))
    return True
  
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
      
    if self.HasChanged("DefaultVal"):
      if self.DefaultVal:
        params['default'] = self.DefaultVal
        sql.append("ALTER COLUMN %(colname)s SET DEFAULT %(default)s" % params)
      else:
        sql.append("ALTER COLUMN (%colname)s DROP DEFAULT" % params)
    if self.HasChanged("DataType Collation Length Precision"):
      
      params['type']=self['DataType'].GetValue()
      n="ALTER COLUMN %(colname)s TYPE %(type)s" % params
      precFlag=self.typeInfo.get(self.DataType)
      if precFlag and self.Length:
        n += "(%d" % self.Length
        if precFlag == 2 and self['Precision'].GetValue():
          n += ", %d" % self.Precision
        n += ")"
      if self.HasChanged("Collation"):
        n += " COLLATE %s" % quoteIdent(self['Collation'].GetValue())
      sql.append(n)
    if self.HasChanged("Statistics"):
      params['val'] = self.Statistics
      sql.append("ALTER COLUMN %(colname)s SET STATISTICS %(val)d" % params)
      
    # type, len, prec, collate
#    if self.HasChanged("Collation"):
#      params['val'] = self["Collation"].GetValue()
#      sql.append("ALTER COLUMN %(colname)s SET COLLATE \"%(val)d\";" % params)
      
    if sql:
      sql=["ALTER TABLE %s\n   %s;" % (self.dialog.node.NameSql() , ",\n   ".join(sql))]
    
    if self.HasChanged('Comment'):
      params['tabname'] = self.dialog.node.NameSql()
      params['comment'] = quoteValue(self.Comment)
      sql.append("COMMENT ON COLUMN %(tabname)s.%(colname)s IS %(comment)s" % params)
    if sql:
      return "\n".join(sql)
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
          _usr="public"
        else:
          _usr=up[0]
          priv=up[1]
        up=shlexSplit(priv, '/')
        priv=up[0]
        if len(up) > 1: _grantor=up[1]
        else:           _grantor=None
#        print (usr, priv, grantor)
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
    sql=self.GetSql()
    if sql:
      self.startTime=localTimeMillis();
      self.node.GetCursor().Execute(sql)
    return True
  
  
class ColumnsPage(adm.NotebookPage):
  name=xlt("Columns")
  order=1
    
  def Display(self, node, _detached):
    if node != self.lastNode:
      def _typename(row):
        return node.colTypeName(row)

      self.lastNode=node
      self.control.ClearAll()
      
      self.control.AddColumnInfo(xlt("Name"), 20,         colname='attname')
      self.control.AddColumnInfo(xlt("Type"), 30,         proc=_typename)
      self.control.AddColumnInfo(xlt("Comment"), -1,      colname='description')
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
      
      self.control.AddColumnInfo(xlt("Name"), 10,         colname='fullname')
      self.control.AddColumnInfo(xlt("Columns"), 15,      colname='colnames', proc=lambda x: ", ".join(x))
      self.control.AddColumnInfo(xlt("Details"), 15,      proc=_getDetails)
      self.control.AddColumnInfo(xlt("Description"), -1,  colname='description')
      self.RestoreListcols()

      node.populateConstraints()
      
      values=[]
      for con in node.constraints:
        icon = node.GetImageId(con['type'])
        values.append( (con, icon) )
      self.control.Fill(values, 'fullname')
   
class Partition(Table):
  relkind='r'
  typename=xlt("Partition")
  shortname=xlt("Partition")
  relispartition=True
  
  @classmethod
  def CheckPresent(cls, parentNode):
    return parentNode.GetServer().version >= 10
  
  def GetPartitionMaster(self):
    if not hasattr(self, 'partitionMaster'):
      rels=self._getRefTables('objid', 'refobjid')
      self.partitionMaster= self.FullName(rels[0])
    return self.partitionMaster


class PartitionedTable(Table):
  relkind='p'
  typename=xlt("Partitioned Table")
  shortname=xlt("Partitioned Table")

  @classmethod
  def CheckPresent(cls, parentNode):
    return parentNode.GetServer().version >= 10

  def GetProperties(self):
    if not len(self.properties):
      super(PartitionedTable, self).GetProperties()
      rels=self._getRefTables('refobjid', 'objid')
      partitions=list(map(self.FullName, rels))
      self.AddProperty(xlt("Partitions"), partitions)
    return self.properties



nodeinfo= [ { "class" : Table, "parents": ["Schema"], "sort": 10, "collection": "Tables", "pages": [ColumnsPage, ConstraintPage, "StatisticsPage" , "SqlPage"] },
#            { "class" : Partition, "parents": ["Schema"], "sort": 11, "collection": "Partitions", "pages": [ColumnsPage, ConstraintPage, "StatisticsPage" , "SqlPage"] },
            { "class" : Partition, "parents": ["PartitionedTable"], "sort": 11, "pages": [ColumnsPage, ConstraintPage, "StatisticsPage" , "SqlPage"] },
            { "class" : PartitionedTable, "parents": ["Schema"], "sort": 12, "collection": "Partitioned Tables", "pages": [ColumnsPage, ConstraintPage, "StatisticsPage" , "SqlPage"] },
            ]    
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


