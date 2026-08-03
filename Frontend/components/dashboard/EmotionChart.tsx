// components/dashboard/EmotionChart.tsx

"use client"

import { Area, AreaChart, Bar, BarChart as RechartsBarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useMemo } from "react"

interface EmotionChartProps {
  data: any[]
}

// Fungsi helper untuk mendeteksi kunci data secara dinamis
const parseDataKeys = (data: any[]) => {
  if (!data || data.length === 0) {
    return { categoryKey: null, valueKeys: [], isTimeSeries: false };
  }

  const sample = data[0];
  if (typeof sample !== 'object' || sample === null) {
      return { categoryKey: null, valueKeys: [], isTimeSeries: false };
  }
  const keys = Object.keys(sample);

  let categoryKey = keys.find(key => typeof sample[key] === 'string' && (key.toLowerCase().includes('date') || key.toLowerCase().includes('day') || key.toLowerCase().includes('emotion') || key.toLowerCase().includes('name')));
  if (!categoryKey) categoryKey = keys.find(key => typeof sample[key] === 'string'); // Cari kunci string apapun
  if (!categoryKey) categoryKey = keys[0]; // Fallback ke kunci pertama
  
  const valueKeys = keys.filter(key => typeof sample[key] === 'number');
  
  const isTimeSeries = categoryKey && (categoryKey.toLowerCase().includes('date') || categoryKey.toLowerCase().includes('timestamp') || categoryKey.toLowerCase().includes('day'));

  return { categoryKey, valueKeys, isTimeSeries };
};

// <-- PERUBAHAN: Fungsi baru untuk diekspor, memeriksa apakah data bisa di-chart -->
export const isDataChartable = (data: any[]): boolean => {
    if (!data || data.length === 0) return false;

    // Pastikan semua item adalah objek dan ada setidaknya satu kunci numerik
    const sample = data[0];
    if (typeof sample !== 'object' || sample === null) return false;

    const keys = Object.keys(sample);
    const hasNumericKey = keys.some(key => typeof sample[key] === 'number');

    return hasNumericKey;
}

export function EmotionChart({ data }: EmotionChartProps) {
  const { categoryKey, valueKeys, isTimeSeries } = useMemo(() => parseDataKeys(data), [data]);

  // Tampilan KPI
  if (data.length === 1 && valueKeys.length === 1) {
    const key = valueKeys[0];
    const value = data[0][key];
    const label = key.replace(/_/g, ' ').replace(/\(\*\)/g, 'Total');

    return (
      <Card className="bg-muted/30">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium capitalize">{label}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-4xl font-bold">{value.toLocaleString()}</div>
        </CardContent>
      </Card>
    )
  }

  // Tampilan Grafik Area
  if (isTimeSeries && categoryKey && valueKeys.length > 0) {
    return (
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted-foreground) / 0.3)" />
          <XAxis dataKey={categoryKey} stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false}/>
          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `${value}`}/>
          <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', borderRadius: '0.5rem' }}/>
          <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
          {valueKeys.map((key, index) => (
             <Area key={key} type="monotone" dataKey={key} stackId="1" stroke={`hsl(var(--primary-h) ${-20 + index*40} ${40 + index*10})`} fill={`hsl(var(--primary-h) ${-20 + index*40} ${50 + index*10} / 0.4)`} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  // Tampilan Grafik Batang
  if (categoryKey && valueKeys.length > 0) {
    return (
      <ResponsiveContainer width="100%" height={250}>
        <RechartsBarChart data={data} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--muted-foreground) / 0.3)" />
          <XAxis dataKey={categoryKey} stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false}/>
          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false}/>
          <Tooltip contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', borderRadius: '0.5rem' }}/>
          <Legend wrapperStyle={{ fontSize: '0.8rem' }} />
          {valueKeys.map((key, index) => (
            <Bar key={key} dataKey={key} fill={`hsl(var(--primary-h) ${-20 + index*40} ${50 + index*10})`} radius={[4, 4, 0, 0]} />
          ))}
        </RechartsBarChart>
      </ResponsiveContainer>
    );
  }

  // <-- PERUBAHAN: Fallback sekarang tidak mengembalikan apa-apa -->
  return null;
}