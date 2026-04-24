param(
    [string]$ServerHost = "127.0.0.1",
    [int]$Port = 3210,
    [string]$PythonPath = ".\.venv\Scripts\python.exe",
    [string]$EmbeddingModel = "text-embedding-3-large",
    [int]$CheckRetries = 3,
    [int]$CheckTimeoutSec = 45,
    [string]$KnowledgeIndexBackend = "json",
    [string]$MemoryIndexBackend = "json",
    [switch]$SkipChatCheck,
    [switch]$RequireChat,
    [switch]$AllowHashFallback
)

if (-not (Test-Path -LiteralPath $PythonPath)) {
    Write-Host "Python executable not found: $PythonPath"
    exit 2
}

if ($RequireChat -and $SkipChatCheck) {
    Write-Host "Invalid args: -RequireChat cannot be used with -SkipChatCheck."
    exit 2
}

$env:ORCHESTRATOR_KNOWLEDGE_INDEX_BACKEND = $KnowledgeIndexBackend
$env:ORCHESTRATOR_MEMORY_INDEX_BACKEND = $MemoryIndexBackend
$env:ORCHESTRATOR_EMBEDDING_MODEL = $EmbeddingModel

if ($AllowHashFallback) {
    $env:ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED = "1"
} else {
    $env:ORCHESTRATOR_EMBEDDING_FALLBACK_ENABLED = "0"
}

$checkArgs = @(
    "-m", "backend.dev.check_embedding_endpoint",
    "--embedding-model", $EmbeddingModel,
    "--retries", "$CheckRetries",
    "--timeout", "$CheckTimeoutSec"
)

if (-not $SkipChatCheck) {
    $checkArgs += "--check-chat"
}
if ($RequireChat) {
    $checkArgs += "--require-chat"
}

Write-Host "[1/2] Checking embedding endpoint availability..."
& $PythonPath @checkArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Embedding preflight check failed. Backend startup aborted."
    exit $LASTEXITCODE
}

Write-Host "[2/2] Starting backend server..."
& $PythonPath -m backend.main --host $ServerHost --port $Port
exit $LASTEXITCODE
