#requires -Version 5.1

$ServiceName = "DNS_Resolver_Conformity"
$ConfFile = "C:\ProgramData\checkmk\agent\config\resolver_dns.conf"

function Out-Checkmk($state, $msg) {
    Write-Output "$state $ServiceName - $msg"
    exit 0
}

function Parse-Conf($path) {
    if (!(Test-Path $path)) {
        Out-Checkmk 2 "Unable to read config file: $path (not found)"
    }

    $conf = @{
        allowed_dns        = @()
        allow_localhost    = $false
        ignore_iface_regex = ""
    }

    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        if ($line -notmatch "=") { return }

        $k, $v = $line.Split("=", 2)
        $k = $k.Trim()
        $v = $v.Trim()

        switch ($k) {
            "allowed_dns" {
                $conf.allowed_dns = $v.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
            }
            "allow_localhost" {
                $conf.allow_localhost = ($v.ToLower() -eq "true")
            }
            "ignore_iface_regex" {
                $conf.ignore_iface_regex = $v
            }
        }
    }

    if ($conf.allowed_dns.Count -eq 0) {
        Out-Checkmk 2 "Config error: allowed_dns is empty"
    }

    return $conf
}

function Is-Localhost($ip) {
    return @("127.0.0.1", "::1") -contains $ip
}

function LocalDnsRunning() {
    try {
        $tcp = Get-NetTCPConnection -LocalPort 53 -State Listen -ErrorAction SilentlyContinue
        if ($tcp) { return $true }
    } catch {}

    try {
        $udp = Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue
        if ($udp) { return $true }
    } catch {}

    try {
        $svc = Get-Service -Name "DNS" -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -eq "Running") { return $true }
    } catch {}

    return $false
}

$conf = Parse-Conf $ConfFile
$allowed = $conf.allowed_dns

# Interfaces UP
$ifaces = Get-NetAdapter -ErrorAction SilentlyContinue |
    Where-Object { $_.Status -eq "Up" -and $_.Name -notmatch "Loopback" }

$ignoredCount = 0
if ($conf.ignore_iface_regex) {
    $rx = [regex]::new($conf.ignore_iface_regex, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
    $before = $ifaces.Count
    $ifaces = $ifaces | Where-Object {
        -not ($rx.IsMatch($_.Name) -or $rx.IsMatch($_.InterfaceDescription))
    }
    $ignoredCount = $before - $ifaces.Count
}

$issuesWarn = @()
$issuesCrit = @()

foreach ($iface in $ifaces) {
    try {
        $dns = (Get-DnsClientServerAddress `
            -InterfaceIndex $iface.ifIndex `
            -AddressFamily IPv4 `
            -ErrorAction SilentlyContinue).ServerAddresses
    } catch {
        continue
    }

    if (-not $dns -or $dns.Count -eq 0) { continue }

    $primary = $dns[0]

    # Localhost handling
    if (Is-Localhost $primary) {
        if (-not $conf.allow_localhost) {
            $issuesCrit += "$($iface.Name): localhost DNS not allowed ($primary)"
            continue
        }
        if (-not (LocalDnsRunning)) {
            $issuesCrit += "$($iface.Name): localhost DNS configured but no local DNS service running"
            continue
        }
    }

    # Authorized resolver present?
    $authorizedPresent = $false
    foreach ($s in $dns) {
        if ($allowed -contains $s) {
            $authorizedPresent = $true
            break
        }
    }

    if (-not $authorizedPresent -and -not (Is-Localhost $primary)) {
        $issuesCrit += "$($iface.Name): no authorized DNS found (configured=$($dns -join ','))"
        continue
    }

    # Primary resolver must be authorized (unless localhost)
    if (-not (Is-Localhost $primary) -and -not ($allowed -contains $primary)) {
        $issuesCrit += "$($iface.Name): primary DNS not authorized ($primary)"
        continue
    }

    # Extra non-authorized resolvers
    $extra = $dns | Where-Object {
        -not ($allowed -contains $_) -and -not (Is-Localhost $_)
    }

    if ($extra.Count -gt 0) {
        $issuesWarn += "$($iface.Name): unauthorized DNS present ($($extra -join ','))"
    }
}

if ($issuesCrit.Count -gt 0) {
    Out-Checkmk 2 ("CRITICAL - " + ($issuesCrit -join " | "))
}

if ($issuesWarn.Count -gt 0) {
    Out-Checkmk 1 ("WARNING - " + ($issuesWarn -join " | ") +
        " | Authorized: $($allowed -join ',') | Ignored_ifaces=$ignoredCount")
}

Out-Checkmk 0 ("OK - DNS resolvers compliant | Authorized: $($allowed -join ',') | Ignored_ifaces=$ignoredCount")
