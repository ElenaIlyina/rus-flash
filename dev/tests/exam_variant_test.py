"""Selection, grouping and exact scoring for generated variants."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ExamVariantTest(unittest.TestCase):
    def test_generation_scoring_and_revision_safety(self):
        script = r'''
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { generateVariant, gradeVariant, validateSession, maxPoints } from './html/js/exam.js';
import { theoryFor } from './html/js/exam-theory.js';
const catalog=JSON.parse(fs.readFileSync('html/assets/data/catalog.json'));
const byId=new Map(catalog.cards.map(c=>[c.id,c]));
for(let seed=0;seed<100;seed++) {
  const s=generateVariant(catalog,[],{seed,now:1,mode:'scored'});
  assert.equal(s.items.length,26);
  assert.equal(new Set(s.items.map(i=>i.id)).size,26);
  assert.ok(validateSession(s,catalog));
  for(const tasks of [[1,2,3],[23,24,25,26]]) {
    const ids=tasks.map(t=>byId.get(s.items[t-1].id).passageGroupId);
    assert.ok(ids[0]); assert.equal(new Set(ids).size,1);
  }
  assert.ok(s.items.every(i=>!byId.get(i.id).hasContentIssue && !byId.get(i.id).explanationNeedsSourceReview));
  if(s.essayId) assert.equal(byId.get(s.essayId).passageGroupId,byId.get(s.items[22].id).passageGroupId);
  assert.deepEqual(s,generateVariant(catalog,[],{seed,now:1,mode:'scored'}));
}
const s=generateVariant(catalog,[],{seed:123,now:1});
for(let task=1;task<=26;task++) { assert.ok(theoryFor(task)?.rule); assert.equal(theoryFor(task).steps.length,3); }
assert.equal(theoryFor(27),null);
const cards=s.items.map(item=>({id:item.id,answer:'12345',acceptedAnswers:['12345'],responseType:'matching'}));
assert.equal(gradeVariant(s,cards).reduce((n,r)=>n+r.points,0),0);
for(const item of s.items) s.answers[item.id]='12345';
assert.equal(gradeVariant(s,cards).reduce((n,r)=>n+r.points,0),28);
for(const task of [8,22]) {
 const id=s.items[task-1].id;
 s.answers[id]='12346';
 let result=gradeVariant(s,cards)[task-1];
 assert.equal(result.points,0); assert.equal(result.max,2);
 s.answers[id]='54321'; assert.equal(gradeVariant(s,cards)[task-1].points,0);
 s.answers[id]='12345'; assert.equal(gradeVariant(s,cards)[task-1].points,2);
}
const id=s.items[0].id;
cards[0].responseType='multiple_choice';s.answers[id]='54321';assert.ok(gradeVariant(s,cards)[0].correct);
s.answers[id]='123455';assert.ok(!gradeVariant(s,cards)[0].correct);
cards[0].acceptedAnswers=['однако','но'];s.answers[id]='НО';assert.ok(gradeVariant(s,cards)[0].correct);
s.theoryUsed.push(id);assert.ok(gradeVariant(s,cards)[0].assisted);
assert.throws(()=>gradeVariant(s,cards.slice(1)));
const changed=structuredClone(s);changed.items[0].version++;assert.ok(!validateSession(changed,catalog));
const duplicate=structuredClone(s);duplicate.items[1]=duplicate.items[0];assert.ok(!validateSession(duplicate,catalog));
assert.throws(()=>generateVariant({cards:[]},[],{seed:1}));
s.finishedAt=10;
const next=generateVariant(catalog,[s],{seed:123,now:11});
assert.ok(next.items.every((item,i)=>item.id!==s.items[i].id));
assert.equal(maxPoints(8),2);assert.equal(maxPoints(22),2);assert.equal(maxPoints(7),1);
'''
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
