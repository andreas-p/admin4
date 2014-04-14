# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


# http://initd.org/psycopg/docs/
import psycopg2
import select
import logger
import adm
import threading
from wh import xlt

class SqlException(adm.ServerException):
  def __init__(self, sql, error):
    logger.querylog(sql, error=error)
    self.error=error
    self.sql=sql
    Exception.__init__(self, sql, error)
  def __str__(self):
    return self.error

class pgCursorResult:
  def __init__(self, cur, colNames=None):
    self.cur=cur
    if colNames:
      self.colNames=colNames
    else:
      self.colNames=[]
      if cur.description: 
        for d in cur.description:
          self.colNames.append(d[0])
      
      
class pgRow(pgCursorResult):
  def __init__(self, cur, row, colNames=None):
    pgCursorResult.__init__(self, cur, colNames)
    self.row=row

  def getDict(self):
    d={}
    for i in range(len(self.colNames)):
      d[self.colNames[i]] = self.row[i]
    return d
  
  def __str__(self):
    cols=[]
    for i in range(len(self.colNames)):
      val=self.row[i]
      val=str(val)
      cols.append("%s=%s" % (self.colNames[i], val))
      
    return "( %s )" % ",".join(cols)
  
  def hasAttr(self, colName):
    try:
      self.colNames.index(colName)
      return True
    except:
      return False
  
  def __getitem__(self, colName):
    try:
      if isinstance(colName, (str, unicode)):
        i=self.colNames.index(colName)
      else:
        i=colName
        colName="#%d" % i
      val=self.row[i]
    except Exception as _e:
      logger.debug("Column %s not found" % colName)
      return None
    return val


class pgRowset(pgCursorResult):
  def __init__(self, cur, autocommit=True):
    pgCursorResult.__init__(self, cur)
    self.autocommit=autocommit
    self.__fetchone()
    
  def GetRowcount(self):
    return self.cur.rowcount
  
  def __fetchone(self):
    if self.cur.rowcount > 0:
      row = self.cur.fetchone()
    else:
      row=None
    if row:
      self.curRow = pgRow(self.cur, row, self.colNames)
    else:
      self.curRow=None

  def HasMore(self):
    return self.curRow != None
          
  def Next(self):
    row=self.curRow
    if row:
      self.__fetchone()
    else:
      if self.autocommit:
        conn=self.cur.connection
        if conn.async:
          self.cur.execute("COMMIT")
          while conn.isexecuting():
            _state = conn.poll()
        else:  
          conn.commit()
    return row 
  
  def getDict(self):
    d={}
    for row in self:
      d[row[0]] = row.getDict()
    return d

  def getDictList(self):
    d=[]
    for row in self:
      d.append(row.getDict())
    return d

  def getList(self):
    d=[]
    for row in self:
      d.append(row[0])
    return d

  def __iter__(self):
    class RowsetIterator:
      def __init__(self, outer):
        self.outer=outer
      def __iter__(self):
        return self
      
      def next(self):
        row=self.outer.Next()
        if row:
          return row
        else:
          raise StopIteration()
        
    return RowsetIterator(self)    
  
  
  
