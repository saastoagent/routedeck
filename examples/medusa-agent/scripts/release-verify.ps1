[CmdletBinding()]
param(
    [switch]$ResetProtectedDemo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDirectory = $PSScriptRoot
$MedusaAgentRoot = [IO.Path]::GetFullPath((Join-Path $ScriptDirectory ".."))
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $MedusaAgentRoot "..\.."))
$DemoStackScript = Join-Path $ScriptDirectory "demo-stack.ps1"
$EnvironmentFile = Join-Path $MedusaAgentRoot ".env.local"
$GeneratedManifest = Join-Path $MedusaAgentRoot "infra\demo-manifest.generated.json"
$E2eRoot = Join-Path $MedusaAgentRoot "e2e"
$RunId = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$BundleRoot = Join-Path $ProjectRoot "artifacts\release\$RunId"
$ContainerBundleRoot = "/workspace/artifacts/release/$RunId"
$RawBrowserRoot = Join-Path ([IO.Path]::GetTempPath()) "routedeck-browser-$RunId"
$CleanRoot = Join-Path ([IO.Path]::GetTempPath()) "routedeck-clean-$RunId"
$CleanSource = Join-Path $CleanRoot "source"
$CommandsPath = Join-Path $BundleRoot "commands.jsonl"
$Python = "python"
$Pnpm = "pnpm"
$PowerShell = "powershell"
$ManagedEnvironmentNames = @(
    "ROUTEDECK_MODEL_MODE",
    "ROUTEDECK_TEST_ONLY",
    "ROUTEDECK_RELEASE_BUNDLE",
    "ROUTEDECK_RELEASE_RAW_DIR",
    "ROUTEDECK_RELEASE_RUN_ID",
    "ROUTEDECK_E2E_REPORT_NAME",
    "ROUTEDECK_PERSISTENCE_STORAGE_STATE"
)
$OriginalEnvironment = @{}
foreach ($name in $ManagedEnvironmentNames) {
    $OriginalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

$RequiredGates = @(
    "framework_correctness",
    "boundary_and_adapter_integrity",
    "real_commerce_source_of_truth",
    "browser_agent_and_developer_experience"
)
$GateResults = [ordered]@{}
foreach ($gate in $RequiredGates) {
    $GateResults[$gate] = [ordered]@{
        status = "fail"
        evidence = [ordered]@{}
    }
}

function Write-Utf8Text([string]$Path, [string]$Text) {
    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Write-Json([string]$Path, [object]$Value) {
    Write-Utf8Text $Path (($Value | ConvertTo-Json -Depth 30) + "`n")
}

function Write-GateResults {
    Write-Json (Join-Path $BundleRoot "gate-results.json") $GateResults
}

function Set-GatePassed([string]$Name, [hashtable]$Evidence) {
    if ($Name -notin $RequiredGates) {
        throw "Unknown release gate: $Name"
    }
    $GateResults[$Name] = [ordered]@{
        status = "pass"
        evidence = $Evidence
    }
    Write-GateResults
}

function Assert-RequiredFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required release input is missing: $Path"
    }
}

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required local command is unavailable: $Name"
    }
}

function Get-SafeArguments([string[]]$Arguments) {
    return @($Arguments | ForEach-Object {
        ([string]$_).Replace($BundleRoot, "<bundle>").Replace(
            $ProjectRoot,
            "<repo>"
        ).Replace([IO.Path]::GetTempPath(), "<temp>\")
    })
}

function Add-CommandRecord([hashtable]$Record) {
    $line = $Record | ConvertTo-Json -Compress -Depth 10
    [IO.File]::AppendAllText(
        $CommandsPath,
        $line + "`n",
        [Text.UTF8Encoding]::new($false)
    )
}

function Invoke-RecordedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory = $ProjectRoot,
        [string]$LogPath,
        [int[]]$SuccessExitCodes = @(0)
    )
    $started = [DateTime]::UtcNow
    $record = [ordered]@{
        name = $Name
        program = [string](@(Get-SafeArguments @($FilePath))[0])
        arguments = @(Get-SafeArguments $Arguments)
        started_utc = $started.ToString("o")
        finished_utc = $null
        status = "fail"
        exit_code = $null
    }
    Push-Location $WorkingDirectory
    try {
        if ([string]::IsNullOrWhiteSpace($LogPath)) {
            & $FilePath @Arguments
        }
        else {
            $logParent = Split-Path -Parent $LogPath
            New-Item -ItemType Directory -Force -Path $logParent | Out-Null
            & $FilePath @Arguments 2>&1 | Tee-Object -FilePath $LogPath
        }
        $exitCode = $LASTEXITCODE
        $record.exit_code = $exitCode
        if ($exitCode -notin $SuccessExitCodes) {
            throw "Release command failed ($exitCode): $Name"
        }
        $record.status = "pass"
    }
    finally {
        Pop-Location
        $record.finished_utc = [DateTime]::UtcNow.ToString("o")
        Add-CommandRecord $record
    }
}

