using System.Globalization;
using Microsoft.Maui.Graphics;
using KerryInternetMonitor.Services;

namespace KerryInternetMonitor.Views
{
    /// <summary>
    /// Scatter chart of every probe matching the Python NetworkQualityPanel:
    /// X = hour of day (0..24), Y = latency (ms), small bar = jitter,
    /// vertical dashed line at top = unreachable sample.
    /// </summary>
    public class ProbeChartDrawable : IDrawable
    {
        private readonly ThemeService _theme;
        public IReadOnlyList<(double FracHour, double? Avg, double Jitter, double Loss)> Points { get; set; }
            = Array.Empty<(double, double?, double, double)>();

        public ProbeChartDrawable(ThemeService theme)
        {
            _theme = theme;
        }

        public void Draw(ICanvas canvas, RectF rect)
        {
            Color bg = _theme.GetBackgroundColor();
            Color border = _theme.GetBorderColor();
            Color textSecondary = _theme.GetTextSecondaryColor();
            Color error = _theme.GetErrorColor();

            canvas.FillColor = bg;
            canvas.FillRectangle(rect);

            float left = 46f, right = 12f, top = 10f, bottom = 22f;
            float plotW = rect.Width - left - right;
            float plotH = rect.Height - top - bottom;
            if (plotW < 10 || plotH < 10) return;

            double yMax = 500.0;
            double? maxAvg = null;
            foreach (var p in Points)
            {
                if (p.Avg.HasValue && (!maxAvg.HasValue || p.Avg.Value > maxAvg.Value))
                    maxAvg = p.Avg.Value;
            }
            if (maxAvg.HasValue) yMax = Math.Max(maxAvg.Value * 1.1, 100.0);

            float Yp(double val)
            {
                return top + plotH - (float)(Math.Min(val, yMax) / yMax * plotH);
            }

            canvas.StrokeColor = border;
            canvas.StrokeSize = 1f;
            canvas.DrawRectangle(left, top, plotW, plotH);

            canvas.FontColor = textSecondary;
            canvas.FontSize = 9f;
            for (int i = 0; i < 5; i++)
            {
                double val = yMax * i / 4.0;
                float y = Yp(val);
                canvas.DrawLine(left, y, left + plotW, y);
                string lbl = val.ToString("F0", CultureInfo.InvariantCulture);
                canvas.DrawString(lbl, left - 40f, y - 6f, 36f, 12f,
                    HorizontalAlignment.Right, VerticalAlignment.Center);
            }

            for (int hh = 0; hh <= 24; hh += 3)
            {
                float x = left + (hh / 24f) * plotW;
                canvas.DrawLine(x, top, x, top + plotH);
                canvas.DrawString(hh.ToString("00"), x - 10f, top + plotH + 4f, 20f, 12f,
                    HorizontalAlignment.Center, VerticalAlignment.Top);
            }

            foreach (var p in Points)
            {
                float x = left + (float)(p.FracHour / 24.0) * plotW;
                if (!p.Avg.HasValue)
                {
                    canvas.StrokeColor = error;
                    canvas.StrokeDashPattern = new float[] { 1f, 3f };
                    canvas.DrawLine(x, top, x, top + plotH);
                    canvas.StrokeDashPattern = null;
                    continue;
                }
                if (p.Jitter > 0)
                {
                    canvas.StrokeColor = textSecondary;
                    canvas.DrawLine(x, Yp(Math.Max(0.0, p.Avg.Value - p.Jitter)),
                                     x, Yp(p.Avg.Value + p.Jitter));
                }
                Color color = HeatmapDrawable.QualityColor(p.Avg, p.Loss);
                canvas.FillColor = color;
                float y = Yp(p.Avg.Value);
                canvas.FillCircle(x, y, 2.5f);
            }

            if (Points.Count == 0)
            {
                canvas.FontColor = textSecondary;
                canvas.FontSize = 11f;
                canvas.DrawString("No probe data yet.",
                    left, top + plotH / 2f - 8f, plotW, 16f,
                    HorizontalAlignment.Center, VerticalAlignment.Center);
            }
        }
    }
}
