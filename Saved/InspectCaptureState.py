import builtins


state = getattr(builtins, "_prophecy_physical_follower_tracking", None)
if not state:
    print("NO_CAPTURE_STATE")
else:
    print("frame={} rows={} handle={}".format(
        state.get("frame"), len(state.get("frames", [])), state.get("handle")))
