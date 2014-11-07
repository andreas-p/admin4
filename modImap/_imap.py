# The Admin4 Project
# (c) 2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


import ssl
import imaplib
import adm
from wh import shlexSplit
from imap_utf7 import decode as decodeUtf7, encode as encodeUtf7 # @UnusedImport

imaplib.Commands['STARTTLS'] ='NONAUTH'
#imaplib.Commands['ID'] ='NONAUTH'

GetImapDate=imaplib.Internaldate2tuple

class Annotations(dict):
  def Get(self, key, default=None):
    for k in self.keys():
      if k.endswith(key):
        return self.get(k)
    return default
    

class ImapServer(imaplib.IMAP4_SSL):
  def __init__(self, host, port, security):
    self.sslobj=None
    self.tls=False
    self.lastError=None
    if security == 'SSL':
      self.callClass=imaplib.IMAP4_SSL
    else:
      self.callClass=imaplib.IMAP4
      
    imaplib.IMAP4_SSL.__init__(self, host, port)
    
  @staticmethod
  def Create(node):
    security=node.settings['security']
    server=ImapServer(node.address, node.port, security)
    if security.startswith('TLS'):
      if "STARTTLS" in server.capabilities: 
        server._starttls()
      else:
        if security == 'TLS-req':
          raise adm.ConnectionException(node, "Connect", "STARTTLS not supported")
    
    return server


  def _starttls(self):
    typ, dat = self._simple_command('STARTTLS')
    if typ != 'OK':
      raise self.error(dat[-1])
    self.sock=ssl.wrap_socket(self.sock)
    self.file=self.sock.makefile()
    self.tls=True

    typ, dat = self.capability()
    if dat == [None]:
      raise self.error('no CAPABILITY response from server')
    self.capabilities = tuple(dat[-1].upper().split())


  def ok(self):
    return self.lastError == None
  
  def getresult(self, result):
    typ,dat=result
    if typ == "OK":
      self.lastError=None
      return dat
    else:
      self.lastError=dat[0]
      return None
    
    
  def HasFailed(self):
    return False
  
  def open(self, host, port):
    return self.callClass.open(self, host, port)

  def send(self, data):
    return self.callClass.send(self, data)
  
  def shutdown(self):
    return self.callClass.shutdown(self)
  
  def xatomResult(self, cmd, *params):
    typ,dat=self.xatom(cmd, *params)  
    if typ == "OK":
      typ, dat=self._untagged_response(typ, dat, cmd)
    return typ,dat
  
  def GetAnnotations(self, mailbox):
    dat=self.getresult(self.getannotation(mailbox, '"*"', '"value.shared"'))
    if not dat:
      return None
    annotations=Annotations()
    
    for ann in dat:
      if not ann:
        continue
      parts=shlexSplit(ann, " ")
      annotations[parts[1]] = parts[-1][:-1]
    return annotations

  def quote(self, txt):
    if not txt:
      return "NIL"
    return self._quote(txt)
  
  
  def SetAnnotation(self, mailbox, name, value):
    if value == "":   value=None
    set='(%s ("value.shared" %s))' % (self.quote(name), self.quote(value))
    return self.getresult(self.setannotation(mailbox, set ))
    return self.ok()
  
  
  def Login(self, user, password):
    if 'AUTH=CRAM-MD5' in self.capabilities:
      res=self.login_cram_md5(user, password)
    else:
      res=self.login(user, password)
    if self.getresult(res):
      self.id={}
      typ,dat=self.xatomResult('ID', 'NIL')
      if typ == "OK":
        parts=shlexSplit(dat[0][1:-1], " ")
        for i in range(0, len(parts), 2):
          self.id[parts[i]]= parts[i+1]
        
    return self.ok()
  
  def GetAcl(self, mailbox):
    result=self.getresult(self.getacl(mailbox))
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
  
  def SetAcl(self, mailbox, who, acl):
    return self.getresult(self.setacl(mailbox, who, acl))
  
  def DelAcl(self, mailbox, who):
    return self.getresult(self.deleteacl(mailbox, who))
  
  def MyRights(self, mailbox):
    result=self.getresult(self.myrights(mailbox))
    if result:
      return result[0].split()[-1]
    return None
  
  def CreateMailbox(self, mailbox):
    return self.getresult(self.create(mailbox))
  
  def RenameMailbox(self, oldmailbox, newmailbox):
    rc= self.getresult(self.rename(oldmailbox, newmailbox))
    return rc

  def DeleteMailbox(self, mailbox):
    rc= self.getresult(self.delete(mailbox))
    return rc

  def Reconstruct(self, mailbox, recursive):
    if recursive:
      res=self.xatom("RECONSTRUCT", self._quote(mailbox), "RECURSIVE")
    else:
      res=self.xatom("RECONSTRUCT", self._quote(mailbox))
    print res
    return self.getresult(res)
  
  
  def GetQuota(self, mailbox):
    res=self.getresult(self.getquotaroot(mailbox))
    quotas={}
    if res and len(res) == 2:
      for quota in res[1]:
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
    res=self.getresult(self.list(directory, pattern))
    if res and len(res) == 1 and res[0] == None:
      return []
    return res
