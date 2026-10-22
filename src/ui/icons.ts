/** Общие пиктограммы 24×24 для ShopScreen и HUD (хотбар предметов) — залитые серые
 *  силуэты. Класс "f" — заливка, "cut" — вырез цветом подложки, "glow" — тёплая
 *  подсветка (фонарь). */
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
  shovel: '<path d="M12 2.4v10.6"/><path class="f" d="M7.5 12.4h9l-1.15 4.9a3.5 3.5 0 0 1-3.4 2.7h-.0a3.5 3.5 0 0 1-3.4-2.7z"/>',
  bandage: '<path class="f" d="M4 9.3A5.3 5.3 0 0 1 9.3 4h5.4A5.3 5.3 0 0 1 20 9.3v5.4A5.3 5.3 0 0 1 14.7 20H9.3A5.3 5.3 0 0 1 4 14.7z"/><path class="cut" d="M12 7.3v9.4M7.3 12h9.4"/>',
  medkit: '<path class="f" d="M3.4 9.4a2 2 0 0 1 2-2h13.2a2 2 0 0 1 2 2v8.2a2 2 0 0 1-2 2H5.4a2 2 0 0 1-2-2z"/><path d="M8.6 7.4V6a2 2 0 0 1 2-2h2.8a2 2 0 0 1 2 2v1.4"/><path class="cut" d="M12 10.6v6M9 13.6h6"/>',
  trap: '<ellipse class="f" cx="12" cy="18.6" rx="8.2" ry="1.5"/><path d="M4.8 18.2 9 7.2M19.2 18.2 15 7.2"/><path d="M6.7 18.2 9.9 9.6M17.3 18.2 14.1 9.6"/>',
  pistol: '<path class="f" d="M3.6 13.2h9.8v-3a1 1 0 0 1 1-1h5.2a1 1 0 0 1 1 1v2.4a1.6 1.6 0 0 1-1.6 1.6h-2.2v3.4a1 1 0 0 1-1 1H9.4l-1.1 2.6H5.4l1-2.6H4.6a1 1 0 0 1-1-1z"/>',
  key: '<circle class="f" cx="7.4" cy="12" r="4.1"/><path d="M11.3 12h9.3M16.6 12v3.1M19.7 12v2.1"/>',
};

/** Имя пиктограммы (ICONS) для каждого предмета (InventorySystem.ItemId) — общее
 *  между ShopScreen (карточка) и HUD (хотбар), чтобы иконка предмета не разъезжалась
 *  между экранами. */
export const ITEM_ICON_NAME: Record<string, string> = {
  bandage: "bandage",
  medkit: "medkit",
  trap: "trap",
  shovel: "shovel",
  spareBulb: "flashlight",
  pistol: "pistol",
  key: "key",
};

export function icon(name: string, className: string): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", className);
  svg.innerHTML = ICONS[name] ?? "";
  return svg;
}
