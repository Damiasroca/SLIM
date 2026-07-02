using System.Globalization;
using System.Net;
using System.Text.Json;
using KerryInternetMonitor.Models;

namespace KerryInternetMonitor.Services
{
    /// <summary>
    /// Looks up the user's external IP via ipapi.co, falling back to ipwho.is.
    /// Mirrors the Python IPInfoPanel data normalization.
    /// </summary>
    public class IpInfoService
    {
        private const string PrimaryUrl = "https://ipapi.co/json/";
        private const string FallbackUrl = "https://ipwho.is/";

        private readonly HttpClient _http;

        public IpInfoService()
        {
            _http = new HttpClient
            {
                Timeout = TimeSpan.FromSeconds(10),
            };
            _http.DefaultRequestHeaders.UserAgent.ParseAdd("SLIM/IPInfo");
        }

        public async Task<IpInfo> FetchAsync(CancellationToken ct = default)
        {
            string? lastErr = null;
            try
            {
                using var resp = await _http.GetAsync(PrimaryUrl, ct);
                if (resp.IsSuccessStatusCode)
                {
                    string body = await resp.Content.ReadAsStringAsync(ct);
                    using var doc = JsonDocument.Parse(body);
                    JsonElement root = doc.RootElement;
                    if (!root.TryGetProperty("error", out _))
                    {
                        return NormalizeIpapi(root);
                    }
                    if (root.TryGetProperty("reason", out JsonElement r))
                        lastErr = r.GetString();
                }
                else
                {
                    lastErr = $"HTTP {(int)resp.StatusCode}";
                }
            }
            catch (Exception ex)
            {
                lastErr = ex.Message;
            }

            try
            {
                using var resp = await _http.GetAsync(FallbackUrl, ct);
                resp.EnsureSuccessStatusCode();
                string body = await resp.Content.ReadAsStringAsync(ct);
                using var doc = JsonDocument.Parse(body);
                JsonElement root = doc.RootElement;
                if (root.TryGetProperty("success", out JsonElement s) &&
                    s.ValueKind == JsonValueKind.False)
                {
                    string msg = root.TryGetProperty("message", out JsonElement m)
                        ? (m.GetString() ?? "Lookup failed")
                        : "Lookup failed";
                    throw new InvalidOperationException(msg);
                }
                return NormalizeIpwhois(root);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(lastErr ?? ex.Message, ex);
            }
        }

        public static async Task<string?> ReverseDnsAsync(string ip, CancellationToken ct = default)
        {
            try
            {
                IPHostEntry entry = await Dns.GetHostEntryAsync(ip, ct);
                return entry.HostName;
            }
            catch
            {
                return null;
            }
        }

        private static IpInfo NormalizeIpapi(JsonElement d)
        {
            return new IpInfo
            {
                Source = "ipapi.co",
                Ip = GetString(d, "ip"),
                Version = GetString(d, "version"),
                Hostname = GetString(d, "hostname"),
                City = GetString(d, "city"),
                Region = GetString(d, "region"),
                Country = GetString(d, "country_name"),
                CountryCode = GetString(d, "country_code"),
                Postal = GetString(d, "postal"),
                Latitude = GetDouble(d, "latitude"),
                Longitude = GetDouble(d, "longitude"),
                Timezone = GetString(d, "timezone"),
                UtcOffset = GetString(d, "utc_offset"),
                CallingCode = GetString(d, "country_calling_code"),
                Currency = GetString(d, "currency"),
                CurrencyName = GetString(d, "currency_name"),
                Languages = GetString(d, "languages"),
                Asn = GetString(d, "asn"),
                Org = GetString(d, "org"),
            };
        }

        private static IpInfo NormalizeIpwhois(JsonElement d)
        {
            JsonElement conn = d.TryGetProperty("connection", out JsonElement c) ? c : default;
            JsonElement tz = d.TryGetProperty("timezone", out JsonElement t) ? t : default;
            JsonElement cur = d.TryGetProperty("currency", out JsonElement cu) ? cu : default;
            string? asnNum = conn.ValueKind == JsonValueKind.Object ? GetString(conn, "asn") : null;
            return new IpInfo
            {
                Source = "ipwho.is",
                Ip = GetString(d, "ip"),
                Version = GetString(d, "type"),
                Hostname = null,
                City = GetString(d, "city"),
                Region = GetString(d, "region"),
                Country = GetString(d, "country"),
                CountryCode = GetString(d, "country_code"),
                Postal = GetString(d, "postal"),
                Latitude = GetDouble(d, "latitude"),
                Longitude = GetDouble(d, "longitude"),
                Timezone = tz.ValueKind == JsonValueKind.Object ? GetString(tz, "id") : null,
                UtcOffset = tz.ValueKind == JsonValueKind.Object ? GetString(tz, "utc") : null,
                CallingCode = GetString(d, "calling_code"),
                Currency = cur.ValueKind == JsonValueKind.Object ? GetString(cur, "code") : null,
                CurrencyName = cur.ValueKind == JsonValueKind.Object ? GetString(cur, "name") : null,
                Languages = null,
                Asn = !string.IsNullOrEmpty(asnNum) ? $"AS{asnNum}" : null,
                Org = conn.ValueKind == JsonValueKind.Object
                    ? (GetString(conn, "isp") ?? GetString(conn, "org"))
                    : null,
            };
        }

        private static string? GetString(JsonElement el, string name)
        {
            if (el.ValueKind != JsonValueKind.Object) return null;
            if (!el.TryGetProperty(name, out JsonElement v)) return null;
            return v.ValueKind switch
            {
                JsonValueKind.String => v.GetString(),
                JsonValueKind.Number => v.GetRawText(),
                JsonValueKind.True => "true",
                JsonValueKind.False => "false",
                JsonValueKind.Null => null,
                _ => null,
            };
        }

        private static double? GetDouble(JsonElement el, string name)
        {
            if (el.ValueKind != JsonValueKind.Object) return null;
            if (!el.TryGetProperty(name, out JsonElement v)) return null;
            if (v.ValueKind == JsonValueKind.Number && v.TryGetDouble(out double d)) return d;
            if (v.ValueKind == JsonValueKind.String &&
                double.TryParse(v.GetString(), NumberStyles.Float, CultureInfo.InvariantCulture, out double ds))
                return ds;
            return null;
        }
    }
}
