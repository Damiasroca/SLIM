using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using Microsoft.Maui.Controls;
using Microsoft.Maui.Devices;
using KerryInternetMonitor.Models;
using KerryInternetMonitor.Services;
using KerryInternetMonitor.Views;

namespace KerryInternetMonitor;

public partial class MainPage : ContentPage
{
    public const string AppVersion = "1.1.0";

    private readonly StenaConnectionService _connectionService;
    private readonly DataStorageService _storageService;
    private readonly ThemeService _themeService;
    private readonly NetworkQualityLogger _qualityLogger;
    private readonly IpInfoService _ipInfoService;

    private Dictionary<string, UserProfile> _profiles = new();
    private JsonElement? _currentData;

    private readonly QuotaGaugeDrawable _gaugeDrawable;
    private readonly HeatmapDrawable _heatmapDrawable;
    private readonly ProbeChartDrawable _chartDrawable;

    private IpInfo? _ipInfo;
    private bool _ipInfoLoading;
    private string? _vpnDismissedReason;

    private enum Tab { Usage, Quality, IpInfo }
    private Tab _currentTab = Tab.Usage;

    public MainPage(StenaConnectionService connectionService,
                    DataStorageService storageService,
                    ThemeService themeService,
                    NetworkQualityLogger qualityLogger,
                    IpInfoService ipInfoService)
    {
        InitializeComponent();

        _connectionService = connectionService;
        _storageService = storageService;
        _themeService = themeService;
        _qualityLogger = qualityLogger;
        _ipInfoService = ipInfoService;

        _gaugeDrawable = new QuotaGaugeDrawable(_themeService);
        _heatmapDrawable = new HeatmapDrawable(_themeService);
        _chartDrawable = new ProbeChartDrawable(_themeService);

        QuotaGaugeView.Drawable = _gaugeDrawable;
        HeatmapView.Drawable = _heatmapDrawable;
        ProbeChartView.Drawable = _chartDrawable;

        _themeService.ThemeChanged += OnThemeChanged;
        _qualityLogger.OnUpdate += OnQualityUpdate;

#if ANDROID
        FlushDnsBtn.IsVisible = false;
#endif

        LoadProfilesAsync();
        ApplyTheme();
        DisplayWelcomeMessage();
        SelectTab(Tab.Usage);
        _qualityLogger.Start();
        ReloadQualityVisuals();
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await Task.Delay(500);
        await CheckConnectionStatusAsync();
        await Task.Delay(300);
        if (_ipInfo == null && !_ipInfoLoading)
        {
            _ = RefreshIpInfoAsync();
        }
    }

    private void OnThemeChanged(object? sender, EventArgs e)
    {
        ApplyTheme();
        QuotaGaugeView.Invalidate();
        HeatmapView.Invalidate();
        ProbeChartView.Invalidate();
    }

    private void ApplyTheme()
    {
        Color bgColor = _themeService.GetBackgroundColor();
        Color bgSecondary = _themeService.GetBackgroundSecondaryColor();
        Color bgTertiary = _themeService.GetBackgroundTertiaryColor();
        Color textColor = _themeService.GetTextColor();
        Color textSecondary = _themeService.GetTextSecondaryColor();
        Color accentColor = _themeService.GetAccentColor();
        Color successColor = _themeService.GetSuccessColor();
        Color warningColor = _themeService.GetWarningColor();
        Color errorColor = _themeService.GetErrorColor();
        Color borderColor = _themeService.GetBorderColor();

        MainScrollView.BackgroundColor = bgColor;
        MainLayout.BackgroundColor = bgColor;
        BackgroundColor = bgColor;

        InfoBanner.BackgroundColor = bgTertiary;
        InfoBanner.BorderColor = accentColor;
        InfoLabel.TextColor = textSecondary;

        CredentialsFrame.BackgroundColor = bgSecondary;
        CredentialsFrame.BorderColor = borderColor;
        CredentialsTitle.TextColor = accentColor;
        UsernameLabel.TextColor = textColor;
        PasswordLabel.TextColor = textColor;
        UsernameEntry.BackgroundColor = bgTertiary;
        UsernameEntry.TextColor = textColor;
        UsernameEntry.PlaceholderColor = textSecondary;
        PasswordEntry.BackgroundColor = bgTertiary;
        PasswordEntry.TextColor = textColor;
        PasswordEntry.PlaceholderColor = textSecondary;

        ProfileFrame.BackgroundColor = bgSecondary;
        ProfileFrame.BorderColor = borderColor;
        ProfileTitle.TextColor = accentColor;
        SelectProfileLabel.TextColor = textColor;
        NewProfileLabel.TextColor = textColor;
        ProfilePicker.BackgroundColor = bgTertiary;
        ProfilePicker.TextColor = textColor;
        NewProfileEntry.BackgroundColor = bgTertiary;
        NewProfileEntry.TextColor = textColor;
        NewProfileEntry.PlaceholderColor = textSecondary;

        SaveProfileBtn.BackgroundColor = successColor;
        SaveProfileBtn.TextColor = Colors.White;
        DeleteProfileBtn.BackgroundColor = warningColor;
        DeleteProfileBtn.TextColor = Colors.White;

        FetchBtn.BackgroundColor = accentColor;
        FetchBtn.TextColor = Colors.White;
        SaveHistoryBtn.BackgroundColor = successColor;
        SaveHistoryBtn.TextColor = Colors.White;
        ClearBtn.BackgroundColor = textSecondary;
        ClearBtn.TextColor = Colors.White;
        FlushDnsBtn.BackgroundColor = warningColor;
        FlushDnsBtn.TextColor = Colors.White;
        DisconnectBtn.BackgroundColor = errorColor;
        DisconnectBtn.TextColor = Colors.White;

        UsageTab.BackgroundColor = bgSecondary;
        UsageTab.BorderColor = borderColor;
        UsageTitle.TextColor = accentColor;
        OutputText.TextColor = textColor;
        OutputText.BackgroundColor = bgTertiary;

        QualityTab.BackgroundColor = bgSecondary;
        QualityTab.BorderColor = borderColor;
        QualityDescription.TextColor = textSecondary;
        QualityCurrentLabel.TextColor = textColor;
        QualityHeatmapTitle.TextColor = successColor;
        QualityDetailLabel.TextColor = textSecondary;
        QualityLegendLabel.TextColor = textSecondary;
        QualitySummaryLabel.TextColor = textColor;
        QualityChartTitle.TextColor = successColor;

        IpInfoTab.BackgroundColor = bgSecondary;
        IpInfoTab.BorderColor = borderColor;
        IpInfoTitle.TextColor = accentColor;
        IpInfoText.TextColor = textColor;
        IpInfoText.BackgroundColor = bgTertiary;
        IpInfoRefreshBtn.BackgroundColor = accentColor;
        IpInfoRefreshBtn.TextColor = Colors.White;

        UsageVpnBanner.BackgroundColor = warningColor;
        UsageVpnBanner.BorderColor = warningColor;
        UsageVpnBannerText.TextColor = bgColor;
        UsageVpnBannerClose.TextColor = bgColor;
        QualityVpnBanner.BackgroundColor = warningColor;
        QualityVpnBanner.BorderColor = warningColor;
        QualityVpnBannerText.TextColor = bgColor;
        QualityVpnBannerClose.TextColor = bgColor;

        StatusLabel.TextColor = textSecondary;

        ThemeToggleLabel.Text = _themeService.GetThemeIcon();
        ThemeToggleLabel.TextColor = textSecondary;
        VersionLabel.Text = $"v{AppVersion}";
        VersionLabel.TextColor = textSecondary;
        GitHubLabel.TextColor = accentColor;

        UpdateTabButtonStyles();
    }

