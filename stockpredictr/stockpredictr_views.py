# stockpredictr_views.py
#
# Copyright (C) 2009,2010 Roger Allen (rallen@gmail.com)
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

import datetime as datetime_module
from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import template

from stockpredictr_config import *
from stockpredictr_utils import *
from stockpredictr_models import *

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class DefaultTemplate(dict):
  """Construct the common-case template values"""
  def __init__(self,uri):
    logged_in_flag = False
    if users.get_current_user():
      login_url = users.create_logout_url(uri)
      login_url_linktext = 'Logout'
      logged_in_flag = True
    else:
      login_url = users.create_login_url(uri)
      login_url_linktext = 'Login'  
    self['logged_in_flag']     = logged_in_flag
    self['login_url']          = login_url
    self['login_url_linktext'] = login_url_linktext
    self['cur_user']           = get_my_current_user()
    self['g_footer']           = g_footer
    self['g_welcome_warning']  = g_welcome_warning

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET index.html
# POST / for a new_contest
class HandleRoot(webapp.RequestHandler):
  def get(self,
          error_flag=False, error_message=None,
          form_symbol="",
          form_year="", form_month="", form_day="",
          form_private="", form_passphrase=""
          ):
    template_values = DefaultTemplate(self.request.uri)

    today = datetime_module.date.today()
    open_contests_query = db.GqlQuery(
      "SELECT * FROM Contest " +
      "WHERE close_date >= :1 " +
      "ORDER BY close_date ASC", today)
    open_contests = open_contests_query.fetch(G_LIST_SIZE)
    closed_contests_query = db.GqlQuery(
      "SELECT * FROM Contest " +
      "WHERE close_date < :1 " +
      "ORDER BY close_date DESC", today)
    closed_contests = closed_contests_query.fetch(G_LIST_SIZE)

    template_values.update({
      'open_contests':      open_contests,
      'closed_contests':    closed_contests,
      'error_flag':         error_flag,
      'error_message':      error_message,
      'form_symbol':        form_symbol,
      'form_year':          form_year,
      'form_month':         form_month,
      'form_day':           form_day,
      'form_private':       form_private,
      'form_passphrase':    form_passphrase,
      })
    self.response.out.write(template.render(template_path('index.html'), template_values))

  def post(self):
    """Create a new contest..."""
    try:
      if not users.get_current_user():
        raise ValueError('must login to create a contest')
      cur_user = get_my_current_user()
      stock = get_or_add_stock_from_symbol(self.request.get('symbol'))
      if stock == None:
        raise ValueError('could not find the stock symbol')
      logging.info('adding contest to db')
      contest = Contest()
      contest.owner        = cur_user
      contest.stock        = stock
      contest.close_date   = datetime_module.date(
        int(self.request.get('year')),
        int(self.request.get('month')),
        int(self.request.get('day')))
      if contest.close_date <= datetime_module.date.today():
        raise ValueError('contest date must be in the future')
      if contest.close_date.weekday() >= 5:
        raise ValueError('contest date must be a weekday')
      contest.final_value  = -1.0
      make_private(contest,
                   self.request.get('private') == '1',
                   self.request.get('passphrase'))
      contest.put()
      logging.info("contest id"+str(contest.key().id()))
      self.redirect('/contest/'+str(contest.key().id()))
    except ValueError, verr: # python2.6!
      logging.exception("CreateContest ValueError")
      self.get(error_flag      = True,
               error_message   = verr,
               form_symbol     = self.request.get('symbol'),
               form_year       = self.request.get('year'),
               form_month      = self.request.get('month'),
               form_day        = self.request.get('day'),
               form_private    = self.request.get('private'),
               form_passphrase = self.request.get('passphrase'),
               )
    except: # pragma: no cover
      logging.exception("CreateContest Error")
      self.get(error_flag      = True,
               error_message   = "There was an error.  Sorry I can't be more specific.",
               form_symbol     = self.request.get('symbol'),
               form_year       = self.request.get('year'),
               form_month      = self.request.get('month'),
               form_day        = self.request.get('day'),
               form_private    = self.request.get('private'),
               form_passphrase = self.request.get('passphrase'),
               )

  
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET about.html
class HandleAbout(webapp.RequestHandler):
  def get(self):
    template_values = DefaultTemplate(self.request.uri)
    self.response.out.write(template.render(template_path('about.html'), template_values))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET contest/id
