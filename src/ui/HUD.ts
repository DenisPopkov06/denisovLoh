import type { ItemId } from "@/systems/InventorySystem";
import { icon, ITEM_ICON_NAME } from "@/ui/icons";

export interface HUDTask {
  label: string;
  done: boolean;
}

/** Предмет из хотбара (1-5) с горячей клавишей — null в hotkey, если у предмета
 *  её нет (зарезервировано на будущее, сейчас у всех есть). */
export interface HUDHotbarItem {
  id: ItemId;
  hotkey: string;
  remaining: number;
}

export interface HUDState {
  flashlightChargePercent: number;
  flashlightOn: boolean;
  remainingSec: number;
  tasks: HUDTask[];
  interactionPrompt: string | null;
  pointerLocked: boolean;
  staminaPercent: number;
  healthPercent: number;
  /** Скрыта, пока зомби ещё не появился (ZombieSystem) — показывать полоску жизней
   *  раньше времени нечего, угрозы для неё ещё нет. */
  healthVisible: boolean;
  /** Игрок у двери дома — вместо обычной подсказки кнопка "E — магазин" (на тач-экране
   *  по ней можно тапнуть, клавиши E там нет). */
  shopPromptVisible: boolean;
  /** null — сейчас ничего не ремонтируется (InteractionSystem.getRepairProgress). */
  repairProgressPercent: number | null;
  /** Запас предметов (InventorySystem) — хотбар под прицелом, у каждого своя клавиша. */
  hotbar: HUDHotbarItem[];
}

const LOW_TIME_THRESHOLD_SEC = 30;

function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.ceil(seconds));
  const minutes = Math.floor(whole / 60);
  const secs = whole % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

/** Сериализация задач для дешёвого сравнения "изменился ли список" между кадрами. */
function serializeTasks(tasks: HUDTask[]): string {
  return tasks.map((t) => `${t.label}:${t.done}`).join("|");
}

export class HUD {
  private readonly root: HTMLElement;
  private readonly flashlightBar: HTMLElement;
  private readonly flashlightHint: HTMLElement;
  private readonly timerEl: HTMLElement;
  private readonly taskListEl: HTMLElement;
  private readonly promptEl: HTMLElement;
  private readonly pointerLockHint: HTMLElement;
  private readonly staminaBar: HTMLElement;
  private readonly healthBar: HTMLElement;
  private readonly healthEl: HTMLElement;
  private readonly shopButton: HTMLButtonElement;
  private readonly repairBar: HTMLElement;
  private readonly repairFill: HTMLElement;
  private readonly hotbarEl: HTMLElement;
  private readonly hitMarker: HTMLElement;
  private lastShopPromptVisible: boolean | null = null;
  private lastRepairPercent: number | null = null;
  private lastHotbarSignature = "";
  private hitMarkerTimeout: ReturnType<typeof setTimeout> | null = null;

  private lastChargePercent = -1;
  private lastStaminaPercent = -1;
  private lastHealthPercent = -1;
  private lastHealthVisible: boolean | null = null;
  private lastPointerLocked: boolean | null = null;
  private lastTimerText = "";
  private lastTasksSignature = "";
  private lastIsLowTime = false;
  private flashlightUsedOnce = false;
  private lastPrompt: string | null = "";