function Copy-CleanSource {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$DestinationRoot
    )

    $started = [DateTime]::UtcNow
    $record = [ordered]@{
        name = "developer.clean_source_copy"
        program = "git"
        arguments = @(Get-SafeArguments @(
            "-C", $SourceRoot, "ls-files", "--cached", "--others",
            "--exclude-standard", "--", "."
        ))
        started_utc = $started.ToString("o")
        finished_utc = $null
        status = "fail"
        exit_code = $null
        file_count = 0
    }

    try {
        $relativePaths = @(
            & git -C $SourceRoot ls-files --cached --others --exclude-standard -- .
        )
        $record.exit_code = $LASTEXITCODE
        if ($LASTEXITCODE -ne 0) {
            throw "Git source inventory failed ($LASTEXITCODE)"
        }
        $relativePaths = @(
            $relativePaths |
                ForEach-Object { ([string]$_).Trim() } |
                Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        )
        if ($relativePaths.Count -eq 0) {
            throw "Git source inventory was empty"
        }

        New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
        $sourcePrefix = [IO.Path]::GetFullPath($SourceRoot).TrimEnd(
            [IO.Path]::DirectorySeparatorChar,
            [IO.Path]::AltDirectorySeparatorChar
        ) + [IO.Path]::DirectorySeparatorChar
        $destinationPrefix = [IO.Path]::GetFullPath($DestinationRoot).TrimEnd(
            [IO.Path]::DirectorySeparatorChar,
            [IO.Path]::AltDirectorySeparatorChar
        ) + [IO.Path]::DirectorySeparatorChar

        foreach ($relativePath in $relativePaths) {
            if ([IO.Path]::IsPathRooted($relativePath)) {
                throw "Git source inventory returned a rooted path"
            }
            $sourcePath = [IO.Path]::GetFullPath((Join-Path $SourceRoot $relativePath))
            $destinationPath = [IO.Path]::GetFullPath(
                (Join-Path $DestinationRoot $relativePath)
            )
            if (
                -not $sourcePath.StartsWith(
                    $sourcePrefix,
                    [StringComparison]::OrdinalIgnoreCase
                ) -or
                -not $destinationPath.StartsWith(
                    $destinationPrefix,
                    [StringComparison]::OrdinalIgnoreCase
                )
            ) {
                throw "Git source inventory path escaped the clean-copy boundary"
            }
            if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                throw "Git source inventory entry is not a file: $relativePath"
            }
            $destinationParent = Split-Path -Parent $destinationPath
            New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
            Copy-Item -LiteralPath $sourcePath -Destination $destinationPath
        }

        $record.file_count = $relativePaths.Count
        $record.status = "pass"
    }
    finally {
        $record.finished_utc = [DateTime]::UtcNow.ToString("o")
        Add-CommandRecord $record
    }
}

function Remove-ScopedTemporaryDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedName,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $resolvedPath = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
    $temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar
    ) + [IO.Path]::DirectorySeparatorChar
    if (
        -not $resolvedPath.StartsWith(
            $temporaryRoot,
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        [IO.Path]::GetFileName($resolvedPath) -ne $ExpectedName
    ) {
        throw "$Label cleanup target escaped the scoped temporary directory"
    }
    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}

