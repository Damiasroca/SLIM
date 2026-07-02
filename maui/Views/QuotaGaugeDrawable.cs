using System.Globalization;
using Microsoft.Maui.Graphics;
using KerryInternetMonitor.Services;

namespace KerryInternetMonitor.Views
{
    /// <summary>
    /// Semicircle fuel-gauge style quota indicator, matching the Python
    /// <c>QuotaGauge</c> widget. Scales to a 1 GB reference by default; if
    /// usage exceeds the scale the dial turns red and the sub-label shows
    /// the overflow amount.
    /// </summary>
    public class QuotaGaugeDrawable : IDrawable
    {
        public const long GaugeMaxBytes = 1024L * 1024L * 1024L;

        public long UsedBytes { get; set; }
        public long MaxBytes { get; set; } = GaugeMaxBytes;

        private readonly ThemeService _theme;

        public QuotaGaugeDrawable(ThemeService theme)
        {
            _theme = theme;
        }

        public void Draw(ICanvas canvas, RectF rect)
        {
            Color bgSecondary = _theme.GetBackgroundSecondaryColor();
            Color bgTertiary = _theme.GetBackgroundTertiaryColor();
            Color text = _theme.GetTextColor();
            Color textSecondary = _theme.GetTextSecondaryColor();
            Color success = _theme.GetSuccessColor();
            Color warning = _theme.GetWarningColor();
            Color error = _theme.GetErrorColor();

            canvas.FillColor = bgSecondary;
            canvas.FillRectangle(rect);

            float cx = rect.Width / 2f;
            float cy = rect.Height - 50f;
            float outerR = Math.Min(cx - 20f, rect.Height - 80f);
            if (outerR < 30) outerR = 30f;
            float innerR = outerR - 24f;
            if (innerR < 5) innerR = 5f;

            double fraction = MaxBytes > 0 ? (double)UsedBytes / MaxBytes : 0.0;
            double clamped = Math.Min(fraction, 1.0);
            bool overLimit = fraction > 1.0;

            Color fillColor;
            if (overLimit || clamped >= 0.85) fillColor = error;
            else if (clamped >= 0.6) fillColor = warning;
            else fillColor = success;

            canvas.FontColor = success;
            canvas.FontSize = 13f;
            canvas.Font = Microsoft.Maui.Graphics.Font.DefaultBold;
            canvas.DrawString("QUOTA", rect.Left, 4f, rect.Width, 20f,
                HorizontalAlignment.Center, VerticalAlignment.Top);

            DrawSemiPie(canvas, cx, cy, outerR, 180f, bgTertiary);
            if (clamped > 0)
            {
                float filledExtent = (float)(180.0 * clamped);
                DrawSemiPie(canvas, cx, cy, outerR, filledExtent, fillColor);
            }
            DrawSemiPie(canvas, cx, cy, innerR, 180f, bgSecondary);

            canvas.StrokeColor = textSecondary;
            canvas.StrokeSize = 1f;
            foreach (float tickFraction in new[] { 0.0f, 0.25f, 0.5f, 0.75f, 1.0f })
            {
                double angle = Math.PI * (1.0 - tickFraction);
                float x1 = cx + (float)(Math.Cos(angle) * (outerR + 1));
                float y1 = cy - (float)(Math.Sin(angle) * (outerR + 1));
                float x2 = cx + (float)(Math.Cos(angle) * (outerR + 7));
                float y2 = cy - (float)(Math.Sin(angle) * (outerR + 7));
                canvas.DrawLine(x1, y1, x2, y2);
            }

            canvas.FillColor = textSecondary;
            canvas.FillCircle(cx, cy, 4f);

            double usedMb = UsedBytes / 1024.0 / 1024.0;
            double maxMb = MaxBytes / 1024.0 / 1024.0;
            double pct = clamped * 100.0;

            canvas.FontColor = text;
            canvas.FontSize = 13f;
            canvas.Font = Microsoft.Maui.Graphics.Font.DefaultBold;
            string primary = string.Format(CultureInfo.InvariantCulture,
                "{0:F0} MB / {1:F0} MB", usedMb, maxMb);
            canvas.DrawString(primary, rect.Left, cy - outerR / 2f - 10f, rect.Width, 20f,
                HorizontalAlignment.Center, VerticalAlignment.Top);

            string sub;
            Color subColor;
            if (overLimit)
            {
                sub = string.Format(CultureInfo.InvariantCulture, "+{0:F0} MB over", usedMb - maxMb);
                subColor = error;
            }
            else
            {
                sub = string.Format(CultureInfo.InvariantCulture, "{0:F0}%", pct);
                subColor = textSecondary;
            }
            canvas.FontColor = subColor;
            canvas.FontSize = 12f;
            canvas.DrawString(sub, rect.Left, cy + 8f, rect.Width, 18f,
                HorizontalAlignment.Center, VerticalAlignment.Top);

            canvas.FontColor = textSecondary;
            canvas.FontSize = 9f;
            canvas.Font = Microsoft.Maui.Graphics.Font.Default;
            canvas.DrawString("0", cx - outerR, cy + 6f, 20f, 14f,
                HorizontalAlignment.Center, VerticalAlignment.Top);
            string maxLabel = string.Format(CultureInfo.InvariantCulture, "{0:F0} MB", maxMb);
            canvas.DrawString(maxLabel, cx + outerR - 20f, cy + 6f, 40f, 14f,
                HorizontalAlignment.Center, VerticalAlignment.Top);
        }

        private static void DrawSemiPie(ICanvas canvas, float cx, float cy, float r,
            float extentDegrees, Color fill)
        {
            if (extentDegrees <= 0 || r <= 0) return;
            var path = new PathF();
            path.MoveTo(cx, cy);

            int steps = Math.Max(6, (int)Math.Ceiling(extentDegrees / 4f));
            float startDeg = 180f - extentDegrees;
            for (int i = 0; i <= steps; i++)
            {
                float t = (float)i / steps;
                float deg = startDeg + t * extentDegrees;
                double rad = Math.PI * deg / 180.0;
                float x = cx + (float)(Math.Cos(rad) * r);
                float y = cy - (float)(Math.Sin(rad) * r);
                path.LineTo(x, y);
            }
            path.Close();
            canvas.FillColor = fill;
            canvas.FillPath(path);
        }
    }
}
