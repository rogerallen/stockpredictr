# stockpredictr_models.py
#
# Copyright (C) 2009-2013 Roger Allen (rallen@gmail.com)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import bisect
import datetime as datetime_module
from django.utils import simplejson
import webapp2 as webapp
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import db

from stockpredictr_config import G_LIST_SIZE
from stockpredictr_utils import *

# NOTE/FIXME -- I'm using memcache.set() quite a bit in the code below.
# The docs say set() is not thread-safe.  Keep this in mind if/when
# we try to adjust the threadsafe app.yaml

# NOTE: Special memcache handling required:
# We've got a few lists to deal with:
#   contests (open_contests & full contest) list
#   predictions
# My strategy will be to try to update any active lists in memcache
# with new items so that the lists are in sync with the added items.
KEY_CACHE_SECONDS        = 1*24*60*60 # 1 day
STOCK_CACHE_SECONDS      = 60 # Update every minute, at most
CONTEST_CACHE_SECONDS    = 60 # The following could be larger or
MYUSER_CACHE_SECONDS     = 60 # smaller. I'm not sure what is best.
PREDICTION_CACHE_SECONDS = 60

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# we need to assign keys ourselves for Contests & such.
# see get_new_contest_key for usage
def get_new_key(model, model_str):
  mckey = "%s_ids"%(model_str)
  model_ids = memcache.get(mckey)
  if ((model_ids is not None) and (len(model_ids) > 0)):
    logging.info("get_new_key from memcache")
  else:
    try:
      model_ids_batch = db.allocate_ids(model.all().get().key(), 10)
      logging.info("get_new_key alloc new from existing model")
    except AttributeError:
      model_ids_batch = db.allocate_ids(db.Key.from_path(model_str, 1), 10)
      logging.info("get_new_key alloc new")
    model_ids = range(model_ids_batch[0], model_ids_batch[1] + 1)
  model_key = db.Key.from_path(model_str, model_ids.pop(0))
  if not memcache.set(mckey,model_ids,KEY_CACHE_SECONDS):
    logging.error('get_new_key memcache set failure')
  logging.info("get_new_key: model=%s id=%s"%(model_str, model_key.id()))
  return model_key

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# our databases
class Stock(db.Model):
  """
  Table of Stocks used in contests.
  symbol - an all-caps version of the stock symbol
  recent_price[_time] - cache the latest price.
  """
  symbol            = db.StringProperty()
  recent_price      = db.FloatProperty()
  recent_price_time = db.DateTimeProperty(auto_now=True)

def get_new_stock_key():
  return get_new_key(Stock,'Stock')

def get_stock_timeout():
  timeout = STOCK_CACHE_SECONDS
  if not market_open():
    timeout = 15*STOCK_CACHE_SECONDS # 15x slower during close
  return timeout

def get_stock_from_db(stock_query,symbol):
  mckey = "stock"+symbol
  stock = memcache.get(mckey)
  if stock is not None:
    logging.info("get_stock_from_db %s from memcache"%(symbol))
  else:
    logging.info("get_stock_from_db %s from DB"%(symbol))
    stocks = stock_query.fetch(1)
    if len(stocks) == 0:
      stock = None
    else:
      assert(len(stocks) == 1)
      stock = stocks[0]
      # stocks from DB need to have prices updated
      logging.info("going to get stock price...")
      try:
        stock.recent_price = get_stock_price_from_web(symbol)
        stock.put()
      except urlfetch.DownloadError:
        logging.exception("GetStockPrice DownloadError.")
        stock_price = stock.recent_price
      except db.BadValueError:
        logging.exception("GetStockPrice BadValueError.")
        stock_price = stock.recent_price
    # put updated stock into memcache for the future
    if ((stock is not None) and
        (not memcache.set(mckey,stock,get_stock_timeout()))):
      logging.error('get_stock_from_db %s memcache set failure'%(symbol))
  return stock

def get_stock_from_symbol(symbol):
  """return the Stock for the symbol.  None if it doesn't exist."""
  return get_stock_from_db(db.GqlQuery("SELECT * FROM Stock " +
                                       "WHERE symbol = :1",
                                       symbol.upper()),
                           symbol)

