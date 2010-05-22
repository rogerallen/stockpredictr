#!/usr/bin/env python
import unittest
import urllib
import urllib2
import sys

# global switch to write gilded files
GILD=False
# global for the sitename.  put in config file someday
SITE='http://localhost:8080/'
# TODO this ID may only work for me.  prob should be in config file
COOKIE_ID    = '185804764220139124118'

# not sure this is necessary
USERAGENT = "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3,gzip(gfe)"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def login_cookie(email,admin_flag,cookie_id):
    """ return string in this format
      dev_appserver_login="test@example.com:True:185804764220139124118"
    """
    login_str = email+':'
    login_str += str(admin_flag)+':'
    login_str += cookie_id
    cookie_str = 'dev_appserver_login="'+login_str+'"'
    return cookie_str

def user_cookie(index=None,admin_flag=False):
    istr=""
    if index:
        istr=str(index)
    return login_cookie('test'+istr+'@example.com',admin_flag,COOKIE_ID)

def admin_cookie(index=None):
    return user_cookie(index,True)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_comparison(url, gold_file_name, values=None, headers={}):
    """Common routine to open a url and return the lines from both the
    fetched web page and the golden comparison file.  If the global
    GILD is set, then the page is saved as the golden comparison.
    """
    if values:
        data = urllib.urlencode(values)
    else:
        data = None
    request  = urllib2.Request(url,data=data,headers=headers)
    response = urllib2.urlopen(request)
    the_page = response.read()
    if GILD:
        gold_page = open('lead/'+gold_file_name,'w')
        print >>gold_page, the_page,
        gold_page.close()
        return ([],[])
    else:
        gold_page = open('gold/'+gold_file_name).read()
        the_page_lines = the_page.split('\n')
        gold_page_lines = gold_page.split('\n')
        return (the_page_lines, gold_page_lines)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def fetch_url(url, values=None, headers={}):
    """Common routine to open a url and return the lines from the page..
    """
    if values:
        data = urllib.urlencode(values)
    else:
        data = None
    request  = urllib2.Request(url,data=data,headers=headers)
    response = urllib2.urlopen(request)
    the_page = response.read()
    return the_page

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def page_name(where,tag=''):
    """given the output of self.id() e.g. __main__.TestBasics.test000RootNoLogin,
    create a good webpage name.  tag is an optional extra argument"""
    name = where + tag + '.html'
    name = name.replace('__main__.TestBasics.test', 'basic_')
    name = name.replace('__main__.TestLong.test',   'long_')
    return name

