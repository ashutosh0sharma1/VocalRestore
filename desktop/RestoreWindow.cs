using System;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

[assembly: System.Reflection.AssemblyTitle("Bedroom ReStore")]
[assembly: System.Reflection.AssemblyProduct("Bedroom ReStore")]
[assembly: System.Reflection.AssemblyDescription("Local vocal cleanup for home recordings")]
[assembly: System.Reflection.AssemblyVersion("2.1.0.0")]

internal sealed class RestoreWindow : Form {
    readonly WebView2 view = new WebView2();
    readonly JavaScriptSerializer json = new JavaScriptSerializer();
    string home, jobs;

    [STAThread]
    static void Main() {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new RestoreWindow());
    }

    RestoreWindow() {
        Text = "Bedroom ReStore";
        Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        FormBorderStyle = FormBorderStyle.None;
        Padding = new Padding(4);
        BackColor = Color.FromArgb(224, 222, 211);
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(810, 700);
        MinimumSize = new Size(520, 540);
        view.Dock = DockStyle.Fill;
        Controls.Add(view);
        Shown += async delegate {
            try { await StartDesktop(); }
            catch (Exception error) { MessageBox.Show(this, error.Message, "Restore startup"); Close(); }
        };
    }

    Dictionary<string,string> StartEngine() {
        string here = AppDomain.CurrentDomain.BaseDirectory;
        string config = Path.Combine(here, "restore-launcher.json");
        var paths = File.Exists(config)
            ? json.Deserialize<Dictionary<string,string>>(File.ReadAllText(config))
            : new Dictionary<string,string>();
        string app = paths.ContainsKey("app_dir") ? paths["app_dir"] : here;
        string python = paths.ContainsKey("python") ? paths["python"] :
            Environment.GetEnvironmentVariable("RESTORE_PYTHON") ?? Path.Combine(app, ".venv", "Scripts", "python.exe");
        var info = new ProcessStartInfo(python, "scripts/launcher.py --no-browser --desktop-owner " +
            Process.GetCurrentProcess().Id + " --python \"" + python + "\"");
        info.WorkingDirectory = app;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        info.RedirectStandardOutput = info.RedirectStandardError = true;
        info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        info.StandardOutputEncoding = System.Text.Encoding.UTF8;
        using (var helper = Process.Start(info)) {
            var errors = helper.StandardError.ReadToEndAsync();
            string line = helper.StandardOutput.ReadLine();
            helper.WaitForExit();
            if (helper.ExitCode != 0 || line == null)
                throw new IOException("Could not open the local audio engine. " + line + " " + errors.Result);
            return json.Deserialize<Dictionary<string,string>>(line);
        }
    }

    async Task StartDesktop() {
        var engine = await Task.Run(() => {
            using (var startup = new System.Threading.Mutex(false, "Local\\VocalRestoreDesktopStartup")) {
                try { startup.WaitOne(); }
                catch (System.Threading.AbandonedMutexException) { }
                try { return StartEngine(); }
                finally { startup.ReleaseMutex(); }
            }
        });
        if (IsDisposed) return;
        home = engine["url"] + "/";
        if (!Regex.IsMatch(home, @"^http://127\.0\.0\.1:\d+/$")) throw new IOException("Invalid local service.");
        jobs = engine["jobs"];
        string profile = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                      "VocalRestore", "DesktopWebView");
        var environment = await CoreWebView2Environment.CreateAsync(null, profile);
        await view.EnsureCoreWebView2Async(environment);
        var core = view.CoreWebView2;
        core.Settings.IsNonClientRegionSupportEnabled = true;
        await core.AddScriptToExecuteOnDocumentCreatedAsync("window.restoreDesktop = true;");
        core.NavigationStarting += (s,e) => { e.Cancel = e.Uri != home; };
        core.NewWindowRequested += (s,e) => { e.Handled = true; };
        core.WebMessageReceived += (s,e) => {
            if (e.Source != home) return;
            string command = e.TryGetWebMessageAsString();
            BeginInvoke(new Action(() => {
                switch (command) {
                    case "minimize": WindowState = FormWindowState.Minimized; break;
                    case "maximize":
                        MaximizedBounds = Screen.FromHandle(Handle).WorkingArea;
                        WindowState = WindowState == FormWindowState.Maximized ?
                            FormWindowState.Normal : FormWindowState.Maximized;
                        break;
                    case "close": Close(); break;
                    default: Export(command); break;
                }
            }));
        };
        core.Navigate(home);
    }

    protected override void WndProc(ref Message m) {
        base.WndProc(ref m);
        const int hitTest = 0x84;
        if (m.Msg != hitTest || WindowState != FormWindowState.Normal) return;
        var point = PointToClient(new Point(unchecked((int)m.LParam.ToInt64())));
        bool left = point.X < Padding.Left, right = point.X >= Width - Padding.Right;
        bool top = point.Y < Padding.Top, bottom = point.Y >= Height - Padding.Bottom;
        // Windows HT codes provide native edge and corner resizing.
        int hit = top ? (left ? 13 : right ? 14 : 12) :
                  bottom ? (left ? 16 : right ? 17 : 15) : left ? 10 : right ? 11 : 0;
        if (hit != 0) m.Result = (IntPtr)hit;
    }

    void Export(string command) {
        var parts = Regex.Match(command, @"^(save|drag) ([a-f0-9]{32}) (wav|mp3)$");
        if (!parts.Success) return;
        try {
            string directory = Path.Combine(jobs, parts.Groups[2].Value);
            var state = json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(directory, "state.json")));
            if ((string)state["status"] != "complete") return;
            string ext = parts.Groups[3].Value;
            string source = Path.Combine(directory, "result", "cleaned." + ext);
            string stem = Path.GetFileNameWithoutExtension((string)state["name"]);
            foreach (char c in Path.GetInvalidFileNameChars()) stem = stem.Replace(c, '_');
            string name = stem + "-cleaned." + ext;
            if (parts.Groups[1].Value == "save") {
                using (var dialog = new SaveFileDialog { FileName = name, DefaultExt = ext,
                        Filter = ext.ToUpperInvariant() + " audio|*." + ext }) {
                    if (dialog.ShowDialog(this) == DialogResult.OK) File.Copy(source, dialog.FileName, true);
                }
            } else {
                // DAWs can reference the dropped file after Restore closes.
                string exports = Directory.CreateDirectory(Path.Combine(directory, "exports")).FullName;
                string path = Path.Combine(exports, name);
                if (!File.Exists(path)) {
                    string temp = Path.Combine(exports, Guid.NewGuid().ToString());
                    try { File.Copy(source, temp); File.Move(temp, path); }
                    finally { if (File.Exists(temp)) File.Delete(temp); }
                }
                var data = new DataObject();
                data.SetFileDropList(new StringCollection { path });
                view.DoDragDrop(data, DragDropEffects.Copy);
            }
        } catch (Exception error) { MessageBox.Show(this, error.Message, "Restore export"); }
    }
}
