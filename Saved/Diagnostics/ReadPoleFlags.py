import unreal
for n in ('Prophecy.Recovery.PoleWindow','Prophecy.Recovery.PolePresentation','Prophecy.Tempering.PoleSmoothing','Prophecy.Tempering.SupportSource'):
 print(n,unreal.SystemLibrary.get_console_variable_int_value(n))
