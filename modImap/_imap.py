# The Admin4 Project
# (c) 2022 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import imaplib
import adm
import logger
from wh import shlexSplit
from .imap_utf7 import encode as encodeUtf7
from .imap_utf7 import decode as decodeUtf7

_x=encodeUtf7
_x=decodeUtf7
imaplib.Commands['STARTTLS'] ='NONAUTH'
#imaplib.Commands['ID'] ='NONAUTH'

def GetImapDate(do):
  return imaplib.Internaldate2tuple(do.encode())

class Annotations(dict):
  def Get(self, key, default=None):
    for k in self.keys():
      if k.endswith(key):
        val=self.get(k)
        if val == "NIL":
          return None
        return val
    return default
    

class ImapServer(imaplib.IMAP4_SSL):
  def __init__(self, host, port, security):
    self.sslobj=None
    self.tls=False
    self.lastError=None
    self.security=security
    self.timeout=5

    super(ImapServer,self).__init__(host, port)


  def _create_socket(self, _timeout=None):
    try:
      sock = imaplib.IMAP4._create_socket(self, self.timeout)
    except TypeError:
      sock = imaplib.IMAP4._create_socket(self)
    if self.security == 'SSL':
      sock=self.ssl_context.wrap_socket(sock, server_hostname=self.host)
    return sock

  @staticmethod
  def Create(node):
    security=node.settings['security']
    server=ImapServer(node.address, node.port, security)
    if security.startswith('TLS'):
      if security != "SSL" and "STARTTLS" in server.capabilities: 
        server.starttls()
        server.tls=True
      else:
        if security == 'TLS-req':
          raise adm.ConnectionException(node, "Connect", "STARTTLS not supported")

    return server


  def ok(self):
    return self.lastError == None

  def getresult(self, response):
    typ,dat=response
    result=[]
    for d in dat:
      if isinstance(d, list):
        lst=[]
        for x in d:
          if x == None:
            lst.append(None)
          else:
            lst.append(x.decode())
        if typ == "OK":
          result.append(lst)
        else:
          result.append(" ".join(lst)) # if error, flatten inner list
      elif d == None:
        result.append(None)
      elif isinstance(d, bytes):
        result.append(d.decode())
      else:
        result.append(d)
    if typ == "OK":
      self.lastError=None
      return result
    else:
      self.lastError=result[0]
      return None
    
    
  def xxgetresult(self, response):
    typ,dat=response
    if typ == "OK":
      self.lastError=None
      result=[]
      for d in dat:
        if isinstance(d, list):
          lst=[]
          for x in d:
            if x == None:
              lst.append(None)
            else:
              lst.append(x.decode())
          result.append(lst)
        elif d == None:
          result.append(None)
        elif isinstance(d, bytes):
          result.append(d.decode())
        else:
          result.append(d)
      return result
    else:
      if isinstance(dat[0], list):
        self.lastError=dat[0][0]
      self.lastError=dat[0].decode()
      return None
    
    
  def HasFailed(self):
    return False
 
   
  def xatomResult(self, cmd, *params):
    typ,dat=self.xatom(cmd, *params)  
    if typ == "OK":
      typ, dat=self._untagged_response(typ, dat, cmd)
    return typ,dat
  
  def GetAnnotations(self, mailbox):
    try:
      dat=self.getresult(self.getannotation(self._quote(mailbox), '"*"', '"value.shared"'))
      if not dat:
        return None
    except Exception as _e:
      logger.exception("Failed to get annotation for %s" % mailbox)
      return None
    annotations=Annotations()
    
    for ann in dat:
      # this tries to deal with some imaplib weirdness if non-ascii is returned.
      # usually, ann should be a string, but if the value.shared contains non-ascii
      # a tuple is returned, with the next ann being ")"
      # This is so for imaplib.__version__ == 2.58
      if not ann or ann == ")":
        continue
      if isinstance(ann, str):
        parts=shlexSplit(ann, " ")
        annotations[parts[1]] = parts[-1][:-1]
      elif isinstance(ann, tuple):
        parts=shlexSplit(ann[0], " ")
        annotations[parts[1]] = ann[1].decode('utf-8')
      else:
        # whats that?
        pass
    return annotations

  
  
  def SetAnnotation(self, mailbox, name, value):
    def quoteNil(txt):
      if not txt:
        return "NIL"
      return self._quote(txt)

    if value == "":   value=None

    dset='(%s ("value.shared" %s))' % (quoteNil(name), quoteNil(value))
    return self.getresult(self.setannotation(self._quote(mailbox), dset ))
    return self.ok()
  
  
  def Login(self, user, password):
    if 'AUTH=CRAM-MD5' in self.capabilities:
      res=self.login_cram_md5(user, password)
    else:
      res=self.login(user, password)
    capabilities=self.getresult(res)
    if capabilities:
      self.id={}
      typ,dat=self.xatomResult('ID', 'NIL')
      if typ == "OK":
        parts=shlexSplit(dat[0][1:-1], " ")
        for i in range(0, len(parts), 2):
          self.id[parts[i]]= parts[i+1]
        
    return self.ok()
  
  def GetAcl(self, mailbox):
    result=self.getresult(self.getacl(self._quote(mailbox)))
    if result:
      acls={}
      for line in result:
        parts=shlexSplit(line, ' ')     
        for i in range(1, len(parts), 2): 
          who=parts[i]
          acl=parts[i+1]
          acls[who] = acl
      return acls
    return None


  def SetAcl(self, mailbox, who, acl=None):
    if isinstance(who, list):
      lst=[self._quote(mailbox)]
      for item in who:
        if isinstance(item, tuple):
          lst.append(item[0])
          lst.append(item[1])
        else:
          lst.append(item)
      return self.getresult(self._simple_command('SETACL', *lst))
    else:
      return self.getresult(self.setacl(self._quote(mailbox), who, acl))
  
  def DelAcl(self, mailbox, who):
    if isinstance(who, list):
      lst=[self._quote(mailbox)]
      lst.extend(who)
      return self.getresult(self._simple_command('DELETEACL', *lst))
    else:
      return self.getresult(self.deleteacl(self._quote(mailbox), who))
  
  def MyRights(self, mailbox):
    result=self.getresult(self.myrights(self._quote(mailbox)))
    if result:
      return result[0].split()[-1]
    return None
  
  def CreateMailbox(self, mailbox):
    return self.getresult(self.create(self._quote(mailbox)))
  
  def RenameMailbox(self, oldmailbox, newmailbox):
    rc= self.getresult(self.rename(self._quote(oldmailbox), self._quote(newmailbox)))
    return rc

  def DeleteMailbox(self, mailbox):
    rc= self.getresult(self.delete(self._quote(mailbox)))
    return rc

  def Reconstruct(self, mailbox, recursive):
    if recursive:
      res=self.xatom("RECONSTRUCT", self._quote(mailbox), "RECURSIVE")
    else:
      res=self.xatom("RECONSTRUCT", self._quote(mailbox))
#    print (res)
    return self.getresult(res)
  

  def SetQuota(self, root, quota):
    if quota:
      l=[]
      for resource, size in quota.items():
        l.append("%s %d" % (resource, int((size+1023)/1024)))
      limits="(%s)" % " ".join(l)
    else:
      limits="()"
    res=self.getresult(self.setquota(self._quote(root), limits))
    return res
  
  def GetQuota(self, mailbox):
    mbx=self._quote(mailbox)
    quotas={}
    res=self.getresult(self.getquotaroot(mbx))
    if res and len(res) == 2:
      res=res[1]
    else:
      res=self.getresult(self.getquota(mbx))
    if res:
      for quota in res:
        parts=shlexSplit(quota, ' ')
        if len(parts) > 3:
          root=parts[0]
          resource=parts[-3][1:]
          filled=int(parts[-2])
          total=int(parts[-1][:-1])
          if resource == 'STORAGE':
            filled *= 1024
            total *= 1024
          quotas[resource] = (root, filled, total)
        return quotas
    return None
  
  
  def List(self, directory, pattern):
    res=self.getresult(self.list(self._quote(directory), self._quote(pattern)))
    if res and len(res) == 1 and res[0] == None:
      return []
    return res
