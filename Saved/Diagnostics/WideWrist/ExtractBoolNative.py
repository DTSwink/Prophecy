from pathlib import Path
p=Path(__file__).parent
src=(p/'AnalyzeNative.py').read_text().replace("rsplit('WIDE_WRIST_START',1)","rsplit('WRIST_BOOL_START',1)")
src=src.replace("'NativeTrace.log'","'BoolNativeTrace.log'").replace("'native_parsed.json'","'bool_native_parsed.json'")
exec(compile(src,'ExtractBoolNative','exec'))