    private void UpdateTabButtonStyles()
    {
        Color accent = _themeService.GetAccentColor();
        Color bgSecondary = _themeService.GetBackgroundSecondaryColor();
        Color textSecondary = _themeService.GetTextSecondaryColor();

        var buttons = new (Button btn, Tab t)[]
        {
            (TabUsageBtn, Tab.Usage),
            (TabQualityBtn, Tab.Quality),
            (TabIpBtn, Tab.IpInfo),
        };
        foreach (var (btn, t) in buttons)
        {
            bool active = t == _currentTab;
            btn.BackgroundColor = active ? accent : bgSecondary;
            btn.TextColor = active ? Colors.White : textSecondary;
            btn.FontFamily = active ? "StenaSansBold" : "StenaSansMedium";
        }
    }

    // ===== Tab switching =====
    private void SelectTab(Tab tab)
    {
        _currentTab = tab;
        UsageTab.IsVisible = tab == Tab.Usage;
        QualityTab.IsVisible = tab == Tab.Quality;
        IpInfoTab.IsVisible = tab == Tab.IpInfo;
        UpdateTabButtonStyles();
        if (tab == Tab.Quality)
        {
            ReloadQualityVisuals();
        }
    }

    private void TabUsage_Clicked(object sender, EventArgs e) => SelectTab(Tab.Usage);
    private void TabQuality_Clicked(object sender, EventArgs e) => SelectTab(Tab.Quality);
    private void TabIp_Clicked(object sender, EventArgs e) => SelectTab(Tab.IpInfo);

    // ===== Profile management =====
    private async void LoadProfilesAsync()
    {
        try
        {
            _profiles = await _storageService.LoadProfilesAsync();
            UpdateProfileList();
        }
        catch (Exception ex)
        {
            DisplayError($"Failed to load profiles: {ex.Message}");
        }
    }

    private void UpdateProfileList()
    {
        ProfilePicker.ItemsSource = _profiles.Keys.ToList();
    }

    private void ProfilePicker_SelectedIndexChanged(object sender, EventArgs e)
    {
        string? selectedProfile = ProfilePicker.SelectedItem as string;
        if (!string.IsNullOrEmpty(selectedProfile) && _profiles.TryGetValue(selectedProfile, out UserProfile? profile))
        {
            UsernameEntry.Text = profile.Username;
            PasswordEntry.Text = profile.Password;
            SetStatus($"Loaded profile: {selectedProfile}", StatusType.Success);
        }
    }

    private async void SaveProfile_Clicked(object sender, EventArgs e)
    {
        string? profileName = NewProfileEntry.Text?.Trim();
        if (string.IsNullOrEmpty(profileName))
        {
            await DisplayAlert("Error", "Profile name cannot be empty", "OK");
            return;
        }

        _profiles[profileName] = new UserProfile
        {
            Username = UsernameEntry.Text ?? string.Empty,
            Password = PasswordEntry.Text ?? string.Empty
        };

        try
        {
            await _storageService.SaveProfilesAsync(_profiles);
            UpdateProfileList();
            ProfilePicker.SelectedItem = profileName;
            NewProfileEntry.Text = string.Empty;
            SetStatus($"Profile '{profileName}' saved", StatusType.Success);
        }
        catch (Exception ex)
        {
            await DisplayAlert("Error", $"Failed to save profile: {ex.Message}", "OK");
            SetStatus("Error saving profile", StatusType.Error);
        }
    }

