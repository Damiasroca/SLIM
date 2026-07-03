using System.Diagnostics;
using System.Net;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace KerryInternetMonitor.Services
{
    public class StenaConnectionService
    {
        private readonly HttpClient _httpClient;
        private readonly CookieContainer _cookies;
        private readonly string _apiUrl = "https://internet.stenaline.com/portal_api.php";

        // Debug logging - writes to logcat on Android, Debug output on Windows
        private static void Log(string message)
        {
            string msg = $"[SLIM] {message}";
            Debug.WriteLine(msg);
            Console.WriteLine(msg);  // Also to console for adb logcat
        }

        private string DumpCookies(Uri uri)
        {
            var cookies = _cookies.GetCookies(uri);
            if (cookies.Count == 0) return "(none)";
            var sb = new StringBuilder();
            foreach (Cookie c in cookies)
            {
                sb.Append($"{c.Name}={c.Value?.Substring(0, Math.Min(c.Value?.Length ?? 0, 12))}... ");
            }
            return sb.ToString().TrimEnd();
        }

        private static string DumpSetCookieHeaders(HttpResponseMessage resp)
        {
            if (!resp.Headers.TryGetValues("Set-Cookie", out var values))
                return "(none)";
            return string.Join(" | ", values.Select(v => v.Length > 60 ? v.Substring(0, 60) + "..." : v));
        }

        // Landing page used to replicate the UCOPIA captive-portal handshake.
        private const string PortalLandingUrl = "https://internet.stenaline.com/";

        // Retry tuning for the slow authenticate/disconnect round-trip to the ship
        // gateway (high-latency satellite link).
        private const int PortalPostAttempts = 4;
        // Cold start needs at least two GETs (degraded sets the cookie, then the
        // zoned /<zone>/portal/ loads); extra margin covers a dropped SYN.
        private const int PortalHandshakeAttempts = 3;
        // Max Location hops we follow per handshake attempt. UCOPIA typically
        // does 1-2 (`/` -> `portal_degraded.php` -> `/<zone>/portal/`); 6 is a
        // safe ceiling that also traps redirect loops.
        private const int PortalRedirectHops = 6;
        private static readonly TimeSpan PortalRequestTimeout = TimeSpan.FromSeconds(30);

        private bool _portalSessionReady;

        public string PortalHost { get; } = "internet.stenaline.com";
        public string? PortalSiteId { get; private set; }
        public string? PortalUrl { get; private set; }

        public StenaConnectionService()
        {
            _cookies = new CookieContainer();
            // AllowAutoRedirect is OFF on purpose. On Android the default
            // HttpClientHandler is AndroidMessageHandler, which (when auto-
            // following redirects) drops Set-Cookie headers coming from
            // intermediate 302 responses (dotnet/android#5587). UCOPIA rotates
            // PHPSESSID on nearly every hop, so losing those cookies leaves
            // the session unbound and portal_api.php then serves the login
            // HTML instead of JSON ("session not bound") on every call after
            // the first. Following redirects by hand below lets every hop's
            // Set-Cookie land in CookieContainer, matching how
            // requests.Session() behaves in the Python client.
            HttpClientHandler handler = new HttpClientHandler
            {
                CookieContainer = _cookies,
                UseCookies = true,
                AllowAutoRedirect = false,
                ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true
            };

            _httpClient = new HttpClient(handler);
            _httpClient.DefaultRequestHeaders.Add("User-Agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1");
            _httpClient.DefaultRequestHeaders.Add("X-Requested-With", "XMLHttpRequest");
            _httpClient.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
        }

        /// <summary>
        /// Expire every cookie we hold for the portal host. Called before a
        /// forced re-handshake after we detect an unbound session, so a
        /// stale/rotated PHPSESSID can't leak into the retry -- which is what
        /// used to make the Android app require an app restart to recover.
        /// </summary>
        private void ClearPortalCookies()
        {
            var uri = new Uri(PortalLandingUrl);
            var cookies = _cookies.GetCookies(uri);
            Log($"ClearPortalCookies: expiring {cookies.Count} cookies");
            foreach (Cookie c in cookies)
            {
                Log($"  Expiring: {c.Name}={c.Value?.Substring(0, Math.Min(c.Value?.Length ?? 0, 12))}...");
                c.Expired = true;
            }
        }

        /// <summary>
        /// Response is "unbound" if the portal is telling us to log in again:
        /// either a 3xx to the portal page (session lost) or a 200 with the
        /// portal HTML body (Ucopia's other way of saying the same thing).
        /// </summary>
        private static bool IsUnboundResponse(HttpResponseMessage response, string body)
        {
            int code = (int)response.StatusCode;
            if (code >= 300 && code < 400) return true;
            return LooksLikeHtml(response, body);
        }

        /// <summary>
        /// Replicate the UCOPIA captive-portal handshake before authenticating.
        ///
        /// Cold start is a two-step on UCOPIA:
        ///   1. First hit (no cookie) lands on `portal_degraded.php`, whose only
        ///      useful effect is setting PHPSESSID.
        ///   2. The next hit, reusing that cookie, resolves to
        ///      `https://internet.stenaline.com/&lt;zone&gt;/portal/` -- the zoned
        ///      session that `authenticate` can actually attach to.
        /// A POST issued while still in the degraded/unzoned state gets the portal
        /// HTML back ("not connected"), so we loop the GET until it reaches
        /// `/&lt;zone&gt;/portal/`. Safe to call repeatedly.
        /// </summary>
        public async Task<bool> EnsurePortalSessionAsync(bool force = false)
        {
            Log($"EnsurePortalSessionAsync(force={force}), _portalSessionReady={_portalSessionReady}");
            
            if (_portalSessionReady && !force)
            {
                Log("  -> already ready, returning true");
                return true;
            }

            _portalSessionReady = false;
            for (int i = 0; i < PortalHandshakeAttempts; i++)
            {
                Log($"  Handshake attempt {i + 1}/{PortalHandshakeAttempts}");
                try
                {
                    Uri current = new Uri(PortalLandingUrl);
                    for (int hop = 0; hop < PortalRedirectHops; hop++)
                    {
                        Log($"    Hop {hop}: GET {current}");
                        Log($"    Cookies being sent: {DumpCookies(current)}");
                        
                        using var cts = new CancellationTokenSource(PortalRequestTimeout);
                        using HttpResponseMessage resp = await _httpClient.GetAsync(current, cts.Token);
                        PortalUrl = current.ToString();

                        int code = (int)resp.StatusCode;
                        Log($"    Response: {code} {resp.ReasonPhrase}");
                        Log($"    Set-Cookie: {DumpSetCookieHeaders(resp)}");
                        Log($"    Cookies after response: {DumpCookies(current)}");
                        
                        if (code >= 300 && code < 400 && resp.Headers.Location != null)
                        {
                            Uri nextUri = resp.Headers.Location.IsAbsoluteUri
                                ? resp.Headers.Location
                                : new Uri(current, resp.Headers.Location);
                            Log($"    -> Redirect to: {nextUri}");
                            current = nextUri;
                            continue;
                        }

                        Match match = Regex.Match(current.ToString(), @"/(\d+)/portal/");
                        if (match.Success)
                        {
                            PortalSiteId = match.Groups[1].Value;
                            _portalSessionReady = true;
                            Log($"    -> SUCCESS: Reached zoned portal, siteId={PortalSiteId}");
                            return true;
                        }
                        
                        Log($"    -> Non-redirect, non-zoned page. Breaking to retry.");
                        break;
                    }
                }
                catch (Exception ex) when (ex is HttpRequestException || ex is TaskCanceledException || ex is OperationCanceledException)
                {
                    Log($"    -> Exception: {ex.GetType().Name}: {ex.Message}");
                }
            }

            Log("  -> FAILED: Could not establish portal session");
            return false;
        }

        /// <summary>
        /// POST to portal_api.php with timeouts, retry and backoff. The
        /// authenticate/disconnect actions trigger a slow backend round-trip to
        /// the ship gateway, so a single attempt often times out even when the
        /// change took effect. Returns (response, body, error); response is null
        /// on total failure. Content is rebuilt each attempt because
        /// FormUrlEncodedContent is single-use.
        /// </summary>
        private async Task<(HttpResponseMessage? Response, string Body, Exception? Error)> PortalPostWithRetryAsync(
            KeyValuePair<string, string>[] fields, int attempts = PortalPostAttempts)
        {
            string action = fields.FirstOrDefault(f => f.Key == "action").Value ?? "unknown";
            Log($"PortalPostWithRetryAsync: action={action}, attempts={attempts}");
            
            Exception? lastErr = null;
            for (int i = 0; i < attempts; i++)
            {
                try
                {
                    var apiUri = new Uri(_apiUrl);
                    Log($"  POST attempt {i + 1}/{attempts} to {_apiUrl}");
                    Log($"  Cookies being sent: {DumpCookies(apiUri)}");
                    
                    using var cts = new CancellationTokenSource(PortalRequestTimeout);
                    using var content = new FormUrlEncodedContent(fields);
                    HttpResponseMessage resp = await _httpClient.PostAsync(_apiUrl, content, cts.Token);
                    string body = await resp.Content.ReadAsStringAsync();
                    
                    string contentType = resp.Content.Headers.ContentType?.MediaType ?? "(none)";
                    Log($"  Response: {(int)resp.StatusCode} {resp.ReasonPhrase}, Content-Type: {contentType}, Body length: {body.Length}");
                    Log($"  Set-Cookie: {DumpSetCookieHeaders(resp)}");
                    
                    bool looksHtml = LooksLikeHtml(resp, body);
                    bool isUnbound = IsUnboundResponse(resp, body);
                    Log($"  LooksLikeHtml={looksHtml}, IsUnboundResponse={isUnbound}");
                    
                    if (body.Length > 0 && body.Length < 500)
                        Log($"  Body: {body}");
                    else if (body.Length >= 500)
                        Log($"  Body (first 500): {body.Substring(0, 500)}...");
                    
                    return (resp, body, null);
                }
                catch (Exception ex) when (ex is HttpRequestException || ex is TaskCanceledException || ex is OperationCanceledException)
                {
                    lastErr = ex;
                    int backoff = (int)Math.Min(Math.Pow(2, i), 8);
                    Log($"  Attempt {i + 1} failed: {ex.GetType().Name}: {ex.Message}, backoff={backoff}s");
                    await Task.Delay(TimeSpan.FromSeconds(backoff));
                }
            }
            Log($"  -> All attempts failed");
            return (null, string.Empty, lastErr);
        }

        private static bool LooksLikeHtml(HttpResponseMessage response, string body)
        {
            // IMPORTANT: The Stena portal often returns valid JSON with
            // Content-Type: text/html. We must check the actual body content,
            // not trust the Content-Type header. If body starts with '{' or '['
            // it's JSON, not HTML.
            string trimmed = body.TrimStart();
            if (trimmed.StartsWith("{") || trimmed.StartsWith("["))
            {
                return false;  // It's JSON, not HTML
            }
            
            // Only now check for actual HTML markers
            if (trimmed.StartsWith("<!doctype", StringComparison.OrdinalIgnoreCase)
                || trimmed.StartsWith("<html", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
            
            // As a fallback, if Content-Type says HTML and body doesn't look like JSON
            string contentType = response.Content.Headers.ContentType?.MediaType ?? string.Empty;
            return contentType.Contains("html", StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// Lightweight `init` call used to verify state after a timeout. Returns
        /// the connected state document when isConnected, otherwise null (never
        /// throws).
        /// </summary>
        private async Task<JsonDocument?> TryGetConnectedStateAsync()
        {
            try
            {
                var fields = new[]
                {
                    new KeyValuePair<string, string>("action", "init"),
                    new KeyValuePair<string, string>("free_urls", "")
                };
                using var cts = new CancellationTokenSource(PortalRequestTimeout);
                using var content = new FormUrlEncodedContent(fields);
                using HttpResponseMessage resp = await _httpClient.PostAsync(_apiUrl, content, cts.Token);
                string body = await resp.Content.ReadAsStringAsync();
                if (string.IsNullOrEmpty(body) || IsUnboundResponse(resp, body))
                {
                    return null;
                }

                JsonDocument doc = JsonDocument.Parse(body);
                JsonElement root = doc.RootElement;
                bool connected = root.TryGetProperty("step", out JsonElement step)
                    && step.GetString() == "FEEDBACK"
                    && root.TryGetProperty("user", out JsonElement user)
                    && user.TryGetProperty("isConnected", out JsonElement isConnected)
                    && isConnected.ValueKind == JsonValueKind.True;
                if (connected)
                {
                    return doc;
                }
                doc.Dispose();
                return null;
            }
            catch
            {
                return null;
            }
        }

        public async Task<JsonDocument> InitAsync()
        {
            try
            {
                // Establish the captive-portal session first so `init` is bound to
                // this device (matches the browser flow).
                await EnsurePortalSessionAsync();

                var fields = new[]
                {
                    new KeyValuePair<string, string>("action", "init"),
                    new KeyValuePair<string, string>("free_urls", "")
                };

                using var cts = new CancellationTokenSource(PortalRequestTimeout);
                using var content = new FormUrlEncodedContent(fields);
                using HttpResponseMessage response = await _httpClient.PostAsync(_apiUrl, content, cts.Token);
                string responseData = await response.Content.ReadAsStringAsync();

                if (IsUnboundResponse(response, responseData))
                {
                    // Portal handed us the login page (as HTML or a 302).
                    // The caller (CheckConnectionStatusAsync) treats an
                    // exception as "not connected", which is correct here.
                    throw new Exception("Portal session not bound");
                }

                if (!string.IsNullOrEmpty(responseData))
                {
                    return JsonDocument.Parse(responseData);
                }

                throw new Exception("Empty response from server");
            }
            catch (HttpRequestException ex)
            {
                throw new Exception($"Network error: {ex.Message}", ex);
            }
            catch (JsonException ex)
            {
                throw new Exception($"Invalid JSON response: {ex.Message}", ex);
            }
            catch (Exception ex)
            {
                throw new Exception($"Init error: {ex.Message}", ex);
            }
        }

        public async Task<JsonDocument> AuthenticateAsync(string username, string password)
        {
            Log($"========== AuthenticateAsync START for user={username} ==========");
            try
            {
                var fields = new[]
                {
                    new KeyValuePair<string, string>("action", "authenticate"),
                    new KeyValuePair<string, string>("switch_package", "true"),
                    new KeyValuePair<string, string>("login", username),
                    new KeyValuePair<string, string>("password", password),
                    new KeyValuePair<string, string>("policy_accept", "true"),
                    new KeyValuePair<string, string>("private_policy_accept", "false"),
                    new KeyValuePair<string, string>("from_ajax", "true"),
                    new KeyValuePair<string, string>("wispr_mode", "false")
                };

                Log("Step 1: EnsurePortalSessionAsync(force=true)");
                await EnsurePortalSessionAsync(force: true);

                Log("Step 2: First PortalPostWithRetryAsync (authenticate)");
                var (response, body, error) = await PortalPostWithRetryAsync(fields);

                if (response == null)
                {
                    Log("Step 2 result: response is NULL (all attempts failed)");
                    Log("Step 3: TryGetConnectedStateAsync to verify");
                    JsonDocument? verified = await TryGetConnectedStateAsync();
                    if (verified != null)
                    {
                        Log("  -> Verified connected despite timeout, returning success");
                        return verified;
                    }
                    Log("  -> Not verified, throwing");
                    throw error ?? new Exception("Authentication failed after retries");
                }

                Log($"Step 2 result: got response, IsUnboundResponse={IsUnboundResponse(response, body)}");
                
                if (IsUnboundResponse(response, body))
                {
                    Log("Step 3: Response is UNBOUND, clearing cookies and retrying");
                    ClearPortalCookies();
                    
                    Log("Step 4: EnsurePortalSessionAsync(force=true) again");
                    await EnsurePortalSessionAsync(force: true);
                    
                    Log("Step 5: Retry PortalPostWithRetryAsync (authenticate)");
                    var (retryResponse, retryBody, _) = await PortalPostWithRetryAsync(fields);
                    if (retryResponse != null)
                    {
                        response = retryResponse;
                        body = retryBody;
                        Log($"Step 5 result: got retry response, IsUnboundResponse={IsUnboundResponse(response, body)}");
                    }
                    else
                    {
                        Log("Step 5 result: retry response is NULL");
                    }
                }

                if (IsUnboundResponse(response, body))
                {
                    Log("Still UNBOUND after retry, trying TryGetConnectedStateAsync");
                    JsonDocument? verified = await TryGetConnectedStateAsync();
                    if (verified != null)
                    {
                        Log("  -> Verified connected, returning success");
                        return verified;
                    }
                    Log("  -> Not verified, throwing 'session not bound'");
                    throw new Exception("Portal returned HTML instead of JSON (session not bound)");
                }

                if (string.IsNullOrEmpty(body))
                {
                    Log("Body is empty, throwing");
                    throw new Exception("Empty response from server");
                }

                Log("SUCCESS: Parsing JSON response");
                Log($"========== AuthenticateAsync END (success) ==========");
                return JsonDocument.Parse(body);
            }
            catch (HttpRequestException ex)
            {
                Log($"========== AuthenticateAsync END (HttpRequestException: {ex.Message}) ==========");
                throw new Exception($"Network error: {ex.Message}", ex);
            }
            catch (JsonException ex)
            {
                Log($"========== AuthenticateAsync END (JsonException: {ex.Message}) ==========");
                throw new Exception($"Invalid JSON response: {ex.Message}", ex);
            }
            catch (Exception ex)
            {
                Log($"========== AuthenticateAsync END (Exception: {ex.Message}) ==========");
                throw new Exception($"Authentication error: {ex.Message}", ex);
            }
        }

        public async Task<JsonDocument> DisconnectAsync(string username)
        {
            try
            {
                var fields = new[]
                {
                    new KeyValuePair<string, string>("action", "disconnect"),
                    new KeyValuePair<string, string>("login", username)
                };

                // Same UCOPIA requirement as authenticate: a fresh GET to
                // /<zone>/portal/ must immediately precede the action.
                await EnsurePortalSessionAsync(force: true);

                var (response, body, error) = await PortalPostWithRetryAsync(fields);

                if (response == null)
                {
                    // All attempts timed out. The disconnect may still have
                    // applied, so verify via init before failing.
                    JsonDocument? verified = await TryGetConnectedStateAsync();
                    if (verified == null)
                    {
                        // No connected session found -> treat as disconnected.
                        return JsonDocument.Parse("{\"info\":{\"code\":\"disconnect_success\"}}");
                    }
                    verified.Dispose();
                    throw error ?? new Exception("Disconnect failed after retries");
                }

                if (IsUnboundResponse(response, body))
                {
                    ClearPortalCookies();
                    await EnsurePortalSessionAsync(force: true);
                    var (retryResponse, retryBody, _) = await PortalPostWithRetryAsync(fields);
                    if (retryResponse != null)
                    {
                        response = retryResponse;
                        body = retryBody;
                    }
                }

                // Check unbound before empty: a 302 legitimately has no body.
                if (IsUnboundResponse(response, body))
                {
                    // Still unbound -> verify whether the disconnect actually applied.
                    JsonDocument? verified = await TryGetConnectedStateAsync();
                    if (verified == null)
                    {
                        return JsonDocument.Parse("{\"info\":{\"code\":\"disconnect_success\"}}");
                    }
                    verified.Dispose();
                    throw new Exception("Portal returned HTML instead of JSON (session not bound)");
                }

                if (string.IsNullOrEmpty(body))
                {
                    throw new Exception("Empty response from server");
                }

                return JsonDocument.Parse(body);
            }
            catch (HttpRequestException ex)
            {
                throw new Exception($"Network error: {ex.Message}", ex);
            }
            catch (JsonException ex)
            {
                throw new Exception($"Invalid JSON response: {ex.Message}", ex);
            }
            catch (Exception ex)
            {
                throw new Exception($"Disconnect error: {ex.Message}", ex);
            }
        }
    }
}
