using System.Diagnostics;
using System.Globalization;
using System.Net.Sockets;
using KerryInternetMonitor.Models;

#if ANDROID
using Android.Content;
using Android.Net;
#endif

namespace KerryInternetMonitor.Services
{
    /// <summary>
    /// Background TCP-connect probe to the captive portal. Mirrors the Python
    /// NetworkQualityLogger: samples avg / min / max / jitter / loss every
    /// `IntervalSeconds`, writes a CSV row, and fires <see cref="OnUpdate"/>.
    /// Pauses while a VPN is detected (writes nothing, fires OnUpdate(null)).
    /// </summary>
    public class NetworkQualityLogger
    {
        public string Host { get; }
        public int Port { get; }
        public string CsvPath { get; }
        public int IntervalSeconds { get; }
        public int SamplesPerCycle { get; }
        public TimeSpan ConnectTimeout { get; }

        public NetworkQualityRecord? LastRecord { get; private set; }
        public string? VpnReason { get; private set; }

        public event EventHandler<NetworkQualityRecord?>? OnUpdate;

        private CancellationTokenSource? _cts;
        private Task? _runTask;

        public NetworkQualityLogger(string host, int port, string csvPath,
            int intervalSeconds = 120, int samplesPerCycle = 4, double timeoutSeconds = 8.0)
        {
            Host = host;
            Port = port;
            CsvPath = csvPath;
            IntervalSeconds = intervalSeconds;
            SamplesPerCycle = samplesPerCycle;
            ConnectTimeout = TimeSpan.FromSeconds(timeoutSeconds);
        }

        public bool IsRunning => _runTask != null && !_runTask.IsCompleted;

        public void Start()
        {
            if (IsRunning) return;
            _cts = new CancellationTokenSource();
            _runTask = Task.Run(() => RunAsync(_cts.Token));
        }

        public void Stop()
        {
            try { _cts?.Cancel(); } catch { }
        }

        private async Task RunAsync(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                var (vpn, reason) = VpnDetector.Check(Host);
                VpnReason = vpn ? reason : null;
                if (vpn)
                {
                    try { OnUpdate?.Invoke(this, null); } catch { }
                    try { await Task.Delay(TimeSpan.FromSeconds(IntervalSeconds), ct); } catch { }
                    continue;
                }

                NetworkQualityRecord rec = await MeasureAsync(ct);
                LastRecord = rec;
                try { AppendCsv(rec); }
                catch (Exception ex) { Debug.WriteLine($"NQ csv append error: {ex.Message}"); }

                try { OnUpdate?.Invoke(this, rec); } catch { }
                try { await Task.Delay(TimeSpan.FromSeconds(IntervalSeconds), ct); } catch { }
            }
        }

        private async Task<double?> TcpLatencyAsync(CancellationToken ct)
        {
#if ANDROID
            // On Android the captive-portal host resolves (and is only reachable)
            // over Wi-Fi. When Wi-Fi is unvalidated (captive), Android keeps
            // cellular as the default network, so an unbound socket routes out
            // cellular and can never reach the portal -> 100% loss. Bind the
            // probe to the Wi-Fi network (and resolve DNS on it) when present.
            Network? wifi = GetWifiNetwork();
            if (wifi != null)
                return await TcpLatencyOnNetworkAsync(wifi, ct);
#endif

            var sw = Stopwatch.StartNew();
            try
            {
                using var sock = new TcpClient();
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(ct);
                timeout.CancelAfter(ConnectTimeout);

                Task connect = sock.ConnectAsync(Host, Port);
                Task delay = Task.Delay(ConnectTimeout, timeout.Token);
                Task winner = await Task.WhenAny(connect, delay);
                if (winner == delay && !connect.IsCompleted) return null;
                await connect;
                sw.Stop();
                return sw.Elapsed.TotalMilliseconds;
            }
            catch
            {
                return null;
            }
        }

#if ANDROID
        private static Network? GetWifiNetwork()
        {
            try
            {
                if (Android.App.Application.Context?.GetSystemService(Context.ConnectivityService) is not ConnectivityManager cm)
                    return null;

#pragma warning disable CA1422 // GetAllNetworks() is deprecated in API 31+ but is the cleanest cross-version way to find the Wi-Fi network for a one-shot probe.
                Network[]? networks = cm.GetAllNetworks();
#pragma warning restore CA1422
                if (networks == null) return null;

                foreach (Network net in networks)
                {
                    NetworkCapabilities? caps = cm.GetNetworkCapabilities(net);
                    if (caps != null && caps.HasTransport(TransportType.Wifi))
                        return net;
                }
            }
            catch
            {
            }
            return null;
        }

