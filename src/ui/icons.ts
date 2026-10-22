/** Пиктограммы 24×24. Навыки (run/jump/flashlight/health/stamina/star/bag/back/
 *  lantern) — залитые силуэты одним цветом (currentColor): класс "f" — заливка,
 *  "cut" — вырез цветом подложки, "glow" — тёплая подсветка. Предметы магазина —
 *  цветные, по референсу дизайнера (физический вид, не просто контур): свои
 *  фиксированные fill-цвета вместо currentColor. */
const SVG_NS = "http://www.w3.org/2000/svg";

export const ICONS: Record<string, string> = {
  star: '<path class="f" d="M12 2.2l2.95 6.1 6.7.95-4.85 4.7 1.15 6.65L12 17.45l-5.95 3.15 1.15-6.65L2.35 9.25l6.7-.95z"/>',
  bag: '<path class="f" d="M8.6 2.6c1.2.7 2.2-.3 3.4-.3s2.2 1 3.4.3l-1.7 3.6h-3.4z"/><path class="f" d="M9.2 7.1h5.6c3.6 2.8 5.9 6.4 5.9 9.6 0 2.9-2 4.8-5 4.8H8.3c-3 0-5-1.9-5-4.8 0-3.2 2.3-6.8 5.9-9.6z"/><path class="cut" d="M12 10.6v8M14.1 12.1c-.4-.7-1.1-1-2.1-1-1.2 0-2 .6-2 1.5 0 2 4.2 1 4.2 3 0 .9-.9 1.6-2.2 1.6-1 0-1.8-.4-2.2-1.1"/>',
  lantern: '<path class="f" d="M9.5 2.5h5v1.6h-5zM8 5h8l-1.2 2.2v9.6L16 19H8l1.2-2.2V7.2z"/><path class="f" d="M7.5 19.6h9v1.9h-9z"/><path class="glow" d="M12 9.2c1.3 1.4 1.6 2.6 1.6 3.6a1.6 1.6 0 0 1-3.2 0c0-1 .3-2.2 1.6-3.6z"/>',
  back: '<path d="M14.5 5.5L8 12l6.5 6.5"/>',
  run: '<circle class="f" cx="15.2" cy="3.9" r="2.2"/><path d="M8.3 21.2l2.6-5.2 3 2.3-.5 3.9M5 10.6l3.6-2.6 4 .4 2.4 3.4 3.6 1M11 15.6l1.8-6.4"/>',
  jump: '<circle class="f" cx="13.6" cy="3.6" r="2.2"/><path d="M12.6 7.4l-1.6 6.6M6.2 9.6l3.2-2.4 3.4.4 2.4 2.8 3.2.4M11 14l3.6 2.2-.6 4.8M11 14l-3 3.4-3.4.4"/>',
  flashlight: '<path class="f" d="M7.6 2.6h8.8v3.6l-2.3 3.1v11.4a1.6 1.6 0 0 1-1.6 1.6h-1a1.6 1.6 0 0 1-1.6-1.6V9.3L7.6 6.2z"/><path class="cut" d="M11 12.6h2"/>',
  health: '<path class="f" d="M12 21.2S2.6 15.6 2.6 9.1A4.9 4.9 0 0 1 12 6.8a4.9 4.9 0 0 1 9.4 2.3c0 6.5-9.4 12.1-9.4 12.1z"/><path class="cut" d="M12 10.3v6.2M8.9 13.4h6.2"/>',
  stamina: '<path d="M12 2.4v8.8M12 11.2c-.9 1-2.1 1.2-3 .4M12 11.2c.9 1 2.1 1.2 3 .4"/><path class="f" d="M9.6 6.4C5.8 6.6 3 12.4 3 17.4c0 2.5 1.4 3.9 3.4 3.9 2.2 0 3.4-1.3 3.4-3.7v-6.5zM14.4 6.4c3.8.2 6.6 6 6.6 11 0 2.5-1.4 3.9-3.4 3.9-2.2 0-3.4-1.3-3.4-3.7v-6.5z"/>',
  // Монохромная версия для строки навыка "Ремонт" (currentColor, как остальные
  // skill-иконки) — отдельно от цветной "shovel" ниже (карточка в магазине/хотбар).
  shovelSkill: '<path d="M12 2.4v10.6"/><path class="f" d="M7.5 12.4h9l-1.15 4.9a3.5 3.5 0 0 1-3.4 2.7h-.0a3.5 3.5 0 0 1-3.4-2.7z"/>',

  // --- предметы магазина: цветные, фиксированная палитра (не currentColor) ---
  shovel:
    '<rect x="10.4" y="1.8" width="2" height="11" rx="1" fill="#8a5a33"/>' +
    '<path d="M6.3 11.4h11.4l-1.3 5.6a4 4 0 0 1-3.9 3.1h-.9a4 4 0 0 1-3.9-3.1z" fill="#9aa0a6"/>' +
    '<path d="M6.3 11.4h11.4l-.35 1.5h-10.7z" fill="#c7cbd1"/>',
  pistol:
    '<path d="M3 13.4h10v-3.1a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2.7a1.8 1.8 0 0 1-1.8 1.8h-2.2v3.4a1 1 0 0 1-1 1H9l-1.3 2.7H5l1.1-2.7H4a1 1 0 0 1-1-1z" fill="#34373c"/>' +
    '<path d="M4.4 12.7h8.4" stroke="#6b6f76" stroke-width="0.7" fill="none"/>',
  flashlightItem:
    '<rect x="3" y="10.6" width="2.6" height="2.8" rx="0.5" fill="#1c1e22"/>' +
    '<rect x="5.3" y="10" width="10.4" height="4" rx="1.4" fill="#2b2e33"/>' +
    '<circle cx="18" cy="12" r="3.3" fill="#e7f4ff"/>' +
    '<circle cx="18" cy="12" r="3.3" fill="none" stroke="#8fd1ff" stroke-width="0.7"/>',
  medkit:
    '<rect x="3" y="8.6" width="18" height="11.2" rx="1.8" fill="#c23b3b"/>' +
    '<rect x="8.4" y="5.4" width="7.2" height="4" rx="1.1" fill="none" stroke="#7a1f1f" stroke-width="1.4"/>' +
    '<rect x="10.6" y="11.6" width="2.8" height="7" fill="#f4f0e8"/>' +
    '<rect x="8.3" y="13.8" width="7.4" height="2.8" fill="#f4f0e8"/>',
  crowbar:
    '<path d="M5.3 19.3 16.7 5.7" stroke="#a82f2a" stroke-width="2.6" stroke-linecap="round"/>' +
    '<path d="M5.3 19.3 7.5 17.6" stroke="#c7c9cc" stroke-width="2.6" stroke-linecap="round"/>' +
    '<path d="M15.4 7 17.1 4.9" stroke="#c7c9cc" stroke-width="2.6" stroke-linecap="round"/>',
  ammo:
    '<rect x="3" y="8.2" width="18" height="11" rx="1.3" fill="#5c6b3f"/>' +
    '<rect x="3" y="8.2" width="18" height="2.6" fill="#48542f"/>' +
    '<rect x="9.3" y="5.3" width="5.4" height="3.2" rx="0.5" fill="#3c4527"/>' +
    '<rect x="5.3" y="12.6" width="2" height="3" fill="#2f3620"/>' +
    '<rect x="16.7" y="12.6" width="2" height="3" fill="#2f3620"/>',
  bandage:
    '<ellipse cx="9" cy="10.3" rx="5.2" ry="5.2" fill="#c9cbce"/>' +
    '<ellipse cx="9" cy="10.3" rx="2.5" ry="2.5" fill="#8d9094"/>' +
    '<rect x="8" y="14.7" width="11" height="3.2" rx="0.8" fill="#dcdee0" transform="rotate(10 8 14.7)"/>',
  trap:
    '<ellipse cx="12" cy="18.6" rx="8.2" ry="1.5" fill="#2a2a2e"/>' +
    '<path d="M4.8 18.2 9 7.2M19.2 18.2 15 7.2" stroke="#3a3a3e" stroke-width="2" fill="none"/>' +
    '<path d="M6.7 18.2 9.9 9.6M17.3 18.2 14.1 9.6" stroke="#55565c" stroke-width="1.6" fill="none"/>',
  key:
    '<circle cx="8" cy="7.4" r="2.7" fill="none" stroke="#c9a227" stroke-width="1.8"/>' +
    '<path d="M9.4 9.2 17.2 17" stroke="#c9a227" stroke-width="1.8" stroke-linecap="round" fill="none"/>' +
    '<path d="M17.2 17 19.6 14.6M17.2 17 18.9 18.7" stroke="#c9a227" stroke-width="1.8" stroke-linecap="round" fill="none"/>' +
    '<path d="M13.6 13.4 15.4 15.2" stroke="#c9a227" stroke-width="1.6" stroke-linecap="round" fill="none"/>',
};

/** Имя пиктограммы (ICONS) для каждого предмета (InventorySystem.ItemId) — общее
 *  между ShopScreen (карточка) и HUD (хотбар), чтобы иконка предмета не разъезжалась
 *  между экранами. */
export const ITEM_ICON_NAME: Record<string, string> = {
  shovel: "shovel",
  pistol: "pistol",
  flashlightItem: "flashlightItem",
  medkit: "medkit",
  crowbar: "crowbar",
  ammo: "ammo",
  bandage: "bandage",
  key: "key",
  trap: "trap",
};

export function icon(name: string, className: string): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", className);
  svg.innerHTML = ICONS[name] ?? "";
  return svg;
}
