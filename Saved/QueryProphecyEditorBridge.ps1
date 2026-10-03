param(
    [string]$Endpoint = "/decal_report?bucket_cm=5&limit=25",
    [int]$Port = 8765,
    [switch]$Raw
)

if ($Endpoint.StartsWith("http://") -or $Endpoint.StartsWith("https://")) {
    $Uri = $Endpoint
} else {
    if (-not $Endpoint.StartsWith("/")) {
        $Endpoint = "/" + $Endpoint
    }
    $Uri = "http://127.0.0.1:$Port$Endpoint"
}

$Result = Invoke-RestMethod -UseBasicParsing -Uri $Uri -TimeoutSec 30

if ($Raw -or -not ($Endpoint -like "/decal_report*")) {
    $Result | ConvertTo-Json -Depth 32
    exit 0
}

"Decal components: $($Result.decal_component_count)"
"Visible decal components: $($Result.visible_decal_component_count)"
"Decal actors: $($Result.decal_actor_count)"
"Actor count: $($Result.actor_count)"
"Map: $($Result.map)"
""
"Warnings:"
foreach ($Warning in $Result.warnings) {
    "- $Warning"
}
""
"Top decal clusters:"
foreach ($Cluster in $Result.top_location_clusters | Select-Object -First 10) {
    $Center = ($Cluster.center_cm | ForEach-Object { "{0:N1}" -f $_ }) -join ", "
    $Size = if ($Cluster.avg_decal_size_cm) { ($Cluster.avg_decal_size_cm | ForEach-Object { "{0:N1}" -f $_ }) -join ", " } else { "unknown" }
    "- count=$($Cluster.count), visible=$($Cluster.visible_count), center=[$Center], avg_size=[$Size]"
}

