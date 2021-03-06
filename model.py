import rom, datetime
from pycoin.encoding import hash160_sec_to_bitcoin_address
from blockchain import new_address, publish_data, archive_address, address_balance
from time import sleep
from config import MIN_SATOSHIS_PAYMENT

class LatestBlockchainDocuments(rom.Model):
  """Helper table for latest confirmed documents retrieval"""
  digests =  rom.ManyToOne('Document') #db.StringListProperty()
  
  def add_document(self, digest):
    print dir(digest)
    print digest.to_dict()

    self.digests = [digest] + self.digests[:-1]
    self.put()

  def put(self):
    self.save()
    print self.to_dict()
  
  @classmethod
  def get_inst(cls):
    '''
    inst = cls.all().get()
    if not inst:
    '''
    inst = cls.query.order_by("-digests").all()
    print "QUERY ALL: ", inst
    
    if len(inst) == 0:
      inst = cls()
      inst.put()
    return inst

class Document(rom.Model):
  # TODO: with keygen prop for string indexables
  """Models a proof of document existence at a certain time"""
  digests = rom.OneToMany('LatestBlockchainDocuments', 'no action', 'digests')

  digest = rom.String(index=True) #db.StringProperty()
  pending = rom.Boolean(index=True) #db.BooleanProperty()
  tx = rom.String(index=True) #db.StringProperty()
  payment_address = rom.String(index=True)  #db.StringProperty()

  timestamp = rom.DateTime(default=datetime.datetime.now())  #db.DateTimeProperty(auto_now_add=True)
  txstamp = rom.DateTime()  #db.DateTimeProperty()
  blockstamp = rom.DateTime() #db.DateTimeProperty()
  
  legacy = rom.Boolean()  #db.BooleanProperty()
  archived= rom.Boolean(index=True) #db.DateTimeProperty()

  def received_payment(self):
    self.pending = False
    self.put()

  def payment_received(self):
    return not self.pending

  def is_actionable(self):
    return self.payment_received() and self.tx == ''

  def to_dict(self):    
    if not self.payment_address:
      self.payment_address = new_address(self.digest)
      self.put()

    return rom.Model.to_dict(self)

  def put(self):
    self.save()

  def has_balance(self):
    balance = address_balance(self.payment_address)
    return True if balance >= MIN_SATOSHIS_PAYMENT else False

  @classmethod
  def get_doc(cls, digest):
    #return cls.all().filter("digest = ", digest).get()
    docs = cls.query.filter(digest=digest).execute()
    return None if len(docs) != 1 else docs[0]

  @classmethod
  def get_by_address(cls, address):
    #return cls.all().filter('payment_address = ', address).get()
    docs = cls.query.filter(payment_address=address).execute()
    return None if len(docs) != 1 else docs[0]

  @classmethod
  def new(cls, digest):
    d = cls(digest=digest)
    d.pending = True
    d.legacy = False
    d.tx = ''
    d.payment_address = None

    d.put()
    return d

  LATEST_N = 5
  @classmethod
  def get_latest(cls, confirmed=False):
    if confirmed:
      bag = LatestBlockchainDocuments.get_inst()
      print bag.to_dict()
      #return [cls.get_doc(digest) for digest in bag.digests]
      try:
        return [cls.get_doc(digest) for digest in bag.digests.iter_result()]
      except Exception as e:
        print e, type(e)

    else:
      #return cls.all().order("-timestamp").run(limit=cls.LATEST_N)
      try:
        return cls.query.order_by("-timestamp").limit(0, cls.LATEST_N).all()
      except Exception as e:
        print e, type(e)

    return []

  @classmethod
  def get_actionable(cls):
    #return cls.all().filter("pending == ", False).filter("tx == ", '').run()
    return cls.query.filter(pending=False).filter(tx="").execute()

  @classmethod
  def get_paid(cls, offset=0):
    limit = datetime.datetime.now() - datetime.timedelta(days=10)
    #.filter("timestamp < ", limit) \
    '''
    pending = cls.all() \
      .filter("pending == ", True) \
      .filter("tx == ", '') \
      .run(offset=offset, limit=50)
    '''
    pending = cls.query.filter(pending=True) \
      .filter(tx="") \
      .limit(offset, 50) \
      .execute()
    
    #for d in pending:
    for d in pending.iter_result():
      if d.has_balance():
        yield d
      sleep(0.2)

  @classmethod
  def update_schema(cls):
    #ds = cls.all()
    ds = cls.query.all()
    n = 0
    #for d in ds:
    for d in ds.iter_result():
      n += 1
    return n

  @classmethod
  def get_archiveable(cls):
    limit = datetime.datetime.now() - datetime.timedelta(days=5)

    '''
    return cls.all() \
      .filter("timestamp < ", limit) \
      .filter("tx == ", '') \
      .filter("archived == ", None) \
      .run(limit=100)
    '''
    return cls.query.filter(timestamp=limit) \
      .filter(tx="") \
      .filter(archived=None) \
      .limit(0, 100) \
      .execute()

  def archive(self):
    result = archive_address(self.payment_address)
    if result.get('archived'):
      self.archived = datetime.now()
      self.put()
    return result

  def blockchain_certify(self):
    if self.tx:
      return {"success" : False, "error": "already certified"}
    txid, message = publish_data(self.digest.decode('hex'))
    if txid:
      self.tx = txid
      self.txstamp = datetime.datetime.now()
      LatestBlockchainDocuments.get_inst().add_document(self.digest)
      self.put()
    return {"success" : txid is not None, "tx" : txid, "message" : message}