        private Task<double?> TcpLatencyOnNetworkAsync(Network net, CancellationToken ct)
        {
            // Java socket bound to the Wi-Fi network, with DNS resolved on that
            // same network so captive-portal DNS hijacking is honored.
            return Task.Run<double?>(() =>
            {
                Java.Net.Socket? sock = null;
                var sw = Stopwatch.StartNew();
                try
                {
                    Java.Net.InetAddress[]? addrs = net.GetAllByName(Host);
                    if (addrs == null || addrs.Length == 0) return null;

                    sock = new Java.Net.Socket();
                    net.BindSocket(sock);
                    sock.Connect(new Java.Net.InetSocketAddress(addrs[0], Port), (int)ConnectTimeout.TotalMilliseconds);
                    sw.Stop();
                    return sw.Elapsed.TotalMilliseconds;
                }
                catch
                {
                    return null;
                }
                finally
                {
                    try { sock?.Close(); } catch { }
                    sock?.Dispose();
                }
            }, ct);
        }
#endif

        private async Task<NetworkQualityRecord> MeasureAsync(CancellationToken ct)
        {
            var latencies = new List<double>();
            int failures = 0;

            for (int i = 0; i < SamplesPerCycle; i++)
            {
                if (ct.IsCancellationRequested) break;
                double? ms = await TcpLatencyAsync(ct);
                if (ms.HasValue) latencies.Add(ms.Value);
                else failures++;
                if (i < SamplesPerCycle - 1)
                {
                    try { await Task.Delay(500, ct); } catch { }
                }
            }

            int total = failures + latencies.Count;
            double loss = total > 0 ? (failures / (double)total * 100.0) : 100.0;

            double? avg = null, lmin = null, lmax = null, jitter = null;
            if (latencies.Count > 0)
            {
                avg = latencies.Average();
                lmin = latencies.Min();
                lmax = latencies.Max();
                if (latencies.Count > 1)
                {
                    double mean = avg.Value;
                    double variance = latencies.Sum(v => (v - mean) * (v - mean)) / latencies.Count;
                    jitter = Math.Sqrt(variance);
                }
                else
                {
                    jitter = 0.0;
                }
            }

            return new NetworkQualityRecord
            {
                Timestamp = DateTime.Now,
                Host = Host,
                Avg = avg,
                Min = lmin,
                Max = lmax,
                Jitter = jitter,
                Loss = loss,
            };
        }

        private void AppendCsv(NetworkQualityRecord r)
        {
            bool exists = File.Exists(CsvPath);
            using var writer = new StreamWriter(CsvPath, append: true);
            if (!exists)
            {
                writer.WriteLine("Timestamp,Host,LatencyAvg(ms),LatencyMin(ms),LatencyMax(ms),Jitter(ms),Loss(%)");
            }
            string Fmt(double? v) => v.HasValue ? v.Value.ToString("F1", CultureInfo.InvariantCulture) : string.Empty;
            writer.WriteLine(string.Join(",",
                r.Timestamp.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture),
                r.Host,
                Fmt(r.Avg), Fmt(r.Min), Fmt(r.Max), Fmt(r.Jitter),
                r.Loss.ToString("F0", CultureInfo.InvariantCulture)));
        }

        public List<NetworkQualityRecord> LoadAll()
        {
            var result = new List<NetworkQualityRecord>();
            if (!File.Exists(CsvPath)) return result;
            try
            {
                using var reader = new StreamReader(CsvPath);
                string? header = reader.ReadLine();
                if (header == null) return result;
                while (!reader.EndOfStream)
                {
                    string? line = reader.ReadLine();
                    if (string.IsNullOrEmpty(line)) continue;
                    string[] parts = line.Split(',');
                    if (parts.Length < 7) continue;
                    if (!DateTime.TryParseExact(parts[0], "yyyy-MM-dd HH:mm:ss",
                        CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTime ts))
                        continue;

                    double? ParseN(string s) => string.IsNullOrEmpty(s)
                        ? (double?)null
                        : (double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out double v) ? v : null);

                    if (!double.TryParse(parts[6], NumberStyles.Float, CultureInfo.InvariantCulture, out double loss))
                        loss = ParseN(parts[2]) == null ? 100.0 : 0.0;

                    result.Add(new NetworkQualityRecord
                    {
                        Timestamp = ts,
                        Host = parts[1],
                        Avg = ParseN(parts[2]),
                        Min = ParseN(parts[3]),
                        Max = ParseN(parts[4]),
                        Jitter = ParseN(parts[5]) ?? 0.0,
                        Loss = loss,
                    });
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"NQ load error: {ex.Message}");
            }
            return result;
        }
    }
}