def get_or_add_stock_from_symbol(symbol):
  """get stock from symbol.  if it is invalid, return None.
  if it doesn't exist, add it to db
  """
  symbol = symbol.upper()
  stock = get_stock_from_symbol(symbol)
  if stock == None:
    logging.info('validating stock %s' % (symbol))
    stock_price = get_stock_price_from_web(symbol)
    if type(stock_price) != type(float()):
      logging.info('invalid stock')
      return None
    logging.info('adding stock %s and price %f to db' % (symbol, stock_price))
    stock = Stock(key=get_new_stock_key())
    stock.symbol = symbol
    stock.recent_price = stock_price
    stock.put()
    mckey = "stock"+symbol
    if not memcache.set(mckey,stock,get_stock_timeout()):
      logging.error('get_or_add_stock_from_symbol %s memcache set failure'%(symbol))
  return stock

def get_stock_price(symbol):
  """get stock price and cache the result"""
  stock = get_stock_from_symbol(symbol)
  if stock == None:
    logging.info("didn't find symbol %s"%(symbol))
    return "Unknown"
  return stock.recent_price

def get_stock_price_from_web(symbol):
  # add 'TEST' short-circuit stock that is always $12.0625/share
  if symbol == 'TEST':
    return 12.0625
  if symbol == 'FAIL':
    return "Unknown"
  # FIXME -- eventually google finance will go away?
  stock_price_url = "http://finance.google.com/finance/info?client=ig&q=%s" % (symbol)
  stock_price_result = urlfetch.fetch(stock_price_url)
  if stock_price_result.status_code == 200:
    tmp = stock_price_result.content.replace('// ','')
    logging.info("stock response = %s" % (tmp))
    stock_data = simplejson.loads(tmp)
    if len(stock_data) > 0:
      stock_price = float(stock_data[0]["l"])
    else:
      stock_price = "Unknown"
  else:
    stock_price = "Unavailable"
  logging.info("stock price = %s" % (stock_price))
  return stock_price

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class MyUser(db.Model):
  """
  Table of Users that play in the contests.
  nickname - how they want to call themselves
  user - how google tracks them
  """
  nickname = db.StringProperty() # custom nickname for this site
  wins     = db.IntegerProperty()
  losses   = db.IntegerProperty()
  win_pct  = db.FloatProperty()
  user     = db.UserProperty()
  authorized_contest_list = db.ListProperty(db.Key)

def get_new_myuser_key():
  return get_new_key(MyUser,'MyUser')

def get_myuser_from_user_id(user_id):
  mckey = "myuser_uid"+user_id
  logging.info(mckey)
  myuser = memcache.get(mckey)
  if myuser is not None:
    logging.info("get_myuser_from_user_id %s from memcache"%(user_id))
  else:
    logging.info("get_myuser_from_user_id %s from DB"%(user_id))
    myusers = db.GqlQuery("SELECT * FROM MyUser WHERE user = :1",
                          users.get_current_user()
                          ).fetch(1)
    if len(myusers) == 0:
      myuser = None
    else:
      assert(len(myusers) == 1)
      myuser = myusers[0]
    if ((myuser is not None) and
        (not memcache.set(mckey,myuser,MYUSER_CACHE_SECONDS))):
      logging.error('get_myuser_from_user_id %s memcache set failure' %
                    (myuser.nickname))
  if myuser is not None:
    logging.info("get_myuser_from_user_id return %s"%(myuser.nickname))
  else:
    logging.info("get_myuser_from_user_id return None")
  return myuser

def get_myuser_from_myuser_id(myuser_id):
  assert(type(myuser_id) == type(str()))
  mckey = "myuser_myuid"+myuser_id
  myuser = memcache.get(mckey)
  if myuser is not None:
    logging.info("get_myuser_from_myuser_id %s from memcache"%(myuser_id))
  else:
    logging.info("get_myuser_from_myuser_id %s from DB"%(myuser_id))
    myuser = MyUser.get_by_id(long(myuser_id))
    if ((myuser is not None) and
        (not memcache.set(mckey,myuser,MYUSER_CACHE_SECONDS))):
      logging.error('get_myuser_from_db %s memcache set failure' %
                    (myuser.nickname))
  if myuser is not None:
    logging.info("get_myuser_from_myuser_id return %s"%(myuser.nickname))
  else:
    logging.info("get_myuser_from_myuser_id return None")
  return myuser