  constructor(parent: HTMLElement, onShopClick: () => void = () => {}) {
    this.root = document.createElement("div");
    this.root.className = "hud";

    const flashlight = document.createElement("div");
    flashlight.className = "hud__flashlight";
    this.flashlightBar = document.createElement("div");
    this.flashlightBar.className = "hud__flashlight-bar";
    flashlight.appendChild(this.flashlightBar);

    this.flashlightHint = document.createElement("div");
    this.flashlightHint.className = "hud__hint";
    this.flashlightHint.textContent = "F — фонарик";

    this.timerEl = document.createElement("div");
    this.timerEl.className = "hud__timer";

    this.taskListEl = document.createElement("ul");
    this.taskListEl.className = "hud__tasks";

    this.promptEl = document.createElement("div");
    this.promptEl.className = "hud__prompt";

    this.pointerLockHint = document.createElement("div");
    this.pointerLockHint.className = "hud__hint hud__hint--pointer-lock";
    this.pointerLockHint.textContent = "Клик — захватить курсор для обзора";

    const stamina = document.createElement("div");
    stamina.className = "hud__stamina";
    this.staminaBar = document.createElement("div");
    this.staminaBar.className = "hud__stamina-bar";
    stamina.appendChild(this.staminaBar);

    this.healthEl = document.createElement("div");
    this.healthEl.className = "hud__health";
    this.healthBar = document.createElement("div");
    this.healthBar.className = "hud__health-bar";
    this.healthEl.appendChild(this.healthBar);

    this.shopButton = document.createElement("button");
    this.shopButton.type = "button";
    this.shopButton.className = "hud__shop-button";
    this.shopButton.textContent = "E — магазин";
    this.shopButton.style.display = "none";
    this.shopButton.addEventListener("click", () => onShopClick());

    // Полоса прогресса ремонта (InteractionSystem.getRepairProgress) — раньше
    // прогресс никак не был виден, кроме текста "Удерживайте E…": навык "Ремонт"
    // (быстрее лопатой) было физически невозможно заметить в игре. Теперь выше
    // уровень — быстрее заполняется эта полоса под прицелом.
    this.repairBar = document.createElement("div");
    this.repairBar.className = "hud__repair";
    this.repairBar.style.display = "none";
    this.repairFill = document.createElement("div");
    this.repairFill.className = "hud__repair-fill";
    this.repairBar.appendChild(this.repairFill);

    this.hotbarEl = document.createElement("div");
    this.hotbarEl.className = "hud__hotbar";

    this.hitMarker = document.createElement("div");
    this.hitMarker.className = "hud__hit-marker";

    this.root.append(
      flashlight,
      stamina,
      this.healthEl,
      this.flashlightHint,
      this.timerEl,
      this.taskListEl,
      this.promptEl,
      this.repairBar,
      this.pointerLockHint,
      this.shopButton,
      this.hotbarEl,
      this.hitMarker,
    );
    parent.appendChild(this.root);
  }

  update(state: HUDState): void {
    this.setFlashlightCharge(state.flashlightChargePercent);
    this.setFlashlightHint(state.flashlightOn);
    this.setTimeRemaining(state.remainingSec);
    this.setTaskList(state.tasks);
    this.setInteractionPrompt(state.shopPromptVisible ? null : state.interactionPrompt);
    this.setShopPrompt(state.shopPromptVisible);
    this.setPointerLockHint(state.pointerLocked);
    this.setStamina(state.staminaPercent);
    this.setHealth(state.healthPercent, state.healthVisible);
    this.setRepairProgress(state.repairProgressPercent);
    this.setHotbar(state.hotbar);
  }

  private setRepairProgress(percent: number | null): void {
    if (percent === this.lastRepairPercent) return;
    this.lastRepairPercent = percent;
    this.repairBar.style.display = percent === null ? "none" : "";
    if (percent !== null) this.repairFill.style.width = `${Math.round(Math.max(0, Math.min(1, percent)) * 100)}%`;
  }

  private setHotbar(items: HUDHotbarItem[]): void {
    const signature = items.map((item) => `${item.id}:${item.hotkey}:${item.remaining}`).join("|");
    if (signature === this.lastHotbarSignature) return;
    this.lastHotbarSignature = signature;

    this.hotbarEl.replaceChildren(
      ...items.map((item) => {
        const slot = document.createElement("div");
        slot.className = "hud__hotbar-slot";
        slot.classList.toggle("hud__hotbar-slot--empty", item.remaining <= 0);

        const iconBox = document.createElement("span");
        iconBox.className = "hud__hotbar-icon";
        iconBox.appendChild(icon(ITEM_ICON_NAME[item.id], "hud__hotbar-svg"));

        const key = document.createElement("span");
        key.className = "hud__hotbar-key";
        key.textContent = item.hotkey;

        const count = document.createElement("span");
        count.className = "hud__hotbar-count";
        count.textContent = String(Math.round(item.remaining));

        slot.append(iconBox, key, count);
        return slot;
      }),
    );
  }