    private async void DeleteProfile_Clicked(object sender, EventArgs e)
    {
        string? selectedProfile = ProfilePicker.SelectedItem as string;
        if (string.IsNullOrEmpty(selectedProfile))
        {
            await DisplayAlert("Error", "No profile selected", "OK");
            return;
        }

        bool confirm = await DisplayAlert("Confirm", $"Delete profile '{selectedProfile}'?", "Yes", "Cancel");
        if (confirm && _profiles.Remove(selectedProfile))
        {
            try
            {
                await _storageService.SaveProfilesAsync(_profiles);
                UpdateProfileList();
                ProfilePicker.SelectedItem = null;
                SetStatus($"Profile '{selectedProfile}' deleted", StatusType.Warning);
            }
            catch (Exception ex)
            {
                await DisplayAlert("Error", $"Failed to delete profile: {ex.Message}", "OK");
                SetStatus("Error deleting profile", StatusType.Error);
            }
        }
    }

    // ===== Connection status check on startup =====
    private async Task CheckConnectionStatusAsync()
    {
        SetStatus("Checking connection status...", StatusType.Info);
        try
        {
            JsonDocument response = await _connectionService.InitAsync();
            JsonElement root = response.RootElement;

            if (root.TryGetProperty("step", out JsonElement stepElement) &&
                stepElement.GetString() == "FEEDBACK" &&
                root.TryGetProperty("user", out JsonElement userElement) &&
                userElement.TryGetProperty("isConnected", out JsonElement isConnectedElement) &&
                isConnectedElement.ValueKind == JsonValueKind.True)
            {
                _currentData = root.Clone();
                DisplayConnectionStatus(root);
            }
            else
            {
                SetStatus("Not connected to network", StatusType.Warning);
                AppendToOutput("\n⚠️ Not currently connected to the network.");
            }
        }
        catch (Exception)
        {
            SetStatus("Not on Stena network", StatusType.Warning);
            AppendToOutput("\n⚠️ Could not connect to Stena network. Make sure you're connected to the ship's WiFi.");
        }
    }

    private void DisplayConnectionStatus(JsonElement data)
    {
        try
        {
            JsonElement user = data.GetProperty("user");
            string username = GetStringValue(user, "login");
            string profile = GetStringValue(user, "profile");

            if (string.IsNullOrEmpty(UsernameEntry.Text))
            {
                UsernameEntry.Text = username;
                PasswordEntry.Text = username;
            }

            ClearOutput();
            StringBuilder output = new();
            output.AppendLine("✓ ALREADY CONNECTED\n");
            output.AppendLine($"Connected as: {username}");
            output.AppendLine($"Profile: {profile}\n");

            if (user.TryGetProperty("consumedData", out JsonElement consumed))
            {
                long downloadBytes = GetLongValue(consumed, "download");
                long uploadBytes = GetLongValue(consumed, "upload");

                output.AppendLine("DATA USAGE");
                output.AppendLine($"Download: {FormatBytes(downloadBytes)}");
                output.AppendLine($"Upload: {FormatBytes(uploadBytes)}");
                output.AppendLine($"Total: {FormatBytes(downloadBytes + uploadBytes)}\n");

                DisplayQuotaInfo(consumed, output);
                DisplayTimeInfo(consumed, output);
            }

            output.AppendLine($"\nLast checked: {DateTime.Now:HH:mm:ss}");
            OutputText.Text = output.ToString();

            SetStatus($"Connected as {username}", StatusType.Success);
        }
        catch (Exception ex)
        {
            DisplayError($"Error displaying connection status: {ex.Message}");
        }
    }

    private void DisplayQuotaInfo(JsonElement consumed, StringBuilder output)
    {
        if (!consumed.TryGetProperty("extra", out JsonElement extraElement) ||
            !extraElement.TryGetProperty("value", out JsonElement extraValue) ||
            extraValue.ValueKind != JsonValueKind.Array)
            return;

        foreach (JsonElement item in extraValue.EnumerateArray())
        {
            bool isSumQuota = item.TryGetProperty("isSumQuota", out JsonElement sq) && IsTrue(sq);
            bool isDisconnectQuota = item.TryGetProperty("isDisconnectQuota", out JsonElement dq) && IsTrue(dq);

            if (isSumQuota && isDisconnectQuota &&
                item.TryGetProperty("total", out JsonElement total) &&
                total.TryGetProperty("upload", out JsonElement totalUpload))
            {
                long totalQuota = GetLongFromElement(totalUpload);
                if (totalQuota <= 0) return;

                if (item.TryGetProperty("available", out JsonElement available) &&
                    available.TryGetProperty("upload", out JsonElement availableUpload))
                {
                    long remaining = GetLongFromElement(availableUpload);
                    long used = totalQuota - remaining;
                    double usagePct = (double)used / totalQuota * 100.0;

                    output.AppendLine("QUOTA");
                    output.AppendLine($"Total Quota: {FormatBytes(totalQuota)}");
                    string usageStatus = usagePct > 80 ? " (HIGH USAGE)" : "";
                    output.AppendLine($"Used: {FormatBytes(used)} ({usagePct:F1}%){usageStatus}");
                    output.AppendLine($"Remaining: {FormatBytes(remaining)}\n");

                    ShowQuotaGauge(used);
                }
                return;
            }
        }
    }

    private void DisplayTimeInfo(JsonElement consumed, StringBuilder output)
    {
        long renewTimestamp = GetLongValue(consumed, "renewTimestamp");
        if (renewTimestamp <= 0) return;

        DateTimeOffset renewTime = DateTimeOffset.FromUnixTimeSeconds(renewTimestamp);
        TimeSpan remaining = renewTime - DateTimeOffset.Now;
        if (remaining.TotalSeconds > 0)
        {
            output.AppendLine("TIME INFO");
            output.AppendLine($"Renewal in: {remaining.Days}d {remaining.Hours}h {remaining.Minutes}m");
        }
    }

