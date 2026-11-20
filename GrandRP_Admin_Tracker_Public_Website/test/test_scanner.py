import asyncio
from datetime import datetime, timezone
import unittest

from bs4 import BeautifulSoup
import httpx

from scanner import (FORUM_URL, TZ, checked_url, date_from_node, is_admin_role,
                     parse_listing, parse_latest_post, period_bounds, scan)

LISTING = '''
<html><body>
<div class="structItem structItem--thread"><div class="structItem-title"><span class="label">Approved</span><a href="/forum/threads/test-thread.101/">Test complaint</a></div>
<div class="structItem-cell--latest"><a class="username" href="/forum/members/mod.55/">Alice</a><div class="structItem-latestDate"><a href="/forum/threads/test-thread.101/post-90"><time data-time="1795200000">Today</time></a></div></div></div>
<div class="structItem structItem--thread"><div class="structItem-title"><a href="/forum/threads/another.102/">Another complaint</a></div><div class="structItem-cell--latest"><a class="username" href="/forum/members/user.56/">Bob</a><div class="structItem-latestDate"><a href="/forum/threads/another.102/post-88"><time data-time="1795200000">Today</time></a></div></div></div>
</body></html>
'''
ADMIN_POST = '''<html><body><article class="message message--post" data-author="Alice"><div class="message-name"><a class="username" href="/forum/members/mod.55/">Alice</a></div><div class="message-userTitle">Good Boy! · Server Administrator</div></article></body></html>'''
USER_POST = '''<html><body><article class="message message--post" data-author="Bob"><div class="message-name"><a class="username" href="/forum/members/user.56/">Bob</a></div><div class="message-userTitle">Member</div></article></body></html>'''

class ParseTest(unittest.TestCase):
    def test_roles(self):
        for label in ['Server Administrator','Senior Admin','Director · Server Administrator',
                      'Good Boy! · Server Administrator','LSPD, GOV · Senior Administrator']:
            self.assertTrue(is_admin_role([label]), label)
        for label in ['Member','Forum Member','Ex Admin','Former Admin', 'Retired Administrator', 'Administrative Assistant']:
            self.assertFalse(is_admin_role([label]), label)

    def test_listing(self):
        rows,nxt,count=parse_listing(LISTING,FORUM_URL)
        self.assertEqual(count,2)
        self.assertIsNone(nxt)
        self.assertEqual([x.id for x in rows],['101','102'])
        self.assertEqual(rows[0].status,'Approved')
        self.assertEqual(rows[0].member_url,'https://gta5grand.com/forum/members/mod.55/')
        self.assertEqual(rows[0].date,1795200000*1000)

    def test_latest(self):
        p=parse_latest_post(ADMIN_POST)
        self.assertEqual(p['name'],'Alice')
        self.assertTrue(is_admin_role(p['roles']))
        self.assertTrue(p['member_url'].endswith('mod.55/'))

    def test_url_restriction(self):
        self.assertIsNone(checked_url('http://gta5grand.com/forum/threads/4/'))
        self.assertIsNone(checked_url('https://example.com/forum/threads/4/'))
        self.assertIsNone(checked_url('https://gta5grand.com/other/'))
        self.assertTrue(checked_url('/forum/threads/x.5/').startswith('https://gta5grand.com'))

    def test_period(self):
        now=datetime(2026,11,21,10,30,tzinfo=TZ)
        self.assertEqual(period_bounds('week',now=now)['from'],'2026-11-16')
        self.assertEqual(period_bounds('week',now=now)['to'],'2026-11-21')
        self.assertEqual(period_bounds('previous-week',now=now)['from'],'2026-11-09')
        self.assertEqual(period_bounds('previous-week',now=now)['to'],'2026-11-15')
        self.assertEqual(period_bounds('previous-month',now=now)['from'],'2026-10-01')
        self.assertEqual(period_bounds('previous-month',now=now)['to'],'2026-10-31')
        self.assertEqual(period_bounds('custom','2026-11-01','2026-11-10',now)['to'],'2026-11-10')

    def test_london_timezone_and_dst_boundaries(self):
        self.assertEqual(TZ.key, 'Europe/London')
        winter = period_bounds('custom', '2026-01-15', '2026-01-15')
        summer = period_bounds('custom', '2026-07-15', '2026-07-15')
        self.assertEqual(winter['timezone'], 'Europe/London')
        self.assertEqual(winter['start'], int(datetime(2026,1,15,tzinfo=timezone.utc).timestamp()*1000))
        self.assertEqual(summer['start'], int(datetime(2026,7,14,23,tzinfo=timezone.utc).timestamp()*1000))
        self.assertEqual(summer['end_exclusive'] - summer['start'], 24*3600*1000)
        spring = period_bounds('custom', '2026-03-29', '2026-03-29')
        autumn = period_bounds('custom', '2026-10-25', '2026-10-25')
        self.assertEqual(spring['end_exclusive']-spring['start'], 23*3600*1000)
        self.assertEqual(autumn['end_exclusive']-autumn['start'], 25*3600*1000)

    def test_london_today_before_utc_day_ends(self):
        # At 00:30 in Perth on Nov 21, London is still on Nov 20.
        from datetime import timedelta
        perth_now = datetime(2026,11,21,0,30,tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(period_bounds('today',now=perth_now)['from'],'2026-11-20')

    def test_relative_timestamp(self):
        tag=BeautifulSoup('<time data-time="1795200000">some date</time>','html.parser').select_one('time')
        self.assertEqual(date_from_node(tag),1795200000000)

class ScanTest(unittest.IsolatedAsyncioTestCase):
    async def test_scan_admin_and_nonadmin(self):
        timestamp=datetime.now(TZ).timestamp()
        listing=LISTING.replace('1795200000',str(int(timestamp)))
        def respond(req):
            if req.url.path.endswith('forums/36/'):
                return httpx.Response(200,text=listing)
            if req.url.path.endswith('101/latest'):
                return httpx.Response(200,text=ADMIN_POST)
            if req.url.path.endswith('102/latest'):
                return httpx.Response(200,text=USER_POST)
            return httpx.Response(404,text='Not found')
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            reports=[evt async for evt in scan('today',client=client)]
        final=reports[-1]
        self.assertEqual(final['status'],'complete')
        self.assertEqual(final['scanned'],2)
        self.assertEqual(len(final['results']),1)
        self.assertEqual(final['results'][0]['name'],'Alice')
        self.assertNotIn('role',final['results'][0])

if __name__=='__main__':unittest.main()
