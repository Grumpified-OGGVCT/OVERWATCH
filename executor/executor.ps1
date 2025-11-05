# OVERWATCH PowerShell Executor Service
# Safe process termination service with audit logging and validation

param(
    [int]$Port = 8080,
    [string]$BearerToken = $env:EXECUTOR_TOKEN,
    [string]$LogPath = "C:\OVERWATCH\logs\executor.log"
)

# Ensure log directory exists
$logDir = Split-Path -Parent $LogPath
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogPath -Value $logMessage
    Write-Host $logMessage
}

function Test-BearerToken {
    param([string]$AuthHeader)
    
    if (-not $AuthHeader) {
        return $false
    }
    
    if ($AuthHeader -notmatch "^Bearer\s+(.+)$") {
        return $false
    }
    
    $token = $Matches[1]
    return ($token -eq $BearerToken)
}

function Test-SafeCommand {
    param([string]$Command)
    
    # Only allow Stop-Process commands with specific format
    if ($Command -match "^Stop-Process\s+-Id\s+(\d+)\s+-Force$") {
        $pid = [int]$Matches[1]
        
        # Never allow killing system PIDs
        if ($pid -lt 1000) {
            return @{
                IsValid = $false
                Error = "Cannot kill system process (PID < 1000)"
            }
        }
        
        # Check if process exists
        try {
            $process = Get-Process -Id $pid -ErrorAction Stop
            
            # Check against deny list
            $denyList = @(
                'System', 'svchost', 'csrss', 'smss', 'wininit',
                'services', 'lsass', 'winlogon', 'explorer',
                'dwm', 'RuntimeBroker', 'Registry'
            )
            
            if ($process.ProcessName -in $denyList) {
                return @{
                    IsValid = $false
                    Error = "Process '$($process.ProcessName)' is protected"
                }
            }
            
            return @{
                IsValid = $true
                PID = $pid
                ProcessName = $process.ProcessName
            }
        }
        catch {
            return @{
                IsValid = $false
                Error = "Process $pid not found"
            }
        }
    }
    else {
        return @{
            IsValid = $false
            Error = "Invalid command format. Only 'Stop-Process -Id <pid> -Force' is allowed"
        }
    }
}

function Invoke-ProcessKill {
    param([int]$PID)
    
    try {
        $process = Get-Process -Id $PID -ErrorAction Stop
        $processName = $process.ProcessName
        
        Write-Log "Attempting to kill process: PID=$PID Name=$processName" -Level "WARN"
        
        # Try graceful termination first
        $process.CloseMainWindow() | Out-Null
        Start-Sleep -Milliseconds 500
        
        # Check if still running
        if (Get-Process -Id $PID -ErrorAction SilentlyContinue) {
            # Force kill
            Stop-Process -Id $PID -Force
            Write-Log "Process killed forcefully: PID=$PID Name=$processName" -Level "WARN"
        }
        else {
            Write-Log "Process terminated gracefully: PID=$PID Name=$processName" -Level "INFO"
        }
        
        # Log to Windows Event Log
        Write-EventLog -LogName Application -Source "OVERWATCH" -EventId 1001 `
            -EntryType Warning -Message "OVERWATCH killed process: PID=$PID Name=$processName" `
            -ErrorAction SilentlyContinue
        
        return @{
            Success = $true
            Message = "Process $PID ($processName) terminated successfully"
            PID = $PID
            ProcessName = $processName
        }
    }
    catch {
        Write-Log "Failed to kill process $PID : $_" -Level "ERROR"
        return @{
            Success = $false
            Error = $_.Exception.Message
            PID = $PID
        }
    }
}

# Create event log source if not exists
if (-not [System.Diagnostics.EventLog]::SourceExists("OVERWATCH")) {
    try {
        New-EventLog -LogName Application -Source "OVERWATCH"
        Write-Log "Created Windows Event Log source: OVERWATCH"
    }
    catch {
        Write-Log "Could not create event log source (may require admin): $_" -Level "WARN"
    }
}

Write-Log "Starting OVERWATCH PowerShell Executor on port $Port"

# Create HTTP listener
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://+:$Port/")

try {
    $listener.Start()
    Write-Log "HTTP listener started successfully"
}
catch {
    Write-Log "Failed to start HTTP listener: $_" -Level "ERROR"
    Write-Log "Make sure to run: netsh http add urlacl url=http://+:$Port/ user=Everyone" -Level "ERROR"
    exit 1
}

