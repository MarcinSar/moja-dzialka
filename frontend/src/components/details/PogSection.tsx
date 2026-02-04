import type { ParcelData } from '@/stores/detailsPanelStore';

export function PogSection({ parcelData }: { parcelData: ParcelData }) {
  if (!parcelData.has_pog) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider">Plan Ogólny Gminy</h3>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <span className="text-[10px] text-slate-500">Symbol</span>
          <p className="text-white font-medium text-sm">{parcelData.pog_symbol || '-'}</p>
        </div>
        {parcelData.pog_oznaczenie && (
          <div>
            <span className="text-[10px] text-slate-500">Oznaczenie</span>
            <p className="text-white text-xs">{parcelData.pog_oznaczenie}</p>
          </div>
        )}
      </div>

      {parcelData.pog_nazwa && (
        <div>
          <span className="text-[10px] text-slate-500">Przeznaczenie</span>
          <p className="text-white text-xs">{parcelData.pog_nazwa}</p>
        </div>
      )}

      {parcelData.pog_profil_podstawowy_nazwy && (
        <div className="p-2 rounded-lg bg-white/3">
          <span className="text-[10px] text-slate-500 block mb-0.5">Profil</span>
          <p className="text-slate-300 text-xs">{parcelData.pog_profil_podstawowy_nazwy}</p>
        </div>
      )}

      {/* Building parameters */}
      <div className="grid grid-cols-2 gap-2">
        {parcelData.pog_maks_wysokosc_m != null && (
          <div>
            <span className="text-[10px] text-slate-500">Max wys.</span>
            <p className="text-white text-xs">{parcelData.pog_maks_wysokosc_m} m</p>
          </div>
        )}
        {parcelData.pog_maks_zabudowa_pct != null && (
          <div>
            <span className="text-[10px] text-slate-500">Max zabudowa</span>
            <p className="text-white text-xs">{parcelData.pog_maks_zabudowa_pct}%</p>
          </div>
        )}
        {parcelData.pog_min_bio_pct != null && (
          <div>
            <span className="text-[10px] text-slate-500">Min bio</span>
            <p className="text-white text-xs">{parcelData.pog_min_bio_pct}%</p>
          </div>
        )}
      </div>

      {/* Residential zone badge */}
      <div className="flex items-center gap-2">
        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
          parcelData.is_residential_zone
            ? 'bg-emerald-500/20 text-emerald-400'
            : 'bg-slate-500/20 text-slate-400'
        }`}>
          {parcelData.is_residential_zone ? 'Strefa mieszkaniowa' : 'Nie-mieszkaniowa'}
        </span>
      </div>
    </div>
  );
}