class HandleContest(webapp.RequestHandler):
  def get(self,contest_id,
          prediction_error_flag=False,
          final_value_error_flag=False,
          passphrase_error_flag=False,
          error_message=None,
          form_prediction="",
          form_final_value="",
          form_passphrase=""):
    try:
      template_values = DefaultTemplate(self.request.uri)
      logging.info("HandleContest/%d (GET)" % int(contest_id))
      contest = Contest.get_by_id(long(contest_id))
      # check for privacy and authorization
      owner_flag = users.get_current_user() == contest.owner.user
      in_authorized_list = False
      cur_user = template_values['cur_user']
      if cur_user:
        in_authorized_list = contest.key() in cur_user.authorized_contest_list
      stock_price = None
      authorized_to_view = True
      if contest.private:
        authorized_to_view = users.is_current_user_admin() or owner_flag or in_authorized_list
        logging.info("private: allowed=%s" % (authorized_to_view))

      prediction_count = G_LIST_SIZE
      cur_index = arg2int(self.request.get('i'))
      if authorized_to_view:
        prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE contest = :1 ORDER BY value DESC",
                                       contest)
        predictions = prediction_query.fetch(prediction_count,cur_index)
        # "prev"/"next" here is referring to indices, but the flag eventually
        # refers to the values of the predictions which is reverse sorted
        # so "prev"=="higher" and "next"=="lower".  A bit confusing, so be
        # careful.
        prev_index = max(0,cur_index-prediction_count)
        prev_predictions_flag = prev_index < cur_index
        next_index = cur_index+len(predictions)
        # if there is a next_prediction, it will be at cur_index+pred_count
        # later, we verify there actually is one here... (bugfix)
        next_predictions_flag = next_index == cur_index+prediction_count
        # help figure out current leader.  get predictions just outside the fetch
        # set huge values to make sure they never win
        prediction_prev = FauxPrediction(
            'prev', -1, -1e6, False, False
            )
        if prev_predictions_flag:
          prediction_prev = prediction_query.fetch(1,cur_index-1)[0]
        prediction_next = FauxPrediction(
            'next', -1, 1e6, False, False
            )
        if next_predictions_flag:
          try:
            prediction_next = prediction_query.fetch(1,cur_index+prediction_count)[0]
          except IndexError:
            # there is no next prediction, so reset this flag & keep the FauxPrediction
            next_predictions_flag = False

        # create a list that can get the stock price inserted
        faux_predictions = []
        for p in predictions:
          faux_predictions.append(FauxPrediction(
            p.user.nickname, p.user.key().id(), p.value, p.winner,False
            ))
          
        # see if we should allow the contest to be updated
        now = get_market_time_now()
        contest_close_market_open = get_market_time_open(
          contest.close_date.year, contest.close_date.month, contest.close_date.day
          )
        can_update_flag = now < contest_close_market_open
        open_flag = contest.final_value < 0.0
        stock_name = contest.stock.symbol
        if open_flag:
          stock_name += " Current Price"
          stock_price = get_stock_price(contest.stock.symbol)
        else:
          stock_name += " Final Price"
          stock_price = contest.final_value

        # find the current leader(s)
        # include next values to allow them to be picked as leader
        # but not be displyed in main list
        if open_flag:
          min_pred = 100000.0
          for prediction in [prediction_prev]+faux_predictions+[prediction_next]:
            delta = abs(prediction.value - stock_price)
            if min_pred > delta:
              min_pred = delta
          for prediction in [prediction_prev]+faux_predictions+[prediction_next]:
            delta = abs(prediction.value - stock_price)
            if min_pred == delta:
              prediction.leader = True

        # add stock price to list of "faux" predictions
        faux_predictions.append(FauxPrediction(
          stock_name, 0, stock_price, False, True
          ))
        faux_predictions.sort(key=lambda p: p.value)
        faux_predictions.reverse()
      else:
        faux_predictions      = []
        can_update_flag       = False
        open_flag             = False
        prev_index            = max(0,cur_index-prediction_count)
        prev_predictions_flag = False
        next_index            = cur_index+prediction_count
        next_predictions_flag = False
        
      template_values.update({
        'authorized':              authorized_to_view,
        'contest':                 contest,
        'predictions':             faux_predictions,
        'can_update_flag':         can_update_flag,
        'owner_flag':              owner_flag,
        'open_flag':               open_flag,
        'prediction_error_flag':   prediction_error_flag,
        'final_value_error_flag':  final_value_error_flag,
        'passphrase_error_flag':   passphrase_error_flag,
        'error_message':           error_message,
        'form_prediction':         form_prediction,
        'form_final_value':        form_final_value,
        'form_passphrase':         form_passphrase,
        'prev_predictions_flag':   prev_predictions_flag,
        'next_predictions_flag':   next_predictions_flag,
        'prev_index':              prev_index,
        'next_index':              next_index,
        })
      self.response.out.write(template.render(template_path('contest.html'), template_values))
    except:
      logging.exception("HandleContest GET Error")
      error_message = "The requested contest does not exist."
      template_values.update({
        'error_message':      error_message,
        })
      self.response.out.write(template.render(template_path('error.html'), template_values))
      
  def post(self,contest_id):
    """There are 3 different forms to handle:
    passphrase, prediction and final_value
    """
    if self.request.get('passphrase') != "":
      self.authorize_contest(contest_id)
    elif self.request.get('prediction') != "":
      self.edit_prediction(contest_id)
    else:
      self.finish_contest(contest_id)
    
  def edit_prediction(self,contest_id):
    try:
      logging.info("HandleContest/%d POST edit_prediction" % int(contest_id))
      if not users.get_current_user():
        raise ValueError('must login to edit prediction')
      contest = Contest.get_by_id(long(contest_id))
      cur_user = get_my_current_user()
      value = float(self.request.get('prediction'))
      prediction_query = db.GqlQuery("SELECT * FROM Prediction WHERE user = :1 AND contest = :2",
                                     cur_user,
                                     contest)
      predictions = prediction_query.fetch(2)
      if predictions:
        assert(len(predictions) == 1)
        logging.info('found previous prediction')
        prediction = predictions[0]
      else:
        logging.info('adding prediction to db')
        prediction = Prediction()
      prediction.user    = cur_user
      prediction.contest = contest
      prediction.value   = value
      prediction.winner  = False
      prediction.put()
      self.get(contest_id)
    except:
      logging.exception("EditPrediction Error")
      self.get(contest_id,
               prediction_error_flag=True,
               error_message="There was an error with your prediction.",
               form_prediction=self.request.get('prediction')
               )

  def finish_contest(self,contest_id):
    try:
      logging.info("HandleContest/%d POST finish_contest" % int(contest_id))
      contest = Contest.get_by_id(long(contest_id))
      final_value = float(self.request.get('final_value'))
      finish_contest(contest,final_value)
      self.get(contest_id)
    except:
      logging.exception("FinishContest Error")
      self.get(contest_id,
               final_value_error_flag=True,
               error_message="There was an error with your final value.",
               form_final_value=self.request.get('final_value')
               )

  def authorize_contest(self,contest_id):
    """Authorize the current user to view this contest
    """
    try:
      logging.info("HandleContest/%d POST authorize_contest" % int(contest_id))
      contest = Contest.get_by_id(long(contest_id))
      passphrase = self.request.get('passphrase')
      if not users.get_current_user():
        raise ValueError('must login to authorize contest')
      logging.info('got cur_user')
      cur_user = get_my_current_user()
      passphrase_match = contest.hashphrase == myhash(passphrase+contest.salt)
      logging.info('passphrase=%s match=%s'%(passphrase,passphrase_match))
      if passphrase_match:
        cur_user.authorized_contest_list.append(contest.key())
        cur_user.put()
        self.get(contest_id)
      else:
        self.get(contest_id,
                 passphrase_error_flag=True,
                 error_message="Your passphrase did not match.",
                 form_passphrase=passphrase
                 )
    except: # pragma: no cover
      logging.exception("AuthorizeContest Error")
      self.get(contest_id,
               passphrase_error_flag=True,
               error_message="There was an error with your passphrase.",
               form_passphrase=passphrase
               )

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET /contests
class HandleContests(webapp.RequestHandler):
  def get(self):
    template_values = DefaultTemplate(self.request.uri)
    contest_count = G_LIST_SIZE
    cur_index = arg2int(self.request.get('i'))
    contests_query = db.GqlQuery(
      "SELECT * FROM Contest ORDER BY close_date DESC")
    contests = contests_query.fetch(contest_count,cur_index)
    later_index = max(0,cur_index-contest_count)
    later_contests_flag = later_index < cur_index
    earlier_index = cur_index+len(contests)
    # there may be an earlier prediction, but we have to test to be sure
    earlier_contests_flag = earlier_index == cur_index+contest_count
    if earlier_contests_flag:
      try:
        contest_earlier = contests_query.fetch(1,cur_index+contest_count)[0]
      except IndexError:
        # there is no earlier contest, so reset this flag
        earlier_contests_flag = False
    template_values.update({
      'contests':              contests,
      'later_contests_flag':   later_contests_flag,
      'earlier_contests_flag': earlier_contests_flag,
      'later_index':           later_index,
      'earlier_index':         earlier_index
      })
    self.response.out.write(template.render(template_path('contests.html'), template_values))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET user/id
