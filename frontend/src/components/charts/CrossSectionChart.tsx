/**
 * Cross-section elevation profile chart.
 * Shows DSM (blue) and DTM (brown dashed) lines with amber fill for heap material.
 */

import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { CrossSectionProfile } from "@/stores/crossSectionStore";

interface ChartDataPoint {
  distance: number;
  dsm_z: number | null;
  dtm_z: number | null;
  height: number | null;
}

interface CrossSectionChartProps {
  profile: CrossSectionProfile;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDataPoint }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const h = d.dsm_z != null && d.dtm_z != null ? d.dsm_z - d.dtm_z : null;
  return (
    <div className="bg-evlos-800 border border-evlos-600 rounded p-2 text-xs font-mono shadow-lg">
      <div className="text-evlos-200">Distanza: {d.distance.toFixed(2)} m</div>
      <div style={{ color: "#3b82f6" }}>DSM: {d.dsm_z?.toFixed(2) ?? "—"} m</div>
      <div style={{ color: "#92400e" }}>DTM: {d.dtm_z?.toFixed(2) ?? "—"} m</div>
      <div style={{ color: "#f59e0b" }}>Altezza: {h != null ? h.toFixed(2) : "—"} m</div>
    </div>
  );
}

export function CrossSectionChart({ profile }: CrossSectionChartProps) {
  const chartData: ChartDataPoint[] = profile.distance.map((d, i) => {
    const dsm = profile.dsm_z[i];
    const dtm = profile.dtm_z[i];
    const height = dsm != null && dtm != null && dsm > dtm ? dsm - dtm : null;
    return { distance: d, dsm_z: dsm, dtm_z: dtm, height };
  });

  // Compute Y domain with padding
  const allZ = chartData
    .flatMap((d) => [d.dsm_z, d.dtm_z])
    .filter((v): v is number => v != null);
  const minZ = allZ.length > 0 ? Math.min(...allZ) - 0.5 : 0;
  const maxZ = allZ.length > 0 ? Math.max(...allZ) + 0.5 : 10;

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 25, left: 15 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a3544" />
        <XAxis
          dataKey="distance"
          tick={{ fontSize: 10, fill: "#9ca3af" }}
          tickFormatter={(v: number) => v.toFixed(0)}
          stroke="#4b5563"
          label={{
            value: "Distanza (m)",
            position: "insideBottom",
            offset: -10,
            style: { fontSize: 10, fill: "#9ca3af" },
          }}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#9ca3af" }}
          tickFormatter={(v: number) => v.toFixed(1)}
          stroke="#4b5563"
          domain={[minZ, maxZ]}
          label={{
            value: "Quota (m)",
            angle: -90,
            position: "insideLeft",
            offset: 5,
            style: { fontSize: 10, fill: "#9ca3af" },
          }}
        />
        <Tooltip content={<CustomTooltip />} />

        {/* DSM filled area above DTM */}
        <Area
          type="monotone"
          dataKey="dsm_z"
          stroke="none"
          fill="#f59e0b"
          fillOpacity={0.2}
          connectNulls={false}
          isAnimationActive={false}
        />

        {/* DTM line — brown dashed */}
        <Line
          type="monotone"
          dataKey="dtm_z"
          stroke="#92400e"
          dot={false}
          strokeWidth={1.5}
          strokeDasharray="4 2"
          connectNulls={false}
          isAnimationActive={false}
          name="DTM"
        />

        {/* DSM line — blue solid */}
        <Line
          type="monotone"
          dataKey="dsm_z"
          stroke="#3b82f6"
          dot={false}
          strokeWidth={2}
          connectNulls={false}
          isAnimationActive={false}
          name="DSM"
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