    // ===== Fetch / Authenticate =====
    private async void FetchData_Clicked(object sender, EventArgs e)
    {
        string username = UsernameEntry.Text ?? string.Empty;
        string password = PasswordEntry.Text ?? string.Empty;

        if (string.IsNullOrEmpty(username) || string.IsNullOrEmpty(password))
        {
            await DisplayAlert("Error", "Username and password are required", "OK");
            SetStatus("Error: Missing credentials", StatusType.Error);
            return;
        }

        SelectTab(Tab.Usage);
        ClearOutput();
        AppendToOutput("Fetching data... Please wait.");
        SetStatus("Fetching data... Please wait.", StatusType.Info);
        FetchBtn.IsEnabled = false;

        try
        {
            JsonDocument response = await _connectionService.AuthenticateAsync(username, password);
            _currentData = response.RootElement.Clone();
            JsonElement root = response.RootElement;

            if (root.TryGetProperty("user", out JsonElement user) &&
                user.TryGetProperty("consumedData", out _))
            {
                DisplayInfo(root);
                SetStatus("Data fetched successfully", StatusType.Success);
            }
            else if (root.TryGetProperty("error", out JsonElement error) &&
                     error.TryGetProperty("code", out JsonElement code))
            {
                string codeStr = code.GetString() ?? "";
                if (codeStr == "error_logon_volume-quota-reached-detail")
                {
                    DisplayQuotaReachedInfo(root);
                    SetStatus("Quota limit reached", StatusType.Warning);
                }
                else if (codeStr == "error_logon_bad-login-or-password")
                {
                    ClearOutput();
                    DisplayBadCredentials(username);
                    SetStatus("Invalid credentials", StatusType.Error);
                }
                else
                {
                    ClearOutput();
                    DisplayError("Authentication failed or no data returned");
                    SetStatus("Error: Authentication failed", StatusType.Error);
                }
            }
            else if (root.TryGetProperty("errorMsg", out JsonElement errorMsg))
            {
                string errorMessage = errorMsg.GetString() ?? "Authentication failed or no data returned";
                ClearOutput();
                DisplayError($"API Error: {errorMessage}");
                SetStatus("Error: API returned an error", StatusType.Error);
            }
            else
            {
                ClearOutput();
                DisplayError("Authentication failed or no data returned");
                SetStatus("Error: Authentication failed", StatusType.Error);
            }
        }
        catch (HttpRequestException ex)
        {
            ClearOutput();
            DisplayError($"Connection error: {ex.Message}");
            SetStatus("Error: Connection failed", StatusType.Error);
        }
        catch (Exception ex)
        {
            ClearOutput();
            DisplayError($"Error: {ex.Message}");
            SetStatus($"Error: {ex.Message}", StatusType.Error);
        }
        finally
        {
            FetchBtn.IsEnabled = true;
        }
    }

    // ===== Disconnect =====
    private async void Disconnect_Clicked(object sender, EventArgs e)
    {
        string username = UsernameEntry.Text ?? string.Empty;
        if (string.IsNullOrEmpty(username))
        {
            await DisplayAlert("Error", "No username to disconnect. Please enter a username or select a profile.", "OK");
            return;
        }

        SelectTab(Tab.Usage);
        DisconnectBtn.IsEnabled = false;
        SetStatus("Disconnecting...", StatusType.Info);
        ClearOutput();
        AppendToOutput($"Disconnecting user '{username}'... Please wait.");

        try
        {
            JsonDocument response = await _connectionService.DisconnectAsync(username);
            JsonElement root = response.RootElement;

            if (root.TryGetProperty("info", out JsonElement info) &&
                info.TryGetProperty("code", out JsonElement code) &&
                code.GetString() == "disconnect_success")
            {
                ClearOutput();
                AppendToOutput($"Successfully disconnected user '{username}' from the network.\n");
                AppendToOutput("You can now connect with a different profile or close the application.");
                SetStatus("Disconnected successfully", StatusType.Success);
            }
            else
            {
                ClearOutput();
                DisplayError("Disconnect returned unexpected response");
                SetStatus("Disconnect: unexpected response", StatusType.Warning);
            }
        }
        catch (Exception ex)
        {
            ClearOutput();
            DisplayError($"Error during disconnect: {ex.Message}");
            SetStatus($"Error: {ex.Message}", StatusType.Error);
        }
        finally
        {
            DisconnectBtn.IsEnabled = true;
        }
    }