  /** Короткая вспышка прицела — обратная связь для выстрела из пистолета. */
  showHitMarker(): void {
    this.hitMarker.classList.remove("hud__hit-marker--active");
    // Форсируем reflow, чтобы повторный выстрел перезапускал анимацию, а не
    // продолжал уже идущую (classList.add сразу после remove иначе не сработает).
    void this.hitMarker.offsetWidth;
    this.hitMarker.classList.add("hud__hit-marker--active");
    if (this.hitMarkerTimeout) clearTimeout(this.hitMarkerTimeout);
    this.hitMarkerTimeout = setTimeout(() => this.hitMarker.classList.remove("hud__hit-marker--active"), 220);
  }

  private setFlashlightCharge(percent: number): void {
    const rounded = Math.round(Math.max(0, Math.min(100, percent)));
    if (rounded === this.lastChargePercent) return;
    this.lastChargePercent = rounded;
    this.flashlightBar.style.width = `${rounded}%`;
  }

  private setStamina(percent: number): void {
    const rounded = Math.round(Math.max(0, Math.min(100, percent)));
    if (rounded === this.lastStaminaPercent) return;
    this.lastStaminaPercent = rounded;
    this.staminaBar.style.width = `${rounded}%`;
  }

  private setHealth(percent: number, visible: boolean): void {
    if (visible !== this.lastHealthVisible) {
      this.lastHealthVisible = visible;
      this.healthEl.style.display = visible ? "" : "none";
    }
    const rounded = Math.round(Math.max(0, Math.min(100, percent)));
    if (rounded === this.lastHealthPercent) return;
    this.lastHealthPercent = rounded;
    this.healthBar.style.width = `${rounded}%`;
    this.healthEl.classList.toggle("hud__health--low", rounded <= 30);
  }

  /** Подсказка клавиши видна, пока игрок ни разу не включил фонарик — он выключен
   *  по умолчанию (решение дизайнера), без подсказки не всем очевидно, что делать. */
  private setFlashlightHint(flashlightOn: boolean): void {
    if (flashlightOn) this.flashlightUsedOnce = true;
    this.flashlightHint.style.display = this.flashlightUsedOnce ? "none" : "";
  }

  private setTaskList(tasks: HUDTask[]): void {
    const signature = serializeTasks(tasks);
    if (signature === this.lastTasksSignature) return;
    this.lastTasksSignature = signature;

    this.taskListEl.replaceChildren(
      ...tasks.map((task) => {
        const item = document.createElement("li");
        item.className = task.done ? "hud__task-item hud__task-item--done" : "hud__task-item";

        const checkbox = document.createElement("span");
        checkbox.className = "hud__task-checkbox";
        checkbox.textContent = task.done ? "✓" : "";

        const label = document.createElement("span");
        label.className = "hud__task-label";
        label.textContent = task.label;

        item.append(checkbox, label);
        return item;
      }),
    );
  }

  private setTimeRemaining(seconds: number): void {
    const text = formatTime(seconds);
    if (text !== this.lastTimerText) {
      this.lastTimerText = text;
      this.timerEl.textContent = text;
    }

    const isLowTime = seconds <= LOW_TIME_THRESHOLD_SEC;
    if (isLowTime !== this.lastIsLowTime) {
      this.lastIsLowTime = isLowTime;
      this.timerEl.classList.toggle("hud__timer--low", isLowTime);
    }
  }

  private setInteractionPrompt(prompt: string | null): void {
    if (prompt === this.lastPrompt) return;
    this.lastPrompt = prompt;
    this.promptEl.textContent = prompt ?? "";
    this.promptEl.style.display = prompt ? "" : "none";
  }

  private setShopPrompt(visible: boolean): void {
    if (visible === this.lastShopPromptVisible) return;
    this.lastShopPromptVisible = visible;
    this.shopButton.style.display = visible ? "" : "none";
  }

  /** Без захвата курсора видимая мышь упирается в край экрана — поворот камеры
   *  ограничен и выглядит "сломанным". Явно подсказываем, что нужно кликнуть. */
  private setPointerLockHint(locked: boolean): void {
    if (locked === this.lastPointerLocked) return;
    this.lastPointerLocked = locked;
    this.pointerLockHint.style.display = locked ? "none" : "";
  }

  /** Прячет весь HUD (например, пока открыт магазин — он закрывает собой экран). */
  setHidden(hidden: boolean): void {
    this.root.style.display = hidden ? "none" : "";
  }

  destroy(): void {
    if (this.hitMarkerTimeout) clearTimeout(this.hitMarkerTimeout);
    this.root.remove();
  }
}