def update_myuser_memcache(myuser):
  mckey = "myuser_uid"+myuser.user.user_id()
  if not memcache.set(mckey,myuser,MYUSER_CACHE_SECONDS):
    logging.error('update_myuser_memcache %s memcache uid set failure' %
                  (myuser.nickname))
  mckey = "myuser_myuid"+str(myuser.key().id())
  if not memcache.set(mckey,myuser,MYUSER_CACHE_SECONDS):
    logging.error('update_myuser_memcache %s memcache myuid set failure' %
                  (myuser.nickname))

def get_current_myuser():
  """return the MyUser for the current_user, adding if necessary"""
  if users.get_current_user() == None:
    return None
  current_user = users.get_current_user()
  current_user_id = users.get_current_user().user_id()
  logging.info("current_user %s id %s"%(current_user,current_user_id))
  myuser = get_myuser_from_user_id(users.get_current_user().user_id())
  if myuser is None:
    logging.info('adding current user %s to db' %
                 (users.get_current_user().nickname()))
    myuser = MyUser(key=get_new_myuser_key())
    myuser.user     = users.get_current_user()
    myuser.nickname = users.get_current_user().nickname()
    myuser.wins     = 0
    myuser.losses   = 0
    myuser.win_pct  = 0.0
    myuser.put()
    update_myuser_memcache(myuser)
  logging.info('get_current_myuser %s uid=%s myuid=%s' %
               (myuser.nickname,
                users.get_current_user().user_id(),
                myuser.key().id()))
  return myuser

def current_user_authorized_to_edit(edit_user):
  return edit_user.user == users.get_current_user()

def set_myuser_nickname(the_user,nickname):
  the_user.nickname = nickname
  the_user.put()
  update_myuser_memcache(the_user)
  logging.info('updated nickname to %s' % (the_user.nickname))

def update_all_users_winloss():
  logging.info("update_all_users_winloss")
  for user in db.GqlQuery("SELECT * FROM MyUser"):
    user.wins = 0
    user.losses = 0
    for prediction in db.GqlQuery("SELECT * FROM Prediction WHERE user = :1",user):
      if prediction.contest.final_value >= 0.0:
        if prediction.winner:
          user.wins += 1
        else:
          user.losses += 1
    try:
      user.win_pct = 100*float(user.wins)/float(user.wins + user.losses)
    except ZeroDivisionError:
      user.win_pct = 0.0
    # round to nearest 100th
    user.win_pct = int(user.win_pct*100)/100.0
    user.put()
    update_myuser_memcache(user)

def authorize_contest(user,contest):
  logging.info("authorize_contest %s %s"%(user.nickname,contest.key().id()))
  user.authorized_contest_list.append(contest.key())
  user.put()
  update_myuser_memcache(user)

def is_authorized_to_view(cur_user,contest):
  authorized_to_view = cur_user is not None # must login (NEW?)
  if contest.private:
    owner = get_myuser_from_myuser_id(str(contest.owner_id))
    owner_flag = users.get_current_user().user_id() == owner.user.user_id()
    in_authorized_list = False
    if cur_user:
      in_authorized_list = contest.key() in cur_user.authorized_contest_list
    authorized_to_view = (users.is_current_user_admin() or
                          owner_flag or
                          in_authorized_list)
  logging.info("is_authorized_to_view private=%s allowed=%s" %
               (contest.private,authorized_to_view))
  return authorized_to_view

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Contest(db.Model):
  """
  The Contests that we play
  private is a flag for requiring a passphrase
  salt is a random number that we use for defeating rainbow attacks (unlikely!)
  hashphrase is the hashed result of passphrase + salt
  """
  owner_id     = db.IntegerProperty() # db.ReferenceProperty(MyUser) memcache fix
  stock_symbol = db.StringProperty()  # db.ReferenceProperty(Stock) memcache fix
  close_date   = db.DateProperty()
  final_value  = db.FloatProperty()
  private      = db.BooleanProperty()
  salt         = db.StringProperty()
  hashphrase   = db.StringProperty()