    // ===== Normal usage display =====
    private void DisplayInfo(JsonElement data)
    {
        try
        {
            ClearOutput();

            if (!data.TryGetProperty("user", out JsonElement user) ||
                !user.TryGetProperty("consumedData", out JsonElement consumed))
            {
                DisplayError("Missing consumption data in API response");
                return;
            }

            string username = GetStringValue(user, "login");
            string profile = GetStringValue(user, "profile");
            long downloadBytes = GetLongValue(consumed, "download");
            long uploadBytes = GetLongValue(consumed, "upload");
            long renewTimestamp = GetLongValue(consumed, "renewTimestamp");

            StringBuilder output = new();
            output.AppendLine("INTERNET USAGE SUMMARY\n");
            output.AppendLine($"User: {username}");
            output.AppendLine($"Profile: {profile}\n");

            output.AppendLine("DATA USAGE");
            output.AppendLine($"Download: {FormatBytes(downloadBytes)}");
            output.AppendLine($"Upload: {FormatBytes(uploadBytes)}");
            output.AppendLine($"Total Usage: {FormatBytes(downloadBytes + uploadBytes)}\n");

            DisplayQuotaInfoForOutput(consumed, output);

            if (renewTimestamp > 0)
            {
                DateTimeOffset renewTime = DateTimeOffset.FromUnixTimeSeconds(renewTimestamp);
                TimeSpan timeRemaining = renewTime - DateTimeOffset.Now;
                if (timeRemaining.TotalSeconds < 0)
                {
                    renewTime = DateTimeOffset.Now.AddHours(24);
                    timeRemaining = TimeSpan.FromHours(24);
                }

                output.AppendLine("TIME INFORMATION");
                output.AppendLine($"Time until renewal: {timeRemaining.Days} days, {timeRemaining.Hours} hours, {timeRemaining.Minutes} minutes");
                output.AppendLine($"Renewal date: {renewTime:yyyy-MM-dd HH:mm:ss}\n");
            }

            output.AppendLine($"Last updated: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            OutputText.Text = output.ToString();
        }
        catch (Exception ex)
        {
            DisplayError($"Error processing data: {ex.Message}", ex.ToString());
        }
    }

    private void DisplayQuotaInfoForOutput(JsonElement consumed, StringBuilder output)
    {
        bool quotaFound = false;
        if (consumed.TryGetProperty("extra", out JsonElement extraElement) &&
            extraElement.TryGetProperty("value", out JsonElement extraValue) &&
            extraValue.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in extraValue.EnumerateArray())
            {
                bool isSumQuota = item.TryGetProperty("isSumQuota", out JsonElement sq) && IsTrue(sq);
                bool isDisconnectQuota = item.TryGetProperty("isDisconnectQuota", out JsonElement dq) && IsTrue(dq);
                if (!isSumQuota || !isDisconnectQuota) continue;
                quotaFound = true;

                if (item.TryGetProperty("total", out JsonElement total) &&
                    total.TryGetProperty("upload", out JsonElement totalUpload))
                {
                    long totalQuota = GetLongFromElement(totalUpload);
                    if (totalQuota <= 0) break;

                    output.AppendLine("QUOTA INFORMATION");
                    output.AppendLine($"Total Traffic Quota: {FormatBytes(totalQuota)}");

                    if (item.TryGetProperty("available", out JsonElement available) &&
                        available.TryGetProperty("upload", out JsonElement availableUpload))
                    {
                        long remaining = GetLongFromElement(availableUpload);
                        long used = totalQuota - remaining;
                        double usagePct = Math.Max(0, Math.Min(100, (double)used / totalQuota * 100.0));

                        output.AppendLine($"Remaining: {FormatBytes(remaining)}");
                        string usageStatus = usagePct > 80 ? "High usage" : "Normal usage";
                        output.AppendLine($"Used: {FormatBytes(used)} ({usagePct:F1}%) - {usageStatus}\n");

                        ShowQuotaGauge(used);
                    }
                }
                break;
            }
        }
        if (!quotaFound)
        {
            output.AppendLine("QUOTA INFORMATION");
            output.AppendLine("Detailed quota information not available\n");
        }
    }

