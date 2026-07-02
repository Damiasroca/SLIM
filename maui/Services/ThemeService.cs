using System.Text.Json;

namespace KerryInternetMonitor.Services
{
    public class ThemeService
    {
        private readonly string _configFilePath;
        private bool _isDarkTheme = true;

        public bool IsDarkTheme => _isDarkTheme;

        public event EventHandler? ThemeChanged;

        public ThemeService()
        {
            _configFilePath = Path.Combine(FileSystem.AppDataDirectory, "config.json");
            LoadConfig();
        }

        private void LoadConfig()
        {
            try
            {
                if (File.Exists(_configFilePath))
                {
                    string json = File.ReadAllText(_configFilePath);
                    var config = JsonSerializer.Deserialize<Dictionary<string, string>>(json);
                    if (config != null && config.TryGetValue("theme", out string? theme))
                    {
                        _isDarkTheme = theme == "dark";
                    }
                }
            }
            catch (Exception)
            {
                _isDarkTheme = true;
            }
        }

        private void SaveConfig()
        {
            try
            {
                var config = new Dictionary<string, string>
                {
                    { "theme", _isDarkTheme ? "dark" : "light" }
                };
                string json = JsonSerializer.Serialize(config);
                File.WriteAllText(_configFilePath, json);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error saving config: {ex.Message}");
            }
        }

        public void ToggleTheme()
        {
            _isDarkTheme = !_isDarkTheme;
            SaveConfig();
            ThemeChanged?.Invoke(this, EventArgs.Empty);
        }

        public Color GetBackgroundColor() => _isDarkTheme 
            ? Color.FromArgb("#1a1a2e") 
            : Color.FromArgb("#f8fafc");

        public Color GetBackgroundSecondaryColor() => _isDarkTheme 
            ? Color.FromArgb("#16213e") 
            : Color.FromArgb("#ffffff");

        public Color GetBackgroundTertiaryColor() => _isDarkTheme 
            ? Color.FromArgb("#0f3460") 
            : Color.FromArgb("#f1f5f9");

        public Color GetTextColor() => _isDarkTheme 
            ? Color.FromArgb("#eaeaea") 
            : Color.FromArgb("#1e293b");

        public Color GetTextSecondaryColor() => _isDarkTheme 
            ? Color.FromArgb("#a0a0a0") 
            : Color.FromArgb("#64748b");

        public Color GetAccentColor() => _isDarkTheme 
            ? Color.FromArgb("#4361ee") 
            : Color.FromArgb("#3b82f6");

        public Color GetSuccessColor() => _isDarkTheme 
            ? Color.FromArgb("#4ade80") 
            : Color.FromArgb("#22c55e");

        public Color GetWarningColor() => _isDarkTheme 
            ? Color.FromArgb("#fbbf24") 
            : Color.FromArgb("#f59e0b");

        public Color GetErrorColor() => _isDarkTheme 
            ? Color.FromArgb("#f87171") 
            : Color.FromArgb("#ef4444");

        public Color GetBorderColor() => _isDarkTheme 
            ? Color.FromArgb("#2a2a4a") 
            : Color.FromArgb("#e2e8f0");

        public string GetThemeIcon() => _isDarkTheme ? "🌙 Dark" : "☀️ Light";
    }
}
