$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
$output = "ffmpeg.zip"
$ffmpegPath = "ffmpeg"

# Download FFmpeg
Invoke-WebRequest -Uri $url -OutFile $output

# Extract the ZIP file
Expand-Archive -Path $output -DestinationPath $ffmpegPath -Force

# Move files from nested directory to ffmpeg directory
$nestedDir = Get-ChildItem -Path $ffmpegPath -Directory | Select-Object -First 1
Move-Item -Path "$($nestedDir.FullName)\*" -Destination $ffmpegPath -Force
Remove-Item $nestedDir.FullName -Force

# Clean up
Remove-Item $output -Force
