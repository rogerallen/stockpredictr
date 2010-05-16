#!/usr/bin/env python
import unittest
import urllib
import urllib2
import sys

# global switch to write gilded files
GILD=False
# global for the sitename
SITE='http://localhost:8080/'
# TODO these may only work for me.  prob should be in config file, not
# checked in
NOADMIN_COOKIE = 'dev_appserver_login="test@example.com:False:185804764220139124118"'
ADMIN_COOKIE = 'dev_appserver_login="test@example.com:True:185804764220139124118"'
USERAGENT = "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3,gzip(gfe)"

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
class TestBasics(unittest.TestCase):

    def test000RootNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'basics000.html'
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test001RootWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'basics001.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test002RootAddBadStock(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'basics002.html',
            values={'symbol': 'nxxx'},
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    def test003RootAddMissingDate(self):
        # TODO - this error is not that great
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'basics003.html',
            values={'symbol':     'test',
                    'year':       '',
                    'month':      '',
                    'day':        '',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    def test004RootAddDateInPast(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'basics004.html',
            values={'symbol':     'test',
                    'year':       '2010',
                    'month':      '5',
                    'day':        '1',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        
    def test005RootAddPublic(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'basics005.html',
            values={'symbol':     'test',
                    'year':       '2011',
                    'month':      '10',
                    'day':        '10',
                    'private':    '',
                    'passphrase': ''
                    },
            headers={'Cookie':NOADMIN_COOKIE}
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test006AboutNoLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'about','basics006.html'
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test007UserWithLogin(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1','basics007.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test008BadUserUrl(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'user/1a3x','basics008.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test009BadContestUrl(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contest/1w2','basics009.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test00aMissingUrl(self):
        self.assertRaises(urllib2.HTTPError,
                          get_comparison,
                          SITE+'gobbledygook',
                          'basics00a.html',
                          None,
                          {'User-Agent': USERAGENT,
                           'Cookie':NOADMIN_COOKIE
                           }
                          )

    def test010AddLotsOfTests(self):
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
                    headers={'Cookie':NOADMIN_COOKIE}
                    )
        # see only 25 on homepage
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE,'basics010a.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=0','basics010b.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=25','basics010c.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=50','basics010d.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])
        # see 25 at a time in contests page
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'contests?i=75','basics010e.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':NOADMIN_COOKIE
                     }
            )
        for i in range(len(max(the_page_lines,gold_page_lines))):
            self.assertEqual(the_page_lines[i],gold_page_lines[i])

    def test020FinishContestsFail(self):
        self.assertRaises(urllib2.HTTPError,
                          get_comparison,
                          SITE+'admin/finish_any',
                          'basics020.html',
                          None,
                          {'User-Agent': USERAGENT,
                           'Cookie':NOADMIN_COOKIE
                           }
                          )

    def test021FinishContests(self):
        (the_page_lines, gold_page_lines) = get_comparison(
            SITE+'admin/finish_any','basics021.html',
            headers={'User-Agent': USERAGENT,
                     'Cookie':ADMIN_COOKIE
                     }
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
