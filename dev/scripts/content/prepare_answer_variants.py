#!/usr/bin/env python3
import argparse,json,hashlib,re
from pathlib import Path
parser=argparse.ArgumentParser(description='Prepare explicit alternative answer hypotheses; no network calls or production edits.')
parser.add_argument('--cards',type=Path,required=True,help='directory of raw card_*.json snapshots')
args=parser.parse_args()
root=Path(__file__).resolve().parents[3];picks={};reasons={}
def add(cid,words,why):
 picks.setdefault(cid,[])
 for word in words:
  if word not in picks[cid]:picks[cid].append(word)
 reasons.setdefault(cid,[]).append(why)
reviews=json.load(open(root/'dev/data/knowledge/ege_1_6_card_reviews.json'))['cards']
for review in reviews:
 if review.get('task')!=1:continue
 cid=review['id'];c=json.load(open(root/f'data/card_{cid}.json'));key=c['answer'].lower()
 families={'но':['однако','а','зато'], 'или':['либо'], 'так как':['потому что','поскольку','ибо'],
 'потом':['затем','позже','далее','после'], 'позже':['затем','потом','далее','после'],
 'затем':['потом','далее','после'], 'например':['скажем'],
 'всяким':['каждым','любым'], 'всякий':['каждый','любой'], 'же':['ведь'], 'хотя':['хоть'],
 'среди':['средь','посреди']}
 if key in families:add(cid,families[key],'Контекстная замена средства связи; гипотезы, не перечень нормативно тождественных слов. Проверить также ограничения части речи в условии.')
manual={
'012CAB':['лаковым','лакировальным'],
'0ED1F6':['величавые'],'832B01':['величавые'],'2FC7D6':['величавой'],
'7FF6B1':['величавой'],
'3AE61A':['заполнить'],'9F9A43':['годичный'],'55BC7E':['экономный'],'E17E48':['двоякую'],
'1D1FBE':['нового'], '2C4EBE':['большое','повышенное','особое','значительное'],
'5D58C2':['спровоцировать'],'62221D':['спровоцировал','породил'],
'74341C':['быстрый','бурный','резкий','стремительно'],
'84A09F':['исполнить'], 'A0983E':['особое','пристальное','значительное','повышенное'],
'C1F6AE':['перемены','изменения'],'D52745':['непрерывную','регулярную','систематическую','неоценимую','неоцененную'],
'DA7A61':['имеют'],'E98B8B':['проблематику','задачу'],'F3E10B':['имеющимися','выявленными','допущенными'],
'16D9F4':['рода'],'EFD46C':['династии'],'C3F6BC':['на всю жизнь'],
'926BD7':['высоких'],
}
# Discard candidates which fail elementary grammar before network checking.
manual['74341C'].remove('стремительно');manual['D52745'].remove('неоцененную')
for cid,words in manual.items():add(cid,words,'Альтернативное исправление конкретного предложения; словарная/контекстная гипотеза, приём ФИПИ не установлен.')
new=json.load(open(root/'dev/data/fipi_new_hypotheses.json'))['checks']
for c in new:
 if c['hypothesisBasis']!='lexical':continue
 cid=c['cardId'];words=[a['answer'] for a in c['candidates']]
 canonical=json.load(open(root/f'data/card_{cid}.json'))
 if re.search('антоним|синоним',canonical['question'],re.I):
  for a in list(words):
   if len(a.split())==2:words += [' '.join(reversed(a.split())),''.join(reversed(a.split()))]
 add(cid,words,'Все подготовленные лексические ответы и способы записи; для пар также обратный порядок. Общий текст — из прежней версии проекта.')
checks=[]
for cid,words in sorted(picks.items()):
 raw=json.load(open(args.cards/f'card_{cid}.json'));canonical=json.load(open(root/f'data/card_{cid}.json'))
 key=canonical.get('answer','').strip().lower();allwords=([key] if key else [])+words
 forms=[]
 for word in allwords:
  for form in [word,word.replace(' ',''),word.replace('ё','е'),word.replace('ё','е').replace(' ','')]:
   if form and form not in forms:forms.append(form)
 assert not (cid=='12BBAB' and 'позже' in forms)
 checks.append({'caseId':'VAR-'+cid,'cardId':cid,'guid':raw['guid'],'sourceSnapshot':raw,
 'sourceContentSha256':hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
 'mode':'verify_alternatives','candidates':[{'answer':a,'wireAnswer':a,'role':'current_key_hypothesis' if a==key else 'alternative_hypothesis'} for a in forms],
 'hypothesisBasis':'alternative_answers','rationale':reasons[cid],
 'contextSource':'data/card_'+cid+'.json','contextSha256':hashlib.sha256(canonical.get('text','').encode()).hexdigest()})
plan={'schemaVersion':1,'project':'AF0ED3F2557F8FFC4C06F80B6803FD26','checks':checks,
 'authorReportedResults':[{'cardId':'12BBAB','answer':'затем','status':'accepted','evidenceType':'author_message','date':'2026-10-29'},
 {'cardId':'12BBAB','answer':'позже','status':'rejected','evidenceType':'author_message','date':'2026-10-29'}]}
(root/'dev/data/fipi_answer_variants.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(len(checks),'cards',sum(len(c['candidates']) for c in checks),'requests')