def get_new_contest_key():
  return get_new_key(Contest,'Contest')

# be careful.  contest updates need to update this list too
def get_contests(contests_query,contest_str,start_index=0):
  num = G_LIST_SIZE
  mckey = contest_str
  contests = memcache.get(mckey)
  if contests is not None:
    logging.info("get_%s from memcache"%(contest_str))
  else:
    logging.info("get_%s from DB"%(contest_str))
    contests = contests_query.fetch(1000) # HACK
    if not memcache.set(mckey,contests,CONTEST_CACHE_SECONDS):
      logging.error('get_%s memcache set failure'%(contest_str))
  # only return num contests
  return contests[start_index:start_index+num] # in case cache has more

def get_open_contests():
  today = datetime_module.date.today()
  return get_contests(db.GqlQuery("SELECT * FROM Contest " +
                                  "WHERE close_date >= :1 " +
                                  "ORDER BY close_date ASC", today),
                      "open_contests")

def get_closed_contests():
  today = datetime_module.date.today()
  return get_contests(db.GqlQuery("SELECT * FROM Contest " +
                                  "WHERE close_date < :1 " +
                                  "ORDER BY close_date DESC", today),
                      "closed_contests")

def get_all_contests(start_index):
  return get_contests(db.GqlQuery("SELECT * FROM Contest " +
                                  "ORDER BY close_date DESC"),
                      "all_contests",
                      start_index)

def is_contest_at(index):
  contests = get_all_contests(index)
  is_contest = len(contests) > 0
  logging.info("is_contest_at %d = %s"%(index,is_contest))
  return is_contest

def update_contest_list(contest_str, contest, reversed_list=False):
  contests = memcache.get(contest_str)
  if contests is not None:
    close_dates = [v.close_date for v in contests]
    if reversed_list:
      close_dates.reverse()
    i = bisect.bisect_left(close_dates,contest.close_date)
    if reversed_list:
      i = len(close_dates) - i
    contests = contests[0:i] + [contest] + contests[i:]
  else:
    contests = [contest]
  #for i,c in enumerate(contests):
  #  logging.info("update_contest_list: %s %d %s"%(contest_str,i,c.key().id()))
  if not memcache.set(contest_str,contests,CONTEST_CACHE_SECONDS):
    logging.error('update_contest_list:%s memcache set failure'%(contest_str))

def put_contest(contest):
  contest_id = str(contest.key().id())
  logging.info("put_contest:"+contest_id)
  contest.put()
  mckey = "contest"+contest_id
  if not memcache.set(mckey,contest,CONTEST_CACHE_SECONDS):
    logging.error('put_contest:%s memcache set failure'%(mckey))
  # also insert into the open_contests & all_contests list.
  # first, force the memcache to be populated
  junk = get_open_contests()
  junk = get_all_contests(0)
  # then add the contest
  update_contest_list("open_contests", contest)
  update_contest_list("all_contests", contest, True)
  # this does seem a bit odd to do this...
  # keep thinking about this...

def get_contest_by_id(contest_id):
  mckey = "contest"+contest_id
  contest = memcache.get(mckey)
  if contest is not None:
    logging.info("get_contest_by_id %s from memcache"%(contest_id))
  else:
    logging.info("get_contest_by_id %s from DB"%(contest_id))
    contest = Contest.get_by_id(long(contest_id))
    if ((contest is not None) and
        (not memcache.set(mckey,contest,CONTEST_CACHE_SECONDS))):
      logging.error('get_contest_by_id %s memcache set failure'%(contest_id))
  return contest

