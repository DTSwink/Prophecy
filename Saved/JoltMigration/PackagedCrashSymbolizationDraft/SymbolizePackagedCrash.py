"""Offline PDB resolution of recorded addresses. Never attaches to another process."""
import ctypes as C, ctypes.wintypes as W, pathlib, json, re, struct, hashlib, xml.etree.ElementTree as ET
root=pathlib.Path(__file__).resolve().parents[3]
exe=root/'Saved/JoltMigration/NNCrowd-20260909-144331-647/Project/Binaries/Win64/GameAnimationSample3.exe'
pdb=exe.with_suffix('.pdb')
crash=pathlib.Path('C:/Users/singerie/.codex/tmp/ProphecyJolt/NNPkg-Development-20260909-182138-994/Stage/Windows/GameAnimationSample3/Saved/Crashes/UECC-Windows-A3E8C76B494CE06605B3F1AB08E1600E_0000')
staged=crash.parents[2]/'Binaries/Win64/GameAnimationSample3.exe'
expected='6d6e1f3657e17fc85fd15aa869fd41776eb739af98ad413e7d30668907314559'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
source_sha=sha(exe); stage_sha=sha(staged)
assert source_sha==stage_sha==expected, (source_sha,stage_sha)
xml=ET.parse(crash/'CrashContext.runtime-xml'); stack=xml.findtext('RuntimeProperties/PCallStack')
records=[(m.group(1),int(m.group(2),16),int(m.group(3),16)) for m in re.finditer(r'(\S+)\s+(0x[0-9a-fA-F]+)\s*\+\s*([0-9a-fA-F]+)',stack)]
base=next(v[1] for v in records if v[0]=='GameAnimationSample3')
with exe.open('rb') as f:
 f.seek(0x3c); pe=struct.unpack('<I',f.read(4))[0]; f.seek(pe+4+20+56); image_size=struct.unpack('<I',f.read(4))[0]
D=C.c_uint32; U=C.c_uint64; P=C.c_void_p; B=C.c_int32
class Symbol(C.Structure):
 _fields_=[('SizeOfStruct',D),('TypeIndex',D),('Reserved',U*2),('Index',D),('Size',D),('ModBase',U),('Flags',D),('Value',U),('Address',U),('Register',D),('Scope',D),('Tag',D),('NameLen',D),('MaxNameLen',D),('Name',C.c_char*1)]
class Line(C.Structure):
 _fields_=[('SizeOfStruct',D),('Key',P),('LineNumber',D),('FileName',C.c_char_p),('Address',U)]
class GUID(C.Structure):
 _fields_=[('a',D),('b',C.c_uint16),('c',C.c_uint16),('d',C.c_ubyte*8)]
class Module(C.Structure):
 _fields_=[('SizeOfStruct',D),('BaseOfImage',U),('ImageSize',D),('TimeDateStamp',D),('CheckSum',D),('NumSyms',D),('SymType',C.c_int32),('ModuleName',C.c_char*32),('ImageName',C.c_char*256),('LoadedImageName',C.c_char*256),('LoadedPdbName',C.c_char*256),('CVSig',D),('CVData',C.c_char*780),('PdbSig',D),('PdbSig70',GUID),('PdbAge',D),('PdbUnmatched',B),('DbgUnmatched',B),('LineNumbers',B),('GlobalSymbols',B),('TypeInfo',B),('SourceIndexed',B),('Publics',B),('MachineType',D),('Reserved',D)]
dbg=C.WinDLL('C:/Windows/System32/dbghelp.dll',use_last_error=True)
kernel=C.WinDLL('kernel32',use_last_error=True); kernel.GetCurrentProcess.restype=P
handle=kernel.GetCurrentProcess()
def bind(name,result,args):
 f=getattr(dbg,name);f.restype=result;f.argtypes=args;return f
