import { SKILLS, SKILL_MAX_LEVEL, type SkillId } from "@/systems/SkillSystem";
import { ITEMS, type ItemId } from "@/systems/InventorySystem";
import { icon, ITEM_ICON_NAME } from "@/ui/icons";

export interface ShopSkillState {
  level: number;
  /** null — уровень максимальный. */
  cost: number | null;
}

export interface ShopItemState {
  remaining: number;
  /** null — больше не купить (ключ, если уже есть). */
  cost: number | null;
}

export interface ShopState {
  coins: number;
  skills: Record<SkillId, ShopSkillState>;
  items: Record<ItemId, ShopItemState>;
}

const SKILL_ICON: Record<SkillId, string> = {
  run: "run",
  jump: "jump",
  flashlight: "flashlight",
  health: "health",
  stamina: "stamina",
  repair: "shovelSkill",
};

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

interface ItemRow {
  card: HTMLElement;
  durabilityFill: HTMLElement;
  stockText: HTMLElement;
  price: HTMLElement;
  priceValue: HTMLElement;
  button: HTMLButtonElement;
}

/** Магазин у дома смотрителя (E у двери): слева прокачка навыков, справа — предметы
 *  (патроны/бинты/лопата и т.п., InventorySystem). Пока открыт — игра и таймер смены
 *  на паузе (Game). */
export class ShopScreen {
  private readonly root: HTMLElement;
  private readonly balanceValue: HTMLElement;
  private readonly rows = new Map<SkillId, SkillRow>();
  private readonly itemRows = new Map<ItemId, ItemRow>();
  private visible = false;

  constructor(
    parent: HTMLElement,
    private readonly onUpgrade: (id: SkillId) => void,
    private readonly onClose: () => void,
    private readonly onBuyItem: (id: ItemId) => void,
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

  /** Перерисовывает баланс, строки навыков и предметов (после покупки или при открытии). */
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
    for (const item of ITEMS) {
      const row = this.itemRows.get(item.id);
      const s = state.items[item.id];
      if (!row || !s) continue;
      const fillPercent = Math.round(Math.min(1, s.remaining / item.rechargeAmount) * 100);
      row.durabilityFill.style.width = `${fillPercent}%`;
      row.stockText.textContent = s.remaining > 0 ? `${Math.round(s.remaining)} ${item.unit}` : "Нет в запасе";

      const soldOut = s.cost === null;
      row.price.style.visibility = soldOut ? "hidden" : "";
      row.priceValue.textContent = soldOut ? "" : String(s.cost);
      const affordable = !soldOut && state.coins >= (s.cost ?? 0);
      row.button.textContent = soldOut ? "Есть" : "Купить";
      row.button.disabled = !affordable;
      row.price.classList.toggle("shop__price--short", !soldOut && !affordable);
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

    const items = el("div", "shop__items");
    for (const item of ITEMS) {
      const card = el("div", "shop__item-card");

      const iconBox = el("span", "shop__item-icon");
      iconBox.appendChild(icon(ITEM_ICON_NAME[item.id], "shop__item-svg"));

      const name = el("span", "shop__item-name", item.title);
      const desc = el("p", "shop__item-desc", item.description);

      const durability = el("div", "shop__item-durability");
      const durabilityFill = el("span", "shop__item-durability-fill");
      durability.appendChild(durabilityFill);
      const stockText = el("p", "shop__item-stock");

      const buy = el("div", "shop__item-buy");
      const price = coinTag("shop__price");
      const button = el("button", "shop__upgrade", "Купить");
      button.type = "button";
      button.addEventListener("click", () => this.onBuyItem(item.id));
      buy.append(price.root, button);

      card.append(iconBox, name, desc, durability, stockText, buy);
      items.appendChild(card);
      this.itemRows.set(item.id, { card, durabilityFill, stockText, price: price.root, priceValue: price.value, button });
    }
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
