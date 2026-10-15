"""Run the active native configuration, then record it for the comparison map."""
import os
from pathlib import Path
os.environ['MIMICKIT_TRANSFER_OUT']=str(Path(__file__).resolve().parents[2]/'Saved/MimicKitTransfer/no-armature-3913')
import native_probe,record_failure_map
native_probe.main()
record_failure_map.main()
