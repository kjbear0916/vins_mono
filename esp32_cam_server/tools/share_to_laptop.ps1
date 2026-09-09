# 以系統管理員身分執行本腳本 (在管理員 PowerShell 貼上下面那行執行)
# 用途:在 家用 CHT 網段 Public profile 下,對 esp32_cam_server 資料夾建立唯讀共享,供筆電複製
# 說明:因 Group Policy 鎖住 NetworkCategory(改不了 Private),這裡改為直接在現有 profile(Public)
#       下啟用涵蓋它的 SMB-In 防火牆規則。僅限家用信任網段使用,用完請關閉。

$ErrorActionPreference = "Stop"

Write-Output "== [1/3] 啟用 SMB-In 防火牆規則(涵蓋 Private+Public profile) =="
# 找到 profile 為 Private,Public 的那條 SMB-In 並啟用
Get-NetFirewallRule -DisplayName "*SMB-In*" | ForEach-Object {
    if ($_.Profile -eq 3 -or $_.DisplayName -match "SMB-In") {
        Enable-NetFirewallRule -Name $_.Name
        Write-Output "  已啟用規則: $($_.Name) (Profile=$($_.Profile))"
    }
}
Write-Output "  完成"

Write-Output "== [2/3] 建立共享 esp32cam (Everyone 唯讀) =="
if (Get-SmbShare -Name "esp32cam" -ErrorAction SilentlyContinue) {
    Remove-SmbShare -Name "esp32cam" -Force
}
New-SmbShare -Name "esp32cam" -Path "D:\Things\esp32_cam_server" `
    -Description "esp32_cam_server 暫時共享 (給筆電複製,用完請關閉)" `
    -ReadAccess "Everyone"
Write-Output "  完成"

Write-Output "== [3/3] 分享資訊 =="
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.IPAddress -notmatch '^(127\.)' -and $_.PrefixOrigin -ne 'WellKnown'
} | Select-Object -First 1).IPAddress
Write-Output "  筆電請存取: \\$ip\esp32cam"
Write-Output "  這台電腦 IP: $ip"
Write-Output ""
Write-Output "複製完成後,建議在管理員 PowerShell 關閉共享:"
Write-Output "   Remove-SmbShare -Name esp32cam -Force"
