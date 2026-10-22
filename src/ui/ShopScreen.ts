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

/** Пиктограммы 24×24 — залитые серые силуэты, как на референсе магазина.
 *  Класс "f" — заливка, остальное — толстая обводка (руки/ноги фигурок). */
const ICONS: Record<string, string> = {
  star: '<path class="f" d="M12 2.2l2.95 6.1 6.7.95-4.85 4.7 1.15 6.65L12 17.45l-5.95 3.15 1.15-6.65L2.35 9.25l6.7-.95z"/>',
  bag: '<path class="f" d="M8.6 2.6c1.2.7 2.2-.3 3.4-.3s2.2 1 3.4.3l-1.7 3.6h-3.4z"/><path class="f" d="M9.2 7.1h5.6c3.6 2.8 5.9 6.4 5.9 9.6 0 2.9-2 4.8-5 4.8H8.3c-3 0-5-1.9-5-4.8 0-3.2 2.3-6.8 5.9-9.6z"/><path class="cut" d="M12 10.6v8M14.1 12.1c-.4-.7-1.1-1-2.1-1-1.2 0-2 .6-2 1.5 0 2 4.2 1 4.2 3 0 .9-.9 1.6-2.2 1.6-1 0-1.8-.4-2.2-1.1"/>',
  lantern: '<path class="f" d="M9.5 2.5h5v1.6h-5zM8 5h8l-1.2 2.2v9.6L16 19H8l1.2-2.2V7.2z"/><path class="f" d="M7.5 19.6h9v1.9h-9z"/><path class="glow" d="M12 9.2c1.3 1.4 1.6 2.6 1.6 3.6a1.6 1.6 0 0 1-3.2 0c0-1 .3-2.2 1.6-3.6z"/>',
  back: '<path d="M14.5 5.5L8 12l6.5 6.5"/>',
  run: '<circle class="f" cx="15.2" cy="3.9" r="2.2"/><path d="M8.3 21.2l2.6-5.2 3 2.3-.5 3.9M5 10.6l3.6-2.6 4 .4 2.4 3.4 3.6 1M11 15.6l1.8-6.4"/>',
  jump: '<circle class="f" cx="13.6" cy="3.6" r="2.2"/><path d="M12.6 7.4l-1.6 6.6M6.2 9.6l3.2-2.4 3.4.4 2.4 2.8 3.2.4M11 14l3.6 2.2-.6 4.8M11 14l-3 3.4-3.4.4"/>',
  flashlight: '<path class="f" d="M7.6 2.6h8.8v3.6l-2.3 3.1v11.4a1.6 1.6 0 0 1-1.6 1.6h-1a1.6 1.6 0 0 1-1.6-1.6V9.3L7.6 6.2z"/><path class="cut" d="M11 12.6h2"/>',
  health: '<path class="f" d="M12 21.2S2.6 15.6 2.6 9.1A4.9 4.9 0 0 1 12 6.8a4.9 4.9 0 0 1 9.4 2.3c0 6.5-9.4 12.1-9.4 12.1z"/><path class="cut" d="M12 10.3v6.2M8.9 13.4h6.2"/>',
  stamina: '<path d="M12 2.4v8.8M12 11.2c-.9 1-2.1 1.2-3 .4M12 11.2c.9 1 2.1 1.2 3 .4"/><path class="f" d="M9.6 6.4C5.8 6.6 3 12.4 3 17.4c0 2.5 1.4 3.9 3.4 3.9 2.2 0 3.4-1.3 3.4-3.7v-6.5zM14.4 6.4c3.8.2 6.6 6 6.6 11 0 2.5-1.4 3.9-3.4 3.9-2.2 0-3.4-1.3-3.4-3.7v-6.5z"/>',
  lockpick: '<path class="f" d="M7.6 11.6V5.2a1.4 1.4 0 0 1 2.8 0v5.4h.6V3.6a1.4 1.4 0 0 1 2.8 0v7h.6V5.2a1.4 1.4 0 0 1 2.8 0v6.4h.6V8a1.4 1.4 0 0 1 2.8 0v6.4c0 4.2-3 7.4-7.2 7.4h-1c-2.6 0-4.4-1.3-5.6-3.6l-2.4-4.6a1.5 1.5 0 0 1 2.6-1.5z"/>',
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
    const storeColumn = el("div", "shop__column");
    storeColumn.append(this.buildStorePanel(), this.buildTip());
    panels.append(this.buildSkillsPanel(), storeColumn);
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

    // Вкладки категорий — как на референсе; предметов пока нет, поэтому они только
    // переключают подсветку, а сетка ниже — пустые карточки-заготовки.
    const tabs = el("div", "shop__tabs");
    const tabButtons: HTMLButtonElement[] = [];
    for (const title of ["Все", "Оружие", "Инструменты", "Расходники"]) {
      const tab = el("button", "shop__tab", title);
      tab.type = "button";
      tab.addEventListener("click", () => {
        for (const other of tabButtons) other.classList.toggle("shop__tab--active", other === tab);
      });
      tabButtons.push(tab);
      tabs.appendChild(tab);
    }
    tabButtons[0]?.classList.add("shop__tab--active");
    panel.appendChild(tabs);

    const items = el("div", "shop__items");
    for (let i = 0; i < 8; i++) {
      const card = el("div", "shop__item-slot");
      card.append(
        el("span", "shop__item-ph shop__item-ph--image"),
        el("span", "shop__item-ph shop__item-ph--name"),
        el("span", "shop__item-ph shop__item-ph--line"),
        el("span", "shop__item-ph shop__item-ph--buy"),
      );
      items.appendChild(card);
    }
    items.appendChild(el("p", "shop__items-empty", "Предметы скоро появятся"));
    panel.appendChild(items);
    return panel;
  }

  private buildTip(): HTMLElement {
    const tip = el("div", "shop__tip");
    const tipIcon = el("span", "shop__tip-icon");
    tipIcon.appendChild(icon("lantern", "shop__svg"));
    tip.append(tipIcon, el("p", "shop__tip-text", "Покупайте предметы и улучшайте навыки, чтобы выжить в этом опасном месте."));
    return tip;
  }
}
