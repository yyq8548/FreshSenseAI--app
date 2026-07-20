param(
  [Parameter(Mandatory=$true)][string]$TextPath,
  [Parameter(Mandatory=$true)][string]$OutputPath,
  [string]$VoiceName = 'Microsoft Zira Desktop'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
  $installed = $speaker.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }
  if ($installed -notcontains $VoiceName) { throw "Required voice is not installed: $VoiceName" }
  $speaker.SelectVoice($VoiceName)
  $speaker.Rate = 0
  $speaker.Volume = 100
  $speaker.SetOutputToWaveFile($OutputPath)
  $speaker.Speak((Get-Content -LiteralPath $TextPath -Raw))
} finally {
  $speaker.Dispose()
}
