[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Provision", "Reset", "Up", "Down", "Status")]
    [string]$Action,

    [ValidateSet("medusa", "agent-api", "frontend", "all")]
    [string[]]$Services = @("medusa")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectName = "routedeck-medusa-demo"
$ProtectionIdentity = "routedeck-medusa-demo-v1"
$DatabaseName = "routedeck_medusa_demo"
$ExpectedVolumes = @(
    "routedeck-medusa-demo-postgres-v1",
    "routedeck-medusa-demo-redis-v1",
    "routedeck-medusa-demo-frontend-node-modules-v1",
    "routedeck-medusa-demo-frontend-core-node-modules-v1",
    "routedeck-medusa-demo-frontend-react-node-modules-v1",
    "routedeck-medusa-demo-frontend-app-node-modules-v1"
)
$ScriptDirectory = $PSScriptRoot
$MedusaAgentRoot = [IO.Path]::GetFullPath((Join-Path $ScriptDirectory ".."))
$RepositoryRoot = [IO.Path]::GetFullPath((Join-Path $MedusaAgentRoot "..\.."))
$ComposeFile = Join-Path $MedusaAgentRoot "infra\compose.yaml"
$ManifestContract = Join-Path $MedusaAgentRoot "infra\demo-manifest.json"
$GeneratedManifest = Join-Path $MedusaAgentRoot "infra\demo-manifest.generated.json"
$GeneratedCredentials = Join-Path $MedusaAgentRoot "infra\CREDS.generated.env"
$EnvironmentFile = Join-Path $MedusaAgentRoot ".env.local"
$DemoDataRoot = [IO.Path]::GetFullPath((Join-Path $MedusaAgentRoot ".demo-data"))
$SqlitePath = [IO.Path]::GetFullPath((Join-Path $DemoDataRoot "routedeck.sqlite"))
$SqliteUrl = "sqlite+pysqlite:///" + $SqlitePath.Replace("\", "/")
$RequiredIgnoreEntries = @(
    "examples/medusa-agent/.demo-data/",
    "examples/medusa-agent/.env.local",
    "examples/medusa-agent/infra/CREDS.generated.*",
    "examples/medusa-agent/infra/demo-manifest.generated.json",
    "*.sqlite-wal",
    "*.sqlite-shm",
    "artifacts/*.json"
)

function Assert-RequiredFiles {
    foreach ($path in @($ComposeFile, $ManifestContract)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Required protected-stack file is missing: $path"
        }
    }
    $ignorePath = Join-Path $RepositoryRoot ".gitignore"
    if (-not (Test-Path -LiteralPath $ignorePath -PathType Leaf)) {
        throw "Repository .gitignore is missing: $ignorePath"
    }
    $ignoreLines = Get-Content -LiteralPath $ignorePath
    foreach ($entry in $RequiredIgnoreEntries) {
        if ($ignoreLines -notcontains $entry) {
            throw "Required generated-data ignore is missing: $entry"
        }
    }
}

function New-Base64UrlSecret([int]$ByteCount) {
    $bytes = [byte[]]::new($ByteCount)
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
}

function Ensure-EnvironmentFile {
    $requiredNames = @(
        "ROUTEDECK_DEMO_POSTGRES_PASSWORD",
        "ROUTEDECK_DEMO_JWT_SECRET",
        "ROUTEDECK_DEMO_COOKIE_SECRET",
        "ROUTEDECK_STATE_ENCRYPTION_KEY"
    )
    if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
        $lines = @(
            "ROUTEDECK_DEMO_POSTGRES_PASSWORD=$(New-Base64UrlSecret 32)",
            "ROUTEDECK_DEMO_JWT_SECRET=$(New-Base64UrlSecret 48)",
            "ROUTEDECK_DEMO_COOKIE_SECRET=$(New-Base64UrlSecret 48)",
            "ROUTEDECK_STATE_ENCRYPTION_KEY=$(New-Base64UrlSecret 32)",
            "MEDUSA_BASE_URL=http://127.0.0.1:9100",
            "ROUTEDECK_DATABASE_URL=$SqliteUrl",
            "OPENAI_MODEL=gpt-5.4-mini",
            "OPENAI_API_KEY="
        )
        [IO.File]::WriteAllLines($EnvironmentFile, $lines, [Text.UTF8Encoding]::new($false))
    }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }
        $separator = $line.IndexOf("=")
        if ($separator -le 0) {
            throw "Malformed line in $EnvironmentFile"
        }
        $name = $line.Substring(0, $separator)
        $value = $line.Substring($separator + 1)
        if ($values.ContainsKey($name)) {
            throw "Duplicate environment setting: $name"
        }
        $values[$name] = $value
    }
    foreach ($name in $requiredNames) {
        if (-not $values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($values[$name])) {
            throw "Required environment setting is missing: $name"
        }
    }
    $bootstrapNames = @(
        "MEDUSA_PUBLISHABLE_KEY",
        "MEDUSA_REGION_ID",
        "MEDUSA_COUNTRY_CODE",
        "MEDUSA_SALES_CHANNEL_ID",
        "MEDUSA_PAYMENT_PROVIDER_ID"
    )
    $missingBootstrap = @($bootstrapNames | Where-Object { -not $values.ContainsKey($_) })
    if ($missingBootstrap.Count -gt 0) {
        $currentLines = @(Get-Content -LiteralPath $EnvironmentFile)
        $bootstrapLines = @($missingBootstrap | ForEach-Object { "$_=__PROVISIONING_REQUIRED__" })
        [IO.File]::WriteAllLines(
            $EnvironmentFile,
            @($currentLines + $bootstrapLines),
            [Text.UTF8Encoding]::new($false)
        )
    }
}

