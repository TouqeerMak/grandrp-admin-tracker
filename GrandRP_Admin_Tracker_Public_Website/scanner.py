"""Grand RP XenForo forum 36 scanner. Role tags are internal verification only.

Never requests user-supplied URLs; redirects restricted to Grand RP /forum/.
Results are *current latest reply* snapshots, not historic action logs.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, date, timezone
from email.utils import parsedate_to_datetime
import re
from typing import AsyncIterator
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag

FORUM_URL = 'https://gta5grand.com/forum/forums/36/'
TZ = ZoneInfo('Europe/London')
PAGE_LIMIT = 50
DELAY_SECONDS = 0.65
MAX_THREADS = 10000
ADMIN_ROLE_WORDS = ('admin', 'administrator')
RESOLVED = re.compile(r'\b(approved|rejected|reviewed|accepted|denied|closed|resolved|finished|completed|declined)\b', re.I)

class ScanError(Exception):
    pass

def normalize(text: str | None) -> str:
    return ' '.join((text or '').split())

def eltext(el) -> str:
    return normalize(el.get_text(' ', strip=True)) if el else ''

def checked_url(href: str | None, base: str = FORUM_URL) -> str | None:
    if not href:
        return None
    full = urljoin(base, href)
    u = urlparse(full)
    if (u.scheme != 'https' or u.hostname != 'gta5grand.com' or
            u.port not in (None, 443) or not u.path.startswith('/forum/')):
        return None
    return full

def thread_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r'/threads/(?:[^/]*\.)?(\d+)(?:/|$)', urlparse(url).path)
    return match.group(1) if match else None

def date_from_node(node: Tag | None, now: datetime | None = None) -> int | None:
    if not node:
        return None
    value = node.get('data-time')
    if value and re.fullmatch(r'\d{9,13}', str(value)):
        ms = int(value)
        return ms if len(str(value)) >= 13 else ms * 1000
    for attr in ('datetime', 'title'):
        val = node.get(attr)
        if val:
            try:
                result = datetime.fromisoformat(str(val).replace('Z', '+00:00'))
                if result.tzinfo is None:
                    result = result.replace(tzinfo=TZ)
                return int(result.timestamp() * 1000)
            except ValueError:
                try:
                    result = parsedate_to_datetime(str(val))
                    return int(result.timestamp() * 1000)
                except (TypeError, ValueError, OverflowError):
                    pass
    text = eltext(node)
    today = (now or datetime.now(TZ)).astimezone(TZ)
    m = re.match(r'^([0-9]+)\s+(seconds?|minutes?|hours?)\s+ago$', text, re.I)
    if m:
        unit = m.group(2).lower()
        multiplier = 1 if unit.startswith('second') else 60 if unit.startswith('minute') else 3600
        return int((today - timedelta(seconds=int(m.group(1))*multiplier)).timestamp() * 1000)
    if text.lower() == 'a moment ago':
        return int(today.timestamp() * 1000)
    m = re.match(r'^(today|yesterday)\s+at\s+(\d{1,2}):(\d{2})\s*(AM|PM)?$', text, re.I)
    if m:
        d = today.date() - timedelta(days=(m.group(1).lower() == 'yesterday'))
        hour = int(m.group(2))
        if m.group(4):
            hour = (hour % 12) + (12 if m.group(4).lower() == 'pm' else 0)
        try:
            return int(datetime(d.year,d.month,d.day,hour,int(m.group(3)),tzinfo=TZ).timestamp()*1000)
        except ValueError:
            return None
    try:
        result = parsedate_to_datetime(text)
        if result.tzinfo is None:
            result = result.replace(tzinfo=TZ)
        return int(result.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return None

@dataclass
class Row:
    id: str
    title: str
    url: str
    latest_url: str
    last_user: str
    member_url: str | None
    date: int | None
    status: str
    sticky: bool

def parse_listing(html: str, url: str = FORUM_URL) -> tuple[list[Row], str | None, int]:
    soup = BeautifulSoup(html, 'html.parser')
    nodes = soup.select('.structItem--thread')
    rows = []
    for node in nodes:
        anchors = [a for a in node.select('.structItem-title a[href*="/threads/"]')
                   if 'labelLink' not in a.get('class', ()) and not a.find_parent(class_='label')]
        if not anchors:
            continue
        title = anchors[0]
        thread_url = checked_url(title.get('href'), url)
        id = thread_id(thread_url)
        if not id or not thread_url:
            continue
        latest = node.select_one('.structItem-cell--latest')
        if not latest:
            latest_date = node.select_one('.structItem-latestDate')
            latest = latest_date.parent if latest_date else None
        date_node = latest.select_one('time[data-time], time[datetime], .u-dt[data-time], .u-dt[datetime], time, .u-dt') if latest else None
        date_ms = date_from_node(date_node)
        latest_link = latest.select_one('.structItem-latestDate a[href]') if latest else None
        if not latest_link and date_node:
            latest_link = date_node.find_parent('a', href=True)
        if not latest_link and latest:
            latest_link = latest.select_one('a[href*="/threads/"]')
        latest_url = checked_url(latest_link.get('href'), url) if latest_link else None
        username = latest.select_one('.username, a[href*="/members/"]') if latest else None
        label = node.select_one('.structItem-title .label, .structItem-title .labelLink')
        rows.append(Row(id=id, title=eltext(title), url=thread_url, latest_url=latest_url or thread_url,
                        last_user=eltext(username), member_url=checked_url(username.get('href'),url) if username else None,
                        date=date_ms, status=eltext(label) or 'Unlabelled',
                        sticky=('structItem--sticky' in node.get('class', ()) or bool(node.select_one('.structItem-status--sticky')))))
    next_link = soup.select_one('.pageNav-jump--next[href], a[rel="next"][href]')
    return rows, checked_url(next_link.get('href'),url) if next_link else None, len(nodes)

def parse_latest_post(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    posts = soup.select('.message--post, article.message')
    if not posts:
        return {'found':False}
    post = posts[-1]
    username = post.select_one('.message-name .username, .message-userDetails .username, .message-name')
    member = post.select_one('.message-name a[href*="/members/"]')
    roles = [eltext(el) for el in post.select('.message-userTitle, .userTitle, .message-userBanner, .userBanner')]
    return {'found':True, 'name': eltext(username) or normalize(post.get('data-author')),
            'member_url': checked_url(member.get('href')) if member else None,
            'roles': list(dict.fromkeys(filter(None, roles)))}

def is_admin_role(roles: list[str]) -> bool:
    source = ' '.join(roles).lower()
    if re.search(r'\b(?:ex[- ]?admin|former admin|retired administrator)\b', source):
        return False
    return any(re.search(r'(?<![a-z])'+re.escape(w)+r'(?![a-z])', source) for w in ADMIN_ROLE_WORDS)

def member_key(url: str | None, name: str) -> str:
    match = re.search(r'/members/(?:[^/]*\.)?(\d+)(?:/|$)', urlparse(url or '').path)
    return 'member:' + match.group(1) if match else 'name:' + name.casefold().strip()

def same_poster(row: Row, post: dict) -> bool:
    if row.member_url and post.get('member_url'):
        return member_key(row.member_url, row.last_user) == member_key(post['member_url'],post.get('name',''))
    if row.last_user and post.get('name'):
        return row.last_user.casefold().strip() == post['name'].casefold().strip()
    return False

def parse_date(raw: str) -> date:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw or ''):
        raise ScanError('Choose a valid start and end date.')
    try:
        return date.fromisoformat(raw)
    except ValueError as e:
        raise ScanError('Choose valid calendar dates.') from e

def period_bounds(preset: str, start: str = '', end: str = '', now: datetime | None = None) -> dict:
    today = (now or datetime.now(TZ)).astimezone(TZ).date()
    d1 = d2 = today
    if preset == 'today': pass
    elif preset == 'yesterday': d1 = d2 = today - timedelta(days=1)
    elif preset == 'week': d1 = today - timedelta(days=today.weekday())
    elif preset == 'previous-week':
        d1 = today - timedelta(days=today.weekday()+7)
        d2 = d1+timedelta(days=6)
    elif preset == 'last7': d1 = today-timedelta(days=6)
    elif preset == 'month': d1 = today.replace(day=1)
    elif preset == 'previous-month':
        d2 = today.replace(day=1)-timedelta(days=1)
        d1 = d2.replace(day=1)
    elif preset == 'last30': d1 = today-timedelta(days=29)
    elif preset == 'custom':
        d1, d2 = parse_date(start), parse_date(end)
    else: raise ScanError('Unknown date range.')
    if d1 > d2:
        raise ScanError('The start date must be before the end date.')
    if d1 > today:
        raise ScanError('The selected date range starts in the future.')
    if (d2-d1).days > 366:
        raise ScanError('Select a range of 367 days or less.')
    start_ms = int(datetime(d1.year,d1.month,d1.day,tzinfo=TZ).timestamp()*1000)
    next_day = d2+timedelta(days=1)
    end_ms = int(datetime(next_day.year,next_day.month,next_day.day,tzinfo=TZ).timestamp()*1000)
    return {'start':start_ms,'end_exclusive':end_ms,'from':d1.isoformat(),'to':d2.isoformat(),
            'label':f'{d1.isoformat()} to {d2.isoformat()}', 'timezone':'Europe/London'}

class ForumClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client=client
        self.request_count=0

    async def html(self,url: str) -> str:
        if not checked_url(url):
            raise ScanError('Disallowed forum URL encountered.')
        for retry in range(3):
            await asyncio.sleep(DELAY_SECONDS if retry == 0 else (retry * 2.0))
            current=url
            for redirect in range(4):
                try:
                    response=await self.client.get(current,follow_redirects=False,timeout=25)
                except (httpx.TimeoutException,httpx.TransportError) as e:
                    raise ScanError(f'Could not connect to Grand RP: {type(e).__name__}.') from e
                self.request_count+=1
                if response.status_code in (301,302,303,307,308):
                    destination=checked_url(response.headers.get('location'), current)
                    if not destination:
                        raise ScanError('Grand RP redirected outside the allowed forum.')
                    current=destination
                    continue
                break
            else:
                raise ScanError('Too many Grand RP redirects.')
            if response.status_code in (429,500,502,503,504) and retry < 2:
                continue
            if response.status_code == 403:
                raise ScanError('Grand RP returned HTTP 403 (access blocked). A normal website cannot bypass this protection. Try importing a CSV from the Chrome extension.')
            if response.status_code == 429:
                raise ScanError('Grand RP is rate-limiting scans (HTTP 429). Try again later.')
            if response.status_code != 200:
                raise ScanError(f'Grand RP returned HTTP {response.status_code}.')
            if len(response.content)>4_000_000:
                raise ScanError('Forum response exceeded the safety limit.')
            html=response.text
            if re.search(r'<title[^>]*>\s*(just a moment|attention required|security check)', html,re.I) or 'cf-chl-widget' in html or 'cf-browser-verification' in html:
                raise ScanError('Grand RP showed a security challenge. A server-side scanner cannot complete it; import a CSV from the extension instead.')
            return html
        raise ScanError('Grand RP request failed after retries.')

async def scan(preset: str, start: str = '', end: str = '', client: httpx.AsyncClient | None = None) -> AsyncIterator[dict]:
    period=period_bounds(preset,start,end)
    state={'type':'progress','phase':'Starting','period':period,'results':[], 'pages':0,
           'scanned':0,'errors':0,'missing_dates':0,'complete':False,'status':'scanning','message':''}
    seen, visited, roles={},set(),{}
    older_pages=0
    reason=''
    own_client=client is None
    if own_client:
        client=httpx.AsyncClient(headers={'User-Agent':'Mozilla/5.0 (compatible; GrandRPAdminDashboard/1.0)',
                                          'Accept':'text/html,application/xhtml+xml',
                                          'Accept-Language':'en-US,en;q=0.9'},follow_redirects=False)
    fetcher=ForumClient(client)
    try:
        next_url=FORUM_URL
        for page in range(1,PAGE_LIMIT+1):
            if not next_url or next_url in visited:
                state['complete']=True
                reason='Reached the final forum page.'
                break
            visited.add(next_url)
            state.update(phase=f'Reading forum page {page}/{PAGE_LIMIT}',pages=page-1)
            yield dict(state)
            html=await fetcher.html(next_url)
            rows,next_link,row_count=parse_listing(html,next_url)
            if page==1 and not row_count:
                raise ScanError('No thread rows were found on forum 36. The page may require login, may be a parent category, or its layout may have changed.')
            state['pages']=page
            candidates=[]
            for row in rows:
                if row.id in seen:continue
                seen[row.id]=True
                if row.date is None:
                    state['missing_dates']+=1
                elif period['start']<=row.date<period['end_exclusive']:
                    candidates.append(row)
            state['scanned']+=len(candidates)
            for index,row in enumerate(candidates):
                key=member_key(row.member_url,row.last_user) if row.last_user else None
                entry=roles.get(key) if key else None
                if entry is None:
                    url=row.url.rstrip('/')+'/latest'
                    try:
                        post=parse_latest_post(await fetcher.html(url))
                        if not post['found'] or not same_poster(row,post):
                            state['errors']+=1
                            continue
                        entry={'admin':is_admin_role(post['roles']), 'name':post['name'],
                               'admin_id':member_key(post.get('member_url'),post['name'])}
                        if key:roles[key]=entry
                    except ScanError as e:
                        # Access blocks cannot be reported as clean zero counts.
                        if 'HTTP 403' in str(e) or 'HTTP 429' in str(e) or 'security challenge' in str(e):raise
                        state['errors']+=1
                        continue
                if entry['admin']:
                    state['results'].append({'id':row.id, 'title':row.title, 'url':row.url,
                                              'date':row.date, 'status':row.status,
                                              'name':entry['name'], 'adminId':entry['admin_id']})
                if (index+1)%5==0:
                    state['phase']=f'Page {page}/{PAGE_LIMIT} · checked {index+1}/{len(candidates)} threads'
                    yield dict(state, results=list(state['results']))
            state['phase']=f'Checked page {page}/{PAGE_LIMIT}'
            yield dict(state, results=list(state['results']))
            standard=[r for r in rows if not r.sticky and r.date is not None]
            if standard and all(r.date < period['start'] for r in standard):
                older_pages+=1
            else:older_pages=0
            if older_pages>=2:
                state['complete']=True
                reason='Reached threads older than the selected range.'
                break
            if not next_link:
                state['complete']=True
                reason='Reached the final forum page.'
                break
            next_url=next_link
            if len(seen)>=MAX_THREADS:
                reason='Stopped at the 10,000-thread safety limit.'
                break
            if page==PAGE_LIMIT:
                reason='Reached the hidden 50-page limit before proving full coverage.'
    except ScanError as e:
        reason=str(e)
    finally:
        if own_client:
            await client.aclose()
    state.update(type='done',status='complete' if state['complete'] and not state['errors'] and not state['missing_dates'] else 'partial',
                 phase='Finished', message=reason, requests=fetcher.request_count)
    yield dict(state, results=list(state['results']))
