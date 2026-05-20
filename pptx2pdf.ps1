# -----------------------------------------------
# INITIAL DRAFT FOR POWERPOINT 2 PDF TRANSFORMATION
# FOR WINDOWS-BASED SYSTEMS WITH POWERSHELL ENABLED
# INITIAL CODE VERSION FROM COPILOT WITH SMALL MANUAL CHANGES.
# TO BE (RE)STARTED MANUALLY OR BY TASK MANAGER
# -----------------------------------------------
#
# Magically turn this file into a oneliner that can be pasted to Powershell prompt instead of running this as a script using the oneliner below:
#
# (Get-Content .\pptx2pdf.ps1) -replace '^\s*#.*','' -replace '\s+$','' -replace '\bexit\s+\d*\b','return' | ? { $_ } | % { $_.Trim() } | Out-String | % { $_ -replace '\r?\n','; ' } | Set-Content .\pptx2pdf_oneliner.txt
#
# Note, end of line comments will produce an unusable oneliner, full line comments are erased 
#
# -----------------------------------------------
# READ TARGET FOLDERS FROM THE PDFPUBLISHER SETTINGS.INI
# -----------------------------------------------
$iniPath = "settings.ini"

# --- Check 1: Does the file exist? ---
if (-not (Test-Path $iniPath)) {
    Write-Error "settings.ini not found at: $iniPath. Aborting script."
    exit 1
}

# Read all lines
$lines = Get-Content $iniPath

# Keys we care about
$keys = @("lecture_slides_dir", "course_slides_dir")

# Extract directories
$folders = foreach ($line in $lines) {
    foreach ($key in $keys) {
        if ($line -match "^\s*$key\s*=\s*(.+)$") {
            $matches[1].Trim()
        }
    }
}

# Remove empty entries
$folders = $folders | Where-Object { $_ -and $_.Trim() -ne "" }

# --- Check 2: Did we find any folders? ---
if ($folders.Count -eq 0) {
    Write-Error "No valid folder paths found in settings.ini. Please add course_slides_dir and lecture_slides_dir keys for directories to monitor. Aborting script."
    exit 1
}

Write-Host "Monitoring the following folders:"
$folders

# -----------------------------------------------
# CONFIGURATION
# -----------------------------------------------
# Sleep time between loops (in seconds)
# 300 = 5 minutes
$sleepSeconds = 300   


# -----------------------------------------------
# MAIN LOOP
# -----------------------------------------------

Write-Host "Starting PPTX → PDF monitor..."

while ($true) {

    Write-Host "Scanning folders at $(Get-Date)..."

    # See if powerpoint is running or not
    $ppApp = $null 
    $powerpointWasRunning = $true
    try { 
        # Try to get an existing instance 
        $ppApp = [Runtime.InteropServices.Marshal]::GetActiveObject("PowerPoint.Application") 
        Write-Host "Powerpoint is running!"
        } catch { 
        # No existing instance → create one 
        Write-Host "Powerpoint needs to be started."
        $powerpointWasRunning = $false 
        $ppApp = New-Object -ComObject PowerPoint.Application 
        }

    #Not visible if possible and powerpoint was not running
    if (-not $powerpointWasRunning) {
        try { 
            # Attempt to hide PowerPoint $ppApp.
            Visible = [Microsoft.Office.Core.MsoTriState]::msoFalse 
            } catch { 
            Write-Warning "PowerPoint cannot be hidden on this system. Continuing with visible window." 
            # Fallback: force it visible so the script continues safely 
            $ppApp.Visible = [Microsoft.Office.Core.MsoTriState]::msoTrue 
            }
        }

    foreach ($folder in $folders) {
        if (-not (Test-Path $folder)) {
            Write-Warning "Folder not found: $folder"
            continue
        }
        Write-Host "Scanning folder $folder..."

        # Get all PPTX files in the folder (non-recursive)
        $pptxFiles = Get-ChildItem -Path $folder -Filter *.pptx -File

        foreach ($pptx in $pptxFiles) {

            $pdf = [System.IO.Path]::ChangeExtension($pptx.FullName, ".pdf")

            $needsUpdate = $false

            if (-not (Test-Path $pdf)) {
                Write-Host "PDF cannot be found for... $($pptx.Name)"
                # PDF does not exist → must create
                $needsUpdate = $true
            } else {
                # Compare timestamps
                $pptTime = (Get-Item $pptx.FullName).LastWriteTime
                $pdfTime = (Get-Item $pdf).LastWriteTime

                if ($pptTime -gt $pdfTime) {
                    Write-Host "PDF version is outdated for... $($pptx.Name)"
                    $needsUpdate = $true
                }
            }

            if ($needsUpdate) {
                Write-Host "Updating..."
                try {
                    $presentation = $ppApp.Presentations.Open($pptx.FullName, $false, $false, $false)
                    # File type 32 = PDF
                    $presentation.SaveAs($pdf, 32)   
                    $presentation.Close()
                } catch {
                    Write-Error "Failed to convert $($pptx.FullName): $_"
                }
            }
        }
    }

    # Close PowerPoint if it was not running
    if (-not $powerpointWasRunning) { 
         Write-Host "Powerpoint was not running, closing..."
         $ppApp.Quit()
    }


    #Variable sleep time depending on time of day and weekday
    if ((Get-Date).DayOfWeek -in 'Saturday','Sunday') {
        $sleepSeconds = 21600
        Write-Host "It's the weekend, sleeping for $($sleepSeconds/3600) hours..."
    } else {
    $hour = (Get-Date).Hour
    if ($hour -ge 8 -and $hour -lt 15) {
        $sleepSeconds = 300
        Write-Host "Office hours, sleeping for $($sleepSeconds/60) minutes..."
    } elseif ($hour -ge 15 -and $hour -lt 21) {
        $sleepSeconds = 1800
        Write-Host "Outside office hours, sleeping for $($sleepSeconds/60) minutes..."
    } else {
        $sleepSeconds = 10800
        Write-Host "Night time... sleeping for $($sleepSeconds/3600) hours..."
    }}

    Start-Sleep -Seconds $sleepSeconds
}