Write-Log "Executor ready. Listening on port $Port"

# Main request loop
while ($listener.IsListening) {
    try {
        # Wait for request
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response
        
        $method = $request.HttpMethod
        $url = $request.Url.LocalPath
        
        Write-Log "Received $method $url from $($request.RemoteEndPoint)"
        
        # Set CORS headers
        $response.Headers.Add("Access-Control-Allow-Origin", "*")
        $response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        $response.Headers.Add("Access-Control-Allow-Headers", "Authorization, Content-Type")
        
        # Handle OPTIONS (preflight)
        if ($method -eq "OPTIONS") {
            $response.StatusCode = 200
            $response.Close()
            continue
        }
        
        # Route: /health
        if ($url -eq "/health" -and $method -eq "GET") {
            $healthData = @{
                status = "healthy"
                timestamp = (Get-Date).ToString("o")
                uptime = (Get-Date) - $script:startTime
            } | ConvertTo-Json
            
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($healthData)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
            $response.StatusCode = 200
            $response.Close()
            continue
        }
        
        # Route: /metrics (Prometheus)
        if ($url -eq "/metrics" -and $method -eq "GET") {
            $metrics = "# HELP overwatch_executor_up Executor service status`n"
            $metrics += "# TYPE overwatch_executor_up gauge`n"
            $metrics += "overwatch_executor_up 1`n"
            
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($metrics)
            $response.ContentType = "text/plain"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
            $response.StatusCode = 200
            $response.Close()
            continue
        }
        
        # Route: /execute (POST only)
        if ($url -eq "/execute" -and $method -eq "POST") {
            # Verify bearer token
            $authHeader = $request.Headers["Authorization"]
            if (-not (Test-BearerToken -AuthHeader $authHeader)) {
                Write-Log "Unauthorized access attempt from $($request.RemoteEndPoint)" -Level "WARN"
                $response.StatusCode = 401
                $errorData = @{ error = "Unauthorized" } | ConvertTo-Json
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($errorData)
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
                $response.Close()
                continue
            }
            
            # Read request body
            $reader = New-Object System.IO.StreamReader($request.InputStream)
            $body = $reader.ReadToEnd()
            $reader.Close()
            
            try {
                $payload = $body | ConvertFrom-Json
                $command = $payload.command
                $alertId = $payload.alert_id
                
                Write-Log "Received execute request: Alert=$alertId Command=$command"
                
                # Validate command
                $validation = Test-SafeCommand -Command $command
                
                if (-not $validation.IsValid) {
                    Write-Log "Command validation failed: $($validation.Error)" -Level "ERROR"
                    $response.StatusCode = 400
                    $errorData = @{ 
                        success = $false
                        error = $validation.Error 
                    } | ConvertTo-Json
                    $buffer = [System.Text.Encoding]::UTF8.GetBytes($errorData)
                    $response.OutputStream.Write($buffer, 0, $buffer.Length)
                    $response.Close()
                    continue
                }
                
                # Execute kill
                $result = Invoke-ProcessKill -PID $validation.PID
                
                $responseData = $result | ConvertTo-Json
                $response.StatusCode = if ($result.Success) { 200 } else { 500 }
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($responseData)
                $response.ContentType = "application/json"
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
                $response.Close()
            }
            catch {
                Write-Log "Error processing execute request: $_" -Level "ERROR"
                $response.StatusCode = 500
                $errorData = @{ 
                    success = $false
                    error = $_.Exception.Message 
                } | ConvertTo-Json
                $buffer = [System.Text.Encoding]::UTF8.GetBytes($errorData)
                $response.OutputStream.Write($buffer, 0, $buffer.Length)
                $response.Close()
            }
            continue
        }
        
        # Route: Unknown
        $response.StatusCode = 404
        $errorData = @{ error = "Not found" } | ConvertTo-Json
        $buffer = [System.Text.Encoding]::UTF8.GetBytes($errorData)
        $response.OutputStream.Write($buffer, 0, $buffer.Length)
        $response.Close()
    }
    catch {
        Write-Log "Error in request loop: $_" -Level "ERROR"
    }
}

# Cleanup
$listener.Stop()
$listener.Close()
Write-Log "Executor stopped"
