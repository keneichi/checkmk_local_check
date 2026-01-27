# Checkmk local check: Windows Updates (Security vs Other) + Reboot required
# Place in: C:\ProgramData\checkmk\agent\local\
# Output format: <state> <service_name> <perfdata> <text>

# ----------------------------
# Thresholds (tweak as you like)
# ----------------------------
$WarnSecurity = 1      # WARN if >= this many security/critical updates pending
$CritSecurity = 5      # CRIT if >= this many security/critical updates pending
$WarnOther    = 5      # WARN if >= this many other updates pending
$CritOther    = 20     # CRIT if >= this many other updates pending

# If $true: reboot required => CRIT, else WARN
$RebootIsCrit = $true

function Write-CheckmkLine($state, $svc, $text, $perf = "-") {
    # Keep it simple: perfdata "-" by default
    Write-Output ("{0} {1} {2} {3}" -f $state, $svc, $perf, $text)
}

function Get-PendingReboot {
    $reasons = New-Object System.Collections.Generic.List[string]

    # Windows Update reboot required
    $wuKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
    if (Test-Path $wuKey) { $reasons.Add("WindowsUpdate") | Out-Null }

    # Component Based Servicing reboot pending
    $cbsKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending"
    if (Test-Path $cbsKey) { $reasons.Add("CBS") | Out-Null }

    # Pending file rename operations
    $sessKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager"
    try {
        $p = (Get-ItemProperty -Path $sessKey -Name "PendingFileRenameOperations" -ErrorAction Stop).PendingFileRenameOperations
        if ($null -ne $p -and $p.Count -gt 0) { $reasons.Add("PendingFileRenameOps") | Out-Null }
    } catch { }

    # Pending computer rename or domain join
    try {
        $nameKey = "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName"
        $active = (Get-ItemProperty $nameKey -Name "ComputerName" -ErrorAction Stop).ComputerName
        $pendingKey = "HKLM:\SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName"
        $pending = (Get-ItemProperty $pendingKey -Name "ComputerName" -ErrorAction Stop).ComputerName
        if ($active -ne $pending) { $reasons.Add("ComputerRename") | Out-Null }
    } catch { }

    # More signals used sometimes
    $netlogonKey = "HKLM:\SYSTEM\CurrentControlSet\Services\Netlogon"
    try {
        $join = (Get-ItemProperty $netlogonKey -Name "JoinDomain" -ErrorAction Stop)."JoinDomain"
        if ($join) { $reasons.Add("DomainJoin") | Out-Null }
    } catch { }

    return @{
        Pending = ($reasons.Count -gt 0)
        Reasons = $reasons
    }
}

function Get-WindowsUpdateCounts {
    # Uses Windows Update Agent COM API (no extra module needed)
    $security = 0
    $other = 0
    $titlesSecurity = New-Object System.Collections.Generic.List[string]
    $titlesOther = New-Object System.Collections.Generic.List[string]

    try {
        $session  = New-Object -ComObject "Microsoft.Update.Session"
        $searcher = $session.CreateUpdateSearcher()

        # Not installed software updates
        $result = $searcher.Search("IsInstalled=0 and Type='Software'")

        for ($i=0; $i -lt $result.Updates.Count; $i++) {
            $upd = $result.Updates.Item($i)

            # Determine "security/critical" by categories
            $isSec = $false
            for ($c=0; $c -lt $upd.Categories.Count; $c++) {
                $cat = $upd.Categories.Item($c).Name
                if ($cat -match "Security Updates" -or $cat -match "Critical Updates") {
                    $isSec = $true
                    break
                }
            }

            if ($isSec) {
                $security++
                if ($titlesSecurity.Count -lt 5) { $titlesSecurity.Add($upd.Title) | Out-Null }
            } else {
                $other++
                if ($titlesOther.Count -lt 5) { $titlesOther.Add($upd.Title) | Out-Null }
            }
        }

        return @{
            Ok = $true
            Security = $security
            Other = $other
            TitlesSecurity = $titlesSecurity
            TitlesOther = $titlesOther
        }
    }
    catch {
        return @{
            Ok = $false
            Error = $_.Exception.Message
        }
    }
}

# ----------------------------
# Main
# ----------------------------
$svcSec   = "Windows_Updates_Security"
$svcOther = "Windows_Updates_Other"
$svcReb   = "Reboot_required"

$wu = Get-WindowsUpdateCounts
if (-not $wu.Ok) {
    Write-CheckmkLine 3 $svcSec   ("CRIT: cannot query Windows Update API: " + $wu.Error)
    Write-CheckmkLine 3 $svcOther ("CRIT: cannot query Windows Update API: " + $wu.Error)
} else {
    # Security status
    $stateSec = 0
    if ($wu.Security -ge $CritSecurity) { $stateSec = 2 }
    elseif ($wu.Security -ge $WarnSecurity) { $stateSec = 1 }

    $secMsg = "pending=$($wu.Security)"
    if ($wu.Security -gt 0 -and $wu.TitlesSecurity.Count -gt 0) {
        $secMsg += " ; examples: " + ($wu.TitlesSecurity -join " | ")
    }
    Write-CheckmkLine $stateSec $svcSec $secMsg ("sec_pending=" + $wu.Security + ";" + $WarnSecurity + ";" + $CritSecurity + ";0")

    # Other status
    $stateOther = 0
    if ($wu.Other -ge $CritOther) { $stateOther = 2 }
    elseif ($wu.Other -ge $WarnOther) { $stateOther = 1 }

    $otherMsg = "pending=$($wu.Other)"
    if ($wu.Other -gt 0 -and $wu.TitlesOther.Count -gt 0) {
        $otherMsg += " ; examples: " + ($wu.TitlesOther -join " | ")
    }
    Write-CheckmkLine $stateOther $svcOther $otherMsg ("other_pending=" + $wu.Other + ";" + $WarnOther + ";" + $CritOther + ";0")
}

# Reboot required
$reb = Get-PendingReboot
if ($reb.Pending) {
    $st = if ($RebootIsCrit) { 2 } else { 1 }
    $why = if ($reb.Reasons.Count -gt 0) { ($reb.Reasons -join ",") } else { "unknown" }
    Write-CheckmkLine $st $svcReb ("YES (" + $why + ")")
} else {
    Write-CheckmkLine 0 $svcReb "NO"
}
