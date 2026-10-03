import pathlib,json,sys,statistics
p=pathlib.Path(__file__).parent;out={};baseline=None
for tag in sys.argv[1:]:
 d=json.loads((p/('AttackStartup-'+tag+'.json')).read_text());rows=d['rows'];intervals=[1000*(b['wall']-a['wall'])for a,b in zip(rows,rows[1:])]
 first=next((i for i,r in enumerate(rows)if any(a['attack']!='None'for a in r['states'])),None)
 events=[]
 for i in range(1,len(rows)):
  if any(a['attack']!='None'for a in rows[i]['states'])and not any(a['attack']!='None'for a in rows[i-1]['states']):
   events.append({'tick':rows[i]['states'][0]['tick'],'max_near_start_ms':max(intervals[max(0,i-3):i+2])})
 states=[[a['attack']for a in r['states']]for r in rows]
 if baseline is None:baseline=states
 result={'reason':d['reason'],'frames':len(rows),'first_sample_wall_ms':1000*rows[0]['wall'],'median_frame_ms':statistics.median(intervals),
  'maximum_frame_ms':max(intervals),'starts':events,'state_sequence_matches_baseline':states==baseline}
 out[tag]=result;print(tag,json.dumps(result))
(p/'AttackStartup-comparison.json').write_text(json.dumps(out,indent=2))
