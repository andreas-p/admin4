# The Admin4 Project
# (c) 2013-2014 Andreas Pflug
#
# Licensed under the Apache License, 
# see LICENSE.TXT for conditions of usage


# http://www.dnspython.org/docs
# http://www.dnspython.org/examples.html

try:
  import dns.query, dns.update, dns.message, dns.resolver, dns.tokenizer
  import dns.zone, dns.tsigkeyring, dns.reversename
  from dns.name import Name
  import dns.ipv4, dns.ipv6
  import dns.rdata, dns.rdataset
  import dns.rdatatype as rdatatype, dns.rdataclass as rdataclass # @UnusedImport
  import dns.rcode as rcode # @UnusedImport
except:
  dns=None

import requests
import xml.etree.cElementTree as xmltree


DnsSupportedTypes={'A':           "IPV4 Address",
                   'AAAA':        "IPV6 Address",
                   'CNAME':       "Canonical Name",
                   'PTR':         "Domain Name Pointer",
                   'SOA':         "Start Of Authority",
                   'MX':          "Mail Exchange", 
                   'NS':          "Name Server", 
                   'TXT':         "Text Record",
                   'SRV':         "Service Locator",         
                   'RRSIG':       "DNSSEC Signature",
                   'DNSKEY':      "DNS Key",
                   'NSEC':        "Next Secure Record",
                   'NSEC3':       "Next Secure Record V3",
                   'NSEC3PARAM':  "NSEC3 Parameters",
                   'SPF':         "Sender Policy Framework",
                   'APL':         "Address Prefix List",
                   'LOC':         "Location",
                   'AFSDB':       "AFS database",
                   'CERT':        "Certificate",
                   'DHCID':       "DHCP Identifier",
                   'DNAME':       "Delegation Name",
                   'DS':          "Delegation Signer",
                   'GPOS':        "Geographical Position",
                   'HINFO':       "Host Information",
                   'HIP':         "Host Identifier Protocol",
                   'IPSECKEY':    "IPSEC Key",
                   'ISDN':        "ISDN Address",
                   'KX':          "Key Exchange",
                   'NAPTR':       "Naming Authority Pointer",
                   'RP':          "Responsible Person",
                   'SIG':         "DNSSEC Signature",
                   'KEY':         "DNSSEC Key",
                   'SSHFP':       "SSH Public Key Fingerprint",
                   'TKEY':        "Secret Key Record",
                   'TLSA':        "TLSA Certificate Association",
                   'TSIG':        "Transaction Signature",
                   'WKS':         "Well known service description",
                   'X25':         "X25 Address",
                   }

def DnsName(*args):
  lst=[]
  for arg in args:
    if isinstance(arg, list):
      lst.extend(arg)
    else:
      lst.extend(arg.split('.'))
      
  return Name(lst)

def DnsAbsName(*args):
  lst=[]
  for arg in args:
    if isinstance(arg, list):
      lst.extend(arg)
    else:
      lst.extend(arg.split('.'))
      
  if lst[-1]:
    lst.append("") # make it an absolute name
  
  return Name(lst)

def RdataClass(rdClass, rdType):
  return dns.rdata.get_rdata_class(rdClass, rdType)

def Rdata(set, *args):
  cls=RdataClass(set.rdclass, set.rdtype)
  return cls(set.rdclass, set.rdtype, *args)

def RdataEmpty(set):
  cls=RdataClass(set.rdclass, set.rdtype)
  zero=[]
  for _slot in cls.__slots__:
    zero.append("0")
  return cls.from_text(set.rdclass, set.rdtype, dns.tokenizer.Tokenizer(" ".join(zero)))
  
def Rdataset(ttl, rdclass, rdtype, *args):
  rds=dns.rdataset.Rdataset(rdclass, rdtype)
  if args:
    rds.add(Rdata(rds, *args), ttl)
  else:
    rds.add(RdataEmpty(rds), ttl)
  return rds


def DnsRevName(address):
  return dns.reversename.from_address(address)

def DnsRevAddress(name):
  return dns.reversename.to_address(name)


def checkIpAddress(address):
  try:
    dns.ipv4.inet_aton(address)
    return 4
  except:
    try:
      dns.ipv6.inet_aton(address)
      return 6
    except:
      pass
  return None

class BindConnection():
  def __init__(self, server):
    self.server=server
    self.hasFailed=False
    
  def HasFailed(self):
    return self.hasFailed
  
  def Updater(self, zonename):
    return dns.update.Update(zonename, keyring=self.GetKeyring())
  
  def Query(self, name, rdtype=dns.rdatatype.A, rdclass=dns.rdataclass.IN):
    if not isinstance(name, Name):
      name=DnsName(name)
    request = dns.message.make_query(name, rdtype, rdclass)
    keyring=self.GetKeyring()
    if keyring:
      request.use_tsig(keyring)
    try:
      response=dns.query.tcp(request, self.server.settings['host'], timeout=self.server.settings.get('timeout', 1.), port=self.server.settings['port'])
      if response:
        answer=dns.resolver.Answer(name, rdtype, rdclass, response)
        return answer.rrset
    except:
      return None
    return []
  
  def GetVersion(self):
    rdtype=dns.rdatatype.TXT
    rdclass=dns.rdataclass.CH
    name=DnsAbsName("version.bind")
    request=dns.message.make_query(name, rdtype, rdclass)
    keyring=self.GetKeyring()
    if keyring:
      request.use_tsig(keyring)
    try:
      response=dns.query.tcp(request, self.server.settings['host'], timeout=self.server.settings.get('timeout', 1.), port=self.server.settings['port'])
      if response:
        answer=dns.resolver.Answer(name, rdtype, rdclass, response)
        rdata=answer.rrset[0]
        return " ".join(rdata.strings)
    except dns.resolver.NoAnswer:
      return ""
    except Exception as _e:
      return None
    return ""
    
  def GetKeyring(self):
    if self.server.password and self.server.settings['keyname']:
      return dns.tsigkeyring.from_text({ self.server.settings['keyname'] : self.server.password })
    else:
      return None

  def ReadStatistics(self):
    if not self.server.settings.get('statsport'):
      return None
    try:
      response=requests.get("http://%s:%d" % (self.server.settings['host'], self.server.settings['statsport']), timeout=self.server.settings.get('timeout', 1.))
      response.raise_for_status()
      txt=response.text
    except Exception as _e:
      return None

    try:
      root=xmltree.fromstring(txt)
    except Exception as _e:
      import logger, adm, time
      fname="%s/xml-%s_%s.xml" % (adm.loaddir, self.server.settings['host'], time.strftime("%Y%m%d%H%M%S", time.localtime(time.time())))
      logger.exception("Error parsing BIND response %s", fname)
      f=open(fname, "w")
      f.write(txt)
      f.close() 
      return None
    return root
  
  def Send(self, updater):
    return dns.query.tcp(updater, self.server.settings['host'], timeout=self.server.settings.get('timeout', 1.), port=self.server.settings['port'])

  def GetZone(self, zone):
    xfr = dns.query.xfr(self.server.settings['host'], zone, timeout=self.server.settings.get('timeout', 1.)*10., port=self.server.settings['port'], keyring=self.GetKeyring())
    zoneObj = dns.zone.from_xfr(xfr)
    return zoneObj