    // ===== Quota reached display =====
    private void DisplayQuotaReachedInfo(JsonElement data)
    {
        try
        {
            ClearOutput();
            if (!data.TryGetProperty("error", out JsonElement error) ||
                !error.TryGetProperty("value", out JsonElement errorValue))
            {
                DisplayError("Missing quota details in API response");
                return;
            }

            long consumedUp = GetLongFromElement(errorValue, "consumedUp");
            long consumedDown = GetLongFromElement(errorValue, "consumedDown");
            long thresholdUp = GetLongFromElement(errorValue, "thresoldUp");
            long renewTimestamp = GetRenewalTimestamp(errorValue);
            long totalConsumed = consumedUp + consumedDown;

            DateTimeOffset renewTime;
            TimeSpan timeRemaining;
            if (renewTimestamp > 0)
            {
                renewTime = DateTimeOffset.FromUnixTimeSeconds(renewTimestamp);
                timeRemaining = renewTime - DateTimeOffset.Now;
                if (timeRemaining.TotalSeconds < 0)
                {
                    renewTime = DateTimeOffset.Now.AddHours(24);
                    timeRemaining = TimeSpan.FromHours(24);
                }
            }
            else
            {
                renewTime = DateTimeOffset.Now.AddHours(24);
                timeRemaining = TimeSpan.FromHours(24);
            }

            StringBuilder output = new();
            output.AppendLine("QUOTA LIMIT REACHED\n");
            output.AppendLine("Your internet quota has been reached. You will have limited or no internet access until the renewal time.\n");

            output.AppendLine("DATA USAGE");
            output.AppendLine($"Download: {FormatBytes(consumedDown)}");
            output.AppendLine($"Upload: {FormatBytes(consumedUp)}");
            output.AppendLine($"Total Usage: {FormatBytes(totalConsumed)}\n");

            output.AppendLine("QUOTA INFORMATION");
            if (totalConsumed > thresholdUp && thresholdUp > 0)
            {
                output.AppendLine($"Total Data Limit: {FormatBytes(thresholdUp)}");
                double usagePct = (double)totalConsumed / thresholdUp * 100.0;
                output.AppendLine($"Total Usage: {usagePct:F1}%");
                double excessMB = (totalConsumed - thresholdUp) / (1024.0 * 1024.0);
                output.AppendLine(excessMB > 0 ? $"Exceeded by {excessMB:F1} MB\n" : "Limit reached\n");
            }
            else if (thresholdUp > 0)
            {
                output.AppendLine($"Upload Limit: {FormatBytes(thresholdUp)}");
                double uploadPct = (double)consumedUp / thresholdUp * 100.0;
                output.AppendLine($"Upload Usage: {uploadPct:F1}% (Limit reached)\n");
            }
            else
            {
                output.AppendLine("Quota limit information not available\n");
            }

            output.AppendLine("TIME INFORMATION");
            output.AppendLine($"Time until renewal: {timeRemaining.Days} days, {timeRemaining.Hours} hours, {timeRemaining.Minutes} minutes");
            output.AppendLine($"Renewal date: {renewTime:yyyy-MM-dd HH:mm:ss}\n");
            output.AppendLine($"Last updated: {DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            OutputText.Text = output.ToString();

            ShowQuotaGauge(totalConsumed > 0 ? totalConsumed : consumedUp);
        }
        catch (Exception ex)
        {
            DisplayError($"Error processing quota-reached data: {ex.Message}", ex.ToString());
        }
    }

    private void DisplayBadCredentials(string? username)
    {
        StringBuilder output = new();
        output.AppendLine("🔒 INVALID CREDENTIALS\n");
        output.AppendLine("The username or password you entered is incorrect.");
        output.AppendLine("Please double-check your credentials and try again.\n");
        if (!string.IsNullOrEmpty(username))
        {
            output.AppendLine($"Username tried: {username}");
        }
        OutputText.Text = output.ToString();
    }

    // ===== Save history =====
    private async void SaveHistory_Clicked(object sender, EventArgs e)
    {
        if (_currentData == null)
        {
            await DisplayAlert("Error", "No data to save. Please fetch data first.", "OK");
            return;
        }

        try
        {
            string username = UsernameEntry.Text ?? "Unknown";
            long downloadBytes = 0, uploadBytes = 0;
            string status = "Active";
            JsonElement data = _currentData.Value;

            if (data.TryGetProperty("user", out JsonElement user) &&
                user.TryGetProperty("consumedData", out JsonElement consumed))
            {
                downloadBytes = GetLongValue(consumed, "download");
                uploadBytes = GetLongValue(consumed, "upload");
            }
            else if (data.TryGetProperty("error", out JsonElement error) &&
                     error.TryGetProperty("code", out JsonElement code) &&
                     code.GetString() == "error_logon_volume-quota-reached-detail")
            {
                if (error.TryGetProperty("value", out JsonElement errorValue))
                {
                    downloadBytes = GetLongFromElement(errorValue, "consumedDown");
                    uploadBytes = GetLongFromElement(errorValue, "consumedUp");
                }
                status = "Quota Reached";
            }
            else
            {
                await DisplayAlert("Error", "Unrecognized data format. Cannot save history.", "OK");
                return;
            }

            await _storageService.SaveHistoryEntryAsync(username, downloadBytes, uploadBytes, status);
            SetStatus("Usage data saved to history file", StatusType.Success);
            await DisplayAlert("Success", "Usage data saved to history file", "OK");
        }
        catch (Exception ex)
        {
            SetStatus("Error saving data", StatusType.Error);
            await DisplayAlert("Error", $"Error saving usage data: {ex.Message}", "OK");
        }
    }

    // ===== Flush DNS (Windows only) =====
    private async void FlushDns_Clicked(object sender, EventArgs e)
    {
        try
        {
            SetStatus("Flushing DNS cache...", StatusType.Info);
#if WINDOWS
            var psi = new ProcessStartInfo
            {
                FileName = "ipconfig",
                Arguments = "/flushdns",
                CreateNoWindow = true,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            using var p = Process.Start(psi);
            if (p == null)
            {
                DisplayError("Could not start ipconfig");
                SetStatus("Failed to flush DNS cache", StatusType.Error);
                return;
            }
            string stdout = await p.StandardOutput.ReadToEndAsync();
            await p.WaitForExitAsync();
            if (p.ExitCode == 0)
            {
                AppendToOutput($"\nDNS cache has been successfully flushed.\n{stdout.Trim()}");
                SetStatus("DNS cache flushed successfully", StatusType.Success);
            }
            else
            {
                DisplayError("Failed to flush DNS cache", stdout);
                SetStatus("Failed to flush DNS cache", StatusType.Error);
            }
#else
            await DisplayAlert("Not supported",
                "Flushing the DNS cache isn't possible on Android without root. Toggle airplane mode or forget+rejoin the Wi-Fi network instead.",
                "OK");
            SetStatus("DNS flush not supported", StatusType.Warning);
#endif
        }
        catch (Exception ex)
        {
            DisplayError($"Error flushing DNS: {ex.Message}");
            SetStatus("Error flushing DNS", StatusType.Error);
        }
    }

    // ===== Quota gauge helpers =====
    private void ShowQuotaGauge(long usedBytes)
    {
        _gaugeDrawable.UsedBytes = Math.Max(0, usedBytes);
        QuotaGaugeView.IsVisible = true;
        QuotaGaugeView.Invalidate();
    }

    private void HideQuotaGauge()
    {
        QuotaGaugeView.IsVisible = false;
    }

    // ===== Output helpers =====
    private void DisplayError(string errorMessage, string? errorDetails = null)
    {
        StringBuilder sb = new();
        sb.AppendLine($"ERROR: {errorMessage}");
        if (!string.IsNullOrEmpty(errorDetails))
        {
            sb.AppendLine("\nError Details:");
            sb.AppendLine(errorDetails);
        }
        OutputText.Text = sb.ToString();
    }

    private void DisplayWelcomeMessage()
    {
        OutputText.Text =
            "Welcome to Stena Line Internet Monitor!\n\n" +
            "This tool helps you monitor your internet usage on the Stena Line network.\n\n" +
            "Getting Started:\n" +
            "1. Enter your password\n" +
            "2. Tap 'Fetch Data/Connect' to check your usage\n" +
            "3. Save profiles for easier access next time\n\n" +
            "Ready to check your internet usage status!";
    }

    private static string FormatBytes(long bytesValue)
    {
        try { return $"{bytesValue / 1024.0 / 1024.0:F1} MB"; }
        catch { return "Error"; }
    }

    private void ClearOutput()
    {
        HideQuotaGauge();
        OutputText.Text = string.Empty;
    }

    private void ClearDisplay_Clicked(object sender, EventArgs e)
    {
        ClearOutput();
        DisplayWelcomeMessage();
    }

    private void AppendToOutput(string text)
    {
        OutputText.Text += text + "\n";
    }

    private void SetStatus(string message, StatusType statusType)
    {
        StatusLabel.Text = message;
        StatusIndicator.BackgroundColor = statusType switch
        {
            StatusType.Success => _themeService.GetSuccessColor(),
            StatusType.Warning => _themeService.GetWarningColor(),
            StatusType.Error => _themeService.GetErrorColor(),
            _ => _themeService.GetAccentColor(),
        };
    }

    private void ToggleTheme_Tapped(object sender, TappedEventArgs e)
    {
        _themeService.ToggleTheme();
    }

    private async void OpenGitHub_Tapped(object sender, TappedEventArgs e)
    {
        try
        {
            await Launcher.OpenAsync(new Uri("https://github.com/Damiasroca/SLIM"));
        }
        catch (Exception ex)
        {
            await DisplayAlert("Error", $"Failed to open GitHub link: {ex.Message}", "OK");
        }
    }

    // ===== Network Quality logger callbacks =====
    private void OnQualityUpdate(object? sender, NetworkQualityRecord? record)
    {
        MainThread.BeginInvokeOnMainThread(ReloadQualityVisuals);
    }

    private void ReloadQualityVisuals()
    {
        RefreshVpnState();

        NetworkQualityRecord? rec = _qualityLogger.LastRecord;
        if (_qualityLogger.VpnReason != null)
        {
            QualityCurrentLabel.Text = "Paused (VPN detected).";
        }
        else if (rec == null)
        {
            QualityCurrentLabel.Text = "Sampling…";
        }
        else if (!rec.Avg.HasValue)
        {
            QualityCurrentLabel.Text = $"Last: unreachable ({rec.Loss:F0}% loss) at {rec.Timestamp:HH:mm:ss}";
        }
        else
        {
            QualityCurrentLabel.Text = $"Last: {rec.Avg:F0} ms  |  jitter {rec.Jitter:F0} ms  |  {rec.Loss:F0}% loss at {rec.Timestamp:HH:mm:ss}";
        }

        List<NetworkQualityRecord> all = _qualityLogger.LoadAll();
        Dictionary<int, (List<double> Lat, List<double> Loss)> hourly = new();
        for (int h = 0; h < 24; h++) hourly[h] = (new List<double>(), new List<double>());
        foreach (var r in all)
        {
            int h = r.Timestamp.Hour;
            hourly[h].Loss.Add(r.Loss);
            if (r.Avg.HasValue) hourly[h].Lat.Add(r.Avg.Value);
        }
        _heatmapDrawable.Hourly = hourly;
        HeatmapView.Invalidate();

        // Quietest-hours summary
        List<(double avg, int h, int n)> ranked = new();
        foreach (var kv in hourly)
        {
            if (kv.Value.Lat.Count > 0)
                ranked.Add((kv.Value.Lat.Average(), kv.Key, kv.Value.Loss.Count));
        }
        if (ranked.Count == 0)
        {
            QualitySummaryLabel.Text = "Quietest hours: no data yet.";
        }
        else
        {
            ranked.Sort((a, b) => a.avg.CompareTo(b.avg));
            string best = string.Join(", ",
                ranked.Take(3).Select(t => $"{t.h:00}:00 ({t.avg.ToString("F0", CultureInfo.InvariantCulture)} ms)"));
            QualitySummaryLabel.Text = $"Quietest hours so far: {best}";
        }

        // Scatter chart points
        List<(double FracHour, double? Avg, double Jitter, double Loss)> points = new();
        foreach (var r in all)
        {
            double frac = r.Timestamp.Hour + r.Timestamp.Minute / 60.0 + r.Timestamp.Second / 3600.0;
            points.Add((frac, r.Avg, r.Jitter ?? 0.0, r.Loss));
        }
        _chartDrawable.Points = points;
        ProbeChartView.Invalidate();
    }

    private void RefreshVpnState()
    {
        string? raw = _qualityLogger.VpnReason;
        if (raw != _vpnDismissedReason)
            _vpnDismissedReason = null;
        string? effective = (raw == null || _vpnDismissedReason != null) ? null : raw;

        bool visible = effective != null;
        string text = effective != null
            ? $"VPN/tunnel detected — the Stena portal won't be reachable. {effective}. Disable the VPN to fetch usage data."
            : string.Empty;
        UsageVpnBanner.IsVisible = visible;
        UsageVpnBannerText.Text = text;
        QualityVpnBanner.IsVisible = visible;
        QualityVpnBannerText.Text = effective != null
            ? $"VPN/tunnel detected — sampling paused. {effective}. Disable the VPN to resume probing the Stena portal."
            : string.Empty;
    }

    private void DismissVpnBanner_Tapped(object sender, TappedEventArgs e)
    {
        _vpnDismissedReason = _qualityLogger.VpnReason;
        RefreshVpnState();
    }

    // ===== IP Info =====
    private async void IpInfoRefresh_Clicked(object sender, EventArgs e)
    {
        await RefreshIpInfoAsync();
    }

    private async Task RefreshIpInfoAsync()
    {
        if (_ipInfoLoading) return;
        _ipInfoLoading = true;
        IpInfoRefreshBtn.IsEnabled = false;
        IpInfoText.Text = "Fetching IP information...";
        try
        {
            IpInfo info = await _ipInfoService.FetchAsync();
            _ipInfo = info;
            RenderIpInfo(info);

            if (!string.IsNullOrEmpty(info.Ip) && string.IsNullOrEmpty(info.Hostname))
            {
                _ = Task.Run(async () =>
                {
                    string? host = await IpInfoService.ReverseDnsAsync(info.Ip);
                    if (!string.IsNullOrEmpty(host) && _ipInfo != null)
                    {
                        _ipInfo.Hostname = host;
                        MainThread.BeginInvokeOnMainThread(() => RenderIpInfo(_ipInfo));
                    }
                });
            }
        }
        catch (Exception ex)
        {
            IpInfoText.Text = $"Failed to fetch IP information.\n{ex.Message}";
        }
        finally
        {
            _ipInfoLoading = false;
            IpInfoRefreshBtn.IsEnabled = true;
        }
    }

    private void RenderIpInfo(IpInfo d)
    {
        StringBuilder sb = new();
        sb.AppendLine("Public IP Address");
        AddRow(sb, "IP Address", d.Ip);
        AddRow(sb, "Version", d.Version);
        AddRow(sb, "Reverse DNS", d.Hostname ?? "—");
        sb.AppendLine();

        sb.AppendLine("Network / ISP");
        AddRow(sb, "Organization", d.Org);
        AddRow(sb, "ASN", d.Asn);
        sb.AppendLine();

        sb.AppendLine("Location");
        var locParts = new[] { d.City, d.Region, d.Country }.Where(s => !string.IsNullOrEmpty(s));
        string loc = string.Join(", ", locParts);
        AddRow(sb, "Location", string.IsNullOrEmpty(loc) ? null : loc);
        AddRow(sb, "Country code", d.CountryCode);
        AddRow(sb, "Postal code", d.Postal);
        if (d.Latitude.HasValue && d.Longitude.HasValue)
            AddRow(sb, "Coordinates",
                $"{d.Latitude.Value.ToString(CultureInfo.InvariantCulture)}, {d.Longitude.Value.ToString(CultureInfo.InvariantCulture)}");
        AddRow(sb, "Timezone", d.Timezone);
        AddRow(sb, "UTC offset", d.UtcOffset);
        sb.AppendLine();

        sb.AppendLine("Region info");
        AddRow(sb, "Calling code", d.CallingCode);
        string? currency = d.CurrencyName != null && d.Currency != null
            ? $"{d.CurrencyName} ({d.Currency})"
            : d.CurrencyName ?? d.Currency;
        AddRow(sb, "Currency", currency);
        AddRow(sb, "Languages", d.Languages);
        sb.AppendLine();

        sb.AppendLine($"Source: {d.Source ?? "unknown"}");
        IpInfoText.Text = sb.ToString();
    }

    private static void AddRow(StringBuilder sb, string label, string? value)
    {
        if (string.IsNullOrEmpty(value)) return;
        sb.AppendLine($"{label,14} : {value}");
    }

    // ===== JSON helpers =====
    private static bool IsTrue(JsonElement el)
    {
        return el.ValueKind == JsonValueKind.True ||
               (el.ValueKind == JsonValueKind.String && string.Equals(el.GetString(), "true", StringComparison.OrdinalIgnoreCase));
    }

    private static long GetRenewalTimestamp(JsonElement errorValue)
    {
        string[] possibleNames = { "renewTimeStamp", "renewTimestamp", "renewTime", "resetTime", "resetTimeStamp" };
        foreach (string name in possibleNames)
        {
            if (errorValue.TryGetProperty(name, out JsonElement timeElement))
            {
                if (timeElement.ValueKind == JsonValueKind.Number) return timeElement.GetInt64();
                if (timeElement.ValueKind == JsonValueKind.String &&
                    long.TryParse(timeElement.GetString(), out long result)) return result;
            }
        }
        return DateTimeOffset.Now.AddHours(24).ToUnixTimeSeconds();
    }

    private static string GetStringValue(JsonElement parent, string propertyName)
    {
        if (parent.TryGetProperty(propertyName, out JsonElement prop) &&
            prop.TryGetProperty("value", out JsonElement value))
        {
            return value.GetString() ?? "N/A";
        }
        return "N/A";
    }

    private static long GetLongValue(JsonElement parent, string propertyName)
    {
        if (parent.TryGetProperty(propertyName, out JsonElement prop) &&
            prop.TryGetProperty("value", out JsonElement value))
        {
            return GetLongFromElement(value);
        }
        return 0;
    }

    private static long GetLongFromElement(JsonElement element, string propertyName)
    {
        if (element.TryGetProperty(propertyName, out JsonElement prop)) return GetLongFromElement(prop);
        return 0;
    }

    private static long GetLongFromElement(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Number) return element.GetInt64();
        if (element.ValueKind == JsonValueKind.String && long.TryParse(element.GetString(), out long result)) return result;
        return 0;
    }
}

public enum StatusType
{
    Info,
    Success,
    Warning,
    Error
}