function Merge-GeneratedEnvironment {
    if (-not (Test-Path -LiteralPath $GeneratedCredentials -PathType Leaf)) {
        throw "Generated Medusa environment is missing: $GeneratedCredentials"
    }
    $requiredGenerated = @(
        "MEDUSA_PUBLISHABLE_KEY",
        "MEDUSA_REGION_ID",
        "MEDUSA_COUNTRY_CODE",
        "MEDUSA_SALES_CHANNEL_ID",
        "MEDUSA_PAYMENT_PROVIDER_ID"
    )
    $allValues = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { continue }
        $separator = $line.IndexOf("=")
        if ($separator -le 0) { throw "Malformed line in $EnvironmentFile" }
        $allValues[$line.Substring(0, $separator)] = $line.Substring($separator + 1)
    }
    $generatedValues = @{}
    foreach ($line in Get-Content -LiteralPath $GeneratedCredentials) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $separator = $line.IndexOf("=")
        if ($separator -le 0) { throw "Malformed generated environment line" }
        $name = $line.Substring(0, $separator)
        if ($name -notin $requiredGenerated) {
            throw "Unexpected generated environment field: $name"
        }
        $generatedValues[$name] = $line.Substring($separator + 1)
    }
    foreach ($name in $requiredGenerated) {
        if (-not $generatedValues.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($generatedValues[$name])) {
            throw "Required generated Medusa field is missing: $name"
        }
        $allValues[$name] = $generatedValues[$name]
    }
    $allValues.Remove("ROUTEDECK_DATABASE_PATH")
    $allValues["ROUTEDECK_DATABASE_URL"] = $SqliteUrl
    $allValues["MEDUSA_BASE_URL"] = "http://127.0.0.1:9100"
    if (-not $allValues.Contains("OPENAI_MODEL") -or [string]::IsNullOrWhiteSpace($allValues["OPENAI_MODEL"])) {
        $allValues["OPENAI_MODEL"] = "gpt-5.4-mini"
    }
    if (-not $allValues.Contains("OPENAI_API_KEY")) {
        $allValues["OPENAI_API_KEY"] = ""
    }
    $rendered = @($allValues.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" })
    [IO.File]::WriteAllLines($EnvironmentFile, $rendered, [Text.UTF8Encoding]::new($false))
}

function Assert-RuntimeEnvironment {
    $required = @(
        "MEDUSA_PUBLISHABLE_KEY",
        "MEDUSA_REGION_ID",
        "MEDUSA_COUNTRY_CODE",
        "MEDUSA_SALES_CHANNEL_ID",
        "MEDUSA_PAYMENT_PROVIDER_ID",
        "MEDUSA_BASE_URL",
        "ROUTEDECK_DATABASE_URL",
        "ROUTEDECK_STATE_ENCRYPTION_KEY",
        "OPENAI_MODEL"
    )
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { continue }
        $separator = $line.IndexOf("=")
        if ($separator -le 0) { throw "Malformed line in $EnvironmentFile" }
        $values[$line.Substring(0, $separator)] = $line.Substring($separator + 1)
    }
    foreach ($name in $required) {
        if (-not $values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($values[$name])) {
            throw "Provisioned runtime environment is missing: $name"
        }
        if ($values[$name] -eq "__PROVISIONING_REQUIRED__") {
            throw "Provisioned runtime environment still contains bootstrap marker: $name"
        }
    }
    if ($values["ROUTEDECK_DATABASE_URL"] -ne $SqliteUrl) {
        throw "ROUTEDECK_DATABASE_URL must target the protected demo-data database"
    }
    if ($values["MEDUSA_BASE_URL"] -ne "http://127.0.0.1:9100") {
        throw "MEDUSA_BASE_URL must use the fixed protected local Medusa port"
    }
}