# POST user/id 
class HandleUser(webapp.RequestHandler):
  def get(self,user_id):
    try:
      template_values = DefaultTemplate(self.request.uri)
      the_user = MyUser.get_by_id(long(user_id))
      logging.info("HandleUser/%d GET" % int(user_id))
      cur_user = template_values['cur_user']
      try:
        authorized_to_view = the_user.user == cur_user.user or users.is_current_user_admin()
        authorized_to_edit = the_user.user == cur_user.user
      except AttributeError:
        authorized_to_view = False
        authorized_to_edit = False
      # NOTE the use of reference properties instead of a query
      # AND they are sorted by contest close date!  (yay)
      predictions = sorted(the_user.prediction_set,key=lambda obj: obj.contest.close_date)
      closed_predictions = filter(lambda obj: obj.contest.final_value >= 0.0, predictions)
      open_predictions = filter(lambda obj: obj.contest.final_value < 0.0, predictions)
      template_values.update({
        'the_user':           the_user,
        'closed_predictions': closed_predictions,
        'open_predictions':   open_predictions,
        'authorized_to_view': authorized_to_view,
        'authorized_to_edit': authorized_to_edit,
        })
      self.response.out.write(template.render(template_path('user.html'), template_values))
    except:
      logging.exception("HandleUser GET Error")
      error_message = "The requested user does not exist."
      template_values.update({
        'error_message':      error_message,
        })
      self.response.out.write(template.render(template_path('error.html'), template_values))
      
  def post(self,user_id):
     try:
       logging.info("HandleUser/%d POST" % int(user_id))
       my_user = MyUser.get_by_id(long(user_id))
       if my_user.user == users.get_current_user():
         my_user.nickname = self.request.get('nickname')
         my_user.put()
         logging.info('updated nickname to %s' % (my_user.nickname))
     except: 
      logging.exception("HandleUser Error")
     self.redirect('/user/'+user_id)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET /admin/finish_any
