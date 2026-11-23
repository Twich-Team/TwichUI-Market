# Private VM only. Explicit selection; no discovery, credentials or background work.
param(
    [Parameter(Mandatory=$true)][ValidateSet(16,32)][int]$Layout,
    [Parameter(Mandatory=$true)][string]$PrivateGameRoot,
    [Parameter(Mandatory=$true)][string]$DevAppData
)
$ErrorActionPreference='Stop'
if ((Split-Path $DevAppData -Leaf) -ne 'team.twich.market.dev') { throw 'Only isolated DEV AppData is supported' }
foreach ($name in @('Wow','WowB','twichui-market-companion','twichui-market-companion-dev')) {
    if (Get-Process -Name $name -ErrorAction SilentlyContinue) { throw "Exit $name fully before changing the test layout" }
}
$game=(Resolve-Path -LiteralPath $PrivateGameRoot).Path
if ($game.StartsWith('\\')) { throw 'Private local game copy required' }
$current=Get-Item -LiteralPath $game
while ($null -ne $current) {
    if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'No linked or shared game paths' }
    $current=$current.Parent
}
$marker=Join-Path $game '.twichui-private-native-test'
if (-not(Test-Path -LiteralPath $marker) -or [IO.File]::ReadAllText($marker) -cne "PRIVATE VM ONLY`n") { throw 'Private VM marker required' }
$configuration=Get-Content -LiteralPath (Join-Path $DevAppData 'workshop-delivery-v1.json') -Raw | ConvertFrom-Json
if ($configuration.version -ne 2 -or -not $configuration.enabled -or (Resolve-Path -LiteralPath $configuration.installation).Path -ne $game) { throw 'Confirm this exact private game in DEV first' }
$capability=Join-Path $game 'Interface\AddOns\TwichUI_Workshop\MarketDelivery.json'
$current=Get-Item -LiteralPath $capability
while ($null -ne $current) {
    if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked capability refused' }
    $current=if ($current.PSIsContainer) { $current.Parent } else { $current.Directory }
}
$value=Get-Content -LiteralPath $capability -Raw | ConvertFrom-Json
if ($value.prepared_current_version -ne 1 -or $value.summary_current_contract -ne 3) { throw 'Pinned prepared reader required' }
$value.prepared_current_partitions=$Layout
[IO.File]::WriteAllText($capability, ($value | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
@{layout=$Layout;history_partitions=64;private_game=$game;network=$false} | ConvertTo-Json -Compress