function Assert-DockerAvailable {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI is unavailable"
    }
    & docker info --format "{{.ServerVersion}}" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "The selected local Docker engine is unavailable"
    }
}

function Invoke-Compose([string[]]$Arguments) {
    & docker compose `
        --project-name $ProjectName `
        --env-file $EnvironmentFile `
        --file $ComposeFile `
        --profile application `
        @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($Arguments -join ' ')"
    }
}

function Get-ComposeOutput([string[]]$Arguments) {
    $output = & docker compose `
        --project-name $ProjectName `
        --env-file $EnvironmentFile `
        --file $ComposeFile `
        --profile application `
        @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($Arguments -join ' ')"
    }
    return @($output)
}

function Invoke-ExistingSentinelValidation {
    Invoke-Compose @(
        "run", "--rm", "--no-deps",
        "-e", "ROUTEDECK_DEMO_SENTINEL_ACTION=validate",
        "medusa-setup",
        "npm", "run", "medusa", "--", "exec",
        "/server/src/scripts/routedeck-demo/medusa-sentinel.ts"
    )
}

function Get-VolumeLabel([string]$VolumeName) {
    $volumeNames = @(& docker volume ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) {
        throw "Could not enumerate Docker volumes"
    }
    if ($volumeNames -notcontains $VolumeName) { return $null }
    $labelJson = & docker volume inspect $VolumeName --format '{{json .Labels}}'
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect Docker volume: $VolumeName" }
    $labels = ([string]$labelJson | ConvertFrom-Json)
    $property = $labels.PSObject.Properties["com.routedeck.demo"]
    if ($null -eq $property) { return "" }
    return ([string]$property.Value).Trim()
}

function Assert-ProjectResources {
    foreach ($volumeName in $ExpectedVolumes) {
        $label = Get-VolumeLabel $volumeName
        if ($null -eq $label) {
            throw "Required protected volume does not exist: $volumeName"
        }
        if ($label -ne $ProtectionIdentity) {
            throw "Volume $volumeName has unexpected protection label '$label'"
        }
    }
    $containerIds = @(& docker ps -a `
        --filter "label=com.docker.compose.project=$ProjectName" `
        --format "{{.ID}}")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect protected project containers"
    }
    foreach ($containerId in $containerIds) {
        if ([string]::IsNullOrWhiteSpace($containerId)) {
            continue
        }
        $labelJson = & docker inspect $containerId --format '{{json .Config.Labels}}'
        if ($LASTEXITCODE -ne 0) {
            throw "Could not inspect protected project container"
        }
        $labels = ([string]$labelJson | ConvertFrom-Json)
        $property = $labels.PSObject.Properties["com.routedeck.demo"]
        if ($null -eq $property -or ([string]$property.Value).Trim() -ne $ProtectionIdentity) {
            throw "Compose project contains a container without the protected identity"
        }
    }
}

function Ensure-NewProtectedVolumes {
    foreach ($volumeName in $ExpectedVolumes) {
        & docker volume create `
            --label "com.routedeck.demo=$ProtectionIdentity" `
            $volumeName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create protected volume: $volumeName"
        }
    }
}

function Assert-DatabaseName {
    $database = (Get-ComposeOutput @(
        "exec", "-T", "postgres", "psql", "-U", "routedeck_medusa",
        "-d", $DatabaseName, "-At", "-c", "SELECT current_database();"
    ) | Select-Object -Last 1).Trim()
    if ($database -ne $DatabaseName) {
        throw "Database identity mismatch: '$database'"
    }
}

