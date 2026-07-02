using Microsoft.Extensions.Logging;
using KerryInternetMonitor.Services;

namespace KerryInternetMonitor;

public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        var builder = MauiApp.CreateBuilder();
        builder
            .UseMauiApp<App>()
            .ConfigureFonts(fonts =>
            {
                fonts.AddFont("StenaSans-Medium.ttf", "StenaSansMedium");
                fonts.AddFont("StenaSans-Bold.ttf", "StenaSansBold");
            });

        // Register services
        builder.Services.AddSingleton<ThemeService>();
        builder.Services.AddSingleton<StenaConnectionService>();
        builder.Services.AddSingleton<DataStorageService>();
        builder.Services.AddSingleton<IpInfoService>();
        builder.Services.AddSingleton<NetworkQualityLogger>(sp =>
        {
            var conn = sp.GetRequiredService<StenaConnectionService>();
            var storage = sp.GetRequiredService<DataStorageService>();
            return new NetworkQualityLogger(conn.PortalHost, 443, storage.NetworkQualityCsvPath);
        });

        // Register pages
        builder.Services.AddTransient<MainPage>();

#if DEBUG
        builder.Logging.AddDebug();
#endif

        return builder.Build();
    }
}
