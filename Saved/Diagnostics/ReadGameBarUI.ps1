Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root=[Windows.Automation.AutomationElement]::RootElement
$windows=$root.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.Condition]::TrueCondition)
foreach($w in $windows) {
 if($w.Current.ProcessId -in @((Get-Process GameBar,GameBarFTServer -ErrorAction SilentlyContinue).Id)) {
  $w.Current | Select-Object Name,ClassName,ProcessId
  $nodes=$w.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
  foreach($n in $nodes){$n.Current | Select-Object Name,AutomationId,ControlType,IsEnabled}
 }
}