function Read-EnvironmentFile {
    Assert-RequiredFile $EnvironmentFile
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }
        $separator = $line.IndexOf("=")
        if ($separator -le 0) {
            throw "Malformed local release environment line"
        }
        $name = $line.Substring(0, $separator)
        if ($values.ContainsKey($name)) {
            throw "Duplicate local release environment setting: $name"
        }
        $values[$name] = $line.Substring($separator + 1)
    }
    return $values
}

function Resolve-RequiredSetting([string]$Name, [hashtable]$FileValues) {
    $processValue = [Environment]::GetEnvironmentVariable($Name, "Process")
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return [ordered]@{ value = $processValue; source = "process_environment" }
    }
    if ($FileValues.ContainsKey($Name) -and -not [string]::IsNullOrWhiteSpace($FileValues[$Name])) {
        return [ordered]@{ value = [string]$FileValues[$Name]; source = "protected_env_file" }
    }
    if ($Name -eq "OPENAI_API_KEY") {
        throw "openai_api_key_missing: a real OPENAI_API_KEY is mandatory for release"
    }
    throw "Required release setting is missing: $Name"
}

function Import-ProtectedEnvironment([hashtable]$FileValues) {
    foreach ($entry in $FileValues.GetEnumerator()) {
        if ($entry.Key -eq "OPENAI_API_KEY" -and -not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
            continue
        }
        [Environment]::SetEnvironmentVariable(
            [string]$entry.Key,
            [string]$entry.Value,
            "Process"
        )
    }
}

function Get-ToolVersion([string]$FilePath, [string[]]$Arguments) {
    $value = (& $FilePath @Arguments 2>&1 | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$value)) {
        throw "Could not determine local tool version: $FilePath"
    }
    return ([string]$value).Trim()
}

function ConvertTo-SemanticVersion([string]$Value, [string]$Label) {
    $match = [Text.RegularExpressions.Regex]::Match($Value, "\d+\.\d+(?:\.\d+)?")
    if (-not $match.Success) {
        throw "Could not parse $Label version: $Value"
    }
    return [version]$match.Value
}

function Test-SmokeUrl([string]$Name, [string]$Url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 15
    }
    catch {
        throw "Local smoke URL failed for $Name at $Url"
    }
    if ([int]$response.StatusCode -lt 200 -or [int]$response.StatusCode -ge 300) {
        throw "Local smoke URL returned HTTP $($response.StatusCode) for $Name at $Url"
    }
    return [int]$response.StatusCode
}

function Write-SeedEvidence([string]$Destination, [int]$TestCreatedRecordCount) {
    Assert-RequiredFile $GeneratedManifest
    $manifest = Get-Content -Raw -LiteralPath $GeneratedManifest | ConvertFrom-Json
    if (
        $manifest.sentinel -ne "routedeck-medusa-demo-v1" -or
        [int]$manifest.contract_version -ne 1 -or
        [string]::IsNullOrWhiteSpace([string]$manifest.sha256)
    ) {
        throw "Protected generated manifest has an invalid sentinel or fingerprint"
    }
    Write-Json $Destination ([ordered]@{
        schema_version = 1
        protected_stack = "routedeck-medusa-demo-v1"
        normalized_seed_fingerprint = [string]$manifest.sha256
        test_created_record_count = $TestCreatedRecordCount
        normalized_seed = $manifest.data
    })
}

function Write-FailedSummary {
    $text = @"
# RouteDeck Release Verification

Run: ``$RunId``

Result: **failed**. At least one mandatory release gate did not complete. No gate was replaced by a fallback, alternate model, provider, host, port, database, or scripted substitute.
"@
    Write-Utf8Text (Join-Path $BundleRoot "RELEASE_SUMMARY.md") ($text + "`n")
}

