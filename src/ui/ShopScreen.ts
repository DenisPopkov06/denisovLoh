import { SKILLS, SKILL_MAX_LEVEL, type SkillId } from "@/systems/SkillSystem";

export interface ShopSkillState {
  level: number;
  /** null — уровень максимальный. */
  cost: number | null;
}

export interface ShopState {
  coins: number;
  skills: Record<SkillId, ShopSkillState>;
}

const SVG_NS = "http://www.w3.org/2000/svg";

/** Контурные иконки 24×24 (stroke = currentColor) — как пиктограммы на референсе магазина. */
const ICONS: Record<string, string> = {
  star: '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
  bag: '<path d="M9 3.5h6l-1.6 3.2h-2.8z"/><path d="M8.2 6.7h7.6c3 3 4.7 6 4.7 9a4.8 4.8 0 0 1-4.8 4.8H8.3a4.8 4.8 0 0 1-4.8-4.8c0-3 1.7-6 4.7-9z"/><path d="M12 10.5v7M14 12c-.3-.8-1-1.2-2-1.2s-2 .6-2 1.5 1 1.3 2 1.5 2 .6 2 1.5-1 1.5-2 1.5-1.7-.4-2-1.2"/>',
  lantern: '<path d="M10 2.5h4M12 2.5v2M8.5 4.5h7l-1 2v9.5l1 2h-7l1-2V6.5z"/><path d="M12 9v4.5"/>',
  back: '<path d="M14.5 5.5L8 12l6.5 6.5"/>',
  run: '<circle cx="14.5" cy="4.2" r="1.9"/><path d="M8 21l2.6-5.6 3 2.4V22M5.5 11.5l3.6-3 3.4.6 2.3 3.2 3.3 1.2M10.6 15.4l1.6-5.1"/>',
  jump: '<circle cx="12" cy="3.8" r="1.9"/><path d="M12 6.8v6.7M7 8.2l5 2.4 5-2.4M8.5 21l3.5-7.5 3.5 7.5M5 18.5h3.5M15.5 18.5H19"/>',
  flashlight: '<path d="M8.5 2.5h7v3.8L13.5 9v11.2a1.3 1.3 0 0 1-1.3 1.3h-.4a1.3 1.3 0 0 1-1.3-1.3V9L8.5 6.3z"/><path d="M11 13.5h2M5 3l1.6 1.4M19 3l-1.6 1.4"/>',
  health: '<path d="M12 20.5s-7.5-4.6-9.2-9.3A4.9 4.9 0 0 1 12 8a4.9 4.9 0 0 1 9.2 3.2C19.5 15.9 12 20.5 12 20.5z"/><path d="M12 10.5v6M9 13.5h6"/>',
  stamina: '<path d="M12 2.5v8.5M12 11c-.8 1-2 1.3-3 .5M12 11c.8 1 2 1.3 3 .5"/><path d="M8.8 6.5C5.6 6.8 3.5 12 3.5 17c0 2.4 1.3 3.5 3.1 3.5 2 0 3.1-1.2 3.1-3.4v-6.2"/><path d="M15.2 6.5c3.2.3 5.3 5.5 5.3 10.5 0 2.4-1.3 3.5-3.1 3.5-2 0-3.1-1.2-3.1-3.4v-6.2"/>',
  lockpick: '<path d="M7 11.5V5.3a1.5 1.5 0 0 1 3 0V10M10 9.5V3.8a1.5 1.5 0 0 1 3 0v6M13 10V5.3a1.5 1.5 0 0 1 3 0V11M16 10.5a1.5 1.5 0 0 1 3 0V14c0 4.1-3 7.5-7 7.5h-.8c-2.9 0-4.8-1.6-6-4l-2-4a1.6 1.6 0 0 1 2.8-1.5L7 14"/>',
};

const SKILL_ICON: Record<SkillId, string> = {
  run: "run",
  jump: "jump",
  flashlight: "flashlight",
  health: "health",
  stamina: "stamina",
  lockpick: "lockpick",
};

function icon(name: string, className: string): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", className);
  svg.innerHTML = ICONS[name] ?? "";
  return svg;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, className: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function coinTag(className: string): { root: HTMLElement; value: HTMLElement } {
  const root = el("span", className);
  const value = el("span", "shop__coin-value");
  root.append(el("span", "shop__coin"), value);
  return { root, value };
}

interface SkillRow {
  level: HTMLElement;
  segments: HTMLElement[];
  price: HTMLElement;
  priceValue: HTMLElement;
  button: HTMLButtonElement;
}

/** Магазин у дома смотрителя (E у двери): слева прокачка навыков, справа — область
 *  под предметы (пока пустая). Пока открыт — игра и таймер смены на паузе (Game). */
export class ShopScreen {
  private readonly root: HTMLElement;
  private readonly balanceValue: HTMLElement;
  private readonly rows = new Map<SkillId, SkillRow>();
  private visible = false;

