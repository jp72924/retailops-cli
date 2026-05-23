param(
    [string]$Repo = "https://github.com/jp72924/retailops-cli.git",
    [string]$Ref = "",
    [switch]$NoCompletion
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    $candidates = @(
        @("py", "-3"),
        @("python")
    )

    foreach ($candidate in $candidates) {
        $cmd = $candidate[0]
        $args = @()
        if ($candidate.Count -gt 1) {
            $args = $candidate[1..($candidate.Count - 1)]
        }

        try {
            $version = & $cmd @args -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            if ($LASTEXITCODE -eq 0) {
                $parts = $version.Trim().Split(".")
                if ([int]$parts[0] -gt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -ge 11)) {
                    return @{ Command = $cmd; Args = $args }
                }
            }
        } catch {
            continue
        }
    }

    throw "RetailOps CLI requires Python 3.11 or newer. Install Python 3.11+ and rerun this installer."
}

function Invoke-Python {
    param(
        [hashtable]$Python,
        [string[]]$Arguments
    )

    & $Python.Command @($Python.Args + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($Arguments -join ' ')"
    }
}

$python = Resolve-Python

try {
    Invoke-Python -Python $python -Arguments @("-m", "pipx", "--version")
} catch {
    Write-Host "Installing pipx..."
    Invoke-Python -Python $python -Arguments @("-m", "pip", "install", "--user", "pipx")
}

Invoke-Python -Python $python -Arguments @("-m", "pipx", "ensurepath")

$spec = "git+$Repo"
if (-not [string]::IsNullOrWhiteSpace($Ref)) {
    $spec = "$spec@$Ref"
}

Write-Host "Installing RetailOps CLI from $spec ..."
Invoke-Python -Python $python -Arguments @("-m", "pipx", "install", "--force", $spec)

$pipxBin = Join-Path $env:USERPROFILE ".local\bin"
if (Test-Path -LiteralPath $pipxBin -and -not ($env:PATH -split ";" | Where-Object { $_ -eq $pipxBin })) {
    $env:PATH = "$pipxBin;$env:PATH"
}

if (-not $NoCompletion -and (Get-Command retailops-cli -ErrorAction SilentlyContinue)) {
    retailops-cli --install-completion
}

Write-Host ""
Write-Host "RetailOps CLI is installed."
Write-Host ""
Write-Host "Next:"
Write-Host "  retailops-cli --help"
Write-Host "  retailops-cli auth login --url <RETAILOPS_API_URL>"
Write-Host "  retailops-cli auth whoami"
Write-Host ""
Write-Host "If the command is not found, restart PowerShell or run:"
Write-Host "  python -m pipx ensurepath"