class pgConnection:
  def __init__(self, node, dbname, async=True, application=None):
    self.node=node
    self.lastError=None
    passwd=node.GetServer().password
    self.conn=self.cur=None  

    if not application:
      application="Admin4 browser"
    try:
      self.conn=psycopg2.connect(host=node.GetServer().address, port=node.GetServer().port,
                                 application_name=application, 
                                 database=dbname, user=node.GetServer().user, password=passwd, async=async)
      self.wait("Connect")
      self.cur=self.conn.cursor()
    except Exception as e:
      self.lastError = str(e)
      self.conn=self.cur=None  
      raise adm.ConnectionException(self.node, xlt("Connect"), self.lastError)   

    
  def disconnect(self):
    if self.conn:
      self.conn.close()
      self.conn=None
      self.cur=None

  def execute(self, cmd, args=None):
    if args:
      if isinstance(args, list):
        args=tuple(args)
      elif isinstance(args, tuple):
        pass
      else:
        args=(args,)
        
    try:
      self.cur.execute(cmd, args)
    except Exception as e:
      self._handleException(e)
    return True

  def _handleException(self, e):
    if self.cur and self.cur.query:
      cmd=self.cur.query
    else:
      cmd=None
    errlines=str(e)
    self.lastError=errlines
    logger.querylog(cmd, error=errlines)
    adm.StopWaiting(adm.mainframe)
    if self.conn and self.conn.closed:
      self.disconnect()
    raise SqlException(cmd, errlines)

  def wait(self, spot=""):
    if self.conn.async:
      while self.conn.isexecuting():
        try:
          state = self.conn.poll()
        except Exception as e:
          self._handleException(e)
          return False
          
        if state == psycopg2.extensions.POLL_OK:
          return True
        elif state == psycopg2.extensions.POLL_WRITE:
          select.select([], [self.conn.fileno()], [])
        elif state == psycopg2.extensions.POLL_READ:
          select.select([self.conn.fileno()], [], [])
        else:
          raise adm.ConnectionException(self.node, xlt("WAIT %s" % spot), self.lastError) 
    return False

  def isRunning(self):
    return self.conn.poll() != psycopg2.extensions.POLL_OK
  
  
  def HasFailed(self):
    return self.conn == None or self.conn.closed

 
  def GetPid(self):
    return self.conn.get_backend_pid()
  
  def Rollback(self):
    self.cur.execute("ROLLBACK")
    self.wait("ROLLBACK")
  
  def Commit(self):
    self.cur.execute("COMMIT")
    self.wait("COMMIT")
  
  
  def ExecuteList(self, cmd, args=None, autocommit=True):
    rowset=self.ExecuteSet(cmd, args, autocommit)
    if rowset:
      return rowset.getList()
    return None
  
  def ExecuteDictList(self, cmd, args=None, autocommit=True):
    rowset=self.ExecuteSet(cmd, args, autocommit)
    if rowset:
      return rowset.getDictList()
    return None
  
  def ExecuteSet(self, cmd, args=None, autocommit=True):
    frame=adm.StartWaiting()
    try:
      self.execute(cmd, args)
      self.wait("ExecuteSet")
      rowset=pgRowset(self.cur, autocommit)
      logger.querylog(self.cur.query, result="%d rows" % rowset.GetRowcount())
      adm.StopWaiting(frame)
      return rowset
    except Exception as e:
      adm.StopWaiting(frame, e)
      raise e
    
    
  def ExecuteRow(self, cmd, args=None):
    frame=adm.StartWaiting()
    try:
      self.execute(cmd, args)
      self.wait("ExecuteRow")
      row=self.cur.fetchone()
      adm.StopWaiting(frame)
    except Exception as e:
      adm.StopWaiting(frame, e)
      raise e
    
    if row:
      row=pgRow(self.cur, row)
      logger.querylog(self.cur.query, result=str(row))
      return row
    return None
    
  
  
  def ExecuteSingle(self, cmd, args=None):
    frame=adm.StartWaiting()
    try:
      self.execute(cmd, args)
      self.wait("ExecuteSingle")
      try:
        row=self.cur.fetchone()
      except:
        row=None
      adm.StopWaiting(frame)
    except Exception as e:
      adm.StopWaiting(frame, e)
      raise e
    if row:
      result=row[0]
      logger.querylog(self.cur.query, result="%s" % result)
      return result
    return None
  
  
  def ExecuteDict(self, cmd, args=None):
    set=self.ExecuteSet(cmd, args)
    d={}
    for row in set:
      d[row[0]] = row[1]
    return d

  def ExecuteAsync(self, cmd, args=None):
    worker=QueryWorker(self, cmd, args)
    return worker

class QueryWorker(threading.Thread):
  def __init__(self, conn, cmd, args):
    threading.Thread.__init__(self)
    self.conn=conn
    self.cmd=cmd
    self.args=args
    self.running=True
    
  def run(self):
    self.cancelled=False
    self.error=None
    try:
      self.conn.execute(self.cmd, self.args)
      self.conn.wait("AsyncWorker")
    except Exception as e:
      self.error=e
    self.running=False

    
  def cancel(self):
    if self.running:
      self.cancelled=True
      self.running=False
      self.conn.conn.cancel()


  def GetResult(self, autocommit=True):
    return pgRowset(self.conn.cur, autocommit)
  
  def IsRunning(self):
    return self.running   
  
  def Cancel(self):
    if self.running:
      self.cancel()