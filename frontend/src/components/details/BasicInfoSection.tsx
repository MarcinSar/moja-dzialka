import type { ParcelData } from '@/stores/detailsPanelStore';

export function BasicInfoSection({ parcelData }: { parcelData: ParcelData }) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Dane podstawowe</h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <span className="text-[10px] text-slate-500">ID działki</span>
          <p className="text-white font-mono text-xs">{parcelData.id_dzialki}</p>
        </div>
        <div>
          <span className="text-[10px] text-slate-500">Powierzchnia</span>
          <p className="text-white font-medium text-sm">
            {parcelData.area_m2?.toLocaleString('pl-PL')} m²
          </p>
        </div>
        <div>
          <span className="text-[10px] text-slate-500">Gmina</span>
          <p className="text-white text-sm">{parcelData.gmina || '-'}</p>
        </div>
        <div>
          <span className="text-[10px] text-slate-500">Dzielnica</span>
          <p className="text-white text-sm">{parcelData.dzielnica || parcelData.miejscowosc || '-'}</p>
        </div>
      </div>

      {/* Categories */}
      <div className="flex flex-wrap gap-1.5 mt-2">
        {parcelData.is_built != null && (
          <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
            parcelData.is_built ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400'
          }`}>
            {parcelData.is_built ? 'Zabudowana' : 'Niezabudowana'}
          </span>
        )}
        {parcelData.kategoria_ciszy && (
          <span className="px-2 py-0.5 rounded text-[10px] bg-teal-500/15 text-teal-400">
            {parcelData.kategoria_ciszy}
          </span>
        )}
        {parcelData.gestosc_zabudowy && (
          <span className="px-2 py-0.5 rounded text-[10px] bg-slate-500/15 text-slate-400">
            {parcelData.gestosc_zabudowy}
          </span>
        )}
      </div>
    </div>
  );
}
