#if ANDROID
using Android.Content;
using Android.Net;
#endif

namespace KerryInternetMonitor.Services
{
    /// <summary>
    /// Heuristic VPN detection. On Android it reports whether the active network
    /// is carried over a VPN transport. On other platforms it always reports
    /// "no VPN" (parity with the Python original, which was Windows-only and
    /// deliberately dropped the portal-IP check because it false-positives
    /// whenever the host is not on the captive-portal subnet, e.g. off-ferry).
    /// </summary>
    public static class VpnDetector
    {
        // portalHost is accepted for call-site compatibility but intentionally
        // unused: resolving it and inspecting the IP produced false positives
        // any time the app ran off the captive portal.
        public static (bool IsVpn, string? Reason) Check(string? portalHost = null)
        {
#if ANDROID
            try
            {
                return CheckAndroid();
            }
            catch
            {
                return (false, null);
            }
#else
            return (false, null);
#endif
        }

#if ANDROID
        private static (bool IsVpn, string? Reason) CheckAndroid()
        {
            var ctx = Android.App.Application.Context;
            if (ctx?.GetSystemService(Context.ConnectivityService) is not ConnectivityManager cm)
                return (false, null);

            // Only inspect the active (default) network. A VPN that is actually
            // routing traffic becomes the default network; enumerating every
            // known network (GetAllNetworks) also surfaces idle/always-on VPN
            // networks that aren't carrying traffic, which false-positives.
            Network? active = cm.ActiveNetwork;
            if (active == null) return (false, null);

            NetworkCapabilities? caps = cm.GetNetworkCapabilities(active);
            if (caps == null) return (false, null);

            if (caps.HasTransport(TransportType.Vpn))
                return (true, "Android VPN transport is active");

            return (false, null);
        }
#endif
    }
}
