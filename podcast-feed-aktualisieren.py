"""Podcast RSS -> lokale JSON-Datei, nur Python-Standardbibliothek.
Ausführen im Website-Hauptordner: python podcast-feed-aktualisieren.py
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import json
import re
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

FEED = 'https://anchor.fm/s/10a1c1668/podcast/rss'
DEST = Path(__file__).with_name('podcast-folgen.json')
ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
MEDIA = '{http://search.yahoo.com/mrss/}'

class ShownotesParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.anchor=None
    def handle_starttag(self, tag, attrs):
        if tag in ('br','p','div','li','h1','h2','h3','h4'): self.parts.append('\n')
        if tag=='li': self.parts.append('• ')
        if tag=='a': self.anchor=dict(attrs).get('href','')
    def handle_endtag(self, tag):
        if tag=='a':
            if self.anchor and self.anchor.startswith(('https://','http://')):
                self.parts.append(' ('+self.anchor+')')
            self.anchor=None
        if tag in ('p','div','li','h1','h2','h3','h4'): self.parts.append('\n')
    def handle_data(self, data): self.parts.append(data)

def clean(value):
    parser=ShownotesParser();parser.feed(value or '')
    result=unescape(''.join(parser.parts)).replace('\r','')
    return re.sub(r'\n{3,}','\n\n',result).strip()

def text(item, key):
    el = item.find(key)
    return (el.text or '').strip() if el is not None else ''

try:
    req = Request(FEED, headers={'User-Agent': 'as-courage-PodcastMediathek/1.0'})
    with urlopen(req, timeout=25) as response:
        content = response.read(12_000_000)
    root = ET.fromstring(content)
    channel = root.find('./channel')
    default_cover = ''
    if channel is not None:
        podcast_image = channel.find(f'{ITUNES}image')
        if podcast_image is not None:
            default_cover = podcast_image.get('href', '').strip()
        if not default_cover:
            default_cover = text(channel, 'image/url')
    entries = []
    for item in root.findall('./channel/item'):
        enclosure = item.find('enclosure')
        audio = enclosure.get('url','').strip() if enclosure is not None else ''
        if not audio.startswith('https://'): continue
        raw_date = text(item, 'pubDate')
        try: date = parsedate_to_datetime(raw_date).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError): date = ''
        episode_cover = ''
        episode_image = item.find(f'{ITUNES}image')
        if episode_image is not None:
            episode_cover = episode_image.get('href', '').strip()
        if not episode_cover:
            thumbnail = item.find(f'{MEDIA}thumbnail')
            if thumbnail is not None:
                episode_cover = thumbnail.get('url', '').strip()
        if not episode_cover:
            episode_cover = default_cover
        if not episode_cover.startswith('https://'):
            episode_cover = ''
        description = text(item, 'description') or text(item, '{http://www.itunes.com/dtds/podcast-1.0.dtd}summary')
        entries.append({'title':text(item,'title'), 'description':clean(description), 'audio':audio,
                        'date':date, 'link':text(item,'link'), 'cover':episode_cover})
    if not entries:
        raise ValueError('Der RSS-Feed lieferte keine Folgen mit HTTPS-Audiodatei. Vorhandene Daten bleiben erhalten.')
    entries.sort(key=lambda e:e['date'],reverse=True)
    if DEST.exists():
        previous = json.loads(DEST.read_text(encoding='utf-8'))
        if isinstance(previous, list) and len(previous) >= 20 and len(entries) < len(previous) * 0.8:
            raise ValueError('RSS-Feed liefert auffällig wenige Folgen: bestehende Daten bleiben erhalten.')
    tmp = DEST.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(DEST)
    print(f'{len(entries)} Folgen gespeichert: {DEST.name}')
except Exception as exc:
    raise SystemExit(f'Keine Aktualisierung durchgeführt: {exc}')
