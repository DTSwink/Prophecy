from pathlib import Path
p=Path('Saved/Diagnostics/ArmedSpineHitch/capture.py');s=p.read_text(encoding='utf-8');s=s.replace("tag='armed_spine_before'","tag='armed_spine_after'");Path('Saved/Diagnostics/ArmedSpineHitch/capture_after.py').write_text(s,encoding='utf-8')
p=Path('Docs/UpperBodyArmedPose.md');s=p.read_text(encoding='utf-8');s+='''

October 2 entry-history correction (validation pending): a current TestNN capture
shows the first Armed-pose application at tick 140 replacing the previous
interpolation endpoint with the sampled displayed local pose. At zero entry weight
this changed spine_05 by 7.026882 degrees and head by 4.702679 degrees / 2.576814 cm;
pelvis history was unchanged. The entry now seeds its cached previous locals from
the incoming previous policy endpoint; the sampled visible pose still starts the
manual rotation track. Subsequent updates continue using the last accepted composite.
Existing .1 blend, 350-degree speed, .1 core influence and Blueprint wiring are preserved.
No added smoothing, duration or inference. Evidence: Saved/Diagnostics/ArmedSpineHitch
and Saved/Diagnostics/Knee202/armed_spine_before.json. Build/replay checks pending.
''';p.write_text(s,encoding='utf-8')
