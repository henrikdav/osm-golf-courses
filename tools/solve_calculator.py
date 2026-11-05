"""Slope and course rating from a club's slope calculator (the Swedish Golf Federation's, embedded on the club's own page).

    python3 tools/solve_calculator.py DIR

DIR holds one file per handicap index the calculator was asked, hcp_<index>.json (hcp_0.json, hcp_53.2.json, …): the answer
the page showed, as the JSON list of { tee, playingHcpWomen?, playingHcpMen? } (a tee that isn't rated for a sex has no
such key). The calculator shows the playing handicap, round(index × slope / 113 + (course rating − par)), so for each tee
and sex this finds every whole slope and every course rating − par (steps of 0.1) that gives all the answers, and says
which indexes would tell the rest apart. Course rating = par + that, with the course's par. When one pair is left per
tee, write it into the club file with its source (how many indexes, the date, par assumed). We never call the
calculator's API ourselves: it answers only requests from the club's own domain."""
import json,math,sys,glob,os
def rnd(x): return math.floor(x+0.5)
d=sys.argv[1]; D={}
for f in sorted(glob.glob(os.path.join(d,'hcp_*.json'))):
    hi=float(os.path.basename(f)[4:-5].replace(',','.'))
    for r in json.load(open(f)):
        for sex,key in (('women','playingHcpWomen'),('men','playingHcpMen')):
            if key in r: D.setdefault((r['tee'],sex),{})[hi]=int(r[key])
sets={k:[(s,x/10) for s in range(55,156) for x in range(-150,151) if all(rnd(h*s/113+x/10)==v for h,v in o.items())] for k,o in D.items()}
for k,s in sorted(sets.items()):
    print(k,len(D[k]),'indexes ->',(sorted({a for a,_ in s})[:1] or ['NONE']),'..',(sorted({a for a,_ in s})[-1:] or ['']),'slope; CR-par',(min([b for _,b in s]),max([b for _,b in s])) if s else None,len(s),'left')
def cost(ch): 
    t=0
    for s in sets.values():
        g={}
        for sl,x in s: g.setdefault(tuple(rnd(h*sl/113+x) for h in ch),[]).append(1)
        t+=max(len(v) for v in g.values()) if g else 0
    return t
print('now',cost([]))
ch=[]
for _ in range(4):
    b=min([i/10 for i in range(541)],key=lambda h:cost(ch+[h])); ch.append(b); print('next:',ch,cost(ch))