def add_contest(user,stock,close_date,is_private,passphrase):
  logging.info('add_contest')
  contest = Contest(key=get_new_contest_key())
  contest.owner_id     = user.key().id()
  contest.stock_symbol = stock.symbol
  contest.close_date   = close_date
  contest.final_value  = -1.0
  contest.private      = is_private
  if contest.private:
    logging.info('this is a private contest')
    contest.salt       = str(int(random.randint(1000,10000)))
    contest.hashphrase = myhash(passphrase+contest.salt)
  else:
    logging.info('this is a public contest')
    contest.salt       = None
    contest.hashphrase = None
  put_contest(contest)
  return contest


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def finish_contest(contest, final_value):
  """
  Finalize a contest's final_value and prediction winner
  """
  logging.info("Closing contest %s %s fv=%s" % (contest.owner_id, contest.stock_symbol, final_value))
  contest.final_value = final_value
  put_contest(contest)
  min_pred = 100000.0
  predictions = get_predictions(contest)
  for prediction in predictions:
    delta = abs(prediction.value - contest.final_value)
    if min_pred > delta:
      min_pred = delta
  for prediction in predictions:
    delta = abs(prediction.value - contest.final_value)
    prediction.winner = (final_value > 0) and (min_pred == delta)
    prediction.put()
    mckey = "prediction"+str(prediction.user_id)+str(contest.key().id())
    if not memcache.set(mckey,prediction,PREDICTION_CACHE_SECONDS):
      logging.error('finish_contest: %s memcache set failure'%(mckey))
  mckey = "predictions"+str(contest.key().id())
  if not memcache.set(mckey,predictions,CONTEST_CACHE_SECONDS):
    logging.error('finish_contest: %s memcache set failure'%(mckey))

def allow_contest_update(contest):
   now = get_market_time_now()
   contest_close_market_open = get_market_time_open(
     contest.close_date.year, contest.close_date.month, contest.close_date.day
     )
   return now < contest_close_market_open

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class Prediction(db.Model):
  """
  Table of Predictions - one per user per contest.  updates allowed.
  """
  user_id    = db.IntegerProperty() # db.ReferenceProperty(MyUser) memcache fix
  contest_id = db.IntegerProperty() # db.ReferenceProperty(Contest) memcache fix
  value      = db.FloatProperty()
  winner     = db.BooleanProperty()

def get_new_prediction_key():
  return get_new_key(Prediction,'Prediction')

# be careful.  contest updates need to update this list too
def get_predictions(contest,start_index=0,num=G_LIST_SIZE):
  "return all or 'num' predictions"
  contest_id = str(contest.key().id())
  mckey = "predictions"+contest_id
  predictions = memcache.get(mckey)
  if predictions is not None:
    logging.info("get_predictions %s from memcache"%(contest_id))
  else:
    logging.info("get_predictions %s from DB"%(contest_id))
    predictions_query = db.GqlQuery("SELECT * FROM Prediction " +
                                    "WHERE contest_id = :1 " +
                                    "ORDER BY value DESC",
                                    contest_id)
    predictions = predictions_query.fetch(1000) # HACK
    if not memcache.set(mckey,predictions,PREDICTION_CACHE_SECONDS):
      logging.error('get_predictions %s memcache set failure'%(contest_id))
  # only return num predictions, unless num == 0
  if num > 0:
    return predictions[start_index:start_index+num] # in case cache has more
  else:
    assert(start_index==0)
    return predictions

def get_myuser_predictions(myuser):
  # I'm not going to worry about caching user predictions
  prediction_query = db.GqlQuery(
    "SELECT * FROM Prediction WHERE user_id = :1 ORDER BY contest_id DESC",
    myuser.key().id())
  predictions = prediction_query.fetch(1000) # HACK
  return predictions

