# Short launcher for PowerShell. Examples:
#   .\dbc.ps1
#   .\dbc.ps1 keys
#   .\dbc.ps1 apply
#   .\dbc.ps1 apply --yes
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsRest
)
uv run dbc @ArgsRest
