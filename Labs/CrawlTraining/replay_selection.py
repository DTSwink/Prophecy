"""Crawl previews: one idle, then spread the remaining rows over crawl worlds."""
def select_replay_worlds(motions, idle_rows, equipment, rows, selection_round):
    rows=min(rows,len(motions))
    idle=list(range(min(idle_rows,len(motions))))
    crawl=list(range(len(idle),len(motions)))
    selected=[idle[selection_round%len(idle)]] if idle and rows else []
    count=min(rows-len(selected),len(crawl))
    selected += [crawl[(i*len(crawl)//count+selection_round)%len(crawl)] for i in range(count)]
    selected += [w for w in range(len(motions)) if w not in selected]
    return selected[:rows]

def patch(package):
    from pathlib import Path
    import shutil
    shutil.copy2(Path(__file__),package/'pipeline/crawl_replay_selection.py')
    p=package/'pipeline/observe_many.py';text=p.read_text()
    marker='class MultiRecorder(Recorder):'
    if 'from crawl_replay_selection import select_replay_worlds' not in text:
        text=text.replace(marker,'from crawl_replay_selection import select_replay_worlds\n\n\n'+marker)
        p.write_text(text)
    p=package/'pipeline/train.py';text=p.read_text()
    text=text.replace('if a.omni_run_lr:recorder.phase_agent=agent','if a.omni_run_lr or a.equipment_omni:recorder.phase_agent=agent')
    p.write_text(text)