def get_prediction(myuser,contest):
  mckey = "prediction"+str(myuser.key().id())+str(contest.key().id())
  prediction = memcache.get(mckey)
  if prediction is not None:
    logging.info("get_prediction %s %s from memcache"%(myuser.key().id(),
                                                       contest.key().id()))
  else:
    logging.info("get_prediction %s %s from DB"%(myuser.key().id(),
                                                 contest.key().id()))
    prediction_query = db.GqlQuery(
      "SELECT * FROM Prediction WHERE user_id = :1 AND contest_id = :2",
      myuser.key().id(), contest.key().id())
    predictions = prediction_query.fetch(1)
    if len(predictions) == 0:
      prediction = None
    else:
      assert(len(predictions) == 1)
      prediction = predictions[0]
      if ((prediction is not None) and
          (not memcache.set(mckey,prediction,PREDICTION_CACHE_SECONDS))):
        logging.error('get_prediction memcache set failure')
  return prediction

def _update_predictions(contest,prediction):
  "keep the predictions list memcache in sync with latest update"
  predictions = get_predictions(contest)
  # remove prediction if it is in the list currently
  for i,p in enumerate(predictions):
    if prediction.key() == p.key():
      predictions = predictions[:i] + predictions[i+1:]
      break
  if predictions is not None:
    prices = [p.value for p in predictions]
    prices.reverse() # reverse for bisect
    i = bisect.bisect_left(prices,prediction.value)
    i = len(prices) - i # get index from end
    predictions = predictions[0:i] + [prediction] + predictions[i:]
  else:
    predictions = [prediction]
  mckey = "predictions"+str(contest.key().id())
  if not memcache.set(mckey,predictions,CONTEST_CACHE_SECONDS):
    logging.error('update_predictions:%s memcache set failure'%(mckey))

def update_prediction(contest, value):
  cur_user = get_current_myuser()
  prediction = get_prediction(cur_user,contest)
  if prediction is None:
    logging.info('adding prediction to db')
    prediction = Prediction(key=get_new_prediction_key())
  prediction.user_id    = cur_user.key().id()
  prediction.contest_id = contest.key().id()
  prediction.value   = value
  prediction.winner  = False
  prediction.put()
  mckey = "prediction"+str(cur_user.key().id())+str(contest.key().id())
  if not memcache.set(mckey,prediction,PREDICTION_CACHE_SECONDS):
    logging.error('update_prediction memcache set failure')
  _update_predictions(contest, prediction)
  return prediction

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class FauxPrediction(object):
  """
  a version of a Prediction we use just for the webpage presentation
  """
  def __init__(self,user_nickname,user_id,value,winner,leader,is_price):
    self.user_nickname = user_nickname
    self.user_id       = user_id
    self.value         = value
    self.value_str     = get_price_str(value)
    self.winner        = winner
    self.leader        = leader
    self.is_price      = is_price

def get_faux_predictions(contest,
                         cur_index,
                         num_predictions,
                         stock_name,
                         stock_price):
  open_flag = contest.final_value < 0.0
  faux_predictions = []
  json_data = {}
  # go through all predictions to find leader(s)
  json_data["predictions"] = []
  min_pred = 100000.0
  if open_flag:
    for (i,p) in enumerate(get_predictions(contest)):
      min_pred = min(min_pred,abs(p.value - stock_price))
  for (i,p) in enumerate(get_predictions(contest)):
    is_leader = False
    if open_flag:
      if min_pred == abs(p.value - stock_price):
        is_leader = True
    # only return data in current displayed range
    # FIXME -- give hints in graph about next/prev data
    if cur_index <= i < cur_index + num_predictions:
      user = get_myuser_from_myuser_id(str(p.user_id))
      faux_predictions.append(FauxPrediction(
          user.nickname, user.key().id(), p.value, p.winner, is_leader, False
          ))
      json_data["predictions"] = [{
          'name': user.nickname,
          'value': get_price_str(p.value)[1:] # drop '$'
          }] + json_data["predictions"]
  # add stock price to list of "faux" predictions (in proper spot)
  faux_predictions.append(FauxPrediction(
      stock_name, 0, stock_price, False, False, True
      ))
  faux_predictions.sort(key=lambda p: p.value)
  faux_predictions.reverse()
  # add stock price to json_data
  json_data["price"] = {
    'name': contest.stock_symbol.replace(' ','\n'),
    'value': get_price_str(stock_price)[1:] # drop '$'
    }
  json_data = simplejson.dumps(json_data)
  return (faux_predictions,
          json_data)
