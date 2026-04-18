param(
  [Parameter(Mandatory = $true)]
  [string]$TargetDoc,

  [Parameter(Mandatory = $true)]
  [string]$MinuteUrl,

  [string]$OutputDir = "",

  [ValidateSet("low", "medium", "high")]
  [string]$MinConfidence = "high",

  [int]$ApplyLimit = 5,

  [int]$ApplyDelaySeconds = 8,

  [switch]$Apply,

  [switch]$AllowFullComments
)

$env:LARK_CLI_NO_PROXY = '1'
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue

$args = @(
  ".\skills\lark-meeting-doc-sync\scripts\sync_lark_comments.py",
  "--target-doc", $TargetDoc,
  "--minute-url", $MinuteUrl,
  "--meeting-artifact", "auto",
  "--min-confidence", $MinConfidence,
  "--apply-limit", "$ApplyLimit",
  "--apply-delay-seconds", "$ApplyDelaySeconds"
)

if ($OutputDir) {
  $args += @("--output-dir", $OutputDir)
}
if ($Apply) {
  $args += "--apply"
}
if ($AllowFullComments) {
  $args += "--allow-full-comments"
}

python @args
