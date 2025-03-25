# 🛡️ Dein Cesium API Token
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI2N2MxMWRmMS04OTczLTQ4N2MtOTMxYS1kYjBjNWE0MGRiZGYiLCJpZCI6MTQ4NzI5LCJpYXQiOjE3NDI4Njc1MDZ9.D-YeHnZEwTfPMRhJIRwu4oL6pJod_nfy4H7g0EK01AY"

# 📦 Lade Assets
$response = Invoke-RestMethod -Uri "https://api.cesium.com/v1/assets" `
  -Headers @{ Authorization = "Bearer $token" }
$assets = $response.items

# 🎯 Filtere Assets mit dem Namen & Status
$targetAssets = $assets | Where-Object {
    $_.name -eq "099082.gml" -and $_.status -eq "AWAITING_FILES"
}

# 🔍 Zeige, was gefunden wurde
if ($targetAssets.Count -eq 0) {
    Write-Host "❌ Keine passenden Assets gefunden."
    exit
}

Write-Host "📄 Gefundene Assets:"
$targetAssets | ForEach-Object {
    Write-Host "🆔 ID: $($_.id) | Status: $($_.status)"
}

# ✅ Benutzerbestätigung einholen
$confirm = Read-Host "`n❗ Möchtest du diese Assets löschen? (ja/nein)"
if ($confirm -ne "ja") {
    Write-Host "🚫 Abbruch. Nichts wurde gelöscht."
    exit
}

# 🗑️ Löschen
foreach ($asset in $targetAssets) {
    Write-Host "🧨 Lösche Asset mit ID $($asset.id)..."
    Invoke-RestMethod -Method Delete -Uri "https://api.cesium.com/v1/assets/$($asset.id)" `
      -Headers @{ Authorization = "Bearer $token" }
    Write-Host "✅ Asset $($asset.id) gelöscht."
}
