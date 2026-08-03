"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
  ReferenceLine,
  Label,
} from "recharts";
import { format, parseISO, startOfToday } from "date-fns";
import { ApiForecastDataPoint } from "../dashboard/forecasting-page"; // Pastikan path ini benar

interface ForecastChartProps {
  chartData: ApiForecastDataPoint[];
  emotion: string;
}

// --- PERUBAHAN DI SINI ---
// Mendefinisikan warna langsung di dalam kode, tanpa bergantung pada file CSS.
const emotionColors: { [key: string]: string } = {
  happy: "#f59e0b",     // Kuning/Oranye cerah
  sad: "#3b82f6",       // Biru
  angry: "#ef4444",     // Merah
  fear: "#db2777",       // Merah muda/Magenta
  surprised: "#8b5cf6", // Ungu
  neutral: "#64748b",     // Abu-abu netral untuk data historis
  default: "#64748b",     // Warna default jika emosi tidak ditemukan
};

const ForecastChart = ({ chartData, emotion }: ForecastChartProps) => {
  const currentEmotionKey = (typeof emotion === 'string' && emotion.trim() !== '') ? emotion.toLowerCase() : 'default';
  
  // Logika pemilihan warna menjadi lebih sederhana
  const color = emotionColors[currentEmotionKey] || emotionColors.default;
  const neutralColor = emotionColors.neutral;

  const todayStr = format(startOfToday(), "yyyy-MM-dd");

  const processedData = useMemo(() => {
    return chartData.map((item) => ({
      ...item,
      confidenceRange: [item.yhat_lower, item.yhat_upper],
    }));
  }, [chartData]);

  if (!processedData || processedData.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
        No data available for this period or emotion.
      </div>
    );
  }

  const todayIndex = processedData.findIndex((p) => p.name === todayStr);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0].payload as any;
      return (
        <div className="bg-background border p-2 rounded shadow-lg text-xs z-50">
          <p className="label font-bold">
            {label ? `Date: ${format(parseISO(label), "PP")}` : ""}
          </p>
          {dataPoint.actual !== null && dataPoint.actual !== undefined && (
            <p style={{ color: neutralColor }}>{`Actual: ${dataPoint.actual.toFixed(2)}`}</p>
          )}
          {dataPoint.yhat !== null && dataPoint.yhat !== undefined && (
            <p style={{ color: color }}>{`Forecast: ${dataPoint.yhat.toFixed(2)}`}</p>
          )}
          {dataPoint.confidenceRange && dataPoint.confidenceRange[0] !== null && dataPoint.confidenceRange[1] !== null && (
            <p style={{ color: color, opacity: 0.8 }}>
              {`Range: ${dataPoint.confidenceRange[0].toFixed(2)} - ${dataPoint.confidenceRange[1].toFixed(2)}`}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  const yDomain = useMemo(() => {
    let minVal = Infinity;
    let maxVal = -Infinity;
    let hasData = false;
    processedData.forEach(p => {
        const values = [p.actual, p.yhat, p.yhat_lower, p.yhat_upper];
        values.forEach(val => {
            if (val !== null && val !== undefined) {
                hasData = true;
                minVal = Math.min(minVal, val);
                maxVal = Math.max(maxVal, val);
            }
        });
    });

    if (!hasData) return ['auto', 'auto'];

    const padding = Math.max(1, (maxVal - minVal) * 0.1);
    return [Math.max(0, Math.floor(minVal - padding)), Math.ceil(maxVal + padding)];
  }, [processedData]);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={processedData} margin={{ top: 5, right: 30, left: 0, bottom: 40 }}>
        <defs>
          <linearGradient id={`colorActual-${currentEmotionKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={neutralColor} stopOpacity={0.4} />
            <stop offset="95%" stopColor={neutralColor} stopOpacity={0} />
          </linearGradient>
          <linearGradient id={`colorForecast-${currentEmotionKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.6} />
            <stop offset="95%" stopColor={color} stopOpacity={0.1} />
          </linearGradient>
          <linearGradient id={`colorConfidence-${currentEmotionKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.2} />
            <stop offset="95%" stopColor={color} stopOpacity={0.05} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
        <XAxis
            dataKey="name"
            tick={{ fontSize: 10 }}
            tickFormatter={(tickItem: string) => format(parseISO(tickItem), "MMM d")}
            angle={-30}
            textAnchor="end"
            height={50}
            interval="preserveStartEnd"
        />
        <YAxis
            tick={{ fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            domain={yDomain}
            allowDataOverflow={false}
        />
        <Tooltip content={<CustomTooltip />} wrapperStyle={{ zIndex: 1000 }} />
        <Legend verticalAlign="top" height={36} wrapperStyle={{ paddingBottom: "10px" }} />

        <Area
          type="monotone"
          dataKey="confidenceRange"
          stroke="transparent"
          fill={`url(#colorConfidence-${currentEmotionKey})`}
          name="Confidence Range"
          connectNulls={true}
        />
        <Area
          type="monotone"
          dataKey="actual"
          stroke={neutralColor}
          fill={`url(#colorActual-${currentEmotionKey})`}
          strokeWidth={1.5}
          strokeDasharray="4 4"
          name="Historical Actual"
          dot={false}
          connectNulls={true}
        />
        <Area
          type="monotone"
          dataKey="yhat"
          stroke={color}
          fill={`url(#colorForecast-${currentEmotionKey})`}
          strokeWidth={2}
          name="Forecast"
          dot={false}
          activeDot={{ r: 5, strokeWidth: 1, fill: 'var(--background)', stroke: color }}
          connectNulls={true}
        />
        {todayIndex !== -1 && processedData[todayIndex] && (
            <ReferenceLine x={processedData[todayIndex].name} stroke="#ef4444" strokeDasharray="3 3" strokeWidth={1.5}>
                <Label value="Today" position="insideTopRight" fill="#ef4444" fontSize={10} offset={5}/>
            </ReferenceLine>
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
};

export default ForecastChart;