#!/usr/bin/env python3
"""Create an offline preview of the actual installed wallpaper videos."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'branding/wallpapers/animated/sources.json'
OUT = ROOT / 'out/wallpaper-previews/index.html'


def static_preview():
    source = ROOT / 'branding/wallpapers/scenes/sources.json'
    if not source.exists():
        return
    entries = json.loads(source.read_text())
    categories = {'Space': 'Universo', 'Abstract': 'Astratti', 'Nature': 'Natura'}
    sections = []
    base = '../../branding/wallpapers/scenes/'
    for category, label in categories.items():
        cards = []
        for entry in entries:
            if entry['category'] != category:
                continue
            cards.append(f'''<article><a href="{base}{html.escape(entry['file'])}">
                <img loading="lazy" src="{base}{html.escape(entry['file'])}" alt="{html.escape(entry['title'])}"></a>
                <h3>{html.escape(entry['title'])}</h3><p>{entry['size'][0]} × {entry['size'][1]} ·
                <a href="{html.escape(entry['source_url'])}">{html.escape(entry['author'])}</a></p></article>''')
        sections.append(f'<h2>{label} · {len(cards)}</h2><div class="grid">' + ''.join(cards) + '</div>')
    page = '''<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Aurora · Sfondi statici</title>
<style>:root{color-scheme:dark;font:16px system-ui;background:#10111b;color:#eeeaf8}
body{max-width:1200px;margin:auto;padding:28px}a{color:#cbb8ff}p{color:#b6b1c8}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:22px}
article{background:#222034;border-radius:14px;overflow:hidden}img{width:100%;aspect-ratio:16/9;object-fit:cover}
h3,article p{margin:12px 16px}</style><h1>Aurora · 15 nuovi sfondi statici</h1>
<p>Scaricati dalle raccolte di wallpaper di Unsplash. Clicca un’immagine per aprirla a piena risoluzione.</p>
<p><a href="index.html">Sfondi animati</a> · <a href="../../branding/wallpapers/scenes/CREDITS.txt">Crediti e licenze</a></p>
SECTIONS</html>'''.replace('SECTIONS', ''.join(sections))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    (OUT.parent / 'static.html').write_text(page)


def main():
    static_preview()
    entries = json.loads(SOURCE.read_text())
    base = '../../branding/wallpapers/animated/'
    review_file = ROOT / 'work/downloaded-wallpapers/review.json'
    review = json.loads(review_file.read_text()) if review_file.exists() else {}
    for entry in entries:
        entry['preview_base'] = base
    proposals = OUT.parent / 'candidates/sources.json'
    if proposals.exists():
        installed = {e['id'] for e in entries}
        decisions = review.get('decisions', {})
        for entry in json.loads(proposals.read_text()):
            if entry['id'] not in installed and decisions.get(entry['id']) != 'replace':
                entry.update(preview_base='candidates/', proposal=True)
                entries.append(entry)
    cards = []
    for entry in entries:
        cards.append(f'''<button class="card" data-id="{html.escape(entry['id'])}"
            data-category="{html.escape(entry['category'])}" aria-pressed="false">
            <img src="{entry['preview_base']}{html.escape(entry['poster'])}" loading="lazy" alt="">
            <span>{html.escape(entry['title'])}<small class="filename">{html.escape(entry['file'])}</small>
            {'<small>Da valutare</small>' if entry.get('proposal') else '<small>Approvato</small>'}
            {'<small>4K · 3840 × 2160</small>' if entry.get('width') == 3840 else ''}</span></button>''')
    payload = json.dumps(entries, ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aurora — COUNT sfondi animati</title>
<style>
:root{color-scheme:dark;font:16px system-ui;background:#10111b;color:#eeeaf8}
body{max-width:1120px;margin:auto;padding:28px}h1{margin:0;font-size:28px}
p{color:#b6b1c8;line-height:1.6}video{width:100%;aspect-ratio:16/9;background:#000;
object-fit:cover;border-radius:18px;box-shadow:0 14px 45px #0005}a{color:#cbb8ff}
.meta{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}
nav{display:flex;gap:8px;margin:24px 0}button{cursor:pointer;color:inherit;font:inherit;
border:1px solid #49435f;background:#222034;border-radius:12px;padding:10px 18px}
button[aria-pressed=true]{border-color:#b89af8;background:#3a2b56}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px}
.card{padding:0;overflow:hidden;text-align:left}.card img{display:block;width:100%;
aspect-ratio:16/9;object-fit:cover}.card span{display:block;padding:12px}
.filename{display:block;margin-top:5px;font-size:12px}.card[hidden]{display:none}small{color:#b6b1c8}button:focus-visible{outline:3px solid #d8c8ff}
</style><h1>Aurora · COUNT sfondi animati</h1>
<p>APPROVED approvati · PROPOSED nuove proposte da valutare.
Scegli una miniatura per guardare il video a grandezza piena.</p>
<video id="player" controls autoplay muted loop playsinline preload="metadata"></video>
<div class="meta"><div><h2 id="name"></h2><small id="details"></small></div>
<a id="source" target="_blank" rel="noopener">Autore e fonte</a></div>
<nav aria-label="Categorie"><button data-filter="All" aria-pressed="true">Tutti (COUNT)</button>
<button data-filter="Nature" aria-pressed="false">Natura</button>
<button data-filter="Space" aria-pressed="false">Universo</button>
<button data-filter="Abstract" aria-pressed="false">Astratti</button></nav>
<nav aria-label="Altre categorie"><button data-filter="Anime" aria-pressed="false">Anime</button>
<button data-filter="Fantasy" aria-pressed="false">Fantasy</button>
<button data-filter="Illustration" aria-pressed="false">Illustrazioni</button></nav>
<p><a href="static.html">15 nuovi sfondi statici · universo, astratti e natura</a></p>
<div class="grid">CARDS</div>
<p><a href="../../branding/wallpapers/animated/CREDITS.txt">Crediti e licenze</a> ·
PROPOSALCREDITS Gli sfondi approvati sono disponibili nelle Impostazioni di Aurora.</p>
<script>
const entries=PAYLOAD, base='../../branding/wallpapers/animated/';
const player=document.querySelector('#player');
function choose(id){const item=entries.find(e=>e.id===id);player.pause();
player.poster=item.preview_base+item.poster;player.src=item.preview_base+item.file;player.load();player.play().catch(()=>{});
document.querySelector('#name').textContent=item.title;
document.querySelector('#details').textContent=(item.width?item.width+' × '+item.height+' · ':'')+item.author+' · '+item.license;
document.querySelector('#source').href=item.source_url;
document.querySelectorAll('.card').forEach(b=>b.setAttribute('aria-pressed',b.dataset.id===id));}
document.querySelectorAll('.card').forEach(b=>b.addEventListener('click',()=>choose(b.dataset.id)));
document.querySelectorAll('[data-filter]').forEach(b=>b.addEventListener('click',()=>{
document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',x===b));
document.querySelectorAll('.card').forEach(x=>x.hidden=b.dataset.filter!=='All'&&x.dataset.category!==b.dataset.filter);}));
const requested=new URLSearchParams(location.search).get('wallpaper') || location.hash.slice(1) || DEFAULT;
choose(entries.some(e=>e.id===requested)?requested:entries[0].id);
</script></html>'''.replace('CARDS', '\n'.join(cards)).replace('PAYLOAD', payload).replace('COUNT', str(len(entries)))
    proposed = sum(bool(e.get('proposal')) for e in entries)
    page = page.replace('APPROVED', str(len(entries) - proposed)).replace('PROPOSED', str(proposed))
    page = page.replace('DEFAULT', json.dumps(review.get('current_proposal', '')))
    page = page.replace('PROPOSALCREDITS', '<a href="candidates/CREDITS.txt">Crediti delle proposte</a> ·' if proposed else '')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(OUT)


if __name__ == '__main__':
    main()
