"use client";

import { useMemo } from "react";
import {
    Bar,
    BarChart,
    CartesianGrid,
    Legend,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from "@/components/ui/chart";
import { format, parseISO } from "date-fns";
import { ApiForecastDataPoint } from "../dashboard/forecasting-page";

interface EmotionComparisonChartProps {
  multiEmotionData: { [emotion: string]: ApiForecastDataPoint[] };
}

// --- PERUBAHAN DI SINI ---
// Mendefinisikan warna langsung di dalam kode, tanpa bergantung pada file CSS.
const emotionColors: { [key: string]: string } = {
  happy: "#f59e0b",     // Kuning/Oranye cerah
  sad: "#3b82f6",       // Biru
  angry: "#ef4444",     // Merah
  fear: "#db2777",       // Merah muda/Magenta
  surprised: "#8b5cf6", // Ungu
  neutral: "#64748b",     // Abu-abu netral
  default: "#64748b",     // Warna default jika emosi tidak ditemukan
};


const EmotionComparisonChart = ({ multiEmotionData }: EmotionComparisonChartProps) => {
  const emotions = useMemo(() => {
    return Object.keys(multiEmotionData).filter(key => typeof key === 'string' && key.trim() !== '');
  }, [multiEmotionData]);

  const chartData = useMemo(() => {
    if (emotions.length === 0) return [];

    const dateMap = new Map<string, any>();
    emotions.forEach(emotion => {
      const dataPoints = multiEmotionData[emotion];
      if (dataPoints) {
        dataPoints.forEach(point => {
          if (!dateMap.has(point.name)) {
            dateMap.set(point.name, { name: point.name });
          }
          dateMap.get(point.name)[`${emotion}_yhat`] = point.yhat === null ? undefined : point.yhat;
        });
      }
    });

    return Array.from(dateMap.values()).sort((a,b) => new Date(a.name).getTime() - new Date(b.name).getTime());
  }, [multiEmotionData, emotions]);

  if (emotions.length === 0 || chartData.length === 0) {
    return <div className="flex items-center justify-center h-full text-sm text-muted-foreground">Select emotions and ensure data is available for comparison.</div>;
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-background border p-2 rounded shadow-lg text-xs z-50">
          <p className="label font-bold">{label ? `Date: ${format(parseISO(label), "PP")}` : ''}</p>
          {payload.map((entry: any) => {
            const emotionNameFromDataKey = typeof entry.dataKey === 'string' ? entry.dataKey.split('_')[0] : 'default';
            const color = entry.color || emotionColors[emotionNameFromDataKey] || emotionColors.default;
            
            // Menggunakan entry.name untuk label yang lebih baik dari legenda
            const displayName = entry.name || (emotionNameFromDataKey.charAt(0).toUpperCase() + emotionNameFromDataKey.slice(1));

            return (
              <p key={entry.dataKey} style={{ color: color }}>
                {`${displayName}: ${typeof entry.value === 'number' ? entry.value.toFixed(2) : 'N/A'}`}
              </p>
            );
          })}
        </div>
      );
    }
    return null;
  };

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 40 }}>
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
        <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} allowDataOverflow={false} domain={['auto', 'auto']} />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} wrapperStyle={{ zIndex: 1000 }}/>
        <Legend verticalAlign="top" height={30} wrapperStyle={{paddingBottom: "10px"}}/>

        {emotions.map((emotion) => {
          const emotionKey = emotion.toLowerCase();
          // Logika pemilihan warna yang lebih sederhana
          const color = emotionColors[emotionKey] || emotionColors.default;
          
          return (
            <Bar
                key={emotionKey}
                dataKey={`${emotionKey}_yhat`}
                fill={color}
                name={emotion.charAt(0).toUpperCase() + emotion.slice(1)}
                radius={[4, 4, 0, 0]}
            />
          );
        })}
      </BarChart>
    </ResponsiveContainer>
  );
};

export default EmotionComparisonChart;