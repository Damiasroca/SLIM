namespace KerryInternetMonitor.Models
{
    public class NetworkQualityRecord
    {
        public DateTime Timestamp { get; set; }
        public string Host { get; set; } = string.Empty;
        public double? Avg { get; set; }
        public double? Min { get; set; }
        public double? Max { get; set; }
        public double? Jitter { get; set; }
        public double Loss { get; set; }
    }
}
