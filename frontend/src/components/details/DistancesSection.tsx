import { School, Bus, TreePine, Droplets, ShoppingCart, Pill } from 'lucide-react';
import type { ParcelData } from '@/stores/detailsPanelStore';

function formatDistance(d: number | null | undefined): string {
  if (d == null) return '-';
  if (d < 1000) return `${Math.round(d)}m`;
  return `${(d / 1000).toFixed(1)}km`;
}

export function DistancesSection({ parcelData }: { parcelData: ParcelData }) {
  const distances = [
    { icon: School, label: 'Szkoła', value: parcelData.dist_to_school },
    { icon: Bus, label: 'Przystanek', value: parcelData.dist_to_bus_stop },
    { icon: TreePine, label: 'Las', value: parcelData.dist_to_forest },
    { icon: Droplets, label: 'Woda', value: parcelData.dist_to_water },
    { icon: ShoppingCart, label: 'Sklep', value: parcelData.dist_to_shop || parcelData.dist_to_supermarket },
    { icon: Pill, label: 'Apteka', value: parcelData.dist_to_pharmacy },
  ].filter((d) => d.value != null);

  if (distances.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Odległości</h3>
      <div className="space-y-2">
        {distances.map((item) => (
          <div key={item.label} className="flex items-center justify-between py-1.5 px-2 rounded-lg bg-white/3 hover:bg-white/5 transition-colors">
            <div className="flex items-center gap-2">
              <item.icon className="w-3.5 h-3.5 text-slate-500" />
              <span className="text-xs text-slate-400">{item.label}</span>
            </div>
            <span className="text-xs font-medium text-white">{formatDistance(item.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
