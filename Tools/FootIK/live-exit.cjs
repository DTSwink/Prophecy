'use strict';
// Event eligibility only. The host arms this after a genuinely influenced
// terrain episode and commits the actual corrected30Hz history once.
const Terrain=require('./live-terrain.cjs');
const S=require('../../Labs/FootIKLab/support.js');
const R=require('../../Labs/FootIKLab/recovery.js');
const DEFAULT_NAMES=['root','pelvis','spine_01','spine_02','spine_03','spine_04','spine_05','clavicle_l','upperarm_l','lowerarm_l','hand_l','clavicle_r','upperarm_r','lowerarm_r','hand_r','neck_01','neck_02','head','thigh_l','calf_l','foot_l','ball_l','thigh_r','calf_r','foot_r','ball_r'];
const margin=.005,epsilon=1e-9,horizon=8/30;
const vector=p=>Array.isArray(p)&&p.length===3&&p.every(Number.isFinite);
const no=reason=>({eligible:false,reason});
const prepared=new WeakMap();
function interval(tile,a,b){
 const p=tile.local(a),q=tile.local(b);let lo=0,hi=1;
 for(const [axis,min,max] of [[0,tile.bounds[0],tile.bounds[1]],[2,tile.bounds[2],tile.bounds[3]]]){
  const delta=q[axis]-p[axis];
  if(Math.abs(delta)<1e-14){if(p[axis]<min-epsilon||p[axis]>max+epsilon)return null;continue;}
  const x=(min-p[axis])/delta,y=(max-p[axis])/delta;lo=Math.max(lo,Math.min(x,y));hi=Math.min(hi,Math.max(x,y));
  if(lo>hi+epsilon)return null;
 }
 return [lo,hi];
}
function covered(tiles,a,b){
 const spans=tiles.map(t=>interval(t,a,b)).filter(Boolean).sort((a,b)=>a[0]-b[0]);let end=0;
 for(const span of spans){if(span[0]>end+epsilon)return false;end=Math.max(end,span[1]);if(end>=1-epsilon)return true;}
 return false;
}
function evaluate({frame,terrain,currentTick,names=DEFAULT_NAMES}={}){
 if(!frame?.pose||!Array.isArray(frame.feet)||frame.feet.length!==2||!Number.isInteger(currentTick)||currentTick<0)return no('invalid_frame');
 if(frame.slide||frame.feet.some(f=>f?.state==='SLIDE'))return no('surface_mode');
 if(frame.feet.some(f=>!f||f.contact))return no('material_contact');
 const source=frame.pose;
 if(!Array.isArray(names)||names.length!==26||!Array.isArray(source.points)||source.points.length!==26||!source.points.every(vector))return no('invalid_pose');
 if(!source.axes&&(!Array.isArray(source.q)||source.q.length!==26||source.q.some(q=>!Array.isArray(q)||q.length!==4||!q.every(Number.isFinite))))return no('invalid_pose');
 const axes=source.axes||source.q.map(R.toAxes);
 if(!Array.isArray(axes)||axes.length!==26||axes.some(a=>!Array.isArray(a)||a.length!==3||!a.every(vector)))return no('invalid_pose');
 const pose={...source,axes},root=frame.root||pose.points[0];if(!vector(root))return no('invalid_root');
 if(!terrain||!Array.isArray(terrain.tiles)||!terrain.tiles.length)return no('no_ground');
 let query;
 try{query=prepared.get(terrain);if(!query){query=Terrain.create(terrain);prepared.set(terrain,query);}}
 catch{return no('nonhorizontal_terrain');}
 const rows=terrain.rootRows,startTick=terrain.rootStartTick??0;
 if(!Number.isInteger(startTick)||!Array.isArray(rows)||rows.length<2)return no('missing_navigation');
 let navigation;try{navigation=Terrain.rootSampler(rows);}catch{return no('invalid_navigation');}
 const time=(currentTick-startTick)/120,end=time+horizon;
 if(time<rows[0].time-epsilon||end>rows.at(-1).time+epsilon)return no('short_navigation');
 const current=navigation.at(time),level=current[1];
 if(R.length(R.sub(current,root))>margin)return no('navigation_mismatch');
 const levelTiles=query.tiles.filter(t=>Math.abs(t.y-level)<=margin);
 if(!covered(levelTiles,root,root))return no('no_level_support');
 const future=[current,...rows.filter(r=>r.time>time+epsilon&&r.time<end-epsilon).map(r=>r.position),navigation.at(end)];
 if(future.some(p=>Math.abs(p[1]-level)>margin))return no('changing_incline');
 const higher=query.tiles.filter(t=>t.y>level+margin);
 for(let i=1;i<future.length;i++){
  if(!covered(levelTiles,future[i-1],future[i]))return no('future_support_gap');
  if(higher.some(t=>{const span=interval(t,future[i-1],future[i]);return span&&span[1]-span[0]>epsilon;}))return no('raised_ahead');
 }
 let minimumSoleGap=Infinity;
 for(const side of ['L','R']){
  const foot=names.indexOf('foot_'+side.toLowerCase()),toe=names.indexOf('ball_'+side.toLowerCase());
  if(foot<0||toe<0)return no('missing_foot');
  const ankle=pose.points[foot],offsets=S.footPoints(pose,foot,toe,side);
  const gap=Math.min(...offsets.map(o=>ankle[1]+o[1]-level));minimumSoleGap=Math.min(minimumSoleGap,gap);
  if(gap<margin)return {...no('shoe_not_clear'),landingHeight:level,minimumSoleGap};
  for(const tile of higher){
   const local=tile.local(ankle);
   // Canonical full box-face clipping, including a tread entering a shoe face.
   // -Infinity is only the no-overlap return sentinel; this query's arithmetic
   // uses local X/Z and shoe offsets, never the supplied ankle Y.
   local[1]=-Infinity;
   const required=tile.query.floorFor(local,tile.shape(offsets));
   if(Number.isFinite(required)&&ankle[1]<tile.y+required+margin)return no('raised_under_shoe');
  }
 }
 return {eligible:true,reason:'clear_level_landing',landingHeight:level,minimumSoleGap,futureThroughTick:currentTick+horizon*120};
}
module.exports={evaluate};