init=bind('SymInitializeW',B,[P,C.c_wchar_p,B]); cleanup=bind('SymCleanup',B,[P]); options=bind('SymSetOptions',D,[D]); load=bind('SymLoadModuleExW',U,[P,P,C.c_wchar_p,C.c_wchar_p,U,D,P,D]); symbol=bind('SymFromAddr',B,[P,U,C.POINTER(U),C.POINTER(Symbol)]); line=bind('SymGetLineFromAddr64',B,[P,U,C.POINTER(D),C.POINTER(Line)]); module=bind('SymGetModuleInfo64',B,[P,U,C.POINTER(Module)])
opts=0x2|0x10|0x200|0x400|0x1000|0x40000|0x80000|0x02000000
options(opts)
assert init(handle,str(exe.parent),False), C.get_last_error()
try:
 loaded=load(handle,None,str(exe),'GameAnimationSample3',base,image_size,None,0)
 assert loaded==base, (hex(loaded),C.get_last_error())
 resolved=[]
 for name,modbase,rva in records:
  if name!='GameAnimationSample3':
   resolved.append({'module':name,'rva':hex(rva),'not_resolved':'Only exact game image/PDB loaded; no network/system symbol lookup.'}); continue
  address=modbase+rva; buf=C.create_string_buffer(C.sizeof(Symbol)+4096); si=C.cast(buf,C.POINTER(Symbol)); si.contents.SizeOfStruct=C.sizeof(Symbol); si.contents.MaxNameLen=4096; displacement=U()
  ok=bool(symbol(handle,address,C.byref(displacement),si)); err=C.get_last_error() if not ok else 0
  record={'module':name,'rva':hex(rva),'address':hex(address),'resolved':ok,'error':err}
  if ok: record.update(symbol=C.string_at(C.addressof(buf)+Symbol.Name.offset,si.contents.NameLen).decode('utf-8','replace'),symbol_displacement=displacement.value,symbol_address=hex(si.contents.Address),symbol_size=si.contents.Size)
  li=Line();li.SizeOfStruct=C.sizeof(Line);ld=D(); lok=bool(line(handle,address,C.byref(ld),C.byref(li)))
  record['line_resolved']=lok
  if lok: record.update(file=li.FileName.decode('utf-8','replace'),line=li.LineNumber,line_displacement=ld.value)
  else: record['line_error']=C.get_last_error()
  resolved.append(record)
  print(json.dumps(record),flush=True)
 mi=Module();mi.SizeOfStruct=C.sizeof(Module); mok=bool(module(handle,base,C.byref(mi)))
 module_info={'queried':mok,'error':0 if mok else C.get_last_error()}
 if mok:
  module_info.update(loaded_pdb=bytes(mi.LoadedPdbName).decode('utf-8','replace'),pdb_age=mi.PdbAge,pdb_unmatched=bool(mi.PdbUnmatched),dbg_unmatched=bool(mi.DbgUnmatched),sym_type=mi.SymType,line_numbers=bool(mi.LineNumbers),global_symbols=bool(mi.GlobalSymbols),type_info=bool(mi.TypeInfo),pdb_guid_raw=bytes(mi.PdbSig70).hex(),image_size=mi.ImageSize)
 result={'scope':'Offline address/PDB lookup in the Python process; invadeProcess=false; no attachment, minidump execution or network symbol search. Game image hash exact; no guessed symbol names.','source_exe':str(exe),'source_exe_sha256':source_sha,'staged_exe':str(staged),'staged_exe_sha256':stage_sha,'pdb':str(pdb),'pdb_sha256':sha(pdb),'crash_xml':str(crash/'CrashContext.runtime-xml'),'crash_xml_sha256':sha(crash/'CrashContext.runtime-xml'),'module_base':hex(base),'image_size':image_size,'dbghelp_options':hex(opts),'module_info':module_info,'stack':resolved}
 destination=pathlib.Path(__file__).with_name('SymbolizedStack.json'); destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print('SAVED',destination,flush=True);print(json.dumps(module_info),flush=True)
finally: cleanup(handle)
