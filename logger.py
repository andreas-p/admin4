# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import time, traceback

loglines=[]
querylines=[]
queryfile=None
logfile=None

class LOGLEVEL:
  NONE=0
  DEBUG=1
  INFO=2
  ERROR=3
  CRIT=4
  @staticmethod
  def Text(level):
    return ["None", "Debug", "Info", "Error", "Critical"][level]
loglevel=LOGLEVEL.NONE
querylevel=LOGLEVEL.NONE


class _Line:
  def __init__(self):
    self.timestamp=time.time()
  
  def Timestamp(self):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))

  def LevelText(self):
    return LOGLEVEL.Text(self.level)
  
  def LevelImageId(self):
    from adm import images
    if self.level:
      return images.GetId(self.LevelText())
    return -1
  
  def __getitem__(self, name):
    return self.__dict__.get(name)



class LogLine(_Line):
  def __init__(self, level, text, tb=None):
    _Line.__init__(self)
    self.level=level
    self.text=text
    self.tb=tb
    


class QueryLine(_Line):
  def __init__(self, level, cmd, error=None, result=None):
    _Line.__init__(self)
    self.level=level
    indent=-1
    lines=[]
    if cmd:
      for line in cmd.splitlines():
        line=line.rstrip()
        sline=line.lstrip()
        if not len(sline):
          continue
        if indent < 0:
          indent = len(line)-len(sline)
          lines.append(sline)
        else:
          ind=len(line)-len(sline) -indent
          empty=""
          for _i in range(ind):
            empty += " "
          lines.append(empty + sline)
    self.cmd = "\n".join(lines)
    self.error=error
    self.result=result
  
  
  def __getitem__(self, name):
    if name == 'err+result':
      if self.error:
        if self.result:
          return "%s - %s" % (self.error, self.result)
        else:
          return self.error
      return self.result
    return self.__dict__.get(name)

  
if False:
  loglines.append( LogLine(LOGLEVEL.DEBUG, "Debug message", None))
  loglines.append( LogLine(LOGLEVEL.INFO, "info message", None))
  loglines.append( LogLine(LOGLEVEL.ERROR, "error message", None))
  loglines.append( LogLine(LOGLEVEL.CRIT, "critical message", None))
  querylines.append( QueryLine(LOGLEVEL.DEBUG, "Debug message", None, "Some weird result"))
  querylines.append( QueryLine(LOGLEVEL.ERROR, "error message", "Some failure", None))



def _log(level, fmt, args, tb=None):
  if level < loglevel and not tb:
    return

  txt=fmt % args
  line=LogLine(level, txt, tb)
  loglines.append(line)

  if logfile:
    try:    txt=txt.encode('utf8')
    except: pass
    try:
      f=open(logfile, 'a')
      f.write("%s %s: %s\n" % (line.Timestamp(), line.LevelText(), txt))
      if tb:
        f.write("%s\n" % tb)
    except Exception as e:
      print "CANNOT LOG", e
      pass


def trace(offset, level, fmt, *args):
  if True:
    txt=fmt % args
    stack=traceback.extract_stack()
    lst=[]
    for i in range(len(stack)-offset, len(stack)-offset-level, -1):
      file=stack[i][0].split('/')[-1]
      lst.append("%s (%s:%d)" % (stack[i][2], file, stack[i][1]))
    print txt, "Stack:", "  ".join(lst)
  
def debug(fmt, *args):
  _log(LOGLEVEL.DEBUG, fmt, args)

def error(fmt, *args):
  _log(LOGLEVEL.ERROR, fmt, args)

def exception(fmt, *args):
  """
  exception(formatStr, [args])
  
  logs error and exception traceback
  """
  _log(LOGLEVEL.ERROR, fmt, args, traceback.format_exc())
  
def sysexception(extype, args, tb):
  _log(LOGLEVEL.ERROR, "%s: %s", (extype.__name__, " ".join(args)),   "".join(traceback.format_tb(tb)))

def querylog(cmd, result=None, error=None):
  if isinstance(cmd, str):
    try:  cmd=cmd.decode('utf8')
    except: pass
    
  line=None
  if querylevel > LOGLEVEL.DEBUG or error:
    line=QueryLine(LOGLEVEL.ERROR, cmd, error, result)
  elif querylevel == LOGLEVEL.DEBUG:
    line=QueryLine(LOGLEVEL.DEBUG, cmd, error, result)
  if line:
    querylines.append(line)

    global queryfile
    if queryfile:
      try:
        f=open(queryfile, 'a')
        f.write(line.cmd)
        f.write("\n\n")
        f.close()
      except:
        _log(LOGLEVEL.ERROR, "Query Log File %s cannot be written.", queryfile)
        queryfile=None
