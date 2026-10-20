"""YouTube-Videos und – soweit abrufbar – ihre Beschreibungen aktualisieren.
Aufruf im Website-Testordner: python video-feed-aktualisieren.py
yt-dlp erforderlich. Keine Zugangsdaten und kein API-Schlüssel.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CHANNEL = 'https://www.youtube.com/@andreassedlag6935/videos'
OUT = Path(__file__).resolve().parent / 'video-folgen.json'

def ytdlp(url, flat=False, timeout=50):
    command=[sys.executable,'-m','yt_dlp','--dump-single-json','--skip-download',
             '--no-warnings','--socket-timeout','12','--retries','1']
    if flat: command.append('--flat-playlist')
    command.append(url)
    try:
        result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
        if result.returncode: return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired,ValueError,OSError):
        return None

def save(videos):
    tmp=OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(videos,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(OUT)

def main():
    old={}
    if OUT.exists():
        try:
            data=json.loads(OUT.read_text(encoding='utf-8'))
            if isinstance(data,list): old={v['id']:v for v in data if isinstance(v,dict) and isinstance(v.get('id'),str)}
        except (ValueError,OSError): pass
    print('Lese öffentliche Videoliste ein …',flush=True)
    root=ytdlp(CHANNEL,flat=True,timeout=120)
    if not root or not isinstance(root.get('entries'),list):
        print('Kanalabruf fehlgeschlagen. Bestehende Videodaten bleiben erhalten.')
        sys.exit(1)
    videos=[];seen=set()
    for item in root['entries']:
        if not isinstance(item,dict):continue
        vid=item.get('id');title=item.get('title')
        if not isinstance(vid,str) or len(vid)!=11 or not isinstance(title,str) or not title or vid in seen:continue
        seen.add(vid)
        prev=old.get(vid,{})
        upload=item.get('upload_date')
        date=(f'{upload[:4]}-{upload[4:6]}-{upload[6:8]}' if isinstance(upload,str) and len(upload)==8 else prev.get('date',''))
        videos.append({'id':vid,'title':title,'description':prev.get('description') or item.get('description') or '', 'date':date})
    if old and len(videos) < len(old) * 0.8:
        print('Auffällig wenige Videos gefunden: bestehende Daten bleiben erhalten.')
        sys.exit(1)
    if not videos:
        print('Keine Videos erkannt. Bestehende Daten bleiben erhalten.')
        sys.exit(1)
    save(videos)
    missing=[v for v in videos if not v['description']]
    print(f'{len(videos)} Videos erfasst. {len(missing)} Beschreibungen werden, soweit möglich, nachgeladen …',flush=True)
    if missing:
        def fetch_one(video):
            data=ytdlp('https://www.youtube.com/watch?v='+video['id'],timeout=40)
            if not data:return video['id'],None
            return video['id'],data
        by_id={v['id']:v for v in videos}
        done=0;found=0
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(fetch_one,v) for v in missing]
            try:
                for future in as_completed(futures):
                    vid,data=future.result();done+=1
                    if data:
                        description=data.get('description')
                        if isinstance(description,str) and description.strip():
                            by_id[vid]['description']=description;found+=1
                        timestamp=data.get('upload_date')
                        if not by_id[vid]['date'] and isinstance(timestamp,str) and len(timestamp)==8:
                            by_id[vid]['date']=f'{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}'
                    if done%10==0 or done==len(missing):
                        save(videos)
                        print(f'Beschreibungen geprüft: {done}/{len(missing)}',flush=True)
            except KeyboardInterrupt:
                save(videos)
                print('Unterbrochen. Bereits geladene Daten sind gespeichert.')
                sys.exit(130)
        print(f'{found} neue Beschreibungen übernommen.',flush=True)
    print(f'Fertig: {len(videos)} Videos gespeichert in {OUT.name}.',flush=True)
    if any(not v['description'] for v in videos):
        print('Hinweis: YouTube liefert nicht zu jedem Video eine Beschreibung. Die Titelsuche funktioniert weiterhin.')

if __name__=='__main__':main()
