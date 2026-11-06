# Private local input only: never print, log, or save the key to a file.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$speechForm = New-Object System.Windows.Forms.Form
$speechForm.Text = 'Prophecy - ElevenLabs connection'
$speechForm.ClientSize = New-Object System.Drawing.Size(590,325)
$speechForm.StartPosition = 'CenterScreen'
$speechForm.FormBorderStyle = 'FixedDialog'
$speechForm.MaximizeBox = $false
$speechForm.Font = New-Object System.Drawing.Font('Segoe UI',10)
$speechHelp = New-Object System.Windows.Forms.Label
$speechHelp.Location = New-Object System.Drawing.Point(20,18)
$speechHelp.Size = New-Object System.Drawing.Size(550,125)
$speechHelp.Text = "1. In ElevenLabs, open Developers > API Keys > Create key.`r`n2. Name it Prophecy speech. Enable Text to Speech, Voices read,`r`n   Models read and User read. Keep other permissions off.`r`n3. Copy the key and paste it below. Do not send it in chat."
$speechForm.Controls.Add($speechHelp)
$speechOpen = New-Object System.Windows.Forms.Button
$speechOpen.Text = 'Open ElevenLabs'
$speechOpen.Location = New-Object System.Drawing.Point(20,143)
$speechOpen.Size = New-Object System.Drawing.Size(170,32)
$speechOpen.Add_Click({ Start-Process 'https://elevenlabs.io/app' })
$speechForm.Controls.Add($speechOpen)
$speechKeyBox = New-Object System.Windows.Forms.TextBox
$speechKeyBox.Location = New-Object System.Drawing.Point(20,190)
$speechKeyBox.Size = New-Object System.Drawing.Size(550,30)
$speechKeyBox.UseSystemPasswordChar = $true
$speechForm.Controls.Add($speechKeyBox)
$speechStatus = New-Object System.Windows.Forms.Label
$speechStatus.Location = New-Object System.Drawing.Point(20,233)
$speechStatus.Size = New-Object System.Drawing.Size(550,28)
$speechStatus.Text = 'Saved only to your Windows user environment. No audio generated.'
$speechForm.Controls.Add($speechStatus)
$speechSave = New-Object System.Windows.Forms.Button
$speechSave.Text = 'Save connection'
$speechSave.Location = New-Object System.Drawing.Point(390,277)
$speechSave.Size = New-Object System.Drawing.Size(180,32)
$speechSave.Add_Click({
    if ([string]::IsNullOrWhiteSpace($speechKeyBox.Text)) { $speechStatus.Text = 'Paste your API key first.'; return }
    try {
        [Environment]::SetEnvironmentVariable('ELEVENLABS_API_KEY',$speechKeyBox.Text.Trim(),'User')
        $speechKeyBox.Clear()
        $speechStatus.Text = 'Saved. Close this window and tell Codex the connection is ready.'
        $speechSave.Enabled = $false
    } catch { $speechStatus.Text = 'Could not save the connection. Your key has not been displayed.' }
})
$speechForm.Controls.Add($speechSave)
$speechForm.AcceptButton = $speechSave
[void]$speechForm.ShowDialog()
$speechKeyBox.Clear()
$speechForm.Dispose()
