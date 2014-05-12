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


######################################################################
class pgCursorResult:
  def __init__(self, cursor, colNames=None):
    self.cursor=cursor
    if colNames:
      self.colNames=colNames
    else:
      self.colNames=[]
      for d in cursor.GetDescription():
        self.colNames.append(d[0])
      
      
class pgRow(pgCursorResult):
  def __init__(self, cursor, row, colNames=None):
    pgCursorResult.__init__(self, cursor, colNames)
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
    if isinstance(val, str):
      return val.decode('utf8')
    return val


class pgRowset(pgCursorResult):
  def __init__(self, cursor):
    pgCursorResult.__init__(self, cursor)
    self.__fetchone()
    
  def GetRowcount(self):
    return self.cursor.GetRowcount()
  
  def __fetchone(self):
    if self.cursor.GetRowcount() > 0:
      row = self.cursor.FetchOne()
    else:
      row=None
    if row:
      self.curRow = pgRow(self.cursor, row, self.colNames)
    else:
      self.curRow=None

  def HasMore(self):
    return self.curRow != None
          
  def Next(self):
    row=self.curRow
    if row:
      self.__fetchone()
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
  
######################################################################  
class pgConnection:
  def __init__(self, dsn, pool=None):
    self.pool=pool
    self.conn=psycopg2.connect(dsn, async=True)
    self.wait("Connect")
    self.cursor=self.conn.cursor()
    self.inUse=False
    self.lastError=None
      
  def disconnect(self):
    self.cursor=None
    if self.conn:
      self.conn.close()
      self.conn=None

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

  def _handleException(self, e):
    if self.cursor and self.cursor.query:
      cmd=self.cursor.query
    else:
      cmd=None
    errlines=str(e)
    self.lastError=errlines
    if self.pool:
      self.pool.lastError=self.errlines
      
    logger.querylog(cmd, error=errlines)
    adm.StopWaiting(adm.mainframe)
    if self.conn and self.conn.closed:
      self.disconnect()
    raise SqlException(cmd, errlines)

  def isRunning(self):
    return self.conn.poll() != psycopg2.extensions.POLL_OK

  def GetCursor(self):
    return pgCursor(self)

  ######################################################################
  
class pgCursor():
  def __init__(self, conn):
    self.conn=conn
    self.cursor=self.conn.cursor
  
  def __del__(self):
    self.Close()
    
  def Close(self):
    if self.conn:
      self.conn.inUse=False
      self.conn=None
      self.cursor=None
    
  def GetPid(self):
    return self.conn.conn.get_backend_pid()

  
  def GetDescription(self):
    if self.cursor.description:
      return self.cursor.description
    return []

  def GetRowcount(self):
    return self.cursor.rowcount
  
  def FetchOne(self):
    row=self.cursor.fetchone()
    return row

#  def Rollback(self):
#    self.cursor.execute("ROLLBACK")
#    self.cursor.wait("ROLLBACK")
#  
#  def Commit(self):
#    self.cursor.execute("COMMIT")
#    self.cursor.wait("COMMIT")


  def execute(self, cmd, args=None):
    if args:
      if isinstance(args, list):
        args=tuple(args)
      elif isinstance(args, tuple):
        pass
      else:
        args=(args,)
        
    try:
      self.cursor.execute(cmd, args)
    except Exception as e:
      self.conn._handleException(e)

  def wait(self, spot=""):
    return self.conn.wait(spot)

  def ExecuteList(self, cmd, args=None):
    rowset=self.ExecuteSet(cmd, args)
    if rowset:
      return rowset.getList()
    return None
  
  def ExecuteDictList(self, cmd, args=None):
    rowset=self.ExecuteSet(cmd, args)
    if rowset:
      return rowset.getDictList()
    return None
  
  def ExecuteSet(self, cmd, args=None):
    frame=adm.StartWaiting()
    try:
      self.execute(cmd, args)
      self.wait("ExecuteSet")
      rowset=pgRowset(self)
      logger.querylog(self.cursor.query, result="%d rows" % rowset.GetRowcount())
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
      row=self.cursor.fetchone()
      adm.StopWaiting(frame)
    except Exception as e:
      adm.StopWaiting(frame, e)
      raise e
    
    if row:
      row=pgRow(self.cursor, row)
      logger.querylog(self.cursor.query, result=str(row))
      return row
    return None
    
  
  
  def ExecuteSingle(self, cmd, args=None):
    frame=adm.StartWaiting()
    try:
      self.execute(cmd, args)
      self.wait("ExecuteSingle")
      try:
        row=self.cursor.fetchone()
      except:
        row=None
      adm.StopWaiting(frame)
    except Exception as e:
      adm.StopWaiting(frame, e)
      raise e
    if row:
      result=row[0]
      logger.querylog(self.cursor.query, result="%s" % result)
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
  
#############################################################################
  
class pgConnectionPool:
  def __init__(self, node, dsn):
    self.node=node
    self.lastError=None
    self.connections=[]  
    self.lock=threading.Lock()
    self.dsn=dsn

    # create first connection to make sure params are ok
    conn=self.CreateConnection()
    with self.lock:
      self.connections.append(conn)
    
    
  def HasFailed(self):
    return len(self.connections) == 0


  def RemoveConnection(self, conn):
    try:    self.connections.remove(conn)
    except: pass
  
  def GetCursor(self):
    conn=None
    with self.lock:
      for c in self.connections:
        if not c.inUse:
          conn=c
          c.inUse=True
          break
    if not conn:
      conn=self.CreateConnection()
    return conn.GetCursor()

  
  def CreateConnection(self):
    try:
      conn=pgConnection(self.dsn, self)
      return conn
    except Exception as e:
      self.lastError = str(e)
      raise adm.ConnectionException(self.node, xlt("Connect"), self.lastError)   


class QueryWorker(threading.Thread):
  def __init__(self, cursor, cmd, args):
    threading.Thread.__init__(self)
    self.cursor=cursor
    self.cmd=cmd
    self.args=args
    self.running=True
    
  def run(self):
    self.cancelled=False
    self.error=None
    try:
      self.cursor.execute(self.cmd, self.args)
      self.cursor.wait("AsyncWorker")
    except Exception as e:
      self.error=e
    self.running=False

    
  def cancel(self):
    if self.running:
      self.cancelled=True
      self.running=False
      self.cursor.conn.conn.cancel()

  def GetRowcount(self):
    return self.cursor.GetRowcount()

  def GetResult(self):
    try:
      return pgRowset(self.cursor)
    except:
      return None
  
  def IsRunning(self):
    return self.running   
  
  def Cancel(self):
    if self.running:
      self.cancel()