# - only admin allowed via app.yaml
# - should be called by cron only
class FinishAnyContests(webapp.RequestHandler):
  def get(self):
    logging.info('FinishAnyContests called')
    today = datetime_module.date.today() # 4:30pm != next day...
    logging.info("today=%s"%(today))
    contests_query = db.GqlQuery("SELECT * FROM Contest WHERE close_date <= :1", today)
    for contest in contests_query:
      # only update contests that need a final value to be added
      if contest.final_value < 0.0:
        final_value = get_stock_price(contest.stock.symbol)
        finish_contest(contest,final_value)
    # now get each person's win/loss record straight
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
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Done')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET /admin/do_that_thing
# - only admin allowed via app.yaml
# meant to be a special one-time call to fixup some database issue
class DoThatThing(webapp.RequestHandler):
  def get(self):                                      # pragma: no cover
    logging.info('DoThatThing called')
    self.response.headers['Content-Type'] = 'text/plain'
    if 0:
      # example--make an old contest private
      the_owner_nickname = 'Mr Predictr'
      the_stock_symbol   = 'NVDA'
      the_close_date     = datetime_module.date(2009,11,6)
      new_hashphrase     = 'longhexvaluehere'
      new_salt           = 'someseedhere'
      new_private        = True
      #
      the_owner = db.GqlQuery(
        "SELECT * FROM MyUser WHERE nickname = :1",
        the_owner_nickname
        ).fetch(1)
      the_stock = db.GqlQuery(
        "SELECT * FROM Stock WHERE symbol = :1",
        the_stock_symbol
        ).fetch(1)
      contests_query = db.GqlQuery(
        "SELECT * FROM Contest WHERE owner = :1 AND stock = :2 AND close_date = :3",
        the_owner[0],
        the_stock[0],
        the_close_date
        ).fetch(1)
      contest = contests_query[0]
      contest.hashphrase = new_hashphrase
      contest.salt       = new_salt
      contest.private    = new_private
      contest.put()
    self.response.out.write('Done\n')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# GET catchall for any page not otherwise handled
class NotFoundPageHandler(webapp.RequestHandler):
  def get(self):
    template_values = DefaultTemplate(self.request.uri)
    logging.info("NotFoundPageHandler")
    self.error(404)
    template_values.update({
      'error_message': "The requested page could not be found.  This is also known as a '404 Error'",
      })
    self.response.out.write(template.render(template_path('error.html'), template_values))