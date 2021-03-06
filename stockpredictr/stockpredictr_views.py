# stockpredictr_views.py
#
# Copyright (C) 2009-2017 Roger Allen (rallen@gmail.com)
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
import webapp2 as webapp
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
    self['cur_user']           = get_current_myuser()
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
    template_values.update({
      'open_contests':      get_open_contests(),
      'closed_contests':    get_closed_contests(),
      'error_flag':         error_flag,
      'error_message':      error_message,
      'form_symbol':        form_symbol,
      'form_year':          form_year,
      'form_month':         form_month,
      'form_day':           form_day,
      'form_private':       form_private,
      'form_passphrase':    form_passphrase,
      })
    self.response.out.write(template_render('index.html', template_values))

  def post(self):
    """Create a new contest..."""
    try:
      if not users.get_current_user():
        raise ValueError('must login to create a contest')
      cur_user = get_current_myuser()
      stock = get_or_add_stock_from_symbol(self.request.get('symbol'))
      if stock == None:
        raise ValueError('could not find the stock symbol')
      close_date = datetime_module.date(
        int(self.request.get('year')),
        int(self.request.get('month')),
        int(self.request.get('day')))
      if close_date <= datetime_module.date.today():
        raise ValueError('contest date must be in the future')
      if close_date.weekday() >= 5:
        raise ValueError('contest date must be a weekday')
      logging.info('adding contest to db')
      contest = add_contest(cur_user,
                            stock,
                            close_date,
                            self.request.get('private') == '1',
                            self.request.get('passphrase'))
      logging.info("contest id"+str(contest.key().id()))
      self.redirect('/contest/'+str(contest.key().id()))
    except ValueError, verr:
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
      contest = get_contest_by_id(contest_id)
      if contest is None:
        raise ValueError('no contest by that id')
      # check for privacy and authorization
      owner = get_myuser_from_myuser_id(str(contest.owner_id))
      owner_flag = users.get_current_user() == owner.user
      stock_price = None
      cur_user = template_values['cur_user']
      authorized_to_view = is_authorized_to_view(cur_user,contest)
      prediction_count = G_LIST_SIZE
      cur_index = arg2int(self.request.get('i'))
      # see if we should allow the contest to be updated
      can_update_flag = allow_contest_update(contest)
      open_flag = contest.final_value < 0.0
      if authorized_to_view:
        # "prev"/"next" here is referring to indices, but the flag eventually
        # refers to the values of the predictions which is reverse sorted
        # so "prev"=="higher" and "next"=="lower".  A bit confusing, so be
        # careful.
        prev_index = max(0,cur_index-1)
        prev_predictions_flag = ((prev_index < cur_index) and
                                 len(get_predictions(contest,prev_index,1)) == 1)
        next_index = cur_index+prediction_count
        next_predictions_flag = len(get_predictions(contest,next_index,1)) == 1

        logging.info("GetContest cur_index=%d prev_index=%d next_index=%d"%(cur_index,prev_index,next_index))
        logging.info("GetContest prev_prediction_flag=%s next_prediciton_flag=%s"%(prev_predictions_flag,next_predictions_flag))

        stock_name = contest.stock_symbol
        if open_flag:
          stock_name += " Current Price"
          stock_price = get_stock_price(contest.stock_symbol)
        else:
          stock_name += " Final Price"
          stock_price = contest.final_value

        # get faux_data for template & json_data for graph of contest.
        # Will have stock price & .winner/.leader labeled
        (faux_predictions,
         json_data) = get_faux_predictions(contest,
                                           cur_index,
                                           prediction_count,
                                           stock_name,
                                           stock_price)
      else:
        can_update_flag       = False
        open_flag             = False
        prev_index            = 0
        prev_predictions_flag = False
        next_index            = 0
        next_predictions_flag = False
        faux_predictions      = []
        json_data             = '{}'

      template_values.update({
        'authorized':              authorized_to_view,
        'contest':                 contest,
        'owner':                   owner,
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
        'json_data':               json_data,
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
      contest = get_contest_by_id(contest_id)
      # FIXES BUG found by David
      if not allow_contest_update(contest):
        raise ValueError('nice try h4cker! no update allowed.')
      value = float(self.request.get('prediction'))
      update_prediction(contest, value)
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
      contest = get_contest_by_id(contest_id)
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
      contest = get_contest_by_id(contest_id)
      passphrase = self.request.get('passphrase')
      if not users.get_current_user():
        raise ValueError('must login to authorize contest')
      logging.info('got cur_user')
      cur_user = get_current_myuser()
      passphrase_match = contest.hashphrase == myhash(passphrase+contest.salt)
      logging.info('passphrase=%s match=%s'%(passphrase,passphrase_match))
      if passphrase_match:
        authorize_contest(cur_user,contest)
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
    template_values       = DefaultTemplate(self.request.uri)
    display_count         = G_LIST_SIZE
    cur_index             = arg2int(self.request.get('i'))
    contests              = get_all_contests(cur_index)
    # contest order is descending. "later" is lower than "earlier"
    later_index           = max(0,cur_index-display_count)
    earlier_index         = cur_index+len(contests)
    later_contests_flag   = later_index < cur_index
    earlier_contests_flag = earlier_index == cur_index+display_count
    if earlier_contests_flag:
      earlier_contests_flag = is_contest_at(cur_index+display_count)
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
      the_user = get_myuser_from_myuser_id(user_id)
      logging.info("HandleUser/%d GET" % int(user_id))
      cur_user = template_values['cur_user']
      try:
        authorized_to_view = the_user.user == cur_user.user or users.is_current_user_admin()
        authorized_to_edit = the_user.user == cur_user.user
      except AttributeError:
        authorized_to_view = False
        authorized_to_edit = False
      predictions = get_myuser_predictions(the_user)
      closed_predictions = filter(lambda obj: get_contest_by_id(obj.contest_id).final_value >= 0.0, predictions)
      open_predictions = filter(lambda obj: get_contest_by_id(obj.contest_id).final_value < 0.0, predictions)
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
       the_user = get_myuser_from_myuser_id(user_id)
       if current_user_authorized_to_edit(the_user):
         set_myuser_nickname(the_user,self.request.get('nickname'))
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
        final_value = get_stock_price(contest.stock_symbol)
        finish_contest(contest,final_value)
    # now get each person's win/loss record straight
    update_all_users_winloss()
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