  constructor(
    parent: HTMLElement,
    private readonly onUpgrade: (id: SkillId) => void,
    private readonly onClose: () => void,
  ) {
    this.root = el("div", "shop");
    this.root.style.display = "none";

    const back = el("button", "shop__back");
    back.type = "button";
    back.append(icon("back", "shop__back-icon"), document.createTextNode("Назад"));
    back.addEventListener("click", () => this.onClose());

    const panels = el("div", "shop__panels");
    panels.append(this.buildSkillsPanel(), this.buildStorePanel());
    this.balanceValue = panels.querySelector(".shop__balance .shop__coin-value") as HTMLElement;

    this.root.append(back, panels);
    parent.appendChild(this.root);
  }

  show(state: ShopState): void {
    this.update(state);
    this.visible = true;
    this.root.style.display = "";
  }

  hide(): void {
    this.visible = false;
    this.root.style.display = "none";
  }

  isVisible(): boolean {
    return this.visible;
  }

  /** Перерисовывает баланс и строки навыков (после покупки или при открытии). */
  update(state: ShopState): void {
    this.balanceValue.textContent = String(state.coins);
    for (const skill of SKILLS) {
      const row = this.rows.get(skill.id);
      const s = state.skills[skill.id];
      if (!row || !s) continue;
      row.level.textContent = `Ур. ${s.level}/${SKILL_MAX_LEVEL}`;
      row.segments.forEach((seg, i) => seg.classList.toggle("shop__seg--on", i < s.level));
      const maxed = s.cost === null;
      row.price.style.visibility = maxed ? "hidden" : "";
      row.priceValue.textContent = maxed ? "" : String(s.cost);
      const affordable = !maxed && state.coins >= (s.cost ?? 0);
      row.button.textContent = maxed ? "Макс." : "Улучшить";
      row.button.disabled = !affordable;
      row.price.classList.toggle("shop__price--short", !maxed && !affordable);
    }
  }

  private buildHeader(iconName: string, title: string, subtitle: string): HTMLElement {
    const header = el("header", "shop__header");
    const iconBox = el("span", "shop__header-icon");
    iconBox.appendChild(icon(iconName, "shop__svg"));
    const text = el("div", "shop__header-text");
    text.append(el("h2", "shop__title", title), el("p", "shop__subtitle", subtitle));
    header.append(iconBox, text);
    return header;
  }

  private buildSkillsPanel(): HTMLElement {
    const panel = el("section", "shop__panel shop__panel--skills");
    panel.appendChild(this.buildHeader("star", "Прокачка", "Улучшайте свои навыки, чтобы выжить дольше"));

    const list = el("ul", "shop__skills");
    for (const skill of SKILLS) {
      const item = el("li", "shop__skill");

      const iconBox = el("span", "shop__skill-icon");
      iconBox.appendChild(icon(SKILL_ICON[skill.id], "shop__svg"));

      const body = el("div", "shop__skill-body");
      const top = el("div", "shop__skill-top");
      const level = el("span", "shop__skill-level");
      top.append(el("span", "shop__skill-name", skill.title), level);
      const progress = el("div", "shop__skill-progress");
      const segments: HTMLElement[] = [];
      for (let i = 0; i < SKILL_MAX_LEVEL; i++) {
        const seg = el("span", "shop__seg");
        segments.push(seg);
        progress.appendChild(seg);
      }
      body.append(top, el("p", "shop__skill-desc", skill.description), progress);

      const buy = el("div", "shop__skill-buy");
      const price = coinTag("shop__price");
      const button = el("button", "shop__upgrade", "Улучшить");
      button.type = "button";
      button.addEventListener("click", () => this.onUpgrade(skill.id));
      buy.append(price.root, button);

      item.append(iconBox, body, buy);
      list.appendChild(item);
      this.rows.set(skill.id, { level, segments, price: price.root, priceValue: price.value, button });
    }
    panel.appendChild(list);
    return panel;
  }

  private buildStorePanel(): HTMLElement {
    const panel = el("section", "shop__panel shop__panel--store");
    const header = this.buildHeader("bag", "Магазин", "Полезные предметы для выживания");
    header.appendChild(coinTag("shop__balance").root);
    panel.appendChild(header);

    // Предметов пока нет — только место под них (сетка пустых ячеек).
    const items = el("div", "shop__items");
    for (let i = 0; i < 8; i++) items.appendChild(el("div", "shop__item-slot"));
    items.appendChild(el("p", "shop__items-empty", "Предметы скоро появятся"));
    panel.appendChild(items);

    const tip = el("div", "shop__tip");
    const tipIcon = el("span", "shop__tip-icon");
    tipIcon.appendChild(icon("lantern", "shop__svg"));
    tip.append(tipIcon, el("p", "shop__tip-text", "Покупайте предметы и улучшайте навыки, чтобы выжить в этом опасном месте."));
    panel.appendChild(tip);
    return panel;
  }
}