function Get-SentinelEvidence {
    $tableName = (Get-ComposeOutput @(
        "exec", "-T", "postgres", "psql", "-U", "routedeck_medusa",
        "-d", $DatabaseName, "-At", "-c",
        "SELECT COALESCE(to_regclass('public.routedeck_demo_sentinel')::text, '');"
    ) | Select-Object -Last 1).Trim()
    if ($tableName -eq "") {
        return $null
    }
    $evidence = @((Get-ComposeOutput @(
        "exec", "-T", "postgres", "psql", "-U", "routedeck_medusa",
        "-d", $DatabaseName, "-At", "-F", "|", "-c",
        "SELECT sentinel_id, contract_version, manifest_sha256 FROM routedeck_demo_sentinel ORDER BY sentinel_id;"
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }))
    if ($evidence.Count -ne 1) {
        throw "Database must contain exactly one protected sentinel row"
    }
    return ([string]$evidence[0]).Trim()
}

function Assert-GeneratedManifest([string]$DatabaseEvidence) {
    if (-not (Test-Path -LiteralPath $GeneratedManifest -PathType Leaf)) {
        throw "Generated seed manifest is missing: $GeneratedManifest"
    }
    $manifest = Get-Content -Raw -LiteralPath $GeneratedManifest | ConvertFrom-Json
    if ($manifest.sentinel -ne $ProtectionIdentity) {
        throw "Generated manifest sentinel mismatch"
    }
    $expectedEvidence = "$($manifest.sentinel)|$($manifest.contract_version)|$($manifest.sha256)"
    if ($DatabaseEvidence -ne $expectedEvidence) {
        throw "Generated manifest fingerprint does not match the database sentinel"
    }
}

function Assert-CompleteProtectedStack {
    Assert-ProjectResources
    Invoke-Compose @("up", "-d", "--wait", "postgres", "redis")
    Assert-DatabaseName
    $evidence = Get-SentinelEvidence
    if ($null -eq $evidence) {
        throw "Protected database sentinel is missing"
    }
    if (-not $evidence.StartsWith("$ProtectionIdentity|1|")) {
        throw "Protected database sentinel mismatch: $evidence"
    }
    Assert-GeneratedManifest $evidence
    Merge-GeneratedEnvironment
    Assert-RuntimeEnvironment
    return $evidence
}

function Assert-SqliteDeletionScope {
    $demoRootWithSeparator = $DemoDataRoot.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (-not $SqlitePath.StartsWith($demoRootWithSeparator, [StringComparison]::OrdinalIgnoreCase)) {
        throw "RouteDeck SQLite path is outside examples/medusa-agent/.demo-data"
    }
}

function Invoke-Provision {
    $existing = @{}
    foreach ($volumeName in $ExpectedVolumes) {
        $existing[$volumeName] = Get-VolumeLabel $volumeName
        if ($null -ne $existing[$volumeName] -and $existing[$volumeName] -ne $ProtectionIdentity) {
            throw "Same-named volume exists without the protected label: $volumeName"
        }
    }
    $existingCount = @($existing.Values | Where-Object { $null -ne $_ }).Count
    if ($existingCount -ne 0 -and $existingCount -ne $ExpectedVolumes.Count) {
        throw "Protected demo volumes are only partially present; refusing to guess recovery"
    }
    if ($existingCount -eq 0) {
        Ensure-NewProtectedVolumes
    }
    Assert-ProjectResources
    Invoke-Compose @("config", "--quiet")
    Invoke-Compose @("up", "-d", "--wait", "postgres", "redis")
    Assert-DatabaseName
    $evidence = Get-SentinelEvidence
    if ($existingCount -eq $ExpectedVolumes.Count) {
        if ($null -ne $evidence) {
            Invoke-ExistingSentinelValidation
            $evidence = Get-SentinelEvidence
            if ($null -eq $evidence) {
                throw "Protected database sentinel disappeared during validation"
            }
            Assert-GeneratedManifest $evidence
            Merge-GeneratedEnvironment
            Assert-RuntimeEnvironment
            Write-Host "Protected demo stack already provisioned; seed was not rerun."
            Write-Host "Manifest evidence: $evidence"
            return
        }
        $publicTableCount = [int]((Get-ComposeOutput @(
            "exec", "-T", "postgres", "psql", "-U", "routedeck_medusa",
            "-d", $DatabaseName, "-At", "-c",
            "SELECT count(*) FROM pg_tables WHERE schemaname = 'public';"
        ) | Select-Object -Last 1).Trim())
        if ($publicTableCount -ne 0) {
            Write-Host "Existing protected database has schema but no sentinel."
            Write-Host "Setup will validate exact canonical seed keys and recover only the sentinel."
        }
        else {
            Write-Host "Resuming an empty, labeled bootstrap created before schema migration."
        }
    }
    elseif ($null -ne $evidence) {
        throw "New protected database unexpectedly contains a sentinel"
    }
    Invoke-Compose @("run", "--rm", "--no-deps", "medusa-setup")
    $evidence = Get-SentinelEvidence
    if ($null -eq $evidence) {
        throw "Provisioning completed without the required database sentinel"
    }
    Assert-GeneratedManifest $evidence
    Merge-GeneratedEnvironment
    Assert-RuntimeEnvironment
    Write-Host "Provisioned protected local Medusa stack."
    Write-Host "Manifest evidence: $evidence"
}

