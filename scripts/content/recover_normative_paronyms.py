#!/usr/bin/env python3
"""Preparation only: PyMuPDF + fontTools; never needed to build or run the site."""
import fitz,io,unicodedata,json,re
from pathlib import Path
from fontTools.ttLib import TTFont
import argparse
parser=argparse.ArgumentParser(description='Recover text using embedded glyph IDs, without OCR guesses')
parser.add_argument('pdf')
parser.add_argument('output_directory')
args=parser.parse_args()
out=Path(args.output_directory);out.mkdir(parents=True,exist_ok=True)
pdf=fitz.open(args.pdf)
fontmaps={}
for page in pdf:
 for xref,ext,kind,name,*_ in page.get_fonts():
  if name in fontmaps:continue
  _,ext,_,b=pdf.extract_font(xref)
  if not b:continue
  font=TTFont(io.BytesIO(b));rev={}
  for u,g in font.getBestCmap().items():
   gid=font.getGlyphID(g)
   if gid not in rev or u==32:rev[gid]=chr(u)
  fontmaps[name]=rev
pages=[];fixed=0
for page in pdf:
 rows={}
 for span in page.get_texttrace():
  rev=fontmaps.get(span['font'],{})
  for u,g,origin,bbox in span['chars']:
   ch=chr(u)
   if ch==' ' and g!=3 and rev.get(g) not in [None,' ','\xa0']:
    ch=rev[g];fixed+=1
   y=round(origin[1],1)
   rows.setdefault(y,[]).append((origin[0],bbox,ch,span['font']))
 lines=[]
 for y,chars in sorted(rows.items()):
  chars.sort(key=lambda c:c[0]);s='';last=None
  for x,box,ch,font in chars:
   if last is not None and x-last>2.0 and not s.endswith(' ') and ch!='\u0301':s+=' '
   s+=ch;last=box[2]
  s=unicodedata.normalize('NFC',s).replace('\xa0',' ')
  plain=''.join(c for c in unicodedata.normalize('NFD',s) if c!='\u0301')
  plain=unicodedata.normalize('NFC',plain)
  if plain.strip():lines.append({'text':plain.strip(),'y':y,'firstFont':chars[0][3]})
 pages.append(lines)
(out/'pages.json').write_text(json.dumps(pages,ensure_ascii=False))
(out/'pages.txt').write_text('\n\f\n'.join('\n'.join(r['text'] for r in p) for p in pages))
print('pages',len(pages),'restored characters',fixed,'fonts',list(fontmaps))
entries=[]
for page_no,lines in enumerate(pages,1):
 if page_no<29 or page_no>1106:continue
 for line_no,row in enumerate(lines):
  m=re.match(r'^([а-яё]+(?:-[а-яё]+)?)\s*,',row['text'])
  if m and 'Bold' in row['firstFont']:
   entries.append({'headword':m[1],'pdfPage':page_no,'line':line_no})
index={}
for n,entry in enumerate(entries):
 next_e=entries[n+1] if n+1<len(entries) else {'pdfPage':1107,'line':0}
 body=[]
 for page_no in range(entry['pdfPage'],next_e['pdfPage']+1):
  for line_no,row in enumerate(pages[page_no-1]):
   if page_no==entry['pdfPage'] and line_no<entry['line']:continue
   if page_no==next_e['pdfPage'] and line_no>=next_e['line']:break
   if row['y']>790:continue
   body.append(row['text'])
 index.setdefault(entry['headword'],[]).append({**entry,'body':'\n'.join(body)})
(out/'article-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
print('articles',len(entries),'distinct lemmas',len(index))
