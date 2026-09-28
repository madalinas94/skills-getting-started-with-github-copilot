// Detectează aplicația din prim-plan, ca să știm pe ce s-a lucrat în sesiune.
// Windows: un proces PowerShell de lungă durată (fără module native).
// macOS: osascript. Linux: xdotool (dacă e instalat).
const { spawn, execFile } = require('child_process');

const INTERVAL_SEC = 5;

const PS_SCRIPT = `
$ErrorActionPreference = 'SilentlyContinue'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class BuddyFg {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
}
"@
while ($true) {
  $h = [BuddyFg]::GetForegroundWindow()
  $procId = 0
  [void][BuddyFg]::GetWindowThreadProcessId($h, [ref]$procId)
  $name = ''
  $desc = ''
  $p = Get-Process -Id $procId
  if ($p) {
    $name = $p.ProcessName
    try { $desc = $p.MainModule.FileVersionInfo.FileDescription } catch {}
  }
  [Console]::Out.WriteLine("$name|$desc")
  [Console]::Out.Flush()
  Start-Sleep -Seconds ${INTERVAL_SEC}
}
`;

// nume prietenoase pentru procesele des întâlnite
const FRIENDLY = {
  winword: 'Microsoft Word', excel: 'Microsoft Excel', powerpnt: 'PowerPoint', outlook: 'Outlook',
  olk: 'Outlook', msedge: 'Microsoft Edge', chrome: 'Google Chrome', firefox: 'Firefox',
  code: 'Visual Studio Code', teams: 'Microsoft Teams', 'ms-teams': 'Microsoft Teams',
  explorer: 'File Explorer', slack: 'Slack', spotify: 'Spotify', notepad: 'Notepad'
};

function friendlyName(proc, desc) {
  const key = (proc || '').toLowerCase();
  if (FRIENDLY[key]) return FRIENDLY[key];
  if (desc && desc.trim()) return desc.trim();
  return proc || 'Necunoscut';
}

class ActivityTracker {
  constructor(onSample) {
    this.onSample = onSample; // (appName, seconds) => void
    this.child = null;
    this.timer = null;
  }

  start() {
    if (this.child || this.timer) return;
    if (process.platform === 'win32') this.startWindows();
    else this.timer = setInterval(() => this.samplePosix(), INTERVAL_SEC * 1000);
  }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
    if (this.child) {
      this.child.kill();
      this.child = null;
    }
  }

  startWindows() {
    const encoded = Buffer.from(PS_SCRIPT, 'utf16le').toString('base64');
    this.child = spawn('powershell.exe',
      ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', encoded],
      { windowsHide: true });
    let buf = '';
    this.child.stdout.on('data', chunk => {
      buf += chunk.toString('utf8');
      let i;
      while ((i = buf.indexOf('\n')) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (!line) continue;
        const [proc, desc] = line.split('|');
        if (proc) this.onSample(friendlyName(proc, desc), INTERVAL_SEC);
      }
    });
    this.child.on('error', () => { this.child = null; });
    this.child.on('exit', () => { this.child = null; });
  }

  samplePosix() {
    if (process.platform === 'darwin') {
      execFile('osascript', ['-e', 'tell application "System Events" to get name of first application process whose frontmost is true'],
        (err, out) => { if (!err && out.trim()) this.onSample(out.trim(), INTERVAL_SEC); });
    } else {
      execFile('xdotool', ['getactivewindow', 'getwindowpid'], (err, out) => {
        if (err) return;
        execFile('ps', ['-p', out.trim(), '-o', 'comm='], (err2, name) => {
          if (!err2 && name.trim()) this.onSample(friendlyName(name.trim()), INTERVAL_SEC);
        });
      });
    }
  }
}

module.exports = { ActivityTracker, INTERVAL_SEC };
