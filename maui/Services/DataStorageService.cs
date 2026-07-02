using System.Text.Json;
using KerryInternetMonitor.Models;

namespace KerryInternetMonitor.Services
{
    public class DataStorageService
    {
        private readonly string _profilesFilePath;
        private readonly string _historyFilePath;

        public string NetworkQualityCsvPath { get; }

        public DataStorageService()
        {
            _profilesFilePath = Path.Combine(FileSystem.AppDataDirectory, "profiles.json");
            _historyFilePath = Path.Combine(FileSystem.AppDataDirectory, "usage_history.csv");
            NetworkQualityCsvPath = Path.Combine(FileSystem.AppDataDirectory, "network_quality.csv");
        }

        public async Task<Dictionary<string, UserProfile>> LoadProfilesAsync()
        {
            try
            {
                if (File.Exists(_profilesFilePath))
                {
                    string json = await File.ReadAllTextAsync(_profilesFilePath);
                    var profiles = JsonSerializer.Deserialize<Dictionary<string, UserProfile>>(json);
                    return profiles ?? new Dictionary<string, UserProfile>();
                }

                return new Dictionary<string, UserProfile>();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error loading profiles: {ex.Message}");
                return new Dictionary<string, UserProfile>();
            }
        }

        public async Task SaveProfilesAsync(Dictionary<string, UserProfile> profiles)
        {
            try
            {
                string json = JsonSerializer.Serialize(profiles);
                await File.WriteAllTextAsync(_profilesFilePath, json);
            }
            catch (Exception ex)
            {
                throw new Exception($"Failed to save profiles: {ex.Message}", ex);
            }
        }

        public async Task SaveHistoryEntryAsync(string username, long downloadBytes, long uploadBytes, string status)
        {
            try
            {
                string timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
                double downloadMB = downloadBytes / 1024.0 / 1024.0;
                double uploadMB = uploadBytes / 1024.0 / 1024.0;
                double totalMB = (downloadBytes + uploadBytes) / 1024.0 / 1024.0;

                string csvLine = $"{timestamp},{username},{downloadMB:F2},{uploadMB:F2},{totalMB:F2},{status}";

                // Check if file exists and create header if needed
                bool fileExists = File.Exists(_historyFilePath);

                using (StreamWriter writer = new StreamWriter(_historyFilePath, true))
                {
                    if (!fileExists)
                    {
                        await writer.WriteLineAsync("Timestamp,Username,Download (MB),Upload (MB),Total (MB),Status");
                    }

                    await writer.WriteLineAsync(csvLine);
                }
            }
            catch (Exception ex)
            {
                throw new Exception($"Failed to save history: {ex.Message}", ex);
            }
        }
    }
}