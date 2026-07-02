using Microsoft.Maui.Graphics;
using KerryInternetMonitor.Models;
using KerryInternetMonitor.Services;

namespace KerryInternetMonitor.Views
{
    /// <summary>
    /// 24-cell hourly latency heatmap matching the Python NetworkQualityPanel.
    /// Green = fast, yellow = sluggish, red = slow / packet loss,
    /// dark red = unreachable, theme-tertiary = no data yet.
    /// </summary>
    public class HeatmapDrawable : IDrawable
    {
        private const float CellW = 26f;
        private const float CellH = 40f;
        private const float Gap = 2f;
        private const float PadX = 16f;
        private const float PadTop = 8f;

        private readonly ThemeService _theme;
        public IReadOnlyDictionary<int, (List<double> Lat, List<double> Loss)>? Hourly { get; set; }

        public HeatmapDrawable(ThemeService theme)
        {
            _theme = theme;
        }

        public static float DesiredWidth => PadX * 2 + 24 * (CellW + Gap);
        public static float DesiredHeight => PadTop + CellH + 22f;

        public void Draw(ICanvas canvas, RectF rect)
        {
            Color bgTertiary = _theme.GetBackgroundTertiaryColor();
            Color border = _theme.GetBorderColor();
            Color textSecondary = _theme.GetTextSecondaryColor();

            for (int h = 0; h < 24; h++)
            {
                float x0 = PadX + h * (CellW + Gap);
                float y0 = PadTop;
                Color cellColor;
                if (Hourly != null && Hourly.TryGetValue(h, out var d) && d.Loss.Count > 0)
                {
                    double? avgLat = d.Lat.Count > 0 ? d.Lat.Average() : null;
                    double avgLoss = d.Loss.Average();
                    cellColor = QualityColor(avgLat, avgLoss);
                }
                else
                {
                    cellColor = bgTertiary;
                }
                canvas.FillColor = cellColor;
                canvas.FillRectangle(x0, y0, CellW, CellH);
                canvas.StrokeColor = border;
                canvas.StrokeSize = 1f;
                canvas.DrawRectangle(x0, y0, CellW, CellH);

                canvas.FontColor = textSecondary;
                canvas.FontSize = 9f;
                string label = h.ToString("00");
                canvas.DrawString(label, x0, y0 + CellH + 2f, CellW, 14f,
                    HorizontalAlignment.Center, VerticalAlignment.Top);
            }
        }

        public static Color QualityColor(double? lat, double loss)
        {
            if (!lat.HasValue) return Color.FromArgb("#7f1d1d");
            const double good = 60.0, bad = 1500.0;
            double t = Math.Clamp((lat.Value - good) / (bad - good), 0.0, 1.0);
            t = Math.Max(t, Math.Min(1.0, loss / 100.0));
            (int r, int g, int b) green = (74, 222, 128);
            (int r, int g, int b) yellow = (251, 191, 36);
            (int r, int g, int b) red = (248, 113, 113);
            (int r, int g, int b) c;
            if (t <= 0.5) c = Lerp(green, yellow, t / 0.5);
            else c = Lerp(yellow, red, (t - 0.5) / 0.5);
            return Color.FromRgb(c.r, c.g, c.b);
        }

        private static (int r, int g, int b) Lerp((int r, int g, int b) a, (int r, int g, int b) b, double f)
        {
            return ((int)(a.r + (b.r - a.r) * f),
                    (int)(a.g + (b.g - a.g) * f),
                    (int)(a.b + (b.b - a.b) * f));
        }
    }
}
