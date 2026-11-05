// Stable Windows launcher/update agent. Application releases replace only runtime/current.
// Built with the .NET Framework compiler already present on supported Windows systems.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

internal static class SeJogaLauncher
{
    const string Repository = "ArchVeketo/SeJogaDesktopCompanion";
    const long MaxDownload = 1073741824;
    const long MaxExtracted = 2147483648;
    static readonly string Root = Path.GetDirectoryName(Application.ExecutablePath);
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = 1048576 };
    static Dictionary<string, object> Settings;
    static string Channel;
    static bool TestScope;
    static bool Quiet;
    static volatile bool CancelRequested;
    static volatile bool Committing;
    static ProgressForm Window;
    static int Result;

    [STAThread]
    static int Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        try
        {
            Settings = ReadJson(Path.Combine(Root, "channel-info.json"));
            Channel = Text(Settings, "channel");
            if (!new[] { "release", "prerelease", "nightly" }.Contains(Channel))
                throw new InvalidDataException("Canal de atualização inválido.");
            string scope = Text(Settings, "scope");
            if (scope != "machine" && scope != "test") throw new InvalidDataException("Instalação inválida.");
            TestScope = scope == "test";
            Quiet = args.Contains("--quiet");
            if (TestScope && (Under(Root, Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles)) ||
                             Under(Root, Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86))))
                throw new InvalidDataException("Modo de teste não pode atualizar Program Files.");
            if (args.Contains("--refresh-registration"))
            {
                RequireAdministrator();
                UpdateRegistry(ReadJson(Path.Combine(CurrentDirectory(), "release-info.json")));
                return 0;
            }
            if (args.Contains("--apply-update") || args.Contains("--prepare"))
            {
                RequireAdministrator();
                bool prepare = args.Contains("--prepare");
                string cache = prepare ? null : Path.Combine(Root, ".bootstrap-payload.zip");
                Window = new ProgressForm();
                Window.Shown += delegate
                {
                    Task.Run(delegate
                    {
                        try { ApplyUpdate(prepare, cache, args.Contains("--repair")); Result = 0; }
                        catch (OperationCanceledException) { Result = 2; }
                        catch (Exception error)
                        {
                            if (CancelRequested && !Committing) { Result = 2; }
                            else {
                            Result = 1;
                            File.WriteAllText(Path.Combine(Root, "update-last-error.txt"), error.Message);
                            if (!Quiet) Window.Invoke((Action)delegate { MessageBox.Show(Window, error.Message,
                                "Atualização não concluída", MessageBoxButtons.OK, MessageBoxIcon.Error); });
                            }
                        }
                        finally { Window.BeginInvoke((Action)delegate { Window.Finished = true; Window.Close(); }); }
                    });
                };
                Application.Run(Window);
                return Result;
            }
            // O instalador unico ja embute o runtime em runtime/current. Quando ele existe,
            // abrimos o mascote direto, sem exigir feed publicado (corrige o erro "nao achou o remote").
            // So disparamos o agente privilegiado em atualizacao manual (--update) ou quando nao ha
            // runtime algum (instalacao antiga/offline sem embutido) para tentar baixar a primeira versao.
            bool temRuntime = File.Exists(CurrentExecutable());
            if (args.Contains("--update") || !temRuntime)
            {
                var start = new ProcessStartInfo(Application.ExecutablePath, "--apply-update")
                    { UseShellExecute = true, Verb = TestScope ? "open" : "runas", WorkingDirectory = Root };
                try
                {
                    using (Process child = Process.Start(start)) { child.WaitForExit(); }
                }
                catch (System.ComponentModel.Win32Exception error)
                {
                    if (error.NativeErrorCode != 1223) throw;
                    return 0; // UAC was declined; the existing mascot was not closed.
                }
            }
            StartCurrent(); // Also recovers the previous app if an attempted update rolled back.
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show(error.Message, "SeJoga Companion", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    static string CurrentDirectory() { return Path.Combine(Root, "runtime", "current"); }
    static void RequireAdministrator()
    {
        if (!TestScope && !new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator))
            throw new InvalidOperationException("A atualização global requer permissão de administrador.");
    }
    static string CurrentExecutable() { return Path.Combine(CurrentDirectory(), "SeJogaCompanion.exe"); }
    static bool Under(string child, string parent)
    {
        if (String.IsNullOrEmpty(parent)) return false;
        return Path.GetFullPath(child).StartsWith(Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);
    }
    static string Text(Dictionary<string, object> data, string key)
    {
        object value;
        if (!data.TryGetValue(key, out value) || !(value is string)) throw new InvalidDataException("Metadado ausente: " + key);
        return (string)value;
    }
    static long Number(Dictionary<string, object> data, string key)
    {
        object value;
        if (!data.TryGetValue(key, out value)) throw new InvalidDataException("Metadado ausente: " + key);
        return Convert.ToInt64(value, CultureInfo.InvariantCulture);
    }
    static long[] VersionOrder(Dictionary<string, object> data)
    {
        object value;
        if (!data.TryGetValue("version_order", out value) || value is string || !(value is System.Collections.IEnumerable))
            throw new InvalidDataException("Ordem de versão ausente.");
        var result = ((System.Collections.IEnumerable)value).Cast<object>().Select(v => Convert.ToInt64(v, CultureInfo.InvariantCulture)).ToArray();
        if (result.Length != 5 || result.Take(3).Any(v => v < 0) || result[3] < -1 || result[3] > 3 || result[4] < 0)
            throw new InvalidDataException("Ordem de versão inválida.");
        return result;
    }
    static int CompareVersion(Dictionary<string, object> left, Dictionary<string, object> right)
    {
        var a = VersionOrder(left); var b = VersionOrder(right);
        for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return a[i].CompareTo(b[i]);
        return 0;
    }
    static Dictionary<string, object> ReadJson(string path)
    {
        if (new FileInfo(path).Length > 1048576) throw new InvalidDataException("Metadados muito grandes.");
        return Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(path, Encoding.UTF8));
    }
    static void Status(string text, int percent)
    {
        Window.BeginInvoke((Action)delegate { Window.Status.Text = text; Window.Progress.Value = Math.Max(0, Math.Min(100, percent)); Window.CancelButtonControl.Enabled = !Committing; });
        if (CancelRequested && !Committing) throw new OperationCanceledException();
    }
    static Uri Feed()
    {
        if (TestScope)
        {
            Uri test = new Uri(Text(Settings, "test_feed"));
            if (!test.IsLoopback || test.Scheme != "http") throw new InvalidDataException("Feed de teste deve ser local.");
            return test;
        }
        return new Uri("https://github.com/" + Repository + "/releases/download/updates-" + Channel + "/channel.json");
    }
    static bool FeedIndisponivel(Exception error)
    {
        // Feed ausente (404) ou rede indisponivel: tratamos como "sem atualizacao" se ja houver runtime.
        var web = error as WebException;
        if (web != null)
        {
            if (web.Status != WebExceptionStatus.ProtocolError) return true;
            var resposta = web.Response as HttpWebResponse;
            return resposta != null && (int)resposta.StatusCode == 404;
        }
        return error is IOException && !(error is InvalidDataException);
    }
    static bool Allowed(Uri uri)
    {
        if (TestScope) return uri.IsLoopback && uri.Scheme == "http";
        return uri.Scheme == "https" && String.IsNullOrEmpty(uri.UserInfo) && new[] {
            "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"
        }.Contains(uri.Host);
    }
    static HttpWebResponse Open(Uri uri)
    {
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
        for (int redirect = 0; redirect < 8; redirect++)
        {
            if (!Allowed(uri)) throw new InvalidDataException("Download fora do servidor oficial.");
            var request = (HttpWebRequest)WebRequest.Create(uri);
            request.AllowAutoRedirect = false;
            request.UserAgent = "SeJogaDesktopCompanion-Updater";
            request.Timeout = request.ReadWriteTimeout = 20000;
            var response = (HttpWebResponse)request.GetResponse();
            if ((int)response.StatusCode >= 300 && (int)response.StatusCode < 400)
            {
                string location = response.Headers["Location"];
                response.Close();
                uri = new Uri(uri, location);
                continue;
            }
            return response;
        }
        throw new IOException("Redirecionamentos demais no download.");
    }
    static Dictionary<string, object> Manifest()
    {
        Status("Consultando a versão atual do canal " + Channel + "…", 2);
        using (var response = Open(Feed()))
        using (var input = response.GetResponseStream())
        using (var content = new MemoryStream())
        {
            byte[] buffer = new byte[8192]; int count;
            while ((count = input.Read(buffer, 0, buffer.Length)) > 0)
            {
                if (content.Length + count > 1048576) throw new InvalidDataException("Manifesto muito grande.");
                content.Write(buffer, 0, count);
            }
            var data = Json.Deserialize<Dictionary<string, object>>(Encoding.UTF8.GetString(content.ToArray()));
            if (Number(data, "schema_version") != 1 || Text(data, "channel") != Channel ||
                Text(data, "architecture") != "windows-x64" || Number(data, "build_id") <= 0)
                throw new InvalidDataException("Pacote incompatível com esta instalação.");
            VersionOrder(data);
            if (Number(data, "size") <= 0 || Number(data, "size") > MaxDownload ||
                !System.Text.RegularExpressions.Regex.IsMatch(Text(data, "sha256"), "^[0-9a-f]{64}$"))
                throw new InvalidDataException("Integridade do pacote não informada.");
            var artifact = new Uri(Text(data, "url"));
            if (!Allowed(artifact) || (!TestScope && (artifact.Host != "github.com" ||
                !artifact.AbsolutePath.StartsWith("/" + Repository + "/releases/download/", StringComparison.Ordinal))))
                throw new InvalidDataException("Origem do pacote inválida.");
            return data;
        }
    }
    static string Hash(string path)
    {
        using (var sha = SHA256.Create())
        using (var stream = File.OpenRead(path))
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
    static bool Verified(string path, Dictionary<string, object> manifest)
    {
        return path != null && File.Exists(path) && new FileInfo(path).Length == Number(manifest, "size") &&
            Hash(path) == Text(manifest, "sha256");
    }
    static string Download(Dictionary<string, object> manifest, string folder, string cache)
    {
        string target = Path.Combine(folder, "payload.zip");
        if (Verified(cache, manifest)) File.Copy(cache, target, true);
        else
        {
            using (var response = Open(new Uri(Text(manifest, "url"))))
            using (var input = response.GetResponseStream())
            using (var output = File.Create(target))
            {
                byte[] buffer = new byte[262144]; int count; long total = 0;
                while ((count = input.Read(buffer, 0, buffer.Length)) > 0)
                {
                    total += count;
                    if (total > Number(manifest, "size")) throw new InvalidDataException("Pacote maior que o informado.");
                    output.Write(buffer, 0, count);
                    Status("Baixando o aplicativo…", 5 + (int)(total * 55 / Number(manifest, "size")));
                }
            }
        }
        if (!Verified(target, manifest)) throw new InvalidDataException("SHA256 inválido ou download incompleto.");
        return target;
    }
    static void Extract(string archive, string destination, Dictionary<string, object> manifest)
    {
        Status("Verificando e preparando os arquivos…", 65);
        Directory.CreateDirectory(destination);
        long total = 0;
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        using (var zip = ZipFile.OpenRead(archive))
        {
            if (zip.Entries.Count > 20000) throw new InvalidDataException("Arquivos demais no pacote.");
            foreach (var entry in zip.Entries)
            {
                string relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
                if (Path.IsPathRooted(relative) || relative.Contains(":") ||
                    relative.Split(Path.DirectorySeparatorChar).Any(p => p == "..") ||
                    relative.StartsWith("user-data", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Caminho inseguro ou perfil pessoal no pacote.");
                string path = Path.GetFullPath(Path.Combine(destination, relative));
                if (!Under(path, destination) || !names.Add(path)) throw new InvalidDataException("Entrada inválida ou duplicada no ZIP.");
                if (entry.FullName.EndsWith("/")) { Directory.CreateDirectory(path); continue; }
                total += entry.Length;
                if (entry.Length < 0 || total > MaxExtracted) throw new InvalidDataException("Pacote descompactado muito grande.");
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                using (var input = entry.Open())
                using (var output = new FileStream(path, FileMode.CreateNew))
                {
                    byte[] buffer = new byte[65536]; int count; long written = 0;
                    while ((count = input.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        written += count;
                        if (written > entry.Length) throw new InvalidDataException("Tamanho descompactado inválido.");
                        output.Write(buffer, 0, count);
                    }
                    if (written != entry.Length) throw new InvalidDataException("Arquivo truncado no pacote.");
                }
                Status("Preparando os arquivos…", 70);
            }
        }
        var info = ReadJson(Path.Combine(destination, "release-info.json"));
        if (!File.Exists(Path.Combine(destination, "SeJogaCompanion.exe")) ||
            !Directory.Exists(Path.Combine(destination, "_internal")) ||
            Text(info, "channel") != Channel || Text(info, "version") != Text(manifest, "version") ||
            Number(info, "build_id") != Number(manifest, "build_id"))
            throw new InvalidDataException("Conteúdo do pacote não corresponde à versão anunciada.");
        if (CompareVersion(info, manifest) != 0) throw new InvalidDataException("Versão inconsistente no pacote.");
    }
    static void ApplyUpdate(bool prepare, string cache, bool repair)
    {
        string mutexName;
        using (var sha = SHA256.Create()) mutexName = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(Root.ToUpperInvariant()))).Replace("-", "");
        using (var mutex = new Mutex(false, "Global\\SeJogaUpdate-" + mutexName))
        {
            bool locked;
            try { locked = mutex.WaitOne(0); }
            catch (AbandonedMutexException) { locked = true; }
            if (!locked) throw new IOException("Outra atualização desta instalação está em andamento.");
            string work = Path.Combine(Root, ".update-" + Guid.NewGuid().ToString("N"));
            try
            {
                string current = CurrentDirectory();
                string previous = Path.Combine(Root, "runtime", "previous");
                if (!prepare && !Directory.Exists(current) && Directory.Exists(previous))
                    Directory.Move(previous, current);
                // Degradacao graciosa: se o feed estiver 404/offline mas ja houver runtime valido,
                // seguimos abrindo o mascote em vez de abortar (corrige o antigo "nao achou o remote").
                Dictionary<string, object> manifest;
                try { manifest = Manifest(); }
                catch (Exception error)
                {
                    if (FeedIndisponivel(error) && File.Exists(CurrentExecutable())) return;
                    throw;
                }
                if (!prepare && File.Exists(Path.Combine(current, "release-info.json")))
                {
                    var installed = ReadJson(Path.Combine(current, "release-info.json"));
                    if (CompareVersion(installed, manifest) > 0 || Number(installed, "build_id") > Number(manifest, "build_id") ||
                        (!repair && Number(installed, "build_id") == Number(manifest, "build_id"))) return;
                }
                Directory.CreateDirectory(work);
                string archive = Download(manifest, work, cache);
                string staged = Path.Combine(work, "staged");
                Extract(archive, staged, manifest);
                if (prepare) { File.Copy(archive, Path.Combine(Root, "prepared-payload.zip"), true); return; }
                Committing = true;
                Status("Fechando o Mário para aplicar a atualização…", 80);
                CloseApplications(new[] { Path.Combine(current, "SeJogaCompanion.exe"), Path.Combine(Root, "SeJogaCompanion.exe") }.Where(File.Exists).ToArray());
                Directory.CreateDirectory(Path.GetDirectoryName(current));
                if (Directory.Exists(previous)) Directory.Delete(previous, true);
                bool moved = false;
                try
                {
                    if (Directory.Exists(current)) { Directory.Move(current, previous); moved = true; }
                    Directory.Move(staged, current);
                }
                catch
                {
                    if (moved && !Directory.Exists(current)) Directory.Move(previous, current);
                    throw;
                }
                UpdateRegistry(manifest);
                Status("Atualização concluída.", 100);
            }
            finally
            {
                if (Directory.Exists(work)) Directory.Delete(work, true);
                mutex.ReleaseMutex();
            }
        }
    }
    static void UpdateRegistry(Dictionary<string, object> manifest)
    {
        // The installer registers the product; payload updates refresh its version.
        string id = TestScope ? "{A243421C-F2B1-4563-873B-7AC5A4C89380}" :
            Channel == "release" ? "{27AD0F68-F575-45DB-B24A-C94954679DA1}" :
            Channel == "prerelease" ? "{E77A6F2A-F8AE-4EB8-BF84-2FC2C6CE0B19}" : "{26B8DB1E-7B18-4E13-802E-202E8C0A4854}";
        using (var hive = Microsoft.Win32.RegistryKey.OpenBaseKey(TestScope ? Microsoft.Win32.RegistryHive.CurrentUser : Microsoft.Win32.RegistryHive.LocalMachine,
                    Microsoft.Win32.RegistryView.Registry64))
        using (var key = hive.OpenSubKey("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\" + id + "_is1", true))
            if (key != null) key.SetValue("DisplayVersion", Text(manifest, "version"));
    }
    static void StartCurrent()
    {
        string exe = CurrentExecutable();
        if (!File.Exists(exe)) throw new FileNotFoundException("Aplicativo não instalado. Execute o instalador com acesso à internet.");
        foreach (var process in Process.GetProcessesByName("SeJogaCompanion"))
        {
            try
            {
                if (process.SessionId == Process.GetCurrentProcess().SessionId &&
                    String.Equals(process.MainModule.FileName, exe, StringComparison.OrdinalIgnoreCase)) return;
            }
            catch (System.ComponentModel.Win32Exception) { }
            catch (InvalidOperationException) { }
            finally { process.Dispose(); }
        }
        Process.Start(new ProcessStartInfo(exe) { UseShellExecute = true, WorkingDirectory = CurrentDirectory() });
    }

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)] static extern int RmStartSession(out uint handle, int flags, StringBuilder key);
    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)] static extern int RmRegisterResources(uint handle, uint count,
        [MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.LPWStr)] string[] files, uint applications, IntPtr processes, uint services, IntPtr serviceNames);
    [DllImport("rstrtmgr.dll")] static extern int RmShutdown(uint handle, uint flags, IntPtr callback);
    [DllImport("rstrtmgr.dll")] static extern int RmEndSession(uint handle);
    static void CloseApplications(string[] files)
    {
        if (files.Length == 0) return;
        uint handle;
        int result = RmStartSession(out handle, 0, new StringBuilder(33));
        if (result != 0) throw new IOException("Não foi possível iniciar o fechamento seguro do aplicativo: " + result);
        try
        {
            result = RmRegisterResources(handle, (uint)files.Length, files, 0, IntPtr.Zero, 0, IntPtr.Zero);
            if (result == 0) result = RmShutdown(handle, 0, IntPtr.Zero);
            if (result != 0) throw new IOException("Feche o Mário em todas as sessões antes de atualizar. Código: " + result);
        }
        finally { RmEndSession(handle); }
    }

    sealed class ProgressForm : Form
    {
        public Label Status = new Label { AutoSize = false, Dock = DockStyle.Top, Height = 58, Text = "Preparando atualização…" };
        public ProgressBar Progress = new ProgressBar { Dock = DockStyle.Bottom, Height = 22 };
        public Button CancelButtonControl = new Button { Text = "Cancelar", Dock = DockStyle.Bottom, Height = 28 };
        public bool Finished;
        public ProgressForm()
        {
            Text = "SeJoga Companion — Atualizações";
            Size = new Size(460, 210); Padding = new Padding(18);
            StartPosition = FormStartPosition.CenterScreen;
            if (Quiet) { ShowInTaskbar = false; Opacity = 0; }
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false;
            Controls.Add(Status); Controls.Add(Progress); Controls.Add(CancelButtonControl);
            CancelButtonControl.Click += delegate { Close(); };
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
            FormClosing += delegate(object sender, FormClosingEventArgs e)
            {
                if (!Finished) { e.Cancel = true; if (!Committing) { CancelRequested = true; Status.Text = "Cancelando…"; } }
            };
        }
    }
}