function Invoke-Reset {
    $null = Assert-CompleteProtectedStack
    Assert-SqliteDeletionScope
    Invoke-Compose @("down", "--volumes", "--remove-orphans")
    foreach ($volumeName in $ExpectedVolumes) {
        $remainingLabel = Get-VolumeLabel $volumeName
        if ($null -eq $remainingLabel) { continue }
        if ($remainingLabel -ne $ProtectionIdentity) {
            throw "Reset stopped because remaining volume identity changed: $volumeName"
        }
        & docker volume rm $volumeName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Reset could not delete the verified protected volume: $volumeName"
        }
    }
    if (Test-Path -LiteralPath $DemoDataRoot) {
        $resolvedDemoRoot = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $DemoDataRoot))
        if ($resolvedDemoRoot -ne $DemoDataRoot) {
            throw "Resolved demo-data deletion target changed unexpectedly"
        }
        Remove-Item -LiteralPath $resolvedDemoRoot -Recurse -Force
    }
    Invoke-Provision
}

function Invoke-Up {
    $evidence = Assert-CompleteProtectedStack
    $targets = [Collections.Generic.List[string]]::new()
    foreach ($service in $Services) {
        switch ($service) {
            "medusa" { $targets.Add("medusa") }
            "agent-api" { $targets.Add("agent-api") }
            "frontend" { $targets.Add("frontend") }
            "all" {
                $targets.Add("medusa")
                $targets.Add("agent-api")
                $targets.Add("frontend")
            }
            default { throw "Unsupported service: $service" }
        }
    }
    Invoke-Compose (@("up", "-d", "--wait") + @($targets | Select-Object -Unique))
    Write-Host "Protected stack identity: $evidence"
    if ($targets -contains "medusa") { Write-Host "Medusa: http://127.0.0.1:9100" }
    if ($targets -contains "agent-api") { Write-Host "Agent API: http://127.0.0.1:8098" }
    if ($targets -contains "frontend") { Write-Host "Frontend: http://127.0.0.1:5198" }
}

function Invoke-Down {
    Assert-ProjectResources
    Invoke-Compose @("down", "--remove-orphans")
    Write-Host "Stopped only Compose project $ProjectName; protected volumes remain."
}

function Invoke-Status {
    Assert-ProjectResources
    if (-not (Test-Path -LiteralPath $GeneratedManifest -PathType Leaf)) {
        throw "Generated seed manifest is missing: $GeneratedManifest"
    }
    $manifest = Get-Content -Raw -LiteralPath $GeneratedManifest | ConvertFrom-Json
    if (
        $manifest.sentinel -ne $ProtectionIdentity -or
        [int]$manifest.contract_version -ne 1 -or
        [string]::IsNullOrWhiteSpace([string]$manifest.sha256)
    ) {
        throw "Generated seed manifest identity is invalid"
    }
    $evidence = "$($manifest.sentinel)|$($manifest.contract_version)|$($manifest.sha256)"
    $allContainers = @(& docker ps -a `
        --filter "label=com.docker.compose.project=$ProjectName" `
        --format "{{.Names}}|{{.State}}|{{.Status}}")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect protected project containers"
    }
    $runningContainers = @(& docker ps `
        --filter "label=com.docker.compose.project=$ProjectName" `
        --format "{{.Names}}")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect running protected project containers"
    }
    Write-Host "Protected project containers: $($allContainers.Count) total, $($runningContainers.Count) running"
    foreach ($container in $allContainers) {
        if (-not [string]::IsNullOrWhiteSpace($container)) {
            Write-Host $container
        }
    }
    Write-Host "Manifest evidence: $evidence"
}

Assert-RequiredFiles
if ($Action -ne "Status") {
    Ensure-EnvironmentFile
}
Assert-DockerAvailable
Assert-SqliteDeletionScope

switch ($Action) {
    "Provision" { Invoke-Provision }
    "Reset" { Invoke-Reset }
    "Up" { Invoke-Up }
    "Down" { Invoke-Down }
    "Status" { Invoke-Status }
}