$Failure = $null
$CleanupFailure = $null
New-Item -ItemType Directory -Force -Path $BundleRoot | Out-Null
foreach ($directory in @(
    "junit",
    "coverage",
    "contracts",
    "medusa",
    "runtime",
    "browser\playwright-report",
    "docs"
)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot $directory) | Out-Null
}
Write-GateResults

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw "Release verification is supported only on the local Windows development machine"
    }
    foreach ($command in @($Python, "node", $Pnpm, "docker", $PowerShell, "git")) {
        Assert-Command $command
    }
    Assert-RequiredFile $DemoStackScript

    $fileValues = Read-EnvironmentFile
    Import-ProtectedEnvironment $fileValues
    $openAi = Resolve-RequiredSetting "OPENAI_API_KEY" $fileValues
    $buyerModel = Resolve-RequiredSetting "OPENAI_BUYER_MODEL" $fileValues
    $entryModel = Resolve-RequiredSetting "OPENAI_ENTRY_MODEL" $fileValues
    $turnPolicyModel = Resolve-RequiredSetting "OPENAI_TURN_POLICY_MODEL" $fileValues
    $encryption = Resolve-RequiredSetting "ROUTEDECK_STATE_ENCRYPTION_KEY" $fileValues
    foreach ($requiredName in @(
        "MEDUSA_PUBLISHABLE_KEY",
        "MEDUSA_REGION_ID",
        "MEDUSA_COUNTRY_CODE",
        "MEDUSA_SALES_CHANNEL_ID",
        "MEDUSA_PAYMENT_PROVIDER_ID"
    )) {
        $null = Resolve-RequiredSetting $requiredName $fileValues
    }
    $explicitInvalidKeys = @("test-key", "dummy", "placeholder", "changeme", "sk-test")
    if ($explicitInvalidKeys -contains ([string]$openAi.value).Trim().ToLowerInvariant()) {
        throw "openai_api_key_missing: a real OPENAI_API_KEY is mandatory for release"
    }
    if ([string]::IsNullOrWhiteSpace([string]$openAi.value)) {
        throw "openai_api_key_missing: a real OPENAI_API_KEY is mandatory for release"
    }
    if ([string]::IsNullOrWhiteSpace([string]$encryption.value)) {
        throw "ROUTEDECK_STATE_ENCRYPTION_KEY is mandatory for release"
    }

    $pythonVersion = Get-ToolVersion $Python @("--version")
    $nodeVersion = Get-ToolVersion "node" @("--version")
    $pnpmVersion = Get-ToolVersion $Pnpm @("--version")
    $dockerVersion = Get-ToolVersion "docker" @("version", "--format", "{{.Server.Version}}")

    if ((ConvertTo-SemanticVersion $pythonVersion "Python") -lt [version]"3.11") {
        throw "Python 3.11 or newer is required for release verification"
    }
    if ((ConvertTo-SemanticVersion $nodeVersion "Node.js") -lt [version]"22.12") {
        throw "Node.js 22.12 or newer is required for release verification"
    }

    $rootPackage = Get-Content -Raw -LiteralPath (Join-Path $ProjectRoot "package.json") | ConvertFrom-Json
    $expectedPnpmVersion = ([string]$rootPackage.packageManager).Replace("pnpm@", "")
    if ((ConvertTo-SemanticVersion $pnpmVersion "pnpm") -ne [version]$expectedPnpmVersion) {
        throw "pnpm $expectedPnpmVersion is required by packageManager"
    }
    if ($null -eq $rootPackage.devDependencies.PSObject.Properties["@vitest/coverage-v8"]) {
        throw "@vitest/coverage-v8 must be a direct devDependency before release coverage can run"
    }
    $e2ePackagePath = Join-Path $E2eRoot "package.json"
    Assert-RequiredFile $e2ePackagePath
    $e2ePackage = Get-Content -Raw -LiteralPath $e2ePackagePath | ConvertFrom-Json
    foreach ($scriptName in @("test:scripted", "test:live-model")) {
        if ($null -eq $e2ePackage.scripts.PSObject.Properties[$scriptName]) {
            throw "Browser release package is missing required script: $scriptName"
        }
    }

    Write-Json (Join-Path $BundleRoot "environment.json") ([ordered]@{
        schema_version = 1
        runtime_target = "local"
        operating_system = "windows"
        tool_versions = [ordered]@{
            python = $pythonVersion
            node = $nodeVersion
            pnpm = $pnpmVersion
            docker = $dockerVersion
        }
        models = [ordered]@{
            buyer = [string]$buyerModel.value
            entry = [string]$entryModel.value
            turn_policy = [string]$turnPolicyModel.value
        }
        model_credential_source = [string]$openAi.source
        secrets_redacted = $true
        ports = [ordered]@{ frontend = 5198; agent_api = 8098; medusa = 9100 }
        smoke_urls = [ordered]@{
            frontend = "http://127.0.0.1:5198"
            agent_api = "http://127.0.0.1:8098"
            medusa = "http://127.0.0.1:9100"
        }
    })

    if (-not $ResetProtectedDemo) {
        throw "Protected reset is mandatory for a release run; rerun with -ResetProtectedDemo after reviewing the sentinel scope"
    }
    Invoke-RecordedCommand -Name "stack.provision" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Provision"
    )
    Invoke-RecordedCommand -Name "stack.sentinel_before_reset" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Status"
    )
    Invoke-RecordedCommand -Name "stack.protected_reset_before" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Reset"
    )
    $fileValuesAfterReset = Read-EnvironmentFile
    Import-ProtectedEnvironment $fileValuesAfterReset
    Write-SeedEvidence (Join-Path $BundleRoot "medusa\seed-before.json") 0
    $env:ROUTEDECK_MODEL_MODE = "live"
    $env:ROUTEDECK_TEST_ONLY = "0"
    Remove-Item Env:\ROUTEDECK_RELEASE_BUNDLE -ErrorAction SilentlyContinue
    Invoke-RecordedCommand -Name "stack.up" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Up", "-Services", "all"
    )

    $frontendStatus = Test-SmokeUrl "frontend" "http://127.0.0.1:5198"
    $agentStatus = Test-SmokeUrl "agent-api" "http://127.0.0.1:8098/api/medusa-agent/health"
    $medusaStatus = Test-SmokeUrl "medusa" "http://127.0.0.1:9100/health"
    Write-Utf8Text (Join-Path $BundleRoot "docs\quickstart-smoke.txt") (@(
        "runtime_target=local",
        "frontend_url=http://127.0.0.1:5198 status=$frontendStatus",
        "agent_api_url=http://127.0.0.1:8098 status=$agentStatus",
        "medusa_url=http://127.0.0.1:9100 status=$medusaStatus"
    ) -join "`n")

    $pythonCoverage = Join-Path $BundleRoot "coverage\python.json"
    Invoke-RecordedCommand -Name "framework.python_tests" -FilePath $Python -Arguments @(
        "-m", "pytest", "tests", "examples/medusa-agent/backend/tests",
        "--ignore=examples/medusa-agent/backend/tests/integration/real_medusa",
        "--cov=routedeck_core", "--cov=routedeck_fastapi", "--cov=routedeck_langgraph",
        "--cov=routedeck_sqlalchemy", "--cov=routedeck_testing", "--cov-branch",
        "--cov-config=.coveragerc", "--cov-report=json:$pythonCoverage",
        "--cov-report=xml:$BundleRoot\coverage\python.xml",
        "--junitxml=$BundleRoot\junit\python.xml", "-q"
    )
    Invoke-RecordedCommand -Name "framework.frontend_tests" -FilePath $Pnpm -Arguments @("test")
    Invoke-RecordedCommand -Name "framework.frontend_typecheck" -FilePath $Pnpm -Arguments @("typecheck")
    Invoke-RecordedCommand -Name "framework.frontend_build" -FilePath $Pnpm -Arguments @("build")
    Invoke-RecordedCommand -Name "framework.python_lint" -FilePath $Python -Arguments @(
        "-m", "ruff", "check", "routedeck_core", "routedeck_langgraph", "routedeck_fastapi",
        "routedeck_sqlalchemy", "routedeck_testing", "examples/medusa-agent/backend", "tests"
    )
    Invoke-RecordedCommand -Name "framework.python_format" -FilePath $Python -Arguments @(
        "-m", "ruff", "format", "--check", "routedeck_core", "routedeck_langgraph",
        "routedeck_fastapi", "routedeck_sqlalchemy", "routedeck_testing",
        "examples/medusa-agent/backend", "tests"
    )
    Invoke-RecordedCommand -Name "framework.python_typecheck" -FilePath $Python -Arguments @(
        "-m", "mypy", "--explicit-package-bases", "routedeck_core", "routedeck_langgraph", "routedeck_fastapi",
        "routedeck_sqlalchemy", "routedeck_testing", "examples/medusa-agent/backend/medusa_agent",
        "examples/medusa-agent/backend/main.py"
    )
    Invoke-RecordedCommand -Name "framework.python_build" -FilePath $Python -Arguments @("-m", "build")

    $typescriptCoverageDirectory = Join-Path $BundleRoot "coverage\typescript"
    Invoke-RecordedCommand -Name "framework.typescript_coverage" -FilePath $Pnpm -Arguments @(
        "exec", "vitest", "run", "--config", "vitest.config.ts",
        "--coverage.enabled=true", "--coverage.provider=v8",
        "--coverage.reporter=json", "--coverage.reportsDirectory=$typescriptCoverageDirectory"
    )
    $typescriptCoverage = Join-Path $typescriptCoverageDirectory "coverage-final.json"
    Assert-RequiredFile $typescriptCoverage
    Invoke-RecordedCommand -Name "framework.critical_coverage" -FilePath $Python -Arguments @(
        "scripts/check_critical_coverage.py", "--python-json", $pythonCoverage,
        "--typescript-json", $typescriptCoverage,
        "--output", "$BundleRoot\coverage\critical-groups.json"
    )

    $contractTemp = Join-Path ([IO.Path]::GetTempPath()) "routedeck-contract-$RunId"
    New-Item -ItemType Directory -Force -Path $contractTemp | Out-Null
    Invoke-RecordedCommand -Name "framework.transport_schema" -FilePath $Python -Arguments @(
        "scripts/export_contracts.py", "--schema-output", "$contractTemp\routedeck.schema.json"
    )
    Invoke-RecordedCommand -Name "framework.typescript_contract_generation" -FilePath $Pnpm -Arguments @(
        "exec", "json2ts", "-i", "$contractTemp\routedeck.schema.json",
        "-o", "$contractTemp\generated.ts"
    )
    $schemaMatches = (Get-FileHash "$contractTemp\routedeck.schema.json" -Algorithm SHA256).Hash -eq
        (Get-FileHash (Join-Path $ProjectRoot "packages\core\schema\routedeck.schema.json") -Algorithm SHA256).Hash
    $typescriptMatches = (Get-FileHash "$contractTemp\generated.ts" -Algorithm SHA256).Hash -eq
        (Get-FileHash (Join-Path $ProjectRoot "packages\core\src\contracts\generated.ts") -Algorithm SHA256).Hash
    Write-Json (Join-Path $BundleRoot "contracts\schema-parity.json") ([ordered]@{
        schema_version = 1
        status = if ($schemaMatches -and $typescriptMatches) { "pass" } else { "fail" }
        python_schema_matches = $schemaMatches
        generated_typescript_matches = $typescriptMatches
    })
    if (-not $schemaMatches -or -not $typescriptMatches) {
        throw "Generated Python/TypeScript contract artifacts have schema drift"
    }
    Invoke-RecordedCommand -Name "framework.compiled_contracts" -FilePath $Python -Arguments @(
        "scripts/export_contracts.py", "--app-factory",
        "medusa_agent.composition:compile_medusa_app_spec", "--output",
        "$BundleRoot\contracts"
    )
    Write-Json (Join-Path $BundleRoot "contracts\conformance-results.json") ([ordered]@{
        schema_version = 1
        status = "pass"
        python = "pass"
        typescript = "pass"
    })
    Set-GatePassed "framework_correctness" @{
        critical_branch_coverage = "pass"
        contract_schema_parity = "pass"
        python_and_typescript_builds = "pass"
    }

    Invoke-RecordedCommand -Name "boundary.report" -FilePath $Python -Arguments @(
        "scripts/check_boundaries.py", "--json", "$BundleRoot\contracts\boundary-report.json"
    )
    Set-GatePassed "boundary_and_adapter_integrity" @{
        boundary_report = "contracts/boundary-report.json"
        expected_violation_count = 0
    }

    Invoke-RecordedCommand -Name "commerce.real_medusa" -FilePath $Python -Arguments @(
        "-m", "pytest", "examples/medusa-agent/backend/tests/integration/real_medusa",
        "--junitxml=$BundleRoot\junit\real-medusa.xml", "-q"
    )

    $env:ROUTEDECK_RELEASE_BUNDLE = $ContainerBundleRoot
    $env:ROUTEDECK_MODEL_MODE = "scripted-test-only"
    $env:ROUTEDECK_TEST_ONLY = "1"
    Invoke-RecordedCommand -Name "browser.scripted_backend_start" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Up", "-Services", "agent-api"
    )
    $null = Test-SmokeUrl "scripted-agent-api" "http://127.0.0.1:8098/api/medusa-agent/health"
    $env:ROUTEDECK_RELEASE_BUNDLE = $BundleRoot
    $env:ROUTEDECK_RELEASE_RAW_DIR = $RawBrowserRoot
    $env:ROUTEDECK_RELEASE_RUN_ID = $RunId
    $env:ROUTEDECK_E2E_REPORT_NAME = "scripted"
    Invoke-RecordedCommand -Name "browser.scripted_test_only" -FilePath $Pnpm -Arguments @(
        "--dir", $E2eRoot, "run", "test:scripted"
    )

    Invoke-RecordedCommand -Name "browser.sanitize_measured_trace" -FilePath $Python -Arguments @(
        "examples/medusa-agent/scripts/sanitize-playwright-trace.py",
        "--input", "$RawBrowserRoot\full-flow-trace.raw.zip",
        "--output", "$BundleRoot\browser\full-flow-trace.zip",
        "--sensitive-values", "$RawBrowserRoot\sensitive-values.json",
        "--network-summary", "$BundleRoot\browser\network-boundary.json"
    )
    foreach ($requiredEvidence in @(
        "$BundleRoot\browser\network-events.ndjson",
        "$BundleRoot\browser\network-boundary.json",
        "$BundleRoot\browser\full-flow-trace.zip",
        "$BundleRoot\medusa\store-api-trace.ndjson",
        "$BundleRoot\medusa\order-proof.json",
        "$BundleRoot\runtime\supervision-trace.ndjson",
        "$BundleRoot\runtime\sse-trace.ndjson"
    )) {
        Assert-RequiredFile $requiredEvidence
    }

    Remove-Item Env:\ROUTEDECK_RELEASE_BUNDLE -ErrorAction SilentlyContinue
    $env:ROUTEDECK_MODEL_MODE = "live"
    $env:ROUTEDECK_TEST_ONLY = "0"
    Invoke-RecordedCommand -Name "browser.live_backend_start" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Up", "-Services", "agent-api"
    )
    $liveAgentStatus = Test-SmokeUrl "live-agent-api" "http://127.0.0.1:8098/api/medusa-agent/health"
    Write-Json (Join-Path $RawBrowserRoot "restart-observed.json") ([ordered]@{
        schema_version = 1
        run_id = $RunId
        agent_api_restart_command_status = "pass"
        post_restart_health_status = $liveAgentStatus
    })
    $env:ROUTEDECK_RELEASE_BUNDLE = $BundleRoot
    $env:ROUTEDECK_PERSISTENCE_STORAGE_STATE = Join-Path $RawBrowserRoot "persistence-storage-state.json"
    $env:ROUTEDECK_E2E_REPORT_NAME = "persistence"
    Invoke-RecordedCommand -Name "browser.persistence_after_restart" -FilePath $Pnpm -Arguments @(
        "--dir", $E2eRoot, "run", "test:persistence"
    )
    Assert-RequiredFile (Join-Path $BundleRoot "runtime\persistence-restart.json")
    Remove-Item Env:\ROUTEDECK_PERSISTENCE_STORAGE_STATE -ErrorAction SilentlyContinue
    $env:ROUTEDECK_E2E_REPORT_NAME = "live-model"
    Invoke-RecordedCommand -Name "browser.real_model" -FilePath $Pnpm -Arguments @(
        "--dir", $E2eRoot, "run", "test:live-model"
    )
    Assert-RequiredFile (Join-Path $BundleRoot "medusa\order-proof.json")
    Set-GatePassed "real_commerce_source_of_truth" @{
        real_medusa_store_api = "pass"
        independent_order_reread = "pass"
        order_proof = "medusa/order-proof.json"
    }

    Copy-CleanSource -SourceRoot $ProjectRoot -DestinationRoot $CleanSource
    Invoke-RecordedCommand -Name "developer.clean_python_venv" -FilePath $Python -Arguments @(
        "-m", "venv", "$CleanRoot\venv"
    ) -WorkingDirectory $CleanSource
    Invoke-RecordedCommand -Name "developer.clean_python_install" -FilePath "$CleanRoot\venv\Scripts\python.exe" -Arguments @(
        "-m", "pip", "install", ".[fastapi,langgraph,persistence,testing]",
        ".\examples\medusa-agent\backend"
    ) -WorkingDirectory $CleanSource
    Invoke-RecordedCommand -Name "developer.clean_python_import" -FilePath "$CleanRoot\venv\Scripts\python.exe" -Arguments @(
        "-c", "import routedeck_core, routedeck_fastapi, routedeck_langgraph, routedeck_sqlalchemy, medusa_agent"
    ) -WorkingDirectory $CleanSource
    Invoke-RecordedCommand -Name "developer.clean_pnpm_install" -FilePath $Pnpm -Arguments @(
        "install", "--frozen-lockfile", "--store-dir", "$CleanRoot\pnpm-store"
    ) -WorkingDirectory $CleanSource
    Invoke-RecordedCommand -Name "developer.clean_pnpm_build" -FilePath $Pnpm -Arguments @("build") `
        -WorkingDirectory $CleanSource
    Write-Utf8Text (Join-Path $BundleRoot "docs\clean-install.txt") (@(
        "runtime_target=local",
        "isolated_source_copy=pass",
        "fresh_python_venv=pass",
        "python_install_and_import=pass",
        "isolated_pnpm_store_install=pass",
        "frontend_build=pass"
    ) -join "`n")

    Set-GatePassed "browser_agent_and_developer_experience" @{
        scripted_model_scope = "test-only"
        live_model_smoke = "pass"
        model_execution = "real_openai_api_key"
        chromium_full_flow = "pass"
        clean_install = "pass"
    }

    Invoke-RecordedCommand -Name "stack.sentinel_before_final_reset" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Status"
    )
    Invoke-RecordedCommand -Name "stack.protected_reset_after" -FilePath $PowerShell -Arguments @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
        "-Action", "Reset"
    )
    Write-SeedEvidence (Join-Path $BundleRoot "medusa\seed-after-reset.json") 0
    Write-GateResults
    Invoke-RecordedCommand -Name "release.bundle_validation" -FilePath $Python -Arguments @(
        "examples/medusa-agent/scripts/release-summary.py", "--bundle", $BundleRoot,
        "--run-id", $RunId
    )
}
catch {
    $Failure = $_
    Write-GateResults
    Write-FailedSummary
}
finally {
    try {
        Invoke-RecordedCommand -Name "stack.scoped_down" -FilePath $PowerShell -Arguments @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $DemoStackScript,
            "-Action", "Down"
        )
    }
    catch {
        $CleanupFailure = $_
    }
    foreach ($cleanupTarget in @(
        @{
            path = $RawBrowserRoot
            expected_name = "routedeck-browser-$RunId"
            label = "Raw browser"
        },
        @{
            path = $CleanRoot
            expected_name = "routedeck-clean-$RunId"
            label = "Clean source"
        }
    )) {
        try {
            Remove-ScopedTemporaryDirectory `
                -Path $cleanupTarget.path `
                -ExpectedName $cleanupTarget.expected_name `
                -Label $cleanupTarget.label
        }
        catch {
            if ($null -eq $CleanupFailure) {
                $CleanupFailure = $_
            }
        }
    }
    foreach ($name in $ManagedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            [string]$OriginalEnvironment[$name],
            "Process"
        )
    }
}

if ($null -ne $Failure) {
    throw $Failure
}
if ($null -ne $CleanupFailure) {
    throw $CleanupFailure
}

Write-Host "RouteDeck release verification passed: $BundleRoot"
