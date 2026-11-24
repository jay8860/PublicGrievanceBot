// Recharts wrappers with a consistent district-admin look.
import React from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

export const PALETTE = ['#27425f', '#486a8b', '#557059', '#967a3d', '#9d5145', '#665984', '#4b7484', '#7e776f'];

const AXIS = { tick: { fontSize: 11, fill: '#7e776f' }, axisLine: false, tickLine: false };
const GRID = { stroke: '#e7e3da' };
const TOOLTIP = {
  contentStyle: { fontSize: 11, borderRadius: 3, border: '1px solid #e7e3da', color: '#302b25' },
  labelStyle: { fontSize: 11, color: '#5f5951' },
};

export function TrendChart({ data, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="date" {...AXIS} tickFormatter={(v) => String(v).slice(5)} />
        <YAxis {...AXIS} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Area type="monotone" dataKey="created" name="Received" stroke="#27425f"
          strokeWidth={1.5} fill="#27425f" fillOpacity={0.06} />
        <Area type="monotone" dataKey="resolved" name="Resolved" stroke="#557059"
          strokeWidth={1.5} fill="#557059" fillOpacity={0.06} />
      </AreaChart>
    </ResponsiveContainer>
  );
}


export function MonthlyChart({ data, height = 280 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey="month" {...AXIS} />
        <YAxis {...AXIS} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line type="monotone" dataKey="created" name="Received" stroke="#27425f"
          strokeWidth={1.5} dot={{ r: 2.5 }} />
        <Line type="monotone" dataKey="resolved" name="Resolved" stroke="#557059"
          strokeWidth={1.5} dot={{ r: 2.5 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function BarsChart({ data, xKey, series, height = 280, layout = 'horizontal' }) {
  const vertical = layout === 'vertical';
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={layout} margin={{ top: 8, right: 12, left: vertical ? 8 : -18, bottom: 0 }}>
        <CartesianGrid {...GRID} horizontal={!vertical} vertical={vertical} />
        {vertical
          ? <XAxis type="number" {...AXIS} allowDecimals={false} />
          : <XAxis dataKey={xKey} {...AXIS} interval={0} tickFormatter={(v) => (String(v).length > 14 ? `${String(v).slice(0, 13)}…` : v)} />}
        {vertical
          ? <YAxis type="category" dataKey={xKey} {...AXIS} width={120} />
          : <YAxis {...AXIS} allowDecimals={false} />}
        <Tooltip {...TOOLTIP} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {series.map((entry, index) => (
          <Bar key={entry.key} dataKey={entry.key} name={entry.name}
            fill={entry.color || PALETTE[index % PALETTE.length]} radius={[2, 2, 0, 0]} maxBarSize={32} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DonutChart({ data, nameKey, valueKey, height = 240, colors = PALETTE }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey={valueKey} nameKey={nameKey} innerRadius="58%" outerRadius="80%"
          paddingAngle={0} strokeWidth={1} stroke="#ffffff">
          {data.map((entry, index) => (
            <Cell key={entry[nameKey]} fill={colors[index % colors.length]} />
          ))}
        </Pie>
        <Tooltip {...TOOLTIP} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}