# ======================================================================
class TestBasics(unittest.TestCase):
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test000RootNoLogin(self):
        print >>sys.stderr, "test basics:",
        (the_page_lines, gold_page_lines) = get_comparison(
           SITE,
           page_name(self.id())
           )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test001RootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test002RootAddContestBadStock(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol': 'nxxx'},
            headers={'Cookie':user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test003RootAddContestMissingDate(self):
        # TODO - this error is not that great
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       '',
                    'month':      '',
                    'day':        '',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test004RootAddContestDateInPast(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       '2010',
                    'month':      '5',
                    'day':        '1',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test005RootAddContestPublic(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       '2011',
                    'month':      '9',
                    'day':        '1',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test006RootAddContestPrivate(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id()),
            values={'symbol':     'test',
                    'year':       '2011',
                    'month':      '9',
                    'day':        '2',
                    'private':    '1',
                    'passphrase': 'password'
                    },
            headers={'Cookie':user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test010AboutNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'about',
            page_name(self.id()),
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test020UserWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test021BadUserUrl(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1a3x',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test022UserWithOtherLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test023UserWithOtherLoginTryChangeNickname(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            values={'nickname': 'must fail'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test024UserChangeNickname(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1',
            page_name(self.id()),
            values={'nickname': 'mr test'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test025BadUserUrlChangeNickaname(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1a3x',
            page_name(self.id()),
            values={'nickname': 'duh'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test030ContestBadUrl(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/1w2',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test031ContestMakePrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id()),
            values={'prediction':'12'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test032ContestMakePrediction2(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id()),
            values={'prediction':'13'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test033ContestMakeBadPrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id()),
            values={'prediction':'1xz3'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test034ContestFinish(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id()),
            values={'final_value':'12.0625'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test035ContestFinishPoorly(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id()),
            values={'final_value':'1x2.0z625'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test036ContestReopen(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id()),
            values={'final_value':'-2'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test037ContestPrivateNotAllowed(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/4',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test038ContestPrivateGiveBadPassphrase(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/4',
            page_name(self.id()),
            values={'passphrase':'blahblah'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test039ContestPrivateGiveGoodPassphrase(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/4',
            page_name(self.id()),
            values={'passphrase':'password'},
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03aContestPrivateMakePrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/4',
            page_name(self.id()),
            values={'prediction':'13'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03bContestPrivateChangePrediction(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/4',
            page_name(self.id()),
            values={'prediction':'12.5'},
            headers={'User-Agent': USERAGENT,
                     'Cookie': user_cookie(2)
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test03cContestCheckStockPrices(self):
        for (i,v) in enumerate(['13.0001','1','11.1','12.52','13.99999999999999']):
            fetch_url(
                SITE+'contest/3',
                values={'prediction':v},
                headers={'Cookie': user_cookie(i+2)})
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id()),
            values={'prediction':'13'},
            headers={'Cookie': user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test040MissingUrl(self):
        self.assertRaises(urllib2.HTTPError,
                          get_comparison,
                          SITE+'gobbledygook',
                          page_name(self.id()),
                          None,
                          {'User-Agent': USERAGENT,
                           'Cookie':user_cookie()
                           }
                          )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test050FinishContestsFail(self):
        self.assertRaises(urllib2.HTTPError,
                          get_comparison,
                          SITE+'admin/finish_any',
                          page_name(self.id()),
                          None,
                          {'User-Agent': USERAGENT,
                           'Cookie':user_cookie()
                           }
                          )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test051FinishContests(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'admin/finish_any',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':admin_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test060ContestsBadIndex(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=x3',
            page_name(self.id()),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
            
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
class TestLong(unittest.TestCase):

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # extra long test
    def test000AddLotsOfTests(self):
        print  >>sys.stderr, "\ntest long:",
        # add a gob of contests
        for month in [ '10', '11', '12' ]:
            for day in range(30):
                fetch_url(
                    SITE,
                    values={'symbol':     'test',
                            'year':       '2011',
                            'month':      month,
                            'day':        str(day),
                            'private':    '',
                            'passphrase': ''
                            },
                    headers={'Cookie':user_cookie()}
                    )
        # see only 25 on homepage
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,
            page_name(self.id(),'A'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=0',
            page_name(self.id(),'B'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=25',
            page_name(self.id(),'C'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=50',
            page_name(self.id(),'D'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=75',
            page_name(self.id(),'E'),
            headers={'User-Agent': USERAGENT,
                     'Cookie':user_cookie()
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test001ContestAddLotsOfPredictions(self):
        for (i,v) in enumerate(range(55)):
            fetch_url(
                SITE+'contest/3',
                values={'prediction': 10.0+v/10.0 },
                headers={'Cookie':    user_cookie(i) })
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3',
            page_name(self.id(),'A'),
            headers={'Cookie': user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3?i=25',
            page_name(self.id(),'B'),
            headers={'Cookie': user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/3?i=50',
            page_name(self.id(),'C'),
            headers={'Cookie': user_cookie()}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

        
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    print "Expecting clear-config app-engine already active..."
    if len(sys.argv) > 1 and 'gild' in sys.argv:
        print "GILD MODE ON.  Writing files to the 'lead' directory."
        GILD=True
        sys.argv.remove('gild')
    unittest.main()
