param([string]$Destination = (Join-Path $PSScriptRoot "../dist/desktop"))
$ErrorActionPreference = "Stop"
$version = "1.0.3650.58"
$cache = Join-Path $env:LOCALAPPDATA "VocalRestore/Build/webview2-$version"
$dll = Join-Path $cache "lib/net462"
if (!(Test-Path "$dll\Microsoft.Web.WebView2.WinForms.dll")) {
    $archive = "$cache.zip"
    New-Item -ItemType Directory -Force (Split-Path $cache) | Out-Null
    Invoke-WebRequest "https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/$version/microsoft.web.webview2.$version.nupkg" -OutFile $archive
    if ((Get-FileHash $archive).Hash -ne "911A472128C82AC8BAA0C486C23342CC9DD6E7DC50D754E676726642CA065C60") {
        throw "Unexpected WebView2 SDK checksum."
    }
    Expand-Archive $archive $cache -Force
}
New-Item -ItemType Directory -Force $Destination | Out-Null
$csc = "$env:WINDIR/Microsoft.NET/Framework64/v4.0.30319/csc.exe"
$source = (Resolve-Path (Join-Path $PSScriptRoot "RestoreWindow.cs")).Path
$Destination = (Resolve-Path $Destination).Path
& $csc /nologo /target:winexe "/win32icon:$PSScriptRoot\bedroom-restore.ico" /platform:x64 /optimize+ "/out:$Destination\VocalRestore.exe" /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll "/r:$dll\Microsoft.Web.WebView2.Core.dll" "/r:$dll\Microsoft.Web.WebView2.WinForms.dll" $source
if ($LASTEXITCODE) { throw "Desktop compilation failed." }
Copy-Item "$dll\Microsoft.Web.WebView2.Core.dll","$dll\Microsoft.Web.WebView2.WinForms.dll","$cache/runtimes/win-x64/native/WebView2Loader.dll" $Destination -Force
foreach ($name in "LICENSE","NOTICE") {
    Copy-Item "$cache/$name.txt" "$Destination/WebView2-$name.txt" -Force
}
$config = Join-Path $Destination "restore-launcher.json"
if (!(Test-Path $config)) {
    $paths = @{ app_dir = (Resolve-Path "$PSScriptRoot/..").Path }
    if ($env:RESTORE_PYTHON) { $paths.python = $env:RESTORE_PYTHON }
    [IO.File]::WriteAllText($config, ($paths | ConvertTo-Json))
}
